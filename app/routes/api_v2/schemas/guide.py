"""Rehber (onboarding guide) API şemaları."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GuideStateModel(BaseModel):
    status: str  # not_started | in_progress | completed | dismissed
    current_chapter: str | None = None
    chapters_done: list[str] = []
    # Bölüm anahtarı → sonuna kadar izlenen adım indeksleri (kaldığı yerden devam)
    steps_watched: dict[str, list[int]] = {}
    completed_at: str | None = None
    dismissed_at: str | None = None


class GuideResponse(BaseModel):
    guide_key: str
    state: GuideStateModel
    # Bölüm anahtarı → REHBER BAŞLADIKTAN SONRA yapılan gerçek eylem
    checklist: dict[str, bool] = {}
    # Bölüm anahtarı → rehberden ÖNCE zaten mevcut veri ("zaten yapmışsın")
    preexisting: dict[str, bool] = {}
    chapters: list[str] = []


class GuideProgressBody(BaseModel):
    action: str = Field(pattern="^(start|chapter_done|watch|complete|dismiss|reset)$")
    chapter: str | None = Field(default=None, max_length=64)
    step: int | None = Field(default=None, ge=0, le=200)


class GuideProgressResult(BaseModel):
    ok: bool = True
    state: GuideStateModel
    checklist: dict[str, bool] = {}
    preexisting: dict[str, bool] = {}
    invalidate: list[str] = []
