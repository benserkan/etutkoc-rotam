"""Öğrenci detay sayfası — haftalık ilerleme ucu (servis: app/services/weekly_progress.py)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.routes.api_v2.deneme_tasks import DenemeAnalysisResponse
from app.routes.api_v2.teacher import _get_owned_student, _require_teacher

router = APIRouter(prefix="/teacher", tags=["v2-weekly-progress"])


class WPWeek(BaseModel):
    program_id: int
    kind: str = "program"  # program | takvim | donem
    start: str
    end: str
    label: str
    day_index: int
    days: int
    ended: bool
    today_label: str
    compare_days: int
    usual_start: str


class WPCard(BaseModel):
    key: str
    name: str
    hint: str
    group: Literal["gelisim", "ilerleme", "risk"]
    unit: str
    direction: int
    value: float | None = None
    value_label: str
    prev: float | None = None
    prev_label: str
    status: Literal["insufficient", "normal", "below", "critical", "above", "high", "low", "info"]
    low: float | None = None
    high: float | None = None
    baseline: list[float] = []
    trend_run: int = 0
    trend: bool = False
    verdict: str


class WPMissing(BaseModel):
    title: str
    tests: int | None = None


class WPDay(BaseModel):
    date: str
    day: str
    label: str
    state: Literal["future", "today", "none", "done", "partial", "missed"]
    total: int
    done: int
    missing: list[WPMissing]
    first_tick: str | None = None


class WPChartPoint(BaseModel):
    label: str
    range: str
    value: float | None = None
    current: bool
    in_baseline: bool


class WPExtreme(BaseModel):
    value: float
    label: str


class WPPeriodSummary(BaseModel):
    weeks: int
    median: float | None = None
    best: WPExtreme | None = None
    worst: WPExtreme | None = None
    band_low: float | None = None
    band_high: float | None = None
    decline_run: int = 0


class WPProjection(BaseModel):
    same_point_pct: float | None = None
    projected_pct: float | None = None
    band_low: float | None = None
    band_high: float | None = None
    position: Literal["below", "within", "above"] | None = None
    last4: list[float] = []
    slope_per_week: float | None = None
    load: int = 0


class WPGroup(BaseModel):
    key: str
    name: str
    desc: str


class WPAction(BaseModel):
    key: str
    title: str
    why: str
    cta_label: str
    cta_href: str
    agenda: str


class WeeklyProgressResponse(BaseModel):
    has_program: bool
    week: WPWeek | None = None
    headline: dict[str, WPCard] = {}
    projection: WPProjection | None = None
    days: list[WPDay] = []
    chart: list[WPChartPoint] = []
    period_summary: WPPeriodSummary | None = None
    groups: list[WPGroup] = []
    cards: list[WPCard] = []
    actions: list[WPAction] = []
    deneme: DenemeAnalysisResponse | None = None


@router.get("/students/{student_id}/weekly-progress", response_model=WeeklyProgressResponse)
def weekly_progress(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Bu hafta (aynı güne kadar kıyas) + haftalar arası gidişat + 13 başlık + önlemler (salt okuma)."""
    from app.services.weekly_progress import build_weekly_progress

    student = _get_owned_student(db, student_id, user.id)
    return build_weekly_progress(db, student)
