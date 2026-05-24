"""API v2 — Public Landing (anasayfa vitrin) endpoint'leri.

Login gerektirmez. Next.js anasayfası (app/page.tsx) feature_catalog
kartlarını + A/B variant'ını buradan çeker; kart davranış telemetrisini
(impression/view/demo_click) buraya gönderir.

Servisler DEĞİŞMEDİ — aynen çağrılır:
  - feature_catalog.get_for_landing_with_variant (A/B + strateji sıralaması)
  - telemetry.ensure_session_id (90g anon session cookie) + record_event (KVKK hash)

Jinja parite: app/main.py index() (landing dalı) + /api/telemetry/event.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db


router = APIRouter(prefix="/landing", tags=["v2-landing-public"])


class LandingCard(BaseModel):
    slug: str
    title: str
    tagline: str
    category_icon: str
    category_label: str
    accent_color: str
    benefits: list[str]
    demo_slug: str | None = None
    demo_duration_label: str | None = None
    mockup_type: str | None = None


class LandingResponse(BaseModel):
    cards: list[LandingCard]
    variant_slug: str | None = None


class LandingTelemetryIn(BaseModel):
    slug: str = Field(..., min_length=1, max_length=80)
    event: str = Field(..., min_length=1, max_length=20)
    variant: str | None = Field(default=None, max_length=40)


def _serialize_card(card) -> LandingCard:
    return LandingCard(
        slug=card.slug,
        title=card.title,
        tagline=card.tagline,
        category_icon=card.category_icon,
        category_label=card.category_label,
        accent_color=card.accent_color or "#3b82f6",
        benefits=list(card.benefits or []),
        demo_slug=card.demo_slug,
        demo_duration_label=card.demo_duration_label,
        mockup_type=card.mockup_type,
    )


@router.get("", response_model=LandingResponse)
def landing_cards(
    request: Request,
    response: Response,
    limit: int = Query(5, ge=1, le=12),
    audience: str | None = Query(None, max_length=40),
    db: Session = Depends(get_db),
):
    """Anasayfa feature kartları + A/B variant_slug.

    Anon session cookie (ensure_session_id) yönetilir — variant ataması ve
    telemetri agregasyonu bu session'a bağlanır (Jinja index() ile aynı).

    audience: "teacher" (koç vitrini, varsayılan akış) | "institution_admin"
      (kurum bandı). Boş → tüm hedef kitleler.
    """
    from app.services import feature_catalog as fc
    from app.services import telemetry as tel

    sid = tel.ensure_session_id(request, response)
    cards, variant_slug = fc.get_for_landing_with_variant(
        db, limit=limit, viewer=None, session_id=sid, audience=audience,
    )
    return LandingResponse(
        cards=[_serialize_card(c) for c in cards],
        variant_slug=variant_slug,
    )


@router.post("/telemetry", status_code=204)
def landing_telemetry(
    payload: LandingTelemetryIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Anasayfa kart davranışı (impression/view/demo_click).

    KVKK: telemetry.record_event içinde IP/UA SHA256 hash'lenir; düz değer
    yazılmaz. Throttle: aynı (session, slug, event) son 10sn'de → no-op.
    Yanıt 204 (sendBeacon için ideal).
    """
    from app.services import telemetry as tel

    sid = tel.ensure_session_id(request, response)
    tel.record_event(
        db,
        slug=payload.slug,
        event_type=payload.event,
        session_id=sid,
        request=request,
        viewer=None,
        variant_slug=payload.variant,
    )
    return Response(status_code=204, headers=response.headers)
