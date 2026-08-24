# -*- coding: utf-8 -*-
"""Haftalık koç raporu — API v2 şemaları (2026-08-19)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportAgendaItem(BaseModel):
    key: str | None = None
    title: str
    detail: str
    severity: str | None = None  # high | medium | info (kural motoru); AI'da None


class CoachingReportRow(BaseModel):
    id: int
    week_start: str
    week_end: str
    version: int
    generated_at: datetime
    has_ai_agenda: bool
    agenda_count: int
    session_count: int  # bu rapora bağlı seans sayısı


class CoachingReportListResponse(BaseModel):
    rows: list[CoachingReportRow]


class CoachingReportCreateBody(BaseModel):
    week_end: str | None = None   # YYYY-MM-DD; boş = programın işlendiği son gün
    days: int | None = None       # varsayılan 7 (3-31)


class CoachingReportDetail(BaseModel):
    id: int
    student_id: int
    student_name: str
    week_start: str
    week_end: str
    version: int
    generated_at: datetime
    agenda: list[ReportAgendaItem]
    ai_agenda: list[ReportAgendaItem] | None = None
    ai_summary: str | None = None
    ai_tips: list[str] = []
    ai_watch_outs: list[str] = []
    ai_generated_at: datetime | None = None
