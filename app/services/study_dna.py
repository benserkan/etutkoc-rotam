"""Stage 13 — Çalışma DNA profili.

Öğrencinin çalışma örüntüsünü kendi yapısı içinde analiz eder:
- 7 × 24 saat heatmap (hangi gün/saat aktif)
- Chronotype: morning (06-12) / afternoon (12-18) / evening (18-22) / night (22-06)
- Ders bazlı tamamlama: TaskBookItem'lardan section → book → subject
- Trend: bu hafta vs geçen hafta (yön + delta)
- Peak hour ve peak day

Veri kaynağı:
- Task.completed_at (saat damgası, UTC) ve Task.status=COMPLETED/PARTIAL
- TaskBookItem.book → book.subject (ders bazlı)

Çıktı bir dataclass; sayfada heatmap + bar chart + özet kartlar gösterilir.

Notlar:
- completed_at UTC. Türkiye saatine çevirmek için UTC+3 kayması uygulanır
  (TR_OFFSET_HOURS = 3). DST yok varsayımı.
- Az veri durumunda (window'da < 5 tamamlanmış task) chronotype="bilinmiyor",
  trend "yetersiz_veri" döner.
- Window default 28 gün; haftalık trend için bu/geçen hafta 7'şer gün.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    User,
    UserRole,
)


TR_OFFSET_HOURS = 3  # Türkiye saati (UTC+3, DST yok)
MIN_TASKS_FOR_PROFILE = 5

# Toplu işaretleme tespiti: bir öğrenci günün sonunda topluca tikleme yaptığında
# tüm görevler aynı saate damgalanır → heatmap, chronotype, night_owl gibi
# saat bazlı tüm metrikler bozulur. "≥3 görev ≤5 dakika içinde tamamlandı"
# kümesi → batch sayılır. Batch elemanları için saat değeri completed_at yerine
# Task.scheduled_hour'a düşer; o da yoksa o görev saat bazlı hesaplamalardan
# tamamen dışlanır (sayım/trend bundan etkilenmez).
BATCH_WINDOW_SECONDS = 5 * 60
BATCH_MIN_TASKS = 3

ChronoType = Literal["morning", "afternoon", "evening", "night", "unknown"]
TrendDirection = Literal["up", "down", "flat", "insufficient"]
HourConfidence = Literal["high", "medium", "none"]


CHRONOTYPE_LABELS_TR: dict[str, str] = {
    "morning": "Sabahcı (06-12)",
    "afternoon": "Öğleden sonra (12-18)",
    "evening": "Akşamcı (18-22)",
    "night": "Gececi (22-06)",
    "unknown": "Yetersiz veri",
}

CHRONOTYPE_EMOJI: dict[str, str] = {
    "morning": "🌅",
    "afternoon": "☀️",
    "evening": "🌆",
    "night": "🌙",
    "unknown": "❓",
}

DAY_NAMES_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]  # weekday() 0=Pzt


@dataclass
class SubjectActivity:
    subject_id: int | None
    subject_name: str
    planned: int
    completed: int

    @property
    def completion_rate(self) -> float:
        return self.completed / self.planned if self.planned > 0 else 0.0


@dataclass
class WeeklyTrend:
    direction: TrendDirection
    this_week_completed: int
    last_week_completed: int
    delta_pct: float | None  # None = bölünemez (last=0)


@dataclass
class StudyDnaProfile:
    """Bir öğrencinin çalışma DNA'sı (window içindeki kompozit profil)."""

    student_id: int
    window_days: int
    computed_at: datetime

    total_completed: int  # window içinde COMPLETED + PARTIAL (hacim — profil/burnout için)
    total_planned: int

    # GÖREV-bazlı gösterim (her madde 1 görev; deneme/test AYRI). Yalnız "Tamamlama"
    # gösterimi için — profil/burnout mantığını (total_*) ETKİLEMEZ.
    display_gorev_total: int = 0
    display_gorev_done: int = 0
    display_test_planned: int = 0   # yalnız soru bankası (deneme HARİÇ)
    display_test_completed: int = 0
    display_deneme_count: int = 0
    display_etkinlik_count: int = 0

    # 7 × 24 matrisi (TR saat); satır = weekday (0=Pzt), sütun = saat 0..23
    heatmap: list[list[int]] = field(default_factory=lambda: [[0]*24 for _ in range(7)])

    chronotype: ChronoType = "unknown"
    peak_hour: int | None = None  # 0-23, TR saati
    peak_day_idx: int | None = None  # 0=Pzt..6=Paz
    peak_day_name: str | None = None

    # Saat bandlarında toplam (yardımcı)
    morning_count: int = 0   # 06-12
    afternoon_count: int = 0  # 12-18
    evening_count: int = 0    # 18-22
    night_count: int = 0      # 22-06 (gece geç + sabaha karşı)

    weekend_count: int = 0
    weekday_count: int = 0

    # Ders bazlı (Subject)
    by_subject: list[SubjectActivity] = field(default_factory=list)

    trend: WeeklyTrend | None = None

    # Saat verisi güvenilirliği: yüzde — completed görevlerin kaçı
    # "tek tık" (high) olarak işaretlendi (batch DEĞİL). Toplu işaretleme
    # arttıkça düşer. < 50 ise UI saat metriklerine kuşkuyla bakmalı.
    hour_data_confidence: int = 100
    batch_completion_count: int = 0   # batch kümesindeki görev sayısı
    fallback_scheduled_count: int = 0  # batch içinde scheduled_hour ile kurtarılan

    @property
    def completion_rate(self) -> float:
        return self.total_completed / self.total_planned if self.total_planned > 0 else 0.0

    @property
    def has_enough_data(self) -> bool:
        return self.total_completed >= MIN_TASKS_FOR_PROFILE


