"""API v2 — Super Admin endpoint'leri (Dalga 6).

Paket 1 (dashboard foundation):
  GET  /api/v2/admin/dashboard  → AdminDashboardResponse

Paket 2 (institutions + account-history):
  GET  /api/v2/admin/institutions                    → InstitutionListResponse
  POST /api/v2/admin/institutions                    → MutationResponse[InstitutionMutationResult]
  GET  /api/v2/admin/institutions/{id}               → InstitutionDetailResponse
  POST /api/v2/admin/institutions/{id}               → MutationResponse[InstitutionMutationResult] (edit)
  POST /api/v2/admin/institutions/{id}/delete        → MutationResponse[InstitutionMutationResult]
  GET  /api/v2/admin/institutions/{id}/backup        → InstitutionBackupSummary (counts + size)
  GET  /api/v2/admin/institutions/{id}/backup.json   → raw JSON (download)
  GET  /api/v2/admin/account-history/{owner_type}/{owner_id} → AccountHistoryResponse
  POST /api/v2/admin/account-history/archive         → MutationResponse[AccountArchiveResult]
  POST /api/v2/admin/account-history/unarchive       → MutationResponse[AccountArchiveResult]
  POST /api/v2/admin/account-history/bulk-archive    → MutationResponse[AccountArchiveResult]

Auth: `_require_super_admin` — UserRole.SUPER_ADMIN dışında 403 role_required.

KURAL: Veri yapısı/sorgular Jinja `app/routes/admin.py` + servisleriyle
**birebir aynı**. UI özgür ama payload korunur.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    AUDIT_ACTION_LABELS,
    AuditAction,
    AuditLog,
    Institution,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import _auth_error, get_current_user_v2
from app.routes.api_v2.schemas.admin import (
    AccountArchiveBody,
    AccountArchiveResult,
    AccountBulkArchiveBody,
    AccountHistoryEvent,
    AccountHistoryResponse,
    AccountOwnerTypeLiteral,
    AccountUnarchiveBody,
    AdminDashboardCounts,
    AdminDashboardResponse,
    AdminImpersonateBody,
    AdminImpersonateEndResult,
    AdminImpersonateResult,
    AdminIndependentTeachersResponse,
    AdminActivatePlanBody,
    AdminUserChangeRoleBody,
    AdminUserCreateBody,
    AdminUserCreateResult,
    AdminUserDetailResponse,
    AdminUserEditBody,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserMutationResult,
    AnnouncementAudienceOption,
    AnnouncementCreateBody,
    AnnouncementItem,
    AnnouncementMutationResult,
    AnnouncementSeverityOption,
    AnnouncementsListResponse,
    AuditActorBrief,
    AuditListItem,
    AuditListResponse,
    AuditLogItem,
    CronStatusItem,
    DatabaseStatusInfo,
    DispatcherStatusInfo,
    HealthAssessmentItem,
    HealthIndicatorItem,
    HealthSummary,
    IndependentTeacherActivitySummary,
    IndependentTeacherBrief,
    IndependentTeacherRiskRow,
    InstitutionBackupCounts,
    InstitutionBackupSummary,
    InstitutionBriefForHealth,
    InstitutionCreateBody,
    InstitutionDetailBrief,
    InstitutionDetailResponse,
    InstitutionEditBody,
    InstitutionFilterLevelLiteral,
    InstitutionListItem,
    InstitutionListResponse,
    InstitutionMutationResult,
    InstitutionRefBrief,
    InstitutionSortLiteral,
    InstitutionUserBrief,
    AdminQuotaResponse,
    AdminUsageResponse,
    FeatureFlagDetailResponse,
    FeatureFlagInstitutionOption,
    FeatureFlagItem,
    FeatureFlagMutationResult,
    FeatureFlagOverrideBody,
    FeatureFlagOverrideItem,
    FeatureFlagsListResponse,
    KvkkDashboardResponse,
    KvkkDataInventoryItem,
    KvkkMutationResult,
    KvkkRejectBody,
    KvkkRequestItem,
    KvkkRequestUserBrief,
    KvkkSummary,
    QuotaCell,
    QuotaInstitutionRow,
    QuotaMutationResult,
    QuotaOverrideBody,
    QuotaPlanRow,
    RoleLiteral,
    SystemHealthResponse,
    UsageAccountInfo,
    UsageBonusBody,
    UsageIndependentRow,
    UsageInstitutionRow,
    UsageKindCost,
    UsageMutationResult,
    UsageTotals,
    DiscoveryBulkBody,
    DiscoveryCardItem,
    DiscoveryMutationResult,
    DiscoveryQueueResponse,
    EnumOption,
    ExperimentCreateBody,
    ExperimentDetail,
    ExperimentDetailResponse,
    ExperimentFormMeta,
    ExperimentListItem,
    ExperimentListResponse,
    ExperimentMutationResult,
    ExperimentStatusBody,
    ExperimentStrategyOption,
    ExperimentVariantBrief,
    ExperimentVariantStat,
    DashboardAnomaly,
    DashboardAuditItem,
    DashboardExperiment,
    DashboardExperimentVariant,
    DashboardLandingHealth,
    DashboardSummary,
    DashboardWindowMetrics,
    FeatureCardBody,
    FeatureCardFiredRule,
    FeatureCardFormMeta,
    FeatureCardFormResponse,
    FeatureCardFull,
    FeatureCardListItem,
    FeatureCardMutationResult,
    FeatureCardPinBody,
    FeatureCardScoreInputs,
    FeatureCardStatusBody,
    FeatureCatalogDashboardResponse,
    FeatureCatalogListResponse,
    MockupOption,
    StatusOption,
    ActionCenterItem,
    ActionCenterResponse,
    ActionSignalItem,
    AtRiskInstitutionItem,
    CohortMatrix,
    CohortRetentionCell,
    CohortRow,
    LtvEstimate,
    MrrProjection,
    PlanChurnSummary,
    PlanLtvItem,
    QuickActionBody,
    RevenueCohortResponse,
    RevenueForecastResponse,
    RevenueMutationResult,
    RiskAtMrr,
    ScenarioComparison,
    ScenarioHorizon,
    SuggestedActionItem,
    CrmActionBody,
    CrmActionCompleteBody,
    CrmActionItem,
    CrmEnumOption,
    CrmMeta,
    CrmNoteBody,
    CrmNoteItem,
    HealthComponentItem,
    HealthHistoryPoint,
    HealthScoreV2Data,
    HealthTriggerItem,
    Institution360Admin,
    Institution360Billing,
    Institution360Health,
    Institution360Identity,
    Institution360Usage,
    InstitutionRevenue360Response,
    OwnerBrief,
    OwnerContactBody,
    OwnerContactData,
    OwnerTagBody,
    OwnerTagItem,
    OwnerTagOption,
    OwnerTypeLiteral,
    PlanChangeItem,
    Revenue360MutationResult,
    Risk360Item,
    StudentHealthCounts,
    StudentRow,
    UserRevenue360Response,
    ActionTemplateBody,
    ActionTemplateItem,
    ActionTemplateMutationResult,
    ActionTemplateRenderResponse,
    ActionTemplatesResponse,
    InvoiceCancelBody,
    InvoiceItem,
    InvoiceMarkPaidBody,
    InvoiceMutationResult,
    InvoicePostponeBody,
    InvoiceReminderBody,
    OfferBody,
    OfferItem,
    RevenueOfferMutationResult,
    CampaignBody,
    CampaignDetail,
    CampaignDetailResponse,
    CampaignFormMeta,
    CampaignFunnel,
    CampaignListItem,
    CampaignMutationResult,
    CampaignPreviewBody,
    CampaignPreviewOwner,
    CampaignPreviewResponse,
    CampaignRecipientItem,
    CampaignSegmentOption,
    CampaignStatsFull,
    CampaignVariant,
    CampaignsListResponse,
    RevenueChangeSummary,
    RevenueChurnProxy,
    RevenueDailyChange,
    RevenueDashboardResponse,
    RevenueDrillResponse,
    RevenueDrillRow,
    RevenueInvoiceRow,
    RevenueInvoiceStatusCount,
    RevenueInvoicesResponse,
    RevenueMrr,
    RevenueOwnerMrr,
    RevenueOwnerPlanDist,
    RevenueOwnerTrial,
    RevenuePaymentBucket,
    RevenuePaymentCalendar,
    RevenuePlanDist,
    RevenueTrialEntry,
    AttentionItemModel,
    AttentionSummaryModel,
    ErrorSummaryModel,
    IntegrityCronDrift,
    IntegrityCronJob,
    IntegrityDbFile,
    IntegrityKvkk,
    IntegrityKvkkSample,
    IntegrityMigration,
    IntegrityOrphanFinding,
    IntegrityOrphans,
    IntegrityResponse,
    NotifDailyTrend,
    NotifFailureItem,
    NotifMatrix,
    NotifSuppressItem,
    NotifWindowSummary,
    NotificationHealthResponse,
    SecurityFailedBucket,
    SecurityImpersonationItem,
    SecurityOverviewResponse,
    SecuritySessionItem,
    SecuritySummary,
    SecuritySuspiciousIp,
    SystemEndpointError,
    SystemErrorGroup,
    SystemHealthDataResponse,
    SystemMutationResult,
    SystemResolveBody,
    SystemSlowRequest,
    ActionSuggestion,
    ActiveUsersDrillResponse,
    ActiveUsersDrillRow,
    ActivityChampionRow,
    ActivityCriticalSummary,
    ActivityDauTrendPoint,
    ActivityDecayRow,
    ActivityFeatureMatrix,
    ActivityFeatureMatrixCell,
    ActivityFeatureMatrixRow,
    ActivityFeaturePopularity,
    ActivityHeartbeatRow,
    ActivityHeartbeatSummary,
    ActivityHeatmap,
    ActivityMilestone,
    ActivityOnboardingRow,
    ActivityPanelResponse,
    ActivityPerTenant,
    ActivityPlanActivityMatrix,
    ActivityPlanBenchmarkRow,
    ActivityPowerUsers,
    ActivityRatioRow,
    ActivityResurrectedRow,
    ActivityRetentionMetric,
    ActivityRoleBreakdownRow,
    ActivitySessionDuration,
    ActivitySilentRow,
    ActivitySoloSpecial,
    ActivityStickiness,
    ActivityStickinessPoint,
    ActivityTotals,
    ActivityWow,
    HeatmapPattern,
    InstitutionHeatmapResponse,
    LiveFeedItem,
    LiveFeedResponse,
    IpBlockBody,
    IpUnblockBody,
    SecurityActionResult,
    AbuseMeta,
    AbuseRemediateResult,
    AbuseResolveBody,
    AbuseResponse,
    AbuseScanResult,
    AbuseSignalItem,
    AlarmEventItem,
    AlarmRuleItem,
    AlarmRuleUpdateBody,
    AlarmScanResult,
    AlarmsResponse,
    AiSettingItem,
    AiSettingsResponse,
    SetAiSettingBody,
    PricingAdminResponse,
    PricingConfigBody,
    ContactRequestItem,
    ContactRequestListResponse,
    ContactRequestUpdateBody,
    ContactRequestMutationResult,
)
from app.routes.api_v2.schemas.common import MutationResponse
from app.services.account_history import (
    account_history,
    archive_record,
    bulk_archive_older_than,
    unarchive_record,
)
from app.services.audit import log_action
from app.services.tenant_backup import export_tenant, export_tenant_json
from app.services.tenant_health import (
    bulk_health_assessment,
    churn_summary,
    compute_health_score,
    filter_unhealthy,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["api-v2-admin"])


# =============================================================================
# Auth dep — _require_super_admin
# =============================================================================


def _require_super_admin(user: User = Depends(get_current_user_v2)) -> User:
    """SUPER_ADMIN rolü zorunlu. Aksi halde 403 role_required."""
    if user.role != UserRole.SUPER_ADMIN:
        raise _auth_error(
            "Bu işlem sadece süper admin içindir.",
            "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


# =============================================================================
# Helpers
# =============================================================================


def _independent_teacher_activity_payload(
    db: Session,
) -> tuple[IndependentTeacherActivitySummary, list[IndependentTeacherRiskRow]]:
    """Bağımsız öğretmen aktivitesi — Jinja `_independent_teacher_activity()`
    helper'ı ile **birebir aynı** heuristik (admin.py:64-128).

    4 bant:
      healthy  : son 7g içinde giriş
      watch    : 7-14g
      risk     : 14-30g
      critical : 30g+ veya hiç giriş yok
    """
    now_utc = datetime.now(timezone.utc)
    indep_teachers = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .order_by(User.full_name.asc(), User.id.asc())
        .all()
    )
    summary_counts = {"healthy": 0, "watch": 0, "risk": 0, "critical": 0}
    rows: list[IndependentTeacherRiskRow] = []
    for t in indep_teachers:
        last = t.last_login_at
        if last is None:
            days: int | None = None
            band = "critical"
            label = "hiç giriş yok"
        else:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days = (now_utc - last).days
            if days >= 30:
                band = "critical"
            elif days >= 14:
                band = "risk"
            elif days >= 7:
                band = "watch"
            else:
                band = "healthy"
            label = f"{days}g önce" if days > 0 else "bugün"
        summary_counts[band] += 1
        rows.append(
            IndependentTeacherRiskRow(
                user=IndependentTeacherBrief(
                    id=t.id, full_name=t.full_name, email=t.email,
                ),
                band=band,  # type: ignore[arg-type]
                days_since_login=days,
                label=label,
                last_login_at=t.last_login_at,
            )
        )
    # Dikkat çeken üstte (critical → risk → watch → healthy)
    band_order = {"critical": 0, "risk": 1, "watch": 2, "healthy": 3}
    rows.sort(
        key=lambda r: (
            band_order.get(r.band, 9),
            -(r.days_since_login or 9999),
        ),
    )
    summary = IndependentTeacherActivitySummary(
        healthy=summary_counts["healthy"],
        watch=summary_counts["watch"],
        risk=summary_counts["risk"],
        critical=summary_counts["critical"],
        unhealthy_total=summary_counts["risk"] + summary_counts["critical"],
        total=len(indep_teachers),
    )
    return summary, rows


def _audit_log_to_item(a: AuditLog) -> AuditLogItem:
    """ORM AuditLog → Pydantic AuditLogItem (action label + via_admin extraction)."""
    action_label = AUDIT_ACTION_LABELS.get(a.action, a.action.value)
    via_admin: int | None = None
    if a.details_json:
        try:
            details = json.loads(a.details_json)
            if isinstance(details, dict):
                v = details.get("_via_admin")
                if isinstance(v, int):
                    via_admin = v
        except (json.JSONDecodeError, TypeError):
            pass
    return AuditLogItem(
        id=a.id,
        actor_id=a.actor_id,
        email_attempted=a.email_attempted,
        action=a.action.value,
        action_label=action_label,
        target_type=a.target_type,
        target_id=a.target_id,
        ip_address=a.ip_address,
        user_agent=a.user_agent,
        details_json=a.details_json,
        created_at=a.created_at,
        via_admin=via_admin,
    )


def _to_health_item(h) -> HealthAssessmentItem:
    """tenant_health.HealthAssessment → Pydantic."""
    inst = h.institution
    return HealthAssessmentItem(
        institution=InstitutionBriefForHealth(
            id=inst.id,
            name=inst.name,
            slug=inst.slug,
            plan=getattr(inst, "plan", None),
            is_active=inst.is_active,
        ),
        score=h.score,
        level=h.level,
        level_label=h.level_label,
        level_emoji=h.level_emoji,
        level_color=h.level_color,
        indicators=[
            HealthIndicatorItem(
                code=ind.code,
                title=ind.title,
                detail=ind.detail,
                weight=ind.weight,
            )
            for ind in h.indicators
        ],
        teacher_count=h.teacher_count,
        student_count=h.student_count,
        active_teacher_count_7d=h.active_teacher_count_7d,
        active_student_count_7d=h.active_student_count_7d,
        last_teacher_login=h.last_teacher_login,
        last_student_login=h.last_student_login,
        weekly_completion_rate=h.weekly_completion_rate,
        teacher_active_pct=h.teacher_active_pct,
        student_active_pct=h.student_active_pct,
    )


# =============================================================================
# GET /admin/dashboard
# =============================================================================


@router.get("/dashboard", response_model=AdminDashboardResponse)
def admin_dashboard_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Süper admin genel bakış — counts + sağlık + bağımsız öğretmen aktivite +
    son audit + 24h başarısız login sayısı.

    Eşdeğer Jinja: admin.py:150-211 (admin_dashboard).
    """
    # Counts — Jinja ile birebir
    counts = AdminDashboardCounts(
        institutions=db.query(Institution).count(),
        active_institutions=db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .count(),
        teachers=db.query(User).filter(User.role == UserRole.TEACHER).count(),
        students=db.query(User).filter(User.role == UserRole.STUDENT).count(),
        parents=db.query(User).filter(User.role == UserRole.PARENT).count(),
        institution_admins=db.query(User)
        .filter(User.role == UserRole.INSTITUTION_ADMIN)
        .count(),
        super_admins=db.query(User)
        .filter(User.role == UserRole.SUPER_ADMIN)
        .count(),
        independent_teachers=db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
        )
        .count(),
    )

    # Kurum sağlığı
    all_insts = db.query(Institution).all()
    health_assessments = bulk_health_assessment(db, institutions=all_insts)
    summary_dict = churn_summary(health_assessments)
    health_summary = HealthSummary(
        healthy=summary_dict["healthy"],
        watch=summary_dict["watch"],
        risk=summary_dict["risk"],
        critical=summary_dict["critical"],
        unhealthy_total=summary_dict["unhealthy_total"],
        needs_attention=summary_dict["needs_attention"],
    )
    top_unhealthy = [
        _to_health_item(h)
        for h in filter_unhealthy(health_assessments, min_level="risk")[:3]
    ]

    # Bağımsız öğretmen aktivite
    teacher_summary, teacher_rows = _independent_teacher_activity_payload(db)
    top_teacher_risk = teacher_rows[:3]

    # Recent audit (son 10)
    recent_audits = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    audit_items = [_audit_log_to_item(a) for a in recent_audits]

    # 24h failed logins
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    failed_logins_24h = (
        db.query(AuditLog)
        .filter(
            AuditLog.action.in_(
                [AuditAction.LOGIN_FAILED, AuditAction.LOGIN_LOCKED]
            ),
            AuditLog.created_at >= cutoff,
        )
        .count()
    )

    return AdminDashboardResponse(
        counts=counts,
        failed_logins_24h=failed_logins_24h,
        health_summary=health_summary,
        top_unhealthy=top_unhealthy,
        teacher_activity_summary=teacher_summary,
        top_teacher_risk=top_teacher_risk,
        recent_audits=audit_items,
    )


# =============================================================================
# P2 — Helpers (institutions + account-history paylaşımlı)
# =============================================================================


def _slugify(text: str) -> str:
    """Türkçe karakter destekli URL-safe slug — Jinja admin.py:_slugify ile birebir."""
    text = (text or "").strip().lower()
    replacements = {
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
        "İ": "i", "Ç": "c", "Ğ": "g", "Ö": "o", "Ş": "s", "Ü": "u",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:64] or "kurum"


def _institution_to_detail_brief(inst: Institution) -> InstitutionDetailBrief:
    return InstitutionDetailBrief(
        id=inst.id,
        name=inst.name,
        slug=inst.slug,
        contact_email=inst.contact_email,
        plan=inst.plan or "free",
        is_active=inst.is_active,
        created_at=inst.created_at,
    )


def _user_to_inst_brief(u: User) -> InstitutionUserBrief:
    return InstitutionUserBrief(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        is_active=u.is_active,
        last_login_at=u.last_login_at,
    )


def _health_to_list_item(h) -> InstitutionListItem:
    inst = h.institution
    return InstitutionListItem(
        institution=InstitutionBriefForHealth(
            id=inst.id,
            name=inst.name,
            slug=inst.slug,
            plan=getattr(inst, "plan", None),
            is_active=inst.is_active,
        ),
        score=h.score,
        level=h.level,
        level_label=h.level_label,
        level_emoji=h.level_emoji,
        level_color=h.level_color,
        indicators=[
            HealthIndicatorItem(
                code=ind.code, title=ind.title,
                detail=ind.detail, weight=ind.weight,
            )
            for ind in h.indicators
        ],
        teacher_count=h.teacher_count,
        student_count=h.student_count,
        teacher_active_pct=h.teacher_active_pct,
        student_active_pct=h.student_active_pct,
        weekly_completion_rate=h.weekly_completion_rate,
        last_teacher_login=h.last_teacher_login,
        last_student_login=h.last_student_login,
    )


def _admin_invalidate() -> list[str]:
    """Admin mutation'larında invalidate edilecek queryKey prefix'leri."""
    return ["admin:dashboard", "admin:institutions", "admin:account-history"]


# =============================================================================
# P2 — Institutions list / create
# =============================================================================


@router.get("/institutions", response_model=InstitutionListResponse)
def admin_list_institutions_v2(
    sort: InstitutionSortLiteral = Query("health"),
    filter_level: InstitutionFilterLevelLiteral | None = Query(None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kurum listesi — sağlık skoruyla sıralı + filtre.

    Eşdeğer Jinja: admin.py:217-271 (list_institutions).
    """
    institutions = db.query(Institution).all()
    assessments = bulk_health_assessment(db, institutions=institutions)
    summary_dict = churn_summary(assessments)
    summary = HealthSummary(
        healthy=summary_dict["healthy"],
        watch=summary_dict["watch"],
        risk=summary_dict["risk"],
        critical=summary_dict["critical"],
        unhealthy_total=summary_dict["unhealthy_total"],
        needs_attention=summary_dict["needs_attention"],
    )

    # Filtre — Jinja birebir
    if filter_level == "unhealthy":
        assessments = filter_unhealthy(assessments, min_level="watch")
    elif filter_level == "critical":
        assessments = filter_unhealthy(assessments, min_level="critical")

    # Sıralama
    if sort == "name":
        assessments.sort(key=lambda a: a.institution.name.lower())
    elif sort == "created":
        assessments.sort(key=lambda a: a.institution.created_at, reverse=True)
    # 'health' default — bulk_health_assessment zaten doğru sırada

    return InstitutionListResponse(
        items=[_health_to_list_item(h) for h in assessments],
        summary=summary,
        sort=sort,
        filter_level=filter_level,
    )


@router.post(
    "/institutions",
    response_model=MutationResponse[InstitutionMutationResult],
)
def admin_create_institution_v2(
    body: InstitutionCreateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Yeni kurum oluştur — slug auto-gen + çakışma kontrolü.

    Eşdeğer Jinja: admin.py:274-323 (create_institution).
    """
    name_clean = (body.name or "").strip()
    if not name_clean:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "name_required",
                "message": "Kurum adı zorunlu.",
            },
        )
    slug_clean = _slugify(body.slug or name_clean)
    existing = (
        db.query(Institution)
        .filter(Institution.slug == slug_clean)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict", "code": "slug_taken",
                "message": f"'{slug_clean}' slug'ı zaten kullanılıyor. Farklı bir ad seçin.",
            },
        )
    plan = (body.plan or "free").strip() or "free"
    inst = Institution(
        name=name_clean,
        slug=slug_clean,
        contact_email=(body.contact_email or "").strip().lower() or None,
        plan=plan,
        is_active=True,
    )
    db.add(inst)
    db.flush()
    log_action(
        db,
        action=AuditAction.INSTITUTION_CREATE,
        actor_id=user.id,
        target_type="institution",
        target_id=inst.id,
        request=request,
        details={"name": name_clean, "slug": slug_clean, "plan": inst.plan},
        autocommit=False,
    )
    db.commit()

    return MutationResponse[InstitutionMutationResult](
        data=InstitutionMutationResult(
            institution=_institution_to_detail_brief(inst),
            message=f"'{name_clean}' kurumu oluşturuldu.",
        ),
        invalidate=_admin_invalidate(),
    )


# =============================================================================
# P2 — Institution detail / edit / delete
# =============================================================================


@router.get(
    "/institutions/{institution_id}",
    response_model=InstitutionDetailResponse,
)
def admin_institution_detail_v2(
    institution_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kurum detayı — sağlık skoru + admin/teacher listeleri + öğrenci sayım.

    Eşdeğer Jinja: admin.py:326-377 (institution_detail).
    """
    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "institution_not_found",
                "message": "Kurum bulunamadı.",
            },
        )

    teachers = (
        db.query(User)
        .filter(User.institution_id == inst.id, User.role == UserRole.TEACHER)
        .order_by(User.full_name)
        .all()
    )
    institution_admins = (
        db.query(User)
        .filter(
            User.institution_id == inst.id,
            User.role == UserRole.INSTITUTION_ADMIN,
        )
        .order_by(User.full_name)
        .all()
    )
    teacher_ids = [t.id for t in teachers]
    student_count = 0
    if teacher_ids:
        student_count = (
            db.query(User)
            .filter(
                User.role == UserRole.STUDENT,
                User.teacher_id.in_(teacher_ids),
            )
            .count()
        )

    health = compute_health_score(db, institution=inst)
    return InstitutionDetailResponse(
        institution=_institution_to_detail_brief(inst),
        health=_to_health_item(health),
        institution_admins=[_user_to_inst_brief(u) for u in institution_admins],
        teachers=[_user_to_inst_brief(u) for u in teachers],
        student_count=student_count,
    )


@router.post(
    "/institutions/{institution_id}",
    response_model=MutationResponse[InstitutionMutationResult],
)
def admin_edit_institution_v2(
    institution_id: int,
    body: InstitutionEditBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kurum bilgilerini güncelle — before/after diff log'lanır.

    Eşdeğer Jinja: admin.py:607-657 (edit_institution).
    """
    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "institution_not_found",
                "message": "Kurum bulunamadı.",
            },
        )
    name_clean = (body.name or "").strip()
    if not name_clean:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "name_required",
                "message": "Kurum adı zorunlu.",
            },
        )

    before = {
        "name": inst.name,
        "contact_email": inst.contact_email,
        "plan": inst.plan,
        "is_active": inst.is_active,
    }
    inst.name = name_clean
    inst.contact_email = (body.contact_email or "").strip().lower() or None
    inst.plan = (body.plan or "free").strip() or "free"
    inst.is_active = bool(body.is_active)
    after = {
        "name": inst.name,
        "contact_email": inst.contact_email,
        "plan": inst.plan,
        "is_active": inst.is_active,
    }
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="institution",
        target_id=inst.id,
        request=request,
        details={"before": before, "after": after},
        autocommit=False,
    )
    db.commit()

    return MutationResponse[InstitutionMutationResult](
        data=InstitutionMutationResult(
            institution=_institution_to_detail_brief(inst),
            message="Kurum güncellendi.",
        ),
        invalidate=_admin_invalidate(),
    )


@router.post(
    "/institutions/{institution_id}/delete",
    response_model=MutationResponse[InstitutionMutationResult],
)
def admin_delete_institution_v2(
    institution_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kurumu sil — bağlı kullanıcılar SET NULL ile bağımsız öğretmen olur.

    Eşdeğer Jinja: admin.py:660-693 (delete_institution).
    """
    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "institution_not_found",
                "message": "Kurum bulunamadı.",
            },
        )

    affected = (
        db.query(User).filter(User.institution_id == inst.id).count()
    )
    name = inst.name
    log_action(
        db,
        action=AuditAction.INSTITUTION_DELETE,
        actor_id=user.id,
        target_type="institution",
        target_id=inst.id,
        request=request,
        details={"name": name, "affected_users": affected},
        autocommit=False,
    )
    db.delete(inst)
    db.commit()

    return MutationResponse[InstitutionMutationResult](
        data=InstitutionMutationResult(
            institution=None,
            message=f"'{name}' kurumu silindi. {affected} kullanıcı bağımsız oldu.",
            affected_users=affected,
        ),
        invalidate=_admin_invalidate(),
    )


# =============================================================================
# P2 — Backup
# =============================================================================


@router.get(
    "/institutions/{institution_id}/backup",
    response_model=InstitutionBackupSummary,
)
def admin_institution_backup_summary_v2(
    institution_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Backup özeti (counts + boyut) — UI'da "Yedeği İndir" butonu öncesi preview.

    Asıl indirme `/backup.json` endpoint'i üzerinden.
    """
    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "institution_not_found",
                "message": "Kurum bulunamadı.",
            },
        )
    payload = export_tenant(db, institution=inst)
    payload_size = len(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )
    return InstitutionBackupSummary(
        institution=_institution_to_detail_brief(inst),
        schema_version=payload["schema_version"],
        exported_at=datetime.fromisoformat(payload["exported_at"]),
        audit_lookback_days=payload["audit_lookback_days"],
        notification_lookback_days=payload["notification_lookback_days"],
        counts=InstitutionBackupCounts(**payload["counts"]),
        size_bytes=payload_size,
    )


