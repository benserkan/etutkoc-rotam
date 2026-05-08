from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import get_db, require_teacher
from app.models import User
from app.services.ai_insights import (
    HEALTH_COLORS,
    HEALTH_LABELS,
    build_fleet_insights,
)
from app.templating import templates


router = APIRouter(prefix="/teacher")


@router.get("/ai-insights")
def ai_insights(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    today = date.today()
    insights = build_fleet_insights(db, user.id, today=today)

    # Trend grafiği için Chart.js verileri
    trend_labels = [b.start.strftime("%d %b") for b in insights.weekly_trend]
    trend_accepted = [b.accepted for b in insights.weekly_trend]
    trend_rejected = [b.rejected for b in insights.weekly_trend]

    return templates.TemplateResponse(
        "teacher/ai_insights.html",
        {
            "request": request,
            "user": user,
            "insights": insights,
            "today": today,
            "trend_labels": trend_labels,
            "trend_accepted": trend_accepted,
            "trend_rejected": trend_rejected,
            "HEALTH_LABELS": HEALTH_LABELS,
            "HEALTH_COLORS": HEALTH_COLORS,
        },
    )
