"""API v2 — Kurum logosu (herkese açık) — 2026-09-30.

E-posta istemcileri logoyu çerezsiz çeker; bu yüzden kurum logosunun herkese
açık bir adresi gerekir. Logo bir marka varlığıdır (kişisel veri değil).
Yalnız aktif kurumların logosu verilir; `?v=` sürüm parametresi önbelleği kırar.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Institution

router = APIRouter(prefix="/brand", tags=["v2-brand-public"])


@router.get("/logo/{institution_id}")
def brand_logo_public_v2(institution_id: int, db: Session = Depends(get_db)):
    inst = db.get(Institution, institution_id)
    if inst is None or not inst.is_active or not inst.logo_content_type or not inst.logo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "logo_not_found", "message": "Logo bulunamadı."},
        )
    return Response(
        content=inst.logo_data,
        media_type=inst.logo_content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
