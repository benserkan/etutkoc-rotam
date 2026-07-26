"""Rehber (rol bazlı yapay zekâ onboarding rehberi) API'si.

Endpoint'ler (authenticated; rehber anahtarı kullanıcının rolüne ait değilse 404):
  - GET  /api/v2/me/guide/{guide_key}           — durum + gerçek-veri kontrol listesi
  - POST /api/v2/me/guide/{guide_key}/progress  — start | chapter_done | complete |
                                                   dismiss | reset

Kontrol listesi saklanmaz — guide_service her istekte gerçek veriden hesaplar
(kitap eklendi mi, program yayınlandı mı...). Kimse başkasının durumunu göremez.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.guide import (
    GuideProgressBody,
    GuideProgressResult,
    GuideResponse,
    GuideStateModel,
)
from app.services import guide_service

router = APIRouter(prefix="/me/guide", tags=["api-v2-guide"])

_INVALIDATE = ["me:guide"]


def _require_guide(user: User, guide_key: str) -> None:
    if not guide_service.can_access(user, guide_key):
        raise HTTPException(status_code=404, detail={"code": "guide_not_found"})


@router.get("/{guide_key}", response_model=GuideResponse)
def get_guide(
    guide_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_v2),
) -> GuideResponse:
    _require_guide(user, guide_key)
    state = guide_service.get_state(db, user, guide_key)
    checklist, preexisting = guide_service.checklist_for(db, user, guide_key, state)
    return GuideResponse(
        guide_key=guide_key,
        state=GuideStateModel(**guide_service.state_payload(state)),
        checklist=checklist,
        preexisting=preexisting,
        chapters=list(guide_service.CHAPTERS_BY_GUIDE.get(guide_key, [])),
    )


@router.post("/{guide_key}/progress", response_model=GuideProgressResult)
def post_guide_progress(
    guide_key: str,
    body: GuideProgressBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_v2),
) -> GuideProgressResult:
    _require_guide(user, guide_key)
    try:
        state = guide_service.apply_progress(
            db, user, guide_key, body.action, chapter=body.chapter, step=body.step
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc
    checklist, preexisting = guide_service.checklist_for(db, user, guide_key, state)
    return GuideProgressResult(
        state=GuideStateModel(**guide_service.state_payload(state)),
        checklist=checklist,
        preexisting=preexisting,
        # "watch" = konum kaydı (adım başına); query bayatlatma churn'u yaratmasın
        invalidate=[] if body.action == "watch" else list(_INVALIDATE),
    )