@router.get("/institutions/{institution_id}/backup.json")
def admin_institution_backup_download_v2(
    institution_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Backup JSON — Content-Disposition attachment ile dosya indir.

    Eşdeğer Jinja: admin.py:383-429 (institution_backup_download).
    """
    from datetime import date as _date

    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "institution_not_found",
                "message": "Kurum bulunamadı.",
            },
        )

    payload = export_tenant_json(db, institution=inst)
    today_str = _date.today().isoformat()
    filename = f"{inst.slug}-backup-{today_str}.json"

    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="institution_backup",
        target_id=inst.id,
        request=request,
        details={
            "action": "backup_downloaded",
            "institution_slug": inst.slug,
            "size_bytes": len(payload.encode("utf-8")),
        },
    )

    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# =============================================================================
# P2 — Account history (poly: institution|user)
# =============================================================================


def _history_event_to_pydantic(e) -> AccountHistoryEvent:
    """services/account_history.HistoryEvent → Pydantic."""
    return AccountHistoryEvent(
        record_type=e.record_type,
        record_id=e.record_id,
        when=e.when,
        title=e.title,
        subtitle=e.subtitle,
        badge_label=e.badge_label,
        badge_color=e.badge_color,
        detail=e.detail,
        archived=e.archived,
        archived_at=e.archived_at,
        archive_note=e.archive_note,
    )


@router.get(
    "/account-history/{owner_type}/{owner_id}",
    response_model=AccountHistoryResponse,
)
def admin_account_history_v2(
    owner_type: AccountOwnerTypeLiteral,
    owner_id: int,
    years: int = Query(3, ge=1, le=10),
    include_archived: int = Query(0, ge=0, le=1),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Owner-pattern hesap hareketleri timeline'ı.

    institution: plan + invoice; user: sadece plan.

    Eşdeğer Jinja: admin.py:432-496 (institution_account_history + user_account_history).
    """
    if owner_type == "institution":
        inst = db.get(Institution, owner_id)
        if inst is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found", "code": "institution_not_found",
                    "message": "Kurum bulunamadı.",
                },
            )
    else:  # user
        u = db.get(User, owner_id)
        if u is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found", "code": "user_not_found",
                    "message": "Kullanıcı bulunamadı.",
                },
            )

    data = account_history(
        db,
        owner_type=owner_type,
        owner_id=owner_id,
        years=years,
        include_archived=bool(include_archived),
    )
    return AccountHistoryResponse(
        owner_type=data["owner_type"],
        owner_id=data["owner_id"],
        owner_name=data["owner_name"],
        window_start=data["window_start"],
        events=[_history_event_to_pydantic(e) for e in data["events"]],
        total_count=data["total_count"],
        archived_count=data["archived_count"],
        older_count=data["older_count"],
        include_archived=data["include_archived"],
        years=data["years"],
    )


@router.post(
    "/account-history/archive",
    response_model=MutationResponse[AccountArchiveResult],
)
def admin_account_history_archive_v2(
    body: AccountArchiveBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tek bir plan|invoice kaydını arşive ekle.

    Eşdeğer Jinja: admin.py:499-529 (account_history_archive).
    """
    result = archive_record(
        db,
        record_type=body.record_type,
        record_id=body.record_id,
        by_user_id=user.id,
        note=body.note,
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type=f"account_history_{body.record_type}",
        target_id=body.record_id,
        request=request,
        details={
            "action": "archive",
            "ok": result.get("ok"),
            "error": result.get("error"),
            "note": (body.note or "")[:200],
        },
    )
    message = (
        "Kayıt arşivlendi" if result.get("ok")
        else f"Hata: {result.get('error')}"
    )
    return MutationResponse[AccountArchiveResult](
        data=AccountArchiveResult(
            ok=bool(result.get("ok")),
            record_type=body.record_type,
            record_id=body.record_id,
            archived_at=result.get("archived_at"),
            error=result.get("error"),
            message=message,
        ),
        invalidate=_admin_invalidate(),
    )


@router.post(
    "/account-history/unarchive",
    response_model=MutationResponse[AccountArchiveResult],
)
def admin_account_history_unarchive_v2(
    body: AccountUnarchiveBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Arşivden geri al.

    Eşdeğer Jinja: admin.py:532-560 (account_history_unarchive).
    """
    result = unarchive_record(
        db, record_type=body.record_type, record_id=body.record_id,
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type=f"account_history_{body.record_type}",
        target_id=body.record_id,
        request=request,
        details={
            "action": "unarchive",
            "ok": result.get("ok"),
            "error": result.get("error"),
        },
    )
    message = (
        "Arşivden çıkarıldı" if result.get("ok")
        else f"Hata: {result.get('error')}"
    )
    return MutationResponse[AccountArchiveResult](
        data=AccountArchiveResult(
            ok=bool(result.get("ok")),
            record_type=body.record_type,
            record_id=body.record_id,
            error=result.get("error"),
            message=message,
        ),
        invalidate=_admin_invalidate(),
    )


@router.post(
    "/account-history/bulk-archive",
    response_model=MutationResponse[AccountArchiveResult],
)
def admin_account_history_bulk_archive_v2(
    body: AccountBulkArchiveBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """X yıldan eski tüm kayıtları topluca arşivle.

    Eşdeğer Jinja: admin.py:563-604 (account_history_bulk_archive).
    """
    if body.owner_type not in ("institution", "user"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "invalid_owner_type",
                "message": "invalid owner_type",
            },
        )
    years = max(1, min(int(body.years), 10))
    result = bulk_archive_older_than(
        db,
        owner_type=body.owner_type,
        owner_id=body.owner_id,
        years=years,
        by_user_id=user.id,
        note=body.note,
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type=f"account_history_bulk_{body.owner_type}",
        target_id=body.owner_id,
        request=request,
        details={
            "action": "bulk_archive",
            "years": years,
            "plan_count": result.get("plan_count"),
            "invoice_count": result.get("invoice_count"),
            "total": result.get("total"),
        },
    )
    message = (
        f"{result['total']} kayıt arşive eklendi "
        f"({result['plan_count']} plan, {result['invoice_count']} fatura)"
    )
    return MutationResponse[AccountArchiveResult](
        data=AccountArchiveResult(
            ok=bool(result.get("ok")),
            plan_count=result.get("plan_count", 0),
            invoice_count=result.get("invoice_count", 0),
            total=result.get("total", 0),
            message=message,
        ),
        invalidate=_admin_invalidate(),
    )


# =============================================================================
# P3 — Users
# =============================================================================


ROLE_LABELS_TR_USERS: dict[UserRole, str] = {
    UserRole.SUPER_ADMIN: "Süper Admin",
    UserRole.INSTITUTION_ADMIN: "Kurum Yöneticisi",
    UserRole.TEACHER: "Öğretmen",
    UserRole.STUDENT: "Öğrenci",
    UserRole.PARENT: "Veli",
}

USER_LIST_LIMIT = 500


def _institution_to_ref_brief(inst: Institution | None) -> InstitutionRefBrief | None:
    if inst is None:
        return None
    return InstitutionRefBrief(id=inst.id, name=inst.name, slug=inst.slug)


def _user_to_admin_item(u: User) -> AdminUserListItem:
    return AdminUserListItem(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=u.role.value,  # type: ignore[arg-type]
        role_label=ROLE_LABELS_TR_USERS.get(u.role, u.role.value),
        institution=_institution_to_ref_brief(u.institution) if u.institution_id else None,
        is_active=u.is_active,
        last_login_at=u.last_login_at,
        last_login_ip=u.last_login_ip,
        locked_until=u.locked_until,
        failed_login_count=u.failed_login_count or 0,
        must_change_password=bool(u.must_change_password),
        created_at=u.created_at,
        plan=u.plan if u.institution_id is None else None,
    )


def _users_invalidate() -> list[str]:
    return ["admin:dashboard", "admin:users", "admin:institutions"]


@router.get("/users", response_model=AdminUserListResponse)
def admin_list_users_v2(
    role: str | None = Query(None),
    institution_id: int | None = Query(None),
    q: str | None = Query(None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kullanıcı listesi — rol + kurum + isim/e-posta arama. 500 cap.

    Eşdeğer Jinja: admin.py:708-754 (list_users).
    """
    query = db.query(User).options(joinedload(User.institution))
    role_filter: str | None = None
    if role:
        try:
            role_enum = UserRole[role.strip().upper()]
            query = query.filter(User.role == role_enum)
            role_filter = role_enum.value
        except KeyError:
            pass
    if institution_id is not None and institution_id > 0:
        query = query.filter(User.institution_id == institution_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (User.email.ilike(like)) | (User.full_name.ilike(like))
        )
    users = (
        query.order_by(User.created_at.desc())
        .limit(USER_LIST_LIMIT)
        .all()
    )
    truncated = len(users) >= USER_LIST_LIMIT
    institutions = (
        db.query(Institution).order_by(Institution.name).all()
    )
    inst_refs = [
        _institution_to_ref_brief(i) for i in institutions if i is not None
    ]
    return AdminUserListResponse(
        items=[_user_to_admin_item(u) for u in users],
        total_returned=len(users),
        truncated=truncated,
        institutions=[i for i in inst_refs if i is not None],
        filter_role=role_filter,
        filter_institution_id=institution_id,
        filter_q=q.strip() if q and q.strip() else None,
    )


@router.post(
    "/users",
    response_model=MutationResponse[AdminUserCreateResult],
)
def admin_create_user_v2(
    body: AdminUserCreateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Yeni kullanıcı — sistem güçlü geçici şifre üretir, must_change=True.

    Eşdeğer Jinja: admin.py:757-846 (create_user).
    """
    from app.services.auth_security import generate_strong_password
    from app.services.security import hash_password as _hash

    full_name_clean = (body.full_name or "").strip()
    email_clean = (body.email or "").strip().lower()
    if not full_name_clean or not email_clean:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "name_or_email_required",
                "message": "Ad ve e-posta zorunlu.",
            },
        )
    try:
        role_enum = UserRole[body.role.strip().upper()]
    except (KeyError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "invalid_role",
                "message": "Geçersiz rol.",
            },
        )
    if db.query(User).filter(User.email == email_clean).first():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict", "code": "email_taken",
                "message": "Bu e-posta zaten kayıtlı.",
            },
        )
    iid: int | None = None
    if body.institution_id is not None and body.institution_id > 0:
        if not db.get(Institution, body.institution_id):
            iid = None
        else:
            iid = body.institution_id
    if role_enum == UserRole.INSTITUTION_ADMIN and iid is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "institution_required",
                "message": "Kurum yöneticisi için kurum seçimi zorunlu.",
            },
        )

    pwd = generate_strong_password(role_enum)
    new_user = User(
        email=email_clean,
        password_hash=_hash(pwd),
        full_name=full_name_clean,
        role=role_enum,
        institution_id=iid,
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        must_change_password=True,
    )
    db.add(new_user)
    db.flush()
    # Load institution relationship for response
    if iid is not None:
        new_user.institution = db.get(Institution, iid)

    log_action(
        db,
        action=AuditAction.USER_CREATE,
        actor_id=user.id,
        target_type="user",
        target_id=new_user.id,
        request=request,
        details={
            "email": email_clean,
            "role": role_enum.value,
            "institution_id": iid,
            "temp_password_issued": True,
        },
        autocommit=False,
    )
    db.commit()
    db.refresh(new_user)
    return MutationResponse[AdminUserCreateResult](
        data=AdminUserCreateResult(
            user=_user_to_admin_item(new_user),
            temp_password=pwd,
            must_change_password=True,
        ),
        invalidate=_users_invalidate(),
    )


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def admin_user_detail_v2(
    user_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kullanıcı detayı + son audit + is_self göstergesi.

    Eşdeğer Jinja: admin.py:848-887 (user_detail).
    """
    target = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.id == user_id)
        .first()
    )
    if not target:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "user_not_found",
                "message": "Kullanıcı bulunamadı.",
            },
        )
    institutions = db.query(Institution).order_by(Institution.name).all()
    recent_audits = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == target.id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    return AdminUserDetailResponse(
        target=_user_to_admin_item(target),
        institutions=[
            i for i in (_institution_to_ref_brief(x) for x in institutions)
            if i is not None
        ],
        recent_audits=[_audit_log_to_item(a) for a in recent_audits],
        password_changed_at=target.password_changed_at,
        is_self=(target.id == user.id),
    )


@router.post(
    "/users/{user_id}",
    response_model=MutationResponse[AdminUserMutationResult],
)
def admin_edit_user_v2(
    user_id: int,
    body: AdminUserEditBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kullanıcı güncelle — before/after diff log + is_active → USER_DEACTIVATE.

    Eşdeğer Jinja: admin.py:890-964 (edit_user).
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "user_not_found",
                "message": "Kullanıcı bulunamadı.",
            },
        )
    full_name_clean = (body.full_name or "").strip()
    email_clean = (body.email or "").strip().lower()
    if not full_name_clean or not email_clean:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "name_or_email_required",
                "message": "Ad ve e-posta zorunlu.",
            },
        )
    if email_clean != target.email:
        existing = db.query(User).filter(User.email == email_clean).first()
        if existing and existing.id != target.id:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "conflict", "code": "email_taken",
                    "message": "Bu e-posta zaten kayıtlı.",
                },
            )
    iid: int | None = None
    if body.institution_id is not None and body.institution_id > 0:
        if db.get(Institution, body.institution_id):
            iid = body.institution_id
    before = {
        "full_name": target.full_name, "email": target.email,
        "institution_id": target.institution_id, "is_active": target.is_active,
    }
    target.full_name = full_name_clean
    target.email = email_clean
    target.institution_id = iid
    was_active = target.is_active
    new_active = bool(body.is_active)
    target.is_active = new_active
    after = {
        "full_name": target.full_name, "email": target.email,
        "institution_id": target.institution_id, "is_active": target.is_active,
    }
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={"before": before, "after": after},
        autocommit=False,
    )
    if was_active and not new_active:
        log_action(
            db,
            action=AuditAction.USER_DEACTIVATE,
            actor_id=user.id,
            target_type="user",
            target_id=target.id,
            request=request,
            autocommit=False,
        )
    db.commit()
    db.refresh(target)
    return MutationResponse[AdminUserMutationResult](
        data=AdminUserMutationResult(
            user=_user_to_admin_item(target),
            message="Kullanıcı güncellendi.",
        ),
        invalidate=_users_invalidate(),
    )


@router.post(
    "/users/{user_id}/reset-password",
    response_model=MutationResponse[AdminUserMutationResult],
)
def admin_reset_user_password_v2(
    user_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Şifre sıfırla — güçlü geçici şifre + must_change=True + kilit aç.

    Eşdeğer Jinja: admin.py:967-1002 (reset_user_password).
    """
    from app.services.auth_security import generate_strong_password
    from app.services.security import hash_password as _hash

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "user_not_found",
                "message": "Kullanıcı bulunamadı.",
            },
        )
    pwd = generate_strong_password(target.role)
    target.password_hash = _hash(pwd)
    target.password_changed_at = datetime.now(timezone.utc)
    target.must_change_password = True
    target.failed_login_count = 0
    target.locked_until = None
    log_action(
        db,
        action=AuditAction.PASSWORD_RESET,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={"forced_by_admin": True, "temp_password_issued": True},
        autocommit=False,
    )
    db.commit()
    db.refresh(target)
    return MutationResponse[AdminUserMutationResult](
        data=AdminUserMutationResult(
            user=_user_to_admin_item(target),
            message="Geçici şifre üretildi. Kullanıcı ilk girişte değiştirecek.",
            temp_password=pwd,
        ),
        invalidate=_users_invalidate(),
    )


@router.post(
    "/users/{user_id}/change-role",
    response_model=MutationResponse[AdminUserMutationResult],
)
def admin_change_user_role_v2(
    user_id: int,
    body: AdminUserChangeRoleBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Rol değişimi — kendi rolünü değiştirme YASAK.

    Eşdeğer Jinja: admin.py:1005-1068 (change_user_role).
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "user_not_found",
                "message": "Kullanıcı bulunamadı.",
            },
        )
    if target.id == user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden", "code": "cannot_change_own_role",
                "message": "Kendi rolünü değiştiremezsin (kilitlenme riski).",
            },
        )
    try:
        role_enum = UserRole[body.new_role.strip().upper()]
    except (KeyError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "invalid_role",
                "message": "Geçersiz rol.",
            },
        )
    iid: int | None = None
    if body.institution_id is not None and body.institution_id > 0:
        iid = body.institution_id
    if role_enum == UserRole.INSTITUTION_ADMIN and iid is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "institution_required",
                "message": "Kurum yöneticisi için kurum seçimi zorunlu.",
            },
        )
    old_role = target.role
    target.role = role_enum
    if iid is not None:
        target.institution_id = iid
    log_action(
        db,
        action=AuditAction.ROLE_CHANGE,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={
            "from": old_role.value, "to": role_enum.value,
            "institution_id": target.institution_id,
        },
        autocommit=False,
    )
    db.commit()
    db.refresh(target)
    return MutationResponse[AdminUserMutationResult](
        data=AdminUserMutationResult(
            user=_user_to_admin_item(target),
            message=(
                f"Rol değişti: {ROLE_LABELS_TR_USERS[old_role]} → "
                f"{ROLE_LABELS_TR_USERS[role_enum]}"
            ),
        ),
        invalidate=_users_invalidate(),
    )


@router.post(
    "/users/{user_id}/activate-plan",
    response_model=MutationResponse[AdminUserMutationResult],
)
def admin_activate_user_plan_v2(
    user_id: int,
    body: AdminActivatePlanBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Bağımsız koç abonelik aktivasyonu (manuel ödeme sonrası).

    Koç uygulama-içinden talep eder (subscription-request → İletişim Talepleri);
    süper admin ödemeyi aldıktan sonra buradan planı aktive eder.
    """
    from app.models import PlanChangeReason, PlanOwnerType
    from app.services.plans import SOLO_PLANS, change_plan, get_plan_info

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "user_not_found",
                    "message": "Kullanıcı bulunamadı."},
        )
    if target.role != UserRole.TEACHER or target.institution_id is not None:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "not_solo_teacher",
                    "message": "Yalnız bağımsız koç planı aktive edilebilir."},
        )
    plan = (body.plan or "").strip()
    if plan not in SOLO_PLANS:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invalid_plan",
                    "message": "Geçersiz solo plan."},
        )
    cycle = (body.cycle or "monthly").strip()
    if cycle not in ("monthly", "academic_year"):
        cycle = "monthly"
    change_plan(
        db, owner_type=PlanOwnerType.USER, owner_id=target.id, new_plan=plan,
        reason=PlanChangeReason.UPGRADE, actor_user_id=user.id,
        note="Süper admin abonelik aktivasyonu (manuel ödeme)", autocommit=False,
    )
    # Abonelik durumu: ücretli plan → active + dönem sonu (yenileme); free → temizle.
    from app.services.plans import is_paid_plan as _is_paid
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    if _is_paid(plan):
        target.subscription_status = "active"
        target.subscription_cycle = cycle
        days = 365 if cycle == "academic_year" else 30
        target.subscription_period_end = _dt.now(_tz.utc) + _td(days=days)
    else:
        target.subscription_status = None
        target.subscription_cycle = None
        target.subscription_period_end = None
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="user", target_id=target.id, request=request,
        details={"action": "activate_plan", "plan": plan}, autocommit=False,
    )
    db.commit()
    db.refresh(target)
    info = get_plan_info(plan)
    return MutationResponse[AdminUserMutationResult](
        data=AdminUserMutationResult(
            user=_user_to_admin_item(target),
            message=f"Abonelik aktive edildi: {info.label if info else plan}",
        ),
        invalidate=_users_invalidate(),
    )


@router.post(
    "/users/{user_id}/delete",
    response_model=MutationResponse[AdminUserMutationResult],
)
def admin_delete_user_v2(
    user_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kullanıcıyı sil — kendi hesabı YASAK + CASCADE.

    Eşdeğer Jinja: admin.py:1071-1107 (delete_user).
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "user_not_found",
                "message": "Kullanıcı bulunamadı.",
            },
        )
    if target.id == user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden", "code": "cannot_delete_self",
                "message": "Kendi hesabını silemezsin.",
            },
        )
    target_name = target.full_name
    log_action(
        db,
        action=AuditAction.USER_DELETE,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={
            "email": target.email, "role": target.role.value,
        },
        autocommit=False,
    )
    db.delete(target)
    db.commit()
    return MutationResponse[AdminUserMutationResult](
        data=AdminUserMutationResult(
            user=None,
            message=f"{target_name} silindi.",
        ),
        invalidate=_users_invalidate(),
    )


# =============================================================================
# P3 — Impersonate
# =============================================================================


@router.post(
    "/users/{user_id}/impersonate",
    response_model=AdminImpersonateResult,
)
def admin_impersonate_user_v2(
    user_id: int,
    body: AdminImpersonateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Süper admin başka bir kullanıcı olarak sahte oturum açar.

    Kurallar:
      - target.id != user.id (kendi)
      - target.role != SUPER_ADMIN (yetki sızıntısı)
      - target.is_active (pasif yasak)
      - reason zorunlu (10-200 char)
      - ImpersonationSession 30dk TTL
      - Mevcut aktif oturum (actor, target) idempotent — eskisi kapanır

    Eşdeğer Jinja: admin.py:1113-1221 (impersonate_user).

    NOT: API v2 endpoint Jinja session'a yazar (SessionMiddleware paylaşımlı).
    Frontend redirect_url'i kullanarak yönlendirir.
    """
    from app.services.impersonation import (
        find_active_for_actor_target,
        start_session,
        validate_reason,
    )

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "user_not_found",
                "message": "Kullanıcı bulunamadı.",
            },
        )
    if target.id == user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden", "code": "cannot_impersonate_self",
                "message": "Kendin olarak sahte oturum açamazsın.",
            },
        )
    if target.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden", "code": "cannot_impersonate_super_admin",
                "message": "Diğer süper admin olarak oturum açamazsın (yetki sızıntısı).",
            },
        )
    if not target.is_active:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden", "code": "target_inactive",
                "message": "Pasif kullanıcı olarak sahte oturum açılamaz.",
            },
        )

    # reason validate
    validation = validate_reason(body.reason)
    if not validation.ok:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "invalid_reason",
                "message": validation.error or "Gerekçe gerekli (10-200 karakter).",
            },
        )

    # Idempotent: aynı admin'in aynı target için aktif oturumu kapansın
    existing = find_active_for_actor_target(
        db, actor_id=user.id, target_id=target.id
    )
    if existing is not None:
        existing.ended_at = datetime.now(timezone.utc)
        existing.end_reason = "manual"
        existing.ended_by_user_id = user.id
        db.commit()

    ip = (request.client.host if request.client else None)
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip()[:64]

    imp = start_session(
        db, actor=user, target=target, reason=validation.cleaned, ip=ip,
    )

    log_action(
        db,
        action=AuditAction.IMPERSONATE_START,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={
            "admin_email": user.email,
            "target_email": target.email,
            "target_role": target.role.value,
            "reason": validation.cleaned,
            "impersonation_id": imp.id,
            "expires_at": imp.expires_at.isoformat(),
        },
    )

    # SessionMiddleware cookie (Jinja-compatible) ile target oturumu set
    try:
        request.session["impersonator_id"] = user.id
        request.session["impersonate_started_at"] = (
            datetime.now(timezone.utc).isoformat()
        )
        request.session["impersonation_id"] = imp.id
        request.session["user_id"] = target.id
        request.session["role"] = target.role.value
        request.session["password_stamp"] = (
            target.password_changed_at.isoformat()
            if target.password_changed_at else None
        )
    except (AttributeError, AssertionError):
        # SessionMiddleware bağlı değilse (test client'ta) — sessizce devam
        pass

    if target.role == UserRole.TEACHER:
        dest = "/teacher"
    elif target.role == UserRole.STUDENT:
        dest = "/student"
    elif target.role == UserRole.PARENT:
        dest = "/parent"
    elif target.role == UserRole.INSTITUTION_ADMIN:
        dest = "/institution"
    else:
        dest = "/"

    return AdminImpersonateResult(
        impersonation_id=imp.id,
        actor_id=user.id,
        target_id=target.id,
        target_full_name=target.full_name,
        target_role=target.role.value,  # type: ignore[arg-type]
        expires_at=imp.expires_at,
        redirect_url=dest,
    )


@router.post("/impersonate/end", response_model=AdminImpersonateEndResult)
def admin_impersonate_end_v2(
    request: Request,
    db: Session = Depends(get_db),
):
    """Sahte oturumu sonlandır — gerçek admin'e restore.

    Auth zorunlu DEĞİL — session.impersonator_id'ye bakılır.

    Eşdeğer Jinja: admin.py:1224-1278 (end_impersonation).
    """
    try:
        impersonator_id = request.session.get("impersonator_id")
    except (AttributeError, AssertionError):
        impersonator_id = None

    if not impersonator_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthenticated", "code": "no_impersonation_session",
                "message": "Aktif sahte oturum yok.",
            },
        )
    admin = db.get(User, impersonator_id)
    if not admin or admin.role != UserRole.SUPER_ADMIN or not admin.is_active:
        try:
            request.session.clear()
        except (AttributeError, AssertionError):
            pass
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthenticated", "code": "admin_unavailable",
                "message": "Admin oturumu geçersiz, tekrar giriş yapın.",
            },
        )
    target_id = request.session.get("user_id")
    imp_id = request.session.get("impersonation_id")
    if imp_id:
        try:
            from app.services.impersonation import end_session as _end_imp
            _end_imp(
                db, session_id=imp_id, end_reason="manual",
                ended_by_user_id=admin.id,
            )
        except Exception:
            logger.exception("impersonation end fail imp=%s", imp_id)
    log_action(
        db,
        action=AuditAction.IMPERSONATE_END,
        actor_id=admin.id,
        target_type="user",
        target_id=target_id,
        request=request,
        details={
            "target_user_id": target_id,
            "impersonation_id": imp_id,
        },
    )
    try:
        request.session.clear()
        request.session["user_id"] = admin.id
        request.session["role"] = admin.role.value
        request.session["password_stamp"] = (
            admin.password_changed_at.isoformat()
            if admin.password_changed_at else None
        )
        request.session["login_at"] = datetime.now(timezone.utc).isoformat()
    except (AttributeError, AssertionError):
        pass

    return AdminImpersonateEndResult(
        admin_id=admin.id,
        admin_full_name=admin.full_name,
        target_user_id=target_id,
        redirect_url="/admin",
    )


# =============================================================================
# P3 — Independent teachers list (sidebar item)
# =============================================================================


@router.get(
    "/independent-teachers", response_model=AdminIndependentTeachersResponse,
)
def admin_independent_teachers_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Bağımsız öğretmenler listesi — login-bazlı 4-band heuristik.

    Eşdeğer Jinja: admin.py:131-147 (independent_teachers_list).
    """
    summary, rows = _independent_teacher_activity_payload(db)
    return AdminIndependentTeachersResponse(summary=summary, rows=rows)


# =============================================================================
# P4 — Audit list (pagination + filter)
# =============================================================================


AUDIT_PER_PAGE = 50


def _parse_iso_date(s: str | None):
    """YYYY-MM-DD parse — geçersizse None."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        from datetime import date as _date
        return _date.fromisoformat(s)
    except ValueError:
        return None


