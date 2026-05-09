"""Stage 10 — Public KVKK + gizlilik politikası bilgi sayfaları.

Auth gerektirmez. Footer linki + login + signup sayfalarından erişilebilir.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.deps import get_current_user
from app.models import User
from app.templating import templates


router = APIRouter()


@router.get("/kvkk")
def kvkk_info(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    """KVKK madde 11 hakları ve aydınlatma metni — Türkçe, public."""
    return templates.TemplateResponse(
        "kvkk/info.html",
        {"request": request, "user": user},
    )


@router.get("/privacy")
def privacy_policy(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    """Gizlilik politikası — public."""
    return templates.TemplateResponse(
        "kvkk/privacy.html",
        {"request": request, "user": user},
    )
