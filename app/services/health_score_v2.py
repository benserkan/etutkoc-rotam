"""Sprint F.1 (Ticari Pano 2.0 — Faz C) — Sağlık Skoru 2.0 + Erken Uyarı.

Kullanım bazlı sağlık skoru — 6 ağırlıklı bileşen:
  1) Aktif öğretmen oranı (haftalık)         %25
  2) Aktif öğrenci oranı (haftalık)           %25
  3) Görev tamamlama oranı (haftalık)         %15
  4) Bildirim başarı oranı (son 30g)          %10
  5) Ödeme zamanlılığı (son 90g)              %15
  6) Plan yaşı (kurumun ay cinsinden ömrü)    %10
  TOPLAM:                                     %100

Skor user-facing 0-100 (yüksek=sağlıklı). Band sınırları:
  80-100 = champion
  60-79  = healthy
  40-59  = at_risk
  20-39  = critical
  0-19   = lost_imminent

Günlük snapshot HealthScoreSnapshot'a yazılır. "7 gün üst üste düşüş"
tetikleyici için son N snapshot karşılaştırılır.

Erken uyarı tetikleyicileri:
  T1: Aktif öğretmen sayısı 7 gün içinde %30+ düştü
  T2: Hafta sonu sıfır görev tamamlandı (Cuma-Pazar 0)
  T3: Skor son 7 günde sürekli düştü (monoton azalan)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    HealthScoreSnapshot,
    Institution,
    Invoice,
    InvoiceStatus,
    Task,
    TaskBookItem,
    User,
    UserRole,
    band_for_score,
)
from app.models.health_score_snapshot import (
    HEALTH_BAND_COLORS,
    HEALTH_BAND_EMOJIS,
    HEALTH_BAND_LABELS_TR,
)


logger = logging.getLogger(__name__)


# ---------------------------- Ağırlıklar ----------------------------

WEIGHTS_V2: dict[str, int] = {
    "active_teacher_pct": 25,
    "active_student_pct": 25,
    "weekly_completion_pct": 15,
    "notification_success_pct": 10,
    "payment_timeliness_pct": 15,
    "plan_age_pct": 10,
}

# User varyantı (bağımsız öğretmen): active_teacher_pct çıkarıldı (tek kişi).
# Kalan 5 bileşen 75 toplamından 100'e yeniden ölçeklendi.
WEIGHTS_V2_USER: dict[str, int] = {
    "active_student_pct": 33,
    "weekly_completion_pct": 20,
    "notification_success_pct": 13,
    "payment_timeliness_pct": 20,
    "plan_age_pct": 14,
}


COMPONENT_LABELS_TR: dict[str, str] = {
    "active_teacher_pct": "Aktif öğretmen oranı",
    "active_student_pct": "Aktif öğrenci oranı",
    "weekly_completion_pct": "Görev tamamlama oranı",
    "notification_success_pct": "Bildirim başarısı",
    "payment_timeliness_pct": "Ödeme zamanlılığı",
    "plan_age_pct": "Plan yaşı (sadakat)",
}


# ---------------------------- Veri yapıları ----------------------------


@dataclass
class HealthComponent:
    code: str
    label: str
    weight_pct: int          # bileşen ağırlığı (0-100)
    value_pct: int           # bileşenin gerçekleşme oranı (0-100, yüksek=iyi)
    contribution: int        # skora katkı = weight * value / 100
    note: str | None = None


@dataclass
class HealthScoreV2:
    institution_id: int | None = None       # backward compat (user variant'ta None)
    user_id: int | None = None
    owner_type: str = "institution"
    score: int = 0           # 0-100, yüksek=sağlıklı
    band: str = "healthy"
    band_label: str = ""
    band_color: str = ""
    band_emoji: str = ""
    components: list[HealthComponent] = field(default_factory=list)
    active_teacher_count: int = 0
    active_student_count: int = 0


@dataclass
class WarningTrigger:
    code: str                # "teacher_drop_30pct" | "weekend_zero_solve" | "score_decline_7d"
    title: str
    detail: str
    severity: str            # "info" | "warning" | "critical"


# ---------------------------- Yardımcılar ----------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _now().date()


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------- Bileşen hesaplama ----------------------------


def _component_active_teacher(
    db: Session, *, institution_id: int, now: datetime,
) -> HealthComponent:
    cutoff_7d = now - timedelta(days=7)
    total = (
        db.query(func.count(User.id))
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.TEACHER,
            User.is_active.is_(True),
        )
        .scalar() or 0
    )
    active = (
        db.query(func.count(User.id))
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.TEACHER,
            User.is_active.is_(True),
            User.last_login_at >= cutoff_7d,
        )
        .scalar() or 0
    )
    if total == 0:
        # Hiç öğretmen yoksa bileşen %0 (kötü)
        value_pct = 0
        note = "Aktif öğretmen yok"
    else:
        value_pct = min(100, int(round(100 * active / total)))
        note = f"{active}/{total} öğretmen son 7g aktif"
    weight = WEIGHTS_V2["active_teacher_pct"]
    return HealthComponent(
        code="active_teacher_pct",
        label=COMPONENT_LABELS_TR["active_teacher_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


def _component_active_student(
    db: Session, *, institution_id: int, now: datetime,
) -> HealthComponent:
    cutoff_7d = now - timedelta(days=7)
    total = (
        db.query(func.count(User.id))
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .scalar() or 0
    )
    active = (
        db.query(func.count(User.id))
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
            User.last_login_at >= cutoff_7d,
        )
        .scalar() or 0
    )
    if total == 0:
        value_pct = 0
        note = "Aktif öğrenci yok"
    else:
        value_pct = min(100, int(round(100 * active / total)))
        note = f"{active}/{total} öğrenci son 7g aktif"
    weight = WEIGHTS_V2["active_student_pct"]
    return HealthComponent(
        code="active_student_pct",
        label=COMPONENT_LABELS_TR["active_student_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


def _component_weekly_completion(
    db: Session, *, institution_id: int, today: date,
) -> HealthComponent:
    week_start = today - timedelta(days=6)
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
            Task.date <= today,
        )
        .first()
    )
    planned = int(row.p) if row else 0
    completed = int(row.c) if row else 0
    if planned == 0:
        value_pct = 0
        note = "Son 7g hiç görev planlanmamış"
    else:
        value_pct = min(100, int(round(100 * completed / planned)))
        note = f"{completed}/{planned} görev tamamlandı"
    weight = WEIGHTS_V2["weekly_completion_pct"]
    return HealthComponent(
        code="weekly_completion_pct",
        label=COMPONENT_LABELS_TR["weekly_completion_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


def _component_notification_success(
    db: Session, *, institution_id: int, now: datetime,
) -> HealthComponent:
    cutoff_30d = now - timedelta(days=30)
    weight = WEIGHTS_V2["notification_success_pct"]
    try:
        from app.models import NotificationLog, NotificationStatus
        # Student üzerinden institution'a bağlan (parent kurumda olmayabilir)
        student_alias = User
        sent = int(
            (db.query(func.count(NotificationLog.id))
             .join(student_alias, student_alias.id == NotificationLog.student_id)
             .filter(
                 student_alias.institution_id == institution_id,
                 NotificationLog.sent_at >= cutoff_30d,
                 NotificationLog.status == NotificationStatus.SENT,
             )
             .scalar()) or 0
        )
        failed = int(
            (db.query(func.count(NotificationLog.id))
             .join(student_alias, student_alias.id == NotificationLog.student_id)
             .filter(
                 student_alias.institution_id == institution_id,
                 NotificationLog.sent_at >= cutoff_30d,
                 NotificationLog.status == NotificationStatus.FAILED,
             )
             .scalar()) or 0
        )
    except Exception:
        logger.exception("notification_success_pct: skip")
        sent, failed = 0, 0
    total = sent + failed
    if total == 0:
        # Veri yoksa nötr (orta puan)
        value_pct = 60
        note = "Yeterli bildirim verisi yok (nötr)"
    else:
        value_pct = min(100, int(round(100 * sent / total)))
        note = f"{sent}/{total} bildirim başarılı"
    return HealthComponent(
        code="notification_success_pct",
        label=COMPONENT_LABELS_TR["notification_success_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


def _component_payment_timeliness(
    db: Session, *, institution_id: int, now: datetime,
) -> HealthComponent:
    cutoff_90d = now - timedelta(days=90)
    weight = WEIGHTS_V2["payment_timeliness_pct"]
    rows = (
        db.query(Invoice.status, Invoice.paid_at, Invoice.due_at)
        .filter(
            Invoice.institution_id == institution_id,
            Invoice.created_at >= cutoff_90d,
            Invoice.status.in_([
                InvoiceStatus.PAID,
                InvoiceStatus.OVERDUE,
                InvoiceStatus.PENDING,
            ]),
        )
        .all()
    )
    on_time = 0
    late = 0
    for r in rows:
        if r.status == InvoiceStatus.PAID and r.paid_at and r.due_at:
            paid = _aware(r.paid_at)
            due = _aware(r.due_at)
            if paid and due:
                if paid <= due:
                    on_time += 1
                else:
                    late += 1
        elif r.status == InvoiceStatus.OVERDUE:
            late += 1
    total = on_time + late
    if total == 0:
        # Veri yoksa nötr (50)
        value_pct = 50
        note = "Son 90g'de fatura yok (nötr)"
    else:
        value_pct = min(100, int(round(100 * on_time / total)))
        note = f"{on_time}/{total} fatura zamanında"
    return HealthComponent(
        code="payment_timeliness_pct",
        label=COMPONENT_LABELS_TR["payment_timeliness_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


# ---------------------------- User varyantı bileşenleri ----------------------------
# Bağımsız öğretmen: kendi öğrencileri (User.teacher_id = user.id) üzerinden hesap.


def _component_active_student_for_user(
    db: Session, *, teacher_user_id: int, now: datetime,
) -> HealthComponent:
    cutoff_7d = now - timedelta(days=7)
    total = (
        db.query(func.count(User.id))
        .filter(
            User.teacher_id == teacher_user_id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .scalar() or 0
    )
    active = (
        db.query(func.count(User.id))
        .filter(
            User.teacher_id == teacher_user_id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
            User.last_login_at >= cutoff_7d,
        )
        .scalar() or 0
    )
    if total == 0:
        value_pct = 0
        note = "Aktif öğrenci yok"
    else:
        value_pct = min(100, int(round(100 * active / total)))
        note = f"{active}/{total} öğrenci son 7g aktif"
    weight = WEIGHTS_V2_USER["active_student_pct"]
    return HealthComponent(
        code="active_student_pct",
        label=COMPONENT_LABELS_TR["active_student_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


def _component_weekly_completion_for_user(
    db: Session, *, teacher_user_id: int, today: date,
) -> HealthComponent:
    week_start = today - timedelta(days=6)
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
            User.teacher_id == teacher_user_id,
            User.is_active.is_(True),
            Task.date >= week_start,
            Task.date <= today,
        )
        .first()
    )
    planned = int(row.p) if row else 0
    completed = int(row.c) if row else 0
    if planned == 0:
        value_pct = 0
        note = "Son 7g hiç görev planlanmamış"
    else:
        value_pct = min(100, int(round(100 * completed / planned)))
        note = f"{completed}/{planned} görev tamamlandı"
    weight = WEIGHTS_V2_USER["weekly_completion_pct"]
    return HealthComponent(
        code="weekly_completion_pct",
        label=COMPONENT_LABELS_TR["weekly_completion_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


def _component_notification_success_for_user(
    db: Session, *, teacher_user_id: int, now: datetime,
) -> HealthComponent:
    cutoff_30d = now - timedelta(days=30)
    weight = WEIGHTS_V2_USER["notification_success_pct"]
    try:
        from app.models import NotificationLog, NotificationStatus
        sent = int(
            (db.query(func.count(NotificationLog.id))
             .join(User, User.id == NotificationLog.student_id)
             .filter(
                 User.teacher_id == teacher_user_id,
                 NotificationLog.sent_at >= cutoff_30d,
                 NotificationLog.status == NotificationStatus.SENT,
             )
             .scalar()) or 0
        )
        failed = int(
            (db.query(func.count(NotificationLog.id))
             .join(User, User.id == NotificationLog.student_id)
             .filter(
                 User.teacher_id == teacher_user_id,
                 NotificationLog.sent_at >= cutoff_30d,
                 NotificationLog.status == NotificationStatus.FAILED,
             )
             .scalar()) or 0
        )
    except Exception:
        logger.exception("notification_success_pct user: skip")
        sent, failed = 0, 0
    total = sent + failed
    if total == 0:
        value_pct = 60
        note = "Yeterli bildirim verisi yok (nötr)"
    else:
        value_pct = min(100, int(round(100 * sent / total)))
        note = f"{sent}/{total} bildirim başarılı"
    return HealthComponent(
        code="notification_success_pct",
        label=COMPONENT_LABELS_TR["notification_success_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


def _component_payment_timeliness_for_user(
    db: Session, *, teacher_user_id: int, now: datetime,
) -> HealthComponent:
    cutoff_90d = now - timedelta(days=90)
    weight = WEIGHTS_V2_USER["payment_timeliness_pct"]
    rows = (
        db.query(Invoice.status, Invoice.paid_at, Invoice.due_at)
        .filter(
            Invoice.user_id == teacher_user_id,
            Invoice.created_at >= cutoff_90d,
            Invoice.status.in_([
                InvoiceStatus.PAID,
                InvoiceStatus.OVERDUE,
                InvoiceStatus.PENDING,
            ]),
        )
        .all()
    )
    on_time = 0
    late = 0
    for r in rows:
        if r.status == InvoiceStatus.PAID and r.paid_at and r.due_at:
            paid = _aware(r.paid_at)
            due = _aware(r.due_at)
            if paid and due:
                if paid <= due:
                    on_time += 1
                else:
                    late += 1
        elif r.status == InvoiceStatus.OVERDUE:
            late += 1
    total = on_time + late
    if total == 0:
        value_pct = 50
        note = "Son 90g'de fatura yok (nötr)"
    else:
        value_pct = min(100, int(round(100 * on_time / total)))
        note = f"{on_time}/{total} fatura zamanında"
    return HealthComponent(
        code="payment_timeliness_pct",
        label=COMPONENT_LABELS_TR["payment_timeliness_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


def _component_plan_age_for_user(
    user_obj: User, *, now: datetime,
) -> HealthComponent:
    weight = WEIGHTS_V2_USER["plan_age_pct"]
    ca = _aware(user_obj.created_at) or now
    age_months = (now - ca).days / 30.0
    value_pct = min(100, int(round(100 * min(12.0, age_months) / 12.0)))
    note = f"Hesap yaşı: {age_months:.1f} ay"
    return HealthComponent(
        code="plan_age_pct",
        label=COMPONENT_LABELS_TR["plan_age_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


def _component_plan_age(
    institution: Institution, *, now: datetime,
) -> HealthComponent:
    weight = WEIGHTS_V2["plan_age_pct"]
    ca = _aware(institution.created_at) or now
    age_months = (now - ca).days / 30.0
    # 0-12 ay lineer, 12+ ay full puan (sadakat)
    value_pct = min(100, int(round(100 * min(12.0, age_months) / 12.0)))
    note = f"Kurum yaşı: {age_months:.1f} ay"
    return HealthComponent(
        code="plan_age_pct",
        label=COMPONENT_LABELS_TR["plan_age_pct"],
        weight_pct=weight,
        value_pct=value_pct,
        contribution=int(round(weight * value_pct / 100)),
        note=note,
    )


# ---------------------------- Skor hesaplama ----------------------------


def compute_health_score_v2(
    db: Session, *, institution: Institution, now: datetime | None = None,
) -> HealthScoreV2:
    """Bir kurumun v2 sağlık skorunu üret (0-100 user-facing)."""
    if now is None:
        now = _now()
    today = now.date()

    components: list[HealthComponent] = [
        _component_active_teacher(db, institution_id=institution.id, now=now),
        _component_active_student(db, institution_id=institution.id, now=now),
        _component_weekly_completion(
            db, institution_id=institution.id, today=today,
        ),
        _component_notification_success(
            db, institution_id=institution.id, now=now,
        ),
        _component_payment_timeliness(
            db, institution_id=institution.id, now=now,
        ),
        _component_plan_age(institution, now=now),
    ]

    score = sum(c.contribution for c in components)
    score = max(0, min(100, score))
    band = band_for_score(score)

    # Aktif sayılar (snapshot için)
    cutoff_7d = now - timedelta(days=7)
    active_t = (
        db.query(func.count(User.id))
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.TEACHER,
            User.is_active.is_(True),
            User.last_login_at >= cutoff_7d,
        )
        .scalar() or 0
    )
    active_s = (
        db.query(func.count(User.id))
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
            User.last_login_at >= cutoff_7d,
        )
        .scalar() or 0
    )

    return HealthScoreV2(
        institution_id=institution.id,
        owner_type="institution",
        score=score,
        band=band,
        band_label=HEALTH_BAND_LABELS_TR.get(band, band),
        band_color=HEALTH_BAND_COLORS.get(band, "slate"),
        band_emoji=HEALTH_BAND_EMOJIS.get(band, "•"),
        components=components,
        active_teacher_count=int(active_t),
        active_student_count=int(active_s),
    )


def compute_health_score_v2_for_user(
    db: Session, *, user_obj: User, now: datetime | None = None,
) -> HealthScoreV2:
    """Bağımsız öğretmen için 5 bileşenli sağlık skoru.

    active_teacher_pct bileşeni kaldırıldı (tek kişi). Ağırlıklar 100'e
    yeniden ölçeklendi (WEIGHTS_V2_USER). Diğer bileşenler bağımsız
    öğretmenin kendi öğrencileri (User.teacher_id) üzerinden hesaplanır.
    """
    if now is None:
        now = _now()
    today = now.date()

    components: list[HealthComponent] = [
        _component_active_student_for_user(
            db, teacher_user_id=user_obj.id, now=now,
        ),
        _component_weekly_completion_for_user(
            db, teacher_user_id=user_obj.id, today=today,
        ),
        _component_notification_success_for_user(
            db, teacher_user_id=user_obj.id, now=now,
        ),
        _component_payment_timeliness_for_user(
            db, teacher_user_id=user_obj.id, now=now,
        ),
        _component_plan_age_for_user(user_obj, now=now),
    ]
    score = sum(c.contribution for c in components)
    score = max(0, min(100, score))
    band = band_for_score(score)

    # Aktif öğrenci sayısı (snapshot için, trigger algılama)
    cutoff_7d = now - timedelta(days=7)
    active_s = (
        db.query(func.count(User.id))
        .filter(
            User.teacher_id == user_obj.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
            User.last_login_at >= cutoff_7d,
        )
        .scalar() or 0
    )

    return HealthScoreV2(
        user_id=user_obj.id,
        owner_type="user",
        score=score,
        band=band,
        band_label=HEALTH_BAND_LABELS_TR.get(band, band),
        band_color=HEALTH_BAND_COLORS.get(band, "slate"),
        band_emoji=HEALTH_BAND_EMOJIS.get(band, "•"),
        components=components,
        active_teacher_count=0,  # bağımsız öğretmen tek kişi
        active_student_count=int(active_s),
    )


# ---------------------------- Snapshot kaydı ----------------------------


def record_snapshot_for(
    db: Session, *,
    institution: Institution | None = None,
    user_obj: User | None = None,
    snapshot_date: date | None = None,
    now: datetime | None = None,
    autocommit: bool = True,
) -> HealthScoreSnapshot:
    """Owner için snapshot yaz (varsa update). XOR: institution veya user_obj."""
    if snapshot_date is None:
        snapshot_date = _today()
    if (institution is None) == (user_obj is None):
        raise ValueError("record_snapshot_for: institution veya user_obj (tam biri)")

    if institution is not None:
        h = compute_health_score_v2(db, institution=institution, now=now)
        owner_filter = (
            HealthScoreSnapshot.institution_id == institution.id,
            HealthScoreSnapshot.snapshot_date == snapshot_date,
        )
        new_kwargs = {
            "owner_type": "institution",
            "institution_id": institution.id,
            "user_id": None,
        }
    else:
        h = compute_health_score_v2_for_user(db, user_obj=user_obj, now=now)
        owner_filter = (
            HealthScoreSnapshot.user_id == user_obj.id,
            HealthScoreSnapshot.snapshot_date == snapshot_date,
        )
        new_kwargs = {
            "owner_type": "user",
            "institution_id": None,
            "user_id": user_obj.id,
        }

    existing = (
        db.query(HealthScoreSnapshot).filter(*owner_filter).first()
    )
    components_payload = [
        {
            "code": c.code, "label": c.label, "weight_pct": c.weight_pct,
            "value_pct": c.value_pct, "contribution": c.contribution,
            "note": c.note,
        }
        for c in h.components
    ]
    cjson = json.dumps(components_payload, ensure_ascii=False)
    if existing:
        existing.score = h.score
        existing.band = h.band
        existing.components_json = cjson
        existing.active_teacher_count = h.active_teacher_count
        existing.active_student_count = h.active_student_count
        snap = existing
    else:
        snap = HealthScoreSnapshot(
            snapshot_date=snapshot_date,
            score=h.score,
            band=h.band,
            components_json=cjson,
            active_teacher_count=h.active_teacher_count,
            active_student_count=h.active_student_count,
            **new_kwargs,
        )
        db.add(snap)
    if autocommit:
        db.commit()
        if not existing:
            db.refresh(snap)
    return snap


def record_daily_snapshots(
    db: Session, *,
    snapshot_date: date | None = None,
    autocommit: bool = True,
) -> dict:
    """Cron: tüm aktif owner'lar (kurum + bağımsız öğretmen) için snapshot."""
    if snapshot_date is None:
        snapshot_date = _today()
    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    inst_count = 0
    for inst in insts:
        try:
            record_snapshot_for(
                db, institution=inst, snapshot_date=snapshot_date,
                autocommit=False,
            )
            inst_count += 1
        except Exception:
            logger.exception("snapshot fail inst=%s", inst.id)

    # Sprint F.3 — bağımsız öğretmenler için de snapshot
    indep_users = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .all()
    )
    user_count = 0
    for u in indep_users:
        try:
            record_snapshot_for(
                db, user_obj=u, snapshot_date=snapshot_date,
                autocommit=False,
            )
            user_count += 1
        except Exception:
            logger.exception("snapshot fail user=%s", u.id)

    if autocommit:
        db.commit()
    return {
        "snapshot_date": snapshot_date.isoformat(),
        "count": inst_count + user_count,
        "institution_count": inst_count,
        "user_count": user_count,
    }