@router.get("/audit", response_model=AuditListResponse)
def admin_audit_list_v2(
    action: str | None = Query(None),
    actor_id: int | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Audit log — 50/sayfa pagination + 4 filter.

    Eşdeğer Jinja: admin.py:1298-1399 (audit_list).
    """
    from datetime import date as _date, datetime as _dt, timedelta as _td

    query = db.query(AuditLog)
    if action:
        try:
            action_enum = AuditAction[action.strip().upper()]
            query = query.filter(AuditLog.action == action_enum)
        except KeyError:
            pass
    if actor_id is not None and actor_id > 0:
        query = query.filter(AuditLog.actor_id == actor_id)

    sd = _parse_iso_date(start_date)
    ed = _parse_iso_date(end_date)
    if sd is not None:
        sd_dt = _dt.combine(sd, _dt.min.time(), tzinfo=timezone.utc)
        query = query.filter(AuditLog.created_at >= sd_dt)
    if ed is not None:
        ed_dt = _dt.combine(ed + _td(days=1), _dt.min.time(), tzinfo=timezone.utc)
        query = query.filter(AuditLog.created_at < ed_dt)

    total = query.count()
    page = max(1, page)
    audits = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * AUDIT_PER_PAGE)
        .limit(AUDIT_PER_PAGE)
        .all()
    )

    # Actor + via_admin map
    actor_ids: set[int] = {a.actor_id for a in audits if a.actor_id}
    via_admin_map: dict[int, int] = {}
    details_parsed_map: dict[int, dict] = {}
    for a in audits:
        if not a.details_json:
            continue
        try:
            d = json.loads(a.details_json)
        except (ValueError, TypeError):
            continue
        if isinstance(d, dict):
            details_parsed_map[a.id] = d
            if d.get("_via_admin"):
                try:
                    via_id = int(d["_via_admin"])
                    via_admin_map[a.id] = via_id
                    actor_ids.add(via_id)
                except (ValueError, TypeError):
                    pass

    actors_map: dict[int, User] = {}
    if actor_ids:
        for u in db.query(User).filter(User.id.in_(actor_ids)).all():
            actors_map[u.id] = u

    def _actor_brief(uid: int | None) -> AuditActorBrief | None:
        if uid is None:
            return None
        u = actors_map.get(uid)
        if u is None:
            return None
        return AuditActorBrief(id=u.id, email=u.email, full_name=u.full_name)

    items: list[AuditListItem] = []
    for a in audits:
        action_label = AUDIT_ACTION_LABELS.get(a.action, a.action.value)
        via_id = via_admin_map.get(a.id)
        items.append(
            AuditListItem(
                id=a.id,
                action=a.action.value,
                action_label=action_label,
                actor_id=a.actor_id,
                actor=_actor_brief(a.actor_id),
                email_attempted=a.email_attempted,
                target_type=a.target_type,
                target_id=a.target_id,
                ip_address=a.ip_address,
                user_agent=a.user_agent,
                details_parsed=details_parsed_map.get(a.id),
                via_admin_id=via_id,
                via_admin=_actor_brief(via_id),
                created_at=a.created_at,
            )
        )

    total_pages = max(1, (total + AUDIT_PER_PAGE - 1) // AUDIT_PER_PAGE)
    all_actions = [
        {"value": a.value, "label": AUDIT_ACTION_LABELS.get(a, a.value)}
        for a in AuditAction
    ]
    return AuditListResponse(
        items=items,
        total=total,
        page=page,
        total_pages=total_pages,
        per_page=AUDIT_PER_PAGE,
        filter_action=action if action else None,
        filter_actor_id=actor_id if actor_id else None,
        filter_start_date=(sd.isoformat() if sd else None),
        filter_end_date=(ed.isoformat() if ed else None),
        all_actions=all_actions,
    )


# =============================================================================
# P4 — System health
# =============================================================================


@router.get("/system-health", response_model=SystemHealthResponse)
def admin_system_health_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Cron + dispatcher + DB sağlık paneli.

    Eşdeğer Jinja: admin.py:3072-3088 (system_health).
    """
    from app.services.system_health import collect_snapshot

    snapshot = collect_snapshot(db)
    crons = [
        CronStatusItem(
            job_key=c.schedule.job_key,
            description=getattr(c.schedule, "description", None),
            dow_label=getattr(c.schedule, "dow_label", "—"),
            time_label=getattr(c.schedule, "time_label", "—"),
            enabled=c.schedule.enabled,
            last_run_at=c.last_run_at,
            last_status=c.last_status,
            last_error=c.last_error,
            hours_since_run=c.hours_since_run,
            health=c.health,
        )
        for c in snapshot.crons
    ]
    dispatcher = (
        DispatcherStatusInfo(
            queued_count=snapshot.dispatcher.queued_count,
            failed_count=snapshot.dispatcher.failed_count,
            oldest_queued_at=snapshot.dispatcher.oldest_queued_at,
            oldest_queued_age_hours=snapshot.dispatcher.oldest_queued_age_hours,
            health=snapshot.dispatcher.health,
        )
        if snapshot.dispatcher
        else None
    )
    database = (
        DatabaseStatusInfo(
            file_path=snapshot.database.file_path,
            file_size_mb=snapshot.database.file_size_mb,
            table_counts=snapshot.database.table_counts,
            health=snapshot.database.health,
        )
        if snapshot.database
        else None
    )
    return SystemHealthResponse(
        crons=crons,
        dispatcher=dispatcher,
        database=database,
        overall_health=snapshot.overall_health,
    )


# =============================================================================
# P4 — Announcements
# =============================================================================


def _announcement_to_item(ann, now: datetime | None = None) -> AnnouncementItem:
    """SystemAnnouncement → AnnouncementItem."""
    from app.models import AUDIENCE_LABELS_TR, SEVERITY_LABELS_TR
    if now is None:
        now = datetime.now(timezone.utc)
    return AnnouncementItem(
        id=ann.id,
        title=ann.title,
        message=ann.message,
        severity=ann.severity.value,  # type: ignore[arg-type]
        severity_label=SEVERITY_LABELS_TR.get(ann.severity, ann.severity.value),
        audience=ann.audience.value,  # type: ignore[arg-type]
        audience_label=AUDIENCE_LABELS_TR.get(ann.audience, ann.audience.value),
        starts_at=ann.starts_at,
        ends_at=ann.ends_at,
        dismissible=bool(ann.dismissible),
        is_active_now=ann.is_active(now),
        created_by=ann.created_by,
        created_at=ann.created_at,
    )


@router.get("/announcements", response_model=AnnouncementsListResponse)
def admin_announcements_list_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tüm duyurular (aktif + geçmiş) — son 50.

    Eşdeğer Jinja: admin.py:2806-2840 (announcements_list).
    """
    from app.models import (
        AUDIENCE_LABELS_TR,
        AnnouncementAudience,
        AnnouncementSeverity,
        SEVERITY_LABELS_TR,
        SystemAnnouncement,
    )

    items = (
        db.query(SystemAnnouncement)
        .order_by(SystemAnnouncement.created_at.desc())
        .limit(50)
        .all()
    )
    now = datetime.now(timezone.utc)
    return AnnouncementsListResponse(
        items=[_announcement_to_item(ann, now) for ann in items],
        severities=[
            AnnouncementSeverityOption(
                value=s.value, label=SEVERITY_LABELS_TR.get(s, s.value),
            )  # type: ignore[arg-type]
            for s in AnnouncementSeverity
        ],
        audiences=[
            AnnouncementAudienceOption(
                value=a.value, label=AUDIENCE_LABELS_TR.get(a, a.value),
            )  # type: ignore[arg-type]
            for a in AnnouncementAudience
        ],
    )


@router.post(
    "/announcements",
    response_model=MutationResponse[AnnouncementMutationResult],
)
def admin_announcements_create_v2(
    body: AnnouncementCreateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Yeni duyuru oluştur.

    Eşdeğer Jinja: admin.py:2843-2916 (announcements_create).
    """
    from app.models import (
        AnnouncementAudience,
        AnnouncementSeverity,
        SystemAnnouncement,
    )
    from app.services.announcements import invalidate_cache as _inv_ann

    msg_clean = (body.message or "").strip()
    if not msg_clean:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "message_required",
                "message": "Mesaj zorunlu",
            },
        )
    try:
        sev = AnnouncementSeverity(body.severity)
    except ValueError:
        sev = AnnouncementSeverity.INFO
    try:
        aud = AnnouncementAudience(body.audience)
    except ValueError:
        aud = AnnouncementAudience.ALL

    sa: datetime | None = None
    ea: datetime | None = None
    try:
        if body.starts_at:
            sa = datetime.fromisoformat(body.starts_at)
            if sa.tzinfo is None:
                sa = sa.replace(tzinfo=timezone.utc)
        if body.ends_at:
            ea = datetime.fromisoformat(body.ends_at)
            if ea.tzinfo is None:
                ea = ea.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "invalid_datetime",
                "message": "Tarih formatı hatalı (YYYY-MM-DDTHH:MM)",
            },
        )

    ann = SystemAnnouncement(
        title=(body.title or "").strip() or None,
        message=msg_clean,
        severity=sev,
        audience=aud,
        starts_at=sa or datetime.now(timezone.utc),
        ends_at=ea,
        dismissible=bool(body.dismissible),
        created_by=user.id,
    )
    db.add(ann)
    db.flush()
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="announcement",
        target_id=ann.id,
        request=request,
        details={"severity": sev.value, "audience": aud.value},
        autocommit=False,
    )
    db.commit()
    db.refresh(ann)
    _inv_ann()
    return MutationResponse[AnnouncementMutationResult](
        data=AnnouncementMutationResult(
            announcement=_announcement_to_item(ann),
            message="Duyuru oluşturuldu",
        ),
        invalidate=["admin:announcements"],
    )


@router.post(
    "/announcements/{announcement_id}/delete",
    response_model=MutationResponse[AnnouncementMutationResult],
)
def admin_announcements_delete_v2(
    announcement_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Duyuru sil.

    Eşdeğer Jinja: admin.py:3091-3119 (announcements_delete).
    """
    from app.models import SystemAnnouncement
    from app.services.announcements import invalidate_cache as _inv_ann

    ann = db.get(SystemAnnouncement, announcement_id)
    if not ann:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "announcement_not_found",
                "message": "Duyuru bulunamadı",
            },
        )
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="announcement",
        target_id=announcement_id,
        request=request,
        details={"deleted": True},
    )
    db.delete(ann)
    db.commit()
    _inv_ann()
    return MutationResponse[AnnouncementMutationResult](
        data=AnnouncementMutationResult(
            announcement=None,
            message="Duyuru silindi",
        ),
        invalidate=["admin:announcements"],
    )


# =============================================================================
# P4 — KVKK
# =============================================================================


def _kvkk_user_brief(u: User | None) -> KvkkRequestUserBrief | None:
    if u is None:
        return None
    return KvkkRequestUserBrief(
        id=u.id, email=u.email, full_name=u.full_name,
    )


def _kvkk_request_to_item(req) -> KvkkRequestItem:
    from app.models import (
        DATA_REQUEST_KIND_LABELS_TR,
        DATA_REQUEST_STATUS_LABELS_TR,
    )
    return KvkkRequestItem(
        id=req.id,
        kind=req.kind.value,  # type: ignore[arg-type]
        kind_label=DATA_REQUEST_KIND_LABELS_TR.get(req.kind, req.kind.value),
        status=req.status.value,  # type: ignore[arg-type]
        status_label=DATA_REQUEST_STATUS_LABELS_TR.get(
            req.status, req.status.value,
        ),
        target_user=_kvkk_user_brief(req.target_user),
        requester_user=_kvkk_user_brief(req.requester_user),
        reason=req.reason,
        admin_note=req.admin_note,
        process_after=req.process_after,
        processed_at=req.processed_at,
        created_at=req.created_at,
    )


@router.get("/kvkk", response_model=KvkkDashboardResponse)
def admin_kvkk_dashboard_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """KVKK denetim paneli — özet + bekleyen/son talepler + envanter.

    Eşdeğer Jinja: admin.py:3125-3169 (admin_kvkk_dashboard).
    """
    from app.models import DataSubjectRequest
    from app.services.kvkk import DATA_INVENTORY, request_summary

    summary_dict = request_summary(db)
    summary = KvkkSummary(
        total=summary_dict.get("total", 0),
        pending=summary_dict.get("pending", 0),
        processing=summary_dict.get("processing", 0),
        completed=summary_dict.get("completed", 0),
        cancelled=summary_dict.get("cancelled", 0),
        rejected=summary_dict.get("rejected", 0),
    )

    pending_rows = (
        db.query(DataSubjectRequest)
        .options(
            joinedload(DataSubjectRequest.target_user),
            joinedload(DataSubjectRequest.requester_user),
        )
        .filter(DataSubjectRequest.status.in_(["pending", "processing"]))
        .order_by(DataSubjectRequest.created_at.desc())
        .limit(50)
        .all()
    )
    recent_rows = (
        db.query(DataSubjectRequest)
        .options(joinedload(DataSubjectRequest.target_user))
        .order_by(DataSubjectRequest.created_at.desc())
        .limit(20)
        .all()
    )
    inventory = [
        KvkkDataInventoryItem(
            table_name=item.table_name,
            label=item.label,
            contains_pii=item.contains_pii,
            retention_days=item.retention_days,
            legal_basis=item.legal_basis,
            purpose=item.purpose,
        )
        for item in DATA_INVENTORY
    ]
    return KvkkDashboardResponse(
        summary=summary,
        pending_rows=[_kvkk_request_to_item(r) for r in pending_rows],
        recent_rows=[_kvkk_request_to_item(r) for r in recent_rows],
        data_inventory=inventory,
    )


@router.post(
    "/kvkk/requests/{request_id}/apply",
    response_model=MutationResponse[KvkkMutationResult],
)
def admin_kvkk_apply_v2(
    request_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Bekleyen silme talebini hemen uygula (30g grace'i atla).

    Eşdeğer Jinja: admin.py:3172-3204 (admin_kvkk_apply).
    """
    from app.models import DataRequestKind, DataRequestStatus, DataSubjectRequest
    from app.services.kvkk import apply_deletion

    req = db.get(DataSubjectRequest, request_id)
    if req is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "kvkk_request_not_found",
                "message": "Talep bulunamadı",
            },
        )
    if req.kind != DataRequestKind.DELETE:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "only_delete_can_be_applied",
                "message": "Yalnız silme talepleri uygulanabilir",
            },
        )
    if req.status not in (DataRequestStatus.PENDING, DataRequestStatus.PROCESSING):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "kvkk_already_closed",
                "message": "Bu talep zaten kapatıldı",
            },
        )

    apply_deletion(db, request=req, by_user=user)
    db.refresh(req)
    return MutationResponse[KvkkMutationResult](
        data=KvkkMutationResult(
            request=_kvkk_request_to_item(req),
            message="Silme talebi uygulandı",
        ),
        invalidate=["admin:kvkk"],
    )


@router.post(
    "/kvkk/requests/{request_id}/reject",
    response_model=MutationResponse[KvkkMutationResult],
)
def admin_kvkk_reject_v2(
    request_id: int,
    body: KvkkRejectBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Talebi reddet — admin gerekçe yazar.

    Eşdeğer Jinja: admin.py:3207-3234 (admin_kvkk_reject).
    """
    from app.models import DataRequestStatus, DataSubjectRequest

    req = db.get(DataSubjectRequest, request_id)
    if req is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "kvkk_request_not_found",
                "message": "Talep bulunamadı",
            },
        )
    if req.status not in (DataRequestStatus.PENDING, DataRequestStatus.PROCESSING):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "kvkk_already_closed",
                "message": "Bu talep zaten kapatıldı",
            },
        )
    req.status = DataRequestStatus.REJECTED
    req.processed_by_user_id = user.id
    req.processed_at = datetime.now(timezone.utc)
    req.admin_note = (body.note or "").strip()[:500] or "Admin reddetti"
    db.commit()
    db.refresh(req)
    return MutationResponse[KvkkMutationResult](
        data=KvkkMutationResult(
            request=_kvkk_request_to_item(req),
            message="Talep reddedildi",
        ),
        invalidate=["admin:kvkk"],
    )


# =============================================================================
# P5 — Usage (owner-pattern: institution|user)
# =============================================================================


def _credit_account_to_info(acc) -> UsageAccountInfo:
    return UsageAccountInfo(
        plan_code=acc.plan_code,
        used_credits=acc.used_credits or 0,
        allocated_credits=acc.allocated_credits,
        bonus_credits=acc.bonus_credits or 0,
        total_allocated=acc.total_allocated,
        remaining_credits=acc.remaining_credits,
        usage_pct=int(acc.usage_pct),
        hard_block_enabled=bool(acc.hard_block_enabled),
        blocked_until=acc.blocked_until,
    )


@router.get("/usage", response_model=AdminUsageResponse)
def admin_usage_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Sistem geneli kullanım — kurumlar + bağımsız öğretmenler (owner-pattern).

    Eşdeğer Jinja: admin.py:1405-1495 (super_admin_usage).
    """
    from app.models import USAGE_KIND_LABELS_TR
    from app.services.credits import (
        KIND_CREDITS,
        CreditOwner,
        current_period,
        get_or_create_account,
    )

    period = current_period()

    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    inst_rows: list[UsageInstitutionRow] = []
    total_used_inst = 0
    total_alloc_inst = 0
    for inst in insts:
        owner = CreditOwner.for_institution(inst)
        acc = get_or_create_account(db, owner=owner, period=period)
        inst_rows.append(
            UsageInstitutionRow(
                institution_id=inst.id,
                name=inst.name,
                slug=inst.slug,
                account=_credit_account_to_info(acc),
            )
        )
        total_used_inst += acc.used_credits or 0
        total_alloc_inst += acc.total_allocated
    db.commit()
    inst_rows.sort(key=lambda r: -r.account.usage_pct)

    indeps = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
        .all()
    )
    indep_rows: list[UsageIndependentRow] = []
    total_used_indep = 0
    total_alloc_indep = 0
    for u in indeps:
        owner = CreditOwner.for_user(u)
        acc = get_or_create_account(db, owner=owner, period=period)
        indep_rows.append(
            UsageIndependentRow(
                user_id=u.id,
                full_name=u.full_name,
                email=u.email,
                account=_credit_account_to_info(acc),
            )
        )
        total_used_indep += acc.used_credits or 0
        total_alloc_indep += acc.total_allocated
    db.commit()
    indep_rows.sort(key=lambda r: -r.account.usage_pct)

    kind_costs = [
        UsageKindCost(
            kind=k.value,
            label=USAGE_KIND_LABELS_TR.get(k, k.value),
            cost=cost,
        )
        for k, cost in KIND_CREDITS.items()
    ]

    return AdminUsageResponse(
        period=period,
        inst_rows=inst_rows,
        indep_rows=indep_rows,
        totals=UsageTotals(
            inst_used=total_used_inst,
            inst_alloc=total_alloc_inst,
            indep_used=total_used_indep,
            indep_alloc=total_alloc_indep,
            grand_used=total_used_inst + total_used_indep,
            grand_alloc=total_alloc_inst + total_alloc_indep,
        ),
        kind_costs=kind_costs,
    )


@router.post(
    "/usage/institution/{institution_id}/hard-block",
    response_model=MutationResponse[UsageMutationResult],
)
def admin_usage_hard_block_toggle_v2(
    institution_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Hard-block toggle — sadece kurumlar için.

    Eşdeğer Jinja: admin.py:1498-1559 (super_admin_hard_block_toggle).
    """
    from app.models import CreditAccount, UsageOwnerType
    from app.services.credits import current_period

    period = current_period()
    acc = (
        db.query(CreditAccount)
        .filter(
            CreditAccount.owner_type == UsageOwnerType.INSTITUTION,
            CreditAccount.owner_id == institution_id,
            CreditAccount.period_year_month == period,
        )
        .first()
    )
    if not acc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "account_not_found",
                "message": "Hesap bulunamadı",
            },
        )
    new_state = not acc.hard_block_enabled
    acc.hard_block_enabled = new_state
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="credit_account",
        target_id=acc.id,
        request=request,
        details={
            "hard_block_enabled": new_state,
            "institution_id": institution_id,
            "period": period,
        },
        autocommit=False,
    )
    db.commit()
    db.refresh(acc)
    msg = (
        f"Kurum #{institution_id} hard-block aktif edildi"
        if new_state
        else f"Kurum #{institution_id} hard-block kapatıldı"
    )
    return MutationResponse[UsageMutationResult](
        data=UsageMutationResult(
            account=_credit_account_to_info(acc),
            message=msg,
        ),
        invalidate=["admin:usage"],
    )


@router.post(
    "/usage/{owner_type}/{owner_id}/bonus",
    response_model=MutationResponse[UsageMutationResult],
)
def admin_usage_add_bonus_v2(
    owner_type: str,
    owner_id: int,
    body: UsageBonusBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Bonus kredi ekle — kurum veya bağımsız öğretmen.

    Eşdeğer Jinja: admin.py:1562-1626 (super_admin_add_bonus).
    """
    from app.models import CreditAccount, UsageOwnerType
    from app.services.credits import current_period

    if owner_type not in ("institution", "user"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "invalid_owner_type",
                "message": "Geçersiz sahip türü",
            },
        )
    if body.bonus_amount <= 0 or body.bonus_amount > 100000:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "invalid_bonus_amount",
                "message": "Bonus 1-100000 arasında olmalı",
            },
        )
    period = current_period()
    owner_enum = (
        UsageOwnerType.INSTITUTION
        if owner_type == "institution"
        else UsageOwnerType.USER
    )
    acc = (
        db.query(CreditAccount)
        .filter(
            CreditAccount.owner_type == owner_enum,
            CreditAccount.owner_id == owner_id,
            CreditAccount.period_year_month == period,
        )
        .first()
    )
    if not acc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "account_not_found",
                "message": "Hesap bulunamadı",
            },
        )
    acc.bonus_credits = (acc.bonus_credits or 0) + body.bonus_amount
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="credit_account",
        target_id=acc.id,
        request=request,
        details={
            "bonus_added": body.bonus_amount,
            "new_bonus_total": acc.bonus_credits,
            "owner_type": owner_type,
            "owner_id": owner_id,
            "period": period,
        },
        autocommit=False,
    )
    db.commit()
    db.refresh(acc)
    return MutationResponse[UsageMutationResult](
        data=UsageMutationResult(
            account=_credit_account_to_info(acc),
            message=f"+{body.bonus_amount} bonus kredi eklendi",
        ),
        invalidate=["admin:usage"],
    )


# =============================================================================
# P5 — Quota
# =============================================================================


@router.get("/quota", response_model=AdminQuotaResponse)
def admin_quota_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tüm kurumların kuota tablosu + override yönetimi.

    Eşdeğer Jinja: admin.py:2922-2986 (super_admin_quota).
    """
    from app.services.quotas import (
        PLAN_QUOTAS,
        QUOTA_KEYS,
        QUOTA_LABELS_TR,
        count_current_usage,
        get_quota_limit,
    )

    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    rows: list[QuotaInstitutionRow] = []
    for inst in insts:
        cells: list[QuotaCell] = []
        max_pct = 0
        for key in QUOTA_KEYS:
            limit, has_override, note = get_quota_limit(
                db, institution=inst, quota_key=key,
            )
            current = count_current_usage(
                db, institution_id=inst.id, quota_key=key,
            )
            is_unlimited = limit == -1
            if is_unlimited:
                pct = 0
            elif limit == 0:
                pct = 100 if current > 0 else 0
            else:
                pct = int(round(100 * current / limit)) if limit > 0 else 0
            max_pct = max(max_pct, pct if not is_unlimited else 0)
            cells.append(
                QuotaCell(
                    key=key,
                    label=QUOTA_LABELS_TR.get(key, key),
                    limit=limit,
                    current=current,
                    pct=pct,
                    is_unlimited=is_unlimited,
                    is_at_limit=(not is_unlimited) and current >= limit,
                    has_override=has_override,
                    note=note,
                )
            )
        rows.append(
            QuotaInstitutionRow(
                institution_id=inst.id,
                name=inst.name,
                slug=inst.slug,
                plan=inst.plan or "free",
                cells=cells,
                max_pct=max_pct,
            )
        )
    rows.sort(key=lambda r: -r.max_pct)

    plans = [
        QuotaPlanRow(
            plan=plan_code,
            teachers=PLAN_QUOTAS[plan_code].get("teachers", 0),
            students=PLAN_QUOTAS[plan_code].get("students", 0),
            institution_admins=PLAN_QUOTAS[plan_code].get(
                "institution_admins", 0
            ),
        )
        for plan_code in PLAN_QUOTAS
    ]
    return AdminQuotaResponse(
        rows=rows,
        quota_keys=list(QUOTA_KEYS),
        quota_labels=dict(QUOTA_LABELS_TR),
        plans=plans,
    )


@router.post(
    "/quota/{institution_id}/override",
    response_model=MutationResponse[QuotaMutationResult],
)
def admin_quota_set_override_v2(
    institution_id: int,
    body: QuotaOverrideBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kuruma kuota override koy (veya güncelle).

    Eşdeğer Jinja: admin.py:2989-3037 (super_admin_quota_set_override).
    """
    from app.services.quotas import QUOTA_KEYS, set_override

    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "institution_not_found",
                "message": "Kurum bulunamadı",
            },
        )
    if body.quota_key not in QUOTA_KEYS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "invalid_quota_key",
                "message": "Geçersiz kuota anahtarı",
            },
        )
    if body.override_value < -1 or body.override_value > 1000000:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "invalid_override_value",
                "message": "override_value -1 (sınırsız), 0 (kapalı) veya 1-1M",
            },
        )
    o = set_override(
        db,
        institution_id=institution_id,
        quota_key=body.quota_key,
        override_value=body.override_value,
        note=(body.note or "").strip() or None,
    )
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="quota_override",
        target_id=o.id,
        request=request,
        details={
            "institution_id": institution_id,
            "quota_key": body.quota_key,
            "override_value": body.override_value,
        },
    )
    label = (
        "sınırsız"
        if body.override_value == -1
        else "kapalı"
        if body.override_value == 0
        else str(body.override_value)
    )
    return MutationResponse[QuotaMutationResult](
        data=QuotaMutationResult(
            message=f"{inst.name} {body.quota_key} → {label}",
        ),
        invalidate=["admin:quota"],
    )


