"""API v2 — Kurum Yöneticisi (INSTITUTION_ADMIN) endpoint'leri (Dalga 4 P1+P2).

Paket 1 kapsamı:
  GET    /api/v2/institution/dashboard               → InstitutionDashboardResponse
  GET    /api/v2/institution/teachers                → InstitutionTeacherListResponse
  POST   /api/v2/institution/teachers                → MutationResponse[TeacherCreateResult]
  GET    /api/v2/institution/teachers/{id}           → TeacherCardResponse
  POST   /api/v2/institution/teachers/{id}/deactivate
                                                      → MutationResponse[TeacherSummaryItem]
  POST   /api/v2/institution/teachers/{id}/activate  → MutationResponse[TeacherSummaryItem]
  POST   /api/v2/institution/teachers/{id}/pause-alerts
                                                      → MutationResponse[TeacherSummaryItem]
  POST   /api/v2/institution/teachers/{id}/resume-alerts
                                                      → MutationResponse[TeacherSummaryItem]
  GET    /api/v2/institution/roster                  → InstitutionRosterResponse
  GET    /api/v2/institution/goals                   → InstitutionGoalsResponse

Paket 2 kapsamı:
  GET    /api/v2/institution/invitations             → InvitationListResponse
  POST   /api/v2/institution/invitations             → MutationResponse[InvitationItem]
  POST   /api/v2/institution/invitations/{id}/revoke → MutationResponse[InvitationItem]
  GET    /api/v2/institution/activity-heatmap        → ActivityHeatmapResponse
  GET    /api/v2/institution/at-risk                 → AtRiskResponse
  GET    /api/v2/institution/burnout                 → BurnoutResponse
  GET    /api/v2/institution/cohorts                 → CohortsResponse

Paket 3 kapsamı:
  GET    /api/v2/institution/subscription            → SubscriptionResponse
  POST   /api/v2/institution/subscription/switch-academic-year
                                                     → MutationResponse[SubscriptionStatusInfo]
  POST   /api/v2/institution/subscription/pause      → MutationResponse[SubscriptionStatusInfo]
  POST   /api/v2/institution/subscription/resume     → MutationResponse[SubscriptionStatusInfo]
  POST   /api/v2/institution/subscription/guarantee/enable
                                                     → MutationResponse[SubscriptionStatusInfo]
  GET    /api/v2/institution/quota                   → QuotaResponse
  GET    /api/v2/institution/usage                   → UsageResponse
  GET    /api/v2/institution/admin-digest            → AdminDigestListResponse
  GET    /api/v2/institution/admin-digest/{id}       → AdminDigestDetailResponse
  POST   /api/v2/institution/admin-digest/send-now   → MutationResponse[AdminDigestSendResult]

GİZLİLİK:
Kurum yöneticisi öğretmenin DETAY verisini (program, notlar, öğrenci günlüğü)
göremez. Bu endpoint'ler /teacher/students/* gibi detay sayfalarına yönlenmek
için ID dönmesine rağmen, UI tarafında bu ID'ler hiçbir detay linki açmaz —
sadece kart-üstü görselleştirme için kullanılır. Tüm sorgular
institution_id == admin.institution_id ile filtrelidir.

Tenant isolation: 29/29 regresyon kontrolü korunur — başka kurumun
kullanıcısı erişirse 404.
"""
from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import (
    AdminWeeklyDigest,
    AuditAction,
    Institution,
    Invitation,
    USAGE_KIND_LABELS_TR,
    UsageEvent,
    UsageKind,
    User,
    UserRole,
    invitation_default_expiry,
)
from app.routes.api_v2.dependencies import _auth_error, get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.institution import (
    ActivityHeatmapResponse,
    AdminDigestDetailResponse,
    AdminDigestListResponse,
    AdminDigestSendResult,
    AdminDigestSummary,
    AtRiskCountsInfo,
    AtRiskResponse,
    AtRiskRowItem,
    BurnoutResponse,
    BurnoutRowItem,
    BurnoutSignalItem,
    ActionCenterItem,
    ActionCenterResponse,
    ActionCenterSummary,
    TeacherScorecardResponse,
    TeacherScorecardRow,
    TeacherScorecardSummary,
    ParentTrustResponse,
    ParentTrustSummary,
    ParentTrustChannel,
    ParentTrustNotificationItem,
    ParentTrustNotificationListResponse,
    ActivityStreamItem,
    ActivityStreamResponse,
    AcademicSummary,
    AcademicSectionRow,
    AcademicTrendPoint,
    AcademicTeacherRow,
    AcademicMoverRow,
    AcademicNoExamRow,
    InstitutionAcademicResponse,
    CohortStatsItem,
    CohortTabInfo,
    CohortTabLiteral,
    CohortsResponse,
    ComplianceEmptyRow,
    ComplianceStudentRow,
    ComplianceSummary,
    ComplianceTeacherRow,
    ComplianceTrendPoint,
    InstitutionComplianceResponse,
    GuaranteeEvaluationInfo,
    HeatmapCellData,
    InstitutionAggregateInfo,
    InstitutionBadgesResponse,
    InstitutionBrief,
    InstitutionDashboardResponse,
    InstitutionGoalsResponse,
    InstitutionInactiveBadge,
    InstitutionRiskBadge,
    InstitutionRosterResponse,
    InstitutionTeacherListResponse,
    InvitationCreateBody,
    NotifyCoachBody,
    CoachInterventionItem,
    CoachInterventionsResponse,
    NotifyCoachResult,
    InvitationItem,
    InvitationListResponse,
    PlanQuotaItem,
    QuotaInfoItem,
    QuotaResponse,
    RiskIndicatorItem,
    RosterFilterOptions,
    RosterRowItem,
    RosterTeacherOption,
    InstitutionPlanOption,
    SubscriptionRequestResult,
    SubscriptionResponse,
    SubscriptionStatusInfo,
    SubscriptionUpgradeRequestBody,
    TeacherCardResponse,
    TeacherCardStudentRow,
    TeacherCreateBody,
    TeacherCreateResult,
    TeacherHeatmapRow,
    TeacherSummaryItem,
    UsageAccountInfo,
    UsageBreakdownEntry,
    UsageDailyPoint,
    UsageEventItem,
    UsageResponse,
    WeekOverWeekInfo,
)
from app.services.admin_digest import send_admin_weekly_digest
from app.services.analytics import week_stats_for, week_test_deneme_for
from app.services.audit import log_action
from app.services.auth_security import generate_strong_password
from app.services.burnout import compute_burnout
from app.services.cohort_analysis import (
    cohort_by_curriculum,
    cohort_by_exam_target,
    cohort_by_grade,
    cohort_by_track,
    institution_week_over_week,
)
from app.services.credits import (
    PLAN_ALLOCATIONS,
    WARN_THRESHOLD_PCT,
    CreditOwner,
    current_period,
    daily_usage_series,
    get_or_create_account,
    recent_events,
    usage_breakdown_by_kind,
)
from app.services.goals import institution_goal_summary
from app.services.institution_view import TeacherSummary, teacher_summaries
from app.services.pause import REASON_MANUAL, pause_user, resume_user
from app.services.quotas import (
    PLAN_QUOTAS,
    QUOTA_KEYS,
    WARN_PCT,
    QuotaExceeded,
    check_quota_for_create,
    get_quota_summary,
)
from app.services.risk_analysis import (
    bulk_risk_assessment,
    filter_at_risk,
    get_active_mutes_for_students,
)
from app.services.security import hash_password
from app.services import support_request_service as support_svc
from app.services.subscription import (
    enable_guarantee,
    evaluate_guarantee,
    get_status as get_subscription_status,
    is_summer_window,
    pause_for_summer,
    resume_from_pause,
    switch_to_academic_year,
)
from app.services.teacher_activity import (
    INACTIVE_DAYS,
    inactive_teachers,
    teacher_activity_heatmap,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/institution", tags=["v2-institution"])


# =============================================================================
# Auth + sahiplik yardımcıları
# =============================================================================


def _require_institution_admin(
    user: User = Depends(get_current_user_v2),
) -> User:
    """INSTITUTION_ADMIN + institution_id zorunlu (configuration guard)."""
    if user.role != UserRole.INSTITUTION_ADMIN:
        raise _auth_error(
            "Bu uç nokta kurum yöneticisi hesabı bekler",
            "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    if user.institution_id is None:
        raise _auth_error(
            "Kurum yöneticisi bir kuruma bağlı olmalı (config hatası)",
            "institution_id_missing",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _get_institution_or_403(db: Session, institution_id: int) -> Institution:
    inst = db.get(Institution, institution_id)
    if not inst or not inst.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "code": "institution_inactive",
                "message": "Kurum aktif değil.",
            },
        )
    return inst


def _get_owned_teacher(
    db: Session, teacher_id: int, institution_id: int
) -> User:
    """Bu kuruma ait öğretmeni yükle, yoksa 404 (cross-tenant erişimde de)."""
    teacher = (
        db.query(User)
        .filter(
            User.id == teacher_id,
            User.role == UserRole.TEACHER,
            User.institution_id == institution_id,
        )
        .first()
    )
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "teacher_not_found",
                "message": "Öğretmen bulunamadı.",
            },
        )
    return teacher


# =============================================================================
# Mapper'lar
# =============================================================================


def _institution_brief(inst: Institution) -> InstitutionBrief:
    return InstitutionBrief(
        id=inst.id, name=inst.name, is_active=bool(inst.is_active)
    )


