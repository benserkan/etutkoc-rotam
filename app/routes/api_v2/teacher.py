"""API v2 — Öğretmen paneli endpoint'leri (Dalga 3 Paket 1 + 2).

Paket 1 (okuma):
  GET  /api/v2/teacher/dashboard               → TeacherDashboardResponse
  GET  /api/v2/teacher/students                → TeacherStudentListResponse
  GET  /api/v2/teacher/students/{id}           → TeacherStudentDetailResponse
  GET  /api/v2/teacher/badges                  → TeacherBadgesResponse (60s polling)
  GET  /api/v2/teacher/me                      → TeacherMeResponse

Paket 2 (program CRUD):
  GET  /api/v2/teacher/students/{id}/day       → TeacherStudentDayResponse
  GET  /api/v2/teacher/students/{id}/week      → TeacherStudentWeekResponse
  POST /api/v2/teacher/students/{id}/tasks     → MutationResponse[TeacherTask]
  PATCH /api/v2/teacher/tasks/{task_id}        → MutationResponse[TeacherTask]
  DELETE /api/v2/teacher/tasks/{task_id}       → MutationResponse[{deleted}]
  POST /api/v2/teacher/tasks/{task_id}/items   → MutationResponse[TeacherTask]
  PATCH /api/v2/teacher/tasks/{task_id}/items/{item_id}
                                                → MutationResponse[TeacherTask]
  POST /api/v2/teacher/students/{id}/bulk-tasks → MutationResponse[BulkResult]

Paket 3 (talep yanıtlama):
  GET  /api/v2/teacher/requests                → TeacherRequestListResponse
  GET  /api/v2/teacher/requests/{id}           → TeacherRequestDetail
  POST /api/v2/teacher/requests/{id}/approve   → MutationResponse[TeacherRequestDetail]
  POST /api/v2/teacher/requests/{id}/reject    → MutationResponse[TeacherRequestDetail]
  POST /api/v2/teacher/requests/{id}/respond   → MutationResponse[TeacherRequestDetail]

Paket 4 destek:
  GET  /api/v2/teacher/books                        → TeacherBookListResponse

Paket 4 (öğrenci yönetimi):
  POST   /api/v2/teacher/students                   → MutationResponse[StudentCreateResult]
  PATCH  /api/v2/teacher/students/{id}              → MutationResponse[StudentBriefProfile]
  POST   /api/v2/teacher/students/{id}/deactivate   → MutationResponse[StudentBriefProfile]
  POST   /api/v2/teacher/students/{id}/reactivate   → MutationResponse[StudentBriefProfile]
  DELETE /api/v2/teacher/students/{id}              → MutationResponse[{deleted}]
  GET    /api/v2/teacher/students/{id}/books        → StudentBookListResponse
  POST   /api/v2/teacher/students/{id}/books        → MutationResponse[StudentBookListItem]
  DELETE /api/v2/teacher/students/{id}/books/{book_id}
                                                     → MutationResponse[{unassigned}]
  GET    /api/v2/teacher/students/{id}/parents      → StudentParentsResponse
  POST   /api/v2/teacher/students/{id}/parents      → MutationResponse[ParentInviteResult]
  DELETE /api/v2/teacher/students/{id}/parents/{link_id}
                                                     → MutationResponse[{unlinked}]

Auth: dual-channel (BFF cookie + Bearer + Session). _require_teacher dependency'si
get_current_user_v2 üzerinden — Jinja /teacher/* dokunulmaz, kontrat ayrı.

Çift sahiplik kontrolü:
  - student.teacher_id == user.id (öğrenci yetkisi)
  - task.student_id → öğrencinin sahibi user.id mi (görev yetkisi)
Cross-tenant erişimde 404 (öğrenciyi/görevi yok say) — tenant isolation
29/29 regresyon kontrolünü korumak için.
"""
from __future__ import annotations

import calendar
import json
import logging
import secrets
import string as _string_mod
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    AcademicYear,
    Book,
    BookSection,
    COACH_PAYMENT_METHOD_LABELS,
    COACHING_CHANNEL_LABELS,
    COACHING_STATUS_LABELS,
    CoachPayment,
    CoachPaymentMethod,
    CoachStudentRate,
    CoachingChannel,
    CoachingInsight,
    CoachingSession,
    CoachingSessionStatus,
    SessionCaptureSource,
    EXAM_SECTION_LABELS,
    ExamResult,
    ExamSection,
    GraduateMode,
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    PARENT_RELATION_LABELS,
    ParentInvitation,
    ParentRelation,
    ParentStudentLink,
    RequestStatus,
    RequestType,
    SectionProgress,
    StudentBook,
    Task,
    TaskBookItem,
    TaskRequest,
    TaskStatus,
    TaskType,
    Track,
    User,
    UserRole,
    WeekNote,
    compute_net,
)
from app.routes.api_v2.dependencies import _auth_error, assert_active_coaching, get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.teacher import (
    BulkResult,
    BulkTasksBody,
    BurnoutSignalRow,
    DashboardRequest,
    DnaNotifyParentBody,
    DnaNotifyParentResult,
    DnaSubjectRow,
    ExamCreateBody,
    ExamListSummary,
    ExamResultRow,
    ExamSectionOption,
    ExamSubjectRow,
    StudentExamListResponse,
    TopicPerformanceResponse,
    build_topic_performance_response,
    CoachingSessionCreateBody,
    CoachingSessionRow,
    CoachingSessionSummary,
    StudentSessionListResponse,
    SessionPrefillResponse,
    SessionPrefillSubject,
    SessionPrefillExam,
    RateUpdateBody,
    PaymentCreateBody,
    PaymentRow,
    StudentPaymentsResponse,
    BillingStudentRow,
    BillingTotals,
    BillingMonthResponse,
    AiConsentResponse,
    CoachingInsightCacheResponse,
    CoachingInsightResponse,
    ParsePhotoBody,
    ParseVoiceBody,
    PlanUpgradeBody,
    SessionDraftResponse,
    SubscriptionRequestBody,
    SubscriptionRequestResult,
    TranscribeResponse,
    TeacherPlanOption,
    TeacherPlanResponse,
    TrialStatusResponse,
    DnaTrendInfo,
    FocusBadge,
    FocusSessionRow,
    GoalNodeRow,
    GoalSubjectProgressRow,
    GoalSummaryInfo,
    GoalTopicProgressRow,
    ParentInviteBody,
    ParentInviteResult,
    ParentLinkItem,
    PendingParentInvitation,
    PromoteBody,
    PromoteChoice,
    PromoteFormResponse,
    PromoteResult,
    PromoteYearOption,
    RequestApproveBody,
    RequestRejectBody,
    RequestRespondBody,
    ReviewBreakdownInfo,
    ReviewCardRow,
    ReviewSeedBody,
    ReviewSeedResult,
    ReviewSubjectOption,
    RiskRow,
    StruggleCardRow,
    StruggleSectionOption,
    SectionCompletedBaselineBody,
    StudentBookAssignBody,
    StudentBookBulkAssignBody,
    StudentBookBulkAssignResult,
    StudentBookListItem,
    StudentBookListResponse,
    StudentBookSectionProgressRow,
    StudentBriefProfile,
    StudentCreateBody,
    StudentCreateResult,
    StudentParentsResponse,
    StudentPatchBody,
    StudentProgramSummary,
    ApplyTaskTemplateBody,
    CarryoverBody,
    CarryoverCandidate,
    CarryoverCandidatesResponse,
    CarryoverResult,
    TaskCreateBody,
    TaskItemBody,
    TaskTemplateCreateBody,
    TaskTemplateFromTaskBody,
    TaskTemplateItemModel,
    TaskTemplateListResponse,
    TaskTemplateModel,
    SetWeekAnchorBody,
    TaskItemPatchBody,
    TaskItemResultBody,
    WeeklyProgramCreateBody,
    WeeklyProgramDeleteBody,
    WeeklyProgramItem,
    WeeklyProgramListResponse,
    WeeklyProgramOverlapItem,
    WeeklyProgramUpdateBody,
    WeeklyProgramWrapLegacyBody,
    WorkBlockCreateBody,
    WorkBlockItem,
    WorkBlockListResponse,
    WorkBlockUpdateBody,
    TaskPatchBody,
    TaskSingleItemEditBody,
    TeacherBadgesResponse,
    TeacherBookListItem,
    TeacherBookListResponse,
    TeacherDashboardResponse,
    TeacherDnaResponse,
    TeacherFocusResponse,
    TeacherGoalActionResult,
    TeacherGoalCreateBody,
    TeacherGoalUpdateBody,
    TeacherGoalsResponse,
    TeacherMeResponse,
    TeacherRequestDetail,
    TeacherRequestListItem,
    TeacherRequestListResponse,
    AnalyticsDayFlag,
    AnalyticsDow,
    AnalyticsExamPoint,
    AnalyticsProjection,
    AnalyticsSubjectRow,
    AnalyticsSummary,
    AnalyticsTrendPoint,
    AnalyticsWarningItem,
    AnalyticsWeekPoint,
    DashboardWarningRow,
    DashboardWarningsFeedResponse,
    ParentNoteBody,
    ParentNoteResult,
    WarningAckBody,
    WarningUnackBody,
    StudentResetPasswordResult,
    TeacherBurnoutFleetResponse,
    TeacherBurnoutFleetRow,
    TeacherReviewFleetResponse,
    TeacherReviewFleetRow,
    TeacherReviewResponse,
    TeacherStudentAnalyticsResponse,
    TeacherStudentDayResponse,
    TeacherStudentDetailResponse,
    TeacherStudentListItem,
    TeacherStudentListResponse,
    TeacherActivePhase,
    TeacherDaySubjectSummary,
    TeacherStudentWeekDay,
    TeacherStudentWeekResponse,
    TeacherSuggestionInline,
    TeacherTask,
    TeacherTaskItem,
    TeacherWeekNote,
)
from app.services.analytics import student_snapshot
from app.services.request_service import (
    RequestError,
    approve_request as svc_approve_request,
    pending_count_for_teacher,
    reject_request as svc_reject_request,
    respond_question as svc_respond_question,
)
from app.services.risk_analysis import (
    bulk_risk_assessment,
    filter_at_risk,
    get_active_mutes,
)
from app.services.task_service import (
    ReservationError,
    release_item,
    release_task_items,
    reserve_item,
    set_item_completion as svc_set_item_completion,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teacher", tags=["v2-teacher"])


# =============================================================================
# Auth kapısı
# =============================================================================


def _require_teacher(user: User = Depends(get_current_user_v2)) -> User:
    """Sadece TEACHER rolüne izin ver."""
    if user.role != UserRole.TEACHER:
        raise _auth_error(
            "Bu uç nokta öğretmen hesabı bekler",
            "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _ai_credit_exhausted_error(user: User, exc_message: str) -> HTTPException:
    """402 ai_credit_exhausted — koçu /teacher/plan'a yönlendiren zenginleştirilmiş hata.

    Frontend toast'una `details.upgrade_url` + `details.upgrade_to_plan_label` ekler
    → "Solo Başlangıç paketini al → /teacher/plan" gibi link yönlendirir.
    """
    from app.services.plans import PLAN_CATALOG
    post_plan = user.post_trial_plan or "solo_pro"
    pti = PLAN_CATALOG.get(post_plan)
    upgrade_label = pti.label if pti else "Solo Başlangıç"
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "error": "credit",
            "code": "ai_credit_exhausted",
            "message": exc_message,
            "details": {
                "upgrade_url": "/teacher/plan",
                "upgrade_to_plan": post_plan,
                "upgrade_to_plan_label": upgrade_label,
            },
        },
    )


def _get_owned_student(db: Session, student_id: int, teacher_id: int) -> User:
    """Öğretmenin kendi öğrencisini yükle, değilse 404.

    Cross-tenant erişimde de 404 — öğrencinin varlığı sızdırılmaz.
    """
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == teacher_id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "student_not_found",
                "message": "Öğrenci bulunamadı.",
            },
        )
    return student


# =============================================================================
# Builder yardımcıları
# =============================================================================


def _has_pending_request_for_student(db: Session, student_id: int) -> bool:
    return (
        db.query(TaskRequest.id)
        .filter(
            TaskRequest.student_id == student_id,
            TaskRequest.status == RequestStatus.PENDING,
        )
        .first()
        is not None
    )


def _pending_request_count_for_student(db: Session, student_id: int) -> int:
    return (
        db.query(func.count(TaskRequest.id))
        .filter(
            TaskRequest.student_id == student_id,
            TaskRequest.status == RequestStatus.PENDING,
        )
        .scalar()
        or 0
    )


def _build_brief_profile(student: User) -> StudentBriefProfile:
    # Paket 3.5b — Jinja student_detail.html header parite için zenginleştirilmiş alanlar
    from app.models.user import TRACK_LABELS, GRADUATE_MODE_LABELS

    CURRICULUM_LABELS = {
        "lgs": "LGS Müfredatı",
        "klasik_lise": "Klasik Lise",
        "maarif_lise": "Maarif Modeli",
    }
    track_value = student.track.value if student.track else None
    track_lbl = TRACK_LABELS.get(student.track) if student.track else None
    cm = student.effective_curriculum_model
    cm_value = cm.value if cm else None
    cm_label = CURRICULUM_LABELS.get(cm_value) if cm_value else None
    exam_date = student.effective_exam_date
    grad_mode_value = (
        student.graduate_mode.value if (student.is_graduate and student.graduate_mode) else None
    )
    return StudentBriefProfile(
        id=student.id,
        full_name=student.full_name,
        email=student.email,
        grade_level=student.grade_level,
        is_active=bool(student.is_active),
        is_graduate=bool(getattr(student, "is_graduate", False)),
        institution_id=student.institution_id,
        teacher_id=student.teacher_id,
        last_login_at=student.last_login_at,
        created_at=student.created_at,
        display_grade_label=student.display_grade_label,
        track=track_value,
        track_label=track_lbl,
        track_required=bool(student.requires_track),
        track_missing=bool(student.requires_track and student.track is None),
        curriculum_model=cm_value,
        curriculum_label=cm_label,
        exam_target=student.effective_exam_target,
        exam_label=student.effective_exam_label,
        exam_date=exam_date.isoformat() if exam_date else None,
        graduate_mode=grad_mode_value,
        academic_year_name=(
            student.academic_year.name if student.academic_year else None
        ),
    )


# =============================================================================
# 1) GET /teacher/dashboard
# =============================================================================


@router.get("/dashboard", response_model=TeacherDashboardResponse)
def teacher_dashboard_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmenin filo paneli — risk + bekleyen talep + KPI özetleri.

    Eşdeğer Jinja: app/routes/teacher_dashboard.py:23 (teacher_dashboard).
    """
    today = date.today()
    students = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    active_students = [s for s in students if s.is_active]

    # StudentSnapshot toplu üretim — YALNIZ AKTİF öğrenci. Koçluğu sonlandırılan
    # (pasif) öğrenci filo özetine + tamamlama oranına GİRMEZ (koçun ortalamasını
    # düşürmez). student_count = toplam, active_student_count = aktif ayrı döner.
    snapshots = [student_snapshot(db, s, today=today) for s in active_students]

    # Öğrenci durumu (Yolunda/Uyarı/Kritik) — risk_assessments hesaplandıktan
    # SONRA aşağıda risk_analysis seviyesinden türetilir (worst_warning_level
    # DEĞİL — o, drilldown ?risk filtresiyle uyuşmuyor, "Kritik 1 ama liste boş"
    # bug'ı yaratıyordu).

    # Hafta + bugün toplamı (soru-bazlı — geriye uyum)
    week_planned = sum(sn.week.planned for sn in snapshots)
    week_completed = sum(sn.week.completed for sn in snapshots)
    today_planned = sum(sn.today.planned for sn in snapshots)
    today_completed = sum(sn.today.completed for sn in snapshots)
    week_rate = (week_completed / week_planned) if week_planned > 0 else 0.0

    # GÖREV-bazlı filo toplamı (görev/test/deneme AYRI) — "X test" şişmesini
    # önler: deneme'nin soruları test hacmine girmez. Tek batch sorgu (snapshot
    # döngüsünden verimli).
    from app.services import gorev_stats
    _wk_start = today - timedelta(days=6)
    _all_ids = [s.id for s in active_students]  # görev/test toplamı yalnız aktif
    gorev_week_total = gorev_week_done = 0
    gorev_today_total = gorev_today_done = 0
    test_week_planned = test_week_completed = 0
    if _all_ids:
        _wk_tasks = (
            db.query(Task)
            .options(joinedload(Task.book_items)
                     .joinedload(TaskBookItem.book).joinedload(Book.subject))
            .filter(Task.student_id.in_(_all_ids), Task.date >= _wk_start,
                    Task.date <= today, Task.is_draft.is_(False))
            .all()
        )
        _wk_by: dict[int, list] = {}
        _today_by: dict[int, list] = {}
        for _t in _wk_tasks:
            _wk_by.setdefault(_t.student_id, []).append(_t)
            if _t.date == today:
                _today_by.setdefault(_t.student_id, []).append(_t)
        for _sid in _all_ids:
            _gw = gorev_stats.summarize(_wk_by.get(_sid, []))
            gorev_week_total += _gw.gorev_total
            gorev_week_done += _gw.gorev_done
            test_week_planned += _gw.test_planned
            test_week_completed += _gw.test_completed
            _gt = gorev_stats.summarize(_today_by.get(_sid, []))
            gorev_today_total += _gt.gorev_total
            gorev_today_done += _gt.gorev_done
    gorev_week_rate = (gorev_week_done / gorev_week_total) if gorev_week_total > 0 else 0.0

    # Risk paneli — sadece aktif + mute'suz medium+
    muted_ids = get_active_mutes(db, user.id)
    risk_assessments = bulk_risk_assessment(db, students=active_students, today=today)
    visible_at_risk = [
        a for a in filter_at_risk(risk_assessments, min_level="medium")
        if a.student.id not in muted_ids
    ]
    at_risk_count = len(visible_at_risk)
    at_risk_critical = sum(1 for a in visible_at_risk if a.level == "critical")

    # Öğrenci durumu kartı (Yolunda/Uyarı/Kritik) — risk_analysis seviyesinden,
    # drilldown (?risk=ok/medium/critical) + /institution/at-risk ile AYNI sistem.
    # muted→ok. Kritik=critical · Uyarı=medium+high · Yolunda=ok. Böylece kart
    # sayısı = tıklanan liste (eski worst_warning_level uyuşmazlığı giderildi).
    _risk_lv = {
        a.student.id: ("ok" if a.student.id in muted_ids else a.level)
        for a in risk_assessments
    }
    fleet_red = sum(1 for lv in _risk_lv.values() if lv == "critical")
    fleet_amber = sum(1 for lv in _risk_lv.values() if lv in ("medium", "high"))
    fleet_green = sum(1 for lv in _risk_lv.values() if lv == "ok")

    top_5: list[RiskRow] = []
    for a in visible_at_risk[:5]:
        top_5.append(RiskRow(
            student_id=a.student.id,
            full_name=a.student.full_name,
            level=a.level,
            reasons=[ind.title for ind in a.indicators[:3]],
        ))

    # Bekleyen talepler — son 5
    pending = (
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
    recent_requests = [
        DashboardRequest(
            id=r.id,
            student_id=r.student_id,
            student_name=r.student.full_name if r.student else "—",
            type=r.type.value,
            task_id=r.task_id,
            task_title=(r.task.title if r.task else None),
            created_at=r.created_at,
        )
        for r in pending
    ]
    pending_total = pending_count_for_teacher(db, user.id)

    return TeacherDashboardResponse(
        student_count=len(students),
        active_student_count=len(active_students),
        at_risk_count=at_risk_count,
        at_risk_critical=at_risk_critical,
        pending_requests_count=pending_total,
        today_planned=today_planned,
        today_completed=today_completed,
        week_planned=week_planned,
        week_completed=week_completed,
        week_completion_rate=week_rate,
        gorev_today_total=gorev_today_total,
        gorev_today_done=gorev_today_done,
        gorev_week_total=gorev_week_total,
        gorev_week_done=gorev_week_done,
        gorev_week_rate=gorev_week_rate,
        test_week_planned=test_week_planned,
        test_week_completed=test_week_completed,
        fleet_red=fleet_red,
        fleet_amber=fleet_amber,
        fleet_green=fleet_green,
        top_5_at_risk=top_5,
        recent_requests=recent_requests,
    )


# =============================================================================
# 2) GET /teacher/students — listele + filtre + sayfalama
# =============================================================================


_RiskFilter = Literal["all", "ok", "medium", "high", "critical"]


@router.get("/students", response_model=TeacherStudentListResponse)
def teacher_students_v2(
    q: str | None = Query(None, max_length=120, description="Ad/email arama"),
    grade_level: int | None = Query(None, ge=5, le=13),
    risk: str | None = Query(None, description="all / ok / medium / high / critical"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmenin tüm öğrencileri — filtreli + sayfalı.

    100+ öğrenci senaryosunda performans için:
      - DB-seviyesinde filtre (q, grade_level)
      - risk filtresi sayfalamadan ÖNCE değerlendirilir (snapshot listesini
        sayfalamak için iki aşamalı: filtre + sayfa kesiti)
    """
    # Risk filtresi parametre normalizasyonu
    risk_norm: _RiskFilter = "all"
    if risk in ("ok", "medium", "high", "critical"):
        risk_norm = risk  # type: ignore[assignment]

    # Temel sorgu
    base_q = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
    )
    if grade_level is not None:
        base_q = base_q.filter(User.grade_level == grade_level)
    if q:
        like = f"%{q.strip().lower()}%"
        base_q = base_q.filter(
            or_(
                func.lower(User.full_name).like(like),
                func.lower(User.email).like(like),
            )
        )

    # Tam liste — risk filtresi snapshot gerektirdiği için önce hepsini çek
    students = base_q.order_by(User.full_name).all()
    today = date.today()

    # Risk filtresi: snapshot/risk hesabı gerek
    risk_levels_by_id: dict[int, str] = {}
    if risk_norm != "all":
        actives = [s for s in students if s.is_active]
        muted_ids = get_active_mutes(db, user.id)
        # bulk_risk_assessment yalnız aktiflere çalışır; pasifler "ok" sayılır
        assessments = bulk_risk_assessment(db, students=actives, today=today)
        for a in assessments:
            if a.student.id in muted_ids:
                risk_levels_by_id[a.student.id] = "ok"
            else:
                risk_levels_by_id[a.student.id] = a.level
        # pasif olanlar zaten 'ok' kabul. "Uyarı" kartı (fleet_amber) medium+high
        # sayıyor → ?risk=medium drilldown'u da high'ı kapsamalı (kart=liste).
        _match = {"medium", "high"} if risk_norm == "medium" else {risk_norm}
        students = [
            s for s in students
            if risk_levels_by_id.get(s.id, "ok") in _match
        ]

    total = len(students)
    start = (page - 1) * page_size
    end = start + page_size
    page_students = students[start:end]

    # Sayfa içindekiler için snapshot toplu üret
    snapshots_by_id = {
        s.id: student_snapshot(db, s, today=today) for s in page_students
    }

    # Bugünün görev sayısı (görev-bazlı, tek batch sorgu) — "Bugün X/Y test"
    # yerine "X/Y görev". Yayınlanmış görevler.
    from app.services import gorev_stats
    _page_ids = [s.id for s in page_students]
    _today_by_student: dict[int, list] = {}
    if _page_ids:
        _all_today = (
            db.query(Task)
            .options(joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject))
            .filter(Task.student_id.in_(_page_ids), Task.date == today, Task.is_draft.is_(False))
            .all()
        )
        for _t in _all_today:
            _today_by_student.setdefault(_t.student_id, []).append(_t)

    _wrank = {"red": 0, "amber": 1, "green": 2}
    items: list[TeacherStudentListItem] = []
    for s in page_students:
        sn = snapshots_by_id.get(s.id)
        week_pct = (
            (sn.week.completed / sn.week.planned)
            if sn and sn.week.planned > 0 else 0.0
        )
        # Satırın NEDEN kırmızı/sarı olduğunu göster: en kötü uyarının başlığı
        ww_title = ww_detail = None
        if sn and sn.warnings:
            ww = min(sn.warnings, key=lambda x: _wrank.get(x.level, 9))
            ww_title, ww_detail = ww.title, ww.detail
        _g = gorev_stats.summarize(_today_by_student.get(s.id, []))
        items.append(TeacherStudentListItem(
            id=s.id,
            full_name=s.full_name,
            email=s.email,
            grade_level=s.grade_level,
            is_active=bool(s.is_active),
            last_login_at=s.last_login_at,
            worst_warning_level=(sn.worst_warning_level if sn else "green"),
            worst_warning_title=ww_title,
            worst_warning_detail=ww_detail,
            today_planned=(sn.today.planned if sn else 0),
            today_completed=(sn.today.completed if sn else 0),
            today_gorev_total=_g.gorev_total,
            today_gorev_done=_g.gorev_done,
            week_pct=week_pct,
            has_pending_request=_has_pending_request_for_student(db, s.id),
        ))

    return TeacherStudentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=end < total,
    )


# =============================================================================
# 3) GET /teacher/students/{id} — 360 paneli
# =============================================================================


def _task_frac(t: Task) -> float:
    """Görev tamamlama oranı (0..1) — manşet/Durum Özeti için.

    COMPLETED görev → 1.0 (tip fark etmez; Diğer/Video/Özet/Tekrar dahil).
    Sayısal görev → çözülen/planlanan soru (max 1). Kalemsiz etkinlik
    tamamlanmamışsa 0. "Diğer" görevi tamamlanınca tamamlamaya SAYILIR.
    """
    if t.status == TaskStatus.COMPLETED:
        return 1.0
    p = sum(int(it.planned_count or 0) for it in t.book_items)
    if p <= 0:
        return 0.0
    c = sum(int(it.completed_count or 0) for it in t.book_items)
    return min(1.0, c / p)


def _task_based_summary(tasks: list[Task]) -> tuple[int, int, float]:
    """(tamamlanan_görev, toplam_görev, oran 0..1) — görev-bazlı (etkinlik dahil)."""
    total = len(tasks)
    if total == 0:
        return 0, 0, 0.0
    fracs = [_task_frac(t) for t in tasks]
    done = sum(1 for f in fracs if f >= 1.0)
    return done, total, sum(fracs) / total


def _build_gorev_breakdown(g):
    """gorev_stats.GorevSummary → API GorevBreakdown (360/gün/hafta ortak)."""
    from app.routes.api_v2.schemas.teacher import (
        GorevBreakdown, GorevSubjectItem, GorevDenemeItem,
    )
    return GorevBreakdown(
        gorev_total=g.gorev_total, gorev_done=g.gorev_done, gorev_pct=g.gorev_pct,
        test_planned=g.test_planned, test_completed=g.test_completed,
        deneme_planned=g.deneme_planned, deneme_completed=g.deneme_completed,
        deneme_count=g.cat_total["deneme"] + g.cat_total["tam_deneme"],
        deneme_done=g.cat_done["deneme"] + g.cat_done["tam_deneme"],
        etkinlik_count=g.cat_total["etkinlik"], etkinlik_done=g.cat_done["etkinlik"],
        subjects=[
            GorevSubjectItem(
                subject_name=x.subject_name, gorev_total=x.gorev_total,
                gorev_done=x.gorev_done, pct=x.pct,
                test_planned=x.test_planned, test_completed=x.test_completed,
            ) for x in g.subjects
        ],
        denemeler=[
            GorevDenemeItem(
                title=d.title, subject=d.subject_name, category=d.category,
                planned=d.planned, completed=d.completed, done=d.done,
            ) for d in g.denemeler
        ],
    )


@router.get(
    "/students/{student_id}",
    response_model=TeacherStudentDetailResponse,
)
def teacher_student_detail_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenci 360 — profil + program özeti + uyarılar.

    Sahiplik 404: başkasının öğrencisi veya cross-tenant erişim.
    """
    from app.routes.teacher_program import _resolve_week_anchor
    from app.routes.api_v2.schemas.teacher import StudentActivePhase

    student = _get_owned_student(db, student_id, user.id)
    today = date.today()
    sn = student_snapshot(db, student, today=today)

    # GÖREV-BAZLI Durum Özeti (etkinlik/"Diğer" görevleri de sayılır).
    # Eski today_pct/week_pct soru-bazlıydı → tamamlanan "Diğer" görev manşete
    # girmiyordu ("Bugün 0/6 görev %0" yanlışı). Yayınlanmış (taslak olmayan)
    # görevler üzerinden, hafta-görünümü manşetiyle aynı _task_frac mantığı.
    _week_start = today - timedelta(days=6)
    _task_opts = joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject)
    _today_tasks = (
        db.query(Task).options(_task_opts)
        .filter(Task.student_id == student.id, Task.date == today, Task.is_draft.is_(False))
        .all()
    )
    _week_tasks = (
        db.query(Task).options(_task_opts)
        .filter(Task.student_id == student.id, Task.date >= _week_start,
                Task.date <= today, Task.is_draft.is_(False))
        .all()
    )
    # Görev/test/deneme ayrımlı özet (tek merkez: gorev_stats)
    from app.services import gorev_stats
    _today_g = gorev_stats.summarize(_today_tasks)
    _week_g = gorev_stats.summarize(_week_tasks)
    today_done, today_tasks_total = _today_g.gorev_done, _today_g.gorev_total
    today_task_pct = _today_g.gorev_pct / 100
    week_done, week_tasks_total = _week_g.gorev_done, _week_g.gorev_total
    week_task_pct = _week_g.gorev_pct / 100

    # Soru-bazlı (hacim) — geriye uyum için korunur; "8 test" gibi sayılar bunu kullanır.
    today_pct = (sn.today.completed / sn.today.planned) if sn.today.planned > 0 else 0.0
    week_pct = (sn.week.completed / sn.week.planned) if sn.week.planned > 0 else 0.0
    warnings_text = [f"{w.title}: {w.detail}" for w in sn.warnings]

    # Uyarı kodu → kanıt sayfası (koç tek tıkla detaya gitsin)
    from app.routes.api_v2.schemas.teacher import WarningItem
    _WARN_LINK = {
        "today_no_tick": ("day", "Bugünü incele"),
        "yesterday_no_tick": ("day", "Günü incele"),
        "inactive_3d": ("week", "Haftalık planı incele"),
        "weekly_miss": ("week", "Haftalık planı incele"),
        "weekly_zero": ("week", "Haftalık planı incele"),
        "projection_shortfall": ("dna", "Çalışma analizini gör"),
    }
    warning_items: list[WarningItem] = []
    for w in sn.warnings:
        suffix, label = _WARN_LINK.get(w.code, ("week", "Programı incele"))
        warning_items.append(WarningItem(
            level=w.level, code=w.code, title=w.title, detail=w.detail,
            link=f"/teacher/students/{student.id}/{suffix}", link_label=label,
        ))

    # Paket 3.5b — anchor durumu + aktif dönem rozeti
    week_anchor = _resolve_week_anchor(db, student)
    anchor_is_manual = student.program_anchor_date is not None
    # Aktif (explicit) program varsa anchor fallback'i kullanılmıyor → UI kartı gizler.
    from app.services.weekly_program_service import get_active_program
    has_active_program = get_active_program(db, student_id=student.id, today=today) is not None

    active_phase: StudentActivePhase | None = None
    if student.academic_year is not None:
        ph = student.academic_year.active_phase_on(today)
        if ph is not None:
            active_phase = StudentActivePhase(
                kind=ph.kind.value if ph.kind else "regular",
                kind_label=ph.kind_label,
                kind_badge=ph.kind_badge,
                name=ph.name,
                start_date=ph.start_date.isoformat(),
                end_date=ph.end_date.isoformat(),
            )

    return TeacherStudentDetailResponse(
        student=_build_brief_profile(student),
        program_summary=StudentProgramSummary(
            today_planned=sn.today.planned,
            today_completed=sn.today.completed,
            today_pct=today_pct,
            week_planned=sn.week.planned,
            week_completed=sn.week.completed,
            week_pct=week_pct,
            consistency_7d=float(sn.consistency_7d),
            hit_rate_7d=float(sn.hit_rate_7d),
            rate_7d=float(sn.rate_7d),
            # Görev-bazlı (etkinlik dahil) — Durum Özeti "X/Y görev" için
            today_tasks_total=today_tasks_total,
            today_tasks_done=today_done,
            today_task_pct=today_task_pct,
            week_tasks_total=week_tasks_total,
            week_tasks_done=week_done,
            week_task_pct=week_task_pct,
        ),
        worst_warning_level=sn.worst_warning_level,
        warnings=warnings_text,
        warning_items=warning_items,
        pending_request_count=_pending_request_count_for_student(db, student.id),
        active_phase=active_phase,
        week_anchor=week_anchor.isoformat() if week_anchor else None,
        anchor_is_manual=anchor_is_manual,
        has_active_program=has_active_program,
        gorev_today=_build_gorev_breakdown(_today_g),
        gorev_week=_build_gorev_breakdown(_week_g),
    )


# =============================================================================
# POST /students/{id}/set-week-anchor — Koçluk takvimi anchor edit
# =============================================================================


@router.post(
    "/students/{student_id}/set-week-anchor",
    response_model=MutationResponse[dict],
)
def teacher_set_week_anchor_v2(
    student_id: int,
    body: SetWeekAnchorBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Manuel hafta anchor'ı set et veya temizle (Jinja teacher_program.py:518-552 parite).

    `anchor="clear"` ile manuel anchor silinir → fallback (en eski Task tarihi).
    Aksi halde ISO YYYY-MM-DD parse edilip `program_anchor_date` set edilir.
    """
    student = _get_owned_student(db, student_id, user.id)
    raw = (body.anchor or "").strip()
    if raw.lower() == "clear":
        student.program_anchor_date = None
    else:
        try:
            student.program_anchor_date = date.fromisoformat(raw)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "invalid_anchor_date",
                    "message": "Geçersiz tarih. YYYY-MM-DD veya 'clear' bekleniyor.",
                },
            )
    db.commit()
    db.refresh(student)
    new_anchor = student.program_anchor_date
    return MutationResponse[dict](
        data={
            "anchor": new_anchor.isoformat() if new_anchor else None,
            "is_manual": new_anchor is not None,
        },
        invalidate=[
            f"teacher:{user.id}:students:{student.id}",
            f"teacher:{user.id}:students:{student.id}:week",
        ],
    )