@router.post(
    "/quota/overrides/{override_id}/delete",
    response_model=MutationResponse[QuotaMutationResult],
)
def admin_quota_remove_override_v2(
    override_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Override sil — kurum plan default'una döner.

    Eşdeğer Jinja: admin.py:3040-3064 (super_admin_quota_remove_override).
    """
    from app.models import InstitutionQuotaOverride
    from app.services.quotas import remove_override

    o = db.get(InstitutionQuotaOverride, override_id)
    if not o:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "override_not_found",
                "message": "Override bulunamadı",
            },
        )
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="quota_override",
        target_id=override_id,
        request=request,
        details={
            "deleted": True,
            "institution_id": o.institution_id,
            "quota_key": o.quota_key,
        },
    )
    remove_override(db, override_id)
    return MutationResponse[QuotaMutationResult](
        data=QuotaMutationResult(
            message="Override silindi (plan default'a döndü)",
        ),
        invalidate=["admin:quota"],
    )


# =============================================================================
# P5 — Feature flags
# =============================================================================


@router.get("/feature-flags", response_model=FeatureFlagsListResponse)
def admin_feature_flags_list_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tüm feature flag'ler + override sayımı.

    Eşdeğer Jinja: admin.py:1633-1660 (feature_flags_list).
    """
    from app.services.feature_flags import all_flags_for_admin

    flags_data = all_flags_for_admin(db)
    return FeatureFlagsListResponse(
        flags=[
            FeatureFlagItem(
                id=fd["flag"].id,
                key=fd["flag"].key,
                description=fd["flag"].description,
                enabled_globally=fd["flag"].enabled_globally,
                override_enabled_count=fd["override_enabled_count"],
                override_disabled_count=fd["override_disabled_count"],
                override_total=fd["override_total"],
            )
            for fd in flags_data
        ],
    )


@router.get(
    "/feature-flags/{flag_id}", response_model=FeatureFlagDetailResponse,
)
def admin_feature_flag_detail_v2(
    flag_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tek flag detayı + override yönetimi.

    Eşdeğer Jinja: admin.py:1663-1698 (feature_flag_detail).
    """
    from app.models import FeatureFlag
    from app.services.feature_flags import get_overrides_for_flag

    flag = db.get(FeatureFlag, flag_id)
    if not flag:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "flag_not_found",
                "message": "Flag bulunamadı",
            },
        )
    overrides = get_overrides_for_flag(db, flag_id)
    institutions = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .order_by(Institution.name)
        .all()
    )
    overridden_ids = {o.institution_id for o in overrides}
    available = [i for i in institutions if i.id not in overridden_ids]
    return FeatureFlagDetailResponse(
        id=flag.id,
        key=flag.key,
        description=flag.description,
        enabled_globally=flag.enabled_globally,
        overrides=[
            FeatureFlagOverrideItem(
                id=o.id,
                institution_id=o.institution_id,
                institution_name=o.institution.name if o.institution else f"#{o.institution_id}",
                enabled=o.enabled,
                note=o.note,
            )
            for o in overrides
        ],
        available_institutions=[
            FeatureFlagInstitutionOption(id=i.id, name=i.name)
            for i in available
        ],
    )


@router.post(
    "/feature-flags/{flag_id}/toggle",
    response_model=MutationResponse[FeatureFlagMutationResult],
)
def admin_feature_flag_toggle_v2(
    flag_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Global enabled toggle.

    Eşdeğer Jinja: admin.py:1701-1731 (feature_flag_toggle_global).
    """
    from app.models import FeatureFlag
    from app.services.feature_flags import set_global

    flag = db.get(FeatureFlag, flag_id)
    if not flag:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "flag_not_found",
                "message": "Flag bulunamadı",
            },
        )
    new_state = not flag.enabled_globally
    set_global(db, flag.key, new_state)
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="feature_flag",
        target_id=flag.id,
        request=request,
        details={"key": flag.key, "enabled_globally": new_state},
    )
    msg = f"'{flag.key}' AÇILDI" if new_state else f"'{flag.key}' KAPATILDI"
    return MutationResponse[FeatureFlagMutationResult](
        data=FeatureFlagMutationResult(
            message=msg,
            enabled_globally=new_state,
        ),
        invalidate=["admin:feature-flags"],
    )


@router.post(
    "/feature-flags/{flag_id}/overrides",
    response_model=MutationResponse[FeatureFlagMutationResult],
)
def admin_feature_flag_add_override_v2(
    flag_id: int,
    body: FeatureFlagOverrideBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Bir kuruma override ekle/güncelle.

    Eşdeğer Jinja: admin.py:1734-1778 (feature_flag_add_override).
    """
    from app.models import FeatureFlag
    from app.services.feature_flags import set_override

    flag = db.get(FeatureFlag, flag_id)
    if not flag:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "flag_not_found",
                "message": "Flag bulunamadı",
            },
        )
    inst = db.get(Institution, body.institution_id)
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "institution_not_found",
                "message": "Kurum bulunamadı",
            },
        )
    o = set_override(
        db,
        flag_id=flag_id,
        institution_id=body.institution_id,
        enabled=body.enabled,
        note=(body.note or "").strip() or None,
    )
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="feature_flag_override",
        target_id=o.id,
        request=request,
        details={
            "flag_key": flag.key,
            "institution_id": body.institution_id,
            "enabled": body.enabled,
        },
    )
    return MutationResponse[FeatureFlagMutationResult](
        data=FeatureFlagMutationResult(
            message=(
                f"'{inst.name}' için override "
                f"{'AÇIK' if body.enabled else 'KAPALI'}"
            ),
        ),
        invalidate=["admin:feature-flags"],
    )


@router.post(
    "/feature-flags/overrides/{override_id}/delete",
    response_model=MutationResponse[FeatureFlagMutationResult],
)
def admin_feature_flag_remove_override_v2(
    override_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Override sil — kurum global ayara döner.

    Eşdeğer Jinja: admin.py:1781-1807 (feature_flag_remove_override).
    """
    from app.models import FeatureFlagOverride
    from app.services.feature_flags import remove_override

    o = db.get(FeatureFlagOverride, override_id)
    if not o:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "override_not_found",
                "message": "Override bulunamadı",
            },
        )
    flag_id = o.feature_flag_id
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="feature_flag_override",
        target_id=override_id,
        request=request,
        details={
            "deleted": True,
            "flag_id": flag_id,
            "institution_id": o.institution_id,
        },
    )
    remove_override(db, override_id)
    return MutationResponse[FeatureFlagMutationResult](
        data=FeatureFlagMutationResult(
            message="Override silindi (global ayara döndü)",
        ),
        invalidate=["admin:feature-flags"],
    )


# =============================================================================
# P6 — Feature Catalog (Vitrin Kartları)
#
# Jinja eşdeğeri: app/routes/admin.py:1847-2800 (17 endpoint).
# 8 destek servisi (feature_scoring / bandit / diversity / telemetry /
# landing_strategies / mockup_registry / feature_discovery / curator_dashboard)
# AYNEN çağrılır — Mamdani fuzzy / LinUCB / MMR / Wilson CI birebir korunur.
# =============================================================================


def _fc_invalidate() -> list[str]:
    """Feature-catalog mutation'larında bayatlanacak queryKey prefix'leri."""
    return [
        "admin:feature-catalog",
        "admin:feature-catalog:dashboard",
        "admin:feature-catalog:discovery",
        "admin:feature-catalog:experiments",
    ]


def _fc_parse_dt(value: str | None):
    """datetime-local / ISO string → UTC datetime. Jinja _parse_dt_local birebir."""
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        if "T" in v:
            dt = datetime.fromisoformat(v)
        else:
            dt = datetime.strptime(v, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fc_discovery_pending(db: Session) -> int:
    """kesif-* slug + DRAFT + reddedilmemiş aday sayısı (Jinja birebir)."""
    from app.models import FeatureCard, FeatureStatus
    return (
        db.query(FeatureCard)
        .filter(
            (FeatureCard.slug.like("kesif-mig-%") | FeatureCard.slug.like("kesif-c-%")),
            FeatureCard.status == FeatureStatus.DRAFT.value,
            FeatureCard.manual_hide.is_(False),
        )
        .count()
    )


def _fc_domain_options() -> list[EnumOption]:
    from app.models import FEATURE_DOMAIN_LABELS_TR, FeatureDomain
    return [
        EnumOption(value=d.value, label=FEATURE_DOMAIN_LABELS_TR[d])
        for d in FeatureDomain
    ]


def _fc_tier_options() -> list[EnumOption]:
    from app.models import FEATURE_TIER_LABELS_TR, FeatureTier
    return [
        EnumOption(value=t.value, label=FEATURE_TIER_LABELS_TR[t])
        for t in FeatureTier
    ]


def _fc_status_options() -> list[StatusOption]:
    from app.models import (
        FEATURE_STATUS_BADGES, FEATURE_STATUS_LABELS_TR, FeatureStatus,
    )
    return [
        StatusOption(
            value=s.value,
            label=FEATURE_STATUS_LABELS_TR[s],
            badge=FEATURE_STATUS_BADGES[s],
        )
        for s in FeatureStatus
    ]


def _fc_card_to_full(card) -> FeatureCardFull:
    return FeatureCardFull(
        id=card.id,
        slug=card.slug,
        title=card.title,
        tagline=card.tagline,
        description_md=card.description_md,
        icon=card.icon,
        accent_color=card.accent_color,
        category_icon=card.category_icon,
        category_label=card.category_label,
        demo_duration_label=card.demo_duration_label,
        mockup_type=card.mockup_type,
        target_roles=card.target_roles,
        benefits=card.benefits,
        pain_points=card.pain_points,
        demo_slug=card.demo_slug,
        domain=card.domain,
        tier=card.tier,
        status=card.status,
        introduced_at=card.introduced_at,
        introduced_in_commit=card.introduced_in_commit,
        pr_url=card.pr_url,
        strategic_priority=card.strategic_priority,
        manual_pin=card.manual_pin,
        pin_until=card.pin_until,
        manual_hide=card.manual_hide,
        cta_label=card.cta_label,
        cta_url=card.cta_url,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def _fc_form_meta() -> FeatureCardFormMeta:
    from app.models import UserRole as _UR
    from app.services.mockup_registry import list_mockups
    return FeatureCardFormMeta(
        domains=_fc_domain_options(),
        tiers=_fc_tier_options(),
        statuses=[EnumOption(value=o.value, label=o.label) for o in _fc_status_options()],
        roles=[r.value for r in _UR],
        mockups=[
            MockupOption(key=m.key, label=m.label, description=m.description)
            for m in list_mockups()
        ],
    )


# ---------------------------- Liste ----------------------------


@router.get("/feature-catalog", response_model=FeatureCatalogListResponse)
def admin_feature_catalog_list_v2(
    status_filter: str | None = Query(None),
    domain_filter: str | None = Query(None),
    tier_filter: str | None = Query(None),
    q: str | None = Query(None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Vitrin kartı listesi + 6 katmanlı zenginleştirme.

    Eşdeğer Jinja: admin.py:1847-1955 (feature_catalog_list).
    """
    from app.models import FeatureBanditState, FeatureStatus
    from app.services import bandit as bd
    from app.services import diversity as dv
    from app.services import feature_catalog as fc
    from app.services import telemetry as tel
    from app.services.feature_scoring import score_card

    cards = fc.list_for_admin(
        db,
        status_filter=status_filter,
        domain_filter=domain_filter,
        tier_filter=tier_filter,
        search=q,
    )
    counts = fc.count_by_status(db)
    discovery_pending = _fc_discovery_pending(db)

    # Katman 5 — fuzzy skor (yalnız landing adayı kartlar)
    scores: dict[int, object] = {}
    for c in cards:
        if (
            c.status == FeatureStatus.PUBLISHED.value
            and c.mockup_type
            and not c.manual_hide
        ):
            scores[c.id] = score_card(c, role=None)

    # Katman 6 — telemetri (bulk)
    card_ids = [c.id for c in cards]
    telemetry_stats = tel.get_bulk_stats(db, card_ids)

    # Katman 7 — bandit
    bandit_rows = (
        db.query(FeatureBanditState)
        .filter(FeatureBanditState.card_id.in_(card_ids))
        .all()
    ) if card_ids else []
    bandit_ctx = bd.extract_context(None)
    bandit_info: dict[int, dict] = {}
    for st in bandit_rows:
        mean, ucb = bd.score(st, bandit_ctx)
        bandit_info[st.card_id] = {"obs": st.reward_count or 0, "mean": mean}

    # Katman 8 — çeşitlilik (gerçek landing sıralaması)
    landing_cards = fc.get_for_landing(db)
    landing_ids = {c.id for c in landing_cards}
    neighbor_sim = dv.neighbor_similarity(landing_cards)
    overall_diversity = dv.diversity_score(landing_cards)
    learning_count = sum(1 for st in bandit_rows if (st.reward_count or 0) > 0)

    domain_opts = {o.value: o.label for o in _fc_domain_options()}
    tier_opts = {o.value: o.label for o in _fc_tier_options()}
    status_opts = {o.value: o for o in _fc_status_options()}

    items: list[FeatureCardListItem] = []
    for c in cards:
        sb = scores.get(c.id)
        ts = telemetry_stats.get(c.id) or {}
        bi = bandit_info.get(c.id)
        sopt = status_opts.get(c.status)
        item = FeatureCardListItem(
            id=c.id,
            slug=c.slug,
            title=c.title,
            tagline=c.tagline,
            accent_color=c.accent_color,
            domain=c.domain,
            domain_label=domain_opts.get(c.domain, c.domain),
            tier=c.tier,
            tier_label=tier_opts.get(c.tier, c.tier),
            status=c.status,
            status_label=sopt.label if sopt else c.status,
            status_badge=sopt.badge if sopt else "slate",
            strategic_priority=c.strategic_priority,
            manual_pin=c.manual_pin,
            manual_hide=c.manual_hide,
            demo_slug=c.demo_slug,
            is_landing=(c.id in landing_ids),
            impression=int(ts.get("impression", 0)),
            view=int(ts.get("view", 0)),
            demo_click=int(ts.get("demo_click", 0)),
            cta_click=int(ts.get("cta_click", 0)),
            bandit_obs=(bi["obs"] if bi else 0),
            bandit_mean=(bi["mean"] if bi else None),
            neighbor_sim=(neighbor_sim.get(c.id) if c.id in landing_ids else None),
        )
        if sb is not None:
            item.score = sb.prominence_int
            item.score_inputs = FeatureCardScoreInputs(
                freshness=sb.inputs["freshness"],
                priority=sb.inputs["priority"],
                tier_strength=sb.inputs["tier_strength"],
                completeness=sb.inputs["completeness"],
                role_match=sb.inputs["role_match"],
            )
            item.fired_rules = [
                FeatureCardFiredRule(label=lbl, strength=strn)
                for lbl, strn in sb.fired_rules[:3]
            ]
        items.append(item)

    return FeatureCatalogListResponse(
        cards=items,
        counts=counts,
        discovery_pending=discovery_pending,
        landing_card_count=len(landing_cards),
        overall_diversity=overall_diversity,
        learning_count=learning_count,
        domains=_fc_domain_options(),
        tiers=_fc_tier_options(),
        statuses=_fc_status_options(),
        status_filter=status_filter,
        domain_filter=domain_filter,
        tier_filter=tier_filter,
        q=q or "",
    )


# ---------------------------- Form meta / create ----------------------------


@router.get("/feature-catalog/new", response_model=FeatureCardFormResponse)
def admin_feature_catalog_new_form_v2(
    user: User = Depends(_require_super_admin),
):
    """Yeni kart formu meta (card=None). Jinja: admin.py:1958."""
    return FeatureCardFormResponse(card=None, meta=_fc_form_meta())


@router.post(
    "/feature-catalog",
    response_model=MutationResponse[FeatureCardMutationResult],
)
def admin_feature_catalog_create_v2(
    body: FeatureCardBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Yeni kart oluştur. Jinja: admin.py:1991-2073 (feature_catalog_create)."""
    from app.services import feature_catalog as fc

    try:
        card = fc.create(
            db,
            actor_id=user.id,
            slug=body.slug,
            title=body.title,
            tagline=body.tagline,
            description_md=body.description_md,
            icon=body.icon,
            accent_color=body.accent_color,
            category_icon=body.category_icon,
            category_label=body.category_label,
            demo_duration_label=body.demo_duration_label,
            mockup_type=(body.mockup_type or None),
            target_roles=body.target_roles,
            benefits=body.benefits,
            pain_points=body.pain_points,
            demo_slug=body.demo_slug,
            domain=body.domain,
            tier=body.tier,
            status=body.status,
            introduced_at=_fc_parse_dt(body.introduced_at),
            introduced_in_commit=body.introduced_in_commit,
            pr_url=body.pr_url,
            strategic_priority=body.strategic_priority,
            manual_pin=body.manual_pin,
            pin_until=_fc_parse_dt(body.pin_until),
            manual_hide=body.manual_hide,
            cta_label=body.cta_label,
            cta_url=body.cta_url,
        )
    except fc.FeatureCatalogError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "feature_card_invalid", "message": str(e)},
        )
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_CREATE,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug, "status": card.status},
    )
    return MutationResponse[FeatureCardMutationResult](
        data=FeatureCardMutationResult(
            message=f"'{card.slug}' oluşturuldu",
            card_id=card.id,
            slug=card.slug,
        ),
        invalidate=_fc_invalidate(),
    )


# ---------------------------- Onay kuyruğu ----------------------------


@router.get(
    "/feature-catalog/discovery-queue",
    response_model=DiscoveryQueueResponse,
)
def admin_feature_catalog_discovery_queue_v2(
    source: str | None = Query(None),
    show_rejected: int = Query(0),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Otomatik keşif onay kuyruğu. Jinja: admin.py:2094-2174."""
    from app.models import AuditAction as _AA, AuditLog as _AL, FeatureCard, FeatureStatus

    query = (
        db.query(FeatureCard)
        .filter(
            (FeatureCard.slug.like("kesif-mig-%") | FeatureCard.slug.like("kesif-c-%")),
            FeatureCard.status == FeatureStatus.DRAFT.value,
        )
    )
    if not show_rejected:
        query = query.filter(FeatureCard.manual_hide.is_(False))
    if source == "migration":
        query = query.filter(FeatureCard.slug.like("kesif-mig-%"))
    elif source == "commit":
        query = query.filter(FeatureCard.slug.like("kesif-c-%"))

    cards = query.order_by(FeatureCard.introduced_at.desc()).all()

    # Discovery audit detayı (source_ref + raw_subject)
    card_ids = [c.id for c in cards]
    audit_by_card: dict[int, dict] = {}
    if card_ids:
        rows = (
            db.query(_AL)
            .filter(
                _AL.action == _AA.FEATURE_CARD_AUTO_DISCOVERED,
                _AL.target_id.in_(card_ids),
                _AL.target_type == "feature_card",
            )
            .all()
        )
        for r in rows:
            if not r.details_json:
                continue
            try:
                d = json.loads(r.details_json)
                if isinstance(d, dict):
                    audit_by_card[r.target_id] = d
            except (json.JSONDecodeError, TypeError):
                pass

    total_pending = _fc_discovery_pending(db)
    mig_pending = (
        db.query(FeatureCard)
        .filter(
            FeatureCard.slug.like("kesif-mig-%"),
            FeatureCard.status == FeatureStatus.DRAFT.value,
            FeatureCard.manual_hide.is_(False),
        )
        .count()
    )
    com_pending = total_pending - mig_pending

    items: list[DiscoveryCardItem] = []
    for c in cards:
        d = audit_by_card.get(c.id) or {}
        items.append(DiscoveryCardItem(
            id=c.id,
            slug=c.slug,
            title=c.title,
            tagline=c.tagline,
            introduced_at=c.introduced_at,
            introduced_in_commit=c.introduced_in_commit,
            manual_hide=c.manual_hide,
            is_migration=c.slug.startswith("kesif-mig-"),
            source_ref=d.get("source_ref"),
            raw_subject=d.get("raw_subject"),
        ))

    return DiscoveryQueueResponse(
        cards=items,
        counts={"total": total_pending, "migration": mig_pending, "commit": com_pending},
        source=source or "",
        show_rejected=bool(show_rejected),
    )


@router.post(
    "/feature-catalog/discovery-queue/bulk",
    response_model=MutationResponse[DiscoveryMutationResult],
)
def admin_feature_catalog_discovery_bulk_v2(
    body: DiscoveryBulkBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Toplu reddet/sil — sadece kesif-* DRAFT. Jinja: admin.py:2208-2293."""
    from app.models import FeatureCard, FeatureStatus
    from app.services import feature_catalog as fc

    if not body.ids:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "no_ids", "message": "Aday seçilmedi"},
        )
    cards = (
        db.query(FeatureCard)
        .filter(
            FeatureCard.id.in_(body.ids),
            (FeatureCard.slug.like("kesif-mig-%") | FeatureCard.slug.like("kesif-c-%")),
            FeatureCard.status == FeatureStatus.DRAFT.value,
        )
        .all()
    )
    affected = 0
    for card in cards:
        if body.action == "reject":
            if card.manual_hide:
                continue
            card.manual_hide = True
            log_action(
                db,
                action=AuditAction.FEATURE_CARD_DISCOVERY_REJECTED,
                actor_id=user.id,
                target_type="feature_card",
                target_id=card.id,
                request=request,
                details={"slug": card.slug, "bulk": True},
                autocommit=False,
            )
            affected += 1
        else:  # delete
            log_action(
                db,
                action=AuditAction.FEATURE_CARD_DELETE,
                actor_id=user.id,
                target_type="feature_card",
                target_id=card.id,
                request=request,
                details={"slug": card.slug, "bulk": True, "via": "discovery_queue"},
                autocommit=False,
            )
            fc.delete(db, card)
            affected += 1
    db.commit()
    verb = "reddedildi" if body.action == "reject" else "silindi"
    return MutationResponse[DiscoveryMutationResult](
        data=DiscoveryMutationResult(message=f"{affected} aday {verb}", affected=affected),
        invalidate=_fc_invalidate(),
    )


# ---------------------------- Dashboard ----------------------------


@router.get(
    "/feature-catalog/dashboard",
    response_model=FeatureCatalogDashboardResponse,
)
def admin_feature_catalog_dashboard_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Vitrin yönetim paneli (curator_dashboard). Jinja: admin.py:2299-2316."""
    from app.services.curator_dashboard import get_dashboard_data, humanize_ago

    data = get_dashboard_data(db)
    s = data["summary"]
    lh = data["landing_health"]
    w = data["last_7d"]

    exp = data.get("experiment")
    exp_model = None
    if exp is not None:
        exp_model = DashboardExperiment(
            id=exp["id"],
            name=exp["name"],
            slug=exp["slug"],
            started_days_ago=exp["started_days_ago"],
            total_impressions=exp["total_impressions"],
            has_significance=exp["has_significance"],
            variants=[
                DashboardExperimentVariant(
                    slug=vslug,
                    label=info["label"],
                    is_control=info["is_control"],
                    ctr=info["ctr"],
                    total_clicks=info["total_clicks"],
                    impression=info["impression"],
                    lift_pct=info.get("lift_pct"),
                    vs_control_significant=info.get("vs_control_significant", False),
                )
                for vslug, info in exp["variants"].items()
            ],
        )

    return FeatureCatalogDashboardResponse(
        summary=DashboardSummary(**s),
        landing_health=DashboardLandingHealth(**lh),
        last_7d=DashboardWindowMetrics(**w),
        experiment=exp_model,
        anomalies=[DashboardAnomaly(**a) for a in data["anomalies"]],
        recent_audit=[
            DashboardAuditItem(
                action=r["action"],
                action_label=r["action_label"],
                target_id=r.get("target_id"),
                target_slug=r.get("target_slug"),
                actor_id=r.get("actor_id"),
                when=r.get("when"),
                ago_seconds=r["ago_seconds"],
                ago_label=humanize_ago(r["ago_seconds"]),
            )
            for r in data["recent_audit"]
        ],
        window_days=data["window_days"],
        generated_at=data["generated_at"],
    )


# ---------------------------- A/B deneyler ----------------------------


def _exp_variant_briefs(exp) -> list[ExperimentVariantBrief]:
    return [
        ExperimentVariantBrief(
            slug=str(v.get("slug", "")),
            label=str(v.get("label", v.get("slug", ""))),
            strategy=str(v.get("strategy", "")),
            weight=int(v.get("weight", 0)),
            is_control=bool(v.get("is_control", False)),
        )
        for v in (exp.variants or [])
    ]


@router.get(
    "/feature-catalog/experiments",
    response_model=ExperimentListResponse,
)
def admin_feature_catalog_experiments_list_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Deney listesi. Jinja: admin.py:2323-2355."""
    from app.models import (
        EXPERIMENT_STATUS_BADGES, EXPERIMENT_STATUS_LABELS_TR, FeatureExperiment,
    )

    rows = (
        db.query(FeatureExperiment)
        .order_by(FeatureExperiment.created_at.desc())
        .all()
    )
    items = [
        ExperimentListItem(
            id=e.id,
            slug=e.slug,
            name=e.name,
            status=e.status,
            status_label=EXPERIMENT_STATUS_LABELS_TR.get(e.status_enum, e.status),
            status_badge=EXPERIMENT_STATUS_BADGES.get(e.status_enum, "slate"),
            hypothesis=e.hypothesis,
            start_at=e.start_at,
            variants=_exp_variant_briefs(e),
        )
        for e in rows
    ]
    return ExperimentListResponse(experiments=items)


@router.get(
    "/feature-catalog/experiments/new",
    response_model=ExperimentFormMeta,
)
def admin_feature_catalog_experiment_form_v2(
    user: User = Depends(_require_super_admin),
):
    """Yeni deney formu — strateji registry. Jinja: admin.py:2358-2381."""
    from app.services.landing_strategies import (
        REGISTRY, STRATEGY_DESCRIPTIONS_TR, STRATEGY_LABELS_TR,
    )
    return ExperimentFormMeta(
        strategies=[
            ExperimentStrategyOption(
                key=k,
                label=STRATEGY_LABELS_TR.get(k, k),
                description=STRATEGY_DESCRIPTIONS_TR.get(k, ""),
            )
            for k in REGISTRY.keys()
        ]
    )


@router.post(
    "/feature-catalog/experiments",
    response_model=MutationResponse[ExperimentMutationResult],
)
def admin_feature_catalog_experiment_create_v2(
    body: ExperimentCreateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Yeni deney oluştur (ctrl+test). Jinja: admin.py:2384-2465."""
    from app.models import ExperimentStatus, FeatureExperiment
    from app.services import experiments as exp_svc
    from app.services import feature_catalog as fc

    name = (body.name or "").strip()
    if not name:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "name_required", "message": "Ad zorunlu"},
        )
    if body.weight_ctrl + body.weight_test != 100 or min(body.weight_ctrl, body.weight_test) < 1:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "weights_invalid",
                "message": "Ağırlıklar toplamı 100 olmalı (her biri 1-99 arası)",
            },
        )
    slug = fc.slugify(body.slug or name)
    if not slug:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "slug_invalid", "message": "Slug üretilemedi"},
        )
    if db.query(FeatureExperiment).filter(FeatureExperiment.slug == slug).first():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict", "code": "slug_taken",
                "message": f"'{slug}' slug zaten kullanımda",
            },
        )
    now = exp_svc.now_utc()
    new_exp = FeatureExperiment(
        slug=slug,
        name=name[:160],
        status=ExperimentStatus.DRAFT.value,
        hypothesis=(body.hypothesis.strip()[:2000] if body.hypothesis.strip() else None),
        created_at=now,
        updated_at=now,
        created_by=user.id,
    )
    new_exp.variants = [
        {"slug": "ctrl", "label": "Kontrol", "strategy": body.ctrl_strategy,
         "weight": body.weight_ctrl, "is_control": True},
        {"slug": "test", "label": "Test", "strategy": body.test_strategy,
         "weight": body.weight_test, "is_control": False},
    ]
    db.add(new_exp)
    db.commit()
    db.refresh(new_exp)
    return MutationResponse[ExperimentMutationResult](
        data=ExperimentMutationResult(
            message="Deney oluşturuldu", experiment_id=new_exp.id, slug=new_exp.slug,
        ),
        invalidate=_fc_invalidate(),
    )


@router.get(
    "/feature-catalog/experiments/{exp_id}",
    response_model=ExperimentDetailResponse,
)
def admin_feature_catalog_experiment_detail_v2(
    exp_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Deney detay + Wilson CI istatistik. Jinja: admin.py:2468-2509."""
    from app.models import (
        EXPERIMENT_STATUS_BADGES, EXPERIMENT_STATUS_LABELS_TR, FeatureExperiment,
    )
    from app.services import experiments as exp_svc
    from app.services.landing_strategies import STRATEGY_LABELS_TR

    exp = db.get(FeatureExperiment, exp_id)
    if exp is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "experiment_not_found", "message": "Deney bulunamadı"},
        )
    stats = exp_svc.compute_stats(db, experiment_id=exp.id)
    stat_items: list[ExperimentVariantStat] = []
    has_any_data = False
    for slug, info in stats.items():
        if info["impression"] > 0:
            has_any_data = True
        stat_items.append(ExperimentVariantStat(
            slug=slug,
            label=info["label"],
            strategy=info["strategy"],
            strategy_label=STRATEGY_LABELS_TR.get(info["strategy"], info["strategy"]),
            weight=info["weight"],
            is_control=info["is_control"],
            impression=info["impression"],
            view=info["view"],
            demo_click=info["demo_click"],
            cta_click=info["cta_click"],
            total_clicks=info["total_clicks"],
            ctr=info["ctr"],
            ctr_low=info["ctr_low"],
            ctr_high=info["ctr_high"],
            lift_pct=info.get("lift_pct"),
            vs_control_significant=info.get("vs_control_significant", False),
        ))

    detail = ExperimentDetail(
        id=exp.id,
        slug=exp.slug,
        name=exp.name,
        status=exp.status,
        status_label=EXPERIMENT_STATUS_LABELS_TR.get(exp.status_enum, exp.status),
        status_badge=EXPERIMENT_STATUS_BADGES.get(exp.status_enum, "slate"),
        hypothesis=exp.hypothesis,
        start_at=exp.start_at,
        end_at=exp.end_at,
        variants=_exp_variant_briefs(exp),
    )
    return ExperimentDetailResponse(
        experiment=detail, stats=stat_items, has_any_data=has_any_data,
    )


