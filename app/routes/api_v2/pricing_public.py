"""API v2 — Public fiyat/üyelik kataloğu (login gerektirmez).

Next.js `/pricing` sayfası bu uçtan plan yapısını çeker. TEK KAYNAK:
`app/services/pricing.py`. Süper admin override (M2) de aynı modülden okunacak.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services import pricing

router = APIRouter(prefix="/pricing", tags=["v2-pricing-public"])


@router.get("")
def pricing_catalog() -> dict[str, Any]:
    """Üyelik/fiyat kataloğu — solo bantları + kurum koç-başı tier'ları."""
    return pricing.get_pricing_catalog()
