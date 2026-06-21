"""API v2 — Süper Admin: Kampanya / Genel Link yönetimi (Yol A).

Kişiye özel olmayan, gruba paylaşılabilen markalı landing linki oluştur/listele/
durum değiştir. Public taraf: campaign_public.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db
from app.models import CampaignLink, User
from app.models.campaign_link import CAMPAIGN_STATUS_LABELS_TR
from app.routes.api_v2.admin import _require_super_admin
from app.services import campaign_link_service as cls
from app.services import plans

router = APIRouter(prefix="/admin/campaign-links", tags=["v2-admin-campaign-links"])


def _public_url(token: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}/kampanya/{token}"


class CampaignLinkCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    plan_code: str = Field(..., min_length=1, max_length=50)
    cycle: str = Field("monthly")
    amount: int | None = Field(None, ge=0)
    title: str | None = Field(None, max_length=200)
    message: str | None = Field(None, max_length=2000)
    audience: str | None = None  # coach | institution (boşsa plandan türer)
    expires_in_days: int | None = Field(None, ge=1, le=365)


class CampaignLinkStatusBody(BaseModel):
    status: str = Field(..., pattern="^(active|paused|archived)$")


class PlanOption(BaseModel):
    code: str
    label: str
    audience: str
    monthly: int | None = None
    annual: int | None = None


class CampaignLinkItem(BaseModel):
    id: int
    token: str
    name: str
    audience: str
    plan_code: str
    plan_label: str
    cycle: str
    amount: int | None
    title: str | None
    status: str
    status_label: str
    view_count: int
    lead_count: int
    public_url: str
    expires_at: datetime | None
    created_at: datetime


class CampaignLinkListResponse(BaseModel):
    items: list[CampaignLinkItem]
    plan_options: list[PlanOption]


def _item(link: CampaignLink) -> CampaignLinkItem:
    pi = plans.get_plan_info(link.plan_code)
    return CampaignLinkItem(
        id=link.id, token=link.token, name=link.name, audience=link.audience,
        plan_code=link.plan_code, plan_label=(pi.label if pi else link.plan_code),
        cycle=link.cycle, amount=link.amount, title=link.title,
        status=link.status,
        status_label=CAMPAIGN_STATUS_LABELS_TR.get(link.status, link.status),
        view_count=link.view_count or 0, lead_count=link.lead_count or 0,
        public_url=_public_url(link.token),
        expires_at=link.expires_at, created_at=link.created_at,
    )


def _plan_options() -> list[PlanOption]:
    out: list[PlanOption] = []
    for code, pi in plans.PLAN_CATALOG.items():
        if not plans.is_paid_plan(code):
            continue
        out.append(PlanOption(
            code=code, label=pi.label, audience=pi.audience,
            monthly=pi.price_monthly_try or None,
            annual=pi.price_yearly_try or None,
        ))
    return out


@router.get("", response_model=CampaignLinkListResponse)
def list_campaign_links(
    include_archived: bool = False,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
) -> CampaignLinkListResponse:
    links = cls.list_links(db, include_archived=include_archived)
    return CampaignLinkListResponse(
        items=[_item(x) for x in links],
        plan_options=_plan_options(),
    )


@router.post("", response_model=CampaignLinkItem)
def create_campaign_link(
    body: CampaignLinkCreate,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
) -> CampaignLinkItem:
    try:
        link = cls.create_link(
            db, admin_id=user.id, name=body.name, plan_code=body.plan_code,
            cycle=body.cycle, amount=body.amount, title=body.title,
            message=body.message, audience=body.audience,
            expires_in_days=body.expires_in_days,
        )
    except cls.CampaignLinkError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation", "code": exc.code, "message": exc.message},
        ) from exc
    return _item(link)


@router.post("/{link_id}/status", response_model=CampaignLinkItem)
def set_campaign_link_status(
    link_id: int, body: CampaignLinkStatusBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
) -> CampaignLinkItem:
    link = cls.get_by_id(db, link_id)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "campaign_not_found",
                    "message": "Kampanya bulunamadı."},
        )
    cls.set_status(db, link, body.status)
    return _item(link)