@router.post(
    "/feature-catalog/experiments/{exp_id}/status",
    response_model=MutationResponse[ExperimentMutationResult],
)
def admin_feature_catalog_experiment_status_v2(
    exp_id: int,
    body: ExperimentStatusBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Deney durumu — tek-RUNNING kuralı. Jinja: admin.py:2512-2562."""
    from app.models import ExperimentStatus, FeatureExperiment
    from app.services import experiments as exp_svc

    exp = db.get(FeatureExperiment, exp_id)
    if exp is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "experiment_not_found", "message": "Deney bulunamadı"},
        )
    new_status = (body.status or "").strip()
    if new_status not in {e.value for e in ExperimentStatus}:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invalid_status", "message": "Geçersiz durum"},
        )
    now = exp_svc.now_utc()
    if new_status == ExperimentStatus.RUNNING.value:
        for other in db.query(FeatureExperiment).filter(
            FeatureExperiment.status == ExperimentStatus.RUNNING.value,
            FeatureExperiment.id != exp.id,
        ).all():
            other.status = ExperimentStatus.PAUSED.value
            other.updated_at = now
        if exp.start_at is None:
            exp.start_at = now
    elif new_status == ExperimentStatus.COMPLETED.value:
        if exp.end_at is None:
            exp.end_at = now
    exp.status = new_status
    exp.updated_at = now
    db.commit()
    return MutationResponse[ExperimentMutationResult](
        data=ExperimentMutationResult(
            message=f"Durum '{new_status}' olarak güncellendi",
            experiment_id=exp.id, slug=exp.slug,
        ),
        invalidate=_fc_invalidate(),
    )


# ---------------------------- Kart detay / update / status / pin / delete ----------------------------


@router.get(
    "/feature-catalog/{card_id}",
    response_model=FeatureCardFormResponse,
)
def admin_feature_catalog_detail_v2(
    card_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kart düzenleme formu. Jinja: admin.py:2565-2603."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "card_not_found", "message": "Kart bulunamadı"},
        )
    return FeatureCardFormResponse(card=_fc_card_to_full(card), meta=_fc_form_meta())


@router.post(
    "/feature-catalog/{card_id}",
    response_model=MutationResponse[FeatureCardMutationResult],
)
def admin_feature_catalog_update_v2(
    card_id: int,
    body: FeatureCardBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kartı güncelle. Jinja: admin.py:2606-2693."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "card_not_found", "message": "Kart bulunamadı"},
        )
    try:
        fc.update(
            db, card,
            actor_id=user.id,
            slug=body.slug,
            title=body.title,
            tagline=body.tagline,
            description_md=body.description_md,
            icon=body.icon,
            accent_color=body.accent_color,
            category_icon=body.category_icon,
            category_label=body.category_label,
            demo_duration_label=body.demo_duration_label,
            mockup_type=(body.mockup_type or None),
            target_roles=body.target_roles,
            benefits=body.benefits,
            pain_points=body.pain_points,
            demo_slug=body.demo_slug,
            domain=body.domain,
            tier=body.tier,
            status=body.status,
            introduced_at=_fc_parse_dt(body.introduced_at),
            introduced_in_commit=body.introduced_in_commit,
            pr_url=body.pr_url,
            strategic_priority=body.strategic_priority,
            manual_pin=body.manual_pin,
            pin_until=_fc_parse_dt(body.pin_until),
            manual_hide=body.manual_hide,
            cta_label=body.cta_label,
            cta_url=body.cta_url,
        )
    except fc.FeatureCatalogError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "feature_card_invalid", "message": str(e)},
        )
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_UPDATE,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug, "status": card.status},
    )
    return MutationResponse[FeatureCardMutationResult](
        data=FeatureCardMutationResult(
            message="Kayıt güncellendi", card_id=card.id, slug=card.slug,
        ),
        invalidate=_fc_invalidate(),
    )


@router.post(
    "/feature-catalog/{card_id}/status",
    response_model=MutationResponse[FeatureCardMutationResult],
)
def admin_feature_catalog_status_v2(
    card_id: int,
    body: FeatureCardStatusBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kart durumu değiştir. Jinja: admin.py:2696-2732."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "card_not_found", "message": "Kart bulunamadı"},
        )
    old_status = card.status
    try:
        fc.set_status(db, card, body.status, actor_id=user.id)
    except fc.FeatureCatalogError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "feature_card_invalid", "message": str(e)},
        )
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_STATUS_CHANGE,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug, "from": old_status, "to": card.status},
    )
    return MutationResponse[FeatureCardMutationResult](
        data=FeatureCardMutationResult(
            message=f"'{card.slug}' durumu: {card.status}", card_id=card.id, slug=card.slug,
        ),
        invalidate=_fc_invalidate(),
    )


@router.post(
    "/feature-catalog/{card_id}/pin",
    response_model=MutationResponse[FeatureCardMutationResult],
)
def admin_feature_catalog_pin_v2(
    card_id: int,
    body: FeatureCardPinBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Pin toggle. Jinja: admin.py:2735-2770."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "card_not_found", "message": "Kart bulunamadı"},
        )
    fc.set_pin(
        db, card,
        pinned=body.pinned,
        until=_fc_parse_dt(body.pin_until),
        actor_id=user.id,
    )
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_PIN,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug, "pinned": body.pinned},
    )
    msg = "sabitlendi" if body.pinned else "serbest bırakıldı"
    return MutationResponse[FeatureCardMutationResult](
        data=FeatureCardMutationResult(message=f"Kart {msg}", card_id=card.id, slug=card.slug),
        invalidate=_fc_invalidate(),
    )


@router.post(
    "/feature-catalog/{card_id}/reject",
    response_model=MutationResponse[DiscoveryMutationResult],
)
def admin_feature_catalog_reject_v2(
    card_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Discovery adayını reddet (manual_hide=True). Jinja: admin.py:2177-2205."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "card_not_found", "message": "Kart bulunamadı"},
        )
    card.manual_hide = True
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_DISCOVERY_REJECTED,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug},
    )
    db.commit()
    return MutationResponse[DiscoveryMutationResult](
        data=DiscoveryMutationResult(message=f"'{card.slug}' reddedildi", affected=1),
        invalidate=_fc_invalidate(),
    )


@router.post(
    "/feature-catalog/{card_id}/delete",
    response_model=MutationResponse[FeatureCardMutationResult],
)
def admin_feature_catalog_delete_v2(
    card_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kartı kalıcı sil. Jinja: admin.py:2773-2800."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "card_not_found", "message": "Kart bulunamadı"},
        )
    slug = card.slug
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_DELETE,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": slug},
        autocommit=False,
    )
    fc.delete(db, card)
    return MutationResponse[FeatureCardMutationResult](
        data=FeatureCardMutationResult(message=f"'{slug}' silindi", slug=slug),
        invalidate=_fc_invalidate(),
    )


# =============================================================================
# P7a — Ticari Pano: Analitik çekirdek (Aksiyon Merkezi / Tahmin / Kohort)
#
# Jinja eşdeğeri: admin.py /revenue/action-center (3456) · /revenue/forecast
# (3901) · /revenue/cohort (3940) · /revenue/action-center/quick-action (3981).
# 3 analitik servisi + institution_360.create_action AYNEN çağrılır.
# =============================================================================


def _revenue_invalidate() -> list[str]:
    return ["admin:revenue:action-center", "admin:revenue:forecast", "admin:revenue:cohort"]


def _action_signal_item(s) -> ActionSignalItem:
    return ActionSignalItem(
        kind=s.kind, severity=s.severity, score=s.score,
        title=s.title, description=s.description,
    )


@router.get("/revenue/action-center", response_model=ActionCenterResponse)
def admin_revenue_action_center_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Aksiyon Merkezi — "Bugün ne yapmalıyım?". Jinja: admin.py:3456-3472."""
    from app.services.action_center import action_center_data

    data = action_center_data(db)
    items = [
        ActionCenterItem(
            institution_id=it.institution_id,
            institution_name=it.institution_name,
            plan=it.plan,
            plan_label=it.plan_label,
            monthly_price_try=it.monthly_price_try,
            total_score=it.total_score,
            severity=it.severity,
            primary_signal=_action_signal_item(it.primary_signal),
            other_signals=[_action_signal_item(s) for s in it.other_signals],
            suggested_actions=[
                SuggestedActionItem(
                    kind=sa.kind, summary=sa.summary, label=sa.label,
                    icon=sa.icon, color=sa.color,
                )
                for sa in it.suggested_actions
            ],
            last_action_at=it.last_action_at,
            last_action_summary=it.last_action_summary,
        )
        for it in data["items"]
    ]
    return ActionCenterResponse(
        generated_at=data["generated_at"],
        items=items,
        total_count=data["total_count"],
        severity_counts=data["severity_counts"],
    )


@router.post(
    "/revenue/action-center/quick-action",
    response_model=MutationResponse[RevenueMutationResult],
)
def admin_revenue_quick_action_v2(
    body: QuickActionBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Önerilen aksiyon → hızlı CrmAction. Jinja: admin.py:3981-4021."""
    from app.services.institution_360 import create_action

    follow_dt = None
    if body.follow_up_days and body.follow_up_days > 0:
        follow_dt = datetime.now(timezone.utc) + timedelta(days=int(body.follow_up_days))
    action = create_action(
        db,
        institution_id=body.institution_id,
        kind=body.kind,
        summary=(body.summary or "").strip(),
        by_user_id=user.id,
        result=body.result,
        follow_up_at=follow_dt,
    )
    if action is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invalid_action_kind", "message": "Geçersiz aksiyon tipi"},
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_action",
        target_id=action.id,
        request=request,
        details={"action": "quick_create", "kind": body.kind, "institution_id": body.institution_id},
    )
    return MutationResponse[RevenueMutationResult](
        data=RevenueMutationResult(message="Aksiyon eklendi"),
        invalidate=_revenue_invalidate(),
    )


def _at_risk_item(x) -> AtRiskInstitutionItem:
    return AtRiskInstitutionItem(
        institution_id=x.institution_id,
        name=x.name,
        plan=x.plan,
        monthly_price_try=x.monthly_price_try,
        health_score=x.health_score,
        severity=x.severity,
        owner_type=x.owner_type,
        detail_url=x.detail_url,
    )


def _risk_at_mrr_model(d: dict) -> RiskAtMrr:
    return RiskAtMrr(
        total_at_risk_mrr=d["total_at_risk_mrr"],
        critical_mrr=d["critical_mrr"],
        risk_mrr=d["risk_mrr"],
        critical_count=d["critical_count"],
        risk_count=d["risk_count"],
        institutions=[_at_risk_item(x) for x in d["institutions"]],
    )


@router.get("/revenue/forecast", response_model=RevenueForecastResponse)
def admin_revenue_forecast_v2(
    save_rate: float = Query(0.5),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """MRR tahmin + senaryo. Jinja: admin.py:3901-3937."""
    from app.services.revenue_forecast import (
        mrr_projection,
        risk_at_mrr,
        scenario_comparison,
    )

    save_rate = max(0.0, min(1.0, float(save_rate)))
    risk = risk_at_mrr(db)
    proj_30 = mrr_projection(db, horizon_days=30, intervention_save_rate=save_rate)
    proj_60 = mrr_projection(db, horizon_days=60, intervention_save_rate=save_rate)
    proj_90 = mrr_projection(db, horizon_days=90, intervention_save_rate=save_rate)
    scenario = scenario_comparison(db, save_rate=save_rate)
    return RevenueForecastResponse(
        risk=_risk_at_mrr_model(risk),
        proj_30=MrrProjection(**proj_30),
        proj_60=MrrProjection(**proj_60),
        proj_90=MrrProjection(**proj_90),
        scenario=ScenarioComparison(
            current_mrr=scenario["current_mrr"],
            save_rate=scenario["save_rate"],
            horizons=[ScenarioHorizon(**h) for h in scenario["horizons"]],
        ),
        save_rate=save_rate,
        save_rate_pct=int(save_rate * 100),
    )


@router.get("/revenue/cohort", response_model=RevenueCohortResponse)
def admin_revenue_cohort_v2(
    months_back: int = Query(12),
    horizon: int = Query(12),
    churn_days: int = Query(90),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kohort tutunma + plan hareketi + LTV. Jinja: admin.py:3940-3978."""
    from app.services.revenue_cohort import (
        ltv_estimate,
        plan_churn_summary,
        signup_cohort_matrix,
    )

    months_back = max(3, min(24, int(months_back)))
    horizon = max(3, min(24, int(horizon)))
    churn_days = max(7, min(365, int(churn_days)))
    matrix = signup_cohort_matrix(db, months_back=months_back, horizon_months=horizon)
    churn = plan_churn_summary(db, days=churn_days)
    ltv = ltv_estimate(db)

    matrix_model = CohortMatrix(
        cohorts=[
            CohortRow(
                cohort_key=c["cohort_key"],
                cohort_label=c["cohort_label"],
                signup_count=c["signup_count"],
                signup_month_age=c["signup_month_age"],
                retention=[CohortRetentionCell(**cell) for cell in c["retention"]],
            )
            for c in matrix["cohorts"]
        ],
        horizon_months=matrix["horizon_months"],
        months_back=matrix["months_back"],
        total_signups=matrix["total_signups"],
    )
    ltv_model = LtvEstimate(
        plans=[
            PlanLtvItem(
                plan=p.plan, label=p.label, monthly_price_try=p.monthly_price_try,
                active_count=p.active_count, avg_age_months=p.avg_age_months,
                estimated_ltv_try=p.estimated_ltv_try,
            )
            for p in ltv["plans"]
        ],
        total_ltv_try=ltv["total_ltv_try"],
        paying_count=ltv["paying_count"],
        avg_ltv_per_paying=ltv["avg_ltv_per_paying"],
    )
    return RevenueCohortResponse(
        matrix=matrix_model,
        churn=PlanChurnSummary(**churn),
        ltv=ltv_model,
        months_back=months_back,
        horizon=horizon,
        churn_days=churn_days,
    )


# =============================================================================
# P7b — Ticari Pano: 360 görünümler + CRM (Owner-pattern)
#
# Jinja eşdeğeri: admin.py /revenue/institutions/{id} (4217) + /revenue/users/
# {id} (3475) + CRM notes/actions + contact + tags. institution_360 /
# revenue_owner / owner_contact / owner_tags / health_score_v2 AYNEN çağrılır.
# =============================================================================


def _rev360_invalidate(owner_type: str, owner_id: int) -> list[str]:
    """360 mutation'larında bayatlanacak prefix'ler."""
    seg = "institutions" if owner_type == "institution" else "users"
    return [f"admin:revenue:360:{seg}:{owner_id}", "admin:revenue:action-center"]


def _crm_meta() -> CrmMeta:
    from app.models import (
        CRM_ACTION_KIND_LABELS_TR, CRM_ACTION_RESULT_COLORS,
        CRM_ACTION_RESULT_LABELS_TR, CrmActionKind, CrmActionResult,
        OFFER_KIND_LABELS_TR, OfferKind,
        OWNER_TAG_COLORS, OWNER_TAG_DESCRIPTIONS, OWNER_TAG_ICONS,
        OWNER_TAG_LABELS_TR, OwnerTagKind,
    )
    return CrmMeta(
        action_kinds=[
            CrmEnumOption(value=k.value, label=CRM_ACTION_KIND_LABELS_TR[k])
            for k in CrmActionKind
        ],
        action_results=[
            CrmEnumOption(
                value=r.value, label=CRM_ACTION_RESULT_LABELS_TR[r],
                color=CRM_ACTION_RESULT_COLORS[r],
            )
            for r in CrmActionResult
        ],
        tag_kinds=[
            OwnerTagOption(
                value=k.value, label=OWNER_TAG_LABELS_TR[k],
                color=OWNER_TAG_COLORS[k], icon=OWNER_TAG_ICONS[k],
                description=OWNER_TAG_DESCRIPTIONS[k],
            )
            for k in OwnerTagKind
        ],
        offer_kinds=[
            EnumOption(value=k.value, label=OFFER_KIND_LABELS_TR[k])
            for k in OfferKind
        ],
    )


def _offer_item(o) -> OfferItem:
    from app.models import OFFER_KIND_LABELS_TR, OFFER_STATUS_COLORS, OFFER_STATUS_LABELS_TR
    from app.services.offers import describe_offer
    summary = describe_offer(o)
    return OfferItem(
        id=o.id,
        kind=o.kind.value,
        kind_label=OFFER_KIND_LABELS_TR.get(o.kind, o.kind.value),
        title=o.title,
        value=float(o.value) if o.value is not None else None,
        value_unit=o.value_unit,
        duration_months=o.duration_months,
        new_plan=o.new_plan,
        public_message=o.public_message,
        admin_note=o.admin_note,
        status=o.status.value,
        status_label=OFFER_STATUS_LABELS_TR.get(o.status, o.status.value),
        status_color=OFFER_STATUS_COLORS.get(o.status, "slate"),
        summary=summary["summary"],
        token=o.token,
        sent_at=o.sent_at,
        responded_at=o.responded_at,
        expires_at=o.expires_at,
        decline_reason=o.decline_reason,
        created_at=o.created_at,
    )


def _invoice_item(row: dict) -> InvoiceItem:
    """revenue_panel._invoice_row dict → InvoiceItem."""
    return InvoiceItem(
        invoice_id=row["invoice_id"],
        owner_type=row["owner_type"],
        owner_id=row.get("owner_id"),
        plan=row["plan"],
        plan_label=row["plan_label"],
        amount_try=row["amount_try"],
        status=row["status"],
        status_label=row["status_label"],
        due_at=row.get("due_at"),
        paid_at=row.get("paid_at"),
        days_until_due=row.get("days_until_due"),
        days_overdue=row.get("days_overdue", 0),
        payment_method=row.get("payment_method"),
        attempt_count=row.get("attempt_count", 0),
        last_reminder_kind=row.get("last_reminder_kind"),
        detail_url=row["detail_url"],
    )


def _crm_note_item(n) -> CrmNoteItem:
    return CrmNoteItem(
        id=n.id, content=n.content, pinned=n.pinned, created_at=n.created_at,
        created_by_name=(n.created_by.full_name if n.created_by else None),
    )


def _crm_action_item(a) -> CrmActionItem:
    from app.models import (
        CRM_ACTION_KIND_LABELS_TR, CRM_ACTION_RESULT_COLORS,
        CRM_ACTION_RESULT_LABELS_TR,
    )
    return CrmActionItem(
        id=a.id,
        kind=a.kind.value,
        kind_label=CRM_ACTION_KIND_LABELS_TR.get(a.kind, a.kind.value),
        summary=a.summary,
        notes=a.notes,
        result=a.result.value,
        result_label=CRM_ACTION_RESULT_LABELS_TR.get(a.result, a.result.value),
        result_color=CRM_ACTION_RESULT_COLORS.get(a.result, "slate"),
        follow_up_at=a.follow_up_at,
        completed_at=a.completed_at,
        created_at=a.created_at,
        created_by_name=(a.created_by.full_name if a.created_by else None),
    )


def _owner_tag_item(t) -> OwnerTagItem:
    from app.models import (
        OWNER_TAG_COLORS, OWNER_TAG_DESCRIPTIONS, OWNER_TAG_ICONS,
        OWNER_TAG_LABELS_TR,
    )
    return OwnerTagItem(
        id=t.id, kind=t.kind.value,
        label=OWNER_TAG_LABELS_TR.get(t.kind, t.kind.value),
        color=OWNER_TAG_COLORS.get(t.kind, "slate"),
        icon=OWNER_TAG_ICONS.get(t.kind, ""),
        description=OWNER_TAG_DESCRIPTIONS.get(t.kind, ""),
        note=t.note,
    )


def _owner_contact_data(c) -> OwnerContactData | None:
    if c is None:
        return None
    return OwnerContactData(
        responsible_person_name=c.responsible_person_name,
        responsible_person_title=c.responsible_person_title,
        billing_email=c.billing_email,
        phone=c.phone,
        whatsapp=c.whatsapp,
        linkedin_url=c.linkedin_url,
        website=c.website,
        address=c.address,
        note=c.note,
        updated_at=c.updated_at,
    )


def _plan_change_item(pc) -> PlanChangeItem:
    reason = pc.reason.value if hasattr(pc.reason, "value") else str(pc.reason)
    return PlanChangeItem(
        id=pc.id, from_plan=pc.from_plan, to_plan=pc.to_plan,
        reason=reason, occurred_at=pc.occurred_at,
    )


def _health_v2_data(h) -> HealthScoreV2Data | None:
    if h is None:
        return None
    return HealthScoreV2Data(
        score=h.score, band=h.band, band_label=h.band_label,
        band_color=h.band_color, band_emoji=h.band_emoji,
        components=[
            HealthComponentItem(
                code=c.code, label=c.label, weight_pct=c.weight_pct,
                value_pct=c.value_pct, contribution=c.contribution, note=c.note,
            )
            for c in h.components
        ],
        active_teacher_count=h.active_teacher_count,
        active_student_count=h.active_student_count,
    )


def _health_history_points(hist) -> list[HealthHistoryPoint]:
    out: list[HealthHistoryPoint] = []
    for s in hist:
        d = s.snapshot_date
        out.append(HealthHistoryPoint(
            snapshot_date=d.isoformat() if hasattr(d, "isoformat") else str(d),
            score=s.score,
            band=s.band,
        ))
    return out


def _crm_owner_kwargs(owner_type: str, owner_id: int) -> dict:
    """owner_type → institution_id/user_id kwargs (institution_360 CRM için)."""
    if owner_type == "institution":
        return {"institution_id": owner_id}
    return {"user_id": owner_id}


# ---------------------------- GET: Kurum 360 ----------------------------


@router.get(
    "/revenue/institutions/{institution_id}",
    response_model=InstitutionRevenue360Response,
)
def admin_revenue_institution_360_v2(
    institution_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kurum 360. Jinja: admin.py:4217-4326."""
    from app.models import Institution as _Inst, PlanChangeHistory as _PCH
    from app.models.plan_history import PlanOwnerType as _POT
    from app.services.health_score_v2 import (
        compute_health_score_v2, detect_warning_triggers, get_score_history,
    )
    from app.services.institution_360 import get_institution_360
    from app.services.owner_contact import get_contact
    from app.services.owner_tags import list_tags_for

    data = get_institution_360(db, institution_id=institution_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "institution_not_found", "message": "Kurum bulunamadı"},
        )
    inst_obj = db.get(_Inst, institution_id)
    try:
        health_v2 = compute_health_score_v2(db, institution=inst_obj)
        triggers = detect_warning_triggers(db, institution=inst_obj)
        history = get_score_history(db, institution_id=institution_id, days=14)
    except Exception:
        health_v2, triggers, history = None, [], []

    owner_tags = list_tags_for(db, owner_type="institution", owner_id=institution_id)
    owner_contact = get_contact(db, owner_type="institution", owner_id=institution_id)
    plan_changes = (
        db.query(_PCH)
        .filter(_PCH.owner_type == _POT.INSTITUTION, _PCH.owner_id == institution_id)
        .order_by(_PCH.occurred_at.desc())
        .limit(30)
        .all()
    )

    from app.services.offers import list_offers_for_owner
    from app.services.revenue_panel import invoices_for_owner
    offers = list_offers_for_owner(db, institution_id=institution_id, limit=50)
    invoices = invoices_for_owner(db, institution_id=institution_id, limit=100)

    ident = data["identity"]
    return InstitutionRevenue360Response(
        identity=Institution360Identity(
            id=ident["id"], name=ident["name"], slug=ident["slug"],
            contact_email=ident["contact_email"], is_active=ident["is_active"],
            plan=ident["plan"], plan_label=ident["plan_label"],
            plan_monthly_price_try=ident["plan_monthly_price_try"],
            trial_ends_at=ident["trial_ends_at"], post_trial_plan=ident["post_trial_plan"],
            subscription_kind=ident["subscription_kind"],
            subscription_period_end=ident["subscription_period_end"],
            subscription_pause_until=ident["subscription_pause_until"],
            performance_guarantee=bool(ident["performance_guarantee"]),
            created_at=ident["created_at"],
            admins=[Institution360Admin(**a) for a in ident["admins"]],
        ),
        health=Institution360Health(**data["health"]),
        usage_30d=Institution360Usage(**data["usage_30d"]),
        billing=Institution360Billing(**data["billing"]),
        risks=[Risk360Item(**r) for r in data["risks"]],
        crm_notes=[_crm_note_item(n) for n in data["crm_notes"]],
        crm_actions=[_crm_action_item(a) for a in data["crm_actions"]],
        health_v2=_health_v2_data(health_v2),
        health_triggers=[
            HealthTriggerItem(code=t.code, title=t.title, detail=t.detail, severity=t.severity)
            for t in triggers
        ],
        health_history=_health_history_points(history),
        owner_tags=[_owner_tag_item(t) for t in owner_tags],
        owner_contact=_owner_contact_data(owner_contact),
        plan_changes=[_plan_change_item(pc) for pc in plan_changes],
        offers=[_offer_item(o) for o in offers],
        invoices=[_invoice_item(r) for r in invoices],
        meta=_crm_meta(),
    )


# ---------------------------- GET: Bağımsız öğretmen 360 ----------------------------


@router.get(
    "/revenue/users/{user_id}",
    response_model=UserRevenue360Response,
)
def admin_revenue_user_360_v2(
    user_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Bağımsız öğretmen 360. Jinja: admin.py:3475-3697."""
    from app.models import (
        PlanChangeHistory as _PCH, Task as _Task, TaskBookItem as _TBI,
        User as _User, UserRole as _UserRole,
    )
    from app.models.plan_history import PlanOwnerType as _POT
    from app.services.health_score_v2 import (
        compute_health_score_v2_for_user, get_score_history,
    )
    from app.services.institution_360 import crm_actions_for, crm_notes_for
    from app.services.owner_contact import get_contact
    from app.services.owner_tags import list_tags_for
    from app.services.revenue_owner import get_owner

    owner = get_owner(db, owner_type="user", owner_id=user_id)
    if owner is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "teacher_not_found", "message": "Bağımsız öğretmen bulunamadı"},
        )
    u = db.get(_User, user_id)
    now_utc = datetime.now(timezone.utc)

    all_students = (
        db.query(_User)
        .filter(_User.teacher_id == user_id, _User.role == _UserRole.STUDENT)
        .order_by(_User.full_name.asc())
        .all()
    )
    active_students = [s for s in all_students if s.is_active]
    student_count = len(active_students)

    student_health = {"healthy": 0, "watch": 0, "risk": 0, "critical": 0}
    student_rows: list[StudentRow] = []
    band_order = {"critical": 0, "risk": 1, "watch": 2, "healthy": 3}
    tmp_rows = []
    for s in all_students:
        last = s.last_login_at
        if last is None:
            band, days, label = "critical", None, "hiç giriş yok"
        else:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days = (now_utc - last).days
            band = ("critical" if days >= 30 else "risk" if days >= 14
                    else "watch" if days >= 7 else "healthy")
            label = f"{days}g önce" if days > 0 else "bugün"
        if s.is_active:
            student_health[band] += 1
        tmp_rows.append((s, band, days, label))
    tmp_rows.sort(key=lambda r: (
        0 if r[0].is_active else 1, band_order.get(r[1], 9), -(r[2] or 9999),
    ))
    for s, band, days, label in tmp_rows:
        student_rows.append(StudentRow(
            id=s.id, full_name=s.full_name, grade_level=s.grade_level,
            is_active=s.is_active, band=band, label=label,
        ))
    sh_counts = StudentHealthCounts(
        healthy=student_health["healthy"], watch=student_health["watch"],
        risk=student_health["risk"], critical=student_health["critical"],
        unhealthy_total=student_health["risk"] + student_health["critical"],
        total=student_count,
    )

    cutoff_30 = (now_utc - timedelta(days=30)).date()
    student_ids = [s.id for s in active_students]
    task_rows = (
        db.query(_Task.is_draft, _TBI.planned_count, _TBI.completed_count)
        .join(_TBI, _TBI.task_id == _Task.id)
        .filter(_Task.student_id.in_(student_ids), _Task.date >= cutoff_30)
        .all()
    ) if student_ids else []
    tasks_planned = sum(r[1] or 0 for r in task_rows if not r[0])
    tasks_completed = sum(r[2] or 0 for r in task_rows if not r[0])
    tasks_draft = sum(1 for r in task_rows if r[0])
    completion_pct = round(100 * tasks_completed / tasks_planned) if tasks_planned > 0 else 0

    teacher_last = u.last_login_at
    if teacher_last is None:
        teacher_band, teacher_label = "critical", "hiç giriş yok"
    else:
        if teacher_last.tzinfo is None:
            teacher_last = teacher_last.replace(tzinfo=timezone.utc)
        td = (now_utc - teacher_last).days
        teacher_band = ("critical" if td >= 30 else "risk" if td >= 14
                        else "watch" if td >= 7 else "healthy")
        teacher_label = f"{td}g önce" if td > 0 else "bugün"

    try:
        health_v2 = compute_health_score_v2_for_user(db, user_obj=u)
    except Exception:
        health_v2 = None
    try:
        score_history = get_score_history(db, user_id=user_id, days=14)
    except Exception:
        score_history = []

    crm_notes = crm_notes_for(db, user_id=user_id)
    crm_actions = crm_actions_for(db, user_id=user_id)
    owner_tags = list_tags_for(db, owner_type="user", owner_id=user_id)
    owner_contact = get_contact(db, owner_type="user", owner_id=user_id)
    plan_changes = (
        db.query(_PCH)
        .filter(_PCH.owner_type == _POT.USER, _PCH.owner_id == user_id)
        .order_by(_PCH.occurred_at.desc())
        .limit(20)
        .all()
    )

    from app.services.offers import list_offers_for_owner
    from app.services.revenue_panel import invoices_for_owner
    offers = list_offers_for_owner(db, user_id=user_id, limit=50)
    invoices = invoices_for_owner(db, user_id=user_id, limit=100)

    return UserRevenue360Response(
        owner=OwnerBrief(
            owner_type=owner.owner_type, owner_id=owner.owner_id, name=owner.name,
            email=owner.email, plan=owner.plan, is_active=owner.is_active,
            monthly_price_try=owner.monthly_price_try, trial_ends_at=owner.trial_ends_at,
        ),
        teacher_band=teacher_band,
        teacher_login_label=teacher_label,
        student_count=student_count,
        all_students_total=len(all_students),
        student_health=sh_counts,
        student_rows=student_rows,
        tasks_planned_30d=tasks_planned,
        tasks_completed_30d=tasks_completed,
        tasks_draft_30d=tasks_draft,
        completion_pct=completion_pct,
        crm_notes=[_crm_note_item(n) for n in crm_notes],
        crm_actions=[_crm_action_item(a) for a in crm_actions],
        health_v2=_health_v2_data(health_v2),
        score_history=_health_history_points(score_history),
        owner_tags=[_owner_tag_item(t) for t in owner_tags],
        owner_contact=_owner_contact_data(owner_contact),
        plan_changes=[_plan_change_item(pc) for pc in plan_changes],
        offers=[_offer_item(o) for o in offers],
        invoices=[_invoice_item(r) for r in invoices],
        meta=_crm_meta(),
    )


# ---------------------------- CRM not mutation'lar (owner-aware) ----------------------------


@router.post(
    "/revenue/{owner_type}/{owner_id}/crm/notes",
    response_model=MutationResponse[Revenue360MutationResult],
)
def admin_revenue_crm_note_add_v2(
    owner_type: OwnerTypeLiteral,
    owner_id: int,
    body: CrmNoteBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """CRM not ekle. Jinja: crm_note_add / user_crm_note_add."""
    from app.services.institution_360 import create_note

    if not (body.content or "").strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "content_required", "message": "Not içeriği boş olamaz"},
        )
    note = create_note(
        db, **_crm_owner_kwargs(owner_type, owner_id),
        content=body.content.strip(), by_user_id=user.id, pinned=body.pinned,
    )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_note", target_id=note.id, request=request,
        details={"action": "create", "owner_type": owner_type, "owner_id": owner_id},
    )
    return MutationResponse[Revenue360MutationResult](
        data=Revenue360MutationResult(message="Not eklendi"),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


@router.post(
    "/revenue/crm/notes/{note_id}/pin",
    response_model=MutationResponse[Revenue360MutationResult],
)
def admin_revenue_crm_note_pin_v2(
    note_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Not sabitle/çöz."""
    from app.models import CrmNote
    from app.services.institution_360 import toggle_note_pin

    note = toggle_note_pin(db, note_id=note_id)
    if note is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "note_not_found", "message": "Not bulunamadı"},
        )
    owner_type = note.owner_type
    owner_id = note.institution_id if owner_type == "institution" else note.user_id
    msg = "Not sabitlendi" if note.pinned else "Sabitleme kaldırıldı"
    return MutationResponse[Revenue360MutationResult](
        data=Revenue360MutationResult(message=msg),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


@router.post(
    "/revenue/crm/notes/{note_id}/delete",
    response_model=MutationResponse[Revenue360MutationResult],
)
def admin_revenue_crm_note_delete_v2(
    note_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Not sil."""
    from app.models import CrmNote
    from app.services.institution_360 import delete_note

    note = db.get(CrmNote, note_id)
    if note is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "note_not_found", "message": "Not bulunamadı"},
        )
    owner_type = note.owner_type
    owner_id = note.institution_id if owner_type == "institution" else note.user_id
    delete_note(db, note_id=note_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_note", target_id=note_id, request=request,
        details={"action": "delete", "owner_type": owner_type, "owner_id": owner_id},
    )
    return MutationResponse[Revenue360MutationResult](
        data=Revenue360MutationResult(message="Not silindi"),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


# ---------------------------- CRM aksiyon mutation'lar ----------------------------


@router.post(
    "/revenue/{owner_type}/{owner_id}/crm/actions",
    response_model=MutationResponse[Revenue360MutationResult],
)
def admin_revenue_crm_action_add_v2(
    owner_type: OwnerTypeLiteral,
    owner_id: int,
    body: CrmActionBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """CRM aksiyon ekle."""
    from app.services.institution_360 import create_action

    if not (body.summary or "").strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "summary_required", "message": "Özet boş olamaz"},
        )
    action = create_action(
        db, **_crm_owner_kwargs(owner_type, owner_id),
        kind=body.kind, summary=body.summary.strip(),
        notes=(body.notes.strip() or None), result=body.result, by_user_id=user.id,
        follow_up_at=_fc_parse_dt(body.follow_up_at),
    )
    if action is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invalid_action_kind", "message": "Geçersiz aksiyon tipi"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_action", target_id=action.id, request=request,
        details={"action": "create", "kind": body.kind, "owner_type": owner_type, "owner_id": owner_id},
    )
    return MutationResponse[Revenue360MutationResult](
        data=Revenue360MutationResult(message="Aksiyon eklendi"),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


@router.post(
    "/revenue/crm/actions/{action_id}/complete",
    response_model=MutationResponse[Revenue360MutationResult],
)
def admin_revenue_crm_action_complete_v2(
    action_id: int,
    body: CrmActionCompleteBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Aksiyon tamamla."""
    from app.models import CrmAction
    from app.services.institution_360 import complete_action

    existing = db.get(CrmAction, action_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "action_not_found", "message": "Aksiyon bulunamadı"},
        )
    owner_type = existing.owner_type
    owner_id = existing.institution_id if owner_type == "institution" else existing.user_id
    a = complete_action(
        db, action_id=action_id, result=body.result, by_user_id=user.id,
        notes=(body.notes.strip() or None),
    )
    if a is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invalid_result", "message": "Geçersiz sonuç"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_action", target_id=action_id, request=request,
        details={"action": "complete", "result": body.result, "owner_type": owner_type, "owner_id": owner_id},
    )
    return MutationResponse[Revenue360MutationResult](
        data=Revenue360MutationResult(message="Aksiyon tamamlandı"),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


@router.post(
    "/revenue/crm/actions/{action_id}/delete",
    response_model=MutationResponse[Revenue360MutationResult],
)
def admin_revenue_crm_action_delete_v2(
    action_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Aksiyon sil."""
    from app.models import CrmAction
    from app.services.institution_360 import delete_action

    existing = db.get(CrmAction, action_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "action_not_found", "message": "Aksiyon bulunamadı"},
        )
    owner_type = existing.owner_type
    owner_id = existing.institution_id if owner_type == "institution" else existing.user_id
    delete_action(db, action_id=action_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_action", target_id=action_id, request=request,
        details={"action": "delete", "owner_type": owner_type, "owner_id": owner_id},
    )
    return MutationResponse[Revenue360MutationResult](
        data=Revenue360MutationResult(message="Aksiyon silindi"),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


# ---------------------------- İletişim + etiket mutation'lar ----------------------------


@router.post(
    "/revenue/{owner_type}/{owner_id}/contact",
    response_model=MutationResponse[Revenue360MutationResult],
)
def admin_revenue_contact_save_v2(
    owner_type: OwnerTypeLiteral,
    owner_id: int,
    body: OwnerContactBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """İletişim bilgilerini kaydet."""
    from app.services.owner_contact import upsert_contact

    upsert_contact(
        db, owner_type=owner_type, owner_id=owner_id, by_user_id=user.id,
        fields=body.model_dump(),
    )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="owner_contact", target_id=owner_id, request=request,
        details={"action": "upsert", "owner_type": owner_type},
    )
    return MutationResponse[Revenue360MutationResult](
        data=Revenue360MutationResult(message="İletişim bilgileri kaydedildi"),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


@router.post(
    "/revenue/{owner_type}/{owner_id}/tags",
    response_model=MutationResponse[Revenue360MutationResult],
)
def admin_revenue_tag_add_v2(
    owner_type: OwnerTypeLiteral,
    owner_id: int,
    body: OwnerTagBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Etiket ekle."""
    from app.services.owner_tags import add_tag

    tag = add_tag(
        db, owner_type=owner_type, owner_id=owner_id,
        kind=body.kind, note=(body.note or None), by_user_id=user.id,
    )
    if tag is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invalid_tag_kind", "message": "Geçersiz etiket türü"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="owner_tag", target_id=tag.id, request=request,
        details={"action": "add", "owner_type": owner_type, "owner_id": owner_id, "kind": body.kind},
    )
    return MutationResponse[Revenue360MutationResult](
        data=Revenue360MutationResult(message="Etiket eklendi"),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


@router.post(
    "/revenue/tags/{tag_id}/delete",
    response_model=MutationResponse[Revenue360MutationResult],
)
def admin_revenue_tag_delete_v2(
    tag_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Etiket sil."""
    from app.models import OwnerTag
    from app.services.owner_tags import remove_tag

    tag = db.get(OwnerTag, tag_id)
    if tag is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "tag_not_found", "message": "Etiket bulunamadı"},
        )
    owner_type = tag.owner_type
    owner_id = tag.institution_id if owner_type == "institution" else tag.user_id
    remove_tag(db, tag_id=tag_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="owner_tag", target_id=tag_id, request=request,
        details={"action": "delete", "owner_type": owner_type, "owner_id": owner_id},
    )
    return MutationResponse[Revenue360MutationResult](
        data=Revenue360MutationResult(message="Etiket silindi"),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


# =============================================================================
# P7c — Teklifler + Aksiyon Şablonları + Fatura Tahsilat
#
# Jinja eşdeğeri: admin.py offers create/send/cancel (4513) + invoice
# postpone/mark-paid/cancel/send-reminder (4027) + action-templates (4813).
# offers / crm_templates / dunning servisleri AYNEN çağrılır.
# =============================================================================


def _offer_owner_invalidate(offer) -> list[str]:
    ot = offer.owner_type
    oid = offer.institution_id if ot == "institution" else offer.user_id
    return _rev360_invalidate(ot, oid)


def _invoice_owner_invalidate(inv) -> list[str]:
    ot = inv.owner_type
    oid = inv.institution_id if ot == "institution" else inv.user_id
    return _rev360_invalidate(ot, oid)


# ---------------------------- Teklifler ----------------------------


@router.post(
    "/revenue/{owner_type}/{owner_id}/offers",
    response_model=MutationResponse[RevenueOfferMutationResult],
)
def admin_revenue_offer_create_v2(
    owner_type: OwnerTypeLiteral,
    owner_id: int,
    body: OfferBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Teklif oluştur (+ send_now ise gönder). Jinja: offer_create / user_offer_create."""
    from app.services.offers import create_offer, send_offer

    offer = create_offer(
        db,
        **(_crm_owner_kwargs(owner_type, owner_id)),
        kind=body.kind,
        title=body.title,
        by_user_id=user.id,
        value=body.value,
        duration_months=body.duration_months,
        new_plan=(body.new_plan.strip() or None),
        public_message=(body.public_message.strip() or None),
        admin_note=(body.admin_note.strip() or None),
        expires_in_days=(int(body.expires_in_days) if body.expires_in_days else None),
    )
    if offer is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invalid_offer_kind", "message": "Geçersiz teklif türü"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="offer", target_id=offer.id, request=request,
        details={"action": "create", "kind": body.kind, "owner_type": owner_type, "owner_id": owner_id},
    )
    msg = "Teklif oluşturuldu"
    if body.send_now:
        result = send_offer(db, offer_id=offer.id)
        if result.get("ok"):
            msg = "Teklif oluşturuldu ve gönderildi"
    return MutationResponse[RevenueOfferMutationResult](
        data=RevenueOfferMutationResult(message=msg, offer_id=offer.id),
        invalidate=_rev360_invalidate(owner_type, owner_id),
    )


@router.post(
    "/revenue/offers/{offer_id}/send",
    response_model=MutationResponse[RevenueOfferMutationResult],
)
def admin_revenue_offer_send_v2(
    offer_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Teklifi gönder (DRAFT → SENT). Jinja: offer_send_endpoint."""
    from app.models import Offer
    from app.services.offers import send_offer

    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "offer_not_found", "message": "Teklif bulunamadı"},
        )
    result = send_offer(db, offer_id=offer_id)
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "offer_send_failed", "message": f"Gönderilemedi: {result.get('error')}"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="offer", target_id=offer_id, request=request,
        details={"action": "send", "sent_via_email": result.get("sent_via_email")},
    )
    return MutationResponse[RevenueOfferMutationResult](
        data=RevenueOfferMutationResult(message="Teklif gönderildi", offer_id=offer_id),
        invalidate=_offer_owner_invalidate(offer),
    )


@router.post(
    "/revenue/offers/{offer_id}/cancel",
    response_model=MutationResponse[RevenueOfferMutationResult],
)
def admin_revenue_offer_cancel_v2(
    offer_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Teklifi iptal et. Jinja: offer_cancel_endpoint."""
    from app.models import Offer
    from app.services.offers import cancel_offer

    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "offer_not_found", "message": "Teklif bulunamadı"},
        )
    inval = _offer_owner_invalidate(offer)
    result = cancel_offer(db, offer_id=offer_id)
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "offer_cancel_failed", "message": f"İptal edilemedi: {result.get('error')}"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="offer", target_id=offer_id, request=request,
        details={"action": "cancel"},
    )
    return MutationResponse[RevenueOfferMutationResult](
        data=RevenueOfferMutationResult(message="Teklif iptal edildi", offer_id=offer_id),
        invalidate=inval,
    )


# ---------------------------- Fatura tahsilat ----------------------------


@router.post(
    "/revenue/invoices/{invoice_id}/postpone",
    response_model=MutationResponse[InvoiceMutationResult],
)
def admin_revenue_invoice_postpone_v2(
    invoice_id: int,
    body: InvoicePostponeBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Fatura vadesini ötele. Jinja: invoice_postpone."""
    from app.models import Invoice, InvoiceStatus

    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "invoice_not_found", "message": "Fatura bulunamadı"},
        )
    if inv.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invoice_not_eligible", "message": "Bu fatura ertelenemez"},
        )
    days = max(1, min(int(body.days), 90))
    base_due = inv.due_at
    if base_due is not None and base_due.tzinfo is None:
        base_due = base_due.replace(tzinfo=timezone.utc)
    inv.due_at = base_due + timedelta(days=days)
    if inv.status == InvoiceStatus.OVERDUE and inv.due_at >= datetime.now(timezone.utc):
        inv.status = InvoiceStatus.PENDING
    inv.notes = ((inv.notes or "") + f"\n[Ötelendi {days}g — {(body.note or '').strip()}]")[:8000]
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="invoice", target_id=invoice_id, request=request,
        details={"action": "postpone", "days": days},
        autocommit=False,
    )
    db.commit()
    return MutationResponse[InvoiceMutationResult](
        data=InvoiceMutationResult(message=f"Vade {days} gün ileri alındı", invoice_id=invoice_id),
        invalidate=_invoice_owner_invalidate(inv),
    )