# ============================================================================
# Hesaplama
# ============================================================================


def _utc_to_tr_hour_weekday(dt: datetime) -> tuple[int, int]:
    """UTC datetime → TR saatine çevirip (hour, weekday) döner."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(timezone(timedelta(hours=TR_OFFSET_HOURS)))
    return local.hour, local.weekday()


def detect_batch_completion_ids(tasks: list[Task]) -> set[int]:
    """Toplu işaretleme yapılan görevlerin id'lerini tespit et.

    Algoritma: tamamlanmış görevleri completed_at'e göre sırala; bir görev için
    ±BATCH_WINDOW_SECONDS içinde toplam BATCH_MIN_TASKS+ görev varsa → batch.
    Bu yaklaşım O(N log N) — pencere kayan iki pointer.

    Senaryo: öğrenci 22:00'de 5 görevini topluca tikleyince hepsinin
    completed_at'i ~22:00'ye düşer; bu fonksiyon hepsini batch işaretler.
    """
    completed = [
        t for t in tasks
        if t.completed_at is not None
        and t.status in (TaskStatus.COMPLETED, TaskStatus.PARTIAL)
        and t.id is not None
    ]
    if len(completed) < BATCH_MIN_TASKS:
        return set()

    def _ts(t: Task) -> float:
        dt = t.completed_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

    sorted_tasks = sorted(completed, key=_ts)
    n = len(sorted_tasks)
    batch_ids: set[int] = set()
    left = 0
    for right in range(n):
        # Sol işaretçiyi pencere sınırına çek
        while _ts(sorted_tasks[right]) - _ts(sorted_tasks[left]) > BATCH_WINDOW_SECONDS:
            left += 1
        # right'in solunda+sağında BATCH_MIN_TASKS-1 komşusu kaldıysa kümeyi
        # batch olarak işaretle — pencere içindeki tüm görevler dahil
        window_size = right - left + 1
        if window_size >= BATCH_MIN_TASKS:
            for i in range(left, right + 1):
                batch_ids.add(sorted_tasks[i].id)
    return batch_ids


def resolve_effective_hour(
    task: Task, *, batch_ids: set[int]
) -> tuple[int | None, int | None, HourConfidence]:
    """Bir görev için saat verisinin (hour, weekday, confidence) üçlüsünü döndür.

    - "high"   → batch DEĞİL; completed_at güvenilir → onun saatini kullan
    - "medium" → batch içinde ama Task.scheduled_hour dolu → onu kullan
                 (planlanan saate düşmüş kabul ediyoruz, gerçeğe yakın)
    - "none"   → batch + scheduled_hour yok → saat bazlı hesaba KATILMAZ
                 (heatmap, chronotype, night_owl bu görevi atlar)

    weekday her zaman completed_at'in günü; toplu işaretleme bile gün
    bilgisini bozmaz (çoğunlukla aynı günün gece saatinde olur).
    """
    if task.completed_at is None or task.status not in (
        TaskStatus.COMPLETED, TaskStatus.PARTIAL
    ):
        return None, None, "none"

    completed_hour, weekday = _utc_to_tr_hour_weekday(task.completed_at)

    if task.id not in batch_ids:
        return completed_hour, weekday, "high"

    # Batch — scheduled_hour'a düş
    if task.scheduled_hour is not None and 0 <= task.scheduled_hour <= 23:
        return task.scheduled_hour, weekday, "medium"

    # Kurtarılamaz — saat bazlı metriklerden dışla
    return None, weekday, "none"


def _derive_chronotype(morning: int, afternoon: int, evening: int, night: int) -> ChronoType:
    """En yoğun bandı seç. Az veri durumunda 'unknown'."""
    total = morning + afternoon + evening + night
    if total < MIN_TASKS_FOR_PROFILE:
        return "unknown"
    bands = {
        "morning": morning,
        "afternoon": afternoon,
        "evening": evening,
        "night": night,
    }
    return max(bands.items(), key=lambda kv: kv[1])[0]  # type: ignore[return-value]


def compute_profile(
    db: Session,
    *,
    student_id: int,
    window_days: int = 28,
    now: datetime | None = None,
) -> StudyDnaProfile:
    """Öğrencinin window içindeki çalışma profilini hesapla."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    window_start = now - timedelta(days=window_days)

    # Tüm task'ları çek (subject ile)
    tasks_q = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject)
        )
        .filter(
            Task.student_id == student_id,
            Task.date >= window_start.date(),
        )
    )
    tasks = tasks_q.all()

    profile = StudyDnaProfile(
        student_id=student_id,
        window_days=window_days,
        computed_at=now,
        total_completed=0,
        total_planned=0,
    )

    # Subject birikim
    by_subject_agg: dict[tuple[int | None, str], dict] = defaultdict(
        lambda: {"planned": 0, "completed": 0}
    )

    # Önce toplu işaretleme kümelerini tespit et — saat metrikleri buna göre filtre
    batch_ids = detect_batch_completion_ids(tasks)
    high_conf_count = 0      # batch DEĞİL — completed_at güvenilir
    medium_conf_count = 0    # batch + scheduled_hour ile kurtarıldı
    completed_with_hour_intent = 0  # toplam tamamlanmış (saat hesabına aday)

    from app.services import gorev_stats
    for task in tasks:
        # Toplam planlanan = book_items varsa planned_count, yoksa 1 (basit görev)
        planned_total = sum(it.planned_count for it in task.book_items) or 1
        completed_total = sum(it.completed_count for it in task.book_items) or (
            planned_total if task.status == TaskStatus.COMPLETED else 0
        )
        profile.total_planned += planned_total
        profile.total_completed += completed_total

        # GÖREV-bazlı gösterim (deneme test'e karışmaz) — yalnız display alanları
        _cat = gorev_stats.classify_gorev(task)
        profile.display_gorev_total += 1
        if gorev_stats.gorev_done(task):
            profile.display_gorev_done += 1
        if _cat == "test":
            profile.display_test_planned += sum(it.planned_count for it in task.book_items)
            profile.display_test_completed += sum(it.completed_count for it in task.book_items)
        elif _cat in ("deneme", "tam_deneme"):
            profile.display_deneme_count += 1
        elif _cat == "etkinlik":
            profile.display_etkinlik_count += 1

        # Subject bazlı
        if task.book_items:
            for it in task.book_items:
                subj = it.book.subject if it.book else None
                key = (subj.id if subj else None, subj.name if subj else "(diğer)")
                by_subject_agg[key]["planned"] += it.planned_count
                by_subject_agg[key]["completed"] += it.completed_count
        else:
            key = (None, "(diğer)")
            by_subject_agg[key]["planned"] += 1
            if task.status == TaskStatus.COMPLETED:
                by_subject_agg[key]["completed"] += 1

        # Heatmap + saat bandı — batch-aware effective_hour kullanarak
        if task.completed_at is not None and task.status in (
            TaskStatus.COMPLETED, TaskStatus.PARTIAL
        ):
            completed_with_hour_intent += 1
            hour, weekday, conf = resolve_effective_hour(task, batch_ids=batch_ids)
            if conf == "high":
                high_conf_count += 1
            elif conf == "medium":
                medium_conf_count += 1
            # Hafta sonu/içi sayım completed_at gününden bağımsız → her zaman say
            if weekday is not None:
                if weekday >= 5:
                    profile.weekend_count += 1
                else:
                    profile.weekday_count += 1
            # Saat bazlı metrikler sadece güvenilir veride
            if hour is None or weekday is None:
                continue
            profile.heatmap[weekday][hour] += 1
            if 6 <= hour < 12:
                profile.morning_count += 1
            elif 12 <= hour < 18:
                profile.afternoon_count += 1
            elif 18 <= hour < 22:
                profile.evening_count += 1
            else:  # 22-06
                profile.night_count += 1

    # Güvenilirlik metriği — high ağırlıklı, medium yarı ağırlıkta
    if completed_with_hour_intent > 0:
        weighted = high_conf_count + 0.5 * medium_conf_count
        profile.hour_data_confidence = int(
            round(100 * weighted / completed_with_hour_intent)
        )
    profile.batch_completion_count = len(batch_ids)
    profile.fallback_scheduled_count = medium_conf_count

    # Chronotype
    profile.chronotype = _derive_chronotype(
        profile.morning_count, profile.afternoon_count,
        profile.evening_count, profile.night_count,
    )

    # Peak saat ve gün
    hour_totals = [0] * 24
    day_totals = [0] * 7
    for d in range(7):
        for h in range(24):
            v = profile.heatmap[d][h]
            hour_totals[h] += v
            day_totals[d] += v
    if sum(hour_totals) > 0:
        profile.peak_hour = hour_totals.index(max(hour_totals))
    if sum(day_totals) > 0:
        profile.peak_day_idx = day_totals.index(max(day_totals))
        profile.peak_day_name = DAY_NAMES_TR[profile.peak_day_idx]

    # Ders bazlı liste — completed descending
    subjects: list[SubjectActivity] = []
    for (sid, sname), stats in by_subject_agg.items():
        subjects.append(SubjectActivity(
            subject_id=sid,
            subject_name=sname,
            planned=stats["planned"],
            completed=stats["completed"],
        ))
    subjects.sort(key=lambda s: -s.completed)
    profile.by_subject = subjects

    # Trend: bu hafta vs geçen hafta tamamlama
    profile.trend = _compute_trend(tasks, now)

    return profile


