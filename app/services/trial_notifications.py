"""Koç trial bildirimleri — son 3 gün hatırlatma + bitiş e-postası.

Yeni cron YOK: mevcut günlük `trial_expire` job'ı (cron_jobs.trial_expire)
bunları çağırır. Yeni tablo/migration YOK — dedup, otomatik oluşturulan
PLAN_UPGRADE teklifinin varlığıyla yapılır.

Akış (kullanıcı kararı 2026-05-22):
  - Son 3 gün: koça "3 gün kaldı" e-postası + otomatik DRAFT teklif (süper
    admin CRM/360'ta görünür = admin bildirimi).
  - Deneme bitince: koça "deneme bitti, ücretsize düştün" e-postası.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.models.offer import Offer, OfferKind, OfferStatus
from app.services import offers as offers_service
from app.services.email_service import send_email
from app.services.plans import SOLO_PRO, SOLO_TRIAL, trial_days_left

logger = logging.getLogger(__name__)

REMINDER_WINDOW_DAYS = 3


def _first_super_admin_id(db: Session) -> int | None:
    row = (
        db.query(User.id)
        .filter(User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True))
        .order_by(User.id)
        .first()
    )
    return row[0] if row else None


def _has_open_upgrade_offer(db: Session, *, user_id: int) -> bool:
    return (
        db.query(Offer.id)
        .filter(
            Offer.user_id == user_id,
            Offer.kind == OfferKind.PLAN_UPGRADE,
            Offer.status.in_([OfferStatus.DRAFT, OfferStatus.SENT]),
        )
        .first()
        is not None
    )


def send_trial_reminders(db: Session, *, now: datetime | None = None) -> int:
    """Trial'ı ≤3 gün içinde bitecek bağımsız koçlara hatırlatma + otomatik teklif.

    Dedup: koçun açık (DRAFT/SENT) PLAN_UPGRADE teklifi varsa atlanır → her
    trial için bir kez çalışır. Returns: işlenen koç sayısı.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=REMINDER_WINDOW_DAYS)
    coaches = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.plan == SOLO_TRIAL,
            User.is_active.is_(True),
            User.trial_ends_at.isnot(None),
            User.trial_ends_at > now,
            User.trial_ends_at <= horizon,
        )
        .all()
    )
    if not coaches:
        return 0

    admin_id = _first_super_admin_id(db)
    processed = 0
    for c in coaches:
        if _has_open_upgrade_offer(db, user_id=c.id):
            continue
        days = trial_days_left(owner=c, now=now) or 0

        # Otomatik DRAFT teklif — süper admin CRM/360'ta görünür (admin bildirimi).
        if admin_id is not None:
            try:
                offers_service.create_offer(
                    db, user_id=c.id, kind="plan_upgrade",
                    title="Pro'ya geçiş — deneme bitiyor",
                    by_user_id=admin_id, new_plan=SOLO_PRO,
                    public_message=(
                        "Deneme süreniz bitiyor. Solo Pro'ya geçerek tüm "
                        "öğrencileriniz ve yapay zekâ özellikleriyle devam edin."
                    ),
                    expires_in_days=7, autocommit=False,
                )
            except Exception:
                logger.exception("trial reminder offer fail user=%s", c.id)

        try:
            send_email(
                to=c.email, template="trial_reminder",
                ctx={
                    "full_name": c.full_name or c.email,
                    "days_left": days,
                    "upgrade_url_path": "/teacher/plan",
                },
            )
        except Exception:
            logger.exception("trial reminder email fail user=%s", c.id)
        processed += 1

    db.commit()
    logger.info("send_trial_reminders: %s koç işlendi", processed)
    return processed


def process_renewals(db: Session, *, now: datetime | None = None) -> dict:
    """Aktif solo aboneliklerin yenileme döngüsü.

    - Yenilemeye 3 gün kala → "yenileme yaklaşıyor" e-postası (gün-3 penceresi,
      bir kez).
    - Dönem sonu geçti → `subscription_status='past_due'` (plan düşmez; paywall
      devreye girer) + "ödeme gerekli" e-postası.
    Returns: {"reminded": N, "past_due": N}
    """
    if now is None:
        now = datetime.now(timezone.utc)
    reminded = 0
    past_due = 0

    # Yaklaşan yenileme (gün-3 penceresi — bir kez tetiklenir)
    upcoming = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.subscription_status == "active",
            User.subscription_period_end.isnot(None),
            User.subscription_period_end > now + timedelta(days=2),
            User.subscription_period_end <= now + timedelta(days=3),
        )
        .all()
    )
    for u in upcoming:
        try:
            send_email(
                to=u.email, template="renewal_reminder",
                ctx={"full_name": u.full_name or u.email, "upgrade_url_path": "/teacher/plan"},
            )
        except Exception:
            logger.exception("renewal reminder fail user=%s", u.id)
        reminded += 1

    # Dönem sonu geçti
    canceled_dropped = 0
    overdue = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.subscription_status.in_(["active", "canceled"]),
            User.subscription_period_end.isnot(None),
            User.subscription_period_end <= now,
        )
        .all()
    )
    from app.models import PlanChangeReason, PlanOwnerType
    from app.services.plans import SOLO_FREE, change_plan
    for u in overdue:
        if u.subscription_status == "canceled":
            # İptal edilmişti → dönem sonunda ücretsize düş (past_due değil).
            change_plan(
                db, owner_type=PlanOwnerType.USER, owner_id=u.id, new_plan=SOLO_FREE,
                reason=PlanChangeReason.DOWNGRADE, note="Abonelik iptali — dönem sonu",
                autocommit=False,
            )
            u.subscription_status = None
            u.subscription_period_end = None
            u.subscription_cycle = None
            canceled_dropped += 1
        else:
            u.subscription_status = "past_due"
            try:
                send_email(
                    to=u.email, template="renewal_overdue",
                    ctx={"full_name": u.full_name or u.email, "upgrade_url_path": "/teacher/plan"},
                )
            except Exception:
                logger.exception("renewal overdue fail user=%s", u.id)
            past_due += 1

    db.commit()
    logger.info("process_renewals: reminded=%s past_due=%s canceled_dropped=%s",
                reminded, past_due, canceled_dropped)
    return {"reminded": reminded, "past_due": past_due, "canceled_dropped": canceled_dropped}


def notify_trial_expired(db: Session, *, user_ids: list[int]) -> int:
    """Trial'ı yeni dolmuş koçlara "deneme bitti" e-postası. Returns: gönderilen."""
    if not user_ids:
        return 0
    sent = 0
    for uid in user_ids:
        u = db.get(User, uid)
        if u is None or not u.email:
            continue
        try:
            send_email(
                to=u.email, template="trial_expired",
                ctx={
                    "full_name": u.full_name or u.email,
                    "upgrade_url_path": "/teacher/plan",
                },
            )
            sent += 1
        except Exception:
            logger.exception("trial expired email fail user=%s", uid)
    return sent