# =============================================================================
# KP4a — Deneme sınavı sonuçları (Akademik Çıktı / Deneme Takibi)
# =============================================================================


def _exam_section_options() -> list[ExamSectionOption]:
    return [
        ExamSectionOption(value=sec.value, label=EXAM_SECTION_LABELS[sec])
        for sec in ExamSection
    ]


def _get_owned_exam(db: Session, exam_id: int, teacher_id: int) -> ExamResult:
    """Öğretmenin kendi öğrencisine ait deneme kaydını yükle, değilse 404."""
    exam = (
        db.query(ExamResult)
        .join(User, User.id == ExamResult.student_id)
        .filter(ExamResult.id == exam_id, User.teacher_id == teacher_id)
        .first()
    )
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "exam_not_found",
                "message": "Deneme kaydı bulunamadı.",
            },
        )
    return exam


def _build_exam_row(exam: ExamResult, *, created_by_name: str | None) -> ExamResultRow:
    subjects: list[ExamSubjectRow] = []
    if exam.subject_nets:
        try:
            for item in json.loads(exam.subject_nets):
                subjects.append(
                    ExamSubjectRow(
                        name=str(item.get("name", "")),
                        correct=int(item.get("correct", 0)),
                        wrong=int(item.get("wrong", 0)),
                        blank=int(item.get("blank", 0)),
                        net=float(item.get("net", 0.0)),
                    )
                )
        except (ValueError, TypeError, AttributeError):
            subjects = []
    return ExamResultRow(
        id=exam.id,
        title=exam.title,
        exam_date=exam.exam_date.isoformat(),
        section=exam.section.value,
        section_label=EXAM_SECTION_LABELS[exam.section],
        total_correct=exam.total_correct,
        total_wrong=exam.total_wrong,
        total_blank=exam.total_blank,
        total_questions=exam.total_correct + exam.total_wrong + exam.total_blank,
        net=exam.net,
        subjects=subjects,
        note=exam.note,
        created_at=exam.created_at,
        created_by_name=created_by_name,
    )


def _validate_and_compute_exam(body: "ExamCreateBody") -> dict:
    """ExamCreateBody doğrula + net/toplam hesapla — create + update ortak kullanır.

    Hata → HTTPException (422). Dönüş: title / exam_date / section / total_* / net /
    subject_payload (ders kırılımı varsa toplamlar ondan türetilir).
    """
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "title_required",
                    "message": "Deneme adı zorunlu."},
        )
    try:
        exam_date = date.fromisoformat((body.exam_date or "").strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_date",
                    "message": "Geçersiz tarih. YYYY-MM-DD bekleniyor."},
        )
    try:
        section = ExamSection(body.section)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_section",
                    "message": "Geçersiz sınav türü."},
        )

    subject_payload: list[dict] = []
    if body.subjects:
        tc = tw = tb = 0
        for subj in body.subjects:
            name = (subj.name or "").strip()
            if not name:
                continue
            c = max(int(subj.correct), 0)
            w = max(int(subj.wrong), 0)
            b = max(int(subj.blank), 0)
            tc += c
            tw += w
            tb += b
            subject_payload.append({
                "name": name, "correct": c, "wrong": w, "blank": b,
                "net": compute_net(c, w, section),
            })
        total_correct, total_wrong, total_blank = tc, tw, tb
    else:
        total_correct = max(int(body.total_correct), 0)
        total_wrong = max(int(body.total_wrong), 0)
        total_blank = max(int(body.total_blank), 0)

    if total_correct + total_wrong + total_blank <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "empty_exam",
                    "message": "En az bir doğru/yanlış/boş değeri girilmeli."},
        )

    return {
        "title": title[:200],
        "exam_date": exam_date,
        "section": section,
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "total_blank": total_blank,
        "net": compute_net(total_correct, total_wrong, section),
        "subject_payload": subject_payload,
    }


@router.get(
    "/students/{student_id}/topic-performance",
    response_model=TopicPerformanceResponse,
)
def teacher_student_topic_performance_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrencinin ders → konu test performansı (çözülen test + D/Y + doğruluk).

    Sahiplik 404. DENEME kitapları hariç (deneme ayrı yüzeyde).
    """
    student = _get_owned_student(db, student_id, user.id)
    from app.services.topic_performance import compute_topic_performance
    return build_topic_performance_response(
        compute_topic_performance(db, student.id)
    )


@router.get(
    "/students/{student_id}/exams",
    response_model=StudentExamListResponse,
)
def teacher_student_exams_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrencinin deneme sonuçları — özet (ortalama/en iyi/gelişim) + liste.

    Sahiplik 404: başkasının öğrencisi veya cross-tenant erişim.
    """
    student = _get_owned_student(db, student_id, user.id)
    exams = (
        db.query(ExamResult)
        .filter(ExamResult.student_id == student.id)
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc())
        .all()
    )
    # created_by isimleri (tek sorguda)
    creator_ids = {e.created_by_id for e in exams if e.created_by_id}
    names: dict[int, str] = {}
    if creator_ids:
        for uid, full_name in (
            db.query(User.id, User.full_name)
            .filter(User.id.in_(creator_ids))
            .all()
        ):
            names[uid] = full_name

    rows = [
        _build_exam_row(e, created_by_name=names.get(e.created_by_id) if e.created_by_id else None)
        for e in exams
    ]

    nets = [e.net for e in exams]
    count = len(nets)
    # exams DESC sıralı → ilk eleman en yeni, son eleman en eski
    last_net = nets[0] if nets else None
    first_net = nets[-1] if nets else None
    summary = ExamListSummary(
        count=count,
        avg_net=round(sum(nets) / count, 2) if count else 0.0,
        best_net=round(max(nets), 2) if nets else 0.0,
        last_net=last_net,
        first_net=first_net,
        trend_delta=round(last_net - first_net, 2) if (count >= 2) else None,
    )
    return StudentExamListResponse(
        summary=summary,
        rows=rows,
        section_options=_exam_section_options(),
    )


@router.post(
    "/students/{student_id}/exams",
    response_model=MutationResponse[ExamResultRow],
)
def teacher_create_exam_v2(
    student_id: int,
    body: ExamCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenciye deneme sonucu ekle. Net sınav türüne göre hesaplanır
    (LGS: D-Y/3, YKS: D-Y/4). Ders kırılımı verilirse toplamlar ondan türetilir.
    """
    student = _get_owned_student(db, student_id, user.id)
    f = _validate_and_compute_exam(body)
    exam = ExamResult(
        student_id=student.id,
        created_by_id=user.id,
        title=f["title"],
        exam_date=f["exam_date"],
        section=f["section"],
        total_correct=f["total_correct"],
        total_wrong=f["total_wrong"],
        total_blank=f["total_blank"],
        net=f["net"],
        subject_nets=(
            json.dumps(f["subject_payload"], ensure_ascii=False)
            if f["subject_payload"] else None
        ),
        note=(body.note or "").strip()[:500] or None,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return MutationResponse[ExamResultRow](
        data=_build_exam_row(exam, created_by_name=user.full_name),
        invalidate=[
            f"teacher:{user.id}:students:{student.id}:exams",
            f"teacher:{user.id}:students:{student.id}",
        ],
    )


@router.post(
    "/exams/{exam_id}",
    response_model=MutationResponse[ExamResultRow],
)
def teacher_update_exam_v2(
    exam_id: int,
    body: ExamCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Deneme kaydını DÜZENLE (hatalı giriş düzeltme). Sahiplik 404.

    Net/toplamlar create ile aynı kuralla yeniden hesaplanır. created_by_id
    DEĞİŞMEZ (kaydı kim girdiyse o kalır)."""
    exam = _get_owned_exam(db, exam_id, user.id)
    f = _validate_and_compute_exam(body)
    exam.title = f["title"]
    exam.exam_date = f["exam_date"]
    exam.section = f["section"]
    exam.total_correct = f["total_correct"]
    exam.total_wrong = f["total_wrong"]
    exam.total_blank = f["total_blank"]
    exam.net = f["net"]
    exam.subject_nets = (
        json.dumps(f["subject_payload"], ensure_ascii=False)
        if f["subject_payload"] else None
    )
    exam.note = (body.note or "").strip()[:500] or None
    db.commit()
    db.refresh(exam)
    creator_name = None
    if exam.created_by_id:
        creator = db.get(User, exam.created_by_id)
        creator_name = creator.full_name if creator else None
    return MutationResponse[ExamResultRow](
        data=_build_exam_row(exam, created_by_name=creator_name),
        invalidate=[
            f"teacher:{user.id}:students:{exam.student_id}:exams",
            f"teacher:{user.id}:students:{exam.student_id}",
        ],
    )


@router.delete(
    "/exams/{exam_id}",
    response_model=MutationResponse[dict],
)
def teacher_delete_exam_v2(
    exam_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Deneme kaydını sil. Sahiplik 404."""
    exam = _get_owned_exam(db, exam_id, user.id)
    student_id = exam.student_id
    db.delete(exam)
    db.commit()
    return MutationResponse[dict](
        data={"deleted": True, "id": exam_id},
        invalidate=[
            f"teacher:{user.id}:students:{student_id}:exams",
            f"teacher:{user.id}:students:{student_id}",
        ],
    )


# =============================================================================
# KS1 — Koçluk seansı / değerlendirme kaydı
# =============================================================================


def _compute_session_prefill(db: Session, student: User) -> dict:
    """Seans formu 'Bu haftanın verisi' otomatik paneli (Kova 1).

    Mevcut analitik servislerden hesaplanır; create'te auto_snapshot olarak
    kaydedilir (sonradan veri değişse de o günkü form korunur).
    """
    from app.services import analytics as an

    today = date.today()
    week = an.week_stats_for(db, student.id, today)
    pct = int(round(100 * week.completed / week.planned)) if week.planned > 0 else None
    # "test/gün hız" → yalnız soru bankası (deneme test'e karışmaz; tutarlılık)
    rate = round(an.recent_rate(db, student.id, today, 7, tests_only=True), 1)

    behind = []
    for s in an.subject_breakdown(db, student.id):
        if s["total"] > 0 and s["percent_done"] < 100:
            behind.append({"name": s["name"], "percent_done": s["percent_done"]})
    behind.sort(key=lambda x: x["percent_done"])
    behind = behind[:3]

    latest_exam = None
    exam_count = (
        db.query(func.count(ExamResult.id))
        .filter(ExamResult.student_id == student.id).scalar() or 0
    )
    last = (
        db.query(ExamResult)
        .filter(ExamResult.student_id == student.id)
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc())
        .first()
    )
    if last is not None:
        total_q = last.total_correct + last.total_wrong + last.total_blank
        latest_exam = {
            "title": last.title,
            "exam_date": last.exam_date.isoformat(),
            "section_label": EXAM_SECTION_LABELS[last.section],
            "net": last.net,
            "net_pct": int(round(100 * last.net / total_q)) if total_q > 0 else None,
        }

    return {
        "week_planned": week.planned,
        "week_completed": week.completed,
        "week_completion_pct": pct,
        "recent_rate": rate,
        "behind_subjects": behind,
        "latest_exam": latest_exam,
        "exam_count": int(exam_count),
    }


def _get_owned_session(db: Session, session_id: int, teacher_id: int) -> CoachingSession:
    s = (
        db.query(CoachingSession)
        .join(User, User.id == CoachingSession.student_id)
        .filter(CoachingSession.id == session_id, User.teacher_id == teacher_id)
        .first()
    )
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "session_not_found",
                    "message": "Seans kaydı bulunamadı."},
        )
    return s


def _build_session_row(s: CoachingSession) -> CoachingSessionRow:
    tags: list[str] = []
    if s.tags:
        try:
            tags = [str(t) for t in json.loads(s.tags)]
        except (ValueError, TypeError):
            tags = []
    snap = None
    if s.auto_snapshot:
        try:
            snap = json.loads(s.auto_snapshot)
        except (ValueError, TypeError):
            snap = None
    return CoachingSessionRow(
        id=s.id,
        session_date=s.session_date.isoformat(),
        status=s.status.value,
        status_label=COACHING_STATUS_LABELS[s.status],
        duration_min=s.duration_min,
        channel=s.channel.value if s.channel else None,
        channel_label=COACHING_CHANNEL_LABELS[s.channel] if s.channel else None,
        agenda=s.agenda,
        next_change=s.next_change,
        coach_note=s.coach_note,
        mood=s.mood,
        tags=tags,
        auto_snapshot=snap,
        capture_source=s.capture_source.value,
        created_at=s.created_at,
    )


def _validate_session_body(body: CoachingSessionCreateBody) -> tuple[date, str]:
    agenda = (body.agenda or "").strip()
    if not agenda:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "agenda_required",
                    "message": "Gündem (konuşulacaklar) zorunlu."},
        )
    try:
        sd = date.fromisoformat((body.session_date or "").strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_date",
                    "message": "Geçersiz tarih. YYYY-MM-DD bekleniyor."},
        )
    if body.mood is not None and not (1 <= body.mood <= 5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_mood",
                    "message": "Ruh hali 1-5 arası olmalı."},
        )
    return sd, agenda


def _apply_session_body(s: CoachingSession, body: CoachingSessionCreateBody, sd: date, agenda: str) -> None:
    s.session_date = sd
    s.status = CoachingSessionStatus(body.status)
    s.duration_min = body.duration_min
    s.channel = CoachingChannel(body.channel) if body.channel else None
    s.agenda = agenda[:5000]
    s.next_change = (body.next_change or "").strip()[:2000] or None
    s.coach_note = (body.coach_note or "").strip()[:8000] or None
    s.mood = body.mood
    clean_tags = [t.strip() for t in (body.tags or []) if t and t.strip()]
    s.tags = json.dumps(clean_tags, ensure_ascii=False) if clean_tags else None
    if body.capture_source:
        s.capture_source = SessionCaptureSource(body.capture_source)


@router.get("/students/{student_id}/sessions", response_model=StudentSessionListResponse)
def teacher_student_sessions_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrencinin koçluk seansları — özet (durum sayıları) + zaman çizelgesi."""
    student = _get_owned_student(db, student_id, user.id)
    rows = (
        db.query(CoachingSession)
        .filter(CoachingSession.student_id == student.id)
        .order_by(CoachingSession.session_date.desc(), CoachingSession.id.desc())
        .all()
    )
    counts = {st: 0 for st in CoachingSessionStatus}
    for r in rows:
        counts[r.status] += 1
    last_date = rows[0].session_date.isoformat() if rows else None
    return StudentSessionListResponse(
        summary=CoachingSessionSummary(
            total=len(rows),
            done_count=counts[CoachingSessionStatus.DONE],
            postponed_count=counts[CoachingSessionStatus.POSTPONED],
            cancelled_count=counts[CoachingSessionStatus.CANCELLED],
            no_show_count=counts[CoachingSessionStatus.NO_SHOW],
            last_session_date=last_date,
        ),
        rows=[_build_session_row(r) for r in rows],
    )


@router.get("/students/{student_id}/sessions/prefill", response_model=SessionPrefillResponse)
def teacher_session_prefill_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Seans formu otomatik panel verisi (haftalık tamamlama + hız + zayıf ders + son deneme)."""
    student = _get_owned_student(db, student_id, user.id)
    d = _compute_session_prefill(db, student)
    return SessionPrefillResponse(
        week_planned=d["week_planned"],
        week_completed=d["week_completed"],
        week_completion_pct=d["week_completion_pct"],
        recent_rate=d["recent_rate"],
        behind_subjects=[SessionPrefillSubject(**s) for s in d["behind_subjects"]],
        latest_exam=SessionPrefillExam(**d["latest_exam"]) if d["latest_exam"] else None,
        exam_count=d["exam_count"],
    )


@router.post("/students/{student_id}/sessions", response_model=MutationResponse[CoachingSessionRow])
def teacher_create_session_v2(
    student_id: int,
    body: CoachingSessionCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Seans kaydı oluştur. Otomatik snapshot (Kova 1) seans anında hesaplanıp saklanır."""
    student = _get_owned_student(db, student_id, user.id)
    sd, agenda = _validate_session_body(body)
    s = CoachingSession(coach_id=user.id, student_id=student.id)
    _apply_session_body(s, body, sd, agenda)
    s.auto_snapshot = json.dumps(_compute_session_prefill(db, student), ensure_ascii=False)
    db.add(s)
    _mark_insight_stale(db, student.id)  # yeni seans → içgörü cache bayatlar (AI çağrısı yok)
    db.commit()
    db.refresh(s)
    return MutationResponse[CoachingSessionRow](
        data=_build_session_row(s),
        invalidate=[
            f"teacher:{user.id}:students:{student.id}:sessions",
            f"teacher:{user.id}:students:{student.id}",
        ],
    )


@router.get("/sessions/{session_id}", response_model=CoachingSessionRow)
def teacher_get_session_v2(
    session_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    return _build_session_row(_get_owned_session(db, session_id, user.id))


@router.post("/sessions/{session_id}", response_model=MutationResponse[CoachingSessionRow])
def teacher_update_session_v2(
    session_id: int,
    body: CoachingSessionCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Seans kaydını düzenle (auto_snapshot dokunulmaz — o günün verisi sabit kalır)."""
    s = _get_owned_session(db, session_id, user.id)
    sd, agenda = _validate_session_body(body)
    _apply_session_body(s, body, sd, agenda)
    _mark_insight_stale(db, s.student_id)  # seans değişti → içgörü cache bayatlar
    db.commit()
    db.refresh(s)
    return MutationResponse[CoachingSessionRow](
        data=_build_session_row(s),
        invalidate=[
            f"teacher:{user.id}:students:{s.student_id}:sessions",
            f"teacher:{user.id}:students:{s.student_id}",
        ],
    )


@router.delete("/sessions/{session_id}", response_model=MutationResponse[dict])
def teacher_delete_session_v2(
    session_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    s = _get_owned_session(db, session_id, user.id)
    student_id = s.student_id
    db.delete(s)
    _mark_insight_stale(db, student_id)  # seans silindi → içgörü cache bayatlar
    db.commit()
    return MutationResponse[dict](
        data={"deleted": True, "id": session_id},
        invalidate=[
            f"teacher:{user.id}:students:{student_id}:sessions",
            f"teacher:{user.id}:students:{student_id}",
        ],
    )


# =============================================================================
# KS3a — AI yakalama (foto → metin)
# =============================================================================


def _require_ai_premium(db: Session, user: User) -> None:
    """AI premium kapısı — paylaşılan dependencies.assert_ai_premium'e delege eder
    (kitap-AI önerisiyle aynı kapı; tutarlılık için tek kaynak)."""
    from app.routes.api_v2.dependencies import assert_ai_premium
    assert_ai_premium(db, user)


@router.get("/ai-consent", response_model=AiConsentResponse)
def teacher_ai_consent_get_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Koçun AI yakalama (ses/foto→metin) rıza durumu + ücretli paket erişimi."""
    from app.services.plans import ai_premium_allowed, effective_plan_for_user
    at = user.ai_capture_consent_at
    return AiConsentResponse(
        consented=at is not None,
        consent_at=at.isoformat() if at else None,
        ai_premium=ai_premium_allowed(db, user),
        plan_code=effective_plan_for_user(db, user),
    )


@router.post("/ai-consent", response_model=MutationResponse[AiConsentResponse])
def teacher_ai_consent_set_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """AI yakalama açık rızası ver (AI işleme + yurt dışı alt-işleyen onayı)."""
    from app.services.plans import ai_premium_allowed, effective_plan_for_user
    if user.ai_capture_consent_at is None:
        user.ai_capture_consent_at = datetime.now(timezone.utc)
        db.add(user)
        db.commit()
        db.refresh(user)
    at = user.ai_capture_consent_at
    return MutationResponse[AiConsentResponse](
        data=AiConsentResponse(
            consented=True, consent_at=at.isoformat() if at else None,
            ai_premium=ai_premium_allowed(db, user),
            plan_code=effective_plan_for_user(db, user),
        ),
        invalidate=["teacher:me:ai-consent"],
    )


@router.post("/students/{student_id}/sessions/parse-photo", response_model=SessionDraftResponse)
def teacher_parse_session_photo_v2(
    student_id: int,
    body: ParsePhotoBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Kâğıt görüşme formu fotoğrafı → seans form taslağı (Claude vision).

    GİZLİLİK: Görsel SAKLANMAZ — yalnız bu çağrıda işlenir. Sonuç taslaktır;
    koç düzenleyip /sessions ile kaydeder. Rıza zorunlu + kredi tüketir.
    """
    from app.services.ai_session_capture import parse_session_photo
    from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
    from app.models import UsageKind
    from app.services.credits import CreditBlocked, CreditOwner, consume_credits

    _get_owned_student(db, student_id, user.id)  # sahiplik 404
    _require_ai_premium(db, user)  # ücretli paket kapısı

    if user.ai_capture_consent_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "consent_required",
                    "message": "AI yakalama için önce açık rıza vermelisiniz."},
        )

    img = (body.image_base64 or "").strip()
    if not img:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "image_required", "message": "Görsel boş."},
        )
    # ~7MB base64 üst sınırı (kabaca)
    if len(img) > 9_500_000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "image_too_large", "message": "Görsel çok büyük (max ~7MB)."},
        )
    if body.media_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_media_type",
                    "message": "Desteklenmeyen görsel türü (jpeg/png/webp)."},
        )

    owner = CreditOwner.for_user(user)
    draft: dict | None = None
    try:
        with consume_credits(
            db, owner=owner, kind=UsageKind.AI_SESSION_CAPTURE,
            actor_user_id=user.id, autocommit=False,
        ) as ctx:
            draft = parse_session_photo(img, body.media_type)
            ctx.set_metadata({"student_id": student_id, "source": "photo"})
    except CreditBlocked as e:
        db.rollback()
        raise _ai_credit_exhausted_error(user, e.message)
    except AIInvalidResponse as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "photo_unreadable",
                    "message": f"Fotoğraf okunamadı: {e}"},
        )
    except AIServiceUnavailable as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "upstream_unavailable", "code": "ai_unavailable",
                    "message": f"AI servisi şu an kullanılamıyor: {e}"},
        )
    db.commit()  # kredi kaydını sabitle
    return SessionDraftResponse(**draft)


@router.post("/students/{student_id}/sessions/transcribe", response_model=TranscribeResponse)
def teacher_transcribe_v2(
    student_id: int,
    body: ParseVoiceBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Sesli dikte → DÜZ METİN (alan doldurma için). Gemini saf transkripsiyon.

    GİZLİLİK: Ses SAKLANMAZ — yalnız bu çağrıda işlenir. Sonuç düz metindir; koç
    ilgili form alanına ekler. Rıza zorunlu + kredi tüketir (ücretli paket).
    """
    from app.services.ai_session_capture import ALLOWED_AUDIO, transcribe_audio
    from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
    from app.models import UsageKind
    from app.services.credits import CreditBlocked, CreditOwner, consume_credits

    _get_owned_student(db, student_id, user.id)  # sahiplik 404
    _require_ai_premium(db, user)  # ücretli paket kapısı

    if user.ai_capture_consent_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "consent_required",
                    "message": "AI yakalama için önce açık rıza vermelisiniz."},
        )

    audio = (body.audio_base64 or "").strip()
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "audio_required", "message": "Ses kaydı boş."},
        )
    if len(audio) > 18_000_000:  # ~13MB ham ses
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "audio_too_large", "message": "Ses kaydı çok uzun/büyük (max ~13MB)."},
        )
    if body.media_type not in ALLOWED_AUDIO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_media_type",
                    "message": "Desteklenmeyen ses türü (webm/mp4/ogg/mp3/wav)."},
        )

    owner = CreditOwner.for_user(user)
    text: str = ""
    try:
        with consume_credits(
            db, owner=owner, kind=UsageKind.AI_TRANSCRIBE,
            actor_user_id=user.id, autocommit=False,
        ) as ctx:
            text = transcribe_audio(audio, body.media_type)
            ctx.set_metadata({"student_id": student_id, "source": "dictation"})
    except CreditBlocked as e:
        db.rollback()
        raise _ai_credit_exhausted_error(user, e.message)
    except AIInvalidResponse as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "voice_unreadable",
                    "message": f"Ses anlaşılamadı: {e}"},
        )
    except AIServiceUnavailable as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "upstream_unavailable", "code": "ai_unavailable",
                    "message": f"AI servisi şu an kullanılamıyor: {e}"},
        )
    db.commit()  # kredi kaydını sabitle
    return TranscribeResponse(text=text)


def _insight_to_response(ci: CoachingInsight) -> CoachingInsightResponse:
    def _load(v: str | None) -> list[str]:
        if not v:
            return []
        try:
            return [str(x) for x in json.loads(v)]
        except (ValueError, TypeError):
            return []
    return CoachingInsightResponse(
        summary=ci.summary,
        agenda_suggestions=_load(ci.agenda_suggestions),
        psychological_tips=_load(ci.psychological_tips),
        watch_outs=_load(ci.watch_outs),
        based_on_sessions=ci.based_on_sessions,
        generated_at=ci.generated_at.isoformat() if ci.generated_at else None,
    )


def _mark_insight_stale(db: Session, student_id: int) -> None:
    """Seans değişince cache'lenmiş içgörüyü bayatla (AI çağrısı YOK — sadece bayrak)."""
    ci = db.query(CoachingInsight).filter(CoachingInsight.student_id == student_id).first()
    if ci is not None and not ci.is_stale:
        ci.is_stale = True


@router.get("/students/{student_id}/coaching-insight", response_model=CoachingInsightCacheResponse)
def teacher_coaching_insight_get_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Cache'lenmiş AI koçluk içgörüsünü oku — KREDİ DÜŞMEZ. None = henüz üretilmemiş.

    Kredi yalnız POST (üret/yenile) ile düşer. Bu salt-okuma.
    """
    _get_owned_student(db, student_id, user.id)  # sahiplik 404
    ci = db.query(CoachingInsight).filter(CoachingInsight.student_id == student_id).first()
    if ci is None:
        return CoachingInsightCacheResponse(insight=None, is_stale=False)
    return CoachingInsightCacheResponse(insight=_insight_to_response(ci), is_stale=ci.is_stale)


@router.post("/students/{student_id}/coaching-insight", response_model=CoachingInsightCacheResponse)
def teacher_coaching_insight_generate_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Seans geçmişi + akademik durum → AI koçluk içgörüsü ÜRET/YENİLE (KS4).

    KREDİ DÜŞER (her çağrıda yeni Claude isteği). Sonuç DB'ye cache'lenir; sonraki
    görüntülemeler GET ile ücretsiz okunur. Rıza zorunlu + en az 1 seans gerekir.
    """
    from app.services.ai_coaching_insight import generate_coaching_insight
    from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
    from app.models import UsageKind
    from app.services.credits import CreditBlocked, CreditOwner, consume_credits

    student = _get_owned_student(db, student_id, user.id)  # sahiplik 404
    _require_ai_premium(db, user)  # ücretli paket kapısı

    if user.ai_capture_consent_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "consent_required",
                    "message": "AI özellikleri için önce açık rıza vermelisiniz."},
        )

    rows = (
        db.query(CoachingSession)
        .filter(CoachingSession.student_id == student.id)
        .order_by(CoachingSession.session_date.desc(), CoachingSession.id.desc())
        .limit(8)
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "not_enough_data",
                    "message": "İçgörü için en az bir seans kaydı gerekir."},
        )

    sessions_data: list[dict] = []
    for r in rows:
        tags: list[str] = []
        if r.tags:
            try:
                tags = [str(t) for t in json.loads(r.tags)]
            except (ValueError, TypeError):
                tags = []
        sessions_data.append({
            "session_date": r.session_date.isoformat(),
            "status_label": COACHING_STATUS_LABELS[r.status],
            "agenda": r.agenda,
            "coach_note": r.coach_note,
            "next_change": r.next_change,
            "mood": r.mood,
            "tags": tags,
        })
    academic = _compute_session_prefill(db, student)

    owner = CreditOwner.for_user(user)
    insight: dict | None = None
    try:
        with consume_credits(
            db, owner=owner, kind=UsageKind.AI_COACHING_INSIGHT,
            actor_user_id=user.id, autocommit=False,
        ) as ctx:
            insight = generate_coaching_insight(student.full_name, sessions_data, academic)
            ctx.set_metadata({"student_id": student_id, "sessions": len(rows)})
    except CreditBlocked as e:
        db.rollback()
        raise _ai_credit_exhausted_error(user, e.message)
    except AIInvalidResponse as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "insight_unreadable",
                    "message": f"İçgörü üretilemedi: {e}"},
        )
    except AIServiceUnavailable as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "upstream_unavailable", "code": "ai_unavailable",
                    "message": f"AI servisi şu an kullanılamıyor: {e}"},
        )

    # Cache'e yaz (öğrenci başına tek kayıt — upsert)
    ci = db.query(CoachingInsight).filter(CoachingInsight.student_id == student.id).first()
    if ci is None:
        ci = CoachingInsight(student_id=student.id)
        db.add(ci)
    ci.generated_by_id = user.id
    ci.summary = insight["summary"]
    ci.agenda_suggestions = json.dumps(insight["agenda_suggestions"], ensure_ascii=False)
    ci.psychological_tips = json.dumps(insight["psychological_tips"], ensure_ascii=False)
    ci.watch_outs = json.dumps(insight["watch_outs"], ensure_ascii=False)
    ci.based_on_sessions = len(rows)
    ci.is_stale = False
    ci.generated_at = datetime.now(timezone.utc)
    db.commit()  # kredi kaydı + cache birlikte sabitlenir
    db.refresh(ci)
    return CoachingInsightCacheResponse(insight=_insight_to_response(ci), is_stale=False)


