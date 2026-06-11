"""QA-1 — Hızlı erişim kartları şemaları (davranıştan öğrenen panel kartları)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PanelVisitEventIn(BaseModel):
    """Tek ziyaret olayı — ham path frontend'den gelir, sunucu katalogla
    normalize eder (katalog-dışı path sessizce atlanır)."""

    path: str = Field(..., max_length=512)
    dwell_ms: int = Field(default=0, ge=0)


class PanelVisitsBody(BaseModel):
    events: list[PanelVisitEventIn] = Field(..., max_length=50)


class PanelVisitsResult(BaseModel):
    accepted: int


class QuickCardModel(BaseModel):
    route_key: str
    entity_id: int | None = None
    href: str
    label: str
    sublabel: str | None = None
    # suggested (önerilen) | established (kalıcı) | pinned (sabitlenen)
    state: str
    score: float
    card_clicks: int


class QuickCardsResponse(BaseModel):
    cards: list[QuickCardModel]


class QuickCardRefBody(BaseModel):
    route_key: str = Field(..., max_length=64)
    entity_id: int | None = None


class QuickCardPinBody(QuickCardRefBody):
    pinned: bool = True


class QuickCardActionResult(BaseModel):
    ok: bool
    state: str | None = None
    card_clicks: int = 0
