"""Kurum sağlık skoru — süper admin için churn / risk göstergesi.

Stage 5: Tenant health scorecard. Süper admin "/admin/institutions" sayfasında
hangi kurumların terk etme (churn) riski taşıdığını tek bakışta görmek ister.

Skor 0-100; yüksek skor = sağlıksız (terk etmek üzere). Skor terc tersi
sezgisel olabilir ama Stage 1'deki risk skoruyla **aynı yönde** tutuldu —
böylece hem öğrenci risk hem kurum risk aynı kafayla okunur (yüksek=tehlike).

Göstergeler ve ağırlıklar:
- no_teacher_login_30d (30): Hiçbir öğretmen 30 gündür sisteme girmiyor.
  Bu kurum fiilen ölü — eğitim verilmiyor.
- no_student_login_30d (25): Hiçbir öğrenci 30 gündür sisteme girmiyor.
  Sistemi adopte edememişler.
- low_active_teacher_pct (15): Aktif öğretmenlerin %50'sinden azı son 7 günde login.
- low_active_student_pct (15): Aktif öğrencilerin %30'undan azı son 7 günde login.
- low_completion (10): Bu hafta tamamlama oranı < %30 (motivasyon kaybı).
- empty_institution (5): Hiç öğrenci yok ya da hiç öğretmen yok (içi boş kurum).

Seviye eşikleri:
- 🟢 healthy: 0-29
- 🟡 watch:   30-49
- 🟠 risk:    50-69
- 🔴 critical: 70+

Bu eşikler sezgisel; ileride veriyle kalibre edilebilir. Kullanıcı dostu
ilkesi: süper admin tek bakışta kim ilgi istiyor görmeli; gri zon olmamalı.

Performans:
- compute_health_score: kurum başına 4-5 SQL (counts + last logins + completion)
- bulk_health_assessment: N kurum için optimize — 5 batched SQL toplam
- /admin/institutions list (5-50 kurum) için <500ms hedef
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Institution,
    Task,
    User,
    UserRole,
)
from app.models.task import TaskBookItem


logger = logging.getLogger(__name__)


# Gösterge ağırlıkları — toplamı 100. UI etiketleriyle birlikte güncellenmeli.
WEIGHTS = {
    "no_teacher_login_30d": 30,
    "no_student_login_30d": 25,
    "low_active_teacher_pct": 15,
    "low_active_student_pct": 15,
    "low_completion": 10,
    "empty_institution": 5,
}

# Aktif kullanıcı eşik oranları
TEACHER_ACTIVE_THRESHOLD_PCT = 50   # %50'den azı login = düşük
STUDENT_ACTIVE_THRESHOLD_PCT = 30   # %30'dan azı login = düşük
LOW_COMPLETION_THRESHOLD_PCT = 30   # %30'dan az tamamlama = düşük

# Skor seviye eşikleri (alt sınır dahil)
LEVEL_THRESHOLDS = [
    (70, "critical"),  # 🔴
    (50, "risk"),      # 🟠
    (30, "watch"),     # 🟡
    (0,  "healthy"),   # 🟢
]

LEVEL_LABELS_TR = {
    "critical": "Kritik",
    "risk":     "Riskli",
    "watch":    "Gözlem",
    "healthy":  "Sağlıklı",
}

LEVEL_EMOJIS = {
    "critical": "🔴",
    "risk":     "🟠",
    "watch":    "🟡",
    "healthy":  "🟢",
}

LEVEL_COLOR_CSS = {
    # Tailwind sınıfları (text/bg/border) — şablonlarda kolayca kullanmak için
    "critical": "rose",
    "risk":     "amber",
    "watch":    "yellow",
    "healthy":  "emerald",
}


# ---------------------------- Veri yapıları ----------------------------


@dataclass
class HealthIndicator:
    """Tek bir sağlık göstergesi — kod + başlık + ayrıntı + ağırlık."""
    code: str
    title: str
    detail: str
    weight: int


@dataclass
class HealthAssessment:
    institution: Institution
    score: int                                    # 0-100, yüksek=tehlike
    level: Literal["healthy", "watch", "risk", "critical"]
    level_label: str
    level_emoji: str
    level_color: str                              # tailwind palette anahtarı
    indicators: list[HealthIndicator] = field(default_factory=list)

    # Ham metrikler (UI/detay için):
    teacher_count: int = 0
    student_count: int = 0
    active_teacher_count_7d: int = 0
    active_student_count_7d: int = 0
    last_teacher_login: datetime | None = None
    last_student_login: datetime | None = None
    weekly_completion_rate: int | None = None     # %0-100

    @property
    def teacher_active_pct(self) -> int | None:
        if self.teacher_count == 0:
            return None
        return int(round(100 * self.active_teacher_count_7d / self.teacher_count))

    @property
    def student_active_pct(self) -> int | None:
        if self.student_count == 0:
            return None
        return int(round(100 * self.active_student_count_7d / self.student_count))


# ---------------------------- Yardımcılar ----------------------------


def _level_for_score(score: int) -> str:
    for threshold, level in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return "healthy"


def _build_assessment(
    institution: Institution,
    score: int,
    indicators: list[HealthIndicator],
    *,
    teacher_count: int,
    student_count: int,
    active_teacher_count_7d: int,
    active_student_count_7d: int,
    last_teacher_login: datetime | None,
    last_student_login: datetime | None,
    weekly_completion_rate: int | None,
) -> HealthAssessment:
    score = min(score, 100)
    level = _level_for_score(score)
    return HealthAssessment(
        institution=institution,
        score=score,
        level=level,  # type: ignore[arg-type]
        level_label=LEVEL_LABELS_TR[level],
        level_emoji=LEVEL_EMOJIS[level],
        level_color=LEVEL_COLOR_CSS[level],
        indicators=indicators,
        teacher_count=teacher_count,
        student_count=student_count,
        active_teacher_count_7d=active_teacher_count_7d,
        active_student_count_7d=active_student_count_7d,
        last_teacher_login=last_teacher_login,
        last_student_login=last_student_login,
        weekly_completion_rate=weekly_completion_rate,
    )


def _normalize_dt(dt: datetime | None) -> datetime | None:
    """SQLite naive UTC datetime → tz-aware UTC. None pass-through."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _days_since(dt: datetime | None, now: datetime) -> int | None:
    dt = _normalize_dt(dt)
    if dt is None:
        return None
    return max(0, (now - dt).days)


