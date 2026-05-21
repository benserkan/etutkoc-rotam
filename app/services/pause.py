"""User pause / resume servisi — manuel + otonom uyarı susturma.

Tasarım (2026-05-14):
- `is_paused=True` user'lar at-risk panel, burnout, admin digest, veli
  bildirimi gibi alert üreticilerinden çıkarılır. is_active YA DA login
  hâlâ açık — sadece uyarılar susar.
- Manuel pause: pause_reason="manual", paused_by_id=koç/admin.
- Otonom pause: pause_reason="auto_inactivity", paused_by_id=NULL (sistem).
- Auto-resume: pasif user "canlı sinyal" üretirse (login, task completion)
  ve pause_reason="auto_*" ise cron beklemeden derhal resume.
- Manuel resume: pause_reason ne olursa olsun, last_manual_resume_at
  damgalanır. 7 günlük sticky cooldown — cron bu süre içinde tekrar
  auto-pause yapmaz (manager kararı korunur).
- Cascade YOK: öğretmen pasif olsa öğrencilerinin uyarıları akmaya devam eder.

Eşikler:
- Öğrenci: 21 gün sessizlik
- Öğretmen: 30 gün sessizlik
- Yeni hesap: 14 gün grace period
- Manuel resume sticky: 7 gün
- Günlük auto-pause limiti: aktif kullanıcının %5'i (panik koruyucu)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import AuditAction, Task, TaskStatus, User, UserRole


logger = logging.getLogger(__name__)


# ---------------------------- Sabitler ----------------------------

# Otonom pasifleştirme eşikleri (gün cinsinden)
AUTO_PAUSE_STUDENT_DAYS = 21
AUTO_PAUSE_TEACHER_DAYS = 30

# Yeni hesap koruması — ilk N gün auto-pause yok
NEW_ACCOUNT_GRACE_DAYS = 14

# Manuel resume sonrası cron N gün boyunca tekrar pause etmez
MANUAL_RESUME_STICKY_DAYS = 7

# Günlük auto-pause limit oranı (aktif kullanıcı sayısının oranı)
# Eşik yanlış set edilirse 1000 kişi birden pasifleşmesin diye panik koruyucu.
DAILY_AUTO_PAUSE_RATIO_LIMIT = 0.05  # %5

# pause_reason değerleri
REASON_MANUAL = "manual"
REASON_AUTO_INACTIVITY = "auto_inactivity"


# ---------------------------- Yardımcılar ----------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_user_alerts_muted(user: User) -> bool:
    """Bu user'a ait uyarılar şu an susturulmuş mu?

    Şu an = sadece kendi is_paused durumu (cascade yok).
    Alert servisleri filter olarak `User.is_paused.is_(False)` kullanır;
    bu helper'ı Python tarafında lazy kontroller için bırakıyoruz.
    """
    return bool(user.is_paused)


def get_last_activity_signal(db: Session, user: User) -> datetime | None:
    """Bu user için "son canlı sinyal" zamanını döndür.

    - Öğrenci: max(last_login_at, en son tamamlanan görevin updated_at)
    - Öğretmen: max(last_login_at, en son oluşturduğu görevin created_at)

    Hiç sinyal yoksa None döner.
    """
    signals: list[datetime] = []
    if user.last_login_at:
        signals.append(_as_utc(user.last_login_at))

    if user.role == UserRole.STUDENT:
        latest = (
            db.query(Task.completed_at)
            .filter(
                Task.student_id == user.id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at.isnot(None),
            )
            .order_by(Task.completed_at.desc())
            .first()
        )
        if latest and latest[0]:
            signals.append(_as_utc(latest[0]))
    elif user.role == UserRole.TEACHER:
        # Öğretmenin son aktivitesi: en son hangi öğrencisinin görevini yarattı
        latest = (
            db.query(Task.created_at)
            .join(User, User.id == Task.student_id)
            .filter(User.teacher_id == user.id)
            .order_by(Task.created_at.desc())
            .first()
        )
        if latest and latest[0]:
            signals.append(_as_utc(latest[0]))

    return max(signals) if signals else None


# ---------------------------- Manuel pause / resume ----------------------------


@dataclass
class PauseResult:
    """Servis çıktısı — route'ta audit log için kullanılır."""
    ok: bool
    user_id: int
    was_paused_before: bool
    reason_before: str | None
    reason_now: str | None
    message: str


def pause_user(
    db: Session, target: User, *, actor: User, reason: str = REASON_MANUAL,
) -> PauseResult:
    """Bir user'ı pasifleştir.

    actor — manuel ise koç/admin; otonom ise None (auto_pause_user kullan).
    reason — REASON_MANUAL / REASON_AUTO_INACTIVITY.

    Idempotent: zaten pasifse durumu güncellemez, OK döner.
    """
    was_paused = bool(target.is_paused)
    reason_before = target.pause_reason
    if was_paused:
        return PauseResult(
            ok=True, user_id=target.id,
            was_paused_before=True,
            reason_before=reason_before, reason_now=target.pause_reason,
            message="Zaten pasif",
        )

    target.is_paused = True
    target.paused_at = _now()
    target.paused_by_id = actor.id if actor else None
    target.pause_reason = reason
    db.commit()
    logger.info(
        "pause_user: user=%s reason=%s actor=%s",
        target.id, reason, actor.id if actor else "system",
    )
    return PauseResult(
        ok=True, user_id=target.id,
        was_paused_before=False,
        reason_before=None, reason_now=reason,
        message="Pasifleştirildi",
    )


