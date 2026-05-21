"""API v2 — Public Offer (Teklif) endpoint'leri (Dalga 7 P5).

Token bazlı, login gerektirmez. Kurum/öğretmen e-postadaki link ile teklifi
görür, kabul/ret kararı verir. Jinja parite: app/routes/offers_public.py.
Servis: app/services/offers.py (DEĞİŞMEDİ — aynen çağrılır).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db


router = APIRouter(prefix="/offers", tags=["v2-offers-public"])


class OfferPublicResponse(BaseModel):
    valid: bool
    status: str                       # sent | accepted | declined | expired | not_found
    kind: str | None = None
    kind_label: str | None = None
    title: str | None = None
    summary: str | None = None        # describe_offer özeti
    public_message: str | None = None
    owner_name: str | None = None
    expires_at: str | None = None


class OfferActionResult(BaseModel):
    ok: bool
    status: str
    message: str


def _owner_name(db: Session, offer) -> str | None:
    from app.models import Institution, User
    if offer.owner_type == "user" and offer.user_id:
        u = db.get(User, offer.user_id)
        return (u.full_name or u.email) if u else None
    if offer.institution_id:
        inst = db.get(Institution, offer.institution_id)
        return inst.name if inst else None
    return None


@router.get("/{token}", response_model=OfferPublicResponse)
def offer_public_view(token: str, db: Session = Depends(get_db)):
    """Teklif görüntüleme (public). Süresi geçmişse otomatik EXPIRED'a çeker."""
    from app.models import OFFER_KIND_LABELS_TR, OfferStatus
    from app.services.offers import _aware, _now, describe_offer, get_offer_by_token

    offer = get_offer_by_token(db, token=token)
    if offer is None:
        return OfferPublicResponse(valid=False, status="not_found")

    if (offer.status == OfferStatus.SENT and offer.expires_at
            and _aware(offer.expires_at) < _now()):
        offer.status = OfferStatus.EXPIRED
        db.commit()

    desc = describe_offer(offer)
    return OfferPublicResponse(
        valid=offer.status == OfferStatus.SENT,
        status=offer.status.value,
        kind=offer.kind.value,
        kind_label=OFFER_KIND_LABELS_TR.get(offer.kind, offer.kind.value),
        title=offer.title,
        summary=desc.get("summary"),
        public_message=offer.public_message,
        owner_name=_owner_name(db, offer),
        expires_at=offer.expires_at.isoformat() if offer.expires_at else None,
    )


_ERROR_MESSAGES = {
    "not_found": "Teklif bulunamadı.",
    "not_open": "Bu teklif artık yanıtlanamaz (zaten yanıtlanmış veya iptal edilmiş).",
    "expired": "Bu teklifin süresi dolmuş.",
    "plan_change_failed": "Teklif uygulanırken bir hata oluştu. Lütfen destek ile iletişime geçin.",
}


@router.post("/{token}/accept", response_model=OfferActionResult)
def offer_public_accept(token: str, db: Session = Depends(get_db)):
    from app.services.offers import accept_offer

    result = accept_offer(db, token=token, by_user_id=None)
    if not result.get("ok"):
        err = result.get("error", "not_open")
        return OfferActionResult(ok=False, status=err, message=_ERROR_MESSAGES.get(err, "İşlem yapılamadı."))
    return OfferActionResult(ok=True, status="accepted", message="Teklifi kabul ettiniz. Teşekkürler!")


class OfferDeclineBody(BaseModel):
    reason: str = ""


@router.post("/{token}/decline", response_model=OfferActionResult)
def offer_public_decline(token: str, body: OfferDeclineBody, db: Session = Depends(get_db)):
    from app.services.offers import decline_offer

    result = decline_offer(db, token=token, reason=body.reason or None)
    if not result.get("ok"):
        err = result.get("error", "not_open")
        return OfferActionResult(ok=False, status=err, message=_ERROR_MESSAGES.get(err, "İşlem yapılamadı."))
    return OfferActionResult(ok=True, status="declined", message="Teklifi reddettiniz.")