@router.post(
    "/revenue/invoices/{invoice_id}/mark-paid",
    response_model=MutationResponse[InvoiceMutationResult],
)
def admin_revenue_invoice_mark_paid_v2(
    invoice_id: int,
    body: InvoiceMarkPaidBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Fatura manuel ödendi işaretle. Jinja: invoice_mark_paid."""
    from app.models import Invoice, InvoiceStatus, PaymentMethod

    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "invoice_not_found", "message": "Fatura bulunamadı"},
        )
    if inv.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invoice_already_paid", "message": "Zaten ödendi"},
        )
    try:
        pm = PaymentMethod(body.method)
    except ValueError:
        pm = PaymentMethod.MANUAL
    inv.status = InvoiceStatus.PAID
    inv.paid_at = datetime.now(timezone.utc)
    inv.payment_method = pm
    if body.note.strip():
        inv.notes = ((inv.notes or "") + f"\n[Manuel öden: {body.note.strip()}]")[:8000]
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="invoice", target_id=invoice_id, request=request,
        details={"action": "mark_paid", "method": pm.value, "amount_try": inv.amount_try},
        autocommit=False,
    )
    db.commit()
    return MutationResponse[InvoiceMutationResult](
        data=InvoiceMutationResult(message="Fatura ödenmiş olarak işaretlendi", invoice_id=invoice_id),
        invalidate=_invoice_owner_invalidate(inv),
    )


@router.post(
    "/revenue/invoices/{invoice_id}/cancel",
    response_model=MutationResponse[InvoiceMutationResult],
)
def admin_revenue_invoice_cancel_v2(
    invoice_id: int,
    body: InvoiceCancelBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Fatura iptal. Jinja: invoice_cancel."""
    from app.models import Invoice, InvoiceStatus

    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "invoice_not_found", "message": "Fatura bulunamadı"},
        )
    if inv.status in (InvoiceStatus.PAID, InvoiceStatus.REFUNDED):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invoice_not_eligible", "message": "Ödenmiş/iade fatura iptal edilemez"},
        )
    inv.status = InvoiceStatus.CANCELLED
    if body.note.strip():
        inv.notes = ((inv.notes or "") + f"\n[İptal: {body.note.strip()}]")[:8000]
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="invoice", target_id=invoice_id, request=request,
        details={"action": "cancel"},
        autocommit=False,
    )
    db.commit()
    return MutationResponse[InvoiceMutationResult](
        data=InvoiceMutationResult(message="Fatura iptal edildi", invoice_id=invoice_id),
        invalidate=_invoice_owner_invalidate(inv),
    )


@router.post(
    "/revenue/invoices/{invoice_id}/send-reminder",
    response_model=MutationResponse[InvoiceMutationResult],
)
def admin_revenue_invoice_send_reminder_v2(
    invoice_id: int,
    body: InvoiceReminderBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Manuel ödeme hatırlatması gönder. Jinja: invoice_send_reminder."""
    from app.models import Invoice
    from app.services.dunning import send_reminder

    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "invoice_not_found", "message": "Fatura bulunamadı"},
        )
    inval = _invoice_owner_invalidate(inv)
    result = send_reminder(
        db, invoice_id=invoice_id, kind=body.kind,
        triggered_by_user_id=user.id, manual=True,
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "reminder_failed", "message": f"Gönderilemedi: {result.get('error')}"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="invoice", target_id=invoice_id, request=request,
        details={"action": "send_reminder_manual", "kind": body.kind},
    )
    return MutationResponse[InvoiceMutationResult](
        data=InvoiceMutationResult(message=f"Hatırlatma gönderildi ({body.kind})", invoice_id=invoice_id),
        invalidate=inval,
    )


# ---------------------------- Aksiyon şablonları ----------------------------


def _action_template_item(t) -> ActionTemplateItem:
    from app.models import CRM_ACTION_KIND_LABELS_TR
    return ActionTemplateItem(
        id=t.id, name=t.name, kind=t.kind.value,
        kind_label=CRM_ACTION_KIND_LABELS_TR.get(t.kind, t.kind.value),
        subject=t.subject, body=t.body, description=t.description,
        is_active=t.is_active,
    )


@router.get("/revenue/action-templates", response_model=ActionTemplatesResponse)
def admin_revenue_action_templates_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Şablon listesi. Jinja: revenue_action_templates_list."""
    from app.models import CRM_ACTION_KIND_LABELS_TR, CrmActionKind
    from app.services.crm_templates import list_templates

    tpls = list_templates(db, active_only=False)
    return ActionTemplatesResponse(
        templates=[_action_template_item(t) for t in tpls],
        kinds=[EnumOption(value=k.value, label=CRM_ACTION_KIND_LABELS_TR[k]) for k in CrmActionKind],
    )


@router.post(
    "/revenue/action-templates",
    response_model=MutationResponse[ActionTemplateMutationResult],
)
def admin_revenue_action_template_create_v2(
    body: ActionTemplateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Şablon oluştur. Jinja: revenue_action_template_create."""
    from app.services.crm_templates import create_template

    tpl = create_template(
        db, name=body.name, kind=body.kind, body=body.body,
        subject=(body.subject or None), description=(body.description or None),
        by_user_id=user.id,
    )
    if tpl is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "template_invalid", "message": "Şablon oluşturulamadı (eksik alan / geçersiz tür)"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_template", target_id=tpl.id, request=request,
        details={"action": "create", "kind": body.kind},
    )
    return MutationResponse[ActionTemplateMutationResult](
        data=ActionTemplateMutationResult(message=f"Şablon eklendi: {tpl.name}", template_id=tpl.id),
        invalidate=["admin:revenue:action-templates"],
    )


@router.post(
    "/revenue/action-templates/{template_id}",
    response_model=MutationResponse[ActionTemplateMutationResult],
)
def admin_revenue_action_template_update_v2(
    template_id: int,
    body: ActionTemplateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Şablon güncelle. Jinja: revenue_action_template_update."""
    from app.services.crm_templates import update_template

    tpl = update_template(
        db, template_id=template_id,
        name=(body.name or None), kind=(body.kind or None), body=(body.body or None),
        subject=body.subject, description=body.description, is_active=body.is_active,
    )
    if tpl is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "template_not_found", "message": "Şablon bulunamadı"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_template", target_id=template_id, request=request,
        details={"action": "update"},
    )
    return MutationResponse[ActionTemplateMutationResult](
        data=ActionTemplateMutationResult(message=f"Şablon güncellendi: {tpl.name}", template_id=template_id),
        invalidate=["admin:revenue:action-templates"],
    )


@router.post(
    "/revenue/action-templates/{template_id}/delete",
    response_model=MutationResponse[ActionTemplateMutationResult],
)
def admin_revenue_action_template_delete_v2(
    template_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Şablon sil. Jinja: revenue_action_template_delete."""
    from app.services.crm_templates import delete_template

    ok = delete_template(db, template_id=template_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "template_not_found", "message": "Şablon bulunamadı"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_template", target_id=template_id, request=request,
        details={"action": "delete"},
    )
    return MutationResponse[ActionTemplateMutationResult](
        data=ActionTemplateMutationResult(message="Şablon silindi", template_id=template_id),
        invalidate=["admin:revenue:action-templates"],
    )


@router.get(
    "/revenue/action-templates/{template_id}/render",
    response_model=ActionTemplateRenderResponse,
)
def admin_revenue_action_template_render_v2(
    template_id: int,
    owner_type: OwnerTypeLiteral = Query("institution"),
    owner_id: int = Query(0),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Şablonu owner bağlamında render et (prefill). Jinja: revenue_action_template_render."""
    from app.services.crm_templates import render_template_for_owner

    if owner_id <= 0:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invalid_owner", "message": "Geçersiz owner"},
        )
    result = render_template_for_owner(
        db, template_id=template_id, owner_type=owner_type, owner_id=owner_id,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "template_not_found", "message": "Şablon bulunamadı"},
        )
    return ActionTemplateRenderResponse(**result)


# =============================================================================
# P7d — Toplu Kampanyalar
#
# Jinja eşdeğeri: admin.py /revenue/campaigns* (5766-6154). campaigns.py
# servisi AYNEN çağrılır. Owner-pattern: segment kurum + bağımsız öğretmen.
# =============================================================================


def _campaign_invalidate() -> list[str]:
    return ["admin:revenue:campaigns"]


def _campaign_funnel(d: dict) -> CampaignFunnel:
    return CampaignFunnel(
        targeted=d.get("targeted", 0),
        sent=d.get("sent", 0),
        accepted=d.get("accepted", 0),
        declined=d.get("declined", 0),
        expired=d.get("expired", 0),
        bounced=d.get("bounced", 0),
        total=d.get("total", 0),
        sent_total=d.get("sent_total", 0),
        accepted_pct=d.get("accepted_pct"),
    )


def _campaign_variant(camp, which: str):
    from app.models import OFFER_KIND_LABELS_TR, OfferKind
    if which == "a":
        kind, title = camp.variant_a_kind, camp.variant_a_title
        value, dur = camp.variant_a_value, camp.variant_a_duration_months
        plan, msg = camp.variant_a_new_plan, camp.variant_a_public_message
    else:
        kind, title = camp.variant_b_kind, camp.variant_b_title
        value, dur = camp.variant_b_value, camp.variant_b_duration_months
        plan, msg = camp.variant_b_new_plan, camp.variant_b_public_message
    try:
        label = OFFER_KIND_LABELS_TR.get(OfferKind(kind), kind) if kind else (kind or "")
    except ValueError:
        label = kind or ""
    return CampaignVariant(
        kind=kind or "",
        kind_label=label,
        title=title or "",
        value=float(value) if value is not None else None,
        duration_months=dur,
        new_plan=plan,
        public_message=msg,
    )