def _days_since(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    src = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return max(0, (now - src).days)


@router.get("/badges", response_model=InstitutionBadgesResponse)
def institution_badges_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Sol menü rozetleri — 'işleyince azalır' (60s polling).

    Gelen Talepler: öğretmenlerden bekleyen talep (cevapla/çöz → düşer).
    Taleplerim: süper adminin cevapladığı kendi talepleri (yanıtla/çöz → düşer).
    """
    from app.models import SUPPORT_STATUS_ANSWERED, SupportRequest
    from app.services import support_request_service as support_svc

    answered = (
        db.query(SupportRequest)
        .filter(
            SupportRequest.requester_id == user.id,
            SupportRequest.status == SUPPORT_STATUS_ANSWERED,
        )
        .count()
    )
    return InstitutionBadgesResponse(
        support_inbox_pending=support_svc.pending_count_institution_admin(db, user),
        support_answered=answered,
        checked_at=datetime.now(timezone.utc),
    )


def _teacher_summary_to_item(s: TeacherSummary) -> TeacherSummaryItem:
    t = s.teacher
    return TeacherSummaryItem(
        id=t.id,
        full_name=t.full_name,
        email=t.email,
        is_active=bool(t.is_active),
        is_paused=bool(t.is_paused),
        pause_reason=t.pause_reason,
        paused_at=t.paused_at,
        student_count=s.student_count,
        weekly_planned=s.planned,
        weekly_completed=s.completed,
        weekly_rate_pct=s.rate_pct,
        weekly_deneme_planned=s.deneme_planned,
        weekly_deneme_completed=s.deneme_completed,
        last_login_at=t.last_login_at,
        last_login_days=s.last_login_days,
    )


def _teacher_to_summary_item(teacher: User, *, today: date | None = None) -> TeacherSummaryItem:
    """Pause/aktivasyon mutation'larından sonra tek bir öğretmenin TeacherSummaryItem
    karşılığını üret. Haftalık planlı/tamamlanan sayıları include etmek için tek
    yan etki: 1+N week_stats_for sorgusu yapar — küçük ölçekte makul.
    """
    if today is None:
        today = date.today()
    from sqlalchemy.orm import object_session
    db = object_session(teacher)
    student_count = 0
    total_planned = 0
    total_completed = 0
    if db is not None:
        students = (
            db.query(User)
            .filter(
                User.role == UserRole.STUDENT,
                User.teacher_id == teacher.id,
                User.is_active.is_(True),
            )
            .all()
        )
        student_count = len(students)
        for s in students:
            w = week_stats_for(db, s.id, today, tests_only=True)
            total_planned += w.planned
            total_completed += w.completed
    rate: int | None = None
    if total_planned > 0:
        rate = int(round(100 * total_completed / total_planned))
    return TeacherSummaryItem(
        id=teacher.id,
        full_name=teacher.full_name,
        email=teacher.email,
        is_active=bool(teacher.is_active),
        is_paused=bool(teacher.is_paused),
        pause_reason=teacher.pause_reason,
        paused_at=teacher.paused_at,
        student_count=student_count,
        weekly_planned=total_planned,
        weekly_completed=total_completed,
        weekly_rate_pct=rate,
        last_login_at=teacher.last_login_at,
        last_login_days=_days_since(teacher.last_login_at),
    )


def _invalidate_keys(institution_id: int, *suffixes: str) -> list[str]:
    """Frontend için queryKey prefix listesi üret."""
    base = f"institution:{institution_id}"
    keys = [base, f"{base}:dashboard", f"{base}:teachers"]
    for s in suffixes:
        keys.append(f"{base}:{s}")
    # Tekrarları koru (sıraya saygı), ama yine de tekleştir
    seen: set[str] = set()
    deduped: list[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return deduped


# =============================================================================
# 1) GET /institution/dashboard
# =============================================================================


@router.get("/dashboard", response_model=InstitutionDashboardResponse)
def institution_dashboard_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum geneli özet — KPI'lar + öğretmen özetleri + risk + pasif uyarısı.

    Eşdeğer Jinja: app/routes/institution.py:52-104 (institution_dashboard).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    summaries = teacher_summaries(db, institution_id=inst.id)

    # Agregat
    teacher_count = len(summaries)
    active_teacher_count = sum(
        1 for s in summaries
        if s.last_login_days is not None and s.last_login_days <= 7
    )
    student_count = sum(s.student_count for s in summaries)
    weekly_planned = sum(s.planned for s in summaries)
    weekly_completed = sum(s.completed for s in summaries)
    weekly_deneme_planned = sum(s.deneme_planned for s in summaries)
    weekly_deneme_completed = sum(s.deneme_completed for s in summaries)
    weekly_rate_pct: int | None = None
    if weekly_planned > 0:
        weekly_rate_pct = int(round(100 * weekly_completed / weekly_planned))

    # Risk paneli özet — kurumdaki aktif öğrenciler
    teacher_ids = [s.teacher.id for s in summaries]
    at_risk_count = 0
    at_risk_critical = 0
    if teacher_ids:
        active_students = (
            db.query(User)
            .filter(
                User.role == UserRole.STUDENT,
                User.teacher_id.in_(teacher_ids),
                User.is_active.is_(True),
            )
            .all()
        )
        risk_assessments = bulk_risk_assessment(db, students=active_students)
        at_risk = filter_at_risk(risk_assessments, min_level="medium")
        at_risk_count = len(at_risk)
        at_risk_critical = sum(1 for a in at_risk if a.level == "critical")

    # Pasif öğretmen — son 7 günde hiç aktivite yok
    inactives = inactive_teachers(db, institution_id=inst.id, days=7)
    inactive_count = len(inactives)
    inactive_names = [t.full_name for t in inactives[:3]]

    return InstitutionDashboardResponse(
        institution=_institution_brief(inst),
        aggregate=InstitutionAggregateInfo(
            teacher_count=teacher_count,
            active_teacher_count=active_teacher_count,
            student_count=student_count,
            weekly_planned=weekly_planned,
            weekly_completed=weekly_completed,
            weekly_rate_pct=weekly_rate_pct,
            weekly_deneme_planned=weekly_deneme_planned,
            weekly_deneme_completed=weekly_deneme_completed,
        ),
        risk=InstitutionRiskBadge(
            at_risk_count=at_risk_count,
            at_risk_critical=at_risk_critical,
        ),
        inactive=InstitutionInactiveBadge(
            inactive_teacher_count=inactive_count,
            inactive_teacher_names=inactive_names,
        ),
        teacher_summaries=[_teacher_summary_to_item(s) for s in summaries],
    )


# =============================================================================
# 2) GET /institution/teachers — liste
# =============================================================================


@router.get("/teachers", response_model=InstitutionTeacherListResponse)
def institution_teachers_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurumdaki öğretmenler listesi (agrega tablo).

    Eşdeğer Jinja: institution.py:107-129 (list_teachers).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    summaries = teacher_summaries(db, institution_id=inst.id)
    items = [_teacher_summary_to_item(s) for s in summaries]
    return InstitutionTeacherListResponse(
        institution=_institution_brief(inst),
        items=items,
        total=len(items),
    )


# =============================================================================
# 3) POST /institution/teachers — yeni öğretmen oluştur
# =============================================================================


@router.post(
    "/teachers",
    response_model=MutationResponse[TeacherCreateResult],
    status_code=status.HTTP_201_CREATED,
)
def institution_create_teacher_v2(
    body: TeacherCreateBody,
    request: Request,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Yeni öğretmen + güçlü geçici şifre.

    Şifre admin tarafından belirlenmez — sistem üretir, must_change_password=True
    ile öğretmen ilk girişte kendi şifresini koyar. Geçici şifre YANIT'ta tek
    seferlik döner; sonradan görüntülenemez.

    Eşdeğer Jinja: institution.py:131-195 (create_teacher).
    """
    full_name_clean = body.full_name.strip()
    email_clean = body.email.strip().lower()
    if not full_name_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "name_required",
                "message": "Ad ve soyad zorunlu.",
            },
        )
    # Basit email biçim doğrulaması — EmailStr kullanılmıyor çünkü
    # email-validator özel-amaçlı TLD'leri (.invalid vs.) red ediyor; v2'nin
    # diğer endpoint'leri (StudentCreateBody, ParentInviteBody) de plain str
    # kullanıp aynı kontrolü uyguluyor.
    if "@" not in email_clean or len(email_clean.split("@")) != 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_email",
                "message": "Geçerli bir e-posta gir.",
            },
        )
    local, _, domain = email_clean.partition("@")
    if not local or "." not in domain:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "invalid_email",
                "message": "Geçerli bir e-posta gir.",
            },
        )
    if db.query(User).filter(User.email == email_clean).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "email_exists",
                "message": "Bu e-posta zaten kayıtlı.",
            },
        )

    # Kota duvarı: plan öğretmen limitini aş(ma). (Davet yolu zaten gate'liydi;
    # doğrudan ekleme açıkta kalmıştı — bu düzeltme limiti tutarlı uygular.)
    inst = _get_institution_or_403(db, user.institution_id)
    try:
        check_quota_for_create(db, institution=inst, quota_key="teachers")
    except QuotaExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "quota_exceeded",
                "code": "quota_exceeded",
                "message": e.message,
                "details": {"limit": e.limit, "current": e.current, "quota_key": "teachers"},
            },
        )

    pwd = generate_strong_password(UserRole.TEACHER)
    new_teacher = User(
        email=email_clean,
        password_hash=hash_password(pwd),
        full_name=full_name_clean,
        role=UserRole.TEACHER,
        institution_id=user.institution_id,
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        must_change_password=True,
    )
    db.add(new_teacher)
    db.flush()
    log_action(
        db,
        action=AuditAction.USER_CREATE,
        actor_id=user.id,
        target_type="user",
        target_id=new_teacher.id,
        request=request,
        details={
            "email": email_clean,
            "role": "teacher",
            "institution_id": user.institution_id,
            "created_by_role": "institution_admin",
            "temp_password_issued": True,
        },
        autocommit=False,
    )
    db.commit()
    db.refresh(new_teacher)

    return MutationResponse[TeacherCreateResult](
        data=TeacherCreateResult(
            id=new_teacher.id,
            full_name=new_teacher.full_name,
            email=new_teacher.email,
            temp_password=pwd,
            must_change_password=True,
        ),
        invalidate=_invalidate_keys(user.institution_id),
    )