# =============================================================================
# Bağımsız koç — Paket (plan) görüntüleme + yükseltme
# =============================================================================

# Self-serve yükseltilebilir solo planlar (ücretli). NOT: ödeme entegrasyonu
# (Stripe vb.) ayrı bir iştir; şimdilik yükseltme doğrudan plan değişimidir.
_SOLO_UPGRADE_TARGETS = ("solo_pro", "solo_elite", "solo_unlimited")


def _build_plan_response(db: Session, user: User):
    from app.services.plans import (
        SOLO_ELITE, SOLO_FREE, SOLO_PRO, SOLO_STUDENT_LIMITS, SOLO_UNLIMITED,
        ai_premium_allowed, count_solo_students, effective_plan_for_user,
        get_plan_info, is_paid_plan, is_trial_active, trial_days_left,
    )
    from app.services import pricing

    effective = effective_plan_for_user(db, user)
    info = get_plan_info(effective)
    is_solo = user.institution_id is None
    options: list[TeacherPlanOption] = []
    note: str | None = None

    # Abonelik durumu + öğrenci-sayısına uygun tier fiyatı (uygulama-içi ekran — tek kaynak)
    catalog = pricing.get_pricing_catalog()
    student_count = count_solo_students(db, teacher_id=user.id) if is_solo else 0
    solo_monthly_price = pricing.compute_solo_monthly(student_count) if is_solo else 0
    recommended_plan = pricing.solo_tier_for_students(student_count)["code"] if is_solo else ""
    if not is_solo:
        status = "managed"
    elif is_trial_active(user):
        status = "trialing"
    elif getattr(user, "subscription_status", None) == "past_due":
        status = "past_due"
    elif is_paid_plan(effective):
        status = "active"
    else:
        status = "free"

    if is_solo:
        cur_info = get_plan_info(effective)
        cur_rank = cur_info.tier_rank if cur_info else 0
        for code in (SOLO_FREE, SOLO_PRO, SOLO_ELITE, SOLO_UNLIMITED):
            pi = get_plan_info(code)
            if pi is None:
                continue
            limit = SOLO_STUDENT_LIMITS.get(code, 0)
            options.append(TeacherPlanOption(
                code=code,
                label=pi.label,
                short_description=pi.short_description,
                price_monthly_try=pi.price_monthly_try,
                max_students=(None if limit < 0 else limit),
                tier_rank=pi.tier_rank,
                ai_included=is_paid_plan(code),
                is_current=(code == effective),
                is_upgrade=(code in _SOLO_UPGRADE_TARGETS and pi.tier_rank > cur_rank),
                is_recommended=(code == recommended_plan),
            ))
    else:
        note = "Paketiniz kurumunuz tarafından yönetilir. Yapay zekâ özellikleri " \
               "kurumunuzun planına bağlıdır."

    # Trial bitince geçecek plan — signup'ta seçilen tier veya solo_free
    from app.services.plans import PLAN_CATALOG
    from app.services.credits import PLAN_ALLOCATIONS
    post_trial = user.post_trial_plan if is_solo else None
    post_trial_label = None
    post_trial_credits = None
    if post_trial:
        pti = PLAN_CATALOG.get(post_trial)
        post_trial_label = pti.label if pti else post_trial
        post_trial_credits = PLAN_ALLOCATIONS.get(post_trial)

    # AI kredi durumu — /teacher/plan ilerleme çubuğu için
    ai_used = 0
    ai_alloc = 0
    if is_solo:
        try:
            from app.services.credits import CreditOwner, get_or_create_account
            acc = get_or_create_account(db, owner=CreditOwner.for_user(user))
            ai_used = int(acc.used_credits or 0)
            ai_alloc = int(acc.total_allocated or 0)
        except Exception:
            pass

    # Bekleyen abonelik/ödeme talebi (subscription-request idempotency'siyle aynı sorgu)
    has_pending_sub = False
    if is_solo:
        from app.models.contact_request import ContactRequest
        has_pending_sub = (
            db.query(ContactRequest.id)
            .filter(
                ContactRequest.email == user.email,
                ContactRequest.source == "subscription_request",
                ContactRequest.status == "new",
            )
            .first()
            is not None
        )

    return TeacherPlanResponse(
        plan_code=effective,
        plan_label=info.label if info else effective,
        is_solo=is_solo,
        ai_premium=ai_premium_allowed(db, user),
        trial_active=is_trial_active(user) if is_solo else False,
        trial_days_left=trial_days_left(owner=user) if is_solo else None,
        options=options,
        note=note,
        status=status,
        student_count=student_count,
        solo_monthly_price=solo_monthly_price,
        recommended_plan=recommended_plan,
        annual_paid_months=int(catalog["annual_paid_months"]),
        sales_email=str(catalog.get("contact", {}).get("sales_email", "")),
        subscription_status=user.subscription_status if is_solo else None,
        subscription_period_end=(
            user.subscription_period_end.isoformat()
            if is_solo and user.subscription_period_end else None
        ),
        subscription_cycle=user.subscription_cycle if is_solo else None,
        post_trial_plan=post_trial,
        post_trial_plan_label=post_trial_label,
        post_trial_plan_credits=post_trial_credits,
        ai_credits_used=ai_used,
        ai_credits_allocated=ai_alloc,
        has_pending_subscription_request=has_pending_sub,
    )


@router.get("/plan", response_model=TeacherPlanResponse)
def teacher_plan_get_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Koçun mevcut paketi + yükseltilebilir solo planlar + AI premium durumu."""
    return _build_plan_response(db, user)


@router.get("/trial-status", response_model=TrialStatusResponse)
def teacher_trial_status_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Bağımsız koç trial geri-sayım + ödeme-duvarı durumu (teacher-shell banner)."""
    from app.services.plans import solo_trial_status
    return TrialStatusResponse(**solo_trial_status(db, user=user))


@router.post("/subscription-request", response_model=MutationResponse[SubscriptionRequestResult])
def teacher_subscription_request_v2(
    body: SubscriptionRequestBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Uygulama-içi 'öde ve devam et' — abonelik aktivasyon talebi.

    Manuel aktivasyon: talep `contact_requests`'e (source=subscription_request)
    düşer → süper admin İletişim Talepleri'nde görür → ödeme alınınca
    /admin/users/{id}/activate-plan ile aktive eder. Migration YOK.
    """
    from app.models.contact_request import ContactRequest
    from app.services import pricing
    from app.services.plans import count_solo_students

    if user.institution_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "managed_by_institution",
                    "message": "Paketin kurumun tarafından yönetilir."},
        )
    plan = (body.plan or "solo_pro").strip()
    if plan not in _SOLO_UPGRADE_TARGETS:
        plan = "solo_pro"
    cycle = (body.cycle or "monthly").strip()
    if cycle not in ("monthly", "academic_year"):
        cycle = "monthly"

    # Aynı koç için bekleyen talep varsa tekrar oluşturma (idempotent).
    existing = (
        db.query(ContactRequest)
        .filter(
            ContactRequest.email == user.email,
            ContactRequest.source == "subscription_request",
            ContactRequest.status == "new",
        )
        .first()
    )
    if existing is not None:
        return MutationResponse[SubscriptionRequestResult](
            data=SubscriptionRequestResult(
                ok=True, already_pending=True,
                message="Zaten bekleyen bir abonelik talebin var. En kısa sürede aktive edilecek.",
            ),
            invalidate=["teacher:me:plan"],
        )

    count = count_solo_students(db, teacher_id=user.id)
    monthly = pricing.compute_solo_monthly(count)
    catalog = pricing.get_pricing_catalog()
    months = int(catalog["annual_paid_months"])
    cycle_label = "Akademik yıl (peşin)" if cycle == "academic_year" else "Aylık"
    price_note = (
        f"~{monthly * months:,} ₺/yıl ({months} ay)".replace(",", ".")
        if cycle == "academic_year"
        else f"~{monthly:,} ₺/ay".replace(",", ".")
    )
    cr = ContactRequest(
        name=user.full_name or user.email,
        email=user.email,
        coach_count=count,
        source="subscription_request",
        message=(
            f"Solo Pro abonelik talebi · {cycle_label} · {count} öğrenci · "
            f"{price_note} · koç_id={user.id}"
        ),
    )
    db.add(cr)
    db.commit()

    # Süper admin/satış inbox'una bildir — talep iletişim talepleri sayfasında
    # zaten görünür, ama mail proaktif uyarı olur (ödeme aktivasyonu manuel).
    try:
        from app.services.email_service import send_email
        catalog = pricing.get_pricing_catalog()
        to = (catalog.get("contact") or {}).get("sales_email") or ""
        if "<" in to and ">" in to:
            to = to.split("<", 1)[1].rstrip(">").strip()
        if to:
            send_email(to=to, template="contact_request_admin", ctx={
                "name": cr.name, "email": cr.email, "phone": "",
                "institution_name": cr.institution_name or "",
                "coach_count": str(cr.coach_count or ""),
                "source_label": "Abonelik talebi (koç)",
                "message": cr.message or "",
            })
    except Exception:
        logger.exception("Koç abonelik talebi admin maili gönderim hatası")

    return MutationResponse[SubscriptionRequestResult](
        data=SubscriptionRequestResult(
            ok=True,
            message="Talebin alındı. Ödeme/aktivasyon için en kısa sürede iletişime geçeceğiz.",
        ),
        invalidate=["teacher:me:plan", "admin:contact-requests"],
    )


@router.post("/subscription/cancel", response_model=MutationResponse[SubscriptionRequestResult])
def teacher_subscription_cancel_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Aktif aboneliği iptal et (yenilenmez). Dönem sonuna kadar erişim sürer,
    sonra ücretsize düşer. Ödeme gerektirmez → self-serve."""
    if user.institution_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "managed_by_institution",
                    "message": "Paketin kurumun tarafından yönetilir."},
        )
    if user.subscription_status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation", "code": "no_active_subscription",
                    "message": "İptal edilecek aktif abonelik yok."},
        )
    user.subscription_status = "canceled"
    db.commit()
    return MutationResponse[SubscriptionRequestResult](
        data=SubscriptionRequestResult(
            ok=True,
            message="Aboneliğin iptal edildi. Dönem sonuna kadar erişimin sürer; sonra ücretsize döner.",
        ),
        invalidate=["teacher:me:plan", "teacher:me:trial-status"],
    )


@router.post("/subscription/resume", response_model=MutationResponse[SubscriptionRequestResult])
def teacher_subscription_resume_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """İptal edilmiş aboneliği geri al (dönem sonunda yenilenmeye devam eder)."""
    if user.institution_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "managed_by_institution",
                    "message": "Paketin kurumun tarafından yönetilir."},
        )
    if user.subscription_status != "canceled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation", "code": "not_canceled",
                    "message": "Geri alınacak iptal edilmiş abonelik yok."},
        )
    user.subscription_status = "active"
    db.commit()
    return MutationResponse[SubscriptionRequestResult](
        data=SubscriptionRequestResult(ok=True, message="İptal geri alındı. Aboneliğin aktif."),
        invalidate=["teacher:me:plan", "teacher:me:trial-status"],
    )


@router.post("/plan/upgrade", response_model=MutationResponse[TeacherPlanResponse])
def teacher_plan_upgrade_v2(
    body: PlanUpgradeBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Bağımsız koç paket yükseltme (solo_pro | solo_elite).

    NOT: Ödeme entegrasyonu ayrı bir iştir; bu uçta yükseltme doğrudan plan
    değişimidir (audit'li). Kurumlu öğretmen self-serve yükseltemez.
    """
    from app.models import PlanChangeReason, PlanOwnerType
    from app.services.plans import (
        change_plan,
        is_paid_plan,
        reactivate_solo_students,
    )

    if user.institution_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "managed_by_institution",
                    "message": "Paketiniz kurumunuz tarafından yönetilir."},
        )
    target = (body.plan or "").strip()
    if target not in _SOLO_UPGRADE_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation", "code": "invalid_plan",
                    "message": "Yalnız Solo paketleri seçilebilir."},
        )

    # Ödeme duvarından / ücretsizden geliyorsa (aktif-ücretli DEĞİLSE) pasif
    # öğrenciler yükseltmede otomatik geri açılır (banner'da verilen söz).
    was_paid_active = (
        is_paid_plan(user.plan or "")
        and getattr(user, "subscription_status", None) == "active"
    )
    change_plan(
        db,
        owner_type=PlanOwnerType.USER,
        owner_id=user.id,
        new_plan=target,
        reason=PlanChangeReason.UPGRADE,
        actor_user_id=user.id,
        note="Bağımsız koç self-serve paket yükseltme",
        autocommit=True,
    )
    if not was_paid_active:
        reactivate_solo_students(db, user, autocommit=True)
    db.refresh(user)
    return MutationResponse[TeacherPlanResponse](
        data=_build_plan_response(db, user),
        invalidate=["teacher:me:ai-consent", "teacher:me:plan"],
    )


# =============================================================================
# KS2 — Tahsilat (koç ↔ öğrenci)
# =============================================================================


def _month_bounds(month: str | None) -> tuple[date, date, str]:
    today = date.today()
    y, m = today.year, today.month
    if month:
        try:
            parts = month.split("-")
            y, m = int(parts[0]), int(parts[1])
            if not (1 <= m <= 12):
                raise ValueError
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "validation", "code": "invalid_month",
                        "message": "Geçersiz ay. YYYY-MM bekleniyor."},
            )
    first = date(y, m, 1)
    last = date(y, m, calendar.monthrange(y, m)[1])
    return first, last, f"{y:04d}-{m:02d}"


def _payment_row(p: CoachPayment) -> PaymentRow:
    return PaymentRow(
        id=p.id,
        amount=p.amount,
        paid_at=p.paid_at.isoformat(),
        method=p.method.value,
        method_label=COACH_PAYMENT_METHOD_LABELS[p.method],
        period_month=p.period_month,
        note=p.note,
        created_at=p.created_at,
    )


def _get_owned_payment(db: Session, payment_id: int, teacher_id: int) -> CoachPayment:
    p = (
        db.query(CoachPayment)
        .join(User, User.id == CoachPayment.student_id)
        .filter(CoachPayment.id == payment_id, User.teacher_id == teacher_id)
        .first()
    )
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "payment_not_found",
                    "message": "Ödeme kaydı bulunamadı."},
        )
    return p


@router.get("/billing", response_model=BillingMonthResponse)
def teacher_billing_v2(
    month: str | None = Query(None),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Aylık tahsilat panosu — öğrenci başına yapılan seans × ücret − ödenen."""
    first, last, month_str = _month_bounds(month)

    students = (
        db.query(User.id, User.full_name, User.email)
        .filter(User.role == UserRole.STUDENT, User.teacher_id == user.id, User.is_active.is_(True))
        .all()
    )
    ids = [int(s.id) for s in students]
    name = {int(s.id): (s.full_name or s.email) for s in students}
    if not ids:
        return BillingMonthResponse(month=month_str, rows=[], totals=BillingTotals(accrued=0, paid=0, balance=0))

    done_rows = (
        db.query(CoachingSession.student_id, func.count(CoachingSession.id))
        .filter(
            CoachingSession.student_id.in_(ids),
            CoachingSession.status == CoachingSessionStatus.DONE,
            CoachingSession.session_date >= first,
            CoachingSession.session_date <= last,
        )
        .group_by(CoachingSession.student_id)
        .all()
    )
    done_map = {int(r[0]): int(r[1]) for r in done_rows}

    rate_map = {
        int(r[0]): int(r[1])
        for r in db.query(CoachStudentRate.student_id, CoachStudentRate.session_fee)
        .filter(CoachStudentRate.student_id.in_(ids)).all()
    }
    pay_map = {
        int(r[0]): int(r[1])
        for r in db.query(CoachPayment.student_id, func.coalesce(func.sum(CoachPayment.amount), 0))
        .filter(CoachPayment.student_id.in_(ids), CoachPayment.period_month == month_str)
        .group_by(CoachPayment.student_id).all()
    }

    rows: list[BillingStudentRow] = []
    t_accrued = t_paid = t_balance = 0
    for sid in ids:
        fee = rate_map.get(sid)
        done = done_map.get(sid, 0)
        paid = pay_map.get(sid, 0)
        if fee is None:
            rows.append(BillingStudentRow(
                student_id=sid, student_name=name[sid], session_fee=None,
                done_sessions=done, accrued=None, paid=paid, balance=None, status="no_rate"))
            continue
        accrued = done * fee
        balance = accrued - paid
        t_accrued += accrued
        t_paid += paid
        t_balance += balance
        if accrued > 0 and balance <= 0:
            st = "paid"
        elif paid > 0:
            st = "partial"
        else:
            st = "pending"
        rows.append(BillingStudentRow(
            student_id=sid, student_name=name[sid], session_fee=fee,
            done_sessions=done, accrued=accrued, paid=paid, balance=balance, status=st))

    rows.sort(key=lambda r: (r.status == "no_rate", -(r.balance or 0)))
    return BillingMonthResponse(
        month=month_str, rows=rows,
        totals=BillingTotals(accrued=t_accrued, paid=t_paid, balance=t_balance),
    )


@router.post("/students/{student_id}/rate", response_model=MutationResponse[dict])
def teacher_set_rate_v2(
    student_id: int,
    body: RateUpdateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenci başına seans ücretini belirle/güncelle (upsert)."""
    student = _get_owned_student(db, student_id, user.id)
    if body.session_fee < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_fee", "message": "Ücret negatif olamaz."},
        )
    rate = db.query(CoachStudentRate).filter(CoachStudentRate.student_id == student.id).first()
    if rate is None:
        rate = CoachStudentRate(coach_id=user.id, student_id=student.id, session_fee=body.session_fee)
        db.add(rate)
    else:
        rate.session_fee = body.session_fee
    db.commit()
    return MutationResponse[dict](
        data={"student_id": student.id, "session_fee": body.session_fee},
        invalidate=[f"teacher:{user.id}:billing", f"teacher:{user.id}:students:{student.id}"],
    )


@router.get("/students/{student_id}/payments", response_model=StudentPaymentsResponse)
def teacher_student_payments_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(db, student_id, user.id)
    rows = (
        db.query(CoachPayment)
        .filter(CoachPayment.student_id == student.id)
        .order_by(CoachPayment.paid_at.desc(), CoachPayment.id.desc())
        .all()
    )
    return StudentPaymentsResponse(
        rows=[_payment_row(p) for p in rows],
        total_paid=sum(p.amount for p in rows),
    )


@router.post("/students/{student_id}/payments", response_model=MutationResponse[PaymentRow])
def teacher_create_payment_v2(
    student_id: int,
    body: PaymentCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Ödeme kaydı ekle (elden/nakit). period_month set'lenirse o ayı kapatır."""
    student = _get_owned_student(db, student_id, user.id)
    if body.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_amount", "message": "Tutar 0'dan büyük olmalı."},
        )
    try:
        paid_at = date.fromisoformat((body.paid_at or "").strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_date", "message": "Geçersiz tarih."},
        )
    pm = (body.period_month or "").strip() or None
    if pm:
        _, _, pm = _month_bounds(pm)  # normalize + validate
    p = CoachPayment(
        coach_id=user.id, student_id=student.id, amount=body.amount, paid_at=paid_at,
        method=CoachPaymentMethod(body.method), period_month=pm,
        note=(body.note or "").strip()[:500] or None,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return MutationResponse[PaymentRow](
        data=_payment_row(p),
        invalidate=[f"teacher:{user.id}:billing", f"teacher:{user.id}:students:{student.id}:payments"],
    )


@router.delete("/payments/{payment_id}", response_model=MutationResponse[dict])
def teacher_delete_payment_v2(
    payment_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    p = _get_owned_payment(db, payment_id, user.id)
    student_id = p.student_id
    db.delete(p)
    db.commit()
    return MutationResponse[dict](
        data={"deleted": True, "id": payment_id},
        invalidate=[f"teacher:{user.id}:billing", f"teacher:{user.id}:students:{student_id}:payments"],
    )


# =============================================================================
# GET /teacher/books — öğretmenin sahip olduğu kitaplar (atama UI için)
# =============================================================================


@router.get("/books", response_model=TeacherBookListResponse)
def teacher_books_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmenin sahip olduğu tüm kitaplar — kitap atama modalında listeye doldurulur."""
    books = (
        db.query(Book)
        .options(joinedload(Book.subject), joinedload(Book.sections))
        .filter(Book.teacher_id == user.id)
        .order_by(Book.name)
        .all()
    )
    items = [
        TeacherBookListItem(
            id=b.id,
            name=b.name,
            type=b.type.value if b.type else "soru_bankasi",
            subject_id=b.subject_id,
            subject_name=b.subject.name if b.subject else None,
            section_count=len(b.sections),
        )
        for b in books
    ]
    return TeacherBookListResponse(items=items, total=len(items))


# =============================================================================
# 4) GET /teacher/badges — 60s polling
# =============================================================================


@router.get("/badges", response_model=TeacherBadgesResponse)
def teacher_badges_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Polling — bekleyen talep + (ertelenmemiş) uyarısı olan öğrenci + cevaplanmış
    destek talebi. Rozetler 'işleyince azalır' (Gördüm/Ertele · cevapla · çöz)."""
    from app.models import SUPPORT_STATUS_ANSWERED, SupportRequest, WarningState

    now = datetime.now(timezone.utc)
    today = date.today()
    students = (
        db.query(User)
        .filter(
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .all()
    )
    muted_ids = get_active_mutes(db, user.id)

    # Ertelenmiş (aktif snooze) uyarı anahtarları → bu uyarılar rozeti tetiklemez
    snoozed_keys = {
        (w.student_id, w.code)
        for w in db.query(WarningState).filter(
            WarningState.actor_id == user.id,
            WarningState.snooze_until.isnot(None),
            WarningState.snooze_until > now,
        ).all()
    }
    # 'Öğrenciler' rozeti = en az bir AKTİF (ertelenmemiş) uyarısı olan öğrenci
    at_risk = 0
    for s in students:
        if s.id in muted_ids:
            continue
        sn = student_snapshot(db, s, today=today)
        if any((s.id, w.code) not in snoozed_keys for w in sn.warnings):
            at_risk += 1

    support_answered = (
        db.query(SupportRequest)
        .filter(
            SupportRequest.requester_id == user.id,
            SupportRequest.status == SUPPORT_STATUS_ANSWERED,
        )
        .count()
    )
    from app.services.support_request_service import pending_count_teacher
    return TeacherBadgesResponse(
        pending_request_count=pending_count_for_teacher(db, user.id),
        at_risk_count=at_risk,
        support_answered_count=support_answered,
        support_inbox_pending=pending_count_teacher(db, user),
        checked_at=now,
    )


# =============================================================================
# 5) GET /teacher/me — hızlı kimlik + öğrenci sayım
# =============================================================================


@router.get("/me", response_model=TeacherMeResponse)
def teacher_me_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    total = (
        db.query(func.count(User.id))
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
        .scalar()
        or 0
    )
    active = (
        db.query(func.count(User.id))
        .filter(
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .scalar()
        or 0
    )
    return TeacherMeResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        institution_id=user.institution_id,
        plan=getattr(user, "plan", None),
        student_count=int(total),
        active_student_count=int(active),
    )


# =============================================================================
# Paket 2 — Program CRUD (öğretmen perspektifi)
# =============================================================================


_TR_WEEK_LABELS_LONG = (
    "Pazartesi", "Salı", "Çarşamba", "Perşembe",
    "Cuma", "Cumartesi", "Pazar",
)


def _get_owned_task(db: Session, task_id: int, teacher_id: int) -> Task:
    """Görevin sahibi olan öğrenci öğretmene aitse görevi döndür, değilse 404.

    JOIN ile tek sorgu: Task → User(student) → teacher_id == teacher_id
    Cross-tenant ve "başkasının görevi" senaryolarında 404.
    """
    task = (
        db.query(Task)
        .options(
            joinedload(Task.book_items)
            .joinedload(TaskBookItem.book)
            .joinedload(Book.subject),
            joinedload(Task.book_items)
            .joinedload(TaskBookItem.section)
            .joinedload(BookSection.topic),
        )
        .join(User, User.id == Task.student_id)
        .filter(
            Task.id == task_id,
            User.teacher_id == teacher_id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "task_not_found",
                "message": "Görev bulunamadı.",
            },
        )
    return task


def _parse_iso_date(s: str | None, *, fallback: date | None = None) -> date:
    if s is None:
        return fallback if fallback is not None else date.today()
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_date",
                "message": "Tarih formatı geçersiz. YYYY-MM-DD bekleniyor.",
            },
        )


def _section_progress_map(
    db: Session, student_id: int, section_ids: list[int],
) -> dict[int, SectionProgress]:
    """SectionProgress satırlarını {section_id → row} olarak yükle.

    Bilgi öğretmenin gördüğü kalem detaylarında rezerv/tamam/kalan exposure'ı için.
    """
    if not section_ids:
        return {}
    rows = (
        db.query(SectionProgress)
        .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
        .filter(
            StudentBook.student_id == student_id,
            SectionProgress.book_section_id.in_(section_ids),
        )
        .all()
    )
    return {r.book_section_id: r for r in rows}


def _build_teacher_task_item(
    item: TaskBookItem, sp_map: dict[int, SectionProgress],
) -> TeacherTaskItem:
    sec = item.section
    sp = sp_map.get(item.book_section_id)
    section_total = sec.test_count if sec else 0
    reserved = sp.reserved_count if sp else 0
    completed = sp.completed_count if sp else 0
    remaining = max(0, section_total - reserved - completed)
    subj = item.book.subject if (item.book and item.book.subject) else None
    return TeacherTaskItem(
        id=item.id,
        book_id=item.book_id,
        book_name=item.book.name if item.book else (item.label or "Deneme"),
        book_type=(item.book.type.value if (item.book and item.book.type) else None),
        subject_id=subj.id if subj else None,
        subject_name=subj.name if subj else None,
        section_id=item.book_section_id,
        section_label=sec.label if sec else None,
        topic_name=sec.topic.name if (sec and sec.topic) else None,
        planned_count=item.planned_count,
        completed_count=item.completed_count,
        section_total_tests=section_total,
        section_reserved_count=reserved,
        section_completed_count=completed,
        section_remaining=remaining,
        correct_count=item.correct_count,
        wrong_count=item.wrong_count,
    )


def _build_teacher_task(db: Session, task: Task) -> TeacherTask:
    section_ids = [it.book_section_id for it in task.book_items]
    sp_map = _section_progress_map(db, task.student_id, section_ids)
    items_out = [_build_teacher_task_item(it, sp_map) for it in task.book_items]
    planned = sum(it.planned_count for it in items_out)
    completed = sum(it.completed_count for it in items_out)
    pct = (completed / planned) if planned > 0 else 0.0
    has_pending = (
        db.query(TaskRequest.id)
        .filter(
            TaskRequest.task_id == task.id,
            TaskRequest.status == RequestStatus.PENDING,
        )
        .first()
        is not None
    )
    return TeacherTask(
        id=task.id,
        student_id=task.student_id,
        date=task.date.isoformat(),
        type=task.type.value if task.type else "test",
        status=task.status.value if task.status else "pending",
        title=task.title or "",
        scheduled_hour=(
            f"{task.scheduled_hour:02d}:00" if task.scheduled_hour is not None else None
        ),
        period=task.period,
        order=task.order,
        is_draft=bool(task.is_draft),
        notes=task.notes,
        items=items_out,
        planned_count=planned,
        completed_count=completed,
        pct=pct,
        solved_count=task.solved_count,
        has_pending_request=has_pending,
        work_block_id=task.work_block_id,
        work_block_title=(task.work_block.title if task.work_block else None),
        work_block_unit=(task.work_block.unit if task.work_block else None),
    )


def _load_day_tasks_for_student(
    db: Session, student_id: int, d: date, *, include_draft: bool = True,
) -> list[Task]:
    """Öğretmen perspektifi: taslakları da gör (öğrencinin /day'i taslakları hariç).

    Sıralama (Jinja `teacher_program.py:142-153` parite):
      1. Saat atanmış görevler önce (NULL last)
      2. Saatli görevler kronolojik
      3. Saatsiz görevler **ders bazında** (subject.order, subject.id) gruplanır
      4. Aynı ders içinde manuel `Task.order`
      5. Son olarak `Task.id` ile stabilize
    """
    q = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.student_id == student_id, Task.date == d)
    )
    if not include_draft:
        q = q.filter(Task.is_draft.is_(False))
    tasks = q.all()
    # SQL-side ORDER BY subject join karmaşası yerine Python-side sort —
    # Jinja teacher_program.py:142-153 ile bire bir aynı davranış.
    tasks.sort(
        key=lambda t: (
            0 if t.scheduled_hour is not None else 1,
            t.scheduled_hour if t.scheduled_hour is not None else 0,
            (
                t.book_items[0].book.subject.order,
                t.book_items[0].book.subject.id,
            )
            if (t.book_items and t.book_items[0].book and t.book_items[0].book.subject)
            else (10**9, 10**9),
            t.order,
            t.id,
        )
    )
    return tasks


def _invalidate_for_task(task: Task, teacher_id: int) -> list[str]:
    """Mutation invalidate listesi — hem öğretmen hem öğrenci tarafını günceller."""
    date_iso = task.date.isoformat()
    sid = task.student_id
    return [
        # Öğretmen perspektifi
        f"teacher:{teacher_id}:students:{sid}:day:{date_iso}",
        f"teacher:{teacher_id}:students:{sid}:week",
        f"teacher:{teacher_id}:students:{sid}:summary",
        f"teacher:{teacher_id}:students:{sid}:sidebar",
        # Serbest iş blokları: bağlı görev ekle/sil/düzenle → dağıtılan/kalan değişir
        f"teacher:{teacher_id}:students:{sid}:work-blocks",
        # Kaynak Durumu sidebar'ı: kitap/section rezerv sayıları değiştiyse
        # yenilensin (görev ekle/sil/düzenle hepsinde geçerli)
        f"teacher:{teacher_id}:dashboard",
        # Öğrenci tarafı (aynı kullanıcı her iki tab'i de açık olabilir)
        f"student:{sid}:day:{date_iso}",
        f"student:{sid}:sidebar",
        f"student:{sid}:summary:{date_iso}",
    ]


def _ensure_section_belongs_to_book(
    db: Session, book_id: int, section_id: int,
) -> tuple[Book, BookSection]:
    """Kitap + bölüm uyumlu mu? Değilse 422 invalid_section."""
    book = db.query(Book).filter(Book.id == book_id).first()
    section = db.query(BookSection).filter(BookSection.id == section_id).first()
    if not book or not section or section.book_id != book.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_section",
                "message": "Kitap ve bölüm uyumsuz.",
            },
        )
    return book, section


