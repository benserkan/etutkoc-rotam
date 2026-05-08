"""HTMX kısmi (fragment) endpoint'leri — küçük, çağıran tarafça yenilenen UI parçaları."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User, UserRole
from app.services.request_service import (
    pending_count_for_student,
    pending_count_for_teacher,
)


router = APIRouter(prefix="/_partial")


def _badge_html(count: int, color: str) -> str:
    if count <= 0:
        return ""
    return (
        f'<span class="inline-flex items-center justify-center min-w-[18px] h-[18px] '
        f'px-1 rounded-full text-[10px] font-bold text-white" '
        f'style="background: {color};">{count}</span>'
    )


@router.get("/teacher-pending-count", response_class=HTMLResponse)
def teacher_pending_count(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user or user.role != UserRole.TEACHER:
        # Boş span döndür ki HTMX hedefi korusun
        return HTMLResponse(
            '<span hx-get="/_partial/teacher-pending-count" hx-trigger="every 30s" hx-swap="outerHTML"></span>'
        )
    count = pending_count_for_teacher(db, user.id)
    badge = _badge_html(count, "#d97706")
    # Tekrarlayan etiketle çağrılsın
    return HTMLResponse(
        f'<span hx-get="/_partial/teacher-pending-count" hx-trigger="every 30s" hx-swap="outerHTML">{badge}</span>'
    )


@router.get("/student-pending-count", response_class=HTMLResponse)
def student_pending_count(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user or user.role != UserRole.STUDENT:
        return HTMLResponse(
            '<span hx-get="/_partial/student-pending-count" hx-trigger="every 60s" hx-swap="outerHTML"></span>'
        )
    count = pending_count_for_student(db, user.id)
    badge = _badge_html(count, "#0ea5e9")
    return HTMLResponse(
        f'<span hx-get="/_partial/student-pending-count" hx-trigger="every 60s" hx-swap="outerHTML">{badge}</span>'
    )
