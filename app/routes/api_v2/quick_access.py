"""QA-1 — Hızlı erişim kartları API'si (davranıştan öğrenen panel kartları).

Endpoint'ler (tüm authenticated roller — veri kullanıcının KENDİ gezinti özeti):
  - POST /api/v2/me/panel-visits        — batch ziyaret kaydı (tracker hook)
  - GET  /api/v2/me/quick-cards         — kartlar (sabitlenen + kalıcı + önerilen)
  - POST /api/v2/me/quick-cards/click   — kart tıkı (3'te otomatik KALICI)
  - POST /api/v2/me/quick-cards/pin     — elle sabitle / sabitlemeyi kaldır
  - POST /api/v2/me/quick-cards/dismiss — kartı kaldır (90 gün önerilmez)

KVKK: ham URL saklanmaz (rota kataloğu anahtarı); kimse başkasının verisini
göremez (tüm sorgular user_id ile sınırlı). Süper admin dahil — bu bir analiz
panosu değil, kişisel kolaylık.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.quick_access import (
    PanelVisitsBody,
    PanelVisitsResult,
    QuickCardActionResult,
    QuickCardModel,
    QuickCardPinBody,
    QuickCardRefBody,
    QuickCardsResponse,
)
from app.services import panel_behavior

router = APIRouter(prefix="/me", tags=["api-v2-quick-access"])

_INVALIDATE = ["me:quick-cards"]


@router.post("/panel-visits", response_model=PanelVisitsResult)
def post_panel_visits(
    body: PanelVisitsBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_v2),
) -> PanelVisitsResult:
    accepted = panel_behavior.record_visits(
        db, user, [e.model_dump() for e in body.events], source="web"
    )
    if accepted:
        db.commit()
    return PanelVisitsResult(accepted=accepted)


@router.get("/quick-cards", response_model=QuickCardsResponse)
def get_quick_cards(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_v2),
) -> QuickCardsResponse:
    cards = panel_behavior.quick_cards(db, user)
    return QuickCardsResponse(cards=[QuickCardModel(**c) for c in cards])


def _stat_or_404(stat):
    if stat is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "code": "card_not_found",
                "message": "Kart bulunamadı.",
            },
        )
    return stat


def _action_result(stat) -> QuickCardActionResult:
    state = "pinned" if stat.pinned_at is not None else (
        "established" if stat.card_clicks >= panel_behavior.ESTABLISH_CLICKS else "suggested"
    )
    return QuickCardActionResult(ok=True, state=state, card_clicks=stat.card_clicks)


@router.post("/quick-cards/click", response_model=MutationResponse[QuickCardActionResult])
def post_quick_card_click(
    body: QuickCardRefBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_v2),
) -> MutationResponse[QuickCardActionResult]:
    stat = _stat_or_404(
        panel_behavior.register_card_click(db, user, body.route_key, body.entity_id)
    )
    db.commit()
    return MutationResponse(data=_action_result(stat), invalidate=_INVALIDATE)


@router.post("/quick-cards/pin", response_model=MutationResponse[QuickCardActionResult])
def post_quick_card_pin(
    body: QuickCardPinBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_v2),
) -> MutationResponse[QuickCardActionResult]:
    stat = _stat_or_404(
        panel_behavior.set_pin(db, user, body.route_key, body.entity_id, body.pinned)
    )
    db.commit()
    return MutationResponse(data=_action_result(stat), invalidate=_INVALIDATE)


@router.post("/quick-cards/dismiss", response_model=MutationResponse[QuickCardActionResult])
def post_quick_card_dismiss(
    body: QuickCardRefBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_v2),
) -> MutationResponse[QuickCardActionResult]:
    stat = _stat_or_404(
        panel_behavior.dismiss_card(db, user, body.route_key, body.entity_id)
    )
    db.commit()
    result = QuickCardActionResult(ok=True, state="dismissed", card_clicks=0)
    return MutationResponse(data=result, invalidate=_INVALIDATE)