def _ensure_student_book_assigned(
    db: Session, student_id: int, book_id: int,
) -> None:
    """Kitap öğrenciye atanmamışsa 422 (mevcut sözleşme: öğretmen önce atamalı)."""
    sb = (
        db.query(StudentBook.id)
        .filter(
            StudentBook.student_id == student_id,
            StudentBook.book_id == book_id,
        )
        .first()
    )
    if not sb:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "book_not_assigned",
                "message": "Bu kitap öğrenciye atanmamış. Önce kitabı atayın.",
            },
        )


def _ensure_count_positive(count: int) -> None:
    if count < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_count",
                "message": "Test/deneme sayısı en az 1 olmalı.",
            },
        )


_VALID_PERIODS = {"morning", "noon", "evening"}


def _validate_period(p: str | None) -> str | None:
    """M6 — periyot string normalize. None/boş → None; geçersiz → 422."""
    if p is None:
        return None
    norm = p.strip().lower()
    if norm == "":
        return None
    if norm not in _VALID_PERIODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_period",
                "message": "Periyot 'morning' | 'noon' | 'evening' olabilir.",
            },
        )
    return norm


def _validate_scheduled_hour(h: int | None) -> int | None:
    if h is None:
        return None
    if not (0 <= h <= 23):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_hour",
                "message": "Saat 0-23 aralığında olmalı.",
            },
        )
    return h


def _reservation_to_http(e: ReservationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "validation",
            "code": "RESERVE_OVER_CAPACITY",
            "message": str(e),
        },
    )


def _next_order_for_day(db: Session, student_id: int, d: date) -> int:
    row = (
        db.query(Task.order)
        .filter(Task.student_id == student_id, Task.date == d)
        .order_by(Task.order.desc())
        .first()
    )
    return (row[0] + 1) if row else 0


def _compose_single_item_title(book: Book, section: BookSection, planned_count: int) -> str:
    """Tek kitap-kalemli görev başlığı — 'Kitap — Bölüm: N test/deneme'.

    Hem oluşturma (_create_task_with_items) hem tek-kalem düzenleme paylaşır →
    yeni görev de düzenlenmiş görevle aynı okunur başlığı taşır (placeholder yok)."""
    unit_word = "deneme" if book.type and book.type.value in (
        "brans_denemesi", "genel_deneme",
    ) else "test"
    return f"{book.name} — {section.label}: {planned_count} {unit_word}"


def _create_task_with_items(
    db: Session,
    *,
    student: User,
    payload: TaskCreateBody | "BulkTasksBody.tasks",  # noqa: F821 (tip ipucu)
) -> Task:
    """TaskCreateBody veya BulkTaskItem'dan tek bir Task üret.

    Rezervi her kalem için reserve_item ile açar; kapasite hatası ReservationError
    çağrıya ulaşır (çağıran wrap eder).
    """
    d = _parse_iso_date(payload.date)
    sched = _validate_scheduled_hour(payload.scheduled_hour)
    period = _validate_period(getattr(payload, "period", None))
    try:
        ttype = TaskType(payload.type)
    except ValueError:
        ttype = TaskType.TEST

    # "test" görevi = soru ataması → en az bir kalem (kitap + bölüm + sayı) şart.
    # Etkinlik tipleri (video/özet/tekrar/diğer) KALEMSİZ olabilir: başlık/not ile
    # tanımlı "yap/yapma" görevi; öğrenci görev-bazında tamamlar, soru %'sine girmez.
    # (Kullanıcı 2026-05-24: etkinlik tiplerine kalemsiz görev izni.)
    if not payload.items and ttype == TaskType.TEST:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "no_items",
                "message": "Test görevinde en az bir kalem olmalı (kitap + bölüm + soru sayısı). "
                           "Soru atamasız bir görev için tipi Video/Özet/Tekrar/Diğer seç.",
            },
        )

    # Kalemler geçerli mi (kitap-bölüm uyumu + atama + sayım)? Kitapsız "deneme"
    # kalemi (book_id None) kitap doğrulaması + rezerv ATLAR; yalnız sayı kontrolü.
    for it in payload.items:
        _ensure_count_positive(it.planned_count)
        if it.book_id is None:
            continue  # kitapsız deneme kalemi — kapasite/atama yok
        _ensure_section_belongs_to_book(db, it.book_id, it.section_id)
        _ensure_student_book_assigned(db, student.id, it.book_id)

    # Opsiyonel serbest iş bloğu bağı (Katman 3) — blok bu öğrenciye ait olmalı.
    work_block_id = getattr(payload, "work_block_id", None)
    if work_block_id is not None:
        from app.models import CoachWorkBlock
        block = (
            db.query(CoachWorkBlock)
            .filter(
                CoachWorkBlock.id == work_block_id,
                CoachWorkBlock.student_id == student.id,
            )
            .first()
        )
        if block is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "code": "work_block_not_found",
                        "message": "İş bloğu bulunamadı."},
            )

    order = _next_order_for_day(db, student.id, d)
    # Smart draft default (Jinja parite): is_draft=None → gelecek tarihler taslak,
    # bugün/geçmiş canlı. Açık True/False değer override eder.
    raw_is_draft = getattr(payload, "is_draft", None)
    if raw_is_draft is None:
        is_draft_value = d > date.today()
    else:
        is_draft_value = bool(raw_is_draft)
    published_at = None if is_draft_value else datetime.now(timezone.utc)
    task = Task(
        student_id=student.id,
        date=d,
        type=ttype,
        title=(payload.title or "").strip() or "—",
        status=TaskStatus.PENDING,
        order=order,
        scheduled_hour=sched,
        period=period,
        is_draft=is_draft_value,
        published_at=published_at,
        notes=(payload.notes or None),
        work_block_id=work_block_id,
    )
    db.add(task)
    db.flush()

    for it in payload.items:
        if it.book_id is None:
            # Kitapsız deneme kalemi: rezerv yok, label deneme adını taşır.
            db.add(TaskBookItem(
                task_id=task.id,
                book_id=None,
                book_section_id=None,
                label=(getattr(it, "label", None) or (payload.title or "").strip() or "Deneme"),
                planned_count=it.planned_count,
                completed_count=0,
            ))
            continue
        # reserve_item kapasite aşımında ReservationError fırlatır
        reserve_item(
            db,
            student_id=student.id,
            book_id=it.book_id,
            section_id=it.section_id,
            count=it.planned_count,
        )
        db.add(TaskBookItem(
            task_id=task.id,
            book_id=it.book_id,
            book_section_id=it.section_id,
            planned_count=it.planned_count,
            completed_count=0,
        ))
    db.flush()

    # Tek kitap-kalemli görevde başlığı otomatik üret — tek-kalem düzenleme ile
    # tutarlı. Frontend 'Görev' placeholder'ı yerine 'Kitap — Bölüm: N test'.
    # (Kitapsız deneme/etkinlik kalemleri kendi label/başlığını korur.)
    book_items = [it for it in payload.items if it.book_id is not None]
    if len(payload.items) == 1 and len(book_items) == 1:
        bi = book_items[0]
        book = db.query(Book).filter(Book.id == bi.book_id).first()
        section = db.query(BookSection).filter(BookSection.id == bi.section_id).first()
        if book and section:
            task.title = _compose_single_item_title(book, section, bi.planned_count)
            db.flush()
    return task


# ---------------------- /students/{id}/day ----------------------


@router.get(
    "/students/{student_id}/day",
    response_model=TeacherStudentDayResponse,
)
def teacher_student_day_v2(
    student_id: int,
    date_param: str | None = Query(None, alias="date"),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen perspektifinde öğrencinin günü — taslaklar dahil."""
    student = _get_owned_student(db, student_id, user.id)
    today = date.today()
    d = _parse_iso_date(date_param, fallback=today)

    tasks = _load_day_tasks_for_student(db, student.id, d, include_draft=True)
    tasks_out = [_build_teacher_task(db, t) for t in tasks]
    planned = sum(t.planned_count for t in tasks_out)
    completed = sum(t.completed_count for t in tasks_out)
    pct = (completed / planned) if planned > 0 else 0.0
    # Görev/test/deneme özeti — yayınlanmış (öğrencinin gördüğü) görevler üzerinden.
    from app.services import gorev_stats
    gorev = _build_gorev_breakdown(
        gorev_stats.summarize([t for t in tasks if not t.is_draft])
    )
    # Öğrencinin o güne dair serbest düşünce notu (salt-okuma)
    from app.models import StudentDayNote
    _note = (
        db.query(StudentDayNote)
        .filter(StudentDayNote.student_id == student.id, StudentDayNote.date == d)
        .first()
    )

    return TeacherStudentDayResponse(
        student_id=student.id,
        date=d.isoformat(),
        is_today=(d == today),
        is_future=(d > today),
        is_past=(d < today),
        prev_date=(d - timedelta(days=1)).isoformat(),
        next_date=(d + timedelta(days=1)).isoformat(),
        tasks=tasks_out,
        today_planned=planned,
        today_completed=completed,
        today_pct=pct,
        gorev=gorev,
        day_note=(_note.body if _note else ""),
    )


# ---------------------- /students/{id}/week ----------------------


@router.get(
    "/students/{student_id}/week",
    response_model=TeacherStudentWeekResponse,
)
def teacher_student_week_v2(
    student_id: int,
    start_param: str | None = Query(None, alias="start"),
    program_id: int | None = Query(None, alias="program_id"),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen perspektifinde program-aware görünüm.

    WP2 (2026-05-31) — Program-aware mantık:
      - `program_id` verilirse o programa odaklanır (geçmiş programları görme)
      - `program_id` yoksa: bugünü içeren aktif program → onun tarih aralığı
      - Aktif program yoksa: fallback (mevcut anchor-blok mantığı, bugünü
        içeren bloğa snap) — eski öğrenciler bozulmadan çalışsın

    Pencere uzunluğu artık dinamik: program 1-14 gün arası ne olursa onu
    gösterir. Eski parite alanları (week_anchor, anchor_is_manual,
    week_draft_total) korunur — frontend hâlâ aynı response şemasını kullanır.
    """
    from app.models import StudentBook, WeeklyProgram
    from app.routes.teacher_program import (
        _resolve_week_anchor,
        _student_week_start,
        compute_day_subject_summary,
    )
    from app.services.suggestions import (
        build_student_model,
        confidence_label,
        maturity,
        maturity_label,
        suggest_for_date,
    )
    from app.services.weekly_program_service import get_active_program

    def _task_completion_fraction(t: Task) -> float:
        """Görev tamamlama oranı (0..1) — manşet %'si için.

        COMPLETED görev → 1.0 (tip fark etmez). Sayısal (test/deneme) görev →
        çözülen/planlanan soru. Kalemsiz etkinlik (Video/Özet/Tekrar/Diğer)
        tamamlanmamışsa 0. Böylece 'Diğer' görevleri 'tamam' işaretlenince
        tamamlama yüzdesine SAYILIR (eskiden soru-bazlı olduğu için %0 görünüyordu).
        """
        if t.status == TaskStatus.COMPLETED:
            return 1.0
        p = sum(int(it.planned_count or 0) for it in t.book_items)
        if p <= 0:
            return 0.0
        c = sum(int(it.completed_count or 0) for it in t.book_items)
        return min(1.0, c / p)

    student = _get_owned_student(db, student_id, user.id)
    today = date.today()

    # Pencere belirleme — öncelik sırası:
    # 1) program_id verildi → o program (sahip kontrolü)
    # 2) start_param verildi → eski mantık (kullanıcı manuel gezdi)
    # 3) Hiçbiri yok → aktif program ara → varsa onu kullan
    # 4) Aktif yoksa → fallback (bugünü içeren anchor-blok)
    active_program: WeeklyProgram | None = None
    if program_id is not None:
        active_program = db.get(WeeklyProgram, program_id)
        if active_program is None or active_program.student_id != student.id:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "code": "program_not_found",
                        "message": "Program bulunamadı."},
            )
        start = active_program.start_date
        end = active_program.end_date
    elif start_param:
        # Açık gezinme — kullanıcı buton bastı; eski 7-günlük davranış
        start = _parse_iso_date(start_param, fallback=today)
        end = start + timedelta(days=6)
    else:
        # Default: bugünü içeren aktif program
        active_program = get_active_program(
            db, student_id=student.id, today=today,
        )
        if active_program is not None:
            start = active_program.start_date
            end = active_program.end_date
        else:
            # Fallback: eski anchor-blok mantığı (bugünü içeren bloğa snap)
            start = _student_week_start(db, student, today)
            end = start + timedelta(days=6)

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    # Tek query'de tüm hafta tasklarını çek (taslaklar dahil — öğretmen görür)
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
            joinedload(Task.book_items).joinedload(TaskBookItem.section).joinedload(BookSection.topic),
        )
        .filter(Task.student_id == student.id, Task.date.in_(days))
        .order_by(Task.date, Task.scheduled_hour.is_(None), Task.scheduled_hour, Task.order, Task.id)
        .all()
    )
    tasks_by_day: dict[date, list[Task]] = {d: [] for d in days}
    for t in tasks:
        tasks_by_day[t.date].append(t)

    # Her gün için Python-side ders bazlı sort (Jinja teacher_program.py:142-153 parite)
    def _day_sort_key(t: Task):
        return (
            0 if t.scheduled_hour is not None else 1,
            t.scheduled_hour if t.scheduled_hour is not None else 0,
            (
                t.book_items[0].book.subject.order,
                t.book_items[0].book.subject.id,
            )
            if (t.book_items and t.book_items[0].book and t.book_items[0].book.subject)
            else (10**9, 10**9),
            t.order,
            t.id,
        )
    for d in days:
        tasks_by_day[d].sort(key=_day_sort_key)

    # WeekNote anchor — mevcut Jinja servisini reuse et
    week_start_anchor = _student_week_start(db, student, start)
    notes_q = (
        db.query(WeekNote)
        .filter(
            WeekNote.student_id == student.id,
            WeekNote.week_start == week_start_anchor,
        )
        .order_by(WeekNote.order.asc(), WeekNote.id.asc())
        .all()
    )
    notes_out = [
        TeacherWeekNote(id=n.id, body=n.body, order=n.order, is_done=bool(n.is_done))
        for n in notes_q
    ]

    # Öğrenciye atanmış kitaplar (ders bazlı özet için)
    assignments = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.book).joinedload(Book.subject))
        .filter(StudentBook.student_id == student.id)
        .all()
    )
    subjects_map: dict[int, object] = {}
    for sb in assignments:
        subjects_map[sb.book.subject.id] = sb.book.subject
    subjects = sorted(subjects_map.values(), key=lambda s: (s.order, s.name))

    # Öğrenme modeli — request başına 1 kez
    student_model = build_student_model(db, student.id, today=today)
    mat = maturity(student_model)
    mat_label = maturity_label(mat)

    days_out: list[TeacherStudentWeekDay] = []
    total_planned = 0
    total_completed = 0
    week_draft_total = 0
    # Manşet % artık GÖREV-TAMAMLAMA bazlı (her görev = 1 birim; 'Diğer' etkinlik
    # görevleri de sayılır). planned/completed soru hacmi olarak KALIR ("8 test"
    # + analitik/veli soru tablosu bunları kullanmaya devam eder).
    from app.services import gorev_stats
    week_frac_sum = 0.0
    week_task_count = 0
    for d in days:
        day_tasks = tasks_by_day[d]
        tt = [_build_teacher_task(db, t) for t in day_tasks]
        planned = sum(t.planned_count for t in tt)
        completed = sum(t.completed_count for t in tt)
        # Görev/test/deneme ayrımı — "122 test" (deneme 120 sorusu test sayılıyordu)
        # yerine test (soru bankası) + deneme AYRI.
        _g = gorev_stats.summarize(day_tasks)
        frac_sum = sum(_task_completion_fraction(t) for t in day_tasks)
        pct = (frac_sum / len(day_tasks)) if day_tasks else 0.0
        week_frac_sum += frac_sum
        week_task_count += len(day_tasks)
        draft_count = sum(1 for t in day_tasks if t.is_draft)
        week_draft_total += draft_count

        # Ders bazlı özet (Jinja compute_day_subject_summary)
        raw_summary = compute_day_subject_summary(day_tasks, subjects)
        day_subject_summary = [
            TeacherDaySubjectSummary(
                subject_id=ent["subject"].id,
                subject_name=ent["subject"].name,
                task_count=ent.get("task_count", 0),
                tests=ent.get("tests", 0),
                denemeler=ent.get("denemeler", 0),
            )
            for ent in raw_summary
        ]

        # Inline öneriler (exclude: günde zaten ekli olan kitap-bölüm çiftleri)
        exclude = {(it.book_id, it.book_section_id) for t in day_tasks for it in t.book_items}
        sugs = suggest_for_date(
            db, student.id, d, model=student_model, exclude_keys=exclude, today=today,
        )
        day_sugs = [
            TeacherSuggestionInline(
                book_id=s.book_id,
                book_name=s.book_name,
                book_type=s.book_type,
                section_id=s.section_id,
                section_label=s.section_label,
                subject_id=s.subject_id,
                subject_name=s.subject_name,
                topic_name=s.topic_name,
                planned_count=s.planned_count,
                remaining=s.remaining,
                confidence=round(float(s.confidence), 3),
                confidence_label=confidence_label(s.confidence),
                score=round(float(s.score), 3),
                reasons=list(s.reasons or []),
            )
            for s in sugs
        ]

        days_out.append(TeacherStudentWeekDay(
            date=d.isoformat(),
            dow_label=_TR_WEEK_LABELS_LONG[d.weekday()],
            is_today=(d == today),
            is_future=(d > today),
            is_past=(d < today),
            tasks_count=len(day_tasks),
            planned=planned,
            completed=completed,
            pct=pct,
            test_planned=_g.test_planned,
            test_completed=_g.test_completed,
            deneme_planned=_g.deneme_planned,
            deneme_completed=_g.deneme_completed,
            deneme_count=_g.cat_total["deneme"] + _g.cat_total["tam_deneme"],
            etkinlik_count=_g.cat_total["etkinlik"],
            tasks=tt,
            draft_count=draft_count,
            subject_summary=day_subject_summary,
            suggestions=day_sugs,
        ))
        total_planned += planned
        total_completed += completed

    total_pct = (week_frac_sum / week_task_count) if week_task_count > 0 else 0.0

    # Hafta anchor (read-only)
    week_anchor = _resolve_week_anchor(db, student)
    anchor_is_manual = student.program_anchor_date is not None

    # Aktif phase (Jinja partial'da rozet için)
    active_phase: TeacherActivePhase | None = None
    if student.academic_year is not None:
        ph = student.academic_year.active_phase_on(today)
        if ph is not None:
            active_phase = TeacherActivePhase(
                kind=ph.kind.value if ph.kind else "regular",
                kind_label=ph.kind_label,
                kind_badge=ph.kind_badge,
                capacity_multiplier=float(ph.capacity_multiplier),
                is_no_school=bool(ph.is_no_school),
            )

    # Track durumu
    from app.models.user import TRACK_LABELS
    track_required = bool(student.requires_track)
    track_missing = track_required and student.track is None
    track_label = TRACK_LABELS.get(student.track) if student.track else None

    # WP2 — Program-aware ek alanlar (program seçici dropdown + banner)
    from app.services.weekly_program_service import (
        get_unlinked_task_summary,
        list_programs,
    )
    all_progs = list_programs(db, student_id=student.id)
    bugune_aktif = get_active_program(db, student_id=student.id, today=today)
    unlinked = get_unlinked_task_summary(db, student_id=student.id)

    # current_program = gösterilen pencereyi temsil eden program (eğer böyle bir
    # program varsa). Pencere tam olarak bir programın aralığıyla eşleşiyorsa
    # o program "current" sayılır.
    current_prog = active_program  # üstte set edildi (program_id veya default)
    if current_prog is None:
        # Pencere bir programın tarih aralığına denk geliyor mu (eski mantık fallback'inde)
        for p in all_progs:
            if p.start_date == start and p.end_date == end:
                current_prog = p
                break

    def _wp_to_brief(p):
        return WeeklyProgramItem(
            id=p.id,
            student_id=p.student_id,
            start_date=p.start_date.isoformat(),
            end_date=p.end_date.isoformat(),
            day_count=p.day_count,
            name=p.name,
            notes=p.notes,
            is_active=p.contains(today),
            created_at=p.created_at,
            label=p.label,
        )

    return TeacherStudentWeekResponse(
        student_id=student.id,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        prev_start=(start - timedelta(days=7)).isoformat(),
        next_start=(start + timedelta(days=7)).isoformat(),
        week_start_anchor=week_start_anchor.isoformat(),
        days=days_out,
        total_planned=total_planned,
        total_completed=total_completed,
        total_pct=total_pct,
        notes=notes_out,
        # Paket 3.5a parity
        week_anchor=week_anchor.isoformat() if week_anchor else None,
        anchor_is_manual=anchor_is_manual,
        week_draft_total=week_draft_total,
        maturity_value=round(mat, 3),
        maturity_label=mat_label,
        weeks_observed=student_model.weeks_observed,
        days_observed=student_model.days_observed,
        active_phase=active_phase,
        track_required=track_required,
        track_missing=track_missing,
        track_label=track_label,
        # WP2 — Program-aware
        active_program_id=bugune_aktif.id if bugune_aktif else None,
        current_program_id=current_prog.id if current_prog else None,
        current_program_label=current_prog.label if current_prog else None,
        current_program_name=current_prog.name if current_prog else None,
        current_program_day_count=current_prog.day_count if current_prog else None,
        programs=[_wp_to_brief(p) for p in all_progs],
        unlinked_task_count=int(unlinked["count"]) if unlinked else 0,
        unlinked_earliest=(
            unlinked["earliest"].isoformat() if unlinked else None
        ),
        unlinked_latest=(
            unlinked["latest"].isoformat() if unlinked else None
        ),
    )


# ---------------------- POST /students/{id}/tasks ----------------------


@router.post(
    "/students/{student_id}/tasks",
    response_model=MutationResponse[TeacherTask],
)
def teacher_create_task_v2(
    student_id: int,
    body: TaskCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Yeni görev + kalem(ler) oluştur. Rezervleri açar, kapasite aşımında 422."""
    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    try:
        task = _create_task_with_items(db, student=student, payload=body)
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    db.refresh(task)
    return MutationResponse[TeacherTask](
        data=_build_teacher_task(db, task),
        invalidate=_invalidate_for_task(task, user.id),
    )


# ---------------------- Devret (carryover) — geçen haftadan eksikler ----------------------


def _carryover_cutoff(db: Session, student_id: int) -> date:
    """Devret/reconcile sınırı: aktif programın başlangıcı, yoksa bugün.
    Bundan ÖNCEKİ haftalar 'geçmiş' sayılır (haftası geçince serbest bırak)."""
    from app.services import weekly_program_service as wps

    today = date.today()
    active = wps.get_active_program(db, student_id=student_id, today=today)
    return active.start_date if active is not None else today


@router.get(
    "/students/{student_id}/carryover-candidates",
    response_model=CarryoverCandidatesResponse,
)
def teacher_carryover_candidates_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Geçen haftalardan yapılmadan kalan kalemler (devret adayları).

    Önce 'ölü rezerv' serbest bırakılır (kapasite geri döner) → koç bu kalemleri
    yeni haftaya taşıyabilir. Aktif programın başlangıcından ÖNCEKİ, tamamlanmamış,
    yayında görevlerin section'lı + kalan>0 kalemleri.
    """
    from app.services import task_service as tsvc

    from datetime import timedelta as _td

    from app.services import weekly_program_service as wps

    student = _get_owned_student(db, student_id, user.id)
    cutoff = _carryover_cutoff(db, student.id)
    # Ölü rezervi serbest bırak (idempotent, TÜM geçmiş) — kapasite hazır olsun.
    res = tsvc.reconcile_past_reservations(db, student_id=student.id, cutoff_date=cutoff)
    if res.get("released_tests"):
        db.commit()
    # Devret listesi YALNIZ bir önceki haftayla sınırlı (koçu tüm geçmiş yığını
    # boğmasın). Önceki program varsa onun başlangıcı, yoksa cutoff'tan 7 gün geri.
    prev = wps.get_previous_program(db, student_id=student.id, before_date=cutoff)
    since = prev.start_date if prev is not None else (cutoff - _td(days=7))
    rows = tsvc.list_carryover_candidates(
        db, student_id=student.id, cutoff_date=cutoff, since_date=since,
    )
    return CarryoverCandidatesResponse(
        candidates=[
            CarryoverCandidate(
                task_item_id=r["task_item_id"],
                task_date=r["task_date"].isoformat(),
                book_id=r["book_id"],
                section_id=r["section_id"],
                book_name=r["book_name"],
                section_label=r["section_label"],
                subject_id=r["subject_id"],
                planned=r["planned"],
                completed=r["completed"],
                remaining=r["remaining"],
            )
            for r in rows
        ],
        cutoff_date=cutoff.isoformat(),
    )


@router.post(
    "/students/{student_id}/carryover",
    response_model=MutationResponse[CarryoverResult],
)
def teacher_carryover_v2(
    student_id: int,
    body: CarryoverBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Seçili eksik kalemleri yeni güne taşı (her kalem → yeni görev).

    Önce ölü rezerv serbest bırakılır (kapasite hazır), sonra her kalem için
    normal görev oluşturma (rezerv açar). Eski (geçmiş) görev kaydı DURUR —
    yalnızca yeni haftada yeni görevler oluşur.
    """
    from app.services import task_service as tsvc

    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    target = _parse_iso_date(body.target_date)
    if not body.items:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid", "code": "no_items", "message": "Taşınacak kalem seçilmedi."},
        )
    # Ölü rezervi serbest bırak → taşınan kalemler için kapasite açılsın.
    cutoff = _carryover_cutoff(db, student.id)
    tsvc.reconcile_past_reservations(db, student_id=student.id, cutoff_date=cutoff)

    created = 0
    try:
        for it in body.items:
            if it.count < 1:
                continue
            payload = TaskCreateBody(
                date=target.isoformat(),
                type="test",
                title="—",  # _create_task_with_items tek-kalemde otomatik başlık üretir
                period=body.period,
                items=[TaskItemBody(book_id=it.book_id, section_id=it.section_id, planned_count=it.count)],
            )
            _create_task_with_items(db, student=student, payload=payload)
            created += 1
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return MutationResponse[CarryoverResult](
        data=CarryoverResult(created_tasks=created, target_date=target.isoformat()),
        invalidate=[
            f"teacher:{user.id}:students:{student.id}:week",
            f"teacher:{user.id}:students:{student.id}:day",
        ],
    )


# ---------------------- Görev şablonları (TaskTemplate) ----------------------


def _task_template_invalidate(teacher_id: int) -> list[str]:
    return [f"teacher:{teacher_id}:task-templates"]


def _build_task_template_model(tpl) -> TaskTemplateModel:
    items: list[TaskTemplateItemModel] = []
    total = 0
    for it in tpl.items:
        total += it.planned_count
        items.append(TaskTemplateItemModel(
            book_id=it.book_id,
            section_id=it.book_section_id,
            book_name=(it.book.name if it.book else "—"),
            section_label=(it.section.label if it.section else "—"),
            planned_count=it.planned_count,
        ))
    return TaskTemplateModel(
        id=tpl.id, name=tpl.name, type=tpl.type.value, items=items,
        item_count=len(items), total_planned=total, created_at=tpl.created_at,
    )


def _get_owned_template(db: Session, template_id: int, teacher_id: int):
    from app.models import TaskTemplate, TaskTemplateItem
    tpl = (
        db.query(TaskTemplate)
        .options(
            joinedload(TaskTemplate.items).joinedload(TaskTemplateItem.book),
            joinedload(TaskTemplate.items).joinedload(TaskTemplateItem.section),
        )
        .filter(TaskTemplate.id == template_id, TaskTemplate.teacher_id == teacher_id)
        .first()
    )
    if not tpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "template_not_found",
                    "message": "Görev şablonu bulunamadı."},
        )
    return tpl


def _validate_template_item(db: Session, teacher_id: int, book_id: int, section_id: int, count: int):
    if count < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_count",
                    "message": "Test sayısı en az 1 olmalı."},
        )
    book = db.query(Book).filter(Book.id == book_id, Book.teacher_id == teacher_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "book_not_found",
                    "message": "Kitap bulunamadı."},
        )
    _ensure_section_belongs_to_book(db, book_id, section_id)


@router.get("/task-templates", response_model=TaskTemplateListResponse)
def teacher_task_templates_list_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmenin görev şablonları (sık kullanılan görev kalıpları)."""
    from app.models import TaskTemplate, TaskTemplateItem
    tpls = (
        db.query(TaskTemplate)
        .options(
            joinedload(TaskTemplate.items).joinedload(TaskTemplateItem.book),
            joinedload(TaskTemplate.items).joinedload(TaskTemplateItem.section),
        )
        .filter(TaskTemplate.teacher_id == user.id)
        .order_by(TaskTemplate.created_at.desc())
        .all()
    )
    return TaskTemplateListResponse(items=[_build_task_template_model(t) for t in tpls])


@router.post("/task-templates", response_model=MutationResponse[TaskTemplateModel])
def teacher_task_template_create_v2(
    body: TaskTemplateCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Yeni görev şablonu oluştur (formdan: kitap+bölüm+sayı kalemleri)."""
    from app.models import TaskTemplate, TaskTemplateItem
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "name_required", "message": "Ad boş olamaz."},
        )
    if not body.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "no_items", "message": "En az bir kalem ekleyin."},
        )
    try:
        ttype = TaskType(body.type)
    except ValueError:
        ttype = TaskType.TEST
    for it in body.items:
        _validate_template_item(db, user.id, it.book_id, it.section_id, it.planned_count)
    tpl = TaskTemplate(teacher_id=user.id, name=name[:160], type=ttype)
    db.add(tpl)
    db.flush()
    for it in body.items:
        db.add(TaskTemplateItem(
            template_id=tpl.id, book_id=it.book_id,
            book_section_id=it.section_id, planned_count=it.planned_count,
        ))
    db.commit()
    tpl = _get_owned_template(db, tpl.id, user.id)
    return MutationResponse[TaskTemplateModel](
        data=_build_task_template_model(tpl), invalidate=_task_template_invalidate(user.id),
    )


@router.post("/task-templates/from-task/{task_id}", response_model=MutationResponse[TaskTemplateModel])
def teacher_task_template_from_task_v2(
    task_id: int,
    body: TaskTemplateFromTaskBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Mevcut bir görevi şablon olarak kaydet (kalemleri kopyalanır)."""
    from app.models import TaskTemplate, TaskTemplateItem
    task = _get_owned_task(db, task_id, user.id)
    if not task.book_items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "no_items", "message": "Görevde kalem yok."},
        )
    name = (body.name or "").strip() or task.title
    tpl = TaskTemplate(teacher_id=user.id, name=name[:160], type=task.type)
    db.add(tpl)
    db.flush()
    for it in task.book_items:
        db.add(TaskTemplateItem(
            template_id=tpl.id, book_id=it.book_id,
            book_section_id=it.book_section_id, planned_count=it.planned_count,
        ))
    db.commit()
    tpl = _get_owned_template(db, tpl.id, user.id)
    return MutationResponse[TaskTemplateModel](
        data=_build_task_template_model(tpl), invalidate=_task_template_invalidate(user.id),
    )


@router.delete("/task-templates/{template_id}", response_model=MutationResponse[dict])
def teacher_task_template_delete_v2(
    template_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    tpl = _get_owned_template(db, template_id, user.id)
    db.delete(tpl)
    db.commit()
    return MutationResponse[dict](
        data={"deleted": template_id}, invalidate=_task_template_invalidate(user.id),
    )


@router.post(
    "/students/{student_id}/tasks/from-template",
    response_model=MutationResponse[TeacherTask],
)
def teacher_apply_task_template_v2(
    student_id: int,
    body: ApplyTaskTemplateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Görev şablonunu öğrenciye belirtilen tarihte tek tıkla uygula → görev oluşturur."""
    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    tpl = _get_owned_template(db, body.template_id, user.id)
    if not tpl.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "no_items",
                    "message": "Şablonda kalem yok (kitap silinmiş olabilir)."},
        )
    # Başlık türet: tek kalem → 'kitap — bölüm: N test', çok kalem → şablon adı
    if len(tpl.items) == 1:
        it0 = tpl.items[0]
        bk = it0.book.name if it0.book else "—"
        sc = it0.section.label if it0.section else "—"
        unit = "deneme" if (it0.book and it0.book.type.value in ("brans_denemesi", "genel_deneme")) else "test"
        title = f"{bk} — {sc}: {it0.planned_count} {unit}"
    else:
        title = tpl.name
    payload = TaskCreateBody(
        date=body.date,
        type=tpl.type.value,
        title=title,
        scheduled_hour=body.scheduled_hour,
        is_draft=body.is_draft,
        notes=None,
        items=[
            TaskItemBody(book_id=it.book_id, section_id=it.book_section_id, planned_count=it.planned_count)
            for it in tpl.items
        ],
    )
    try:
        task = _create_task_with_items(db, student=student, payload=payload)
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    db.refresh(task)
    return MutationResponse[TeacherTask](
        data=_build_teacher_task(db, task),
        invalidate=_invalidate_for_task(task, user.id),
    )


# ---------------------- PATCH /tasks/{task_id} ----------------------


@router.patch(
    "/tasks/{task_id}",
    response_model=MutationResponse[TeacherTask],
)
def teacher_patch_task_v2(
    task_id: int,
    body: TaskPatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Görev meta alanlarını güncelle (title/type/scheduled_hour/order/is_draft/notes).

    Kalem değişiklikleri burada YOK — dedicated endpoint'ler rezerv invariant'ını
    güvence altına alır.
    """
    task = _get_owned_task(db, task_id, user.id)

    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "invalid_title",
                    "message": "Başlık boş olamaz.",
                },
            )
        task.title = title
    if body.type is not None:
        try:
            task.type = TaskType(body.type)
        except ValueError:
            pass
    if body.scheduled_hour is not None:
        task.scheduled_hour = _validate_scheduled_hour(body.scheduled_hour)
    if body.period is not None:
        # Boş string ("") → period temizle (NULL).
        task.period = _validate_period(body.period if body.period else None)
    if body.order is not None:
        task.order = int(body.order)
    if body.is_draft is not None:
        task.is_draft = bool(body.is_draft)
    if body.notes is not None:
        task.notes = body.notes.strip() or None

    db.flush()
    db.commit()
    db.refresh(task)
    return MutationResponse[TeacherTask](
        data=_build_teacher_task(db, task),
        invalidate=_invalidate_for_task(task, user.id),
    )


# ---------------------- DELETE /tasks/{task_id} ----------------------


@router.delete(
    "/tasks/{task_id}",
    response_model=MutationResponse[dict],
)
def teacher_delete_task_v2(
    task_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Görevi sil — `planned - completed` kadar rezervi iade et."""
    task = _get_owned_task(db, task_id, user.id)
    invalidate = _invalidate_for_task(task, user.id)
    try:
        release_task_items(db, task.student_id, list(task.book_items))
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)
    db.delete(task)
    db.commit()
    return MutationResponse[dict](
        data={"deleted": True, "task_id": task_id},
        invalidate=invalidate,
    )


# ---------------------- POST /tasks/{task_id}/items ----------------------


@router.post(
    "/tasks/{task_id}/items",
    response_model=MutationResponse[TeacherTask],
)
def teacher_add_task_item_v2(
    task_id: int,
    body: TaskItemBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Mevcut göreve yeni kalem ekle (rezerv açar)."""
    task = _get_owned_task(db, task_id, user.id)
    _ensure_count_positive(body.planned_count)
    _ensure_section_belongs_to_book(db, body.book_id, body.section_id)
    _ensure_student_book_assigned(db, task.student_id, body.book_id)

    try:
        reserve_item(
            db,
            student_id=task.student_id,
            book_id=body.book_id,
            section_id=body.section_id,
            count=body.planned_count,
        )
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)

    db.add(TaskBookItem(
        task_id=task.id,
        book_id=body.book_id,
        book_section_id=body.section_id,
        planned_count=body.planned_count,
        completed_count=0,
    ))
    db.commit()
    db.refresh(task)
    return MutationResponse[TeacherTask](
        data=_build_teacher_task(db, task),
        invalidate=_invalidate_for_task(task, user.id),
    )


# ---------------------- POST /tasks/{task_id}/items/{item_id}/result ----------------------


def _teacher_validate_result_distribution(
    *,
    completed: int,
    correct: int | None,
    wrong: int | None,
    is_book_item: bool,
) -> None:
    """D/Y validation — birim duyarlı (öğrenci simetrisi).

    Kitaplı görev: completed = test sayısı; D/Y = soru sayısı (bağımsız) →
    sadece c ≥ 0, w ≥ 0.
    Kitapsız deneme: completed = soru; c + w ≤ completed.
    """
    c = correct if correct is not None else 0
    w = wrong if wrong is not None else 0
    if c < 0 or w < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation_error",
                "code": "invalid_result_distribution",
                "message": "Doğru ve yanlış sayıları negatif olamaz.",
            },
        )
    if not is_book_item and c + w > completed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation_error",
                "code": "invalid_result_distribution",
                "message": (
                    f"Doğru ({c}) + Yanlış ({w}) = {c + w}, çözülen "
                    f"({completed}) sorudan fazla olamaz."
                ),
            },
        )


