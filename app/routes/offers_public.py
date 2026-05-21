"""Sprint D.1 — Public Offer (Teklif) sayfaları.

Token bazlı, login gerektirmez. Kurum yetkilisi e-postadaki link ile
buraya gelir, teklifi görür ve kabul/ret kararı verir.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.templating import templates


router = APIRouter()


@router.get("/offers/{token}")
def offer_public_view(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Kuruma açık teklif sayfası — login gerektirmez."""
    from app.models import OFFER_KIND_ICONS, OFFER_KIND_LABELS_TR, Institution, OfferStatus
    from app.services.offers import describe_offer, get_offer_by_token

    offer = get_offer_by_token(db, token=token)
    if offer is None:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
    inst = db.get(Institution, offer.institution_id)
    desc = describe_offer(offer)
    # Süre kontrolü (otomatik EXPIRED'a çek)
    from app.services.offers import _aware, _now
    if (offer.status == OfferStatus.SENT
            and offer.expires_at
            and _aware(offer.expires_at) < _now()):
        offer.status = OfferStatus.EXPIRED
        db.commit()
    return templates.TemplateResponse(
        "offers_public/view.html",
        {
            "request": request,
            "offer": offer,
            "institution": inst,
            "description": desc,
            "kind_label": OFFER_KIND_LABELS_TR.get(offer.kind, offer.kind.value),
            "kind_icon": OFFER_KIND_ICONS.get(offer.kind, "🎁"),
        },
    )


@router.post("/offers/{token}/accept")
def offer_public_accept(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.services.offers import accept_offer
    result = accept_offer(db, token=token, by_user_id=None)
    if not result.get("ok"):
        return RedirectResponse(
            url=f"/offers/{token}?err=" + result.get("error", "fail"),
            status_code=303,
        )
    return RedirectResponse(
        url=f"/offers/{token}?accepted=1",
        status_code=303,
    )


@router.post("/offers/{token}/decline")
def offer_public_decline(
    token: str,
    request: Request,
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.services.offers import decline_offer
    result = decline_offer(db, token=token, reason=reason or None)
    if not result.get("ok"):
        return RedirectResponse(
            url=f"/offers/{token}?err=" + result.get("error", "fail"),
            status_code=303,
        )
    return RedirectResponse(
        url=f"/offers/{token}?declined=1",
        status_code=303,
    )