# =============================================================================
# 4) POST /institution/teachers/{id}/deactivate
# =============================================================================


@router.post(
    "/teachers/{teacher_id}/deactivate",
    response_model=MutationResponse[TeacherSummaryItem],
)
def institution_deactivate_teacher_v2(
    teacher_id: int,
    request: Request,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Öğretmeni pasifleştir (is_active=False). Tam silme YOK — veri korunur.

    Eşdeğer Jinja: institution.py:197-236 (deactivate_teacher).
    """
    teacher = _get_owned_teacher(db, teacher_id, user.institution_id)
    teacher.is_active = False
    log_action(
        db,
        action=AuditAction.USER_DEACTIVATE,
        actor_id=user.id,
        target_type="user",
        target_id=teacher.id,
        request=request,
        details={"performed_by_role": "institution_admin"},
        autocommit=False,
    )
    db.commit()
    db.refresh(teacher)
    return MutationResponse[TeacherSummaryItem](
        data=_teacher_to_summary_item(teacher),
        invalidate=_invalidate_keys(
            user.institution_id, f"teachers:{teacher_id}", "roster"
        ),
    )


# =============================================================================
# 5) POST /institution/teachers/{id}/activate
# =============================================================================


@router.post(
    "/teachers/{teacher_id}/activate",
    response_model=MutationResponse[TeacherSummaryItem],
)
def institution_activate_teacher_v2(
    teacher_id: int,
    request: Request,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Pasif öğretmeni geri aktif et.

    Eşdeğer Jinja: institution.py:322-357 (activate_teacher).
    """
    teacher = _get_owned_teacher(db, teacher_id, user.institution_id)
    teacher.is_active = True
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="user",
        target_id=teacher.id,
        request=request,
        details={
            "action": "activate",
            "performed_by_role": "institution_admin",
        },
        autocommit=False,
    )
    db.commit()
    db.refresh(teacher)
    return MutationResponse[TeacherSummaryItem](
        data=_teacher_to_summary_item(teacher),
        invalidate=_invalidate_keys(
            user.institution_id, f"teachers:{teacher_id}", "roster"
        ),
    )


# =============================================================================
# 6) POST /institution/teachers/{id}/pause-alerts
# =============================================================================