@router.post(
    "/tasks/{task_id}/items/{item_id}/result",
    response_model=MutationResponse[TeacherTask],
)
def teacher_set_task_item_result_v2(
    task_id: int,
    item_id: int,
    body: TaskItemResultBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Koç bir görev kaleminin çözüldü + D/Y sonucunu düzenler.

    Öğrenci girmediyse veya yanlış girdiyse koç düzeltir. completed > planned →
    klamp (svc tarafında). correct + wrong ≤ completed (validation).

    Tutarlılık: svc_set_item_completion mevcut rezerv/section progress
    mantığını AYNEN uygular; D/Y opsiyonel parametre olarak iletilir.
    """
    task = _get_owned_task(db, task_id, user.id)
    item = next((i for i in task.book_items if i.id == item_id), None)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "item_not_found",
                "message": "Görev kalemi bulunamadı.",
            },
        )

    effective_completed = max(0, min(body.completed, item.planned_count))
    _teacher_validate_result_distribution(
        completed=effective_completed,
        correct=body.correct,
        wrong=body.wrong,
        is_book_item=item.book_id is not None,
    )

    try:
        svc_set_item_completion(
            db, item, body.completed, correct=body.correct, wrong=body.wrong
        )
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)

    # Görev status'ünü kalem toplamlarına göre yeniden değerlendir
    total_planned = sum(i.planned_count for i in task.book_items)
    total_done = sum(i.completed_count for i in task.book_items)
    if total_done == 0:
        task.status = TaskStatus.PENDING
        task.completed_at = None
    elif total_done >= total_planned:
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
    else:
        task.status = TaskStatus.PARTIAL
        task.completed_at = None

    db.commit()
    db.refresh(task)
    return MutationResponse[TeacherTask](
        data=_build_teacher_task(db, task),
        invalidate=_invalidate_for_task(task, user.id),
    )


# ---------------------- PATCH /tasks/{task_id}/items/{item_id} ----------------------


@router.patch(
    "/tasks/{task_id}/items/{item_id}",
    response_model=MutationResponse[TeacherTask],
)
def teacher_patch_task_item_v2(
    task_id: int,
    item_id: int,
    body: TaskItemPatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Kalemin planned_count'unu değiştir (delta'ya göre rezerv ekle/iade).

    Tamamlanmış kısma asla dokunulmaz — yeni planned ≥ completed olmalı.
    """
    task = _get_owned_task(db, task_id, user.id)
    item = next((i for i in task.book_items if i.id == item_id), None)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "item_not_found",
                "message": "Görev kalemi bulunamadı.",
            },
        )
    _ensure_count_positive(body.planned_count)
    if body.planned_count < item.completed_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "planned_below_completed",
                "message": (
                    f"Yeni sayı ({body.planned_count}) tamamlanan ({item.completed_count})'dan küçük olamaz."
                ),
            },
        )
    delta = body.planned_count - item.planned_count
    if delta == 0:
        return MutationResponse[TeacherTask](
            data=_build_teacher_task(db, task),
            invalidate=_invalidate_for_task(task, user.id),
        )

    try:
        if delta > 0:
            reserve_item(
                db,
                student_id=task.student_id,
                book_id=item.book_id,
                section_id=item.book_section_id,
                count=delta,
            )
        else:
            release_item(
                db,
                student_id=task.student_id,
                book_id=item.book_id,
                section_id=item.book_section_id,
                count=abs(delta),
            )
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)

    item.planned_count = body.planned_count
    db.commit()
    db.refresh(task)
    return MutationResponse[TeacherTask](
        data=_build_teacher_task(db, task),
        invalidate=_invalidate_for_task(task, user.id),
    )


# ---------------------- PATCH /tasks/{task_id}/single-item ----------------------


@router.patch(
    "/tasks/{task_id}/single-item",
    response_model=MutationResponse[TeacherTask],
)
def teacher_patch_task_single_item_v2(
    task_id: int,
    body: TaskSingleItemEditBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Tek kalemli görev için atomik düzenleme (Jinja `task_edit.html` parite).

    - Kalem sayısı ≠ 1 ise 422 `multi_item_task` (kalem ekle/sil için ayrı endpoint).
    - Kaynak (book/section) değişti AMA `completed_count > 0` ise 422
      `source_change_with_completed` (öğretmen önce çözülenleri sıfırlamalı).
    - `planned_count < item.completed_count` ise 422 `planned_below_completed`.
    - Aksi halde: eski kaynaktan `planned - completed` rezervi iade et, yeni
      kaynaktan gereken miktarı reserve_item ile aç, başlığı yeniden üret.
    """
    task = _get_owned_task(db, task_id, user.id)
    if len(task.book_items) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "multi_item_task",
                "message": (
                    "Bu endpoint tek kalemli görevler içindir. "
                    "Çok kalemli görevlerde POST /items + DELETE /items kullanın."
                ),
            },
        )
    item = task.book_items[0]

    new_date = _parse_iso_date(body.date)
    new_sched = _validate_scheduled_hour(body.scheduled_hour)
    try:
        new_type = TaskType(body.type)
    except ValueError:
        new_type = task.type

    _ensure_count_positive(body.planned_count)
    _ensure_section_belongs_to_book(db, body.book_id, body.section_id)
    _ensure_student_book_assigned(db, task.student_id, body.book_id)

    source_changed = (
        body.book_id != item.book_id or body.section_id != item.book_section_id
    )
    if source_changed and item.completed_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "source_change_with_completed",
                "message": (
                    f"Bu görevde {item.completed_count} test tamamlanmış; "
                    "kaynak değiştirilemez. Yeni görev oluşturup eskisini silebilirsiniz."
                ),
            },
        )
    if body.planned_count < item.completed_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "planned_below_completed",
                "message": (
                    f"Yeni sayı ({body.planned_count}) tamamlanmış miktardan "
                    f"({item.completed_count}) küçük olamaz."
                ),
            },
        )

    # Rezerv dengeleme (Jinja edit_task.py:560-586 parite)
    try:
        old_pending = item.planned_count - item.completed_count
        if old_pending > 0:
            release_item(
                db,
                student_id=task.student_id,
                book_id=item.book_id,
                section_id=item.book_section_id,
                count=old_pending,
            )
        new_pending = body.planned_count - (
            item.completed_count if not source_changed else 0
        )
        if new_pending > 0:
            reserve_item(
                db,
                student_id=task.student_id,
                book_id=body.book_id,
                section_id=body.section_id,
                count=new_pending,
            )
    except ReservationError as e:
        db.rollback()
        raise _reservation_to_http(e)

    # Item'ı güncelle
    item.book_id = body.book_id
    item.book_section_id = body.section_id
    item.planned_count = body.planned_count
    if source_changed:
        item.completed_count = 0  # kaynak değişti → eski tamamlama anlamsız

    # Task meta güncelle
    task.date = new_date
    task.type = new_type
    task.scheduled_hour = new_sched
    task.notes = (body.notes or "").strip() or None
    task.link_url = (body.link_url or "").strip() or None

    # Başlığı otomatik üret (oluşturma ile paylaşılan helper — book.type'a göre
    # "test" / "deneme")
    new_book = db.query(Book).filter(Book.id == body.book_id).first()
    new_section = db.query(BookSection).filter(BookSection.id == body.section_id).first()
    if new_book and new_section:
        task.title = _compose_single_item_title(new_book, new_section, body.planned_count)

    db.commit()
    db.refresh(task)
    return MutationResponse[TeacherTask](
        data=_build_teacher_task(db, task),
        invalidate=_invalidate_for_task(task, user.id),
    )


# ---------------------- POST /students/{id}/bulk-tasks ----------------------


MAX_BULK_TASKS = 20


@router.post(
    "/students/{student_id}/bulk-tasks",
    response_model=MutationResponse[BulkResult],
)
def teacher_bulk_tasks_v2(
    student_id: int,
    body: BulkTasksBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Atomik bulk task oluşturma — "Haftaya yay" akışı.

    Sözleşme:
      - Max MAX_BULK_TASKS görev (default 20)
      - Tek bir hata (kapasite, geçersiz section, vb.) tüm batch'i geri çevirir
      - SAVEPOINT (db.begin_nested) — outer transaction rollback ile sağlama
    """
    student = _get_owned_student(db, student_id, user.id)
    assert_active_coaching(db, user)
    if not body.tasks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "no_tasks",
                "message": "En az bir görev gönderin.",
            },
        )
    if len(body.tasks) > MAX_BULK_TASKS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "too_many_tasks",
                "message": f"Tek seferde en fazla {MAX_BULK_TASKS} görev gönderebilirsiniz.",
            },
        )

    created_ids: list[int] = []
    # Atomik: tek bir savepoint, ilk hata → rollback, hiçbir görev kalmaz.
    sp = db.begin_nested()
    try:
        for payload in body.tasks:
            t = _create_task_with_items(db, student=student, payload=payload)
            created_ids.append(t.id)
        sp.commit()
    except ReservationError as e:
        sp.rollback()
        raise _reservation_to_http(e)
    except HTTPException:
        sp.rollback()
        raise
    except Exception:
        sp.rollback()
        raise

    db.commit()
    invalidate = [
        f"teacher:{user.id}:students:{student.id}:day",
        f"teacher:{user.id}:students:{student.id}:week",
        f"teacher:{user.id}:students:{student.id}:summary",
        f"teacher:{user.id}:dashboard",
        f"student:{student.id}:day",
        f"student:{student.id}:sidebar",
    ]
    return MutationResponse[BulkResult](
        data=BulkResult(created_count=len(created_ids), task_ids=created_ids),
        invalidate=invalidate,
    )


# =============================================================================
# Paket 3 — Talep Yanıtlama (öğretmen perspektifi)
# =============================================================================


_REQ_TYPE_VALUES = {"change", "replace", "remove", "question", "add"}
_REQ_STATUS_VALUES = {"pending", "approved", "rejected", "withdrawn", "resolved"}


def _get_owned_request(
    db: Session, request_id: int, teacher_id: int,
) -> TaskRequest:
    """Talep öğretmene aitse yükle, değilse 404 (varlık sızdırılmaz)."""
    req = (
        db.query(TaskRequest)
        .options(
            joinedload(TaskRequest.student),
            joinedload(TaskRequest.task).joinedload(Task.book_items)
                .joinedload(TaskBookItem.book),
            joinedload(TaskRequest.task).joinedload(Task.book_items)
                .joinedload(TaskBookItem.section).joinedload(BookSection.topic),
            joinedload(TaskRequest.proposed_book),
            joinedload(TaskRequest.proposed_section),
        )
        .filter(
            TaskRequest.id == request_id,
            TaskRequest.teacher_id == teacher_id,
        )
        .first()
    )
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "request_not_found",
                "message": "Talep bulunamadı.",
            },
        )
    return req


def _build_request_list_item(req: TaskRequest) -> TeacherRequestListItem:
    return TeacherRequestListItem(
        id=req.id,
        student_id=req.student_id,
        student_name=req.student.full_name if req.student else "—",
        type=req.type.value,
        status=req.status.value,
        task_id=req.task_id,
        # Task silindiyse (REMOVE onaylanmış) snapshot'tan göster — audit izi
        task_title=(req.task.title if req.task else req.task_title_snapshot),
        task_date=(
            req.task.date.isoformat() if req.task
            else (req.task_date_snapshot.isoformat() if req.task_date_snapshot else None)
        ),
        message=req.message,
        proposed_count=req.proposed_count,
        proposed_date=req.proposed_date.isoformat() if req.proposed_date else None,
        teacher_response=req.teacher_response,
        created_at=req.created_at,
        responded_at=req.responded_at,
    )


def _build_request_detail(db: Session, req: TaskRequest) -> TeacherRequestDetail:
    """Diff için mevcut task'ın kalemlerini de döndür."""
    current_items: list[TeacherTaskItem] = []
    if req.task and req.task.book_items:
        section_ids = [it.book_section_id for it in req.task.book_items]
        sp_map = _section_progress_map(db, req.task.student_id, section_ids)
        current_items = [
            _build_teacher_task_item(it, sp_map) for it in req.task.book_items
        ]
    return TeacherRequestDetail(
        id=req.id,
        student_id=req.student_id,
        student_name=req.student.full_name if req.student else "—",
        student_email=req.student.email if req.student else "",
        type=req.type.value,
        status=req.status.value,
        task_id=req.task_id,
        # Task silindiyse (REMOVE onaylanmış) snapshot'tan göster — audit izi
        task_title=(req.task.title if req.task else req.task_title_snapshot),
        task_date=(
            req.task.date.isoformat() if req.task
            else (req.task_date_snapshot.isoformat() if req.task_date_snapshot else None)
        ),
        message=req.message,
        teacher_response=req.teacher_response,
        proposed_book_id=req.proposed_book_id,
        proposed_book_name=req.proposed_book.name if req.proposed_book else None,
        proposed_section_id=req.proposed_section_id,
        proposed_section_label=req.proposed_section.label if req.proposed_section else None,
        proposed_count=req.proposed_count,
        proposed_date=req.proposed_date.isoformat() if req.proposed_date else None,
        current_items=current_items,
        created_at=req.created_at,
        updated_at=req.updated_at,
        responded_at=req.responded_at,
    )


def _invalidate_for_request(
    req: TaskRequest, teacher_id: int, *, affected_date: date | None = None,
) -> list[str]:
    """Talep mutasyonu invalidate listesi — öğretmen+öğrenci her iki perspektif.

    affected_date: approve sonrası etkilenen task'ın tarihi (eski/yeni). Verildiyse
    o günün view'ı da invalidate edilir.
    """
    sid = req.student_id
    keys = [
        # Öğretmen
        f"teacher:{teacher_id}:requests",
        f"teacher:{teacher_id}:requests:{req.id}",
        f"teacher:{teacher_id}:badges",
        f"teacher:{teacher_id}:dashboard",
        f"teacher:{teacher_id}:students:{sid}:summary",
        # Öğrenci tarafı (talep eden)
        f"student:{sid}:requests",
        f"badges:student:{sid}:pending",
    ]
    # Mevcut göreve referans varsa o günün viewları da bayatlar
    if req.task and req.task.date:
        d = req.task.date.isoformat()
        keys.append(f"teacher:{teacher_id}:students:{sid}:day:{d}")
        keys.append(f"teacher:{teacher_id}:students:{sid}:week")
        keys.append(f"student:{sid}:day:{d}")
        keys.append(f"student:{sid}:summary:{d}")
    # Talep önerilen yeni tarih veya approve sonrası başka bir tarih etkiliyorsa
    if req.proposed_date:
        d = req.proposed_date.isoformat()
        keys.append(f"teacher:{teacher_id}:students:{sid}:day:{d}")
        keys.append(f"student:{sid}:day:{d}")
    if affected_date is not None:
        d = affected_date.isoformat()
        if f"teacher:{teacher_id}:students:{sid}:day:{d}" not in keys:
            keys.append(f"teacher:{teacher_id}:students:{sid}:day:{d}")
            keys.append(f"student:{sid}:day:{d}")
    return keys


def _request_error_to_http(e: RequestError) -> HTTPException:
    """RequestError → 422 (öğretmen perspektifi). Mesaj kullanıcıya gösterilir."""
    msg = str(e)
    code = "request_invalid"
    upper = msg.upper()
    if "KAPASITE" in upper or "KAPASİTE" in upper or "REZERV" in upper:
        code = "RESERVE_OVER_CAPACITY"
    elif "BEKLEYEN TALEPLER" in upper or "ZATEN" in upper:
        code = "request_state_invalid"
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "validation",
            "code": code,
            "message": msg,
        },
    )


# ---------------------- GET /requests (liste) ----------------------


@router.get("/requests", response_model=TeacherRequestListResponse)
def teacher_list_requests_v2(
    status_filter: str | None = Query(None, alias="status"),
    type_filter: str | None = Query(None, alias="type"),
    student_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmenin tüm öğrencilerinin talepleri.

    Filtreler:
      - status: pending (default) / approved / rejected / withdrawn / resolved / all
      - type:   change / replace / remove / question / add / all
      - student_id: belirli bir öğrencinin taleplerini izole et
    Sıralama: created_at desc.
    """
    q = (
        db.query(TaskRequest)
        .options(
            joinedload(TaskRequest.student),
            joinedload(TaskRequest.task),
        )
        .filter(TaskRequest.teacher_id == user.id)
    )

    # Status — default pending; "all" tümü
    if status_filter is None or status_filter == "":
        q = q.filter(TaskRequest.status == RequestStatus.PENDING)
    elif status_filter == "all":
        pass
    elif status_filter in _REQ_STATUS_VALUES:
        try:
            st = RequestStatus(status_filter)
            q = q.filter(TaskRequest.status == st)
        except ValueError:
            pass

    # Type
    if type_filter and type_filter != "all":
        if type_filter in _REQ_TYPE_VALUES:
            try:
                tp = RequestType(type_filter)
                q = q.filter(TaskRequest.type == tp)
            except ValueError:
                pass

    # Belirli öğrenci — sahiplik kontrolü: cross-tenant id verilirse boş döner
    if student_id is not None:
        q = q.filter(TaskRequest.student_id == student_id)

    total = q.count()
    rows = (
        q.order_by(TaskRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_build_request_list_item(r) for r in rows]
    pending = pending_count_for_teacher(db, user.id)
    end = page * page_size
    return TeacherRequestListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=end < total,
        pending_count=pending,
    )


# ---------------------- GET /requests/{id} (detay) ----------------------


@router.get(
    "/requests/{request_id}",
    response_model=TeacherRequestDetail,
)
def teacher_request_detail_v2(
    request_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Talep tam detay — mevcut görev kalemleri ile birlikte diff için."""
    req = _get_owned_request(db, request_id, user.id)
    return _build_request_detail(db, req)


# ---------------------- POST /requests/{id}/approve ----------------------


@router.post(
    "/requests/{request_id}/approve",
    response_model=MutationResponse[TeacherRequestDetail],
)
def teacher_approve_request_v2(
    request_id: int,
    body: RequestApproveBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Talebi onayla — request_service.approve_request mevcut uygulamayı yürütür.

    Defansif kapsül: tüm uygulama bir SAVEPOINT içinde; kapasite ihlali (R-024)
    veya başka RequestError olursa rollback yapılır ve talep PENDING kalır.
    """
    req = _get_owned_request(db, request_id, user.id)
    if req.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "already_answered",
                "message": "Bu talep zaten yanıtlanmış.",
            },
        )

    affected_date: date | None = None
    sp = db.begin_nested()
    try:
        affected_task = svc_approve_request(
            db, teacher=user, req=req, response=body.response,
        )
        if affected_task is not None:
            affected_date = affected_task.date
        sp.commit()
    except RequestError as e:
        sp.rollback()
        raise _request_error_to_http(e)
    except HTTPException:
        sp.rollback()
        raise
    except Exception:
        sp.rollback()
        raise
    db.commit()
    db.refresh(req)
    return MutationResponse[TeacherRequestDetail](
        data=_build_request_detail(db, req),
        invalidate=_invalidate_for_request(req, user.id, affected_date=affected_date),
    )


# ---------------------- POST /requests/{id}/reject ----------------------


@router.post(
    "/requests/{request_id}/reject",
    response_model=MutationResponse[TeacherRequestDetail],
)
def teacher_reject_request_v2(
    request_id: int,
    body: RequestRejectBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Talebi reddet — `reason` zorunlu (boş ≠ valid), veri değiştirmez."""
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "reason_required",
                "message": "Red gerekçesi boş olamaz.",
            },
        )
    req = _get_owned_request(db, request_id, user.id)
    if req.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "already_answered",
                "message": "Bu talep zaten yanıtlanmış.",
            },
        )
    try:
        svc_reject_request(db, teacher=user, req=req, response=reason)
        db.commit()
    except RequestError as e:
        db.rollback()
        raise _request_error_to_http(e)
    db.refresh(req)
    return MutationResponse[TeacherRequestDetail](
        data=_build_request_detail(db, req),
        invalidate=_invalidate_for_request(req, user.id),
    )


# ---------------------- POST /requests/{id}/respond ----------------------


@router.post(
    "/requests/{request_id}/respond",
    response_model=MutationResponse[TeacherRequestDetail],
)
def teacher_respond_request_v2(
    request_id: int,
    body: RequestRespondBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """QUESTION tipindeki talebe cevap yaz — status RESOLVED'a geçer."""
    response_text = (body.response or "").strip()
    if not response_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "response_required",
                "message": "Cevap boş olamaz.",
            },
        )
    req = _get_owned_request(db, request_id, user.id)
    if req.type != RequestType.QUESTION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "respond_only_for_question",
                "message": "Sadece soru tipindeki talepler için cevap yazılır.",
            },
        )
    if req.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "already_answered",
                "message": "Bu talep zaten yanıtlanmış.",
            },
        )
    try:
        svc_respond_question(db, teacher=user, req=req, response=response_text)
        db.commit()
    except RequestError as e:
        db.rollback()
        raise _request_error_to_http(e)
    db.refresh(req)
    return MutationResponse[TeacherRequestDetail](
        data=_build_request_detail(db, req),
        invalidate=_invalidate_for_request(req, user.id),
    )


# =============================================================================
# Paket 4 — Students CRUD (öğrenci yönetimi)
# =============================================================================


_PARENT_RELATION_VALUES = {"anne", "baba", "vasi", "diger"}


def _gen_temp_password(n: int = 10) -> str:
    alphabet = _string_mod.ascii_letters + _string_mod.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _parse_track(v: str | None) -> Track | None:
    if not v:
        return None
    try:
        return Track(v)
    except ValueError:
        return None


def _parse_graduate_mode(v: str | None) -> GraduateMode | None:
    if not v:
        return None
    try:
        return GraduateMode(v)
    except ValueError:
        return None


def _validation_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error": "validation", "code": code, "message": message},
    )


def _check_student_creation_quota(
    db: Session, teacher: User,
) -> None:
    """Plan kotası kontrolü — kurumlu öğretmen için institution quota, solo
    öğretmen için plan-bazlı solo quota. Aşımda HTTPException 422 fırlatılır.
    """
    # Ödeme duvarı: deneme bitip limit aşılmış / abonelik past_due ise yeni
    # öğrenci eklemek de aktif koçluk sayılır → 403 (program/görev ile tutarlı).
    assert_active_coaching(db, teacher)
    # Kurumsal
    if teacher.institution_id is not None and teacher.institution is not None:
        from app.services.quotas import (
            QuotaExceeded,
            check_quota_for_create,
        )
        try:
            check_quota_for_create(
                db, institution=teacher.institution, quota_key="students",
            )
        except QuotaExceeded as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "plan_quota_exceeded",
                    "message": e.message,
                    "details": {
                        "limit": e.limit,
                        "current": e.current,
                        "scope": "institution",
                    },
                },
            )
        return

    # Solo
    if teacher.institution_id is None and teacher.role == UserRole.TEACHER:
        from app.services.plans import check_solo_student_quota
        result = check_solo_student_quota(db, teacher=teacher, extra_count=1)
        if not result.ok:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "plan_quota_exceeded",
                    "message": (
                        f"{result.plan_label} planında en fazla {result.limit} aktif "
                        "öğrenci bulundurabilirsiniz."
                    ),
                    "details": {
                        "limit": result.limit,
                        "current": result.current,
                        "scope": "solo",
                        "upgrade_target": result.upgrade_target_code,
                    },
                },
            )


def _invalidate_for_students(teacher_id: int, student_id: int | None = None) -> list[str]:
    keys = [
        f"teacher:{teacher_id}:students",
        f"teacher:{teacher_id}:dashboard",
        f"teacher:{teacher_id}:badges",
        f"teacher:{teacher_id}:me",
    ]
    if student_id is not None:
        keys.append(f"teacher:{teacher_id}:students:{student_id}")
        keys.append(f"teacher:{teacher_id}:students:{student_id}:summary")
        keys.append(f"teacher:{teacher_id}:students:{student_id}:books")
        keys.append(f"teacher:{teacher_id}:students:{student_id}:parents")
    return keys


# ---------------------- POST /teacher/students ----------------------