@router.get("/revenue/campaigns", response_model=CampaignsListResponse)
def admin_revenue_campaigns_list_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kampanya listesi + funnel. Jinja: admin.py:5766-5803."""
    from app.models import (
        CAMPAIGN_SEGMENT_LABELS_TR, CAMPAIGN_STATUS_COLORS, CAMPAIGN_STATUS_LABELS_TR,
    )
    from app.services.campaigns import campaign_stats, list_campaigns, sync_recipient_statuses

    campaigns = list_campaigns(db, limit=100)
    items: list[CampaignListItem] = []
    for c in campaigns:
        try:
            sync_recipient_statuses(db, campaign_id=c.id)
        except Exception:
            pass
        st = campaign_stats(db, campaign_id=c.id)
        items.append(CampaignListItem(
            id=c.id, name=c.name, description=c.description,
            segment=c.segment.value,
            segment_label=CAMPAIGN_SEGMENT_LABELS_TR.get(c.segment, c.segment.value),
            status=c.status.value,
            status_label=CAMPAIGN_STATUS_LABELS_TR.get(c.status, c.status.value),
            status_color=CAMPAIGN_STATUS_COLORS.get(c.status, "slate"),
            has_variant_b=c.has_variant_b,
            created_at=c.created_at,
            funnel=_campaign_funnel(st.get("overall", {})),
        ))
    return CampaignsListResponse(campaigns=items)


@router.get("/revenue/campaigns/new", response_model=CampaignFormMeta)
def admin_revenue_campaign_form_meta_v2(
    user: User = Depends(_require_super_admin),
):
    """Kampanya formu meta. Jinja: admin.py:5806-5833."""
    from app.models import (
        CAMPAIGN_SEGMENT_DESCRIPTIONS, CAMPAIGN_SEGMENT_LABELS_TR,
        OFFER_KIND_LABELS_TR, CampaignSegment, OfferKind,
    )
    return CampaignFormMeta(
        segments=[
            CampaignSegmentOption(
                value=s.value, label=CAMPAIGN_SEGMENT_LABELS_TR[s],
                description=CAMPAIGN_SEGMENT_DESCRIPTIONS[s],
            )
            for s in CampaignSegment
        ],
        offer_kinds=[EnumOption(value=k.value, label=OFFER_KIND_LABELS_TR[k]) for k in OfferKind],
    )


@router.post("/revenue/campaigns/preview", response_model=CampaignPreviewResponse)
def admin_revenue_campaign_preview_v2(
    body: CampaignPreviewBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Segment önizleme — eligible owner sayısı + ilk 10. Jinja: admin.py:5836-5873."""
    from app.models import CampaignSegment
    from app.services.campaigns import preview_segment

    try:
        seg = CampaignSegment(body.segment)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "invalid_segment", "message": "Geçersiz segment"},
        )
    owners = preview_segment(db, segment=seg, filter_plan=body.filter_plan.strip() or None)
    inst_count = sum(1 for o in owners if o.owner_type == "institution")
    user_count = sum(1 for o in owners if o.owner_type == "user")
    return CampaignPreviewResponse(
        count=len(owners),
        inst_count=inst_count,
        user_count=user_count,
        preview=[
            CampaignPreviewOwner(
                owner_type=o.owner_type, owner_id=o.owner_id, name=o.name,
                plan=o.plan, url=o.url,
            )
            for o in owners[:10]
        ],
    )


@router.post(
    "/revenue/campaigns",
    response_model=MutationResponse[CampaignMutationResult],
)
def admin_revenue_campaign_create_v2(
    body: CampaignBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kampanya oluştur (DRAFT). Jinja: admin.py:5876-5961."""
    from app.services.campaigns import create_campaign

    camp = create_campaign(
        db,
        name=body.name,
        segment=body.segment,
        segment_filter_plan=(body.filter_plan.strip() or None),
        variant_a_kind=body.variant_a_kind,
        variant_a_title=body.variant_a_title,
        by_user_id=user.id,
        description=(body.description.strip() or None),
        admin_note=(body.admin_note.strip() or None),
        variant_a_value=body.variant_a_value,
        variant_a_duration_months=body.variant_a_duration_months,
        variant_a_new_plan=(body.variant_a_new_plan.strip() or None),
        variant_a_public_message=(body.variant_a_public_message.strip() or None),
        has_variant_b=body.has_variant_b,
        variant_b_kind=(body.variant_b_kind.strip() or None),
        variant_b_title=(body.variant_b_title.strip() or None),
        variant_b_value=body.variant_b_value,
        variant_b_duration_months=body.variant_b_duration_months,
        variant_b_new_plan=(body.variant_b_new_plan.strip() or None),
        variant_b_public_message=(body.variant_b_public_message.strip() or None),
        offer_expires_in_days=int(body.offer_expires_in_days or 14),
    )
    if camp is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "campaign_invalid", "message": "Kampanya oluşturulamadı (geçersiz segment / teklif türü)"},
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="campaign", target_id=camp.id, request=request,
        details={"action": "create", "segment": body.segment, "has_variant_b": body.has_variant_b},
    )
    return MutationResponse[CampaignMutationResult](
        data=CampaignMutationResult(message="Kampanya taslak olarak kaydedildi", campaign_id=camp.id),
        invalidate=_campaign_invalidate(),
    )


@router.get(
    "/revenue/campaigns/{campaign_id}",
    response_model=CampaignDetailResponse,
)
def admin_revenue_campaign_detail_v2(
    campaign_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kampanya detay + funnel + recipient. Jinja: admin.py:5965-6030."""
    from app.models import (
        CAMPAIGN_SEGMENT_LABELS_TR, CAMPAIGN_STATUS_COLORS, CAMPAIGN_STATUS_LABELS_TR,
        Campaign, CampaignRecipient, Institution, RECIPIENT_STATUS_LABELS_TR,
    )
    from app.services.campaigns import campaign_stats, sync_recipient_statuses

    camp = db.get(Campaign, campaign_id)
    if camp is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "campaign_not_found", "message": "Kampanya bulunamadı"},
        )
    sync_recipient_statuses(db, campaign_id=campaign_id)
    st = campaign_stats(db, campaign_id=campaign_id)
    recips = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign_id)
        .order_by(CampaignRecipient.id.desc())
        .limit(200)
        .all()
    )
    inst_ids = [r.institution_id for r in recips if r.owner_type == "institution" and r.institution_id]
    user_ids = [r.user_id for r in recips if r.owner_type == "user" and r.user_id]
    inst_map = {i.id: i for i in db.query(Institution).filter(Institution.id.in_(set(inst_ids))).all()} if inst_ids else {}
    users_map = {u.id: u for u in db.query(User).filter(User.id.in_(set(user_ids))).all()} if user_ids else {}

    recip_items: list[CampaignRecipientItem] = []
    for r in recips:
        if r.owner_type == "user":
            ent = users_map.get(r.user_id)
            name = (ent.full_name or ent.email) if ent else f"(silinmiş öğretmen #{r.user_id})"
            plan = ent.plan if ent else None
        else:
            ent = inst_map.get(r.institution_id)
            name = ent.name if ent else f"(silinmiş kurum #{r.institution_id})"
            plan = ent.plan if ent else None
        recip_items.append(CampaignRecipientItem(
            id=r.id, owner_type=r.owner_type, owner_id=r.owner_id,
            owner_name=name, owner_plan=plan, owner_url=r.owner_detail_url,
            variant=r.variant, status=r.status.value,
            status_label=RECIPIENT_STATUS_LABELS_TR.get(r.status, r.status.value),
            sent_at=r.sent_at, responded_at=r.responded_at,
            offer_id=r.offer_id,
            offer_token=(r.offer.token if r.offer else None),
            error_note=r.error_note,
        ))

    detail = CampaignDetail(
        id=camp.id, name=camp.name, description=camp.description, admin_note=camp.admin_note,
        segment=camp.segment.value,
        segment_label=CAMPAIGN_SEGMENT_LABELS_TR.get(camp.segment, camp.segment.value),
        segment_filter_plan=camp.segment_filter_plan,
        status=camp.status.value,
        status_label=CAMPAIGN_STATUS_LABELS_TR.get(camp.status, camp.status.value),
        status_color=CAMPAIGN_STATUS_COLORS.get(camp.status, "slate"),
        has_variant_b=camp.has_variant_b,
        variant_a=_campaign_variant(camp, "a"),
        variant_b=_campaign_variant(camp, "b") if camp.has_variant_b else None,
        offer_expires_in_days=camp.offer_expires_in_days,
        created_at=camp.created_at, started_at=camp.started_at, completed_at=camp.completed_at,
    )
    stats = CampaignStatsFull(
        status=st["status"],
        overall=_campaign_funnel(st["overall"]),
        variant_a=_campaign_funnel(st["variant_a"]),
        variant_b=_campaign_funnel(st["variant_b"]) if st.get("variant_b") else None,
        has_variant_b=st["has_variant_b"],
        institution_count=st["institution_count"],
        user_count=st["user_count"],
    )
    return CampaignDetailResponse(campaign=detail, stats=stats, recipients=recip_items)


def _campaign_lifecycle(
    db: Session, request: Request, user: User, *, campaign_id: int,
    action: str, fn, ok_msg: str,
) -> MutationResponse[CampaignMutationResult]:
    result = fn(db, campaign_id=campaign_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="campaign", target_id=campaign_id, request=request,
        details={"action": action, "ok": result.get("ok")},
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": f"campaign_{action}_failed",
                    "message": f"İşlem başarısız: {result.get('error')}"},
        )
    data = CampaignMutationResult(message=ok_msg, campaign_id=campaign_id)
    if action == "launch":
        data.recipient_count = result.get("recipient_count")
        data.sent = result.get("sent")
        data.errors = result.get("errors")
        sent = result.get("sent", 0)
        rc = result.get("recipient_count", 0)
        data.message = f"Kampanya başlatıldı — {sent}/{rc} e-posta gönderildi"
    return MutationResponse[CampaignMutationResult](data=data, invalidate=_campaign_invalidate())


@router.post(
    "/revenue/campaigns/{campaign_id}/launch",
    response_model=MutationResponse[CampaignMutationResult],
)
def admin_revenue_campaign_launch_v2(
    campaign_id: int, request: Request,
    user: User = Depends(_require_super_admin), db: Session = Depends(get_db),
):
    """Kampanyayı başlat. Jinja: admin.py:6033-6062."""
    from app.services.campaigns import launch_campaign
    return _campaign_lifecycle(db, request, user, campaign_id=campaign_id,
                               action="launch", fn=launch_campaign, ok_msg="Kampanya başlatıldı")


@router.post(
    "/revenue/campaigns/{campaign_id}/pause",
    response_model=MutationResponse[CampaignMutationResult],
)
def admin_revenue_campaign_pause_v2(
    campaign_id: int, request: Request,
    user: User = Depends(_require_super_admin), db: Session = Depends(get_db),
):
    """Kampanyayı duraklat. Jinja: admin.py:6065-6085."""
    from app.services.campaigns import pause_campaign
    return _campaign_lifecycle(db, request, user, campaign_id=campaign_id,
                               action="pause", fn=pause_campaign, ok_msg="Kampanya duraklatıldı")


@router.post(
    "/revenue/campaigns/{campaign_id}/resume",
    response_model=MutationResponse[CampaignMutationResult],
)
def admin_revenue_campaign_resume_v2(
    campaign_id: int, request: Request,
    user: User = Depends(_require_super_admin), db: Session = Depends(get_db),
):
    """Kampanyayı devam ettir. Jinja: admin.py:6088-6108."""
    from app.services.campaigns import resume_campaign
    return _campaign_lifecycle(db, request, user, campaign_id=campaign_id,
                               action="resume", fn=resume_campaign, ok_msg="Kampanya devam ediyor")


@router.post(
    "/revenue/campaigns/{campaign_id}/complete",
    response_model=MutationResponse[CampaignMutationResult],
)
def admin_revenue_campaign_complete_v2(
    campaign_id: int, request: Request,
    user: User = Depends(_require_super_admin), db: Session = Depends(get_db),
):
    """Kampanyayı tamamla. Jinja: admin.py:6111-6131."""
    from app.services.campaigns import complete_campaign
    return _campaign_lifecycle(db, request, user, campaign_id=campaign_id,
                               action="complete", fn=complete_campaign, ok_msg="Kampanya tamamlandı")


@router.post(
    "/revenue/campaigns/{campaign_id}/cancel",
    response_model=MutationResponse[CampaignMutationResult],
)
def admin_revenue_campaign_cancel_v2(
    campaign_id: int, request: Request,
    user: User = Depends(_require_super_admin), db: Session = Depends(get_db),
):
    """Kampanyayı iptal et. Jinja: admin.py:6134-6154."""
    from app.services.campaigns import cancel_campaign
    return _campaign_lifecycle(db, request, user, campaign_id=campaign_id,
                               action="cancel", fn=cancel_campaign, ok_msg="Kampanya iptal edildi")


# =============================================================================
# G1 — Ticari Ana Dashboard (security-monitor/revenue)
#
# Jinja eşdeğeri: admin.py /security-monitor/revenue (3374) + /revenue/drill
# (3429) + /revenue/invoices (5165). revenue_panel.py + revenue_owner.py
# AYNEN çağrılır — hepsi salt-okunur. Owner-pattern segment toggle korunur.
# =============================================================================


