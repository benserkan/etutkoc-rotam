"""Sprint D.1 (Ticari Pano 2.0 — Faz E Seviye 1) — Bireysel teklif servisi.

İş akışı:
  1) Admin Kurum 360'tan teklif oluşturur → status = DRAFT
  2) Admin "Gönder" der → status = SENT, sent_at set
  3) Kuruma public link gönderilir: /offers/{token}
  4) Kurum yetkilisi linki açar, "Kabul" veya "Reddet" der
  5) Kabul: status = ACCEPTED, plan değişim tetikle (varsa) + PlanChangeHistory
     Ret: status = DECLINED, decline_reason kaydet
  6) Expire: status = EXPIRED (cron veya manuel)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import (
    Institution,
    Offer,
    OfferKind,
    OfferStatus,
    PlanChangeHistory,
    PlanChangeReason,
    User,
)
from app.models.plan_history import PlanOwnerType


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# Tür → birim eşlemesi (UI form için varsayılan)
KIND_DEFAULTS: dict[OfferKind, dict] = {
    OfferKind.DISCOUNT_PERCENT: {"unit": "%", "needs_value": True, "needs_duration": True},
    OfferKind.DISCOUNT_FIXED: {"unit": "TRY", "needs_value": True, "needs_duration": True},
    OfferKind.TRIAL_EXTENSION: {"unit": "gün", "needs_value": True, "needs_duration": False},
    OfferKind.PLAN_UPGRADE: {"unit": None, "needs_value": False, "needs_duration": True},
    OfferKind.FREE_FEATURE: {"unit": None, "needs_value": False, "needs_duration": True},
    OfferKind.ONBOARDING_HOURS: {"unit": "saat", "needs_value": True, "needs_duration": False},
    OfferKind.CUSTOM: {"unit": None, "needs_value": False, "needs_duration": False},
}


# ---------------------------- CRUD ----------------------------


def create_offer(
    db: Session, *,
    institution_id: int | None = None,
    user_id: int | None = None,
    kind: str,
    title: str,
    by_user_id: int,
    value: float | None = None,
    value_unit: str | None = None,
    duration_months: int | None = None,
    new_plan: str | None = None,
    admin_note: str | None = None,
    public_message: str | None = None,
    expires_in_days: int | None = 14,
    autocommit: bool = True,
) -> Offer | None:
    """Yeni teklif oluştur (status=DRAFT).
    Owner XOR: `institution_id` veya `user_id` — tam biri verilmeli."""
    try:
        kind_enum = OfferKind(kind)
    except ValueError:
        return None
    if (institution_id is None) == (user_id is None):
        raise ValueError("create_offer: institution_id veya user_id (tam biri)")
    if institution_id is not None:
        owner_kw = {"owner_type": "institution",
                    "institution_id": institution_id, "user_id": None}
    else:
        owner_kw = {"owner_type": "user",
                    "institution_id": None, "user_id": user_id}
    # Unit yoksa türe göre varsayılan koy
    if not value_unit:
        value_unit = KIND_DEFAULTS.get(kind_enum, {}).get("unit")
    expires_at = None
    if expires_in_days and expires_in_days > 0:
        expires_at = _now() + timedelta(days=int(expires_in_days))
    offer = Offer(
        kind=kind_enum,
        title=title.strip()[:255],
        value=value,
        value_unit=value_unit,
        duration_months=duration_months,
        new_plan=new_plan,
        admin_note=admin_note,
        public_message=public_message,
        expires_at=expires_at,
        created_by_user_id=by_user_id,
        status=OfferStatus.DRAFT,
        **owner_kw,
    )
    db.add(offer)
    if autocommit:
        db.commit()
        db.refresh(offer)
    return offer


def send_offer(
    db: Session, *, offer_id: int, autocommit: bool = True,
) -> dict:
    """Teklifi DRAFT → SENT yap. Gerçek e-posta gönderimi opsiyonel (stub)."""
    offer = db.get(Offer, offer_id)
    if offer is None:
        return {"ok": False, "error": "not_found"}
    if offer.status != OfferStatus.DRAFT:
        return {"ok": False, "error": "not_draft",
                "current_status": offer.status.value}
    now = _now()
    offer.status = OfferStatus.SENT
    offer.sent_at = now

    # E-posta gönder — owner-aware (institution: institution_admin / contact_email,
    # user: bağımsız öğretmenin kendi email'i)
    sent_via_email = False
    try:
        email: str | None = None
        recipient_name: str | None = None
        if offer.owner_type == "user" and offer.user_id is not None:
            u = db.get(User, offer.user_id)
            if u and u.email:
                email = u.email
                recipient_name = u.full_name or u.email
        else:
            from app.services.dunning import _institution_admin_email
            email, recipient_name = _institution_admin_email(
                db, institution_id=offer.institution_id,
            )
        if email:
            from app.services.email_service import send_email
            sent_via_email = send_email(
                to=email,
                template="offer_invitation",
                ctx={
                    "subject": f"Size özel teklif — {offer.title}",
                    "title": offer.title,
                    "recipient_name": recipient_name,
                    "public_message": offer.public_message or "",
                    "offer_url_path": f"/offers/{offer.token}",
                    "expires_at": offer.expires_at.isoformat() if offer.expires_at else None,
                },
            )
    except Exception:
        logger.exception("offer email send fail offer=%s", offer_id)

    if autocommit:
        db.commit()
    return {
        "ok": True,
        "offer_id": offer.id,
        "token": offer.token,
        "sent_at": now.isoformat(),
        "sent_via_email": sent_via_email,
    }


def cancel_offer(
    db: Session, *, offer_id: int, autocommit: bool = True,
) -> dict:
    """Henüz cevap verilmemiş teklifi iptal et (admin)."""
    offer = db.get(Offer, offer_id)
    if offer is None:
        return {"ok": False, "error": "not_found"}
    if offer.status in (OfferStatus.ACCEPTED, OfferStatus.DECLINED,
                        OfferStatus.CANCELLED):
        return {"ok": False, "error": "already_closed",
                "current_status": offer.status.value}
    offer.status = OfferStatus.CANCELLED
    offer.responded_at = _now()
    if autocommit:
        db.commit()
    return {"ok": True, "offer_id": offer.id}


def update_offer(
    db: Session, *, offer_id: int,
    title: str | None = None,
    public_message: str | None = None,
    admin_note: str | None = None,
    value: float | None = None,
    duration_months: int | None = None,
    new_plan: str | None = None,
    expires_in_days: int | None = None,
    autocommit: bool = True,
) -> dict:
    """Henüz GÖNDERİLMEMİŞ (DRAFT) teklifi düzenle — admin son rötuş.

    Yalnız DRAFT düzenlenebilir (SENT/ACCEPTED vb. değişmez). None geçilen alanlar
    dokunulmaz; boş string → temizler. expires_in_days verilirse expires_at yeniden
    hesaplanır (0/negatif → süresiz)."""
    offer = db.get(Offer, offer_id)
    if offer is None:
        return {"ok": False, "error": "not_found"}
    if offer.status != OfferStatus.DRAFT:
        return {"ok": False, "error": "not_draft", "current_status": offer.status.value}
    if title is not None and title.strip():
        offer.title = title.strip()[:255]
    if public_message is not None:
        offer.public_message = public_message.strip() or None
    if admin_note is not None:
        offer.admin_note = admin_note.strip() or None
    if value is not None:
        offer.value = value
    if duration_months is not None:
        offer.duration_months = duration_months
    if new_plan is not None:
        offer.new_plan = new_plan.strip() or None
    if expires_in_days is not None:
        offer.expires_at = (_now() + timedelta(days=int(expires_in_days))) if expires_in_days > 0 else None
    if autocommit:
        db.commit()
        db.refresh(offer)
    return {"ok": True, "offer_id": offer.id}


def get_offer_by_token(db: Session, *, token: str) -> Offer | None:
    return db.query(Offer).filter(Offer.token == token).first()


def list_offers_for_institution(
    db: Session, *, institution_id: int, limit: int = 50,
) -> list[Offer]:
    return (
        db.query(Offer)
        .filter(Offer.institution_id == institution_id)
        .order_by(desc(Offer.created_at))
        .limit(limit)
        .all()
    )


def list_offers_for_owner(
    db: Session, *,
    institution_id: int | None = None,
    user_id: int | None = None,
    limit: int = 50,
) -> list[Offer]:
    """Owner XOR — institution_id veya user_id verilmeli."""
    q = db.query(Offer)
    if institution_id is not None and user_id is None:
        q = q.filter(Offer.institution_id == institution_id)
    elif user_id is not None and institution_id is None:
        q = q.filter(Offer.user_id == user_id)
    else:
        raise ValueError("list_offers_for_owner: institution_id veya user_id (tam biri)")
    return q.order_by(desc(Offer.created_at)).limit(limit).all()


# ---------------------------- Kabul / Red akışı ----------------------------


def _apply_plan_change_on_accept(
    db: Session, *, offer: Offer, by_user_id: int | None,
) -> int | None:
    """Kabul edilen teklifin gerektirdiği plan değişikliğini uygula.
    Owner-aware: institution veya bağımsız öğretmen (User).

    Returns: PlanChangeHistory.id (kayıt oluşturulduysa) veya None.
    """
    # Owner objesini çek (institution veya user)
    owner_obj: Institution | User | None = None
    if offer.owner_type == "user" and offer.user_id is not None:
        owner_obj = db.get(User, offer.user_id)
    elif offer.owner_type == "institution" and offer.institution_id is not None:
        owner_obj = db.get(Institution, offer.institution_id)
    if owner_obj is None:
        return None

    old_plan = owner_obj.plan
    new_plan_code: str | None = None
    note_extra = ""
    now = _now()

    if offer.kind == OfferKind.PLAN_UPGRADE and offer.new_plan:
        new_plan_code = offer.new_plan
        note_extra = f"Teklif kabul: {old_plan} → {new_plan_code}"
    elif offer.kind == OfferKind.TRIAL_EXTENSION:
        days = int(offer.value or 0)
        if days > 0:
            current_te = _aware(owner_obj.trial_ends_at) or now
            owner_obj.trial_ends_at = current_te + timedelta(days=days)
            note_extra = f"Teklif kabul: trial {days} gün uzatıldı"
    elif offer.kind in (
        OfferKind.DISCOUNT_PERCENT, OfferKind.DISCOUNT_FIXED,
        OfferKind.FREE_FEATURE, OfferKind.ONBOARDING_HOURS,
        OfferKind.CUSTOM,
    ):
        note_extra = f"Teklif kabul ({offer.kind.value}): {offer.title}"

    # PlanChangeHistory — owner_type'a göre PlanOwnerType
    pch_owner_type = (
        PlanOwnerType.USER if offer.owner_type == "user" else PlanOwnerType.INSTITUTION
    )
    pch_owner_id = offer.user_id if offer.owner_type == "user" else offer.institution_id
    pch = PlanChangeHistory(
        owner_type=pch_owner_type,
        owner_id=pch_owner_id,
        from_plan=old_plan,
        to_plan=new_plan_code or old_plan,
        reason=PlanChangeReason.ADMIN_OVERRIDE,
        actor_user_id=by_user_id,
        note=f"[Offer #{offer.id}] {note_extra}",
    )
    db.add(pch)
    db.flush()

    if new_plan_code:
        owner_obj.plan = new_plan_code

    return pch.id


def accept_offer(
    db: Session, *, token: str, by_user_id: int | None = None,
    autocommit: bool = True,
) -> dict:
    """Public link sahibi (veya admin) teklifi kabul eder.

    by_user_id None ise public/anonim kabul (login yok).
    """
    offer = get_offer_by_token(db, token=token)
    if offer is None:
        return {"ok": False, "error": "not_found"}
    if offer.status != OfferStatus.SENT:
        return {"ok": False, "error": "not_open",
                "current_status": offer.status.value}
    # Süre dolmuş mu?
    if offer.expires_at:
        if _aware(offer.expires_at) < _now():
            offer.status = OfferStatus.EXPIRED
            if autocommit:
                db.commit()
            return {"ok": False, "error": "expired"}

    now = _now()
    offer.status = OfferStatus.ACCEPTED
    offer.responded_at = now

    # Plan değişikliği uygula
    try:
        pch_id = _apply_plan_change_on_accept(
            db, offer=offer, by_user_id=by_user_id,
        )
        offer.plan_change_history_id = pch_id
    except Exception:
        logger.exception("offer accept plan-change fail offer=%s", offer.id)
        if autocommit:
            db.rollback()
        return {"ok": False, "error": "plan_change_failed"}

    if autocommit:
        db.commit()
    return {
        "ok": True,
        "offer_id": offer.id,
        "institution_id": offer.institution_id,
        "plan_change_history_id": offer.plan_change_history_id,
        "responded_at": now.isoformat(),
    }


def decline_offer(
    db: Session, *, token: str, reason: str | None = None,
    autocommit: bool = True,
) -> dict:
    """Public link sahibi teklifi reddeder."""
    offer = get_offer_by_token(db, token=token)
    if offer is None:
        return {"ok": False, "error": "not_found"}
    if offer.status != OfferStatus.SENT:
        return {"ok": False, "error": "not_open",
                "current_status": offer.status.value}
    if offer.expires_at and _aware(offer.expires_at) < _now():
        offer.status = OfferStatus.EXPIRED
        if autocommit:
            db.commit()
        return {"ok": False, "error": "expired"}

    offer.status = OfferStatus.DECLINED
    offer.responded_at = _now()
    if reason:
        offer.decline_reason = reason.strip()[:500]
    if autocommit:
        db.commit()
    return {"ok": True, "offer_id": offer.id}


def expire_old_offers(
    db: Session, *, autocommit: bool = True,
) -> dict:
    """Cron: süresi dolmuş SENT teklifleri EXPIRED'a çek."""
    now = _now()
    rows = (
        db.query(Offer)
        .filter(
            Offer.status == OfferStatus.SENT,
            Offer.expires_at.isnot(None),
            Offer.expires_at < now,
        )
        .all()
    )
    count = 0
    for o in rows:
        o.status = OfferStatus.EXPIRED
        count += 1
    if autocommit:
        db.commit()
    return {"expired_count": count}