def _compute_trend(tasks: list[Task], now: datetime) -> WeeklyTrend:
    """Bu hafta (son 7g) vs geçen hafta (8-14g önce) tamamlama sayısı."""
    today = now.date()
    this_start = today - timedelta(days=6)
    last_end = this_start - timedelta(days=1)
    last_start = last_end - timedelta(days=6)

    this_n = 0
    last_n = 0
    for t in tasks:
        if t.status not in (TaskStatus.COMPLETED, TaskStatus.PARTIAL):
            continue
        d = t.date if isinstance(t.date, date) else t.date
        if this_start <= d <= today:
            this_n += 1
        elif last_start <= d <= last_end:
            last_n += 1

    if this_n + last_n < MIN_TASKS_FOR_PROFILE:
        return WeeklyTrend(
            direction="insufficient",
            this_week_completed=this_n,
            last_week_completed=last_n,
            delta_pct=None,
        )
    if last_n == 0:
        return WeeklyTrend(
            direction="up" if this_n > 0 else "flat",
            this_week_completed=this_n,
            last_week_completed=last_n,
            delta_pct=None,
        )
    delta = (this_n - last_n) / last_n * 100
    if delta > 10:
        direction = "up"
    elif delta < -10:
        direction = "down"
    else:
        direction = "flat"
    return WeeklyTrend(
        direction=direction,
        this_week_completed=this_n,
        last_week_completed=last_n,
        delta_pct=delta,
    )
