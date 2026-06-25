"""API v2 — Public Kampanya / Genel Link (Yol A).

Token bazlı, login GEREKTİRMEZ. Admin linki WhatsApp grubuna paylaşır → tıklayan
markalı sayfayı görür (bu uçlar) → ad+telefon bırakır → lead (prospect) + contact
request → admin İletişim Talepleri'nde aktive eder. Servis: campaign_link_service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db
from app.services import campaign_link_service as cls

router = APIRouter(prefix="/campaign", tags=["v2-campaign-public"])


class CampaignPublicView(BaseModel):
    valid: bool
    status: str
    audience: str | None = None
    title: str | None = None
    message: str | None = None
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


class CampaignLeadBody(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    phone: str = Field(..., min_length=5, max_length=40)
    email: str | None = Field(None, max_length=255)
    note: str | None = Field(None, max_length=300)


class CampaignLeadResult(BaseModel):
    ok: bool = True
    message: str


@router.get("/{token}", response_model=CampaignPublicView)
def campaign_public(token: str, db: Session = Depends(get_db)) -> CampaignPublicView:
    link = cls.get_by_token(db, token)
    if link is None:
        return CampaignPublicView(valid=False, status="not_found")
    return CampaignPublicView(**cls.public_view(db, link))


@router.post("/{token}/lead", response_model=CampaignLeadResult)
def campaign_lead(
    token: str, body: CampaignLeadBody, db: Session = Depends(get_db),
) -> CampaignLeadResult:
    link = cls.get_by_token(db, token)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "campaign_not_found",
                    "message": "Kampanya bulunamadı."},
        )
    try:
        cls.record_lead(db, link, name=body.name, phone=body.phone,
                        email=body.email, note=body.note)
    except cls.CampaignLinkError as exc:
        code_status = {
            "not_active": status.HTTP_409_CONFLICT,
            "invalid_phone": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "invalid_name": status.HTTP_422_UNPROCESSABLE_ENTITY,
        }.get(exc.code, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(
            status_code=code_status,
            detail={"error": "validation", "code": exc.code, "message": exc.message},
        ) from exc
    return CampaignLeadResult(
        ok=True,
        message="Talebin alındı. Ekibimiz en kısa sürede seninle iletişime geçecek.",
    )
