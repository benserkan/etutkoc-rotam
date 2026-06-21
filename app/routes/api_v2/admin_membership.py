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
from app.models import MembershipOffer, User, UserRole
from app.routes.api_v2.admin import _require_super_admin
from app.services import membership_offer_service as mos
from app.services import plans

_BULK_MAX = 200

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
    wa_sent: bool = False           # K2 — Cloud API ile branded gönderildi mi
    wa_sent_at: str | None = None


class MembershipOfferListResponse(BaseModel):
    items: list[MembershipOfferListItem]
    plan_options: list[PlanOption]
    whatsapp_enabled: bool = False  # K2 — Cloud API anahtarları dolu mu (buton göster)
    offer_template: str = ""        # onaylı şablon adı (bilgi)


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
        wa_sent=o.wa_sent_at is not None,
        wa_sent_at=o.wa_sent_at.isoformat() if o.wa_sent_at else None,
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
    from app.services import whatsapp as _wa
    return MembershipOfferListResponse(
        items=[_list_item(db, o) for o in offers],
        plan_options=_plan_options(),
        whatsapp_enabled=_wa.is_enabled(),
        offer_template=settings.whatsapp_offer_template,
    )


class SendWhatsAppResult(BaseModel):
    ok: bool
    wa_sent_at: str | None = None
    message: str


@router.post("/{offer_id}/send-whatsapp", response_model=SendWhatsAppResult)
def send_membership_offer_whatsapp(
    offer_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """K2 — onaylı branded şablonu (uyelik_teklifi) Cloud API ile hedefe gönder."""
    from app.services import whatsapp as _wa
    if not _wa.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "whatsapp", "code": "whatsapp_disabled",
                    "message": "WhatsApp Cloud API yapılandırılmamış (anahtarlar eksik)."},
        )
    offer = db.get(MembershipOffer, offer_id)
    if offer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "offer_not_found", "message": "Teklif bulunamadı."},
        )
    try:
        mos.send_via_whatsapp(db, offer)
    except mos.MembershipOfferError as e:
        code_status = {
            "no_phone": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "not_active": status.HTTP_409_CONFLICT,
            "wa_send_failed": status.HTTP_502_BAD_GATEWAY,
        }.get(e.code, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(
            status_code=code_status,
            detail={"error": "whatsapp", "code": e.code, "message": e.message},
        )
    return SendWhatsAppResult(
        ok=True,
        wa_sent_at=offer.wa_sent_at.isoformat() if offer.wa_sent_at else None,
        message="Branded üyelik teklifi WhatsApp'tan gönderildi.",
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


# ============================================================================
# Paket 3 — Toplu / gruplu üyelik teklifi
# ============================================================================

# Bağımsız koç hedef grupları (üyelik teklifi kitlesi). plan koduna göre.
_MEMBERSHIP_GROUPS = [
    ("free", "Ücretsiz koçlar", ["solo_free"]),
    ("trial", "Denemedeki koçlar", ["solo_trial"]),
    ("paid", "Ücretli koçlar (yenileme)", ["solo_pro", "solo_elite", "solo_unlimited"]),
]


class AudienceMember(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None = None
    plan: str | None = None


class AudienceGroup(BaseModel):
    key: str
    label: str
    count: int
    members: list[AudienceMember]


class AudienceResponse(BaseModel):
    groups: list[AudienceGroup]


def _solo_base(db: Session):
    return (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
    )


@router.get("/audience", response_model=AudienceResponse)
def membership_audience(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Toplu teklif için bağımsız koç hedef grupları (üye listeleriyle)."""
    groups: list[AudienceGroup] = []
    for key, label, codes in _MEMBERSHIP_GROUPS:
        rows = (
            _solo_base(db)
            .filter(User.plan.in_(codes))
            .order_by(User.full_name.asc())
            .limit(_BULK_MAX)
            .all()
        )
        groups.append(AudienceGroup(
            key=key, label=label, count=len(rows),
            members=[
                AudienceMember(id=u.id, full_name=u.full_name, email=u.email,
                               phone=u.phone, plan=u.plan)
                for u in rows
            ],
        ))
    return AudienceResponse(groups=groups)


class BulkMembershipOfferBody(BaseModel):
    target_user_ids: list[int]
    offer_type: str = "new"
    plan_code: str
    cycle: str = "monthly"
    amount: int | None = None
    title: str | None = None
    message: str | None = None
    expires_in_days: int | None = 30


class BulkOfferResultItem(BaseModel):
    target_user_id: int
    full_name: str | None = None
    phone: str | None = None
    token: str
    public_url: str


class BulkMembershipOfferResult(BaseModel):
    created: int
    skipped: int
    items: list[BulkOfferResultItem]


@router.post("/bulk", response_model=BulkMembershipOfferResult)
def create_membership_offers_bulk(
    body: BulkMembershipOfferBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Seçili koçların her birine birer üyelik teklifi (kişisel token+link) üretir."""
    ids = list(dict.fromkeys(body.target_user_ids))[:_BULK_MAX]  # tekilleştir + cap
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "no_targets", "message": "Hedef seçilmedi."},
        )
    if plans.get_plan_info(body.plan_code) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "membership", "code": "invalid_plan", "message": "Geçersiz plan."},
        )
    items: list[BulkOfferResultItem] = []
    skipped = 0
    for uid in ids:
        u = db.get(User, uid)
        if u is None:
            skipped += 1
            continue
        try:
            offer = mos.create_offer(
                db, admin=user, target_user_id=uid, offer_type=body.offer_type,
                plan_code=body.plan_code, cycle=body.cycle, amount=body.amount,
                title=body.title, message=body.message,
                expires_in_days=body.expires_in_days,
            )
        except mos.MembershipOfferError:
            skipped += 1
            continue
        items.append(BulkOfferResultItem(
            target_user_id=uid, full_name=u.full_name,
            phone=(u.phone if u.phone else None),
            token=offer.token, public_url=_public_url(offer.token),
        ))
    return BulkMembershipOfferResult(created=len(items), skipped=skipped, items=items)
