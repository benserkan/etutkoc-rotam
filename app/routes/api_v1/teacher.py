"""API v1 — Öğretmen endpoint'leri (JSON).

- GET /teacher/students             → öğrenci listesi (özet)
- GET /teacher/students/{id}        → tek öğrenci detay özet
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User, UserRole
from app.routes.api_v1.dependencies import require_api_teacher
from app.services.analytics import student_snapshot


router = APIRouter(prefix="/teacher", tags=["teacher"])


class StudentSummaryOut(BaseModel):
    id: int
    full_name: str
    email: str
    grade_level: int | None
    is_graduate: bool
    is_active: bool
    grade_label: str
    exam_label: str


class StudentListOut(BaseModel):
    students: list[StudentSummaryOut]
    total: int


class StudentDetailOut(BaseModel):
    student: StudentSummaryOut
    today_planned: int
    today_completed: int
    week_planned: int
    week_completed: int
    rate_7d: float
    rate_30d: float
    consistency_7d: float
    hit_rate_7d: float
    worst_warning_level: str
    warnings: list[dict]


def _summary(student: User) -> StudentSummaryOut:
    return StudentSummaryOut(
        id=student.id,
        full_name=student.full_name,
        email=student.email,
        grade_level=student.grade_level,
        is_graduate=student.is_graduate,
        is_active=student.is_active,
        grade_label=student.display_grade_label,
        exam_label=student.effective_exam_label,
    )


@router.get("/students", response_model=StudentListOut)
def teacher_students_list(
    user: User = Depends(require_api_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmenin yönettiği öğrencilerin özet listesi."""
    students = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    return StudentListOut(
        students=[_summary(s) for s in students],
        total=len(students),
    )


@router.get("/students/{student_id}", response_model=StudentDetailOut)
def teacher_student_detail(
    student_id: int,
    user: User = Depends(require_api_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenci detay özet — bugün/hafta + 7/30g oran + uyarılar."""
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        raise HTTPException(
            status_code=404,
            detail={"error": "Öğrenci bulunamadı.", "code": "student_not_found"},
        )

    snap = student_snapshot(db, student, today=date.today())
    warnings = [
        {"level": w.level, "code": w.code, "title": w.title, "detail": w.detail}
        for w in (snap.warnings or [])
    ]
    return StudentDetailOut(
        student=_summary(student),
        today_planned=snap.today.planned,
        today_completed=snap.today.completed,
        week_planned=snap.week.planned,
        week_completed=snap.week.completed,
        rate_7d=float(snap.rate_7d or 0.0),
        rate_30d=float(snap.rate_30d or 0.0),
        consistency_7d=float(snap.consistency_7d or 0.0),
        hit_rate_7d=float(snap.hit_rate_7d or 0.0),
        worst_warning_level=snap.worst_warning_level,
        warnings=warnings,
    )