# ---------------------------- Offer açıklamasını UI için üret ----------------------------


def describe_offer(offer: Offer) -> dict:
    """Kuruma gösterilecek teklif özeti — value+unit+duration birleşik metin."""
    parts: list[str] = []
    if offer.kind == OfferKind.DISCOUNT_PERCENT and offer.value:
        s = f"%{int(offer.value)} indirim"
        if offer.duration_months:
            s += f" ({offer.duration_months} ay boyunca)"
        parts.append(s)
    elif offer.kind == OfferKind.DISCOUNT_FIXED and offer.value:
        s = f"{int(offer.value):,} ₺ indirim"
        if offer.duration_months:
            s += f" ({offer.duration_months} ay boyunca)"
        parts.append(s)
    elif offer.kind == OfferKind.TRIAL_EXTENSION and offer.value:
        parts.append(f"{int(offer.value)} gün ek deneme süresi")
    elif offer.kind == OfferKind.PLAN_UPGRADE and offer.new_plan:
        s = f"{offer.new_plan} paketine yükseltme"
        if offer.duration_months:
            s += f" ({offer.duration_months} ay ücretsiz)"
        parts.append(s)
    elif offer.kind == OfferKind.FREE_FEATURE:
        s = "Ücretsiz ek özellik"
        if offer.duration_months:
            s += f" ({offer.duration_months} ay)"
        parts.append(s)
    elif offer.kind == OfferKind.ONBOARDING_HOURS and offer.value:
        parts.append(f"{int(offer.value)} saat ücretsiz onboarding eğitimi")
    elif offer.kind == OfferKind.CUSTOM:
        parts.append(offer.title)
    return {
        "summary": " · ".join(parts) if parts else offer.title,
        "value": offer.value,
        "value_unit": offer.value_unit,
        "duration_months": offer.duration_months,
        "new_plan": offer.new_plan,
    }


__all__ = [
    "KIND_DEFAULTS",
    "accept_offer",
    "cancel_offer",
    "create_offer",
    "decline_offer",
    "describe_offer",
    "expire_old_offers",
    "get_offer_by_token",
    "list_offers_for_institution",
    "send_offer",
]
