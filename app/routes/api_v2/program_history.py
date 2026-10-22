"""Program geçmişi zaman çizelgesi uçları (koç + öğrenci) — 2026-10-22.

GET /teacher/students/{id}/program-history · GET /student/program-history
Salt okuma. Hafta sınırları ve sayılar `program_history` servisinden (tek merkez).
"""
from __future__ import annotations


from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.models.pool import PROGRAM_MODE_LABELS
from app.routes.api_v2.pool_student import history_row_out
from app.routes.api_v2.schemas.pool import PoolHistoryRow
from app.routes.api_v2.student import _require_student
from app.routes.api_v2.teacher import _get_owned_student, _require_teacher
from app.services import pool_mode as pm
from app.services.program_history import build_program_history

router = APIRouter(tags=["v2-program-history"])


class HistoryWeekOut(BaseModel):
    start: str
    end: str
    week_kind: str
    program_id: int | None = None
    cut: bool = False
    current: bool = False
    gorev_total: int
    gorev_done: int
    test_planned: int
    test_completed: int
    deneme_units: int
    deneme_done: int
    pct: int
    days_with_tasks: int


class HistorySwitchOut(BaseModel):
    date: str
    from_label: str
    to_label: str
    to_mode: str
    note: str | None = None


class HistoryEntryOut(BaseModel):
    kind: str  # week | period | switch
    week: HistoryWeekOut | None = None
    period: PoolHistoryRow | None = None
    period_current: bool = False
    switch: HistorySwitchOut | None = None


class ProgramHistoryResponse(BaseModel):
    student_id: int
    program_mode: str
    program_mode_label: str
    entries: list[HistoryEntryOut] = []
    weeks_count: int = 0
    periods_count: int = 0


def _response(db: Session, student: User, *, include_drafts: bool) -> ProgramHistoryResponse:
    rows = build_program_history(db, student, include_drafts=include_drafts)
    out: list[HistoryEntryOut] = []
    for e in rows:
        if e.kind == "week":
            out.append(HistoryEntryOut(kind="week", week=HistoryWeekOut(
                start=e.start.isoformat(), end=e.end.isoformat(), week_kind=e.week_kind or "program",
                program_id=e.program_id, cut=e.cut, current=e.current, gorev_total=e.gorev_total,
                gorev_done=e.gorev_done, test_planned=e.test_planned, test_completed=e.test_completed,
                deneme_units=e.deneme_units, deneme_done=e.deneme_done, pct=e.pct,
                days_with_tasks=e.days_with_tasks)))
        elif e.kind == "period":
            out.append(HistoryEntryOut(kind="period", period=history_row_out(e.period), period_current=e.current))
        else:
            s = e.switch or {}
            out.append(HistoryEntryOut(kind="switch", switch=HistorySwitchOut(
                date=e.start.isoformat(), from_label=s["from_label"], to_label=s["to_label"],
                to_mode=s["to_mode"], note=s.get("note"))))
    mode = pm.mode_of(student)
    return ProgramHistoryResponse(
        student_id=student.id, program_mode=mode, program_mode_label=PROGRAM_MODE_LABELS.get(mode, mode),
        entries=out, weeks_count=sum(1 for e in rows if e.kind == "week"),
        periods_count=sum(1 for e in rows if e.kind == "period"))


@router.get("/teacher/students/{student_id}/program-history", response_model=ProgramHistoryResponse)
def teacher_program_history(student_id: int, user: User = Depends(_require_teacher),
                            db: Session = Depends(get_db)) -> ProgramHistoryResponse:
    student = _get_owned_student(db, student_id, user.id)
    return _response(db, student, include_drafts=False)


@router.get("/student/program-history", response_model=ProgramHistoryResponse)
def student_program_history(user: User = Depends(_require_student),
                            db: Session = Depends(get_db)) -> ProgramHistoryResponse:
    return _response(db, user, include_drafts=False)


