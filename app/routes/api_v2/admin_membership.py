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
from app.models import MembershipOffer, User
from app.routes.api_v2.admin import _require_super_admin
from app.services import membership_offer_service as mos
from app.services import plans

router = APIRouter(prefix="/admin/membership-offers", tags=["v2-admin-membership"])


def _public_url(token: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}/membership/{token}"


_COMPLETION_LABELS = {
    None: "—",
    "requested": "Üyelik talebi bıraktı",
    "havale_claimed": "Havale/EFT ödedim dedi",
    "activated": "Aktive edildi",
}
_STATUS_LABELS = {
    "active": "Bekliyor",
    "accepted": "Yanıtladı",
    "cancelled": "İptal",
    "expired": "Süresi doldu",
}


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


class PlanOption(BaseModel):
    code: str
    label: str
    audience: str
    monthly: int
    annual: int


class MembershipOfferListItem(BaseModel):
    id: int
    token: str
    public_url: str
    target_user_id: int | None = None
    target_name: str | None = None
    target_phone: str | None = None
    offer_type: str
    plan_code: str
    plan_label: str
    cycle: str
    amount: int | None = None
    status: str
    status_label: str
    completion: str | None = None
    completion_label: str
    title: str | None = None
    message: str | None = None
    created_at: str
    viewed: bool = False


class MembershipOfferListResponse(BaseModel):
    items: list[MembershipOfferListItem]
    plan_options: list[PlanOption]


def _list_item(db: Session, o: MembershipOffer) -> MembershipOfferListItem:
    pi = plans.get_plan_info(o.plan_code)
    target = o.target_user
    return MembershipOfferListItem(
        id=o.id,
        token=o.token,
        public_url=_public_url(o.token),
        target_user_id=o.target_user_id,
        target_name=(target.full_name if target else None),
        target_phone=(target.phone if (target and target.phone) else None),
        offer_type=o.offer_type,
        plan_code=o.plan_code,
        plan_label=(pi.label if pi else o.plan_code),
        cycle=o.cycle,
        amount=o.amount,
        status=o.status,
        status_label=_STATUS_LABELS.get(o.status, o.status),
        completion=o.completion,
        completion_label=_COMPLETION_LABELS.get(o.completion, o.completion or "—"),
        title=o.title,
        message=o.message,
        created_at=o.created_at.isoformat() if o.created_at else "",
        viewed=o.viewed_at is not None,
    )


def _plan_options() -> list[PlanOption]:
    out: list[PlanOption] = []
    for code, pi in plans.PLAN_CATALOG.items():
        if not plans.is_paid_plan(code):
            continue  # trial/free satılmaz
        out.append(PlanOption(
            code=code, label=pi.label, audience=pi.audience,
            monthly=pi.price_monthly_try, annual=pi.price_yearly_try,
        ))
    out.sort(key=lambda p: (p.audience, p.monthly if p.monthly > 0 else 10**9))
    return out


@router.get("", response_model=MembershipOfferListResponse)
def list_membership_offers(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    offers = (
        db.query(MembershipOffer)
        .order_by(MembershipOffer.created_at.desc())
        .limit(100)
        .all()
    )
    return MembershipOfferListResponse(
        items=[_list_item(db, o) for o in offers],
        plan_options=_plan_options(),
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
