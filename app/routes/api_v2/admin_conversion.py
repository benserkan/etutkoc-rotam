"""API v2 — Süper Admin: Dönüşüm (conversion) hunisi panosu.

Landing → üyelik → ücretli hunisi + A/B varyant dönüşümü. Salt-okuma agregat.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.routes.api_v2.admin import _require_super_admin
from app.routes.api_v2.schemas.conversion import ConversionResponse
from app.services import conversion_service

router = APIRouter(prefix="/admin/conversion", tags=["v2-admin-conversion"])


@router.get("", response_model=ConversionResponse)
def admin_conversion(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Son N gün landing dönüşüm hunisi + varyant kırılımı."""
    return ConversionResponse(**conversion_service.compute_funnel(db, days=days))