@router.post("/students", response_model=MutationResponse[StudentCreateResult])
def teacher_create_student_v2(
    body: StudentCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Yeni öğrenci oluştur — geçici şifre döner.

    İş kuralları:
      - Email unique (case-insensitive); çakışma 409 email_taken
      - Plan/kurum kotası kontrolü (kurumlu/solo)
      - 11+ veya is_graduate=True → track zorunlu
      - is_graduate=True → graduate_mode zorunlu
      - academic_year_id verilirse öğretmenin sahibi olmalı
    """
    full_name = (body.full_name or "").strip()
    email = (body.email or "").strip().lower()
    if not full_name:
        raise _validation_error("full_name_required", "Ad Soyad zorunlu.")
    if "@" not in email or len(email) < 5:
        raise _validation_error("invalid_email", "Geçerli bir e-posta girin.")
    if body.grade_level is not None and not (5 <= body.grade_level <= 12):
        raise _validation_error("invalid_grade", "Sınıf 5-12 aralığında olmalı.")

    # Track / graduate_mode iş kuralı
    grade = body.grade_level
    is_graduate = bool(body.is_graduate)
    if is_graduate:
        grade = None
    track_required = is_graduate or (grade is not None and grade >= 11)
    track_enum = _parse_track(body.track)
    if track_required and track_enum is None:
        raise _validation_error(
            "track_required",
            "11. sınıf, 12. sınıf ve mezunlar için alan zorunlu.",
        )
    grad_mode_enum: GraduateMode | None = None
    if is_graduate:
        grad_mode_enum = _parse_graduate_mode(body.graduate_mode)
        if grad_mode_enum is None:
            raise _validation_error(
                "graduate_mode_required",
                "Mezun öğrenciler için çalışma şekli zorunlu.",
            )

    # Email çakışma — case-insensitive
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "email_taken",
                "message": "Bu e-posta zaten kayıtlı.",
            },
        )

    # Akademik yıl sahiplik
    parsed_year_id: int | None = None
    if body.academic_year_id is not None:
        owns = (
            db.query(AcademicYear.id)
            .filter(
                AcademicYear.id == body.academic_year_id,
                AcademicYear.teacher_id == user.id,
            )
            .first()
        )
        if not owns:
            raise _validation_error(
                "invalid_academic_year",
                "Akademik yıl bulunamadı veya size ait değil.",
            )
        parsed_year_id = body.academic_year_id

    # Kota kontrolü — exception fırlatır
    _check_student_creation_quota(db, user)

    # Yarat
    from app.services.security import hash_password
    temp_pw = _gen_temp_password()
    student = User(
        email=email,
        password_hash=hash_password(temp_pw),
        full_name=full_name,
        role=UserRole.STUDENT,
        teacher_id=user.id,
        institution_id=user.institution_id,
        academic_year_id=parsed_year_id,
        grade_level=grade,
        is_graduate=is_graduate,
        track=track_enum,
        graduate_mode=grad_mode_enum,
        must_change_password=True,  # ilk girişte geçici parolayı değiştirmek ZORUNLU
    )
    db.add(student)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(student)

    return MutationResponse[StudentCreateResult](
        data=StudentCreateResult(
            id=student.id,
            full_name=student.full_name,
            email=student.email,
            grade_level=student.grade_level,
            is_graduate=bool(student.is_graduate),
            is_active=bool(student.is_active),
            temp_password=temp_pw,
        ),
        invalidate=_invalidate_for_students(user.id),
    )


# ---------------------- PATCH /teacher/students/{id} ----------------------


@router.patch(
    "/students/{student_id}",
    response_model=MutationResponse[StudentBriefProfile],
)
def teacher_patch_student_v2(
    student_id: int,
    body: StudentPatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenci profil alanları — None olanlar değişmez.

    Track/graduate_mode iş kuralı yine geçerli: yeni hedef sınıf 11+/mezun ise
    track zorunlu kalır.
    """
    student = _get_owned_student(db, student_id, user.id)

    new_full_name = student.full_name
    if body.full_name is not None:
        nn = body.full_name.strip()
        if not nn:
            raise _validation_error("full_name_required", "Ad Soyad boş olamaz.")
        new_full_name = nn

    new_is_graduate = bool(student.is_graduate) if body.is_graduate is None else bool(body.is_graduate)
    new_grade = student.grade_level if body.grade_level is None else body.grade_level
    if new_is_graduate:
        new_grade = None
    if new_grade is not None and not (5 <= new_grade <= 12):
        raise _validation_error("invalid_grade", "Sınıf 5-12 aralığında olmalı.")

    new_track = student.track
    if body.track is not None:
        new_track = _parse_track(body.track) or new_track
    elif body.is_graduate is not None or body.grade_level is not None:
        # field belirtilmedi ama mevcut değeri koru
        pass

    new_grad_mode = student.graduate_mode
    if body.graduate_mode is not None:
        new_grad_mode = _parse_graduate_mode(body.graduate_mode)

    track_required = new_is_graduate or (new_grade is not None and new_grade >= 11)
    if track_required and new_track is None:
        raise _validation_error(
            "track_required",
            "11. sınıf, 12. sınıf ve mezunlar için alan zorunlu.",
        )
    if new_is_graduate and new_grad_mode is None:
        raise _validation_error(
            "graduate_mode_required",
            "Mezun öğrenciler için çalışma şekli zorunlu.",
        )

    new_year_id = student.academic_year_id
    if body.academic_year_id is not None:
        owns = (
            db.query(AcademicYear.id)
            .filter(
                AcademicYear.id == body.academic_year_id,
                AcademicYear.teacher_id == user.id,
            )
            .first()
        )
        if not owns:
            raise _validation_error(
                "invalid_academic_year",
                "Akademik yıl bulunamadı veya size ait değil.",
            )
        new_year_id = body.academic_year_id

    # Email değişimi — opsiyonel. Boş string atılırsa "değişmedi" sayılır
    # (Pydantic str | None None ise zaten None). Format + uniqueness kontrolü.
    new_email = student.email
    if body.email is not None:
        candidate = body.email.strip().lower()
        if not candidate:
            # Boş string = "değişme" — sessizce yok say
            pass
        elif candidate != student.email.lower():
            # Basit format kontrolü (Pydantic EmailStr eklemiyoruz çünkü
            # diğer alanlarla simetri için str — burada elle doğrula).
            if "@" not in candidate or "." not in candidate.split("@")[-1]:
                raise _validation_error(
                    "invalid_email", "Geçersiz e-posta adresi."
                )
            # Çakışma: başka kullanıcı bu email'i kullanıyor mu?
            existing = (
                db.query(User.id)
                .filter(
                    User.email == candidate,
                    User.id != student.id,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "conflict",
                        "code": "email_taken",
                        "message": "Bu e-posta başka bir hesap tarafından kullanılıyor.",
                    },
                )
            new_email = candidate

    # Email değişimi etkisi: doğrulama sıfırla (koç değiştiriyor → öğrenci
    # yeni adresi doğrulasın). pwd_stamp'a dokunulmaz — oturum kesilmez.
    email_changed = new_email != student.email
    student.full_name = new_full_name
    student.email = new_email
    if email_changed:
        student.email_verified_at = None
    student.grade_level = new_grade
    student.is_graduate = new_is_graduate
    student.track = new_track
    student.graduate_mode = new_grad_mode if new_is_graduate else None
    student.academic_year_id = new_year_id

    db.commit()
    db.refresh(student)
    return MutationResponse[StudentBriefProfile](
        data=_build_brief_profile(student),
        invalidate=_invalidate_for_students(user.id, student.id),
    )


# ---------------------- POST /deactivate ve /reactivate ----------------------


@router.post(
    "/students/{student_id}/deactivate",
    response_model=MutationResponse[StudentBriefProfile],
)
def teacher_deactivate_student_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenciyi pasif yap. is_active=False → kota sayımına dahil edilmez."""
    student = _get_owned_student(db, student_id, user.id)
    if not student.is_active:
        return MutationResponse[StudentBriefProfile](
            data=_build_brief_profile(student),
            invalidate=_invalidate_for_students(user.id, student.id),
        )
    student.is_active = False
    db.commit()
    db.refresh(student)
    return MutationResponse[StudentBriefProfile](
        data=_build_brief_profile(student),
        invalidate=_invalidate_for_students(user.id, student.id),
    )


@router.post(
    "/students/{student_id}/reactivate",
    response_model=MutationResponse[StudentBriefProfile],
)
def teacher_reactivate_student_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenciyi aktif yap. Kota kontrolü uygulanır (pasiften aktife geçişi
    yeni kayıt gibi say)."""
    student = _get_owned_student(db, student_id, user.id)
    if student.is_active:
        return MutationResponse[StudentBriefProfile](
            data=_build_brief_profile(student),
            invalidate=_invalidate_for_students(user.id, student.id),
        )
    _check_student_creation_quota(db, user)
    student.is_active = True
    db.commit()
    db.refresh(student)
    return MutationResponse[StudentBriefProfile](
        data=_build_brief_profile(student),
        invalidate=_invalidate_for_students(user.id, student.id),
    )


# ---------------------- DELETE /teacher/students/{id} ----------------------


@router.delete(
    "/students/{student_id}",
    response_model=MutationResponse[dict],
)
def teacher_delete_student_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenciyi tamamen sil — sadece tarihçesi YOKSA.

    Bloklayan koşullar (409 has_history):
      - Task sayısı > 0
      - TaskRequest sayısı > 0
    """
    student = _get_owned_student(db, student_id, user.id)

    task_count = (
        db.query(func.count(Task.id))
        .filter(Task.student_id == student.id)
        .scalar() or 0
    )
    request_count = (
        db.query(func.count(TaskRequest.id))
        .filter(TaskRequest.student_id == student.id)
        .scalar() or 0
    )
    if task_count > 0 or request_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "has_history",
                "message": (
                    "Bu öğrencinin geçmiş kayıtları var (görev/talep). "
                    "Önce 'pasifleştir' kullanın."
                ),
                "details": {
                    "task_count": int(task_count),
                    "request_count": int(request_count),
                },
            },
        )

    db.delete(student)
    db.commit()
    return MutationResponse[dict](
        data={"deleted": True, "student_id": student_id},
        invalidate=_invalidate_for_students(user.id, student_id),
    )


# ---------------------- GET /teacher/students/{id}/books ----------------------


def _student_book_summary(
    db: Session, sb: StudentBook,
) -> StudentBookListItem:
    from app.models.book import BOOK_TYPE_LABELS

    book = sb.book
    sections = (
        db.query(BookSection)
        .options(joinedload(BookSection.topic))
        .filter(BookSection.book_id == sb.book_id)
        .order_by(BookSection.order, BookSection.id)
        .all()
    )
    section_ids = [s.id for s in sections]
    sp_rows = (
        db.query(SectionProgress)
        .filter(
            SectionProgress.student_book_id == sb.id,
            SectionProgress.book_section_id.in_(section_ids),
        )
        .all()
    ) if section_ids else []
    sp_by_section = {p.book_section_id: p for p in sp_rows}
    reserved_total = sum(p.reserved_count for p in sp_rows)
    completed_total = sum(p.completed_count for p in sp_rows)
    section_total_tests = sum(s.test_count for s in sections)

    section_rows: list[StudentBookSectionProgressRow] = []
    for s in sections:
        sp = sp_by_section.get(s.id)
        section_rows.append(StudentBookSectionProgressRow(
            section_id=s.id,
            label=s.label,
            order=s.order,
            topic_id=s.topic_id,
            topic_name=s.topic.name if s.topic else None,
            test_count=s.test_count,
            completed_count=sp.completed_count if sp else 0,
            reserved_count=sp.reserved_count if sp else 0,
        ))

    book_type = book.type if book and book.type else None
    subject = book.subject if book else None

    return StudentBookListItem(
        student_book_id=sb.id,
        book_id=sb.book_id,
        book_name=book.name if book else "—",
        book_type=(book_type.value if book_type else "soru_bankasi"),
        book_type_label_tr=(BOOK_TYPE_LABELS.get(book_type, "—") if book_type else "—"),
        publisher=(book.publisher if book else None),
        subject_id=(subject.id if subject else 0),
        subject_name=(subject.name if subject else "Diğer"),
        section_count=len(sections),
        section_total_tests=section_total_tests,
        section_reserved_total=reserved_total,
        section_completed_total=completed_total,
        has_reservations=(reserved_total > 0),
        sections=section_rows,
    )


@router.get(
    "/students/{student_id}/books",
    response_model=StudentBookListResponse,
)
def teacher_student_books_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(db, student_id, user.id)
    sbs = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.book).joinedload(Book.subject))
        .filter(StudentBook.student_id == student.id)
        .all()
    )
    items = [_student_book_summary(db, sb) for sb in sbs]
    # Ders adına, ardından kitap adına göre — frontend gruplama bunu varsayar
    items.sort(key=lambda x: (x.subject_name.lower(), x.book_name.lower()))
    return StudentBookListResponse(items=items, total=len(items))


@router.post(
    "/students/{student_id}/books/{student_book_id}/sections/{section_id}/completed",
    response_model=MutationResponse[StudentBookListItem],
)
def teacher_set_section_completed_v2(
    student_id: int,
    student_book_id: int,
    section_id: int,
    body: SectionCompletedBaselineBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Bir bölümü 'öğrenci zaten çözmüş' olarak işaretle (geçmiş yıl baseline).

    completed_count'u DOĞRUDAN set eder (görev gerektirmez); o bölümün kalanı
    (test − rezerv − tamam) düşer → programda bir daha atanmaz. completed_count=0
    işareti kaldırır. Üst sınır = test_count − reserved_count (aktif rezerv korunur).
    """
    student = _get_owned_student(db, student_id, user.id)
    sb = (
        db.query(StudentBook)
        .filter(StudentBook.id == student_book_id, StudentBook.student_id == student.id)
        .first()
    )
    if not sb:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "student_book_not_found",
                    "message": "Bu öğrenciye ait kitap bulunamadı."},
        )
    section = (
        db.query(BookSection)
        .filter(BookSection.id == section_id, BookSection.book_id == sb.book_id)
        .first()
    )
    if not section:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "section_not_found",
                    "message": "Bölüm bu kitaba ait değil."},
        )
    sp = (
        db.query(SectionProgress)
        .filter(SectionProgress.student_book_id == sb.id,
                SectionProgress.book_section_id == section_id)
        .first()
    )
    if not sp:
        sp = SectionProgress(
            student_book_id=sb.id, book_section_id=section_id,
            reserved_count=0, completed_count=0,
        )
        db.add(sp)
        db.flush()
    max_allowed = max(0, int(section.test_count or 0) - int(sp.reserved_count or 0))
    if body.completed_count > max_allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "exceeds_available",
                    "message": (f"En fazla {max_allowed} test işaretlenebilir "
                                f"(bölüm {section.test_count} test, {sp.reserved_count} rezerv).")},
        )
    sp.completed_count = body.completed_count
    db.commit()
    db.refresh(sb)
    return MutationResponse[StudentBookListItem](
        data=_student_book_summary(db, sb),
        invalidate=_invalidate_for_students(user.id, student.id) + [
            f"teacher:{user.id}:students:{student.id}:books",
        ],
    )


# ---------------------- GET /students/{id}/books/{book_id}/grid (cinema-seat) ----------------------


@router.get(
    "/students/{student_id}/books/{book_id}/book-grid",
)
def teacher_student_book_grid_v2(
    student_id: int,
    book_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Sinema-koltuğu grid (öğretmen perspektifi).

    Eşdeğer Jinja: `app/routes/teacher_program.py` book-grid handler +
    `app/templates/teacher/partials/book_grid_content.html`. Her bölüm için
    test sayısı kadar hücre: DONE (çözüldü) / RESERVED (rezerv) / FREE (boş).
    """
    from app.routes.api_v2.schemas.student import (
        BookCell,
        BookGridResponse,
        BookSectionGrid,
    )
    from app.routes.teacher_program import build_book_grid_slots

    student = _get_owned_student(db, student_id, user.id)
    sb = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
        )
        .filter(StudentBook.student_id == student.id, StudentBook.book_id == book_id)
        .first()
    )
    if not sb:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "code": "book_not_assigned",
                "message": "Bu kitap bu öğrenciye atanmamış.",
            },
        )

    pmap = {p.book_section_id: p for p in sb.section_progress}
    section_ids = [sec.id for sec in sb.book.sections]
    slots_map = build_book_grid_slots(
        db, student.id, section_ids, teacher_student_id=student.id,
    )

    sections_data: list[BookSectionGrid] = []
    total_done = 0
    total_res = 0
    for sec in sb.book.sections:
        sp = pmap.get(sec.id)
        completed = sp.completed_count if sp else 0
        reserved = sp.reserved_count if sp else 0
        slots = slots_map.get(sec.id, {"completed": [], "reserved": []})
        done_slots = slots.get("completed", [])
        res_slots = slots.get("reserved", [])

        cells: list[BookCell] = []
        idx = 0
        for s in done_slots:
            idx += 1
            cells.append(BookCell(
                number=idx,
                state="DONE",
                task_id=s.get("task_id"),
                task_date=s.get("date"),
            ))
        for s in res_slots:
            idx += 1
            cells.append(BookCell(
                number=idx,
                state="RESERVED",
                task_id=s.get("task_id"),
                task_date=s.get("date"),
            ))
        while idx < sec.test_count:
            idx += 1
            cells.append(BookCell(number=idx, state="FREE"))

        sections_data.append(BookSectionGrid(
            section_id=sec.id,
            label=sec.label,
            topic_name=sec.topic.name if sec.topic else None,
            test_count=sec.test_count,
            completed=completed,
            reserved=reserved,
            cells=cells,
        ))
        total_done += completed
        total_res += reserved

    return BookGridResponse(
        student_book_id=sb.id,
        book_id=sb.book.id,
        book_name=sb.book.name,
        subject_name=sb.book.subject.name if sb.book.subject else "—",
        book_type=sb.book.type.value,
        total_tests=sb.book.total_tests,
        total_completed=total_done,
        total_reserved=total_res,
        sections=sections_data,
    )


# ---------------------- POST /teacher/students/{id}/books ----------------------


@router.post(
    "/students/{student_id}/books",
    response_model=MutationResponse[StudentBookListItem],
)
def teacher_assign_book_v2(
    student_id: int,
    body: StudentBookAssignBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Kitabı öğrenciye ata. Kitap öğretmenin sahibi olmalı; duplicate 409."""
    student = _get_owned_student(db, student_id, user.id)
    book = (
        db.query(Book)
        .options(joinedload(Book.sections))
        .filter(Book.id == body.book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "book_not_found",
                "message": "Kitap bulunamadı veya size ait değil.",
            },
        )

    # Duplicate?
    existing = (
        db.query(StudentBook.id)
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.book_id == book.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "already_assigned",
                "message": "Bu kitap zaten öğrenciye atanmış.",
            },
        )

    sb = StudentBook(student_id=student.id, book_id=book.id)
    db.add(sb)
    db.flush()
    for section in book.sections:
        db.add(SectionProgress(
            student_book_id=sb.id,
            book_section_id=section.id,
            reserved_count=0,
            completed_count=0,
        ))
    db.commit()
    db.refresh(sb)

    return MutationResponse[StudentBookListItem](
        data=_student_book_summary(db, sb),
        invalidate=_invalidate_for_students(user.id, student.id) + [
            f"teacher:{user.id}:students:{student.id}:books",
            f"teacher:{user.id}:library:books",
            f"teacher:{user.id}:library:book-sets",
        ],
    )


# ---------------------- POST /teacher/students/{id}/books/bulk ----------------------


@router.post(
    "/students/{student_id}/books/bulk",
    response_model=MutationResponse[StudentBookBulkAssignResult],
)
def teacher_assign_books_bulk_v2(
    student_id: int,
    body: StudentBookBulkAssignBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Birden fazla kitabı tek seferde öğrenciye ata (Jinja `/books/assign` paritesi).

    Davranış:
      - Öğretmenin sahibi olmayan id'ler `skipped_invalid_ids` listesinde döner.
      - Zaten atanmış olanlar `skipped_already_ids` listesinde döner.
      - Kalanlar oluşturulur (her section için 0-baseline SectionProgress).
      - Boş `book_ids` → 200 / 0 atama.
    """
    student = _get_owned_student(db, student_id, user.id)
    requested = list(dict.fromkeys(body.book_ids or []))  # dedupe, preserve order
    if not requested:
        return MutationResponse[StudentBookBulkAssignResult](
            data=StudentBookBulkAssignResult(
                assigned=[],
                assigned_count=0,
                skipped_already_ids=[],
                skipped_invalid_ids=[],
            ),
            invalidate=_invalidate_for_students(user.id, student.id) + [
                f"teacher:{user.id}:students:{student.id}:books",
            ],
        )

    valid_books = (
        db.query(Book)
        .options(joinedload(Book.sections))
        .filter(
            Book.teacher_id == user.id,
            Book.id.in_(requested),
        )
        .all()
    )
    valid_by_id = {b.id: b for b in valid_books}
    invalid_ids = [bid for bid in requested if bid not in valid_by_id]

    already = {
        row.book_id
        for row in db.query(StudentBook.book_id)
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.book_id.in_(list(valid_by_id.keys())) if valid_by_id else False,
        )
        .all()
    }
    already_ids = [bid for bid in requested if bid in already]

    created: list[StudentBook] = []
    for bid in requested:
        book = valid_by_id.get(bid)
        if not book or bid in already:
            continue
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb)
        db.flush()
        for section in book.sections:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=section.id,
                reserved_count=0,
                completed_count=0,
            ))
        created.append(sb)

    db.commit()
    for sb in created:
        db.refresh(sb)

    return MutationResponse[StudentBookBulkAssignResult](
        data=StudentBookBulkAssignResult(
            assigned=[_student_book_summary(db, sb) for sb in created],
            assigned_count=len(created),
            skipped_already_ids=already_ids,
            skipped_invalid_ids=invalid_ids,
        ),
        invalidate=_invalidate_for_students(user.id, student.id) + [
            f"teacher:{user.id}:students:{student.id}:books",
            f"teacher:{user.id}:library:books",
            f"teacher:{user.id}:library:book-sets",
        ],
    )


# ---------------------- DELETE /teacher/students/{id}/books/{book_id} ----------------------


@router.delete(
    "/students/{student_id}/books/{book_id}",
    response_model=MutationResponse[dict],
)
def teacher_unassign_book_v2(
    student_id: int,
    book_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Atamayı kaldır. Aktif rezerv (`reserved_count>0`) varsa 409 has_reservations."""
    student = _get_owned_student(db, student_id, user.id)
    sb = (
        db.query(StudentBook)
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.book_id == book_id,
        )
        .first()
    )
    if not sb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "assignment_not_found",
                "message": "Atama bulunamadı.",
            },
        )
    # Aktif rezerv varsa engelle
    has_reserved = (
        db.query(func.count(SectionProgress.id))
        .filter(
            SectionProgress.student_book_id == sb.id,
            SectionProgress.reserved_count > 0,
        )
        .scalar() or 0
    )
    if has_reserved > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "has_reservations",
                "message": (
                    "Bu kitapta açık görev rezervi var. Önce görevleri silin "
                    "veya tamamlayın."
                ),
            },
        )
    # Section progress kayıtlarını + sb'yi sil (cascade yoksa manuel)
    db.execute(
        SectionProgress.__table__.delete().where(
            SectionProgress.student_book_id == sb.id
        )
    )
    db.delete(sb)
    db.commit()
    return MutationResponse[dict](
        data={"unassigned": True, "book_id": book_id, "student_id": student_id},
        invalidate=_invalidate_for_students(user.id, student.id) + [
            f"teacher:{user.id}:students:{student.id}:books",
            f"teacher:{user.id}:library:books",
            f"teacher:{user.id}:library:book-sets",
        ],
    )


# ---------------------- GET /teacher/students/{id}/parents ----------------------


_PARENT_RELATION_LABEL_DEFAULT = "diger"


@router.get(
    "/students/{student_id}/parents",
    response_model=StudentParentsResponse,
)
def teacher_student_parents_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenciye bağlı veliler + bekleyen davetler."""
    student = _get_owned_student(db, student_id, user.id)
    links = (
        db.query(ParentStudentLink)
        .options(joinedload(ParentStudentLink.parent))
        .filter(ParentStudentLink.student_id == student.id)
        .all()
    )
    now_utc = datetime.now(timezone.utc)
    pending = (
        db.query(ParentInvitation)
        .filter(
            ParentInvitation.student_id == student.id,
            ParentInvitation.consumed_at.is_(None),
            ParentInvitation.expires_at > now_utc,
        )
        .order_by(ParentInvitation.created_at.desc())
        .all()
    )
    link_items = [
        ParentLinkItem(
            link_id=l.id,
            parent_id=l.parent_id,
            parent_email=l.parent.email if l.parent else "—",
            parent_full_name=l.parent.full_name if l.parent else "—",
            relation=l.relation.value,
            is_primary=bool(l.is_primary),
            muted=bool(l.muted),
            created_at=l.created_at,
        )
        for l in links
    ]
    pending_items = [
        PendingParentInvitation(
            invitation_id=p.id,
            invited_email=p.invited_email,
            relation=p.relation.value,
            is_primary=bool(p.is_primary),
            expires_at=p.expires_at,
            created_at=p.created_at,
        )
        for p in pending
    ]
    return StudentParentsResponse(
        links=link_items,
        pending_invitations=pending_items,
    )


# ---------------------- POST /teacher/students/{id}/parents ----------------------


@router.post(
    "/students/{student_id}/parents",
    response_model=MutationResponse[ParentInviteResult],
)
def teacher_invite_parent_v2(
    student_id: int,
    body: ParentInviteBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Veli davet et — mevcut Jinja akışıyla aynı service'i kullanır.

    Hata kodları:
      - invalid_email (422)
      - email_in_use_other_role (409) — başka rolde kullanıcı
      - already_invited (409) — açık davet var
      - already_linked (409) — zaten bağlı
    """
    student = _get_owned_student(db, student_id, user.id)
    email = (body.parent_email or "").strip().lower()
    if "@" not in email or len(email) < 5:
        raise _validation_error("invalid_email", "Geçerli bir e-posta girin.")

    relation_value = (body.relation or _PARENT_RELATION_LABEL_DEFAULT).lower()
    if relation_value not in _PARENT_RELATION_VALUES:
        relation_value = _PARENT_RELATION_LABEL_DEFAULT
    relation_enum = ParentRelation(relation_value)

    from app.services.parent_invitation import (
        can_register_parent_email,
        create_invitation,
        has_pending_invitation,
    )
    can_register, conflict_role = can_register_parent_email(db, email)
    if not can_register:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "email_in_use_other_role",
                "message": (
                    "Bu e-posta başka bir rolde kullanılıyor — veli olarak eklenemez."
                ),
                "details": {"conflict_role": conflict_role.value if conflict_role else None},
            },
        )
    if has_pending_invitation(db, invited_email=email, student_id=student.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "already_invited",
                "message": "Bu e-postaya açık bir davet zaten var.",
            },
        )
    # Mevcut bağ kontrolü
    parent_user = (
        db.query(User)
        .filter(User.email == email, User.role == UserRole.PARENT)
        .first()
    )
    if parent_user:
        existing_link = (
            db.query(ParentStudentLink.id)
            .filter(
                ParentStudentLink.parent_id == parent_user.id,
                ParentStudentLink.student_id == student.id,
            )
            .first()
        )
        if existing_link:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "conflict",
                    "code": "already_linked",
                    "message": "Bu veli öğrenciye zaten bağlı.",
                },
            )

    inv = create_invitation(
        db,
        invited_email=email,
        student_id=student.id,
        invited_by_id=user.id,
        relation=relation_enum,
        is_primary=bool(body.is_primary),
    )
    db.commit()
    db.refresh(inv)

    # Davet mailini gönder — Jinja akışıyla eşdeğer (teacher_parents.py:132-158).
    # Bu yoksa davet satırı DB'de durur ama veliye link asla ulaşmaz (gerçek bug).
    from app.services.email_service import notify_parent_invitation
    sent_ok = False
    try:
        sent_ok = notify_parent_invitation(
            inv,
            teacher=user,
            student=student,
            relation_label=PARENT_RELATION_LABELS[relation_enum],
        )
    except Exception:
        logger.exception("Veli davet maili gönderim hatası")
    db.add(NotificationLog(
        parent_id=user.id,  # henüz parent yok — KVKK izi için davet eden öğretmen
        student_id=student.id,
        kind=NotificationKind.INVITATION,
        channel=NotificationChannel.EMAIL,
        status=NotificationStatus.SENT if sent_ok else NotificationStatus.QUEUED,
        subject=f"Veli daveti: {student.full_name}",
        payload_json=None,
        external_id=None,
        sent_at=datetime.now(timezone.utc) if sent_ok else None,
    ))
    db.commit()

    return MutationResponse[ParentInviteResult](
        data=ParentInviteResult(
            invitation_id=inv.id,
            invited_email=inv.invited_email,
            expires_at=inv.expires_at,
        ),
        invalidate=_invalidate_for_students(user.id, student.id) + [
            f"teacher:{user.id}:students:{student.id}:parents",
        ],
    )


# ---------------------- DELETE /teacher/students/{id}/parents/{link_id} ----------------------


@router.delete(
    "/students/{student_id}/parents/{link_id}",
    response_model=MutationResponse[dict],
)
def teacher_unlink_parent_v2(
    student_id: int,
    link_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Veli bağlantısını kaldır (veli hesabı silinmez — başka çocuklarına bağ varsa korunur)."""
    student = _get_owned_student(db, student_id, user.id)
    link = (
        db.query(ParentStudentLink)
        .filter(
            ParentStudentLink.id == link_id,
            ParentStudentLink.student_id == student.id,
        )
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "link_not_found",
                "message": "Veli bağlantısı bulunamadı.",
            },
        )
    db.delete(link)
    db.commit()
    return MutationResponse[dict](
        data={"unlinked": True, "link_id": link_id, "student_id": student.id},
        invalidate=_invalidate_for_students(user.id, student.id) + [
            f"teacher:{user.id}:students:{student.id}:parents",
        ],
    )


# ---------------------- DELETE /teacher/students/{id}/parent-invitations/{inv_id} ----------------------


@router.delete(
    "/students/{student_id}/parent-invitations/{invitation_id}",
    response_model=MutationResponse[dict],
)
def teacher_revoke_parent_invitation_v2(
    student_id: int,
    invitation_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Bekleyen veli davetini geri çek (henüz kullanılmamış davet → satır silinir).
    Tüketilmiş (consumed_at dolu) davet 404 ile reddedilir — bağ zaten kurulmuş,
    veli bağlantısını kaldırmak için DELETE /parents/{link_id} kullanılır.
    """
    student = _get_owned_student(db, student_id, user.id)
    inv = (
        db.query(ParentInvitation)
        .filter(
            ParentInvitation.id == invitation_id,
            ParentInvitation.student_id == student.id,
            ParentInvitation.consumed_at.is_(None),
        )
        .first()
    )
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "invitation_not_found",
                "message": "Bekleyen davet bulunamadı (zaten kullanılmış veya silinmiş olabilir).",
            },
        )
    db.delete(inv)
    db.commit()
    return MutationResponse[dict](
        data={"revoked": True, "invitation_id": invitation_id, "student_id": student.id},
        invalidate=_invalidate_for_students(user.id, student.id) + [
            f"teacher:{user.id}:students:{student.id}:parents",
        ],
    )


# =============================================================================
# Paket 3.5c — Sınıf Yükselt (Promote)
# =============================================================================


_GRADE_CHOICES_5C: list[tuple[str, str]] = [
    ("5", "5. Sınıf"),
    ("6", "6. Sınıf"),
    ("7", "7. Sınıf"),
    ("8", "8. Sınıf (LGS)"),
    ("9", "9. Sınıf"),
    ("10", "10. Sınıf"),
    ("11", "11. Sınıf"),
    ("12", "12. Sınıf"),
    ("graduate", "Mezun (YKS hazırlık)"),
]
_TRACK_CHOICES_5C: list[tuple[str, str]] = [
    ("sayisal", "Sayısal"),
    ("ea", "Eşit Ağırlık"),
    ("sozel", "Sözel"),
    ("dil", "Dil"),
]
_GRADUATE_MODE_CHOICES_5C: list[tuple[str, str]] = [
    ("full_time", "Tam-zamanlı (okul yok)"),
    ("dershane", "Dershane / etüt merkezi"),
]


def _next_grade_5c(grade_level: int | None, is_graduate: bool) -> str:
    if is_graduate:
        return "graduate"
    if grade_level is None:
        return "8"
    if grade_level == 12:
        return "graduate"
    if 5 <= grade_level < 12:
        return str(grade_level + 1)
    return str(grade_level)


def _invalidate_for_student_detail(teacher_id: int, student_id: int) -> list[str]:
    return [
        f"teacher:{teacher_id}:students:{student_id}",
        f"teacher:{teacher_id}:students:{student_id}:promote-form",
        f"teacher:{teacher_id}:students:{student_id}:focus",
        f"teacher:{teacher_id}:students:{student_id}:dna",
        f"teacher:{teacher_id}:students:{student_id}:review",
        f"teacher:{teacher_id}:students:{student_id}:goals",
        f"teacher:{teacher_id}:students:{student_id}:week",
        f"teacher:{teacher_id}:students",
    ]