def resume_user(
    db: Session, target: User, *, actor: User | None,
    is_auto_resume: bool = False,
) -> PauseResult:
    """Bir user'ı tekrar aktif et.

    actor — manuel ise koç/admin; otonom (login/task hook) ise None.
    is_auto_resume — otonom geri açma mı (audit ayrımı için).

    Manuel resume → last_manual_resume_at damgalanır → 7 gün sticky cooldown.
    Idempotent: zaten aktifse OK döner.
    """
    was_paused = bool(target.is_paused)
    reason_before = target.pause_reason
    if not was_paused:
        return PauseResult(
            ok=True, user_id=target.id,
            was_paused_before=False,
            reason_before=None, reason_now=None,
            message="Zaten aktif",
        )

    target.is_paused = False
    target.paused_at = None
    target.paused_by_id = None
    target.pause_reason = None
    if not is_auto_resume:
        # Manuel resume → sticky cooldown
        target.last_manual_resume_at = _now()
    db.commit()
    logger.info(
        "resume_user: user=%s prev_reason=%s actor=%s auto=%s",
        target.id, reason_before,
        actor.id if actor else "system", is_auto_resume,
    )
    return PauseResult(
        ok=True, user_id=target.id,
        was_paused_before=True,
        reason_before=reason_before, reason_now=None,
        message="Aktifleştirildi (auto)" if is_auto_resume else "Aktifleştirildi",
    )


# ---------------------------- Otonom pause ----------------------------


def is_eligible_for_auto_pause(db: Session, user: User, *, now: datetime | None = None) -> tuple[bool, str | None]:
    """User auto-pause için uygun mu? (uygun, sebep_kodu) döner.

    Eligibility kriterleri:
    - is_active=True (zaten kapalı hesabı pasifleştirmek anlamsız)
    - is_paused=False (zaten pasif)
    - role STUDENT veya TEACHER
    - Hesap >= 14 gün önce oluşturulmuş (grace period)
    - last_manual_resume_at son 7 gün içinde değil (sticky)
    - Son canlı sinyal eşik gününden eski
    """
    if now is None:
        now = _now()
    if not user.is_active:
        return False, "inactive_account"
    if user.is_paused:
        return False, "already_paused"
    if user.role not in (UserRole.STUDENT, UserRole.TEACHER):
        return False, "irrelevant_role"

    created = _as_utc(user.created_at)
    if created and (now - created) < timedelta(days=NEW_ACCOUNT_GRACE_DAYS):
        return False, "new_account_grace"

    last_resume = _as_utc(user.last_manual_resume_at)
    if last_resume and (now - last_resume) < timedelta(days=MANUAL_RESUME_STICKY_DAYS):
        return False, "manual_resume_sticky"

    threshold_days = (
        AUTO_PAUSE_STUDENT_DAYS if user.role == UserRole.STUDENT
        else AUTO_PAUSE_TEACHER_DAYS
    )
    last_signal = get_last_activity_signal(db, user)
    if last_signal is None:
        # Hiç sinyal yok — created_at'i sinyal say (grace zaten geçtiyse uygun)
        last_signal = created or now
    if (now - last_signal) >= timedelta(days=threshold_days):
        return True, None
    return False, "still_active"


def find_auto_pause_candidates(
    db: Session, *, now: datetime | None = None,
) -> list[tuple[User, datetime]]:
    """Şu an auto-pause edilmesi gereken user'ları + son sinyal tarihlerini döndürür."""
    if now is None:
        now = _now()
    candidates: list[tuple[User, datetime]] = []
    users = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            User.is_paused.is_(False),
            User.role.in_([UserRole.STUDENT, UserRole.TEACHER]),
        )
        .all()
    )
    for u in users:
        eligible, _ = is_eligible_for_auto_pause(db, u, now=now)
        if eligible:
            last_signal = get_last_activity_signal(db, u) or _as_utc(u.created_at) or now
            candidates.append((u, last_signal))
    return candidates


def maybe_auto_resume(db: Session, user: User) -> bool:
    """Login / task completion hook'larında çağrılır.

    User pasifse ve pause_reason "auto_*" ise hemen resume eder.
    Manuel pasif olanlara dokunmaz (koç kararı korunsun).
    True dönerse resume edildi.
    """
    if not user.is_paused:
        return False
    reason = (user.pause_reason or "")
    if not reason.startswith("auto_"):
        return False
    resume_user(db, user, actor=None, is_auto_resume=True)
    return True