def get_score_history(
    db: Session, *,
    institution_id: int | None = None,
    user_id: int | None = None,
    days: int = 14,
) -> list[HealthScoreSnapshot]:
    """Son N gün snapshot listesi (eskiden yeniye sıralı). Owner-aware."""
    cutoff = _today() - timedelta(days=days)
    q = db.query(HealthScoreSnapshot).filter(
        HealthScoreSnapshot.snapshot_date >= cutoff,
    )
    if institution_id is not None and user_id is None:
        q = q.filter(HealthScoreSnapshot.institution_id == institution_id)
    elif user_id is not None and institution_id is None:
        q = q.filter(HealthScoreSnapshot.user_id == user_id)
    else:
        raise ValueError("get_score_history: institution_id veya user_id (tam biri)")
    return (
        q
        .order_by(HealthScoreSnapshot.snapshot_date)
        .all()
    )


# ---------------------------- Erken uyarı tetikleyiciler ----------------------------


def detect_warning_triggers(
    db: Session, *, institution: Institution, now: datetime | None = None,
) -> list[WarningTrigger]:
    """Bir kurum için aktif erken uyarı tetikleyicilerini döndür."""
    if now is None:
        now = _now()
    today = now.date()
    triggers: list[WarningTrigger] = []

    # T1: Öğretmen sayısı 7g'de %30+ düştü (snapshot karşılaştırma)
    snap_today = (
        db.query(HealthScoreSnapshot)
        .filter(
            HealthScoreSnapshot.institution_id == institution.id,
            HealthScoreSnapshot.snapshot_date <= today,
        )
        .order_by(HealthScoreSnapshot.snapshot_date.desc())
        .first()
    )
    snap_7d_ago = (
        db.query(HealthScoreSnapshot)
        .filter(
            HealthScoreSnapshot.institution_id == institution.id,
            HealthScoreSnapshot.snapshot_date <= today - timedelta(days=7),
        )
        .order_by(HealthScoreSnapshot.snapshot_date.desc())
        .first()
    )
    if snap_today and snap_7d_ago and snap_7d_ago.active_teacher_count >= 3:
        before = snap_7d_ago.active_teacher_count
        after = snap_today.active_teacher_count
        if before > 0:
            drop_pct = 100 * (before - after) / before
            if drop_pct >= 30:
                triggers.append(WarningTrigger(
                    code="teacher_drop_30pct",
                    title="Aktif öğretmen sayısı düştü",
                    detail=(
                        f"7 gün önce {before} aktif öğretmen vardı, şimdi {after}. "
                        f"%{int(round(drop_pct))} düşüş."
                    ),
                    severity="critical",
                ))

    # T2: Hafta sonu sıfır görev tamamlandı (Cuma-Pazar)
    # Son cumartesi-pazar
    days_since_sat = (today.weekday() - 5) % 7  # weekday: Mon=0..Sun=6
    last_sat = today - timedelta(days=days_since_sat or 7)
    last_sun = last_sat + timedelta(days=1)
    weekend_completion = (
        db.query(
            func.coalesce(func.sum(TaskBookItem.completed_count), 0)
        )
        .select_from(User)
        .join(Task, Task.student_id == User.id)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution.id,
            User.is_active.is_(True),
            Task.date >= last_sat,
            Task.date <= last_sun,
        )
        .scalar()
    )
    weekend_completed = int(weekend_completion or 0)
    # T2 sadece ücretli planda anlamlı; trial/free için flag etmez
    student_count = (
        db.query(func.count(User.id))
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .scalar() or 0
    )
    if student_count >= 5 and weekend_completed == 0:
        triggers.append(WarningTrigger(
            code="weekend_zero_solve",
            title="Hafta sonu sıfır aktivite",
            detail=(
                f"Son Cuma-Pazar arası ({last_sat.strftime('%d.%m')} - "
                f"{last_sun.strftime('%d.%m')}) hiç görev tamamlanmamış."
            ),
            severity="warning",
        ))

    # T3: Son 7 günde skor monoton düştü
    history = (
        db.query(HealthScoreSnapshot)
        .filter(
            HealthScoreSnapshot.institution_id == institution.id,
            HealthScoreSnapshot.snapshot_date >= today - timedelta(days=7),
        )
        .order_by(HealthScoreSnapshot.snapshot_date)
        .all()
    )
    if len(history) >= 4:
        scores = [s.score for s in history]
        # Monoton azalma kontrolü (her birinden bir sonraki <=, ve toplam düşüş >= 10)
        is_declining = all(
            scores[i] >= scores[i + 1] for i in range(len(scores) - 1)
        )
        total_drop = scores[0] - scores[-1]
        if is_declining and total_drop >= 10:
            triggers.append(WarningTrigger(
                code="score_decline_7d",
                title="Skor 7 gündür düşüyor",
                detail=(
                    f"Skor {scores[0]} → {scores[-1]} ({total_drop} puan düşüş). "
                    f"Acil temas önerilir."
                ),
                severity="critical",
            ))

    return triggers


__all__ = [
    "COMPONENT_LABELS_TR",
    "HealthComponent",
    "HealthScoreV2",
    "WEIGHTS_V2",
    "WarningTrigger",
    "compute_health_score_v2",
    "detect_warning_triggers",
    "get_score_history",
    "record_daily_snapshots",
    "record_snapshot_for",
]
