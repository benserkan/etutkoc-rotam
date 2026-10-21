"""Öğrenci "Gelişim" sayfası uçları (2026-10-21).

Koçun öğrenci detayındaki göstergelerin öğrenciye görünen hâli — hesap koç ekranıyla AYNI
servislerden (build_student_analytics + build_weekly_progress), sayılar iki yüzde birebir.
Koça yönelik parçalar (uyarı kartları, "Seansa ekle" önlemleri) öğrenciye gönderilmez.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.routes.api_v2.schemas.teacher import TeacherStudentAnalyticsResponse
from app.routes.api_v2.student import _require_student
from app.routes.api_v2.weekly_progress import WeeklyProgressResponse

router = APIRouter(prefix="/student", tags=["v2-student-progress"])


@router.get("/analytics", response_model=TeacherStudentAnalyticsResponse)
def student_analytics(user: User = Depends(_require_student), db: Session = Depends(get_db)):
    from app.routes.api_v2.teacher import build_student_analytics

    out = build_student_analytics(db, user, user.teacher_id)
    out.warnings = []  # koç dili ("öğrenciyle konuş") — öğrenci görmez
    return out


@router.get("/weekly-progress", response_model=WeeklyProgressResponse)
def student_weekly_progress(user: User = Depends(_require_student), db: Session = Depends(get_db)):
    from app.services.weekly_progress import build_weekly_progress

    data = build_weekly_progress(db, user)
    data["actions"] = []  # koçun "Seansa ekle" önlemleri
    return data
