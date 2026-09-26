"""Haftalık İskelet şemaları (F1, 2026-09-25)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SkeletonSlotIn(BaseModel):
    weekday: int = Field(ge=0, le=6)          # 0=Pazartesi … 6=Pazar
    period: str | None = None                 # morning|noon|evening|None
    subject_id: int
    position: int = 0
    is_routine: bool = False
    default_count: int | None = Field(default=None, ge=1, le=100)


class SkeletonSlotOut(SkeletonSlotIn):
    id: int
    subject_name: str


class SkeletonSubjectOption(BaseModel):
    id: int
    name: str


class SkeletonResponse(BaseModel):
    exists: bool
    name: str | None = None
    source: str | None = None
    slots: list[SkeletonSlotOut] = []
    subjects: list[SkeletonSubjectOption] = []


class SkeletonSaveBody(BaseModel):
    name: str | None = None
    slots: list[SkeletonSlotIn] = Field(default_factory=list, max_length=120)


class SkeletonFromWeekBody(BaseModel):
    start: str
    end: str


class ChipBadge(BaseModel):
    code: str
    label: str
    tone: str


class GhostChip(BaseModel):
    rank: int
    kind: str                                 # thread|next|new|weak
    section_id: int
    book_id: int
    book_name: str
    section_label: str
    topic_id: int | None = None
    topic_name: str | None = None
    count: int
    remaining: int
    total: int
    reason: str
    badges: list[ChipBadge] = []


class GhostCell(BaseModel):
    slot_id: int
    date: str
    subject_id: int
    subject_name: str
    period: str | None = None
    position: int
    is_routine: bool
    chips: list[GhostChip] = []


class GhostDay(BaseModel):
    date: str
    ghosts: list[GhostCell] = []


class GhostsResponse(BaseModel):
    has_skeleton: bool
    days: list[GhostDay] = []


class GhostAcceptBody(BaseModel):
    slot_id: int
    date: str
    section_id: int
    count: int = Field(ge=1, le=100)
    chip_rank: int | None = None              # None = çip dışı seçim ("başka konu")
    chip_kind: str | None = None
    chip_count: int | None = None


class GhostActionBody(BaseModel):
    slot_id: int
    date: str
    action: str                               # dismissed|restore


class GhostRoutineBody(BaseModel):
    date: str


class GhostAcceptResult(BaseModel):
    task_ids: list[int] = []
    created: int = 0


class GhostAcceptanceReport(BaseModel):
    actions: int
    accepted: int
    other: int
    dismissed: int
    acceptance_pct: int | None = None
    by_rank: dict[int, int] = {}
    by_kind: dict[str, int] = {}