@router.post(
    "/teachers/{teacher_id}/pause-alerts",
    response_model=MutationResponse[TeacherSummaryItem],
)
def institution_pause_alerts_v2(
    teacher_id: int,
    request: Request,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Öğretmenin kişisel uyarı/notification akışını sustur (is_paused=True).

    is_active'ten farklı: öğretmen giriş yapmaya + öğrencilerine erişmeye
    devam eder; sadece haftalık digest e-postası ve kişisel uyarılar durur.

    Eşdeğer Jinja: institution.py:238-281 (pause_teacher_alerts).
    """
    teacher = _get_owned_teacher(db, teacher_id, user.institution_id)
    pause_user(db, teacher, actor=user, reason=REASON_MANUAL)
    log_action(
        db,
        action=AuditAction.USER_PAUSE_ALERTS,
        actor_id=user.id,
        target_type="user",
        target_id=teacher.id,
        request=request,
        details={"role": "teacher", "reason": REASON_MANUAL},
    )
    db.refresh(teacher)
    return MutationResponse[TeacherSummaryItem](
        data=_teacher_to_summary_item(teacher),
        invalidate=_invalidate_keys(
            user.institution_id, f"teachers:{teacher_id}"
        ),
    )


# =============================================================================
# 7) POST /institution/teachers/{id}/resume-alerts
# =============================================================================


@router.post(
    "/teachers/{teacher_id}/resume-alerts",
    response_model=MutationResponse[TeacherSummaryItem],
)
def institution_resume_alerts_v2(
    teacher_id: int,
    request: Request,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Susturulmuş uyarıları tekrar aç (manuel resume → 7 gün sticky cooldown).

    Eşdeğer Jinja: institution.py:283-320 (resume_teacher_alerts).
    """
    teacher = _get_owned_teacher(db, teacher_id, user.institution_id)
    resume_user(db, teacher, actor=user, is_auto_resume=False)
    log_action(
        db,
        action=AuditAction.USER_RESUME_ALERTS,
        actor_id=user.id,
        target_type="user",
        target_id=teacher.id,
        request=request,
        details={"role": "teacher"},
    )
    db.refresh(teacher)
    return MutationResponse[TeacherSummaryItem](
        data=_teacher_to_summary_item(teacher),
        invalidate=_invalidate_keys(
            user.institution_id, f"teachers:{teacher_id}"
        ),
    )


# =============================================================================
# 8) GET /institution/teachers/{id} — kart (öğrenci listesi + agrega)
# =============================================================================


@router.get(
    "/teachers/{teacher_id}",
    response_model=TeacherCardResponse,
)
def institution_teacher_card_v2(
    teacher_id: int,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Öğretmen kart — gizlilik korumalı. Öğrenci adı + sınıf + haftalık oran;
    detay linki YOK.

    Eşdeğer Jinja: institution.py:359-423 (teacher_card).
    """
    teacher = _get_owned_teacher(db, teacher_id, user.institution_id)
    today = date.today()
    students = (
        db.query(User)
        .filter(User.role == UserRole.STUDENT, User.teacher_id == teacher.id)
        .order_by(User.full_name)
        .all()
    )
    rows: list[TeacherCardStudentRow] = []
    total_planned = 0
    total_completed = 0
    total_deneme_planned = 0
    total_deneme_completed = 0
    for s in students:
        td = week_test_deneme_for(db, s.id, today)  # test + deneme AYRI
        rate: int | None = None
        if td.test_planned > 0:
            rate = int(round(100 * td.test_completed / td.test_planned))
        total_planned += td.test_planned
        total_completed += td.test_completed
        total_deneme_planned += td.deneme_planned
        total_deneme_completed += td.deneme_completed
        rows.append(TeacherCardStudentRow(
            id=s.id,
            full_name=s.full_name,
            grade_level=s.grade_level,
            display_grade_label=getattr(s, "display_grade_label", None),
            is_active=bool(s.is_active),
            weekly_planned=td.test_planned,
            weekly_completed=td.test_completed,
            weekly_rate_pct=rate,
            weekly_deneme_planned=td.deneme_planned,
            weekly_deneme_completed=td.deneme_completed,
        ))
    overall_rate: int | None = None
    if total_planned > 0:
        overall_rate = int(round(100 * total_completed / total_planned))

    return TeacherCardResponse(
        teacher=_teacher_to_summary_item(teacher, today=today),
        students=rows,
        total_planned=total_planned,
        total_completed=total_completed,
        overall_rate_pct=overall_rate,
        total_deneme_planned=total_deneme_planned,
        total_deneme_completed=total_deneme_completed,
    )


# =============================================================================
# 9) GET /institution/roster — öğrenci roster + filtre seçenekleri
# =============================================================================


@router.get(
    "/roster",
    response_model=InstitutionRosterResponse,
)
def institution_roster_v2(
    teacher_id: int | None = Query(None, ge=1, description="Öğretmen filtresi"),
    grade: int | None = Query(None, ge=5, le=12, description="Sınıf seviyesi filtresi"),
    is_graduate: bool | None = Query(None, description="Mezun mu?"),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum altındaki tüm öğrenciler + öğretmen + haftalık özet.

    Filtreler:
      - teacher_id → sadece o öğretmenin öğrencileri
      - grade → sınıf seviyesi (5-12)
      - is_graduate → mezunları ayrı süz

    Eşdeğer Jinja: institution.py:992-1041 (institution_roster_view).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    today = date.today()

    # Öğretmenler — filtre seçenekleri için
    teachers = (
        db.query(User)
        .filter(
            User.institution_id == inst.id,
            User.role == UserRole.TEACHER,
        )
        .order_by(User.full_name)
        .all()
    )
    teacher_options = [
        RosterTeacherOption(id=t.id, full_name=t.full_name) for t in teachers
    ]
    teacher_names = {t.id: t.full_name for t in teachers}
    teacher_ids = list(teacher_names.keys())

    if not teacher_ids:
        return InstitutionRosterResponse(
            institution=_institution_brief(inst),
            items=[],
            total=0,
            filters=RosterFilterOptions(
                teachers=[], grades=[], has_graduates=False,
            ),
        )

    # Filtre uygulanmış öğrenci sorgusu
    q = db.query(User).filter(
        User.role == UserRole.STUDENT,
        User.teacher_id.in_(teacher_ids),
    )
    if teacher_id is not None:
        if teacher_id not in teacher_names:
            # Cross-tenant veya yanlış teacher_id → boş liste
            q = q.filter(User.id == -1)
        else:
            q = q.filter(User.teacher_id == teacher_id)
    if grade is not None:
        q = q.filter(User.grade_level == grade, User.is_graduate.is_(False))
    if is_graduate is True:
        q = q.filter(User.is_graduate.is_(True))
    if is_graduate is False:
        q = q.filter(User.is_graduate.is_(False))

    students = q.order_by(User.full_name).all()

    # Mezun var mı? Filtre options için ayrı sorgu (filtreden bağımsız)
    has_graduates = (
        db.query(User.id)
        .filter(
            User.role == UserRole.STUDENT,
            User.teacher_id.in_(teacher_ids),
            User.is_graduate.is_(True),
        )
        .first()
        is not None
    )

    # Mevcut sınıf seviyeleri (filtreden bağımsız)
    grade_rows = (
        db.query(User.grade_level)
        .filter(
            User.role == UserRole.STUDENT,
            User.teacher_id.in_(teacher_ids),
            User.is_graduate.is_(False),
            User.grade_level.isnot(None),
        )
        .distinct()
        .all()
    )
    grades_present = sorted({row[0] for row in grade_rows if row[0] is not None})

    items: list[RosterRowItem] = []
    for s in students:
        w = week_stats_for(db, s.id, today, tests_only=True)
        rate: int | None = None
        if w.planned > 0:
            rate = int(round(100 * w.completed / w.planned))
        items.append(RosterRowItem(
            student_id=s.id,
            full_name=s.full_name,
            grade_level=s.grade_level,
            display_grade_label=getattr(s, "display_grade_label", None),
            teacher_id=s.teacher_id,
            teacher_name=teacher_names.get(s.teacher_id or 0, "—"),
            weekly_planned=w.planned,
            weekly_completed=w.completed,
            weekly_rate_pct=rate,
            is_active=bool(s.is_active),
            is_paused=bool(s.is_paused),
        ))

    return InstitutionRosterResponse(
        institution=_institution_brief(inst),
        items=items,
        total=len(items),
        filters=RosterFilterOptions(
            teachers=teacher_options,
            grades=grades_present,
            has_graduates=has_graduates,
        ),
    )


# =============================================================================
# 10) GET /institution/goals — kurum geneli hedef özeti
# =============================================================================


@router.get(
    "/goals",
    response_model=InstitutionGoalsResponse,
)
def institution_goals_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum geneli öğrenci hedef agrega özeti (gizlilik: öğrenci-bazlı detay
    görünmez).

    Eşdeğer Jinja: app/routes/goals.py:478-497 (institution_goals_page).
    """
    summary = institution_goal_summary(db, institution_id=user.institution_id)
    return InstitutionGoalsResponse(
        students_with_goals=summary["students_with_goals"],
        students_without_goals=summary["students_without_goals"],
        total_goals=summary["total_goals"],
        achieved_goals=summary["achieved_goals"],
        active_goals=summary["active_goals"],
        avg_overall_pct=summary["avg_overall_pct"],
    )


# =============================================================================
# D4 Paket 2 — Davetiyeler
# =============================================================================


def _invitation_to_item(inv: Invitation, origin: str) -> InvitationItem:
    """Bir Invitation modelini API zarfına çevir. signup_url tam URL döner."""
    return InvitationItem(
        id=inv.id,
        token=inv.token,
        full_name=inv.full_name,
        email=inv.email,
        role=inv.role.value if hasattr(inv.role, "value") else str(inv.role),
        status=inv.status.value,
        created_at=inv.created_at,
        expires_at=inv.expires_at,
        consumed_at=inv.consumed_at,
        consumed_by_user_id=inv.consumed_by_user_id,
        revoked_at=inv.revoked_at,
        is_usable=inv.is_usable,
        signup_url=f"{origin.rstrip('/')}/signup/invite/{inv.token}",
    )


def _request_origin(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


@router.get("/invitations", response_model=InvitationListResponse)
def institution_invitations_list_v2(
    request: Request,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurumun tüm davetiyeleri (pending / consumed / expired / revoked).

    Eşdeğer Jinja: institution.py:429-458 (list_invitations).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    origin = _request_origin(request)
    invs = (
        db.query(Invitation)
        .filter(Invitation.institution_id == inst.id)
        .order_by(Invitation.created_at.desc())
        .all()
    )
    items = [_invitation_to_item(i, origin) for i in invs]
    return InvitationListResponse(
        institution=_institution_brief(inst),
        items=items,
        total=len(items),
        origin=origin,
    )


@router.post(
    "/invitations",
    response_model=MutationResponse[InvitationItem],
    status_code=status.HTTP_201_CREATED,
)
def institution_invitations_create_v2(
    body: InvitationCreateBody,
    request: Request,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Yeni öğretmen davetiyesi üret.

    E-posta opsiyonel — boşsa "açık davetiye" (linki olan herkes kullanabilir).
    Dolu ise mevcut user kontrolü + kuota kontrolü yapılır.

    Eşdeğer Jinja: institution.py:461-531 (create_invitation).
    """
    full_name_clean = (body.full_name or "").strip() or None
    email_clean = (body.email or "").strip().lower() or None

    if email_clean and db.query(User).filter(User.email == email_clean).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "email_exists",
                "message": f"{email_clean} zaten kayıtlı — davetiye gerekmez.",
            },
        )

    # Kuota kontrolü — öğretmen davet ediliyor
    inst = _get_institution_or_403(db, user.institution_id)
    try:
        check_quota_for_create(db, institution=inst, quota_key="teachers")
    except QuotaExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "quota_exceeded",
                "code": "quota_exceeded",
                "message": e.message,
            },
        )

    token = secrets.token_urlsafe(32)
    inv = Invitation(
        token=token,
        email=email_clean,
        full_name=full_name_clean,
        role=UserRole.TEACHER,
        institution_id=user.institution_id,
        created_by_user_id=user.id,
        expires_at=invitation_default_expiry(),
    )
    db.add(inv)
    db.flush()
    log_action(
        db,
        action=AuditAction.USER_CREATE,
        actor_id=user.id,
        target_type="invitation",
        target_id=inv.id,
        request=request,
        details={
            "type": "invitation_created",
            "role": "teacher",
            "institution_id": user.institution_id,
            "email": email_clean,
        },
        autocommit=False,
    )
    db.commit()
    db.refresh(inv)

    return MutationResponse[InvitationItem](
        data=_invitation_to_item(inv, _request_origin(request)),
        invalidate=_invalidate_keys(user.institution_id, "invitations"),
    )


@router.post(
    "/invitations/{invitation_id}/revoke",
    response_model=MutationResponse[InvitationItem],
)
def institution_invitations_revoke_v2(
    invitation_id: int,
    request: Request,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Bekleyen davetiyeyi iptal et.

    Eşdeğer Jinja: institution.py:534-575 (revoke_invitation).
    """
    inv = (
        db.query(Invitation)
        .filter(
            Invitation.id == invitation_id,
            Invitation.institution_id == user.institution_id,
        )
        .first()
    )
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "invitation_not_found",
                "message": "Davetiye bulunamadı.",
            },
        )
    if not inv.is_usable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "invitation_not_usable",
                "message": "Bu davetiye zaten kullanılmış, süresi geçmiş veya iptal edilmiş.",
            },
        )
    inv.revoked_at = datetime.now(timezone.utc)
    inv.revoked_by_user_id = user.id
    log_action(
        db,
        action=AuditAction.USER_DEACTIVATE,
        actor_id=user.id,
        target_type="invitation",
        target_id=inv.id,
        request=request,
        details={"type": "invitation_revoked"},
        autocommit=False,
    )
    db.commit()
    db.refresh(inv)

    return MutationResponse[InvitationItem](
        data=_invitation_to_item(inv, _request_origin(request)),
        invalidate=_invalidate_keys(user.institution_id, "invitations"),
    )


# =============================================================================
# D4 Paket 2 — Aktivite ısı haritası
# =============================================================================


@router.get("/activity-heatmap", response_model=ActivityHeatmapResponse)
def institution_activity_heatmap_v2(
    weeks: int = Query(4, description="4 veya 12; geçersizse 4'e düşer"),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Öğretmen aktivite ısı haritası — son N hafta.

    Aktivite kaynakları: login + task oluşturma + veli notu. Skor 0..1.

    Eşdeğer Jinja: institution.py:578-616 (activity_heatmap_panel).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    if weeks not in (4, 12):
        weeks = 4

    heatmaps = teacher_activity_heatmap(
        db, institution_id=inst.id, weeks=weeks,
    )
    inactive_count = sum(1 for h in heatmaps if h.is_inactive)

    rows: list[TeacherHeatmapRow] = []
    for h in heatmaps:
        cells = [
            HeatmapCellData(
                day=c.day,
                login_count=c.login_count,
                tasks_created=c.tasks_created,
                notes_created=c.notes_created,
                activity_score=float(c.activity_score),
            )
            for c in h.cells
        ]
        rows.append(TeacherHeatmapRow(
            teacher_id=h.teacher.id,
            full_name=h.teacher.full_name,
            cells=cells,
            last_active_day=h.last_active_day,
            days_since_active=h.days_since_active,
            total_logins=h.total_logins,
            total_tasks=h.total_tasks,
            total_notes=h.total_notes,
            is_inactive=h.is_inactive,
            is_new=h.is_new,
        ))

    return ActivityHeatmapResponse(
        institution=_institution_brief(inst),
        weeks=weeks,
        days_count=weeks * 7,
        inactive_threshold_days=INACTIVE_DAYS,
        inactive_count=inactive_count,
        teachers=rows,
    )


# =============================================================================
# D4 Paket 2 — Risk listesi (privacy korumalı)
# =============================================================================


@router.get("/at-risk", response_model=AtRiskResponse)
def institution_at_risk_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum geneli risk panel — gizlilik korunur.

    Öğrenci-öğretmen eşlemesi görünür ama detay sayfasına link YOK.
    Mute durumu rozet olarak gösterilir (kurum admin'e gizleme yok).

    Eşdeğer Jinja: at_risk.py:177-244 (institution_at_risk_panel).
    """
    inst = _get_institution_or_403(db, user.institution_id)

    teacher_ids_query = (
        db.query(User.id)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id == inst.id,
        )
    )
    teacher_ids = [t[0] for t in teacher_ids_query.all()]

    students: list[User] = []
    teacher_map: dict[int, User] = {}
    if teacher_ids:
        students = (
            db.query(User)
            .filter(
                User.role == UserRole.STUDENT,
                User.teacher_id.in_(teacher_ids),
                User.is_active.is_(True),
            )
            .order_by(User.full_name)
            .all()
        )
        for t in db.query(User).filter(User.id.in_(teacher_ids)).all():
            teacher_map[t.id] = t

    assessments = bulk_risk_assessment(db, students=students)
    at_risk = filter_at_risk(assessments, min_level="medium")
    healthy_count = sum(1 for a in assessments if a.level == "ok")

    student_ids = [a.student.id for a in at_risk]
    muted_map = get_active_mutes_for_students(db, student_ids)

    counts = AtRiskCountsInfo(
        critical=sum(1 for a in at_risk if a.level == "critical"),
        high=sum(1 for a in at_risk if a.level == "high"),
        medium=sum(1 for a in at_risk if a.level == "medium"),
    )

    rows: list[AtRiskRowItem] = []
    for a in at_risk:
        teacher = teacher_map.get(a.student.teacher_id) if a.student.teacher_id else None
        rows.append(AtRiskRowItem(
            student_id=a.student.id,
            full_name=a.student.full_name,
            grade_level=a.student.grade_level,
            display_grade_label=getattr(a.student, "display_grade_label", None),
            is_active=bool(a.student.is_active),
            is_paused=bool(a.student.is_paused),
            pause_reason=a.student.pause_reason,
            teacher_id=a.student.teacher_id,
            teacher_name=(teacher.full_name if teacher else None),
            score=a.score,
            level=a.level,
            level_label=a.level_label,
            level_emoji=a.level_emoji,
            indicators=[
                RiskIndicatorItem(
                    code=ind.code, title=ind.title, detail=ind.detail, weight=ind.weight,
                )
                for ind in a.indicators
            ],
            last_login_days=a.last_login_days,
            weekly_planned=a.weekly_planned,
            weekly_completed=a.weekly_completed,
            weekly_rate_pct=a.weekly_rate_pct,
            is_muted=a.student.id in muted_map,
        ))

    return AtRiskResponse(
        institution=_institution_brief(inst),
        counts=counts,
        total_students=len(students),
        healthy_count=healthy_count,
        at_risk=rows,
    )


# =============================================================================
# D4 Paket 2 — Burnout listesi
# =============================================================================


@router.get("/burnout", response_model=BurnoutResponse)
def institution_burnout_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum geneli burnout listesi. Risk skoru > 0 olan tüm öğrenciler;
    sıra: skor desc, ad asc.

    Eşdeğer Jinja: dna.py:220-260 (institution_burnout).
    """
    inst = _get_institution_or_403(db, user.institution_id)

    # Öğretmen-ad eşlemesi (kurum içi)
    teachers = (
        db.query(User)
        .filter(
            User.institution_id == inst.id,
            User.role == UserRole.TEACHER,
        )
        .all()
    )
    teacher_map = {t.id: t for t in teachers}

    students = (
        db.query(User)
        .filter(
            User.institution_id == inst.id,
            User.role == UserRole.STUDENT,
        )
        .order_by(User.full_name)
        .all()
    )
    now = datetime.now(timezone.utc)
    rows: list[BurnoutRowItem] = []
    for s in students:
        report = compute_burnout(db, student_id=s.id, now=now)
        if report.risk_score == 0:
            continue
        teacher = teacher_map.get(s.teacher_id) if s.teacher_id else None
        rows.append(BurnoutRowItem(
            student_id=s.id,
            full_name=s.full_name,
            grade_level=s.grade_level,
            display_grade_label=getattr(s, "display_grade_label", None),
            teacher_id=s.teacher_id,
            teacher_name=(teacher.full_name if teacher else None),
            risk_score=report.risk_score,
            risk_level=report.risk_level,
            signal_count=len(report.signals),
            signals=[
                BurnoutSignalItem(
                    kind=sig.kind,
                    severity=str(sig.severity),
                    label=sig.label,
                    emoji=sig.emoji,
                    detail=sig.detail,
                    metric=sig.metric,
                )
                for sig in report.signals
            ],
        ))
    rows.sort(key=lambda r: (-r.risk_score, r.full_name.lower()))

    return BurnoutResponse(
        institution=_institution_brief(inst),
        items=rows,
        total=len(rows),
    )


@router.get("/logo/{institution_id}")
def institution_logo_v2(
    institution_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Kurum logosunu servis eder (co-branding `<img src>`).

    Erişim: süper admin (her kurum) VEYA kuruma bağlı kullanıcı (kendi kurumu —
    yönetici/öğretmen/öğrenci/veli). Logo kişisel veri değil; özel cache.
    """
    if user.role != UserRole.SUPER_ADMIN and user.institution_id != institution_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "logo_not_found", "message": "Logo bulunamadı."},
        )
    inst = db.get(Institution, institution_id)
    if inst is None or not inst.logo_content_type or not inst.logo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "logo_not_found", "message": "Logo bulunamadı."},
        )
    return Response(
        content=inst.logo_data,
        media_type=inst.logo_content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("/notify-coach", response_model=MutationResponse[NotifyCoachResult])
def institution_notify_coach_v2(
    body: NotifyCoachBody,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Tükenmişlik/risk panosundan ilgili koça müdahale talebi açar (aşağı yönlü
    SupportRequest, audience=teacher). Gizlilik: kurum yöneticisi öğrenci detayına
    inemez; müdahale kolu KOÇtur — bu uç koça bildirim/talep iletir.

    Koç, kurum yöneticisinin kendi kurumuna bağlı olmalı (tenant izolasyonu).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    teacher = (
        db.query(User)
        .filter(
            User.id == body.teacher_id,
            User.institution_id == inst.id,
            User.role == UserRole.TEACHER,
        )
        .first()
    )
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "coach_not_found",
                    "message": "Koç bulunamadı."},
        )

    student_name = (body.student_name or "").strip()
    ctx_label = {
        "burnout": "tükenmişlik panosunda",
        "at_risk": "risk panosunda",
    }.get(body.context or "", "panoda")
    subject = (
        f"Riskli öğrenci: {student_name}" if student_name
        else "Risk altındaki öğrenci için müdahale"
    )
    note = (body.note or "").strip()
    lines = [
        f"Kurum yöneticisi, {ctx_label} risk işareti taşıyan bir öğrenciniz için"
        f" sizinle birebir görüşmenizi/inceleme yapmanızı rica ediyor.",
    ]
    if student_name:
        lines.append(f"Öğrenci: {student_name}")
    if note:
        lines.append(f"Not: {note}")
    lines.append(
        "Lütfen öğrenciyi kendi panelinizden inceleyin; gerekiyorsa programı"
        " ve çalışma temposunu gözden geçirin."
    )
    message_body = "\n".join(lines)

    try:
        req = support_svc.notify_coach(
            db, admin=user, teacher=teacher, subject=subject, body=message_body,
            category="student_risk",
        )
    except support_svc.SupportError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation", "code": e.code, "message": e.message},
        )
    db.commit()
    return MutationResponse[NotifyCoachResult](
        data=NotifyCoachResult(
            request_id=req.id,
            teacher_id=teacher.id,
            teacher_name=teacher.full_name or teacher.email,
        ),
        invalidate=["support:inbox", "support:mine", "institution:me:interventions"],
    )


@router.get("/coach-interventions", response_model=CoachInterventionsResponse)
def institution_coach_interventions_v2(
    days: int = Query(60, ge=1, le=365),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Yöneticinin "Koça ilet" ile açtığı müdahale talepleri (geçmiş). Risk/
    tükenmişlik panosunda öğrenci satırına "X tarihinde koça iletildi" eşlemek
    için ad-bazlı eşleşme kullanılır (notify-coach öğrenciyi isimle referans eder)."""
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    from app.models import (
        SUPPORT_AUDIENCE_TEACHER, SUPPORT_STATUS_LABELS_TR, SupportRequest,
    )
    cutoff = _dt.now(_tz.utc) - _td(days=days)
    rows = (
        db.query(SupportRequest)
        .filter(
            SupportRequest.requester_id == user.id,
            SupportRequest.audience == SUPPORT_AUDIENCE_TEACHER,
            SupportRequest.category == "student_risk",
            SupportRequest.created_at >= cutoff,
        )
        .order_by(SupportRequest.created_at.desc())
        .all()
    )
    prefix = "Riskli öğrenci: "
    items: list[CoachInterventionItem] = []
    for r in rows:
        sname = None
        if r.subject and r.subject.startswith(prefix):
            sname = r.subject[len(prefix):].strip() or None
        items.append(CoachInterventionItem(
            request_id=r.id,
            student_name=sname,
            coach_name=(r.target_user.full_name or r.target_user.email) if r.target_user else None,
            created_at=r.created_at,
            status=r.status,
            status_label=SUPPORT_STATUS_LABELS_TR.get(r.status, r.status),
        ))
    return CoachInterventionsResponse(items=items)


# =============================================================================
# D4 Paket 2 — Kohortlar (4 sekme)
# =============================================================================


_COHORT_FNS = {
    "grade": cohort_by_grade,
    "track": cohort_by_track,
    "curriculum": cohort_by_curriculum,
    "exam_target": cohort_by_exam_target,
}
_COHORT_TAB_LABELS: list[CohortTabInfo] = [
    CohortTabInfo(key="grade", label="Sınıf"),
    CohortTabInfo(key="track", label="Alan"),
    CohortTabInfo(key="curriculum", label="Müfredat"),
    CohortTabInfo(key="exam_target", label="Hedef Sınav"),
]


@router.get("/cohorts", response_model=CohortsResponse)
def institution_cohorts_v2(
    tab: str = Query("grade", description="grade / track / curriculum / exam_target"),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kohort karşılaştırma — 4 sekme (grade / track / curriculum / exam_target).

    Sadece aktif sekme'nin verisi hesaplanır (performans). WoW ve sekme listesi
    her zaman döner.

    Eşdeğer Jinja: institution.py:865-920 (cohort_panel).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    if tab not in _COHORT_FNS:
        tab = "grade"
    active_tab: CohortTabLiteral = tab  # type: ignore[assignment]

    cohorts = _COHORT_FNS[tab](db, institution_id=inst.id)
    wow = institution_week_over_week(db, institution_id=inst.id)

    cohort_items = [
        CohortStatsItem(
            cohort_key=c.cohort_key,
            cohort_label=c.cohort_label,
            student_count=c.student_count,
            weekly_planned=c.weekly_planned,
            weekly_completed=c.weekly_completed,
            weekly_rate_pct=c.weekly_rate_pct,
            at_risk_count=c.at_risk_count,
            at_risk_pct=c.at_risk_pct,
            rate_color=c.rate_color,
        )
        for c in cohorts
    ]

    return CohortsResponse(
        institution=_institution_brief(inst),
        active_tab=active_tab,
        tabs=_COHORT_TAB_LABELS,
        cohorts=cohort_items,
        wow=WeekOverWeekInfo(
            this_week_rate=wow.this_week_rate,
            last_week_rate=wow.last_week_rate,
            delta_pct=wow.delta_pct,
            direction=wow.direction,
        ),
    )


# =============================================================================
# D4 Paket 3 — Abonelik (subscription)
# =============================================================================


def _status_to_info(status_obj) -> SubscriptionStatusInfo:
    """SubscriptionStatus dataclass → Pydantic info."""
    return SubscriptionStatusInfo(
        kind=status_obj.kind,
        kind_label=status_obj.kind_label,
        period_end=status_obj.period_end,
        pause_until=status_obj.pause_until,
        in_summer_window=status_obj.in_summer_window,
        can_pause=status_obj.can_pause,
        can_resume=status_obj.can_resume,
        can_switch_to_academic_year=status_obj.can_switch_to_academic_year,
        days_until_period_end=status_obj.days_until_period_end,
        performance_guarantee=status_obj.performance_guarantee,
        guarantee_extended_at=status_obj.guarantee_extended_at,
    )


def _subscription_keys(institution_id: int) -> list[str]:
    return _invalidate_keys(institution_id, "subscription", "quota")


def _institution_plan_label(plan_code: str) -> str:
    """Plan kodu → okunur ad (kurum). get_plan_info varsa onu kullan."""
    from app.services.plans import get_plan_info
    info = get_plan_info(plan_code)
    if info:
        return info.label
    return {"free": "Kurum Tanıma"}.get(plan_code, plan_code)


def _institution_upgrade_options() -> list[InstitutionPlanOption]:
    """Yükseltme talebi için kurum kademeleri — /pricing kataloğu (tek kaynak)."""
    from app.services import pricing
    cat = pricing.get_pricing_catalog()
    out: list[InstitutionPlanOption] = []
    for t in cat["institution"]["tiers"]:
        mc = t.get("max_coaches")
        coaches = f"{t['min_coaches']}+ koç" if mc is None else f"{t['min_coaches']}–{mc} koç"
        if t.get("price_hidden") or t.get("monthly_total") is None:
            price = "Özel teklif"
        else:
            price = f"{int(t['monthly_total']):,}".replace(",", ".") + " ₺/ay"
        out.append(InstitutionPlanOption(code=t["code"], label=t["label"], coaches=coaches, price_label=price))
    return out


def _pending_institution_sub_request(db: Session, institution_id: int):
    """Bu kuruma ait bekleyen (status=new) abonelik talebini döner (yoksa None).

    Mesajdaki `kurum_id={id}` işaretinden eşler — substring çakışmasına karşı
    Python tarafında tam sayı karşılaştırması.
    """
    import re
    from app.models.contact_request import ContactRequest
    rows = (
        db.query(ContactRequest)
        .filter(ContactRequest.source == "subscription_request", ContactRequest.status == "new")
        .order_by(ContactRequest.created_at.desc())
        .all()
    )
    for cr in rows:
        if cr.message:
            m = re.search(r"kurum_id=(\d+)", cr.message)
            if m and int(m.group(1)) == institution_id:
                return cr
    return None


def _requested_plan_label_from_message(message: str | None) -> str | None:
    """Bekleyen talebin mesajından hedef paket etiketini çıkar (varsa)."""
    import re
    if not message:
        return None
    m = re.search(r"hedef=([^·]+)·", message)
    return m.group(1).strip() if m else None


@router.get("/subscription", response_model=SubscriptionResponse)
def institution_subscription_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Abonelik durumu + 60g garanti değerlendirmesi.

    Eşdeğer Jinja: institution.py:1043-1069 (subscription_page).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    status_info = get_subscription_status(inst)
    guarantee_eval = evaluate_guarantee(db, institution=inst)
    pending = _pending_institution_sub_request(db, inst.id)
    return SubscriptionResponse(
        institution=_institution_brief(inst),
        plan=inst.plan or "free",
        plan_label=_institution_plan_label(inst.plan or "free"),
        status=_status_to_info(status_info),
        guarantee_evaluation=GuaranteeEvaluationInfo(
            eligible=guarantee_eval.eligible,
            period_started_at=guarantee_eval.period_started_at,
            days_into_period=guarantee_eval.days_into_period,
            period_total_days=guarantee_eval.period_total_days,
            average_completion_rate=guarantee_eval.average_completion_rate,
            threshold=guarantee_eval.threshold,
            triggered=guarantee_eval.triggered,
            already_extended=guarantee_eval.already_extended,
            can_extend=guarantee_eval.can_extend,
            note=guarantee_eval.note,
            student_count=guarantee_eval.student_count,
            total_planned_questions=guarantee_eval.total_planned_questions,
            total_completed_questions=guarantee_eval.total_completed_questions,
            is_provisional=guarantee_eval.is_provisional,
        ),
        available_plans=_institution_upgrade_options(),
        pending_upgrade_request=pending is not None,
        requested_plan_label=_requested_plan_label_from_message(pending.message) if pending else None,
    )


@router.post(
    "/subscription-request",
    response_model=MutationResponse[SubscriptionRequestResult],
)
def institution_subscription_request_v2(
    body: SubscriptionUpgradeRequestBody,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum yöneticisi plan yükseltme TALEBİ — satın alma DEĞİL.

    Talep `contact_requests`'e (source=subscription_request, mesajda kurum_id=N)
    düşer → süper admin İletişim Talepleri'nde "Abonelik talebi (kurum)" olarak
    görür → kurum detayından planı değiştirir. Koç akışıyla simetrik. Idempotent:
    bekleyen talep varsa tekrar oluşturmaz. Migration YOK.
    """
    from app.models.contact_request import ContactRequest

    inst = _get_institution_or_403(db, user.institution_id)

    # Bekleyen talep varsa tekrar oluşturma (idempotent)
    pending = _pending_institution_sub_request(db, inst.id)
    if pending is not None:
        return MutationResponse[SubscriptionRequestResult](
            data=SubscriptionRequestResult(
                ok=True, already_pending=True,
                message="Zaten bekleyen bir yükseltme talebin var. Ekibimiz en kısa sürede iletişime geçecek.",
            ),
            invalidate=_subscription_keys(inst.id),
        )

    # Hedef paket (opsiyonel) — geçerli kademe ise kod + etiketini sakla.
    # hedef_kod, süper admin kurum sayfasındaki PlanCard'da ön-seçim için kullanılır
    # (admin tekrar seçmesin — kurum hangi paketi istediyse o gelir).
    options = {o.code: o for o in _institution_upgrade_options()}
    target = (body.plan or "").strip()
    valid_target = target if target in options else ""
    target_label = options[target].label if target in options else "Belirtilmedi"

    teacher_count = (
        db.query(User)
        .filter(
            User.institution_id == inst.id,
            User.role == UserRole.TEACHER,
            User.is_active.is_(True),
        )
        .count()
    )
    note = (body.note or "").strip()
    note_part = f" · not: {note[:300]}" if note else ""
    cr = ContactRequest(
        name=user.full_name or user.email,
        email=user.email,
        institution_name=inst.name,
        coach_count=teacher_count,
        source="subscription_request",
        message=(
            f"Kurum paket yükseltme talebi · hedef={target_label} · "
            f"mevcut={_institution_plan_label(inst.plan or 'free')} · "
            f"{teacher_count} aktif öğretmen{note_part} · "
            f"hedef_kod={valid_target} · kurum_id={inst.id}"
        ),
    )
    db.add(cr)
    db.commit()

    # Süper admin/satış inbox'una bildir — kurum talebi proaktif uyarı.
    try:
        from app.services import pricing as _pricing
        from app.services.email_service import send_email
        catalog = _pricing.get_pricing_catalog()
        to = (catalog.get("contact") or {}).get("sales_email") or ""
        if "<" in to and ">" in to:
            to = to.split("<", 1)[1].rstrip(">").strip()
        if to:
            send_email(to=to, template="contact_request_admin", ctx={
                "name": cr.name, "email": cr.email, "phone": "",
                "institution_name": cr.institution_name or "",
                "coach_count": str(cr.coach_count or ""),
                "source_label": "Abonelik talebi (kurum)",
                "message": cr.message or "",
            })
    except Exception:
        logger.exception("Kurum abonelik talebi admin maili gönderim hatası")

    return MutationResponse[SubscriptionRequestResult](
        data=SubscriptionRequestResult(
            ok=True,
            message="Talebin alındı. Ekibimiz en kısa sürede seninle iletişime geçecek.",
        ),
        invalidate=_subscription_keys(inst.id) + ["admin:contact-requests"],
    )


@router.post(
    "/subscription/switch-academic-year",
    response_model=MutationResponse[SubscriptionStatusInfo],
)
def institution_subscription_switch_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Aylık → akademik yıl planına geçiş.

    Eşdeğer Jinja: institution.py:1072-1089 (subscription_switch_academic).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    switch_to_academic_year(
        db, institution=inst, actor_user_id=user.id,
        note="Kurum yöneticisi akademik yıla geçti",
    )
    status_info = get_subscription_status(inst)
    return MutationResponse[SubscriptionStatusInfo](
        data=_status_to_info(status_info),
        invalidate=_subscription_keys(inst.id),
    )


@router.post(
    "/subscription/pause",
    response_model=MutationResponse[SubscriptionStatusInfo],
)
def institution_subscription_pause_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Yaz pause moduna geç (sadece Tem-Ağu penceresi + akademik yıl planı).

    Eşdeğer Jinja: institution.py:1092-1119 (subscription_pause).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    if not is_summer_window():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "summer_window_required",
                "message": "Pause moduna sadece yaz aylarında (Tem-Ağu) geçilebilir.",
            },
        )
    try:
        pause_for_summer(db, institution=inst, actor_user_id=user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "pause_not_allowed",
                "message": str(e),
            },
        )
    status_info = get_subscription_status(inst)
    return MutationResponse[SubscriptionStatusInfo](
        data=_status_to_info(status_info),
        invalidate=_subscription_keys(inst.id),
    )


@router.post(
    "/subscription/resume",
    response_model=MutationResponse[SubscriptionStatusInfo],
)
def institution_subscription_resume_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Pause modundan akademik yıla manuel dönüş.

    Eşdeğer Jinja: institution.py:1122-1136 (subscription_resume_action).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    resume_from_pause(db, institution=inst, actor_user_id=user.id)
    status_info = get_subscription_status(inst)
    return MutationResponse[SubscriptionStatusInfo](
        data=_status_to_info(status_info),
        invalidate=_subscription_keys(inst.id),
    )


@router.post(
    "/subscription/guarantee/enable",
    response_model=MutationResponse[SubscriptionStatusInfo],
)
def institution_subscription_guarantee_enable_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """60g performans garantisini aktive et.

    Eşdeğer Jinja: institution.py:1139-1152 (subscription_guarantee_enable).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    enable_guarantee(db, institution=inst, actor_user_id=user.id)
    status_info = get_subscription_status(inst)
    return MutationResponse[SubscriptionStatusInfo](
        data=_status_to_info(status_info),
        invalidate=_subscription_keys(inst.id),
    )


# =============================================================================
# D4 Paket 3 — Quota dashboard
# =============================================================================


@router.get("/quota", response_model=QuotaResponse)
def institution_quota_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurumun aktif entity kuotaları (öğretmen / öğrenci / kurum yöneticisi).

    Eşdeğer Jinja: institution.py:926-945 (quota_dashboard).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    summary = get_quota_summary(db, institution=inst)

    summary_items = [
        QuotaInfoItem(
            key=q.key,
            label=q.label,
            limit=q.limit,
            current=q.current,
            pct=q.pct,
            is_unlimited=q.is_unlimited,
            is_at_limit=q.is_at_limit,
            is_warn=q.is_warn,
            has_override=q.has_override,
            override_note=q.override_note,
        )
        for q in summary
    ]
    # Karşılaştırma tablosu: kanonik kurum kademeleri (legacy "free" + trial HARİÇ;
    # mükerrer "Kurum Tanıma" satırı olmasın). Tek free adı: institution_free.
    compare_codes = ["institution_free", "etut_standart", "dershane_pro", "enterprise"]
    plans = [
        PlanQuotaItem(
            plan=code,
            teachers=PLAN_QUOTAS[code].get("teachers", 0),
            students=PLAN_QUOTAS[code].get("students", 0),
            institution_admins=PLAN_QUOTAS[code].get("institution_admins", 0),
        )
        for code in compare_codes
        if code in PLAN_QUOTAS
    ]
    # Mevcut planı kanonik koda normalize et → header etiketi + tablo vurgusu tutarlı.
    cur = inst.plan or "institution_free"
    if cur == "free":
        cur = "institution_free"
    return QuotaResponse(
        institution=_institution_brief(inst),
        plan=cur,
        summary=summary_items,
        plans=plans,
        warn_pct=WARN_PCT,
    )


# =============================================================================
# D4 Paket 3 — Usage dashboard
# =============================================================================


def _kind_label(kind_value: str) -> str:
    """UsageKind enum value → Türkçe etiket."""
    for k, label in USAGE_KIND_LABELS_TR.items():
        if k.value == kind_value:
            return label
    return kind_value


@router.get("/usage", response_model=UsageResponse)
def institution_usage_v2(
    days: int = Query(30, ge=1, le=90, description="Günlük seri penceresi"),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurumun aylık kredi tüketimi: bakiye + tip kırılımı + günlük seri +
    son olaylar.

    Eşdeğer Jinja: institution.py:951-989 (usage_dashboard).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    owner = CreditOwner.for_institution(inst)
    period = current_period()
    account = get_or_create_account(db, owner=owner, period=period)
    db.commit()  # yeni satır oluştuysa kaydet

    breakdown_map = usage_breakdown_by_kind(db, owner=owner, period=period)
    series_raw = daily_usage_series(db, owner=owner, days=days)
    events = recent_events(db, owner=owner, limit=50)

    # %100+ aşımı için 999 cap; UI `>100` rozetiyle gösterir.
    raw_pct = int(account.usage_pct) if account.total_allocated > 0 else 0
    usage_pct = min(999, max(0, raw_pct))

    # Şeffaflık: bu periyotta tüm event'lerin ilk/son zamanı + toplam adet
    from app.models import UsageEvent
    period_events_q = (
        db.query(UsageEvent)
          .filter(
              UsageEvent.owner_type == owner.type,
              UsageEvent.owner_id == owner.id,
              UsageEvent.period_year_month == period,
          )
    )
    total_event_count = period_events_q.count()
    first_at = period_events_q.order_by(UsageEvent.occurred_at.asc()).first()
    last_at = period_events_q.order_by(UsageEvent.occurred_at.desc()).first()

    # Actor isimlerini tek seferde çek (N+1 önleme)
    actor_ids = sorted({e.actor_user_id for e in events if e.actor_user_id is not None})
    actor_name_map: dict[int, str] = {}
    if actor_ids:
        for u in db.query(User).filter(User.id.in_(actor_ids)).all():
            actor_name_map[u.id] = u.full_name or u.email

    # balance_after: olayları ESKİDEN YENİYE sırala, cumulative cıkar
    # account.total_allocated (alocated + bonus) - cumulative_used = balance_after
    # `recent_events` zaten DESC döner — bunu kullanırken cumulative_used'u
    # newest'ten geriye doğru azaltarak hesaplıyoruz.
    used_so_far = account.used_credits
    event_items: list[UsageEventItem] = []
    for e in events:  # newest first
        balance_after = account.total_allocated - used_so_far
        actor_name = (
            actor_name_map.get(e.actor_user_id) if e.actor_user_id is not None
            else "Otomatik (sistem)"
        )
        event_items.append(UsageEventItem(
            id=e.id,
            occurred_at=e.occurred_at,
            kind=e.kind.value,
            kind_label=_kind_label(e.kind.value),
            credits=e.credits,
            actor_user_id=e.actor_user_id,
            actor_name=actor_name,
            balance_after=balance_after,
        ))
        used_so_far -= e.credits  # bir önceki olay bu kadar az kullandırmıştı

    return UsageResponse(
        institution=_institution_brief(inst),
        account=UsageAccountInfo(
            period_year_month=account.period_year_month,
            plan_code=account.plan_code,
            allocated_credits=account.allocated_credits,
            bonus_credits=account.bonus_credits,
            total_allocated=account.total_allocated,
            used_credits=account.used_credits,
            remaining_credits=account.remaining_credits,
            usage_pct=usage_pct,
            hard_block_enabled=bool(account.hard_block_enabled),
            blocked_until=account.blocked_until,
            first_event_at=first_at.occurred_at if first_at else None,
            last_event_at=last_at.occurred_at if last_at else None,
            total_event_count=total_event_count,
        ),
        breakdown=[
            UsageBreakdownEntry(
                kind=kind_str,
                label=_kind_label(kind_str),
                credits=credits,
            )
            for kind_str, credits in sorted(
                breakdown_map.items(), key=lambda x: -x[1]
            )
        ],
        series=[
            UsageDailyPoint(day=d, credits=c) for d, c in series_raw
        ],
        events=event_items,
        warn_threshold_pct=WARN_THRESHOLD_PCT,
    )


# =============================================================================
# D4 Paket 3 — Admin Weekly Digest
# =============================================================================


def _digest_to_summary(d: AdminWeeklyDigest) -> AdminDigestSummary:
    return AdminDigestSummary(
        id=d.id,
        institution_id=d.institution_id,
        week_start_date=d.week_start_date,
        week_end_date=d.week_end_date,
        send_status=d.send_status,
        recipient_count=d.recipient_count,
        sent_at=d.sent_at,
        error_message=d.error_message,
        created_at=d.created_at,
    )


@router.get("/admin-digest", response_model=AdminDigestListResponse)
def institution_admin_digest_list_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Son 12 haftanın yönetici özet arşivi.

    Eşdeğer Jinja: institution.py:619-647 (admin_digest_archive).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    digests = (
        db.query(AdminWeeklyDigest)
        .filter(AdminWeeklyDigest.institution_id == inst.id)
        .order_by(AdminWeeklyDigest.week_start_date.desc())
        .limit(12)
        .all()
    )
    items = [_digest_to_summary(d) for d in digests]
    return AdminDigestListResponse(
        institution=_institution_brief(inst),
        items=items,
        total=len(items),
    )


@router.get(
    "/admin-digest/{digest_id}",
    response_model=AdminDigestDetailResponse,
)
def institution_admin_digest_detail_v2(
    digest_id: int,
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Tek bir digest detayı + JSON payload snapshot + alıcı email listesi.

    Eşdeğer Jinja: institution.py:683-718 (admin_digest_detail).
    """
    import json as _json
    inst = _get_institution_or_403(db, user.institution_id)
    digest = (
        db.query(AdminWeeklyDigest)
        .filter(
            AdminWeeklyDigest.id == digest_id,
            AdminWeeklyDigest.institution_id == inst.id,
        )
        .first()
    )
    if not digest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "digest_not_found",
                "message": "Özet kaydı bulunamadı.",
            },
        )
    payload: dict | None = None
    if digest.payload_json:
        try:
            payload = _json.loads(digest.payload_json)
        except (ValueError, TypeError):
            payload = None
    emails: list[str] = []
    if digest.recipient_emails:
        emails = [
            e.strip() for e in digest.recipient_emails.split(",") if e.strip()
        ]
    summary = _digest_to_summary(digest)
    return AdminDigestDetailResponse(
        **summary.model_dump(),
        payload=payload,
        recipient_emails=emails,
    )


@router.post(
    "/admin-digest/send-now",
    response_model=MutationResponse[AdminDigestSendResult],
)
def institution_admin_digest_send_now_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Manuel tetik — bu hafta için özet üret + e-posta gönder (force=True).

    Eşdeğer Jinja: institution.py:650-680 (admin_digest_send_now).
    """
    inst = _get_institution_or_403(db, user.institution_id)
    try:
        digest = send_admin_weekly_digest(
            db, institution=inst, force=True,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal",
                "code": "digest_send_failed",
                "message": f"Özet üretimi başarısız: {type(e).__name__}: {e}",
            },
        )
    summary = _digest_to_summary(digest)
    msg = (
        f"Haftalık özet üretildi. Durum: {digest.send_status}, "
        f"alıcı: {digest.recipient_count}"
    )
    return MutationResponse[AdminDigestSendResult](
        data=AdminDigestSendResult(digest=summary, message=msg),
        invalidate=_invalidate_keys(inst.id, "admin-digest"),
    )


@router.get("/compliance", response_model=InstitutionComplianceResponse)
def institution_compliance_v2(
    weeks: int = Query(8, ge=2, le=16),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Program Uyum Panosu — kurum geneli + öğretmen/öğrenci kırılımı + trend.

    Tamamlama = yayınlanmış görevlerde Σ yapılan ÷ Σ planlanan; doğruluk =
    Σ doğru ÷ (doğru+yanlış). Gizlilik: öğrenci detay sayfası YOK (D4 deseni)."""
    from app.services.institution_compliance import compute_compliance

    inst = _get_institution_or_403(db, user.institution_id)
    d = compute_compliance(db, institution_id=inst.id, weeks=weeks)
    return InstitutionComplianceResponse(
        institution=_institution_brief(inst),
        summary=ComplianceSummary(**d["summary"]),
        trend=[ComplianceTrendPoint(**t) for t in d["trend"]],
        teachers=[ComplianceTeacherRow(**t) for t in d["teachers"]],
        attention_students=[ComplianceStudentRow(**s) for s in d["attention_students"]],
        empty_program=[ComplianceEmptyRow(**e) for e in d["empty_program"]],
    )


@router.get("/action-center", response_model=ActionCenterResponse)
def institution_action_center_v2(
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Müdahale Merkezi — 'bugün kime dokunmalıyım?' önceliklendirilmiş aksiyon
    kartları (boş program + düşük uyum + riskli öğrenci). Gizlilik: detay linki YOK."""
    from app.services.institution_action_center import compute_action_center

    inst = _get_institution_or_403(db, user.institution_id)
    d = compute_action_center(db, institution_id=inst.id)
    return ActionCenterResponse(
        institution=_institution_brief(inst),
        summary=ActionCenterSummary(**d["summary"]),
        items=[ActionCenterItem(**i) for i in d["items"]],
    )


@router.get("/teacher-scorecard", response_model=TeacherScorecardResponse)
def institution_teacher_scorecard_v2(
    weeks: int = Query(4, ge=2, le=12),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Öğretmen Etkililik Karnesi — tamamlama + doğruluk + disiplin + risk birleşik
    skor (son N hafta). 'Kim sonuç alıyor?' Gizlilik: öğrenci detayı YOK."""
    from app.services.institution_teacher_scorecard import compute_teacher_scorecard

    inst = _get_institution_or_403(db, user.institution_id)
    d = compute_teacher_scorecard(db, institution_id=inst.id, weeks=weeks)
    return TeacherScorecardResponse(
        institution=_institution_brief(inst),
        summary=TeacherScorecardSummary(**d["summary"]),
        teachers=[TeacherScorecardRow(**t) for t in d["teachers"]],
    )


@router.get("/parent-trust", response_model=ParentTrustResponse)
def institution_parent_trust_v2(
    days: int = Query(30, ge=7, le=90),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Veli Güveni Görünürlüğü — veli kapsaması + aktif veli + bekleyen davet +
    bildirim teslimat sağlığı (kanal kırılımlı). Kurumun veli nezdindeki değeri."""
    from app.services.institution_parent_trust import compute_parent_trust

    inst = _get_institution_or_403(db, user.institution_id)
    d = compute_parent_trust(db, institution_id=inst.id, days=days)
    return ParentTrustResponse(
        institution=_institution_brief(inst),
        summary=ParentTrustSummary(**d["summary"]),
        channels=[ParentTrustChannel(**c) for c in d["channels"]],
    )


@router.get("/activity-stream", response_model=ActivityStreamResponse)
def institution_activity_stream_v2(
    days: int = Query(30, ge=1, le=90),
    type: str | None = Query(None, description="all/signup/invitation/commercial/change"),
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum yöneticisi — kurum kapsamlı üyelik & aktivite akışı.

    Tek yerden: kuruma katılan yeni öğretmenler/öğrenciler, öğretmenlerin
    yaptığı veli davetleri, kurum-koç davetleri, abonelik talepleri, plan
    değişimleri.
    """
    from app.services.activity_stream import fetch_activity
    inst = _get_institution_or_403(db, user.institution_id)
    items, counts = fetch_activity(
        db, institution_id=inst.id, days=days, type_filter=type, limit=limit,
    )
    return ActivityStreamResponse(
        items=[ActivityStreamItem(**i) for i in items],
        counts=counts, days=days,
    )


@router.get(
    "/parent-trust/notifications",
    response_model=ParentTrustNotificationListResponse,
)
def institution_parent_trust_notifications_v2(
    days: int = Query(30, ge=7, le=90),
    status: str | None = Query(None, description="sent/failed/suppressed/queued; boşsa hepsi"),
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Veli güveni — son N gün NotificationLog detay listesi.

    Hangi velilere/öğrencilere hangi mailler gitmiş/başarısız olmuş tek tek
    görmek için. Kart sayılarındaki "2 ulaştı · 2 başarısız" gibi rakamların
    arkasındaki gerçek kayıtları gösterir.
    """
    from app.services.institution_parent_trust import list_notifications

    inst = _get_institution_or_403(db, user.institution_id)
    items, total = list_notifications(
        db,
        institution_id=inst.id,
        days=days,
        status_filter=status,
        limit=limit,
    )
    return ParentTrustNotificationListResponse(
        items=[ParentTrustNotificationItem(**it) for it in items],
        days=days,
        total_count=total,
    )


@router.get("/academic", response_model=InstitutionAcademicResponse)
def institution_academic_v2(
    weeks: int = Query(8, ge=2, le=16),
    user: User = Depends(_require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum Akademik Çıktı Panosu — KP4a deneme sonuçlarının kurum agregasyonu:
    kapsama + net başarı oranı (normalize, karşılaştırılabilir) + sınav türü
    kırılımı + haftalık trend + öğretmen kırılımı + en çok gelişen/gerileyen +
    deneme girmeyen. Gizlilik: öğrenci detay sayfası YOK (D4 deseni)."""
    from app.services.institution_academic import compute_academic

    inst = _get_institution_or_403(db, user.institution_id)
    d = compute_academic(db, institution_id=inst.id, weeks=weeks)
    return InstitutionAcademicResponse(
        institution=_institution_brief(inst),
        summary=AcademicSummary(**d["summary"]),
        sections=[AcademicSectionRow(**s) for s in d["sections"]],
        trend=[AcademicTrendPoint(**t) for t in d["trend"]],
        teachers=[AcademicTeacherRow(**t) for t in d["teachers"]],
        improving=[AcademicMoverRow(**m) for m in d["improving"]],
        declining=[AcademicMoverRow(**m) for m in d["declining"]],
        no_exam_program=[AcademicNoExamRow(**n) for n in d["no_exam_program"]],
    )