# ---------------------------- Tek kurum hesabı ----------------------------


def _compute_weekly_completion_rate(
    db: Session, *, institution_id: int, today: date,
) -> int | None:
    """Bu haftanın (Pzt-Paz) tamamlama oranı — %0-100, hiç plan yoksa None."""
    weekday = today.weekday()
    week_start = today - timedelta(days=weekday)
    week_end = week_start + timedelta(days=6)
    row = (
        db.query(
            func.coalesce(func.sum(TaskBookItem.planned_count), 0).label("p"),
            func.coalesce(func.sum(TaskBookItem.completed_count), 0).label("c"),
        )
        .select_from(User)
        .join(Task, Task.student_id == User.id)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
            Task.date >= week_start,
            Task.date <= week_end,
        )
        .first()
    )
    if not row or not row.p:
        return None
    return int(round(100 * row.c / row.p))


def compute_health_score(
    db: Session, *, institution: Institution, now: datetime | None = None,
    today: date | None = None,
) -> HealthAssessment:
    """Bir kurumun sağlık skorunu hesapla + göstergeleri döner.

    Pasif kurum (is_active=False) yine ölçülür (pasif olmasının kendisi
    bilgi taşır), ama 'empty_institution' tetiklenir; süper admin 'aktif
    et' kararı için skoru görmek isteyebilir.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if today is None:
        today = now.date()

    cutoff_30d = now - timedelta(days=30)
    cutoff_7d = now - timedelta(days=7)

    # Aktif öğretmen + öğrenci sayıları (kurumu boş mu sorgusu için)
    teacher_count = (
        db.query(User)
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.TEACHER,
            User.is_active.is_(True),
        )
        .count()
    )
    student_count = (
        db.query(User)
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .count()
    )

    # Son 7 günde login yapan teacher / student sayısı + en güncel login zamanı
    teacher_stats = (
        db.query(
            func.count(User.id).label("recent"),
            func.max(User.last_login_at).label("last"),
        )
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.TEACHER,
            User.is_active.is_(True),
            User.last_login_at >= cutoff_7d,
        )
        .first()
    )
    active_teacher_count_7d = int(teacher_stats.recent or 0) if teacher_stats else 0

    last_teacher_login_row = (
        db.query(func.max(User.last_login_at))
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.TEACHER,
            User.is_active.is_(True),
        )
        .scalar()
    )
    last_teacher_login = _normalize_dt(last_teacher_login_row)

    student_stats = (
        db.query(
            func.count(User.id).label("recent"),
        )
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
            User.last_login_at >= cutoff_7d,
        )
        .first()
    )
    active_student_count_7d = int(student_stats.recent or 0) if student_stats else 0

    last_student_login_row = (
        db.query(func.max(User.last_login_at))
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .scalar()
    )
    last_student_login = _normalize_dt(last_student_login_row)

    weekly_rate = _compute_weekly_completion_rate(
        db, institution_id=institution.id, today=today,
    )

    # ---------- Göstergeleri değerlendir ----------
    indicators: list[HealthIndicator] = []
    score = 0

    # 1) Empty institution (öğretmen ya da öğrenci yok)
    is_empty = teacher_count == 0 or student_count == 0
    if is_empty:
        if teacher_count == 0 and student_count == 0:
            detail = "Bu kurumda hiç aktif öğretmen veya öğrenci yok"
        elif teacher_count == 0:
            detail = "Bu kurumda hiç aktif öğretmen yok"
        else:
            detail = "Bu kurumda hiç aktif öğrenci yok"
        indicators.append(HealthIndicator(
            code="empty_institution",
            title="İçi boş kurum",
            detail=detail,
            weight=WEIGHTS["empty_institution"],
        ))
        score += WEIGHTS["empty_institution"]

    # 2) no_teacher_login_30d — yalnızca öğretmen varsa anlamlı
    if teacher_count > 0:
        days = _days_since(last_teacher_login, now)
        teacher_dead = (days is None) or (days >= 30)
        if teacher_dead:
            if days is None:
                t_detail = "Hiçbir öğretmen sisteme hiç girmemiş"
            else:
                t_detail = f"En son öğretmen girişi: {days} gün önce"
            indicators.append(HealthIndicator(
                code="no_teacher_login_30d",
                title="Öğretmenler sistemden uzak",
                detail=t_detail,
                weight=WEIGHTS["no_teacher_login_30d"],
            ))
            score += WEIGHTS["no_teacher_login_30d"]

    # 3) no_student_login_30d
    if student_count > 0:
        days = _days_since(last_student_login, now)
        student_dead = (days is None) or (days >= 30)
        if student_dead:
            if days is None:
                s_detail = "Hiçbir öğrenci sisteme hiç girmemiş"
            else:
                s_detail = f"En son öğrenci girişi: {days} gün önce"
            indicators.append(HealthIndicator(
                code="no_student_login_30d",
                title="Öğrenciler sistemden uzak",
                detail=s_detail,
                weight=WEIGHTS["no_student_login_30d"],
            ))
            score += WEIGHTS["no_student_login_30d"]

    # 4) low_active_teacher_pct — kurum boş değilse + öğretmenler hâlâ erişebiliyorken
    if teacher_count > 0:
        pct = int(round(100 * active_teacher_count_7d / teacher_count))
        if pct < TEACHER_ACTIVE_THRESHOLD_PCT:
            indicators.append(HealthIndicator(
                code="low_active_teacher_pct",
                title="Düşük öğretmen aktivitesi",
                detail=f"Son 7 günde öğretmenlerin sadece %{pct}'i giriş yaptı ({active_teacher_count_7d}/{teacher_count})",
                weight=WEIGHTS["low_active_teacher_pct"],
            ))
            score += WEIGHTS["low_active_teacher_pct"]

    # 5) low_active_student_pct
    if student_count > 0:
        pct = int(round(100 * active_student_count_7d / student_count))
        if pct < STUDENT_ACTIVE_THRESHOLD_PCT:
            indicators.append(HealthIndicator(
                code="low_active_student_pct",
                title="Düşük öğrenci aktivitesi",
                detail=f"Son 7 günde öğrencilerin sadece %{pct}'i giriş yaptı ({active_student_count_7d}/{student_count})",
                weight=WEIGHTS["low_active_student_pct"],
            ))
            score += WEIGHTS["low_active_student_pct"]

    # 6) low_completion — yalnızca plan varsa anlamlı
    if weekly_rate is not None and weekly_rate < LOW_COMPLETION_THRESHOLD_PCT:
        indicators.append(HealthIndicator(
            code="low_completion",
            title="Düşük tamamlama oranı",
            detail=f"Bu haftaki haftalık tamamlama: %{weekly_rate} (eşik: %{LOW_COMPLETION_THRESHOLD_PCT})",
            weight=WEIGHTS["low_completion"],
        ))
        score += WEIGHTS["low_completion"]

    return _build_assessment(
        institution,
        score,
        indicators,
        teacher_count=teacher_count,
        student_count=student_count,
        active_teacher_count_7d=active_teacher_count_7d,
        active_student_count_7d=active_student_count_7d,
        last_teacher_login=last_teacher_login,
        last_student_login=last_student_login,
        weekly_completion_rate=weekly_rate,
    )


# ---------------------------- Toplu hesap ----------------------------


def bulk_health_assessment(
    db: Session, *, institutions: Iterable[Institution],
    now: datetime | None = None, today: date | None = None,
) -> list[HealthAssessment]:
    """Çoklu kurum için sağlık skoru — skoru yüksekten düşüğe sıralı liste.

    Her kurum tek tek hesaplanır; toplam SQL sayısı = N kurum × ~5 sorgu.
    50 kuruma kadar yeterince hızlı (<500ms).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if today is None:
        today = now.date()
    out = [
        compute_health_score(db, institution=i, now=now, today=today)
        for i in institutions
    ]
    # Yüksek skor (tehlikeli) listede önce; aynı skorda alfabetik
    out.sort(key=lambda h: (-h.score, h.institution.name))
    return out


def filter_unhealthy(
    assessments: list[HealthAssessment], min_level: str = "watch",
) -> list[HealthAssessment]:
    """Belirli seviye+'sını döner. Default: watch (30+) ve üstü."""
    levels_order = ["healthy", "watch", "risk", "critical"]
    min_idx = levels_order.index(min_level) if min_level in levels_order else 1
    return [a for a in assessments if levels_order.index(a.level) >= min_idx]


def churn_summary(assessments: list[HealthAssessment]) -> dict[str, int]:
    """Dashboard callout için özet sayım: her seviyeden kaç kurum var."""
    summary = {"healthy": 0, "watch": 0, "risk": 0, "critical": 0}
    for a in assessments:
        summary[a.level] = summary.get(a.level, 0) + 1
    summary["unhealthy_total"] = summary["watch"] + summary["risk"] + summary["critical"]
    summary["needs_attention"] = summary["risk"] + summary["critical"]
    return summary