@router.get(
    "/students/{student_id}/promote-form",
    response_model=PromoteFormResponse,
)
def teacher_promote_form_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Sınıf Yükselt formu için seçenekler + mevcut profil.

    Eşdeğer Jinja: app/routes/teacher_students.py:273 (promote_student_form).
    """
    from app.models.user import GRADUATE_MODE_LABELS, TRACK_LABELS

    student = _get_owned_student(db, student_id, user.id)
    years = (
        db.query(AcademicYear)
        .filter(AcademicYear.teacher_id == user.id)
        .order_by(AcademicYear.name.desc())
        .all()
    )
    suggested_year_id: int | None = None
    if student.academic_year and student.academic_year.start_year is not None:
        cur_start = student.academic_year.start_year
        candidates = [y for y in years if y.start_year and y.start_year > cur_start]
        if candidates:
            suggested_year_id = min(candidates, key=lambda y: y.start_year).id

    curriculum_labels = {
        "lgs": "LGS Müfredatı",
        "klasik_lise": "Klasik Lise",
        "maarif_lise": "Maarif Modeli",
    }
    cm = student.effective_curriculum_model
    cm_value = cm.value if cm else None
    track_value = student.track.value if student.track else None
    track_label = TRACK_LABELS.get(student.track) if student.track else None
    grad_mode_value = (
        student.graduate_mode.value
        if (student.is_graduate and student.graduate_mode)
        else None
    )

    return PromoteFormResponse(
        student_id=student.id,
        student_name=student.full_name,
        current_grade_label=student.display_grade_label,
        current_track=track_value,
        current_track_label=track_label,
        current_curriculum_model=cm_value,
        current_curriculum_label=curriculum_labels.get(cm_value) if cm_value else None,
        current_exam_label=student.effective_exam_label,
        current_graduate_mode=grad_mode_value,
        current_academic_year_name=(
            student.academic_year.name if student.academic_year else None
        ),
        entry_year_grade9=student.entry_year_grade9,
        is_graduate=bool(student.is_graduate),
        years=[
            PromoteYearOption(id=y.id, name=y.name, start_year=y.start_year)
            for y in years
        ],
        suggested_year_id=suggested_year_id,
        suggested_grade=_next_grade_5c(student.grade_level, student.is_graduate),
        grade_choices=[PromoteChoice(value=v, label=l) for v, l in _GRADE_CHOICES_5C],
        track_choices=[PromoteChoice(value=v, label=l) for v, l in _TRACK_CHOICES_5C],
        graduate_mode_choices=[
            PromoteChoice(value=v, label=l) for v, l in _GRADUATE_MODE_CHOICES_5C
        ],
    )


@router.post(
    "/students/{student_id}/promote",
    response_model=MutationResponse[PromoteResult],
)
def teacher_promote_v2(
    student_id: int,
    body: PromoteBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenciyi yeni sınıfa/akademik yıla taşı.

    Eşdeğer Jinja: app/routes/teacher_students.py:325 (promote_student).
    Kitap kütüphanesi ve görev tarihçesi korunur — sadece profil alanları
    güncellenir. 11-12 ve mezun için track zorunlu; mezun için graduate_mode
    zorunlu. Müfredat modeli akademik yıl + sınıf + (override) entry_year'dan
    türetilir.
    """
    from app.models.curriculum import derive_curriculum_model
    from app.models.user import GRADUATE_MODE_LABELS, TRACK_LABELS

    student = _get_owned_student(db, student_id, user.id)

    grade_raw = body.grade
    if grade_raw == "graduate":
        new_grade: int | None = None
        new_is_graduate = True
    else:
        try:
            new_grade = int(grade_raw)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "invalid_grade",
                    "message": "Sınıf değeri geçersiz.",
                },
            )
        new_is_graduate = False

    track_required = new_is_graduate or (new_grade is not None and new_grade >= 11)
    track_enum: Track | None = None
    if body.track:
        try:
            track_enum = Track(body.track)
        except ValueError:
            track_enum = None
    if track_required and track_enum is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "track_required",
                "message": "11. sınıf, 12. sınıf ve mezunlar için alan zorunlu.",
            },
        )

    graduate_mode_enum: GraduateMode | None = None
    if body.graduate_mode:
        try:
            graduate_mode_enum = GraduateMode(body.graduate_mode)
        except ValueError:
            graduate_mode_enum = None
    if new_is_graduate and graduate_mode_enum is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "graduate_mode_required",
                "message": "Mezun öğrenciler için çalışma şekli zorunlu.",
            },
        )

    parsed_year_id: int | None = body.academic_year_id
    if parsed_year_id is not None:
        owns = (
            db.query(AcademicYear)
            .filter(
                AcademicYear.id == parsed_year_id,
                AcademicYear.teacher_id == user.id,
            )
            .first()
        )
        if not owns:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "invalid_academic_year",
                    "message": "Akademik yıl bulunamadı veya sizin değil.",
                },
            )

    entry_year = body.entry_year_grade9
    if entry_year is not None and not (2000 <= entry_year <= 2100):
        entry_year = None

    student.grade_level = new_grade
    student.is_graduate = new_is_graduate
    student.track = track_enum
    student.graduate_mode = graduate_mode_enum if new_is_graduate else None
    student.entry_year_grade9 = entry_year
    if parsed_year_id is not None:
        student.academic_year_id = parsed_year_id

    db.commit()
    db.refresh(student)

    curriculum_labels = {
        "lgs": "LGS Müfredatı",
        "klasik_lise": "Klasik Lise",
        "maarif_lise": "Maarif Modeli",
    }
    new_cm = derive_curriculum_model(
        grade_level=new_grade,
        is_graduate=new_is_graduate,
        entry_year_grade9=entry_year,
        academic_year_start=(
            student.academic_year.start_year if student.academic_year else None
        ),
    )
    cm_label = curriculum_labels.get(new_cm.value) if new_cm else "—"

    msg = f"{student.full_name} → {student.display_grade_label}"
    if student.academic_year:
        msg += f" · {student.academic_year.name}"
    msg += f" · müfredat: {cm_label}"

    return MutationResponse[PromoteResult](
        data=PromoteResult(
            student_id=student.id,
            new_grade_label=student.display_grade_label,
            new_curriculum_label=cm_label or "—",
            new_track_label=TRACK_LABELS.get(student.track) if student.track else None,
            new_graduate_mode_label=(
                GRADUATE_MODE_LABELS.get(student.graduate_mode)
                if (student.is_graduate and student.graduate_mode)
                else None
            ),
            new_academic_year_name=(
                student.academic_year.name if student.academic_year else None
            ),
            message=msg,
        ),
        invalidate=_invalidate_for_student_detail(user.id, student.id),
    )


# =============================================================================
# Paket 3.5c — Odak (Focus) — read-only öğretmen görünümü
# =============================================================================


def _focus_session_to_row(s) -> FocusSessionRow:
    return FocusSessionRow(
        id=s.id,
        kind=s.kind.value if hasattr(s.kind, "value") else str(s.kind),
        started_at=s.started_at,
        ended_at=s.ended_at,
        planned_minutes=s.planned_minutes,
        actual_minutes=s.actual_minutes or 0,
        interrupted=bool(s.interrupted),
        label=s.label,
    )


@router.get(
    "/students/{student_id}/focus",
    response_model=TeacherFocusResponse,
)
def teacher_student_focus_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen — öğrencinin pomodoro istatistikleri.

    Eşdeğer Jinja: app/routes/focus.py:291 (teacher_student_focus).
    Read-only: öğretmen seans başlatamaz/bitiremez.
    """
    from app.services.gamification import (
        compute_points,
        compute_streak,
        list_student_badges,
        longest_streak,
    )
    from app.services.pomodoro import (
        recent_sessions as svc_recent,
        today_summary as svc_today,
        total_work_minutes as svc_30d,
    )

    student = _get_owned_student(db, student_id, user.id)
    now = datetime.now(timezone.utc)
    summary = svc_today(db, student_id=student.id, now=now)
    recent = svc_recent(db, student_id=student.id, limit=20)
    streak = compute_streak(db, student_id=student.id, now=now)
    longest = longest_streak(db, student_id=student.id)
    points_bd = compute_points(db, student_id=student.id)
    points_total = points_bd.total if hasattr(points_bd, "total") else int(points_bd)
    badges_raw = list_student_badges(db, student_id=student.id)
    work_30 = svc_30d(db, student_id=student.id, since_days=30)

    badges: list[FocusBadge] = []
    for badge_def, rec in badges_raw:
        badges.append(FocusBadge(
            kind=str(badge_def.kind.value if hasattr(badge_def.kind, "value") else badge_def.kind),
            title=badge_def.title,
            emoji=badge_def.emoji,
            description=badge_def.description,
            earned_at=rec.earned_at,
        ))

    return TeacherFocusResponse(
        student_id=student.id,
        student_name=student.full_name,
        today_work_sessions=summary.work_sessions,
        today_work_minutes=summary.work_minutes,
        today_break_minutes=summary.break_minutes,
        today_interrupted_count=summary.interrupted_count,
        streak_days=streak,
        longest_streak=longest,
        points_total=points_total,
        work_minutes_30d=work_30,
        badges=badges,
        recent_sessions=[_focus_session_to_row(s) for s in recent],
    )


# =============================================================================
# Paket 3.5c — DNA (Çalışma profili + Tükenmişlik)
# =============================================================================


@router.get(
    "/students/{student_id}/dna",
    response_model=TeacherDnaResponse,
)
def teacher_student_dna_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen — öğrencinin DNA profili + burnout sinyalleri + veliye mesaj
    önizleme.

    Eşdeğer Jinja: app/routes/dna.py:91 (teacher_student_dna).
    """
    from app.services.burnout import compute_burnout
    from app.services.dna_parent_message import build_dna_parent_message
    from app.services.event_triggers import _active_parents_for
    from app.services.study_dna import DAY_NAMES_TR, compute_profile

    student = _get_owned_student(db, student_id, user.id)
    now = datetime.now(timezone.utc)
    profile = compute_profile(db, student_id=student.id, now=now)
    burnout = compute_burnout(db, student_id=student.id, now=now)

    by_subject = [
        DnaSubjectRow(
            subject_id=sa.subject_id,
            subject_name=sa.subject_name,
            planned=sa.planned,
            completed=sa.completed,
            completion_rate=float(sa.completion_rate),
        )
        for sa in profile.by_subject
    ]
    trend = None
    if profile.trend is not None:
        trend = DnaTrendInfo(
            direction=profile.trend.direction,
            this_week_completed=profile.trend.this_week_completed,
            last_week_completed=profile.trend.last_week_completed,
            delta_pct=profile.trend.delta_pct,
        )
    signals = [
        BurnoutSignalRow(
            kind=s.kind,
            severity=s.severity,
            label=s.label,
            emoji=s.emoji,
            detail=s.detail,
            metric=s.metric,
        )
        for s in burnout.signals
    ]
    peak_day_name = None
    if profile.peak_day_idx is not None and 0 <= profile.peak_day_idx < 7:
        peak_day_name = DAY_NAMES_TR[profile.peak_day_idx]

    parents = _active_parents_for(db, student.id)
    parent_count = len(parents)
    parent_preview = build_dna_parent_message(
        student=student, teacher=user, burnout=burnout, profile=profile,
    )

    return TeacherDnaResponse(
        student_id=student.id,
        student_name=student.full_name,
        window_days=profile.window_days,
        has_enough_data=profile.has_enough_data,
        total_completed=profile.total_completed,
        total_planned=profile.total_planned,
        completion_rate=float(profile.completion_rate),
        chronotype=profile.chronotype,
        peak_hour=profile.peak_hour,
        peak_day_idx=profile.peak_day_idx,
        peak_day_name=peak_day_name,
        heatmap=profile.heatmap,
        morning_count=profile.morning_count,
        afternoon_count=profile.afternoon_count,
        evening_count=profile.evening_count,
        night_count=profile.night_count,
        weekend_count=profile.weekend_count,
        weekday_count=profile.weekday_count,
        by_subject=by_subject,
        trend=trend,
        hour_data_confidence=profile.hour_data_confidence,
        batch_completion_count=getattr(profile, "batch_completion_count", 0),
        fallback_scheduled_count=getattr(profile, "fallback_scheduled_count", 0),
        burnout_risk_score=burnout.risk_score,
        burnout_risk_level=burnout.risk_level,
        burnout_signals=signals,
        parent_count=parent_count,
        parent_message_preview=parent_preview,
    )


@router.post(
    "/students/{student_id}/dna/notify-parent",
    response_model=MutationResponse[DnaNotifyParentResult],
)
def teacher_student_dna_notify_v2(
    student_id: int,
    body: DnaNotifyParentBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """DNA panelinden veliye sayı destekli mesaj gönder.

    Eşdeğer Jinja: app/routes/dna.py:139 (teacher_student_dna_notify_parent).
    Mesaj boşsa 422; veli yoksa 422 no_active_parents; başarıda mevcut bildirim
    kuyruğuna düşer (email + WhatsApp).
    """
    from app.models import TeacherNoteToParent
    from app.services.event_triggers import _active_parents_for, on_teacher_note_created

    student = _get_owned_student(db, student_id, user.id)
    text = (body.body or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "empty_message",
                "message": "Mesaj boş olamaz.",
            },
        )
    if len(text) > 2000:
        text = text[:2000]

    parents = _active_parents_for(db, student.id)
    if not parents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "no_active_parents",
                "message": "Bu öğrenciye bağlı aktif veli yok.",
            },
        )

    note = TeacherNoteToParent(
        student_id=student.id,
        teacher_id=user.id,
        body=text,
    )
    db.add(note)
    db.flush()
    on_teacher_note_created(db, note)
    db.commit()
    db.refresh(note)

    return MutationResponse[DnaNotifyParentResult](
        data=DnaNotifyParentResult(
            note_id=note.id,
            student_id=student.id,
            parent_count=len(parents),
        ),
        invalidate=[
            f"teacher:{user.id}:students:{student.id}:dna",
            f"teacher:{user.id}:students:{student.id}:parents",
        ],
    )


# =============================================================================
# Paket 3.5c — Tekrar (Review / FSRS)
# =============================================================================


@router.get(
    "/students/{student_id}/review",
    response_model=TeacherReviewResponse,
)
def teacher_student_review_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen — öğrencinin tekrar kartları + müdahale önerileri.

    Eşdeğer Jinja: app/routes/review.py:117 (teacher_student_review).
    Subject listesi öğrencinin sınıf seviyesi + müfredat modeline göre
    filtrelenir. Struggle cards 0-100 skor + öğrenci envanterindeki uygun
    bölüm listesi ile döner.
    """
    from app.models import REVIEW_STATE_LABELS_TR, REVIEW_STATE_NEW, ReviewCard, Subject, Topic
    from app.services.review_scheduler import cards_breakdown, struggling_topics_for_student

    student = _get_owned_student(db, student_id, user.id)
    now = datetime.now(timezone.utc)
    breakdown = cards_breakdown(db, student_id=student.id, now=now)

    cards_q = (
        db.query(ReviewCard)
        .options(joinedload(ReviewCard.topic).joinedload(Topic.subject))
        .filter(ReviewCard.student_id == student.id)
        .order_by(
            (ReviewCard.state == REVIEW_STATE_NEW).desc(),
            ReviewCard.due_at.asc().nulls_first(),
        )
        .all()
    )
    cards = [
        ReviewCardRow(
            id=c.id,
            topic_id=c.topic_id,
            topic_name=c.topic.name if c.topic else "—",
            subject_id=c.topic.subject_id if (c.topic and c.topic.subject) else None,
            subject_name=c.topic.subject.name if (c.topic and c.topic.subject) else None,
            state=c.state,
            state_label=REVIEW_STATE_LABELS_TR.get(c.state, c.state),
            due_at=c.due_at,
            last_reviewed_at=c.last_reviewed_at,
            last_rating=c.last_rating,
            review_count=c.review_count,
            lapse_count=c.lapse_count,
            stability=float(c.stability),
            difficulty=float(c.difficulty),
        )
        for c in cards_q
    ]

    # Subject listesi — sınıf seviyesi + müfredat modeline göre filtreli
    from sqlalchemy import or_ as sa_or
    all_subjects = (
        db.query(Subject)
        .filter(
            sa_or(Subject.is_builtin.is_(True), Subject.teacher_id == user.id)
        )
        .order_by(Subject.order, Subject.name)
        .all()
    )
    student_cm = student.effective_curriculum_model
    seen: set[str] = set()
    subjects: list[ReviewSubjectOption] = []
    for s in all_subjects:
        if not s.covers_grade(student.grade_level, is_graduate=student.is_graduate):
            continue
        if student_cm and s.curriculum_model and s.curriculum_model != student_cm:
            continue
        if s.name in seen:
            continue
        seen.add(s.name)
        subjects.append(ReviewSubjectOption(id=s.id, name=s.name))

    # Struggle cards + uygun book sections
    struggling = struggling_topics_for_student(
        db, student_id=student.id, limit=8, min_score=10.0,
    )
    struggle_cards: list[StruggleCardRow] = []
    if struggling:
        topic_ids = [st.topic_id for st in struggling]
        rows = (
            db.query(BookSection)
            .options(joinedload(BookSection.book))
            .join(StudentBook, StudentBook.book_id == BookSection.book_id)
            .filter(
                StudentBook.student_id == student.id,
                BookSection.topic_id.in_(topic_ids),
            )
            .all()
        )
        sections_by_topic: dict[int, list] = {}
        for sec in rows:
            sections_by_topic.setdefault(sec.topic_id, []).append(sec)

        for st in struggling:
            secs = sections_by_topic.get(st.topic_id, [])
            struggle_cards.append(StruggleCardRow(
                topic_id=st.topic_id,
                topic_name=st.topic_name,
                subject_id=st.subject_id,
                subject_name=st.subject_name,
                card_id=st.card_id,
                state=st.state,
                state_label=REVIEW_STATE_LABELS_TR.get(st.state, st.state),
                difficulty=float(st.difficulty),
                stability=float(st.stability),
                lapse_count=st.lapse_count,
                review_count=st.review_count,
                score=float(st.score),
                reasons=list(st.reasons),
                sections=[
                    StruggleSectionOption(
                        id=sec.id,
                        book_id=sec.book_id,
                        book_name=sec.book.name,
                        label=sec.label,
                        test_count=sec.test_count or 0,
                    )
                    for sec in secs
                ],
            ))

    return TeacherReviewResponse(
        student_id=student.id,
        student_name=student.full_name,
        grade_label=student.display_grade_label,
        exam_label=student.effective_exam_label,
        breakdown=ReviewBreakdownInfo(
            new=breakdown.new,
            learning=breakdown.learning,
            review=breakdown.review,
            relearning=breakdown.relearning,
            due_now=breakdown.due_now,
            total=breakdown.total,
        ),
        cards=cards,
        subjects=subjects,
        struggle_cards=struggle_cards,
    )


@router.post(
    "/students/{student_id}/review/seed",
    response_model=MutationResponse[ReviewSeedResult],
)
def teacher_student_review_seed_v2(
    student_id: int,
    body: ReviewSeedBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Ders kataloğundaki tüm topic'leri öğrenciye kart olarak ekle (idempotent).

    Eşdeğer Jinja: app/routes/review.py:255 (teacher_seed_subject).
    Subject başkasının ise 404; öğrencinin sınıf seviyesine uymuyorsa yine
    seed yapılır (servis idempotent; eşleşmeyen topic eklemez).
    """
    from sqlalchemy import or_ as sa_or
    from app.models import Subject
    from app.services.review_scheduler import seed_subject_for_student

    student = _get_owned_student(db, student_id, user.id)
    subject = (
        db.query(Subject)
        .filter(
            Subject.id == body.subject_id,
            sa_or(Subject.is_builtin.is_(True), Subject.teacher_id == user.id),
        )
        .first()
    )
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "subject_not_found",
                "message": "Ders bulunamadı.",
            },
        )

    res = seed_subject_for_student(
        db, student=student, subject=subject, teacher=user,
    )
    db.commit()

    return MutationResponse[ReviewSeedResult](
        data=ReviewSeedResult(
            subject_id=subject.id,
            subject_name=subject.name,
            added=res.added,
            skipped_existing=res.skipped_existing,
        ),
        invalidate=[f"teacher:{user.id}:students:{student.id}:review"],
    )


# =============================================================================
# Paket 3.5c — Hedefler (Goals)
# =============================================================================


def _goal_node_to_row(node, *, kind_labels, kind_emojis) -> GoalNodeRow:
    g = node.goal
    return GoalNodeRow(
        id=g.id,
        parent_id=g.parent_id,
        kind=g.kind.value,
        kind_label=kind_labels.get(g.kind, g.kind.value),
        kind_emoji=kind_emojis.get(g.kind, "⭐"),
        status=g.status.value,
        title=g.title,
        description=g.description,
        target_value=g.target_value,
        current_value=g.current_value,
        unit=g.unit,
        target_date=g.target_date.isoformat() if g.target_date else None,
        is_auto_generated=bool(g.is_auto_generated),
        progress_pct=g.progress_pct,
        aggregated_pct=node.aggregated_pct,
        achieved_count=node.achieved_count,
        total_count=node.total_count,
        achieved_at=g.achieved_at,
        created_at=g.created_at,
        children=[
            _goal_node_to_row(c, kind_labels=kind_labels, kind_emojis=kind_emojis)
            for c in node.children
        ],
    )


def _filter_personal_goal_roots(roots):
    """EXAM_TARGET + auto-generated SUBJECT'leri gizle (goals.py:149 paritesi)."""
    from app.models import GoalKind

    out = []
    for r in roots:
        g = r.goal
        if g.kind == GoalKind.EXAM_TARGET and g.is_auto_generated:
            continue
        if g.kind == GoalKind.SUBJECT and g.is_auto_generated:
            continue
        out.append(r)
    return out


@router.get(
    "/students/{student_id}/goals",
    response_model=TeacherGoalsResponse,
)
def teacher_student_goals_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen — müfredat ilerleme + kişisel hedef ağacı.

    Eşdeğer Jinja: app/routes/goals.py:194 (teacher_student_goals).
    Otomatik üretilmiş EXAM_TARGET / SUBJECT'ler ağaçtan gizlenir.
    """
    from app.models import GOAL_KIND_EMOJIS, GOAL_KIND_LABELS_TR, GoalKind
    from app.services.goals import build_tree, student_goal_summary
    from app.services.goals_progress import (
        compute_overall_progress,
        compute_subject_progress,
        list_active_topic_progress,
    )

    student = _get_owned_student(db, student_id, user.id)

    topics = list_active_topic_progress(db, student_id=student.id)
    subjects_progress = compute_subject_progress(topics)
    overall = compute_overall_progress(subjects_progress)

    finished = 0
    for sp in subjects_progress:
        for t in sp.topics:
            if t.progress_pct >= 100:
                finished += 1

    roots = build_tree(db, student_id=student.id, include_abandoned=True)
    personal = _filter_personal_goal_roots(roots)

    summary_dict = student_goal_summary(db, student_id=student.id)
    raw_next = summary_dict.get("next_target_date")
    next_iso = (
        raw_next if isinstance(raw_next, str)
        else raw_next.isoformat() if raw_next is not None
        else None
    )

    return TeacherGoalsResponse(
        student_id=student.id,
        student_name=student.full_name,
        subjects=[
            GoalSubjectProgressRow(
                subject_id=sp.subject_id,
                subject_name=sp.subject_name,
                total_completed=sp.total_completed,
                total_target=sp.total_target,
                progress_pct=sp.progress_pct,
                topics=[
                    GoalTopicProgressRow(
                        section_id=t.section_id,
                        section_label=t.section_label,
                        book_id=t.book_id,
                        book_name=t.book_name,
                        completed_tests=t.completed_tests,
                        target_tests=t.target_tests,
                        progress_pct=t.progress_pct,
                    )
                    for t in sp.topics
                ],
            )
            for sp in subjects_progress
        ],
        topic_count=len(topics),
        overall_pct=overall,
        roots=[
            _goal_node_to_row(
                r,
                kind_labels=GOAL_KIND_LABELS_TR,
                kind_emojis=GOAL_KIND_EMOJIS,
            )
            for r in personal
        ],
        summary=GoalSummaryInfo(
            total=summary_dict.get("total", 0),
            active=summary_dict.get("active", 0),
            achieved=summary_dict.get("achieved", 0),
            abandoned=summary_dict.get("abandoned", 0),
            overall_pct=summary_dict.get("overall_pct"),
            next_target_date=next_iso,
        ),
        finished_topic_count=finished,
        kind_options=[
            PromoteChoice(value=k.value, label=GOAL_KIND_LABELS_TR.get(k, k.value))
            for k in GoalKind
        ],
    )


@router.post(
    "/students/{student_id}/goals",
    response_model=MutationResponse[GoalNodeRow],
)
def teacher_create_goal_v2(
    student_id: int,
    body: TeacherGoalCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen yeni hedef oluştur (her kind dahil EXAM_TARGET).

    Eşdeğer Jinja: app/routes/goals.py:268 (teacher_create_goal).
    title boş→422 invalid_title; target_date geçersiz→422 invalid_date.
    """
    from app.models import GOAL_KIND_EMOJIS, GOAL_KIND_LABELS_TR, GoalKind
    from app.services.goals import build_tree, create_goal

    student = _get_owned_student(db, student_id, user.id)

    title = (body.title or "").strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_title",
                "message": "Başlık boş olamaz.",
            },
        )
    target_date_parsed: date | None = None
    if body.target_date:
        try:
            target_date_parsed = date.fromisoformat(body.target_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "invalid_date",
                    "message": "Tarih formatı geçersiz. YYYY-MM-DD bekleniyor.",
                },
            )

    try:
        kind_enum = GoalKind(body.kind)
    except ValueError:
        kind_enum = GoalKind.CUSTOM

    try:
        g = create_goal(
            db, student=student, kind=kind_enum, title=title,
            parent_id=body.parent_id,
            description=body.description,
            target_value=body.target_value,
            current_value=body.current_value,
            unit=(body.unit or "").strip() or None,
            target_date=target_date_parsed,
            created_by_user_id=user.id,
        )
    except (ValueError, PermissionError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "goal_create_failed",
                "message": str(e),
            },
        )

    # Roots'tan kendi node'unu bul — children + aggregated_pct dolu olsun
    roots = build_tree(db, student_id=student.id, include_abandoned=True)
    found_node = None

    def _find(node):
        nonlocal found_node
        if node.goal.id == g.id:
            found_node = node
            return
        for c in node.children:
            _find(c)
            if found_node is not None:
                return

    for r in roots:
        _find(r)
        if found_node is not None:
            break

    if found_node is None:
        raise HTTPException(status_code=500, detail="goal node missing after create")

    return MutationResponse[GoalNodeRow](
        data=_goal_node_to_row(
            found_node,
            kind_labels=GOAL_KIND_LABELS_TR,
            kind_emojis=GOAL_KIND_EMOJIS,
        ),
        invalidate=[f"teacher:{user.id}:students:{student.id}:goals"],
    )


def _get_owned_goal_for_teacher(db: Session, goal_id: int, teacher_id: int):
    from app.models import StudentGoal, User as UserModel

    g = db.get(StudentGoal, goal_id)
    if g is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "goal_not_found",
                "message": "Hedef bulunamadı.",
            },
        )
    student = db.get(UserModel, g.student_id)
    if not student or student.teacher_id != teacher_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "goal_not_found",
                "message": "Hedef bulunamadı.",
            },
        )
    return g, student


@router.patch(
    "/goals/{goal_id}",
    response_model=MutationResponse[TeacherGoalActionResult],
)
def teacher_update_goal_v2(
    goal_id: int,
    body: TeacherGoalUpdateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen — hedefi güncelle (title/desc/target/current/unit/target_date)."""
    from app.services.goals import update_goal

    g, student = _get_owned_goal_for_teacher(db, goal_id, user.id)

    target_date_parsed: date | None = None
    if body.target_date:
        try:
            target_date_parsed = date.fromisoformat(body.target_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "invalid_date",
                    "message": "Tarih formatı geçersiz. YYYY-MM-DD bekleniyor.",
                },
            )

    update_goal(
        db, goal=g,
        title=(body.title.strip() if body.title is not None and body.title.strip() else None),
        description=(body.description if body.description is not None else None),
        target_value=body.target_value,
        current_value=body.current_value,
        unit=(body.unit.strip() if body.unit else None),
        target_date=target_date_parsed,
    )
    return MutationResponse[TeacherGoalActionResult](
        data=TeacherGoalActionResult(
            goal_id=g.id, student_id=student.id, status=g.status.value,
        ),
        invalidate=[f"teacher:{user.id}:students:{student.id}:goals"],
    )


@router.post(
    "/goals/{goal_id}/achieve",
    response_model=MutationResponse[TeacherGoalActionResult],
)
def teacher_achieve_goal_v2(
    goal_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    from app.services.goals import mark_achieved

    g, student = _get_owned_goal_for_teacher(db, goal_id, user.id)
    mark_achieved(db, goal=g)
    return MutationResponse[TeacherGoalActionResult](
        data=TeacherGoalActionResult(
            goal_id=g.id, student_id=student.id, status=g.status.value,
        ),
        invalidate=[f"teacher:{user.id}:students:{student.id}:goals"],
    )


@router.post(
    "/goals/{goal_id}/abandon",
    response_model=MutationResponse[TeacherGoalActionResult],
)
def teacher_abandon_goal_v2(
    goal_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    from app.services.goals import mark_abandoned

    g, student = _get_owned_goal_for_teacher(db, goal_id, user.id)
    mark_abandoned(db, goal=g)
    return MutationResponse[TeacherGoalActionResult](
        data=TeacherGoalActionResult(
            goal_id=g.id, student_id=student.id, status=g.status.value,
        ),
        invalidate=[f"teacher:{user.id}:students:{student.id}:goals"],
    )


@router.delete(
    "/goals/{goal_id}",
    response_model=MutationResponse[TeacherGoalActionResult],
)
def teacher_delete_goal_v2(
    goal_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    from app.services.goals import delete_goal

    g, student = _get_owned_goal_for_teacher(db, goal_id, user.id)
    sid = student.id
    delete_goal(db, goal=g)
    return MutationResponse[TeacherGoalActionResult](
        data=TeacherGoalActionResult(goal_id=goal_id, student_id=sid, deleted=True),
        invalidate=[f"teacher:{user.id}:students:{sid}:goals"],
    )


@router.post(
    "/students/{student_id}/goals/seed-exam",
    response_model=MutationResponse[TeacherGoalActionResult],
)
def teacher_seed_exam_goals_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrencinin sınav hedefinden otomatik subject ağacı türet (idempotent)."""
    from app.services.goals_auto import seed_for_exam_target

    student = _get_owned_student(db, student_id, user.id)
    result = seed_for_exam_target(
        db, student=student, created_by_user_id=user.id,
    )
    if result.get("exam_target") is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "no_exam_target",
                "message": "Önce öğrenciye sınav hedefi (exam_target) tanımla.",
            },
        )
    if result.get("skipped_existing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "already_seeded",
                "message": "Bu öğrenciye zaten otomatik hedef ağacı kurulu.",
            },
        )
    return MutationResponse[TeacherGoalActionResult](
        data=TeacherGoalActionResult(goal_id=0, student_id=student.id, status="active"),
        invalidate=[f"teacher:{user.id}:students:{student.id}:goals"],
    )


# =============================================================================
# Paket 3.5d.1 — Analitik (30 gün trend + ders bazlı)
# =============================================================================


_TR_MONTHS_SHORT = [
    "Oca", "Şub", "Mar", "Nis", "May", "Haz",
    "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
]


