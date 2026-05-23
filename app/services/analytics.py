"""Öğrenci analitik hesaplamaları.

Tek merkezden beslenir: öğrenci detayı (öğretmen), öğrenci kendi paneli,
öğretmen dashboard uyarıları ve veli raporu aynı fonksiyonları kullanır.

Terminoloji:
- **planned**: task.book_items.planned_count toplamı (öğretmenin atadığı hedef)
- **completed**: task.book_items.completed_count toplamı (öğrencinin tiklediği)
- **rate**: günlük ortalama tamamlanan test (son N gün)
- **remaining**: tüm kitapların toplam_test − çözüldü − rezerv
- **projection**: kalan süre × mevcut hız → tamamlanabilir test
- **gap**: projection − remaining (pozitif = yetecek, negatif = yetmeyecek)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Literal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AcademicYear,
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    User,
)


# ---------------------------- Veri türleri ----------------------------


@dataclass
class DailyStats:
    planned: int = 0
    completed: int = 0
    tasks_total: int = 0
    tasks_completed: int = 0


@dataclass
class Projection:
    exam_date: date | None
    days_left: int | None
    rate_per_day: float          # son penceredeki günlük genel ortalama (basit)
    window_days: int             # tarihçe penceresi (gün)
    total_tests: int
    completed: int
    reserved: int
    remaining: int               # yeni rezerv açılabilir alan (kalan − rezerv)
    projected_completable: int   # gerçekçi tahmin (DOW × etkili gün)
    gap: int                     # projection − kalan_iş
    required_rate: float         # günlük gereken hız (kalan_iş / etkili_gün)
    # === Gerçekçi model ek alanları ===
    buffer_days: int = 5         # sınav öncesi tampon — son N gün üretken sayılmaz
    effective_days: int = 0      # bugünden buffer_end'e kadar gün sayısı
    dow_rates: dict[int, float] = field(default_factory=dict)        # tamamlanan ortalama (0-6)
    dow_planned_rates: dict[int, float] = field(default_factory=dict)  # planlanan ortalama (0-6)
    dow_hit_rates: dict[int, float] = field(default_factory=dict)    # tutturma oranı (0..1, planlı gün varsa)
    dow_hit_measured: dict[int, bool] = field(default_factory=dict)  # geçmişte tutturma ölçülebildi mi
    simple_projected: int = 0    # eski naif yöntem (karşılaştırma için)
    confidence_level: str = "low"   # "high"/"medium"/"low"  (veri yeterliliğine göre)
    methodology: str = "dow_weighted"   # "naive" / "dow_weighted"


@dataclass
class Warning:
    level: Literal["green", "amber", "red"]
    code: str
    title: str
    detail: str


@dataclass
class StudentSnapshot:
    student: User
    today: DailyStats
    week: DailyStats
    rate_7d: float
    rate_30d: float
    consistency_7d: float        # 0..1 — son 7 günün kaçında tik var
    hit_rate_7d: float           # 0..1 — planlanan→tamamlanan
    projection: Projection
    warnings: list[Warning] = field(default_factory=list)
    worst_warning_level: Literal["green", "amber", "red"] = "green"


# ---------------------------- Yardımcılar ----------------------------


def _daterange(start: date, end_inclusive: date) -> Iterable[date]:
    d = start
    while d <= end_inclusive:
        yield d
        d += timedelta(days=1)


def _as_local_date(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    # Eğer naive ise UTC kabul et; ardından local (sistem) tarihe dönüştür
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().date()


# ---------------------------- Günlük seriler ----------------------------


def daily_completed_series(
    db: Session, student_id: int, end_date: date, days_back: int
) -> dict[date, int]:
    """Son N gün için her günün tamamlanan test sayısı.

    Görevin **plan tarihine (Task.date)** göre bucket'lanır — bu hit_rate hesabı için
    plan-gerçekleşme tutarlılığını sağlar. Yani bir görevi geç tıklamak hala görevin
    asıl tarihine puan yazar.
    """
    start = end_date - timedelta(days=days_back - 1)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.student_id == student_id)
        .filter(Task.date >= start)
        .filter(Task.date <= end_date)
        .all()
    )
    result = {d: 0 for d in _daterange(start, end_date)}
    for t in tasks:
        if t.date not in result:
            continue
        total = sum(it.completed_count for it in t.book_items)
        if total > 0:
            result[t.date] += total
    return result


def daily_action_series(
    db: Session, student_id: int, end_date: date, days_back: int
) -> dict[date, int]:
    """Görev TIKLAMA gününe (Task.completed_at) göre seri — "öğrenci o gün ne kadar
    aktif oldu" göstergesi. UI/aktivite için kullanılabilir, hit_rate için değil.
    """
    start = end_date - timedelta(days=days_back - 1)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.student_id == student_id)
        .filter(Task.completed_at.isnot(None))
        .filter(func.date(Task.completed_at) >= start)
        .filter(func.date(Task.completed_at) <= end_date)
        .all()
    )
    result = {d: 0 for d in _daterange(start, end_date)}
    for t in tasks:
        d = _as_local_date(t.completed_at) or t.date
        if d not in result:
            continue
        total = sum(it.completed_count for it in t.book_items)
        if total > 0:
            result[d] += total
    return result


def daily_planned_series(
    db: Session, student_id: int, end_date: date, days_back: int
) -> dict[date, int]:
    """Her gün için o güne atanmış planlanan toplam test (Task.date bazında)."""
    start = end_date - timedelta(days=days_back - 1)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end_date,
        )
        .all()
    )
    result = {d: 0 for d in _daterange(start, end_date)}
    for t in tasks:
        if t.date not in result:
            continue
        result[t.date] += sum(it.planned_count for it in t.book_items)
    return result


def daily_stats_for(db: Session, student_id: int, d: date) -> DailyStats:
    """Belirli bir gün için planlanan/tamamlanan sayılarını döner."""
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.student_id == student_id, Task.date == d)
        .all()
    )
    planned = sum(it.planned_count for t in tasks for it in t.book_items)
    completed = sum(it.completed_count for t in tasks for it in t.book_items)
    return DailyStats(
        planned=planned,
        completed=completed,
        tasks_total=len(tasks),
        tasks_completed=sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
    )


def week_stats_for(db: Session, student_id: int, end_date: date) -> DailyStats:
    """Son 7 gün toplamı (end dahil)."""
    start = end_date - timedelta(days=6)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end_date,
        )
        .all()
    )
    planned = sum(it.planned_count for t in tasks for it in t.book_items)
    completed = sum(it.completed_count for t in tasks for it in t.book_items)
    return DailyStats(
        planned=planned,
        completed=completed,
        tasks_total=len(tasks),
        tasks_completed=sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
    )


# ---------------------------- Hız ve projeksiyon ----------------------------


def recent_rate(
    db: Session, student_id: int, end_date: date, window_days: int
) -> float:
    """Son N günde günde ortalama tamamlanan test."""
    series = daily_completed_series(db, student_id, end_date, window_days)
    if not series:
        return 0.0
    return sum(series.values()) / window_days


def inventory_totals(db: Session, student_id: int) -> tuple[int, int, int]:
    """Öğrencinin tüm kitaplarının toplam / çözüldü / rezerv sayıları."""
    total = 0
    completed = 0
    reserved = 0
    sbs = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.sections),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student_id)
        .all()
    )
    for sb in sbs:
        total += sb.total_tests
        completed += sb.completed_tests
        reserved += sb.reserved_tests
    return total, completed, reserved


def get_exam_date(db: Session, student: User) -> date | None:
    """Öğrenci-spesifik sınav tarihi.

    Hedef sınav öğrencinin sınıf+mezunluk durumundan türetilir
    (User.effective_exam_target). Tarih de oradan gelir; akademik yıl
    seviyesinde tek bir 'sınav tarihi' tutmuyoruz çünkü aynı yılda LGS+YKS
    öğrenciler birlikte yer alabilir.
    """
    return student.effective_exam_date


def compute_projection(
    db: Session, student: User, today: date,
    window_days: int = 28, buffer_days: int = 5,
) -> Projection:
    """Gerçekçi projeksiyon hesaplaması.

    Yöntem (DOW-weighted forward walk):
    1. Son `window_days` gün için her **haftagünü (0-6)** ortalama tamamlanan test sayısı
       hesaplanır (dow_rates).
    2. Bugünden başlayarak **sınav tarihi − buffer_days**'e kadar her gün için o günün
       haftagününe ait ortalama eklenir → projected_completable.
       (Sınav haftasının son 5 günü tampon kabul edilir; öğrenci o günlerde sıfır
        ya da minimum çalışma yapar varsayımıdır.)
    3. Gap = projected_completable − (kalan_iş = total − completed)
    4. required_rate = kalan_iş / etkili_gün  (etkili = sınav − bugün − buffer)
    5. Karşılaştırma için **naif** yöntem (genel ortalama × etkili_gün) `simple_projected`
       alanında saklanır.
    6. Güven seviyesi: ≥21 aktif gün → high, 7-20 → medium, <7 → low.
    """
    exam_date = get_exam_date(db, student)
    days_left: int | None
    if exam_date:
        days_left = (exam_date - today).days
        if days_left < 0:
            days_left = 0
        buffer_end = exam_date - timedelta(days=buffer_days)
        effective_days = max(0, (buffer_end - today).days)
    else:
        days_left = None
        effective_days = 0

    # Tarihçe — günlük tamamlama (sadece geçmiş)
    series = daily_completed_series(db, student.id, today, window_days)
    overall_rate = (sum(series.values()) / window_days) if window_days > 0 else 0.0

    # Planlama serisi — geçmiş + gelecek (öğretmenin tüm planını yansıtır)
    # daily_planned_series end_date'e doğru bakıyor; gelecek için ayrı çekip birleştiriyoruz.
    past_planned = daily_planned_series(db, student.id, today, window_days)
    # Geleceğe planları al — gelecek görevleri sınav tarihine kadar kapsar
    from app.models import Task as _Task, TaskBookItem as _TBI
    future_q = (
        db.query(_Task)
        .options(joinedload(_Task.book_items))
        .filter(_Task.student_id == student.id, _Task.date >= today)
        .all()
    )
    future_planned: dict[date, int] = {}
    for t in future_q:
        future_planned[t.date] = future_planned.get(t.date, 0) + sum(it.planned_count for it in t.book_items)

    # DOW bazlı: tamamlanan = sadece geçmiş, planlanan = geçmiş + gelecek (yalnızca plan girilmiş günler)
    dow_completed_buckets: dict[int, list[int]] = {i: [] for i in range(7)}
    dow_planned_buckets: dict[int, list[int]] = {i: [] for i in range(7)}
    # Geçmiş tamamlama — boş günler dahil (ortalama doğru çıksın)
    for d, count in series.items():
        dow_completed_buckets[d.weekday()].append(count)
    # Planlama: yalnızca plan girilmiş günleri kullan (boş günleri ortalamaya katma)
    for d, count in {**past_planned, **future_planned}.items():
        if count > 0:
            dow_planned_buckets[d.weekday()].append(count)

    dow_rates: dict[int, float] = {}            # ortalama tamamlanan
    dow_planned_rates: dict[int, float] = {}    # ortalama planlanan (sadece planlı günler)
    dow_hit_rates: dict[int, float] = {}        # tutturma oranı (sadece planlı geçmiş günler)
    # Geçmişte planlı ve tamamlanmış DOW hit oranı için ayrı bucket
    dow_past_planned_buckets: dict[int, int] = {i: 0 for i in range(7)}
    dow_past_completed_buckets: dict[int, int] = {i: 0 for i in range(7)}
    for d, count in past_planned.items():
        if count > 0:
            dow_past_planned_buckets[d.weekday()] += count
            dow_past_completed_buckets[d.weekday()] += series.get(d, 0)
    dow_hit_measured: dict[int, bool] = {}
    for dow in range(7):
        c_vals = dow_completed_buckets[dow]
        p_vals = dow_planned_buckets[dow]
        dow_rates[dow] = (sum(c_vals) / len(c_vals)) if c_vals else 0.0
        dow_planned_rates[dow] = (sum(p_vals) / len(p_vals)) if p_vals else 0.0
        if dow_past_planned_buckets[dow] > 0:
            dow_hit_rates[dow] = dow_past_completed_buckets[dow] / dow_past_planned_buckets[dow]
            dow_hit_measured[dow] = True
        else:
            dow_hit_rates[dow] = 0.0
            dow_hit_measured[dow] = False

    total, completed, reserved = inventory_totals(db, student.id)
    remaining_unassigned = total - completed - reserved
    remaining_overall = total - completed  # tüm hedef iş

    # Forward projection
    # Algoritma: o günün planlanan ortalama × o günün tutturma oranı
    # Planlı gün yoksa: completed-bazlı dow_rates kullan (geçmişten direkt)
    # Hiçbir veri yoksa: overall_rate fallback
    # Genel tutturma oranı (fallback olarak)
    total_past_planned = sum(dow_past_planned_buckets.values())
    total_past_completed = sum(dow_past_completed_buckets.values())
    overall_hit_rate = (total_past_completed / total_past_planned) if total_past_planned > 0 else 0.0

    projected_real = 0.0
    if effective_days > 0:
        for i in range(effective_days):
            d = today + timedelta(days=i)
            dow = d.weekday()
            planned_avg = dow_planned_rates.get(dow, 0.0)
            hit = dow_hit_rates.get(dow, 0.0)
            past_completed = dow_rates.get(dow, 0.0)
            if planned_avg > 0 and hit > 0:
                # Plan-bazlı: gelecek günlerde bu kadar plan, bu oranda tutturuyor
                r = planned_avg * hit
            elif planned_avg > 0 and overall_hit_rate > 0:
                # Plan var ama bu DOW'da geçmiş tamamlama yok → genel hit oranı
                r = planned_avg * overall_hit_rate
            elif past_completed > 0:
                # Plan yok ama geçmişte bu DOW'da tamamlama vardı
                r = past_completed
            elif overall_rate > 0:
                # Hiç DOW verisi yok → genel ortalama
                r = overall_rate
            else:
                r = 0.0
            projected_real += r
    projected_int = int(round(projected_real))

    # Naif karşılaştırma (eski yöntem)
    simple_projected = int(round(overall_rate * effective_days)) if effective_days > 0 else 0

    # required = kalan_iş / etkili_gün (sınav günü ve son 5 gün dahil değil)
    required = (remaining_overall / effective_days) if effective_days > 0 else 0.0

    # Gap
    gap = projected_int - remaining_overall

    # Güven seviyesi — kaç günde aktivite var
    days_with_data = sum(1 for v in series.values() if v > 0)
    if days_with_data >= 21:
        confidence = "high"
    elif days_with_data >= 7:
        confidence = "medium"
    else:
        confidence = "low"

    return Projection(
        exam_date=exam_date,
        days_left=days_left,
        rate_per_day=overall_rate,
        window_days=window_days,
        total_tests=total,
        completed=completed,
        reserved=reserved,
        remaining=remaining_unassigned,
        projected_completable=projected_int,
        gap=gap,
        required_rate=required,
        buffer_days=buffer_days,
        effective_days=effective_days,
        dow_rates=dow_rates,
        dow_planned_rates=dow_planned_rates,
        dow_hit_rates=dow_hit_rates,
        dow_hit_measured=dow_hit_measured,
        simple_projected=simple_projected,
        confidence_level=confidence,
        methodology="dow_weighted",
    )


# ---------------------------- Performans skorları ----------------------------


def consistency_score(
    db: Session, student_id: int, end_date: date, days: int = 7
) -> float:
    """Son N günün kaçında en az 1 test tamamlanmış (tik var) / N."""
    series = daily_completed_series(db, student_id, end_date, days)
    if not series:
        return 0.0
    active_days = sum(1 for v in series.values() if v > 0)
    return active_days / days


def hit_rate(
    db: Session, student_id: int, end_date: date, days: int = 7
) -> float:
    """Planlanan → tamamlanan oranı (son N gün, Task.date penceresi).

    Dönüş 0..N arası — genellikle 0..1. Bazen planlanandan fazlası çözülür
    (öğretmenin manuel kalem eklemesi, ileri tarihli görev tıklama), 1.0'ı
    aşmaması için kırpma yapmıyoruz; kullanan yer görselleştirebilir.
    """
    start = end_date - timedelta(days=days - 1)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end_date,
        )
        .all()
    )
    planned = sum(it.planned_count for t in tasks for it in t.book_items)
    completed = sum(it.completed_count for t in tasks for it in t.book_items)
    return (completed / planned) if planned > 0 else 0.0


# ---------------------------- Ders bazında ----------------------------


def subject_breakdown(db: Session, student_id: int) -> list[dict]:
    """Her ders için toplam/çözüldü/rezerv ve tamamlanma yüzdesi."""
    sbs = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student_id)
        .all()
    )
    bucket: dict[int, dict] = {}
    for sb in sbs:
        s = sb.book.subject
        b = bucket.setdefault(
            s.id,
            {
                "subject_id": s.id,
                "name": s.name,
                "order": s.order,
                "total": 0,
                "completed": 0,
                "reserved": 0,
                "books": 0,
                "last_completed_at": None,
            },
        )
        b["total"] += sb.total_tests
        b["completed"] += sb.completed_tests
        b["reserved"] += sb.reserved_tests
        b["books"] += 1
    # Ders bazında "son tamamlama tarihi" — en son o derste tiklenmiş görev
    last_per_subject_q = (
        db.query(Subject.id, func.max(Task.completed_at))
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(Book, Book.id == TaskBookItem.book_id)
        .join(Subject, Subject.id == Book.subject_id)
        .filter(Task.student_id == student_id)
        .filter(Task.completed_at.isnot(None))
        .group_by(Subject.id)
        .all()
    )
    for sid, last in last_per_subject_q:
        if sid in bucket:
            bucket[sid]["last_completed_at"] = last
    # Yüzde
    out = []
    for b in sorted(bucket.values(), key=lambda x: (x["order"], x["name"])):
        t = b["total"]
        b["percent_done"] = int(round(100 * b["completed"] / t)) if t > 0 else 0
        b["percent_reserved"] = int(round(100 * b["reserved"] / t)) if t > 0 else 0
        b["remaining"] = t - b["completed"] - b["reserved"]
        out.append(b)
    return out


# ---------------------------- Uyarı üreticiler ----------------------------


def generate_warnings(
    db: Session, student: User, today: date, projection: Projection
) -> list[Warning]:
    """Araba-ekranı tarzı akıllı uyarılar. Sadece uyulması gereken durumlarda dön."""
    out: list[Warning] = []

    # Onboarding: yeni oluşturulmuş öğrenci (hesap < 3 gün) inaktivite uyarısı
    # ALMAZ — henüz programı/girişi olmayabilir (false-positive önleme).
    _created = student.created_at
    if _created is not None and _created.tzinfo is None:
        _created = _created.replace(tzinfo=timezone.utc)
    account_age_days = (
        max(0, (datetime.now(timezone.utc) - _created).days) if _created else None
    )

    # 1) Bugün hiç tik yapmadı mı (plan vardı ama tamamlama yok)
    today_stats = daily_stats_for(db, student.id, today)
    if today_stats.planned > 0 and today_stats.completed == 0:
        # Saat geç mi? Akşam geçmiş ama hiç tik yok — kırmızı; gün hâlâ devam ediyorsa sarı
        hour = datetime.now().hour
        level = "red" if hour >= 20 else "amber"
        out.append(Warning(
            level=level,
            code="today_no_tick",
            title="Bugün hiç tik yapmadı",
            detail=f"Bugüne planlanmış {today_stats.planned} test var, henüz hiçbiri tiklenmedi.",
        ))

    # 2) Dün de tik yoksa — ciddileştir
    yesterday = today - timedelta(days=1)
    yesterday_stats = daily_stats_for(db, student.id, yesterday)
    if yesterday_stats.planned > 0 and yesterday_stats.completed == 0:
        out.append(Warning(
            level="red",
            code="yesterday_no_tick",
            title="Dün hiç ilerleme yok",
            detail=f"Dün {yesterday_stats.planned} test planlı idi, tamamlanmadı.",
        ))

    # 3) Son 3 günde hiç tik yok mu — SADECE programı olan (planlı görevi bulunan)
    # ve hesabı ≥3 günlük öğrenci için. Yeni/programsız öğrenciye "hareket yok"
    # demek yanlış-pozitif (programsızlık ayrı sinyal).
    series3 = daily_completed_series(db, student.id, today, 3)
    dby_stats = daily_stats_for(db, student.id, today - timedelta(days=2))
    planned_3 = today_stats.planned + yesterday_stats.planned + dby_stats.planned
    if (
        sum(series3.values()) == 0
        and planned_3 > 0
        and (account_age_days is None or account_age_days >= 3)
    ):
        out.append(Warning(
            level="red",
            code="inactive_3d",
            title="3 gündür hareket yok",
            detail="Son 3 günde öğrencinin hiç test tamamlaması yok.",
        ))

    # 4) Haftalık hedef tutturma oranı düşük
    hit = hit_rate(db, student.id, today, 7)
    if hit > 0 and hit < 0.5:
        out.append(Warning(
            level="amber",
            code="weekly_miss",
            title="Haftalık tempo düşük",
            detail=f"Son 7 günde planlanan görevlerin sadece %{int(hit*100)}'i tamamlanmış.",
        ))
    elif hit == 0 and projection.days_left and projection.days_left > 0:
        # Tamamen durmuş
        out.append(Warning(
            level="red",
            code="weekly_zero",
            title="Haftalık ilerleme sıfır",
            detail="Son 7 günde hiç test tamamlanmamış.",
        ))

    # 5) Projeksiyon açığı
    if projection.days_left is not None and projection.days_left > 0:
        remaining_overall = projection.total_tests - projection.completed
        if remaining_overall > 0 and projection.rate_per_day > 0:
            if projection.gap < 0:
                # İleriye-dönük projeksiyon açığı: öğrenci AKTİF çalışıyor
                # (rate_per_day > 0) ama tempoca geride → 'dikkat' (amber), acil
                # hareketsizlik (red) ile aynı şiddette değil. Tamamen durmuş
                # öğrenci için ayrı 'projection_zero_rate' (red) var.
                out.append(Warning(
                    level="amber",
                    code="projection_shortfall",
                    title="Sınava yetişmeyecek",
                    detail=(
                        f"Mevcut hızla ({projection.rate_per_day:.1f} test/gün) "
                        f"{abs(projection.gap)} test eksik kalacak. "
                        f"Gerekli hız: {projection.required_rate:.1f} test/gün."
                    ),
                ))
            elif projection.gap < remaining_overall * 0.1:
                # Sınırda
                out.append(Warning(
                    level="amber",
                    code="projection_tight",
                    title="Projeksiyon sınırda",
                    detail=(
                        f"Mevcut hızla hedefi çok az farkla tutturuyor "
                        f"(±{projection.gap} test). Hız düşerse gecikir."
                    ),
                ))
        elif projection.rate_per_day == 0 and remaining_overall > 0:
            out.append(Warning(
                level="red",
                code="projection_zero_rate",
                title="Hız sıfır — projeksiyon imkansız",
                detail=f"Son 7 günde tik yok; {remaining_overall} test tamamlanmayı bekliyor.",
            ))

    # 6) Bir dersten 7+ gün uzak
    breakdown = subject_breakdown(db, student.id)
    for s in breakdown:
        if s["remaining"] > 0 and s["reserved"] > 0:
            # Rezerv var ama tiklenmiyor
            pass  # (checked below)
        if s["total"] > 0 and s["last_completed_at"]:
            last = _as_local_date(s["last_completed_at"])
            days_gap = (today - last).days if last else 999
            if days_gap >= 7 and s["percent_done"] < 100:
                out.append(Warning(
                    level="amber",
                    code=f"subject_stale_{s['subject_id']}",
                    title=f"{s['name']} dersinde durgunluk",
                    detail=f"Son {days_gap} gündür bu derste tamamlama yok (%{s['percent_done']} bitmiş).",
                ))
        elif s["total"] > 0 and s["last_completed_at"] is None and s["reserved"] > 0:
            # Hiç çözülmemiş ama rezerv var
            out.append(Warning(
                level="amber",
                code=f"subject_untouched_{s['subject_id']}",
                title=f"{s['name']} henüz başlanmadı",
                detail=f"Rezerv açılmış ama hiçbir test tamamlanmamış.",
            ))

    return out


def worst_level(warnings: list[Warning]) -> Literal["green", "amber", "red"]:
    if any(w.level == "red" for w in warnings):
        return "red"
    if any(w.level == "amber" for w in warnings):
        return "amber"
    return "green"


# ---------------------------- Birleşik snapshot ----------------------------


def student_snapshot(
    db: Session, student: User, today: date | None = None
) -> StudentSnapshot:
    """Dashboard ve detay sayfası için hepsi bir arada özet."""
    if today is None:
        today = date.today()
    today_stats = daily_stats_for(db, student.id, today)
    week_stats = week_stats_for(db, student.id, today)
    rate7 = recent_rate(db, student.id, today, 7)
    rate30 = recent_rate(db, student.id, today, 30)
    cons7 = consistency_score(db, student.id, today, 7)
    hit7 = hit_rate(db, student.id, today, 7)
    # Gerçekçi projeksiyon — 28 günlük DOW penceresi + 5 günlük sınav tamponu
    proj = compute_projection(db, student, today, window_days=28, buffer_days=5)
    warnings = generate_warnings(db, student, today, proj)
    return StudentSnapshot(
        student=student,
        today=today_stats,
        week=week_stats,
        rate_7d=rate7,
        rate_30d=rate30,
        consistency_7d=cons7,
        hit_rate_7d=hit7,
        projection=proj,
        warnings=warnings,
        worst_warning_level=worst_level(warnings),
    )