@router.get("/security-monitor/revenue", response_model=RevenueDashboardResponse)
def admin_revenue_dashboard_v2(
    segment: str = Query("all"),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Ticari ana dashboard — MRR/plan/trial/değişim/churn/ödeme takvimi.
    Jinja: admin.py:3374-3426."""
    from app.services.revenue_owner import (
        mrr_owner_aware, plan_distribution_owner_aware, trial_ending_soon_owner_aware,
    )
    from app.services.revenue_panel import get_revenue_panel_data

    if segment not in ("all", "institution", "user"):
        segment = "all"
    data = get_revenue_panel_data(db)

    try:
        mrr_combined = mrr_owner_aware(db, segment=segment)
        plan_dist_combined = plan_distribution_owner_aware(db, segment=segment)
        trial_combined = trial_ending_soon_owner_aware(db, days_horizon=7, segment=segment)
        mrr_all = mrr_owner_aware(db, segment="all")
    except Exception:
        mrr_combined, plan_dist_combined, trial_combined, mrr_all = None, [], [], None

    return RevenueDashboardResponse(
        generated_at=data["generated_at"],
        mrr=RevenueMrr(**data["mrr"]),
        plan_distribution=[RevenuePlanDist(**p) for p in data["plan_distribution"]],
        trial_ending_soon=[
            RevenueTrialEntry(
                institution_id=t.institution_id, institution_name=t.institution_name,
                plan=t.plan, trial_ends_at=t.trial_ends_at, days_left=t.days_left,
                post_trial_plan=t.post_trial_plan,
            )
            for t in data["trial_ending_soon"]
        ],
        trial_expired_30d=data["trial_expired_30d"],
        change_summary_30d=RevenueChangeSummary(**data["change_summary_30d"]),
        daily_changes_30d=[
            RevenueDailyChange(
                day=d["day"], signup=d.get("signup", 0), upgrade=d.get("upgrade", 0),
                downgrade=d.get("downgrade", 0), trial_expired=d.get("trial_expired", 0),
                pause=d.get("pause", 0), total=d.get("total", 0),
            )
            for d in data["daily_changes_30d"]
        ],
        churn_proxy=RevenueChurnProxy(
            healthy=data["churn_proxy"].get("healthy", 0),
            watch=data["churn_proxy"].get("watch", 0),
            risk=data["churn_proxy"].get("risk", 0),
            critical=data["churn_proxy"].get("critical", 0),
            unhealthy_total=data["churn_proxy"].get("unhealthy_total", 0),
            needs_attention=data["churn_proxy"].get("needs_attention"),
        ),
        payment_calendar=RevenuePaymentCalendar(
            buckets=[RevenuePaymentBucket(
                key=b["key"], label=b["label"], count=b["count"], total_try=b["total_try"],
            ) for b in data["payment_calendar"]["buckets"]],
            total_count=data["payment_calendar"]["total_count"],
            total_amount_try=data["payment_calendar"]["total_amount_try"],
            overdue_total_try=data["payment_calendar"]["overdue_total_try"],
            upcoming_total_try=data["payment_calendar"]["upcoming_total_try"],
            days_horizon=data["payment_calendar"]["days_horizon"],
        ),
        mrr_combined=RevenueOwnerMrr(**mrr_combined) if mrr_combined else None,
        plan_dist_combined=[RevenueOwnerPlanDist(**p) for p in plan_dist_combined],
        trial_combined=[
            RevenueOwnerTrial(
                owner_type=o.owner_type, owner_id=o.owner_id, name=o.name,
                plan=o.plan, trial_ends_at=o.trial_ends_at, url=o.url,
            )
            for o in trial_combined
        ],
        segment=segment,
        segment_counts={
            "all": (mrr_all.get("total_owners") if mrr_all else 0),
            "institution": (mrr_all.get("institution_count") if mrr_all else 0),
            "user": (mrr_all.get("user_count") if mrr_all else 0),
        },
    )


@router.get("/security-monitor/revenue/drill", response_model=RevenueDrillResponse)
def admin_revenue_drill_v2(
    key: str = Query(...),
    plan: str | None = Query(None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """KPI drill-down — bir sayının arkasındaki kurum listesi. Jinja: admin.py:3429-3453."""
    from app.services.revenue_panel import drill_for_key

    result = drill_for_key(db, key=key, plan=plan)
    return RevenueDrillResponse(
        title=result.get("title", ""),
        icon=result.get("icon", ""),
        key=result.get("key", key),
        plan=result.get("plan"),
        count=result.get("count", 0),
        rows=[
            RevenueDrillRow(
                institution_id=r["institution_id"],
                institution_name=r["institution_name"],
                plan=r["plan"],
                plan_label=r["plan_label"],
                monthly_price_try=r.get("monthly_price_try"),
                is_active=r.get("is_active"),
                trial_ends_at=r.get("trial_ends_at"),
                post_trial_plan=r.get("post_trial_plan"),
                reason=r.get("reason"),
                detail_url=r.get("detail_url", f"/admin/institutions/{r['institution_id']}"),
                health_score=r.get("health_score"),
                active_teacher_pct=r.get("active_teacher_pct"),
                active_student_pct=r.get("active_student_pct"),
                event_at=r.get("event_at"),
                event_days_ago=r.get("event_days_ago"),
            )
            for r in result.get("rows", [])
        ],
        error=result.get("error"),
    )


@router.get("/security-monitor/revenue/invoices", response_model=RevenueInvoicesResponse)
def admin_revenue_invoices_v2(
    status_filter: str | None = Query(None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tüm faturalar (status filtre + sayım). Jinja: admin.py:5165-5227."""
    from app.models import (
        INVOICE_STATUS_BADGE_COLOR, INVOICE_STATUS_LABELS_TR,
        Institution, Invoice, InvoiceStatus,
    )

    q = db.query(Invoice).order_by(Invoice.due_at.desc())
    if status_filter:
        try:
            q = q.filter(Invoice.status == InvoiceStatus(status_filter))
        except ValueError:
            pass
    rows = q.limit(200).all()
    inst_ids = {r.institution_id for r in rows if r.institution_id is not None}
    user_ids = {r.user_id for r in rows if r.user_id is not None}
    insts = {i.id: i for i in db.query(Institution).filter(Institution.id.in_(inst_ids)).all()} if inst_ids else {}
    users_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    status_counts_raw = (
        db.query(Invoice.status, sa_func.count(Invoice.id), sa_func.coalesce(sa_func.sum(Invoice.amount_try), 0))
        .group_by(Invoice.status)
        .all()
    )
    status_counts = {
        s.value: RevenueInvoiceStatusCount(count=int(c), total_try=int(t))
        for s, c, t in status_counts_raw
    }

    row_items: list[RevenueInvoiceRow] = []
    for r in rows:
        if r.owner_type == "user":
            u = users_map.get(r.user_id)
            name = (u.full_name or u.email) if u else f"Öğretmen #{r.user_id}"
            url = f"/admin/revenue/users/{r.user_id}"
        else:
            inst = insts.get(r.institution_id)
            name = inst.name if inst else f"Kurum #{r.institution_id}"
            url = f"/admin/revenue/institutions/{r.institution_id}"
        row_items.append(RevenueInvoiceRow(
            id=r.id, owner_type=r.owner_type, owner_id=r.owner_id,
            owner_name=name, owner_url=url, plan=r.plan, amount_try=r.amount_try,
            status=r.status.value,
            status_label=INVOICE_STATUS_LABELS_TR.get(r.status, r.status.value),
            status_color=INVOICE_STATUS_BADGE_COLOR.get(r.status, "slate"),
            due_at=r.due_at, paid_at=r.paid_at,
            payment_method=(r.payment_method.value if r.payment_method else None),
        ))

    return RevenueInvoicesResponse(
        rows=row_items,
        status_counts=status_counts,
        statuses=[
            StatusOption(value=s.value, label=INVOICE_STATUS_LABELS_TR.get(s, s.value),
                         badge=INVOICE_STATUS_BADGE_COLOR.get(s, "slate"))
            for s in InvoiceStatus
        ],
        status_filter=status_filter,
    )


# =============================================================================
# G2a — Güvenlik Kamarası: Genel Bakış + Bütünlük + Sistem + Bildirim
# =============================================================================


def _attention_item_to_model(it) -> AttentionItemModel:
    """attention_engine.AttentionItem dataclass → Pydantic (alanlar birebir)."""
    return AttentionItemModel(
        severity=it.severity,
        icon=it.icon,
        title=it.title,
        description=it.description,
        action_url=it.action_url,
        action_label=it.action_label,
        category=it.category,
        ts=it.ts,
        score=it.score,
        explainer=it.explainer or "",
    )


@router.get("/security-monitor", response_model=SecurityOverviewResponse)
def admin_security_overview_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Güvenlik kamerası genel bakış: aktif oturumlar, şüpheli/blokli IP'ler,
    son 24h başarısız login dağılımı, kritik aksiyon akışı, süper admin
    login'leri, aktif kimliğe-bürünme + dikkat odası. Jinja: admin.py:3240-3277."""
    from app.services.security_monitor import get_security_dashboard_data
    from app.services.impersonation import list_active as list_active_impersonations
    from app.services.abuse_detection import open_signal_count
    from app.services.error_capture import error_summary
    from app.services.alarm_engine import unacknowledged_count
    from app.services.attention_engine import get_attention_summary

    data = get_security_dashboard_data(db)
    attention = get_attention_summary(db)
    return SecurityOverviewResponse(
        generated_at=data["generated_at"],
        summary=SecuritySummary(**data["summary"]),
        role_counts=data["role_counts"],
        active_sessions=[SecuritySessionItem(**s) for s in data["active_sessions"]],
        suspicious_ips=[SecuritySuspiciousIp(**s) for s in data["suspicious_ips"]],
        failed_login_buckets=[
            SecurityFailedBucket(
                ip=b.ip,
                fail_count=b.fail_count,
                distinct_email_count=b.distinct_email_count,
                last_seen_at=b.last_seen_at,
            )
            for b in data["failed_login_buckets"]
        ],
        critical_audits=[_audit_log_to_item(a) for a in data["critical_audits"]],
        super_admin_logins=[_audit_log_to_item(a) for a in data["super_admin_logins"]],
        active_impersonations=[
            SecurityImpersonationItem(**imp) for imp in list_active_impersonations(db)
        ],
        abuse_open_count=open_signal_count(db),
        system_error_summary=ErrorSummaryModel(**error_summary(db, hours=24)),
        unack_alarm_count=unacknowledged_count(db),
        attention=AttentionSummaryModel(
            items=[_attention_item_to_model(it) for it in attention["items"]],
            total=attention["total"],
            by_severity=attention["by_severity"],
            by_category=attention["by_category"],
            top_severity=attention["top_severity"],
            is_clean=attention["is_clean"],
        ),
    )


@router.get("/security-monitor/integrity", response_model=IntegrityResponse)
def admin_security_integrity_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Veri bütünlüğü kamerası: migration / DB dosyası / orphan tarama /
    KVKK SLA / cron drift. Jinja: admin.py data_integrity panel."""
    from app.services.data_integrity import get_integrity_panel_data

    data = get_integrity_panel_data(db)
    db_file = data["db_file"]
    orphans = data["orphans"]
    kvkk = data["kvkk_sla"]
    cron = data["cron_drift"]
    return IntegrityResponse(
        generated_at=data["generated_at"],
        migration=IntegrityMigration(**data["migration"]),
        db_file=IntegrityDbFile(
            path=db_file.get("path"),
            size_mb=db_file.get("size_mb", 0),
            size_bytes=db_file.get("size_bytes"),
            modified_at=db_file.get("modified_at"),
            age_seconds=db_file.get("age_seconds", 0),
            level=db_file.get("level", "unknown"),
        ),
        orphans=IntegrityOrphans(
            total_findings=orphans["total_findings"],
            findings=[IntegrityOrphanFinding(**f) for f in orphans["findings"]],
        ),
        kvkk_sla=IntegrityKvkk(
            sla_days=kvkk["sla_days"],
            overdue_count=kvkk["overdue_count"],
            open_total=kvkk["open_total"],
            overdue_samples=[IntegrityKvkkSample(**s) for s in kvkk["overdue_samples"]],
        ),
        cron_drift=IntegrityCronDrift(
            summary=cron["summary"],
            jobs=[IntegrityCronJob(**j) for j in cron["jobs"]],
        ),
    )


@router.get("/security-monitor/system", response_model=SystemHealthDataResponse)
def admin_security_system_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Sistem sağlığı kamerası: açık hata grupları + endpoint hata oranı +
    yavaş istekler. Jinja: admin.py error_capture panel."""
    from app.services.error_capture import get_system_health_data

    data = get_system_health_data(db)
    return SystemHealthDataResponse(
        generated_at=data["generated_at"],
        summary=ErrorSummaryModel(**data["summary"]),
        error_groups=[SystemErrorGroup(**g) for g in data["error_groups"]],
        endpoint_top=[SystemEndpointError(**e) for e in data["endpoint_top"]],
        slow_requests=[SystemSlowRequest(**s) for s in data["slow_requests"]],
    )


@router.post(
    "/security-monitor/system/{error_id}/resolve",
    response_model=MutationResponse[SystemMutationResult],
)
def admin_security_system_resolve_v2(
    error_id: int,
    body: SystemResolveBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Hata grubunu çözüldü olarak işaretle. Jinja: admin.py resolve_error."""
    from app.services.error_capture import resolve_error

    row = resolve_error(
        db, error_id=error_id, resolved_by_user_id=user.id, note=(body.note or None)
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found", "code": "error_not_found",
                "message": "Hata kaydı bulunamadı.",
            },
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="error_event",
        target_id=row.id,
        request=request,
        details={"action": "resolve", "signature": row.signature, "note": (body.note or "")[:200]},
    )
    return MutationResponse[SystemMutationResult](
        data=SystemMutationResult(
            message="Hata çözüldü olarak işaretlendi.", error_id=row.id
        ),
        invalidate=["admin:security:system", "admin:security:overview"],
    )


@router.get("/security-monitor/notifications", response_model=NotificationHealthResponse)
def admin_security_notifications_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Bildirim teslimat sağlık kamerası: 24h/7g özet + kanal/tür matrisi +
    suppress dağılımı + günlük trend + son hatalar. Jinja: notification_health."""
    from app.services.notification_health import get_health_data

    data = get_health_data(db)
    s24 = data["summary_24h"]
    s7d = data["summary_7d"]
    ch = data["channel_matrix_24h"]
    kd = data["kind_matrix_24h"]
    return NotificationHealthResponse(
        generated_at=data["generated_at"],
        summary_24h=NotifWindowSummary(
            window_label=s24.window_label, window_hours=s24.window_hours,
            total=s24.total, sent=s24.sent, failed=s24.failed,
            queued=s24.queued, suppressed=s24.suppressed, success_pct=s24.success_pct,
        ),
        summary_7d=NotifWindowSummary(
            window_label=s7d.window_label, window_hours=s7d.window_hours,
            total=s7d.total, sent=s7d.sent, failed=s7d.failed,
            queued=s7d.queued, suppressed=s7d.suppressed, success_pct=s7d.success_pct,
        ),
        oldest_queued_minutes=data["oldest_queued_minutes"],
        channel_matrix_24h=NotifMatrix(
            rows=ch["channels"], statuses=ch["statuses"],
            matrix=ch["matrix"], rollups=ch["rollups"], window_hours=ch["window_hours"],
        ),
        kind_matrix_24h=NotifMatrix(
            rows=kd["kinds"], statuses=kd["statuses"],
            matrix=kd["matrix"], rollups=kd["rollups"], window_hours=kd["window_hours"],
        ),
        suppress_distribution_24h=[
            NotifSuppressItem(**s) for s in data["suppress_distribution_24h"]
        ],
        daily_trend_7d=[NotifDailyTrend(**d) for d in data["daily_trend_7d"]],
        recent_failures_24h=[NotifFailureItem(**f) for f in data["recent_failures_24h"]],
    )


# =============================================================================
# G2b — Güvenlik Kamarası: Aktivite Kamerası
# =============================================================================


def _str_matrix(matrix: dict) -> dict[str, dict[str, int]]:
    """int-key heatmap matrix → str-key (JSON/Pydantic uyumu)."""
    return {
        str(h): {str(d): int(v) for d, v in row.items()}
        for h, row in matrix.items()
    }


@router.get("/security-monitor/activity", response_model=ActivityPanelResponse)
def admin_security_activity_v2(
    segment: str = Query("all"),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kurum + Bağımsız Öğretmen Aktivite Kamerası — 6 sekme × 3 segment.
    Jinja: admin.py:3295-3321. Tüm sekmelerin verisi tek çağrıda döner;
    'tab' salt UI tarafında — backend segment'e göre hesaplar."""
    from app.services.tenant_activity import get_activity_panel_data_with_summary

    if segment not in ("all", "institution", "solo"):
        segment = "all"
    d = get_activity_panel_data_with_summary(db, segment=segment)

    return ActivityPanelResponse(
        generated_at=d["generated_at"],
        segment=d["segment"],
        totals=ActivityTotals(**d["totals"]),
        per_tenant=[ActivityPerTenant(**t) for t in d["per_tenant"]],
        heatmap=ActivityHeatmap(
            days_window=d["heatmap"]["days_window"],
            matrix=_str_matrix(d["heatmap"]["matrix"]),
            max_value=d["heatmap"]["max_value"],
            total=d["heatmap"]["total"],
            day_labels=d["heatmap"]["day_labels"],
        ),
        dau_trend_14d=[ActivityDauTrendPoint(**p) for p in d["dau_trend_14d"]],
        silent_tenants_7d=[ActivitySilentRow(**s) for s in d["silent_tenants_7d"]],
        role_breakdown=[ActivityRoleBreakdownRow(**r) for r in d["role_breakdown"]["rows"]],
        heartbeats=[ActivityHeartbeatRow(**h) for h in d["heartbeats"]],
        heartbeat_summary=ActivityHeartbeatSummary(**d["heartbeat_summary"]),
        wow=ActivityWow(**d["wow"]),
        stickiness=ActivityStickiness(**d["stickiness"]),
        stickiness_trend_30d=[ActivityStickinessPoint(**p) for p in d["stickiness_trend_30d"]],
        week1=_retention_metric(d["week1"]),
        day30=_retention_metric(d["day30"]),
        resurrected=[ActivityResurrectedRow(**r) for r in d["resurrected"]],
        decay_rates=[ActivityDecayRow(**r) for r in d["decay_rates"]],
        plan_activity=ActivityPlanActivityMatrix(**d["plan_activity"]),
        session_duration=ActivitySessionDuration(**d["session_duration"]),
        teacher_student_ratios=[ActivityRatioRow(**r) for r in d["teacher_student_ratios"]],
        power_users=ActivityPowerUsers(**d["power_users"]),
        feature_popularity=[ActivityFeaturePopularity(**f) for f in d["feature_popularity"]],
        feature_matrix=ActivityFeatureMatrix(**d["feature_matrix"]),
        onboarding=[ActivityOnboardingRow(**o) for o in d["onboarding"]],
        plan_benchmark=[ActivityPlanBenchmarkRow(**r) for r in d["plan_benchmark"]],
        champions=[ActivityChampionRow(**c) for c in d["champions"]],
        action_suggestions={
            band: [ActionSuggestion(**s) for s in suggs]
            for band, suggs in d["action_suggestions"].items()
        },
        solo_special=ActivitySoloSpecial(**d["solo_special"]) if d.get("solo_special") else None,
        critical_summary=ActivityCriticalSummary(**d["critical_summary"]),
    )


def _retention_metric(m: dict) -> ActivityRetentionMetric:
    return ActivityRetentionMetric(
        total=m.get("total", 0),
        active=m.get("active", 0),
        ratio_pct=m.get("ratio_pct"),
        health=m.get("health"),
        color=m.get("color"),
    )


@router.get(
    "/security-monitor/activity/active-users",
    response_model=ActiveUsersDrillResponse,
)
def admin_security_activity_active_users_v2(
    window: str = Query("dau"),
    role: str = Query(""),
    institution_id: int | None = Query(None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Aktif kullanıcı drill-down (DAU/WAU/MAU). Jinja: admin.py:3324-3355."""
    from app.services.tenant_activity import active_users_window

    rows = active_users_window(
        db, window=window, role=role or None,
        institution_id=institution_id, limit=100,
    )
    win_label = {"dau": "son 24 saat", "wau": "son 7 gün",
                 "mau": "son 30 gün"}.get(window, window)
    role_label = {
        "teacher": "Öğretmen", "student": "Öğrenci",
        "parent": "Veli", "institution_admin": "Kurum Yöneticisi",
    }.get(role, "Tüm roller") if role else "Tüm roller"
    return ActiveUsersDrillResponse(
        window=window,
        window_label=win_label,
        role=role,
        role_label=role_label,
        rows=[ActiveUsersDrillRow(**r) for r in rows],
    )


@router.get(
    "/security-monitor/activity/heatmap",
    response_model=InstitutionHeatmapResponse,
)
def admin_security_activity_heatmap_v2(
    institution_id: int = Query(...),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tek kurum saat × gün heatmap'i + örüntü etiketleri. Jinja: admin.py:3358-3371."""
    from app.services.tenant_activity import institution_hour_day_heatmap

    h = institution_hour_day_heatmap(db, institution_id=institution_id)
    return InstitutionHeatmapResponse(
        institution_id=h["institution_id"],
        institution_name=h.get("institution_name"),
        plan=h.get("plan"),
        days_window=h["days_window"],
        matrix=_str_matrix(h["matrix"]),
        max_value=h["max_value"],
        total=h["total"],
        day_labels=h["day_labels"],
        patterns=[HeatmapPattern(**p) for p in h["patterns"]],
    )


# =============================================================================
# G3 — Güvenlik Kamarası: Oturumlar + Canlı Akış + IP + Impersonation
# =============================================================================

_SECURITY_SESSIONS_INVALIDATE = ["admin:security:overview", "admin:security:sessions"]


@router.get("/security-monitor/live/feed", response_model=LiveFeedResponse)
def admin_security_live_feed_v2(
    since_seconds: int = Query(600, ge=10, le=86400),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Canlı olay akışı: son N saniye AuditLog + AlarmEvent karışık. Jinja: admin.py:5357-5370."""
    from app.services.alarm_engine import live_event_stream

    items = live_event_stream(db, since_seconds=since_seconds, limit=80)
    return LiveFeedResponse(
        since_seconds=since_seconds,
        items=[
            LiveFeedItem(
                type=it["type"],
                ts=it.get("ts"),
                title=it["title"],
                actor_id=it.get("actor_id"),
                ip=it.get("ip"),
                details=it.get("details") or "",
                severity=it["severity"],
            )
            for it in items
        ],
    )


@router.post(
    "/security-monitor/sessions/{session_token}/revoke",
    response_model=MutationResponse[SecurityActionResult],
)
def admin_security_revoke_session_v2(
    session_token: str,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Uzaktan oturum sonlandır. Jinja: admin.py:5667-5693."""
    from app.services.security_monitor import revoke_session_by_token

    ok = revoke_session_by_token(db, session_token=session_token, by_user_id=user.id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "session_not_found", "message": "Oturum bulunamadı."},
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="active_session",
        request=request,
        details={"action": "revoke", "session_token_prefix": session_token[:8]},
    )
    return MutationResponse[SecurityActionResult](
        data=SecurityActionResult(message="Oturum kapatıldı."),
        invalidate=_SECURITY_SESSIONS_INVALIDATE,
    )


@router.post(
    "/security-monitor/ips/block",
    response_model=MutationResponse[SecurityActionResult],
)
def admin_security_block_ip_v2(
    body: IpBlockBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Manuel IP blok ekle/uzat (1-720 saat). Jinja: admin.py:5696-5728."""
    from app.services.security_monitor import block_ip_manual

    ip_clean = (body.ip or "").strip()[:64]
    if not ip_clean:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "code": "ip_required", "message": "IP boş olamaz."},
        )
    hours = max(1, min(int(body.hours or 1), 24 * 30))
    block_ip_manual(db, ip=ip_clean, hours=hours, note=body.note, by_user_id=user.id)
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="suspicious_ip",
        request=request,
        details={"action": "block", "ip": ip_clean, "hours": hours, "note": (body.note or "")[:100]},
    )
    return MutationResponse[SecurityActionResult](
        data=SecurityActionResult(message=f"IP engellendi: {ip_clean}"),
        invalidate=_SECURITY_SESSIONS_INVALIDATE,
    )


@router.post(
    "/security-monitor/ips/unblock",
    response_model=MutationResponse[SecurityActionResult],
)
def admin_security_unblock_ip_v2(
    body: IpUnblockBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """IP blok'unu kaldır. Jinja: admin.py:5731-5758."""
    from app.services.security_monitor import unblock_ip

    ip_clean = (body.ip or "").strip()[:64]
    ok = unblock_ip(db, ip=ip_clean)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "ip_not_found", "message": "IP kaydı yok."},
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="suspicious_ip",
        request=request,
        details={"action": "unblock", "ip": ip_clean},
    )
    return MutationResponse[SecurityActionResult](
        data=SecurityActionResult(message=f"IP serbest: {ip_clean}"),
        invalidate=_SECURITY_SESSIONS_INVALIDATE,
    )


@router.post(
    "/security-monitor/impersonations/{imp_id}/end",
    response_model=MutationResponse[SecurityActionResult],
)
def admin_security_end_impersonation_v2(
    imp_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Başka adminin aktif sahte oturumunu uzaktan sonlandır. Jinja: admin.py:5628-5664."""
    from app.services.impersonation import end_session as _end_imp

    row = _end_imp(db, session_id=imp_id, end_reason="revoked", ended_by_user_id=user.id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "impersonation_not_found", "message": "Oturum bulunamadı."},
        )
    log_action(
        db,
        action=AuditAction.IMPERSONATE_REVOKED,
        actor_id=user.id,
        target_type="user",
        target_id=row.target_user_id,
        request=request,
        details={"impersonation_id": imp_id, "original_actor_id": row.actor_user_id},
    )
    return MutationResponse[SecurityActionResult](
        data=SecurityActionResult(message="Sahte oturum kapatıldı."),
        invalidate=_SECURITY_SESSIONS_INVALIDATE,
    )


# =============================================================================
# G4 — Güvenlik Kamarası: Alarmlar + Suistimal
# =============================================================================

_SECURITY_ALARMS_INVALIDATE = ["admin:security:alarms", "admin:security:overview"]
_SECURITY_ABUSE_INVALIDATE = ["admin:security:abuse", "admin:security:overview"]


@router.get("/security-monitor/alarms", response_model=AlarmsResponse)
def admin_security_alarms_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Alarm kuralları + son 72s tetiklenenler. Jinja: admin.py:5230-5254."""
    from app.services.alarm_engine import (
        list_recent_events,
        list_rules,
        unacknowledged_count,
    )

    rules = list_rules(db)
    events = list_recent_events(db, hours=72, limit=50)
    return AlarmsResponse(
        rules=[
            AlarmRuleItem(
                id=r.id, key=r.key, name=r.name, description=r.description,
                threshold=r.threshold, cooldown_minutes=r.cooldown_minutes,
                enabled=r.enabled, channels=r.channels,
                last_triggered_at=r.last_triggered_at, last_value=r.last_value,
            )
            for r in rules
        ],
        events=[AlarmEventItem(**e) for e in events],
        unack_count=unacknowledged_count(db),
    )


@router.post(
    "/security-monitor/alarms/scan",
    response_model=MutationResponse[AlarmScanResult],
)
def admin_security_alarms_scan_v2(
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tüm kuralları anlık değerlendir. Jinja: admin.py:5257-5280."""
    from app.services.alarm_engine import evaluate_all

    results = evaluate_all(db)
    triggered = sum(1 for r in results if r.triggered)
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="alarm_scan",
        request=request,
        details={"triggered": triggered, "total_rules": len(results)},
    )
    return MutationResponse[AlarmScanResult](
        data=AlarmScanResult(
            message=f"Tarama tamam — {triggered} alarm tetiklendi",
            triggered=triggered, total_rules=len(results),
        ),
        invalidate=_SECURITY_ALARMS_INVALIDATE,
    )


@router.post(
    "/security-monitor/alarms/{event_id}/ack",
    response_model=MutationResponse[SecurityActionResult],
)
def admin_security_alarms_ack_v2(
    event_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Alarm olayını gördüm olarak işaretle. Jinja: admin.py:5283-5301."""
    from app.services.alarm_engine import acknowledge

    row = acknowledge(db, event_id=event_id, user_id=user.id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "alarm_not_found", "message": "Alarm bulunamadı."},
        )
    return MutationResponse[SecurityActionResult](
        data=SecurityActionResult(message="Alarm onaylandı."),
        invalidate=_SECURITY_ALARMS_INVALIDATE,
    )


@router.post(
    "/security-monitor/alarms/rules/{rule_id}/update",
    response_model=MutationResponse[SecurityActionResult],
)
def admin_security_alarms_update_rule_v2(
    rule_id: int,
    body: AlarmRuleUpdateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Alarm kuralı eşik/cooldown/enabled/kanal güncelle. Jinja: admin.py:5304-5342."""
    from app.services.alarm_engine import update_rule

    row = update_rule(
        db, rule_id=rule_id, threshold=body.threshold,
        cooldown_minutes=body.cooldown_minutes, enabled=body.enabled,
        channels=body.channels,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "alarm_rule_not_found", "message": "Kural bulunamadı."},
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="alarm_rule",
        target_id=rule_id,
        request=request,
        details={
            "key": row.key, "threshold": body.threshold,
            "cooldown_minutes": body.cooldown_minutes, "enabled": body.enabled,
        },
    )
    return MutationResponse[SecurityActionResult](
        data=SecurityActionResult(message="Kural güncellendi."),
        invalidate=_SECURITY_ALARMS_INVALIDATE,
    )


@router.get("/security-monitor/abuse", response_model=AbuseResponse)
def admin_security_abuse_v2(
    only_open: int = Query(1),
    kind: str | None = Query(None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Kötüye kullanım sinyalleri. Jinja: admin.py:5482-5521."""
    from app.services.abuse_detection import list_signals, open_signal_count
    from app.services.abuse_remediation import ACTION_BUTTON_LABELS_TR
    from app.models import (
        ABUSE_KIND_DESCRIPTIONS_TR,
        ABUSE_KIND_LABELS_TR,
        ABUSE_SEVERITY_BADGE_COLOR,
        ABUSE_SEVERITY_LABELS_TR,
    )

    signals = list_signals(db, only_open=bool(only_open), kind=kind, limit=200)
    return AbuseResponse(
        signals=[AbuseSignalItem(**s) for s in signals],
        open_count=open_signal_count(db),
        filter_only_open=bool(only_open),
        filter_kind=kind,
        meta=AbuseMeta(
            kind_labels=dict(ABUSE_KIND_LABELS_TR),
            kind_descriptions=dict(ABUSE_KIND_DESCRIPTIONS_TR),
            severity_labels=dict(ABUSE_SEVERITY_LABELS_TR),
            severity_colors=dict(ABUSE_SEVERITY_BADGE_COLOR),
            action_button_labels=dict(ACTION_BUTTON_LABELS_TR),
        ),
    )


@router.post(
    "/security-monitor/abuse/scan",
    response_model=MutationResponse[AbuseScanResult],
)
def admin_security_abuse_scan_v2(
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tüm dedektörleri çalıştır, sinyalleri upsert et. Jinja: admin.py:5524-5546."""
    from app.services.abuse_detection import run_all

    summary = run_all(db)
    total = sum(summary.values())
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="abuse_scan",
        request=request,
        details={"manual_scan": True, "summary": summary, "total_hits": total},
    )
    return MutationResponse[AbuseScanResult](
        data=AbuseScanResult(
            message=f"Tarama tamam — {total} sinyal değerlendirildi",
            summary=summary, total=total,
        ),
        invalidate=_SECURITY_ABUSE_INVALIDATE,
    )


@router.post(
    "/security-monitor/abuse/{signal_id}/resolve",
    response_model=MutationResponse[SecurityActionResult],
)
def admin_security_abuse_resolve_v2(
    signal_id: int,
    body: AbuseResolveBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Sinyali çözüldü olarak işaretle (aksiyonsuz). Jinja: admin.py:5549-5578."""
    from app.services.abuse_detection import resolve_signal

    row = resolve_signal(
        db, signal_id=signal_id, resolved_by_user_id=user.id, note=(body.note or None)
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "abuse_signal_not_found", "message": "Sinyal bulunamadı."},
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="abuse_signal",
        target_id=signal_id,
        request=request,
        details={"action": "resolve", "kind": row.kind, "note": (body.note or "")[:200]},
    )
    return MutationResponse[SecurityActionResult](
        data=SecurityActionResult(message="Sinyal çözüldü."),
        invalidate=_SECURITY_ABUSE_INVALIDATE,
    )


@router.post(
    "/security-monitor/abuse/{signal_id}/remediate",
    response_model=MutationResponse[AbuseRemediateResult],
)
def admin_security_abuse_remediate_v2(
    signal_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Sinyal türüne göre toplu aksiyon uygula + otomatik resolve. Jinja: admin.py:5582-5625."""
    from app.services.abuse_remediation import auto_remediate_signal

    result = auto_remediate_signal(db, signal_id=signal_id, by_user_id=user.id, autocommit=True)
    if not result.ok:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid", "code": "remediation_failed",
                "message": f"Aksiyon yapılamadı: {result.note}",
            },
        )
    log_action(
        db,
        action=AuditAction.ABUSE_REMEDIATION,
        actor_id=user.id,
        target_type="abuse_signal",
        target_id=signal_id,
        request=request,
        details={
            "kind": result.kind, "action": result.action,
            "affected_count": result.affected_count, "note": result.note[:200],
        },
    )
    return MutationResponse[AbuseRemediateResult](
        data=AbuseRemediateResult(
            message=f"{result.note} (sinyal otomatik çözüldü)",
            ok=result.ok, kind=result.kind, action=result.action,
            affected_count=result.affected_count, note=result.note,
        ),
        invalidate=_SECURITY_ABUSE_INVALIDATE,
    )


# =============================================================================
# Süper Admin — AI Ayarları (Gemini anahtarları + modelleri, merkezi/şifreli)
# =============================================================================

_AI_SETTINGS_INVALIDATE = ["admin:settings:ai"]


@router.get("/settings/ai", response_model=AiSettingsResponse)
def admin_ai_settings_get_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Gemini AI ayarları — anahtarlar maskeli, modeller düz. Kaynak (db/env/default)."""
    from app.services.system_secrets import ai_settings_status
    return AiSettingsResponse(items=[AiSettingItem(**s) for s in ai_settings_status(db)])


@router.post("/settings/ai", response_model=MutationResponse[AiSettingsResponse])
def admin_ai_settings_set_v2(
    body: SetAiSettingBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Gemini anahtarı/modeli kaydet/güncelle (anahtarlar şifreli). Tüm sistem kullanır."""
    from app.services.system_secrets import (
        CONFIG_NAMES, SECRET_NAMES, ai_settings_status, set_secret,
    )

    name = (body.name or "").strip()
    if name not in SECRET_NAMES and name not in CONFIG_NAMES:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "code": "invalid_setting",
                    "message": "Geçersiz ayar adı."},
        )
    value = (body.value or "").strip()
    if not value:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "code": "empty_value",
                    "message": "Değer boş olamaz."},
        )

    set_secret(db, name, value, actor_user_id=user.id)
    log_action(
        db,
        action=AuditAction.SYSTEM_SETTING_UPDATE,
        actor_id=user.id,
        target_type="system_secret",
        request=request,
        details={"name": name, "action": "set"},  # değer ASLA loglanmaz
    )
    return MutationResponse[AiSettingsResponse](
        data=AiSettingsResponse(items=[AiSettingItem(**s) for s in ai_settings_status(db)]),
        invalidate=_AI_SETTINGS_INVALIDATE,
    )


@router.post("/settings/ai/{name}/delete", response_model=MutationResponse[AiSettingsResponse])
def admin_ai_settings_delete_v2(
    name: str,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Gemini anahtarı/model override'ını sil (DB'den). Varsa env/default'a döner."""
    from app.services.system_secrets import (
        CONFIG_NAMES, SECRET_NAMES, ai_settings_status, delete_secret,
    )

    n = (name or "").strip()
    if n not in SECRET_NAMES and n not in CONFIG_NAMES:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "code": "invalid_setting",
                    "message": "Geçersiz ayar adı."},
        )
    delete_secret(db, n)
    log_action(
        db,
        action=AuditAction.SYSTEM_SETTING_UPDATE,
        actor_id=user.id,
        target_type="system_secret",
        request=request,
        details={"name": n, "action": "delete"},
    )
    return MutationResponse[AiSettingsResponse](
        data=AiSettingsResponse(items=[AiSettingItem(**s) for s in ai_settings_status(db)]),
        invalidate=_AI_SETTINGS_INVALIDATE,
    )


# =============================================================================
# Süper Admin — Üyelik/Fiyat yapılandırması (tek kaynak: services/pricing.py)
# =============================================================================

_PRICING_INVALIDATE = ["admin:settings:pricing", "pricing"]

_PRICING_EDITABLE_KEYS = (
    "annual_paid_months", "solo_trial_days", "solo_free_students", "solo_bands",
    "solo_over_cap_per_student", "institution_trial_days", "institution_free_teachers",
    "institution_free_students", "institution_students_per_coach", "institution_tiers",
)


def _pricing_editable(cfg: dict) -> dict:
    return {k: cfg[k] for k in _PRICING_EDITABLE_KEYS if k in cfg}


@router.get("/settings/pricing", response_model=PricingAdminResponse)
def admin_pricing_get_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Etkin üyelik/fiyat yapısı (override dahil) + kod varsayılanı (sıfırlama için)."""
    from app.services import pricing
    return PricingAdminResponse(
        config=_pricing_editable(pricing.get_effective_config()),
        defaults=_pricing_editable(pricing.defaults()),
    )


@router.post("/settings/pricing", response_model=MutationResponse[PricingAdminResponse])
def admin_pricing_set_v2(
    body: PricingConfigBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Üyelik/fiyat override'ını kaydet. Tüm sistem (/pricing, Paket, entitlement) buradan okur."""
    from app.services import app_settings, pricing

    payload = body.model_dump()
    # Basit doğrulama: negatif fiyat/sayı yok; en az 1 bant + 1 tier.
    if not payload["solo_bands"] or not payload["institution_tiers"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "code": "invalid_pricing",
                    "message": "En az bir öğrenci bandı ve bir kurum tier'ı gerekir."},
        )
    for b in payload["solo_bands"]:
        if b["max_students"] <= 0 or b["monthly"] < 0:
            raise HTTPException(status_code=400, detail={"error": "validation", "code": "invalid_pricing",
                    "message": "Bant değerleri geçersiz."})
    for t in payload["institution_tiers"]:
        if t["per_coach_monthly"] < 0 or t["min_coaches"] <= 0:
            raise HTTPException(status_code=400, detail={"error": "validation", "code": "invalid_pricing",
                    "message": "Tier değerleri geçersiz."})

    app_settings.set_json(db, pricing.PRICING_KEY, payload, actor_user_id=user.id)
    log_action(
        db, action=AuditAction.SYSTEM_SETTING_UPDATE, actor_id=user.id,
        target_type="pricing", request=request, details={"action": "set"},
    )
    return MutationResponse[PricingAdminResponse](
        data=PricingAdminResponse(
            config=_pricing_editable(pricing.get_effective_config()),
            defaults=_pricing_editable(pricing.defaults()),
        ),
        invalidate=_PRICING_INVALIDATE,
    )


# =============================================================================
# Süper Admin — İletişim Talepleri (kurumsal/genel form gönderimleri)
# =============================================================================

_CONTACT_INVALIDATE = ["admin:contact-requests"]


def _contact_item(cr) -> ContactRequestItem:
    import re

    from app.models.contact_request import (
        CONTACT_SOURCE_LABELS_TR,
        CONTACT_STATUS_LABELS_TR,
    )
    linked_user_id = None
    if cr.source == "subscription_request" and cr.message:
        m = re.search(r"koç_id=(\d+)", cr.message)
        if m:
            linked_user_id = int(m.group(1))
    return ContactRequestItem(
        id=cr.id,
        created_at=cr.created_at.isoformat() if cr.created_at else "",
        name=cr.name,
        email=cr.email,
        phone=cr.phone,
        institution_name=cr.institution_name,
        coach_count=cr.coach_count,
        message=cr.message,
        source=cr.source,
        source_label=CONTACT_SOURCE_LABELS_TR.get(cr.source, cr.source),
        status=cr.status,
        status_label=CONTACT_STATUS_LABELS_TR.get(cr.status, cr.status),
        handled_by_id=cr.handled_by_id,
        handled_at=cr.handled_at.isoformat() if cr.handled_at else None,
        admin_note=cr.admin_note,
        linked_user_id=linked_user_id,
    )


@router.get("/contact-requests", response_model=ContactRequestListResponse)
def admin_contact_requests_list_v2(
    status: str | None = Query(default=None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """İletişim talepleri (en yeni üstte) + durum sayımları."""
    from app.models.contact_request import (
        CONTACT_STATUS_CLOSED,
        CONTACT_STATUS_CONTACTED,
        CONTACT_STATUS_LABELS_TR,
        CONTACT_STATUS_NEW,
        ContactRequest,
    )

    q = db.query(ContactRequest)
    if status in (CONTACT_STATUS_NEW, CONTACT_STATUS_CONTACTED, CONTACT_STATUS_CLOSED):
        q = q.filter(ContactRequest.status == status)
    rows = q.order_by(ContactRequest.created_at.desc()).limit(500).all()

    def _count(st: str) -> int:
        return db.query(ContactRequest).filter(ContactRequest.status == st).count()

    counts = {
        "new": _count(CONTACT_STATUS_NEW),
        "contacted": _count(CONTACT_STATUS_CONTACTED),
        "closed": _count(CONTACT_STATUS_CLOSED),
    }
    counts["total"] = counts["new"] + counts["contacted"] + counts["closed"]

    return ContactRequestListResponse(
        items=[_contact_item(r) for r in rows],
        counts=counts,
        status_labels=dict(CONTACT_STATUS_LABELS_TR),
    )


@router.post(
    "/contact-requests/{request_id}",
    response_model=MutationResponse[ContactRequestMutationResult],
)
def admin_contact_request_update_v2(
    request_id: int,
    body: ContactRequestUpdateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Talebin durumunu güncelle + yönetim notu ekle."""
    from datetime import datetime, timezone

    from app.models.contact_request import (
        CONTACT_STATUS_CLOSED,
        CONTACT_STATUS_CONTACTED,
        CONTACT_STATUS_NEW,
        ContactRequest,
    )

    cr = db.get(ContactRequest, request_id)
    if cr is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "contact_request_not_found",
                    "message": "İletişim talebi bulunamadı."},
        )
    if body.status not in (CONTACT_STATUS_NEW, CONTACT_STATUS_CONTACTED, CONTACT_STATUS_CLOSED):
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "code": "invalid_status",
                    "message": "Geçersiz durum."},
        )

    cr.status = body.status
    cr.admin_note = (body.admin_note or "").strip() or None
    cr.handled_by_id = user.id
    cr.handled_at = datetime.now(timezone.utc)
    db.commit()

    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="contact_request", target_id=cr.id, request=request,
        details={"status": cr.status},
    )
    return MutationResponse[ContactRequestMutationResult](
        data=ContactRequestMutationResult(id=cr.id, status=cr.status),
        invalidate=_CONTACT_INVALIDATE,
    )


@router.post("/settings/pricing/reset", response_model=MutationResponse[PricingAdminResponse])
def admin_pricing_reset_v2(
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Override'ı sil → kod varsayılanına dön."""
    from app.services import app_settings, pricing
    app_settings.delete(db, pricing.PRICING_KEY)
    log_action(
        db, action=AuditAction.SYSTEM_SETTING_UPDATE, actor_id=user.id,
        target_type="pricing", request=request, details={"action": "reset"},
    )
    return MutationResponse[PricingAdminResponse](
        data=PricingAdminResponse(
            config=_pricing_editable(pricing.get_effective_config()),
            defaults=_pricing_editable(pricing.defaults()),
        ),
        invalidate=_PRICING_INVALIDATE,
    )