def _format_trend_label(d: date) -> str:
    return f"{d.day:02d} {_TR_MONTHS_SHORT[d.month - 1]}"


@router.get(
    "/students/{student_id}/analytics",
    response_model=TeacherStudentAnalyticsResponse,
)
def teacher_student_analytics_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenci analitik sekmesi — 30 gün trend + ders bazlı dağılım.

    Eşdeğer Jinja: app/routes/teacher_student_detail.py:65-72 (trend serileri) +
    app/services/analytics.py:489 (subject_breakdown).
    """
    from app.services.analytics import (
        consistency_score,
        daily_activity_flag_series,
        daily_completed_series,
        daily_planned_series,
        student_snapshot,
        subject_breakdown,
    )
    from app.models.curriculum import EXAM_SECTION_LABELS, ExamSection
    from app.models.exam_result import ExamResult

    student = _get_owned_student(db, student_id, user.id)
    today = date.today()

    # --- 30 gün TEST trendi (mevcut) — yalnız soru bankası ---
    completed = daily_completed_series(db, student.id, today, 30, tests_only=True)
    planned = daily_planned_series(db, student.id, today, 30, tests_only=True)
    days = sorted(completed.keys())
    trend = [
        AnalyticsTrendPoint(date=d.isoformat(), label=_format_trend_label(d),
                            completed=completed[d], planned=planned[d])
        for d in days
    ]

    # --- Ders bazlı ilerleme (mevcut) ---
    raw_subjects = subject_breakdown(db, student.id)
    subjects = [
        AnalyticsSubjectRow(
            subject_id=row["subject_id"], name=row["name"], total=row["total"],
            completed=row["completed"], reserved=row["reserved"], remaining=row["remaining"],
            percent_done=row["percent_done"], percent_reserved=row["percent_reserved"],
            last_completed_at=row["last_completed_at"],
        )
        for row in raw_subjects
    ]

    # --- Snapshot: tempo + projeksiyon + uyarılar ---
    snap = student_snapshot(db, student, today=today)
    proj = snap.projection

    # Aktif gün + en uzun seri (son 30 gün)
    flags30 = daily_activity_flag_series(db, student.id, today, 30)
    active_days_30 = sum(1 for v in flags30.values() if v)
    longest = cur = 0
    for d in sorted(flags30.keys()):
        if flags30[d]:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0

    summary = AnalyticsSummary(
        rate_7d=round(snap.rate_7d, 2),
        rate_30d=round(snap.rate_30d, 2),
        consistency_7d_pct=round(snap.consistency_7d * 100),
        consistency_30d_pct=round(consistency_score(db, student.id, today, 30) * 100),
        hit_rate_7d_pct=min(100, round(snap.hit_rate_7d * 100)),
        active_days_30=active_days_30,
        longest_streak_30=longest,
        worst_warning_level=snap.worst_warning_level,
    )

    # --- Haftalık tamamlama trendi (son ~10 hafta) ---
    wk_c = daily_completed_series(db, student.id, today, 70, tests_only=True)
    wk_p = daily_planned_series(db, student.id, today, 70, tests_only=True)
    wk_buckets: dict[date, dict[str, int]] = {}
    for d in wk_p:
        mon = d - timedelta(days=d.weekday())
        b = wk_buckets.setdefault(mon, {"planned": 0, "completed": 0})
        b["planned"] += wk_p[d]
        b["completed"] += wk_c.get(d, 0)
    weekly_trend = []
    for mon in sorted(wk_buckets.keys()):
        b = wk_buckets[mon]
        pct = round(100 * b["completed"] / b["planned"]) if b["planned"] > 0 else 0
        weekly_trend.append(AnalyticsWeekPoint(
            week_start=mon.isoformat(), label=_format_trend_label(mon),
            planned=b["planned"], completed=b["completed"], pct=pct))

    # --- Aktivite takvimi (son 35 gün) ---
    flags35 = daily_activity_flag_series(db, student.id, today, 35)
    plan35 = daily_planned_series(db, student.id, today, 35, tests_only=False)
    activity_calendar = [
        AnalyticsDayFlag(date=d.isoformat(), weekday=d.weekday(),
                         active=flags35[d], has_plan=plan35.get(d, 0) > 0)
        for d in sorted(flags35.keys())
    ]

    # --- Haftanın günleri performansı (DOW) ---
    _DOW = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
    dow_performance = [
        AnalyticsDow(weekday=i, label=_DOW[i],
                     avg_completed=round(proj.dow_rates.get(i, 0.0), 1),
                     hit_pct=min(100, round(proj.dow_hit_rates.get(i, 0.0) * 100)),
                     measured=bool(proj.dow_hit_measured.get(i, False)))
        for i in range(7)
    ]

    # --- Sınava projeksiyon ---
    remaining_work = max(0, proj.total_tests - proj.completed)
    if remaining_work <= 0:
        pstatus = "green"
    elif proj.gap < 0:
        pstatus = "red" if abs(proj.gap) > remaining_work * 0.2 else "amber"
    elif proj.gap < remaining_work * 0.1:
        pstatus = "amber"
    else:
        pstatus = "green"
    projection = AnalyticsProjection(
        exam_label=student.effective_exam_label,
        exam_date=proj.exam_date.isoformat() if proj.exam_date else None,
        days_left=proj.days_left,
        total_tests=proj.total_tests,
        completed=proj.completed,
        remaining=remaining_work,
        projected_completable=proj.projected_completable,
        gap=proj.gap,
        rate_per_day=round(proj.rate_per_day, 2),
        required_rate=round(proj.required_rate, 2),
        confidence_level=proj.confidence_level,
        status=pstatus,
    )

    # --- Deneme net trendi (son 60 gün) ---
    def _sec_label(s):
        if s is None:
            return "Deneme"
        if isinstance(s, ExamSection):
            return EXAM_SECTION_LABELS.get(s, s.value.upper())
        return str(s).upper()

    def _sec_val(s):
        return s.value if hasattr(s, "value") else (str(s) if s else None)

    exam_rows = (
        db.query(ExamResult)
        .filter(ExamResult.student_id == student.id,
                ExamResult.exam_date >= today - timedelta(days=60))
        .order_by(ExamResult.exam_date.desc(), ExamResult.created_at.desc())
        .limit(8).all()
    )
    exam_trend = [
        AnalyticsExamPoint(title=r.title,
                           exam_date=r.exam_date.isoformat() if r.exam_date else None,
                           section_label=_sec_label(r.section),
                           net=float(r.net) if r.net is not None else 0.0)
        for r in exam_rows
    ]
    exam_trend_delta = None
    exam_trend_section = None
    if exam_rows:
        latest = exam_rows[0]
        lsec = _sec_val(latest.section)
        prev = next((r for r in exam_rows[1:] if _sec_val(r.section) == lsec), None)
        if prev is not None and latest.net is not None and prev.net is not None:
            exam_trend_delta = round(float(latest.net) - float(prev.net), 2)
            exam_trend_section = _sec_label(latest.section)

    warnings = [
        AnalyticsWarningItem(level=w.level, code=w.code, title=w.title, detail=w.detail)
        for w in snap.warnings
    ]

    return TeacherStudentAnalyticsResponse(
        student_id=student.id,
        student_name=student.full_name,
        window_days=30,
        trend=trend,
        subjects=subjects,
        summary=summary,
        weekly_trend=weekly_trend,
        activity_calendar=activity_calendar,
        dow_performance=dow_performance,
        projection=projection,
        exam_trend=exam_trend,
        exam_trend_section=exam_trend_section,
        exam_trend_delta=exam_trend_delta,
        warnings=warnings,
    )


# =============================================================================
# Paket 3.5d.1 — Veliye Not Gönder (Veliler sekmesi)
# =============================================================================


@router.post(
    "/students/{student_id}/parent-note",
    response_model=MutationResponse[ParentNoteResult],
)
def teacher_send_parent_note_v2(
    student_id: int,
    body: ParentNoteBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrencinin tüm aktif velilerine özel not gönder.

    Eşdeğer Jinja: app/routes/teacher_student_detail.py:291 (send_parent_note).
    Validation: 10-2000 karakter. on_teacher_note_created tüm aktif veliler için
    bildirim üretir. ÖĞRENCİ bu notu görmez (gizlilik kuralı).
    """
    from app.models import TeacherNoteToParent
    from app.services.event_triggers import _active_parents_for, on_teacher_note_created

    student = _get_owned_student(db, student_id, user.id)
    text = (body.body or "").strip()
    if len(text) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "note_too_short",
                "message": "Not en az 10 karakter olmalıdır.",
            },
        )
    if len(text) > 2000:
        text = text[:2000]

    parents = _active_parents_for(db, student.id)
    parent_count = len(parents)
    if parent_count == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "no_active_parents",
                "message": "Bu öğrenciye bağlı aktif veli yok.",
            },
        )

    note = TeacherNoteToParent(
        student_id=student.id,
        teacher_id=user.id,
        body=text,
    )
    db.add(note)
    db.flush()

    summary = on_teacher_note_created(db, note)
    db.commit()
    db.refresh(note)

    return MutationResponse[ParentNoteResult](
        data=ParentNoteResult(
            note_id=note.id,
            fired=int(summary.get("fired", 0)),
            parent_count=parent_count,
        ),
        invalidate=[
            f"teacher:{user.id}:students:{student.id}:parents",
        ],
    )


# =============================================================================
# Paket 3.5d.1 — Fleet panoları (Burnout + Review tüm-öğrenciler)
# =============================================================================


@router.get(
    "/burnout",
    response_model=TeacherBurnoutFleetResponse,
)
def teacher_burnout_fleet_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Tüm öğrenciler için tükenmişlik risk listesi.

    Eşdeğer Jinja: app/routes/dna.py:197 (teacher_burnout_dashboard).
    """
    from app.services.burnout import bulk_burnout_for_teacher

    now = datetime.now(timezone.utc)
    rows = bulk_burnout_for_teacher(db, teacher_id=user.id, now=now)

    healthy = sum(1 for r in rows if r["risk_level"] == "healthy")
    watch = sum(1 for r in rows if r["risk_level"] == "watch")
    warn = sum(1 for r in rows if r["risk_level"] == "warn")
    critical = sum(1 for r in rows if r["risk_level"] == "critical")

    return TeacherBurnoutFleetResponse(
        rows=[
            TeacherBurnoutFleetRow(
                student_id=r["student"].id,
                full_name=r["student"].full_name,
                risk_score=r["risk_score"],
                risk_level=r["risk_level"],
                signal_count=r["signal_count"],
                is_active=bool(r["student"].is_active),
            )
            for r in rows
        ],
        healthy_count=healthy,
        watch_count=watch,
        warn_count=warn,
        critical_count=critical,
    )


@router.get(
    "/review",
    response_model=TeacherReviewFleetResponse,
)
def teacher_review_fleet_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Tüm öğrenciler için tekrar (FSRS) yükü.

    Eşdeğer Jinja: app/routes/review.py:300 (teacher_review_dashboard).
    """
    from app.services.review_scheduler import teacher_review_load

    now = datetime.now(timezone.utc)
    rows = teacher_review_load(db, teacher_id=user.id, now=now)

    total_due = sum(int(r.get("due_now", 0)) for r in rows)
    total_cards = sum(int(r.get("total", 0)) for r in rows)

    return TeacherReviewFleetResponse(
        rows=[
            TeacherReviewFleetRow(
                student_id=r["student"].id,
                full_name=r["student"].full_name,
                due_now=int(r.get("due_now", 0)),
                total=int(r.get("total", 0)),
                is_active=bool(r["student"].is_active),
            )
            for r in rows
        ],
        total_due=total_due,
        total_cards=total_cards,
    )


# =============================================================================
# Paket 3.5d.2 — Dashboard warnings-feed
# =============================================================================


@router.get(
    "/dashboard/warnings-feed",
    response_model=DashboardWarningsFeedResponse,
)
def teacher_dashboard_warnings_feed_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Tüm öğrencilerin aktif uyarı listesi (öncelik sıralı, üst N).

    Eşdeğer Jinja: teacher_dashboard.py top_warnings — öğrenci için
    student_snapshot.warnings, sonra severity sıralı liste.
    """
    from app.services.warning_state_service import reconcile_states

    now = datetime.now(timezone.utc)

    def _aw(dt):
        return dt if (dt is None or dt.tzinfo) else dt.replace(tzinfo=timezone.utc)

    today = date.today()
    # YALNIZ AKTİF öğrenci — koçluğu sonlandırılan (pasif) öğrenci uyarı akışına
    # girmez (bayat "program yok / 3 gün boş" uyarıları koçun ekranında kalmaz;
    # velisine zaten bildirim gitmiyor).
    students = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT,
                User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    )
    level_rank = {"red": 0, "amber": 1, "green": 2}
    raw: list[tuple[User, object]] = []
    present_keys: set[tuple[int, str]] = set()
    for s in students:
        sn = student_snapshot(db, s, today=today)
        for w in sn.warnings:
            raw.append((s, w))
            present_keys.add((s.id, w.code))

    # Tazelik + erteleme durumlarını canlı uyarılarla uzlaştır (first_seen yaz,
    # koşulu düzelenleri sil). GET ama durum izleme yan etkisi — commit edilir.
    states = reconcile_states(db, actor_id=user.id, present_keys=present_keys, now=now)
    db.commit()

    active: list[DashboardWarningRow] = []
    snoozed: list[DashboardWarningRow] = []
    for s, w in raw:
        st = states[(s.id, w.code)]
        age_days = max(0, (now - _aw(st.first_seen_at)).days)
        snz = _aw(st.snooze_until)
        is_snoozed = bool(snz and snz > now)
        row = DashboardWarningRow(
            student_id=s.id, student_name=s.full_name, level=w.level, code=w.code,
            title=w.title, detail=w.detail, is_paused=bool(s.is_paused),
            age_days=age_days, snoozed=is_snoozed, snooze_until=st.snooze_until,
        )
        (snoozed if is_snoozed else active).append(row)

    active.sort(key=lambda r: (level_rank.get(r.level, 9), r.student_name.lower()))
    snoozed.sort(key=lambda r: (level_rank.get(r.level, 9), r.student_name.lower()))
    return DashboardWarningsFeedResponse(
        rows=active[:30], snoozed_rows=snoozed[:30],
        total=len(active), snoozed_count=len(snoozed),
    )


@router.post("/dashboard/warnings/ack", response_model=MutationResponse[dict])
def teacher_warning_ack_v2(
    body: WarningAckBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Uyarıyı 'gördüm/ertele' — N gün aktif akıştan gizler (koşul sürerse geri döner)."""
    from app.services.warning_state_service import set_snooze

    _get_owned_student(db, body.student_id, user.id)  # sahiplik 404
    set_snooze(db, actor_id=user.id, student_id=body.student_id,
               code=body.code, days=body.snooze_days)
    db.commit()
    return MutationResponse[dict](
        data={"ok": True},
        invalidate=[f"teacher:{user.id}:dashboard:warnings-feed"],
    )


@router.post("/dashboard/warnings/unack", response_model=MutationResponse[dict])
def teacher_warning_unack_v2(
    body: WarningUnackBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Erteleme/gördüm geri al → uyarı aktif akışa döner."""
    from app.services.warning_state_service import clear_snooze

    _get_owned_student(db, body.student_id, user.id)
    clear_snooze(db, actor_id=user.id, student_id=body.student_id, code=body.code)
    db.commit()
    return MutationResponse[dict](
        data={"ok": True},
        invalidate=[f"teacher:{user.id}:dashboard:warnings-feed"],
    )


# =============================================================================
# Paket 3.5d.2 — Öğrenci şifre sıfırla
# =============================================================================


def _gen_temp_password_5d(n: int = 10) -> str:
    alphabet = _string_mod.ascii_letters + _string_mod.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


@router.post(
    "/students/{student_id}/reset-password",
    response_model=MutationResponse[StudentResetPasswordResult],
)
def teacher_reset_student_password_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrencinin şifresini sıfırla — geçici parola üret, must_change_password=True.

    Eşdeğer Jinja: app/routes/teacher_students.py:443 (reset_password).
    Öğrenci ilk girişinde mecburen şifre değiştirme ekranına yönlendirilir.
    """
    from app.services.security import hash_password

    student = _get_owned_student(db, student_id, user.id)
    temp_pw = _gen_temp_password_5d()
    student.password_hash = hash_password(temp_pw)
    student.must_change_password = True
    student.failed_login_count = 0
    student.locked_until = None
    db.commit()
    db.refresh(student)
    return MutationResponse[StudentResetPasswordResult](
        data=StudentResetPasswordResult(
            student_id=student.id,
            email=student.email,
            temp_password=temp_pw,
            full_name=student.full_name,
        ),
        invalidate=[
            f"teacher:{user.id}:students:{student.id}",
            f"teacher:{user.id}:students",
        ],
    )


# =============================================================================
# WP1 — Weekly Programs CRUD endpoint'leri (2026-05-31)
# =============================================================================


def _wp_to_item(p, *, today: date) -> WeeklyProgramItem:
    return WeeklyProgramItem(
        id=p.id,
        student_id=p.student_id,
        start_date=p.start_date.isoformat(),
        end_date=p.end_date.isoformat(),
        day_count=p.day_count,
        name=p.name,
        notes=p.notes,
        is_active=p.contains(today),
        created_at=p.created_at,
        label=p.label,
    )


def _wp_overlap_to_item(o) -> WeeklyProgramOverlapItem:
    return WeeklyProgramOverlapItem(
        program_id=o.program_id,
        label=o.label,
        start_date=o.start_date.isoformat(),
        end_date=o.end_date.isoformat(),
        overlap_days=o.overlap_days,
        task_count_in_overlap=o.task_count_in_overlap,
    )


def _wp_program_error_to_http(e) -> HTTPException:
    """ProgramError → HTTPException dönüşümü."""
    code = getattr(e, "code", "validation")
    msg = str(e)
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    if code == "not_found":
        status_code = status.HTTP_404_NOT_FOUND
    elif code == "overlap":
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(
        status_code=status_code,
        detail={"error": "validation", "code": code, "message": msg},
    )


@router.get(
    "/students/{student_id}/programs",
    response_model=WeeklyProgramListResponse,
)
def teacher_list_programs_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Bir öğrencinin tüm programları + aktif program + unlinked tasks özeti."""
    from app.services.weekly_program_service import (
        get_active_program,
        get_unlinked_task_summary,
        list_programs,
    )

    student = _get_owned_student(db, student_id, user.id)
    today = date.today()

    programs = list_programs(db, student_id=student.id)
    active = get_active_program(db, student_id=student.id, today=today)
    unlinked = get_unlinked_task_summary(db, student_id=student.id)

    return WeeklyProgramListResponse(
        student_id=student.id,
        items=[_wp_to_item(p, today=today) for p in programs],
        active_program_id=active.id if active else None,
        unlinked_task_count=int(unlinked["count"]) if unlinked else 0,
        unlinked_earliest=(
            unlinked["earliest"].isoformat() if unlinked else None
        ),
        unlinked_latest=(
            unlinked["latest"].isoformat() if unlinked else None
        ),
    )


@router.post(
    "/students/{student_id}/programs",
    response_model=MutationResponse[WeeklyProgramItem],
)
def teacher_create_program_v2(
    student_id: int,
    body: WeeklyProgramCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Yeni program yarat. Çakışma varsa 409 + detail.overlaps listesi.

    Kullanıcı uyarıyı görüp `allow_overlap=True` ile yeniden çağırırsa zorla yaratılır.
    """
    from app.services.weekly_program_service import (
        ProgramError,
        create_program,
        find_overlapping,
    )

    try:
        start = date.fromisoformat(body.start_date)
        end = date.fromisoformat(body.end_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation", "code": "invalid_date",
                    "message": "Tarih formatı YYYY-MM-DD olmalı."},
        )

    try:
        prog = create_program(
            db,
            coach=user,
            student_id=student_id,
            start=start,
            end=end,
            name=body.name,
            notes=body.notes,
            allow_overlap=body.allow_overlap,
        )
    except ProgramError as e:
        if e.code == "overlap":
            overlaps = find_overlapping(
                db, student_id=student_id, start=start, end=end,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "conflict",
                    "code": "overlap",
                    "message": str(e),
                    "overlaps": [
                        _wp_overlap_to_item(o).model_dump() for o in overlaps
                    ],
                },
            )
        raise _wp_program_error_to_http(e)

    db.commit()
    db.refresh(prog)
    today = date.today()
    return MutationResponse[WeeklyProgramItem](
        data=_wp_to_item(prog, today=today),
        invalidate=[
            f"teacher:{user.id}:students:{student_id}:programs",
            f"teacher:{user.id}:students:{student_id}:week",
        ],
    )


@router.post(
    "/students/{student_id}/programs/wrap-legacy",
    response_model=MutationResponse[WeeklyProgramItem],
)
def teacher_wrap_legacy_v2(
    student_id: int,
    body: WeeklyProgramWrapLegacyBody | None = None,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Programa bağlı olmayan tüm görevleri tek "Eski Dönem" programına bağla.

    Bu route TANIM SIRASI ÖNEMLİDİR: `/programs/{program_id}` (UPDATE) ile aynı
    pattern'i paylaştığı için bu route DAHA ÖNCE tanımlı olmalı — FastAPI ilk
    eşleşeni alır. Aksi halde "wrap-legacy" path param olarak yorumlanır ve
    422 int_parsing hatası alınır.
    """
    from app.services.weekly_program_service import ProgramError, wrap_legacy_tasks

    name = (body.name if body else None) or "Eski Dönem"
    try:
        prog = wrap_legacy_tasks(
            db, coach=user, student_id=student_id, name=name,
        )
    except ProgramError as e:
        raise _wp_program_error_to_http(e)
    db.commit()
    db.refresh(prog)
    today = date.today()
    return MutationResponse[WeeklyProgramItem](
        data=_wp_to_item(prog, today=today),
        invalidate=[
            f"teacher:{user.id}:students:{student_id}:programs",
            f"teacher:{user.id}:students:{student_id}:week",
        ],
    )


@router.post(
    "/students/{student_id}/programs/{program_id}",
    response_model=MutationResponse[WeeklyProgramItem],
)
def teacher_update_program_v2(
    student_id: int,
    program_id: int,
    body: WeeklyProgramUpdateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Program tarih/etiket güncelle."""
    from app.services.weekly_program_service import (
        ProgramError,
        find_overlapping,
        update_program,
    )

    _get_owned_student(db, student_id, user.id)

    start = None
    end = None
    if body.start_date:
        try:
            start = date.fromisoformat(body.start_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail={"error": "validation", "code": "invalid_date",
                        "message": "Başlangıç tarihi YYYY-MM-DD olmalı."},
            )
    if body.end_date:
        try:
            end = date.fromisoformat(body.end_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail={"error": "validation", "code": "invalid_date",
                        "message": "Bitiş tarihi YYYY-MM-DD olmalı."},
            )

    try:
        prog = update_program(
            db,
            coach=user,
            program_id=program_id,
            start=start,
            end=end,
            name=body.name,
            notes=body.notes,
            allow_overlap=body.allow_overlap,
        )
    except ProgramError as e:
        if e.code == "overlap":
            from app.models import WeeklyProgram
            current = db.get(WeeklyProgram, program_id)
            new_start = start or (current.start_date if current else date.today())
            new_end = end or (current.end_date if current else date.today())
            overlaps = find_overlapping(
                db, student_id=student_id, start=new_start, end=new_end,
                exclude_id=program_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "conflict", "code": "overlap", "message": str(e),
                    "overlaps": [
                        _wp_overlap_to_item(o).model_dump() for o in overlaps
                    ],
                },
            )
        raise _wp_program_error_to_http(e)

    db.commit()
    db.refresh(prog)
    today = date.today()
    return MutationResponse[WeeklyProgramItem](
        data=_wp_to_item(prog, today=today),
        invalidate=[
            f"teacher:{user.id}:students:{student_id}:programs",
            f"teacher:{user.id}:students:{student_id}:week",
        ],
    )


@router.post(
    "/students/{student_id}/programs/{program_id}/delete",
    response_model=MutationResponse[dict],
)
def teacher_delete_program_v2(
    student_id: int,
    program_id: int,
    body: WeeklyProgramDeleteBody | None = None,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Program'ı sil. body.delete_tasks=True ise içindeki görevleri de sil."""
    from app.services.weekly_program_service import ProgramError, delete_program

    _get_owned_student(db, student_id, user.id)
    delete_tasks = bool(body.delete_tasks) if body else False
    try:
        result = delete_program(
            db, coach=user, program_id=program_id,
            delete_tasks=delete_tasks,
        )
    except ProgramError as e:
        raise _wp_program_error_to_http(e)
    db.commit()
    return MutationResponse[dict](
        data=result,
        invalidate=[
            f"teacher:{user.id}:students:{student_id}:programs",
            f"teacher:{user.id}:students:{student_id}:week",
            f"teacher:{user.id}:students:{student_id}",
        ],
    )


# ============================================================================
# Serbest iş blokları (Katman 3) — CoachWorkBlock CRUD + dağıtılan/kalan
# ============================================================================

_WORK_BLOCK_UNITS = ("test", "soru", "deneme")


def _work_block_aggregates(
    db: Session, student_id: int, block_ids: list[int],
) -> dict[int, tuple[int, int, int]]:
    """block_id -> (dağıtılan, çözülen, görev_sayısı). İptal görevler hariç."""
    if not block_ids:
        return {}
    rows = (
        db.query(
            Task.work_block_id,
            func.coalesce(func.sum(TaskBookItem.planned_count), 0),
            func.coalesce(func.sum(TaskBookItem.completed_count), 0),
            func.count(func.distinct(Task.id)),
        )
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .filter(
            Task.student_id == student_id,
            Task.work_block_id.in_(block_ids),
            Task.status != TaskStatus.CANCELLED,
        )
        .group_by(Task.work_block_id)
        .all()
    )
    return {r[0]: (int(r[1]), int(r[2]), int(r[3])) for r in rows}


def _build_work_block_item(block, agg: tuple[int, int, int]) -> WorkBlockItem:
    distributed, completed, task_count = agg
    return WorkBlockItem(
        id=block.id,
        title=block.title,
        subject_id=block.subject_id,
        subject_name=(block.subject.name if block.subject else None),
        total_count=block.total_count,
        unit=block.unit,
        note=block.note,
        status=block.status,
        distributed=distributed,
        completed=completed,
        remaining=max(0, block.total_count - distributed),
        task_count=task_count,
        created_at=block.created_at,
        archived_at=block.archived_at,
    )


def _get_owned_work_block(db: Session, block_id: int, user: User):
    """Bloğu getir + bloğun öğrencisi bu koça ait olmalı (tenant izolasyonu)."""
    from app.models import CoachWorkBlock
    block = db.query(CoachWorkBlock).filter(CoachWorkBlock.id == block_id).first()
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "work_block_not_found",
                    "message": "İş bloğu bulunamadı."},
        )
    # _get_owned_student koça ait değilse 404 fırlatır → sızıntı önleme.
    _get_owned_student(db, block.student_id, user.id)
    return block


@router.get(
    "/students/{student_id}/work-blocks",
    response_model=WorkBlockListResponse,
)
def teacher_list_work_blocks_v2(
    student_id: int,
    include_archived: bool = Query(False),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrencinin serbest iş blokları — dağıtılan/kalan hesaplı.

    Varsayılan yalnız aktif/biten bloklar; include_archived=True ise arşivliler de.
    """
    from app.models import CoachWorkBlock

    student = _get_owned_student(db, student_id, user.id)
    q = db.query(CoachWorkBlock).filter(CoachWorkBlock.student_id == student.id)
    if not include_archived:
        q = q.filter(CoachWorkBlock.status != "archived")
    blocks = q.order_by(CoachWorkBlock.created_at.desc()).all()
    agg = _work_block_aggregates(db, student.id, [b.id for b in blocks])
    items = [_build_work_block_item(b, agg.get(b.id, (0, 0, 0))) for b in blocks]
    return WorkBlockListResponse(items=items)


@router.post(
    "/students/{student_id}/work-blocks",
    response_model=MutationResponse[WorkBlockItem],
)
def teacher_create_work_block_v2(
    student_id: int,
    body: WorkBlockCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Yeni serbest iş bloğu oluştur (sistem-dışı kaynak için sayaç)."""
    from app.models import CoachWorkBlock

    student = _get_owned_student(db, student_id, user.id)
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "title_required",
                    "message": "Blok adı zorunlu."},
        )
    if body.total_count < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_total",
                    "message": "Toplam en az 1 olmalı."},
        )
    unit = body.unit if body.unit in _WORK_BLOCK_UNITS else "test"
    block = CoachWorkBlock(
        coach_id=user.id,
        student_id=student.id,
        title=title[:255],
        subject_id=body.subject_id,
        total_count=body.total_count,
        unit=unit,
        note=(body.note or None),
        status="active",
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return MutationResponse[WorkBlockItem](
        data=_build_work_block_item(block, (0, 0, 0)),
        invalidate=[f"teacher:{user.id}:students:{student.id}:work-blocks"],
    )


@router.post(
    "/work-blocks/{block_id}",
    response_model=MutationResponse[WorkBlockItem],
)
def teacher_update_work_block_v2(
    block_id: int,
    body: WorkBlockUpdateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Bloğu düzenle — None geçilen alan değişmez. status='archived' arşivler."""
    block = _get_owned_work_block(db, block_id, user)
    if body.title is not None:
        t = body.title.strip()
        if t:
            block.title = t[:255]
    if body.total_count is not None:
        if body.total_count < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "validation", "code": "invalid_total",
                        "message": "Toplam en az 1 olmalı."},
            )
        block.total_count = body.total_count
    if body.unit is not None and body.unit in _WORK_BLOCK_UNITS:
        block.unit = body.unit
    if body.subject_id is not None:
        block.subject_id = body.subject_id or None
    if body.note is not None:
        block.note = body.note.strip() or None
    if body.status is not None and body.status in ("active", "done", "archived"):
        block.status = body.status
        block.archived_at = (
            datetime.now(timezone.utc) if body.status == "archived" else None
        )
    db.commit()
    db.refresh(block)
    agg = _work_block_aggregates(db, block.student_id, [block.id]).get(
        block.id, (0, 0, 0)
    )
    return MutationResponse[WorkBlockItem](
        data=_build_work_block_item(block, agg),
        invalidate=[f"teacher:{user.id}:students:{block.student_id}:work-blocks"],
    )


@router.post(
    "/work-blocks/{block_id}/archive",
    response_model=MutationResponse[dict],
)
def teacher_archive_work_block_v2(
    block_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Bloğu arşivle (yumuşak) — görev bağları korunur, listeden gizlenir."""
    block = _get_owned_work_block(db, block_id, user)
    block.status = "archived"
    block.archived_at = datetime.now(timezone.utc)
    sid = block.student_id
    db.commit()
    return MutationResponse[dict](
        data={"ok": True},
        invalidate=[f"teacher:{user.id}:students:{sid}:work-blocks"],
    )


@router.delete(
    "/work-blocks/{block_id}",
    response_model=MutationResponse[dict],
)
def teacher_delete_work_block_v2(
    block_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Bloğu sil — bağlı görevler KALIR (work_block_id SET NULL)."""
    block = _get_owned_work_block(db, block_id, user)
    sid = block.student_id
    db.delete(block)
    db.commit()
    return MutationResponse[dict](
        data={"ok": True},
        invalidate=[
            f"teacher:{user.id}:students:{sid}:work-blocks",
            f"teacher:{user.id}:students:{sid}:week",
        ],
    )


