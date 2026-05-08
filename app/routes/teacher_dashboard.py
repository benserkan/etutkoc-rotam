from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import get_db, require_teacher
from app.models import User, UserRole
from app.services.analytics import StudentSnapshot, student_snapshot
from app.services.request_service import pending_count_for_teacher
from app.templating import templates
from sqlalchemy.orm import joinedload
from app.models import RequestStatus, TaskRequest


router = APIRouter()


@router.get("/teacher")
def teacher_dashboard(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    today = date.today()
    students = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )

    snapshots: list[StudentSnapshot] = []
    for s in students:
        snapshots.append(student_snapshot(db, s, today=today))

    # Öğrencileri duruma göre sırala: kırmızı → sarı → yeşil, sonra isme göre
    level_order = {"red": 0, "amber": 1, "green": 2}
    snapshots.sort(
        key=lambda s: (level_order[s.worst_warning_level], s.student.full_name)
    )

    # Filo özeti
    fleet_red = sum(1 for s in snapshots if s.worst_warning_level == "red")
    fleet_amber = sum(1 for s in snapshots if s.worst_warning_level == "amber")
    fleet_green = sum(1 for s in snapshots if s.worst_warning_level == "green")

    # Toplam uyarı feed — en acil 15 tanesi
    all_warnings = []
    for sn in snapshots:
        for w in sn.warnings:
            all_warnings.append((sn.student, w))
    level_rank = {"red": 0, "amber": 1, "green": 2}
    all_warnings.sort(key=lambda t: (level_rank[t[1].level], t[0].full_name))
    top_warnings = all_warnings[:15]

    # Bu hafta toplam plan / tamamlanma (öğretmenin tüm öğrencileri)
    week_planned = sum(sn.week.planned for sn in snapshots)
    week_completed = sum(sn.week.completed for sn in snapshots)
    today_planned = sum(sn.today.planned for sn in snapshots)
    today_completed = sum(sn.today.completed for sn in snapshots)

    # Bekleyen talepler (öğrenci geri bildirimleri)
    pending_requests = (
        db.query(TaskRequest)
        .options(joinedload(TaskRequest.student), joinedload(TaskRequest.task))
        .filter(
            TaskRequest.teacher_id == user.id,
            TaskRequest.status == RequestStatus.PENDING,
        )
        .order_by(TaskRequest.created_at.desc())
        .limit(5)
        .all()
    )
    pending_requests_total = pending_count_for_teacher(db, user.id)

    return templates.TemplateResponse(
        "teacher/dashboard.html",
        {
            "request": request,
            "user": user,
            "today": today,
            "snapshots": snapshots,
            "fleet_red": fleet_red,
            "fleet_amber": fleet_amber,
            "fleet_green": fleet_green,
            "fleet_total": len(snapshots),
            "top_warnings": top_warnings,
            "total_warnings": len(all_warnings),
            "week_planned": week_planned,
            "week_completed": week_completed,
            "today_planned": today_planned,
            "today_completed": today_completed,
            "pending_requests": pending_requests,
            "pending_requests_total": pending_requests_total,
        },
    )
