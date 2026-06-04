"""API v2 — Süper Admin: WhatsApp Üyelik Teklifi yönetimi (Paket 1).

Teklif oluşturma (token + public link üretir) + havale/EFT bilgisi ayarı.
Teklif WhatsApp ile gönderilir (tekli/toplu Click-to-WhatsApp — P2/P3).
Public taraf: membership_public.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db
from app.models import User
from app.routes.api_v2.admin import _require_super_admin
from app.services import membership_offer_service as mos

router = APIRouter(prefix="/admin/membership-offers", tags=["v2-admin-membership"])


def _public_url(token: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}/membership/{token}"


class CreateMembershipOfferBody(BaseModel):
    target_user_id: int | None = None
    offer_type: str = "new"            # new | renewal
    plan_code: str
    cycle: str = "monthly"             # monthly | annual
    amount: int | None = None          # özel fiyat (TL); None = plan varsayılanı
    title: str | None = None
    message: str | None = None
    expires_in_days: int | None = 30


class MembershipOfferCreated(BaseModel):
    id: int
    token: str
    public_url: str
    plan_code: str
    offer_type: str
    cycle: str
    amount: int | None = None
    target_user_id: int | None = None
    status: str


class HavaleInfoBody(BaseModel):
    iban: str = ""
    name: str = ""
    note: str = ""


class HavaleInfoResponse(BaseModel):
    enabled: bool
    iban: str = ""
    name: str = ""
    note: str = ""


@router.post("", response_model=MembershipOfferCreated)
def create_membership_offer(
    body: CreateMembershipOfferBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        offer = mos.create_offer(
            db,
            admin=user,
            target_user_id=body.target_user_id,
            offer_type=body.offer_type,
            plan_code=body.plan_code,
            cycle=body.cycle,
            amount=body.amount,
            title=body.title,
            message=body.message,
            expires_in_days=body.expires_in_days,
        )
    except mos.MembershipOfferError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "membership", "code": e.code, "message": e.message},
        )
    return MembershipOfferCreated(
        id=offer.id,
        token=offer.token,
        public_url=_public_url(offer.token),
        plan_code=offer.plan_code,
        offer_type=offer.offer_type,
        cycle=offer.cycle,
        amount=offer.amount,
        target_user_id=offer.target_user_id,
        status=offer.status,
    )


@router.get("/havale", response_model=HavaleInfoResponse)
def get_membership_havale(
    user: User = Depends(_require_super_admin),
):
    return HavaleInfoResponse(**mos.get_havale_info())


@router.post("/havale", response_model=HavaleInfoResponse)
def set_membership_havale(
    body: HavaleInfoBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    info = mos.set_havale_info(
        db, iban=body.iban, name=body.name, note=body.note, actor_user_id=user.id
    )
    return HavaleInfoResponse(**info)
