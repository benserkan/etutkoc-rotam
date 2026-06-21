"""API v2 — Public WhatsApp Üyelik Teklifi (Paket 1).

Token bazlı, login GEREKTİRMEZ. Kullanıcı WhatsApp'tan gelen linke tıklar →
markalı sayfa bu uçları çağırır: teklifi görüntüle + "Üye ol/Yenile" talebi +
"Havale/EFT ile ödedim" bildirimi. Servis: membership_offer_service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db
from app.services import membership_offer_service as mos

router = APIRouter(prefix="/membership", tags=["v2-membership-public"])


class HavaleInfo(BaseModel):
    enabled: bool
    iban: str = ""
    name: str = ""
    note: str = ""


class MembershipPublicResponse(BaseModel):
    valid: bool
    status: str                       # active | accepted | cancelled | expired | not_found
    completion: str | None = None
    offer_type: str | None = None
    offer_type_label: str | None = None
    title: str | None = None
    message: str | None = None
    target_name: str | None = None
    plan_code: str | None = None
    plan_label: str | None = None
    plan_short: str | None = None
    plan_features: list[str] = []
    cycle: str | None = None
    cycle_label: str | None = None
    amount: int | None = None
    list_price: int | None = None
    savings: int | None = None
    discount_pct: int | None = None
    havale: HavaleInfo | None = None


class MembershipActionBody(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None


class MembershipActionResult(BaseModel):
    ok: bool
    status: str
    completion: str | None = None
    message: str


@router.get("/{token}", response_model=MembershipPublicResponse)
def membership_offer_public(token: str, db: Session = Depends(get_db)):
    offer = mos.get_by_token(db, token)
    if offer is None:
        return MembershipPublicResponse(valid=False, status="not_found")
    return MembershipPublicResponse(**mos.public_view(db, offer))


@router.post("/{token}/request", response_model=MembershipActionResult)
def membership_offer_request(
    token: str, body: MembershipActionBody | None = None, db: Session = Depends(get_db)
):
    offer = mos.get_by_token(db, token)
    if offer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "offer_not_found", "message": "Teklif bulunamadı."},
        )
    b = body or MembershipActionBody()
    try:
        mos.record_request(db, offer, name=b.name, email=b.email, phone=b.phone)
    except mos.MembershipOfferError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "membership", "code": e.code, "message": e.message},
        )
    return MembershipActionResult(
        ok=True, status="accepted", completion="requested",
        message="Talebin alındı. En kısa sürede seninle iletişime geçilip üyeliğin aktive edilecek.",
    )


@router.post("/{token}/havale-claim", response_model=MembershipActionResult)
def membership_offer_havale(
    token: str, body: MembershipActionBody | None = None, db: Session = Depends(get_db)
):
    offer = mos.get_by_token(db, token)
    if offer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "offer_not_found", "message": "Teklif bulunamadı."},
        )
    if not mos.get_havale_info()["enabled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "membership", "code": "havale_disabled",
                    "message": "Havale/EFT seçeneği şu an kapalı."},
        )
    b = body or MembershipActionBody()
    try:
        mos.record_havale_claim(db, offer, name=b.name, email=b.email, phone=b.phone)
    except mos.MembershipOfferError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "membership", "code": e.code, "message": e.message},
        )
    return MembershipActionResult(
        ok=True, status="accepted", completion="havale_claimed",
        message="Bildirimin alındı. Ödemen kontrol edilip üyeliğin aktive edilecek.",
    )
