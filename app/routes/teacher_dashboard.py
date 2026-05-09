from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import get_db, require_teacher
from app.models import User, UserRole
from app.services.analytics import StudentSnapshot, student_snapshot
from app.services.request_service import pending_count_for_teacher
from app.services.risk_analysis import (
    bulk_risk_assessment,
    filter_at_risk,
    get_active_mutes,
)
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

    # Risk paneli özeti — sadece aktif öğrenciler, mute'lu olanlar dışta
    active_students = [s for s in students if s.is_active]
    risk_assessments = bulk_risk_assessment(db, students=active_students, today=today)
    muted_ids = get_active_mutes(db, user.id)
    visible_at_risk = [
        a for a in filter_at_risk(risk_assessments, min_level="medium")
        if a.student.id not in muted_ids
    ]
    at_risk_count = len(visible_at_risk)
    at_risk_critical = sum(1 for a in visible_at_risk if a.level == "critical")

    # Stage 6 — bağımsız öğretmen için kredi durumu (banner gösterimi için)
    credit_banner = None
    if user.institution_id is None:
        from app.services.credits import (
            CreditOwner, current_period, get_or_create_account,
        )
        owner = CreditOwner.for_user(user)
        acc = get_or_create_account(db, owner=owner, period=current_period())
        db.commit()
        if acc.is_currently_blocked():
            credit_banner = {
                "level": "blocked",
                "blocked_until": acc.blocked_until,
                "remaining": acc.remaining_credits,
            }
        elif acc.usage_pct >= 80:
            credit_banner = {
                "level": "warn",
                "pct": acc.usage_pct,
                "remaining": acc.remaining_credits,
            }

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
            "at_risk_count": at_risk_count,
            "at_risk_critical": at_risk_critical,
            "credit_banner": credit_banner,
        },
    )
