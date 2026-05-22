"""API v2 — Super Admin şemaları (Dalga 6 Paket 1+).

KURAL: Veri yapısı/sorgular `app/routes/admin.py` + `services/tenant_health.py`
+ `services/audit.py` ile **birebir aynı** — sadece JSON serialization için
Pydantic'e sarılır. UI özgür ama backend payload aynı.

Paket 1 kapsamı (dashboard foundation):
  - Counts, health summary, top unhealthy
  - Independent teacher activity (login-bazlı 4-band heuristik)
  - Recent audit (son 10)
  - Failed logins last 24h

Sonraki paketler bu dosyaya kendi modellerini ekleyecek.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# Ortak — health level + audit action literals
# =============================================================================


HealthLevelLiteral = Literal["healthy", "watch", "risk", "critical"]


# =============================================================================
# Dashboard — counts bloğu
# =============================================================================


class AdminDashboardCounts(BaseModel):
    """Jinja admin.py admin_dashboard() `counts` dict ile birebir."""
    institutions: int
    active_institutions: int
    teachers: int
    students: int
    parents: int
    institution_admins: int
    super_admins: int
    independent_teachers: int


# =============================================================================
# Dashboard — health summary (kurum sağlığı)
# =============================================================================


class HealthSummary(BaseModel):
    """tenant_health.churn_summary() çıktısı — 4 bant sayım + agregat."""
    healthy: int
    watch: int
    risk: int
    critical: int
    unhealthy_total: int
    needs_attention: int


class HealthIndicatorItem(BaseModel):
    """tenant_health.HealthIndicator — neden bayrak çıktı."""
    code: str
    title: str
    detail: str
    weight: int


class InstitutionBriefForHealth(BaseModel):
    id: int
    name: str
    slug: str
    plan: str | None = None
    is_active: bool


class HealthAssessmentItem(BaseModel):
    """tenant_health.HealthAssessment — dashboard top-3 ve sonraki paketlerde liste."""
    institution: InstitutionBriefForHealth
    score: int
    level: HealthLevelLiteral
    level_label: str
    level_emoji: str
    level_color: str  # "rose" / "amber" / "yellow" / "emerald"
    indicators: list[HealthIndicatorItem]
    teacher_count: int
    student_count: int
    active_teacher_count_7d: int
    active_student_count_7d: int
    last_teacher_login: datetime | None = None
    last_student_login: datetime | None = None
    weekly_completion_rate: int | None = None
    teacher_active_pct: int | None = None
    student_active_pct: int | None = None


# =============================================================================
# Dashboard — bağımsız öğretmen aktivite (login-bazlı heuristik)
# =============================================================================


class IndependentTeacherActivitySummary(BaseModel):
    """_independent_teacher_activity() summary dict ile birebir."""
    healthy: int
    watch: int
    risk: int
    critical: int
    unhealthy_total: int
    total: int


class IndependentTeacherBrief(BaseModel):
    id: int
    full_name: str
    email: str


class IndependentTeacherRiskRow(BaseModel):
    """_independent_teacher_activity() rows dict ile birebir."""
    user: IndependentTeacherBrief
    band: HealthLevelLiteral
    days_since_login: int | None = None
    label: str  # "5g önce" / "bugün" / "hiç giriş yok"
    last_login_at: datetime | None = None


# =============================================================================
# Dashboard — recent audit
# =============================================================================


class AuditLogItem(BaseModel):
    """AuditLog tablosu satırı — UI rendering için."""
    id: int
    actor_id: int | None = None
    email_attempted: str | None = None
    action: str  # AuditAction.value
    action_label: str  # AUDIT_ACTION_LABELS[action]
    target_type: str | None = None
    target_id: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details_json: str | None = None
    created_at: datetime
    via_admin: int | None = None  # impersonation marker (details_json._via_admin)


# =============================================================================
# Dashboard response
# =============================================================================


class AdminDashboardResponse(BaseModel):
    """GET /api/v2/admin/dashboard yanıtı.

    Eşdeğer Jinja: admin.py:150-211 (admin_dashboard).
    """
    counts: AdminDashboardCounts
    failed_logins_24h: int
    health_summary: HealthSummary
    top_unhealthy: list[HealthAssessmentItem]
    teacher_activity_summary: IndependentTeacherActivitySummary
    top_teacher_risk: list[IndependentTeacherRiskRow]
    recent_audits: list[AuditLogItem]


# =============================================================================
# P2 — Institutions
# =============================================================================


InstitutionSortLiteral = Literal["health", "name", "created"]
InstitutionFilterLevelLiteral = Literal["unhealthy", "critical"]


class InstitutionListItem(BaseModel):
    """list_institutions tablosu satırı = HealthAssessment + plan + slug."""
    institution: InstitutionBriefForHealth
    score: int
    level: HealthLevelLiteral
    level_label: str
    level_emoji: str
    level_color: str
    indicators: list[HealthIndicatorItem]
    teacher_count: int
    student_count: int
    teacher_active_pct: int | None = None
    student_active_pct: int | None = None
    weekly_completion_rate: int | None = None
    last_teacher_login: datetime | None = None
    last_student_login: datetime | None = None


class InstitutionListResponse(BaseModel):
    """GET /api/v2/admin/institutions yanıtı."""
    items: list[InstitutionListItem]
    summary: HealthSummary
    sort: InstitutionSortLiteral
    filter_level: InstitutionFilterLevelLiteral | None = None


class InstitutionCreateBody(BaseModel):
    """POST /api/v2/admin/institutions body."""
    name: str
    slug: str | None = None
    contact_email: str | None = None
    plan: str = "free"


class InstitutionEditBody(BaseModel):
    """POST /api/v2/admin/institutions/{id} body."""
    name: str
    contact_email: str | None = None
    plan: str = "free"
    is_active: bool = True


class InstitutionDetailBrief(BaseModel):
    """Detay sayfası için kurum kimliği — slug+email+plan+is_active+created_at."""
    id: int
    name: str
    slug: str
    contact_email: str | None = None
    plan: str
    is_active: bool
    created_at: datetime | None = None


class InstitutionUserBrief(BaseModel):
    """institution_detail içindeki yönetici/öğretmen listesi satırı."""
    id: int
    email: str
    full_name: str
    is_active: bool
    last_login_at: datetime | None = None


class InstitutionDetailResponse(BaseModel):
    """GET /api/v2/admin/institutions/{id} yanıtı."""
    institution: InstitutionDetailBrief
    health: HealthAssessmentItem
    institution_admins: list[InstitutionUserBrief]
    teachers: list[InstitutionUserBrief]
    student_count: int


class InstitutionMutationResult(BaseModel):
    """Create/edit/delete sonrası dönen kurum + flash mesajı."""
    institution: InstitutionDetailBrief | None = None
    message: str
    affected_users: int = 0  # delete için


# =============================================================================
# P2 — Account history (poly: institution|user)
# =============================================================================


AccountOwnerTypeLiteral = Literal["institution", "user"]
AccountRecordTypeLiteral = Literal["plan", "invoice"]


class AccountHistoryEvent(BaseModel):
    """account_history.HistoryEvent dataclass'ı ile birebir."""
    record_type: AccountRecordTypeLiteral
    record_id: int
    when: datetime
    title: str
    subtitle: str
    badge_label: str
    badge_color: str
    detail: dict  # JSON-serialize edilebilir; UI sadece tanıdığı alanları okur
    archived: bool
    archived_at: datetime | None = None
    archive_note: str | None = None


class AccountHistoryResponse(BaseModel):
    """GET /api/v2/admin/account-history/{owner_type}/{owner_id} yanıtı.

    Eşdeğer Jinja: services/account_history.account_history() dict.
    """
    owner_type: AccountOwnerTypeLiteral
    owner_id: int
    owner_name: str | None = None
    window_start: datetime
    events: list[AccountHistoryEvent]
    total_count: int
    archived_count: int
    older_count: int
    include_archived: bool
    years: int


class AccountArchiveBody(BaseModel):
    """POST /api/v2/admin/account-history/archive body."""
    record_type: AccountRecordTypeLiteral
    record_id: int
    note: str | None = None


class AccountUnarchiveBody(BaseModel):
    record_type: AccountRecordTypeLiteral
    record_id: int


class AccountBulkArchiveBody(BaseModel):
    owner_type: AccountOwnerTypeLiteral
    owner_id: int
    years: int = 3
    note: str | None = None


class AccountArchiveResult(BaseModel):
    """archive_record / unarchive_record / bulk_archive_older_than dict çıktısı."""
    ok: bool
    record_type: AccountRecordTypeLiteral | None = None
    record_id: int | None = None
    archived_at: str | None = None
    error: str | None = None
    # bulk için
    plan_count: int = 0
    invoice_count: int = 0
    total: int = 0
    message: str | None = None


# =============================================================================
# P2 — Tenant backup
# =============================================================================


class InstitutionBackupCounts(BaseModel):
    """export_tenant() counts dict ile birebir."""
    users: int
    teachers: int
    students: int
    books: int
    sections: int
    tasks: int
    task_items: int
    notifications: int
    audit_logs: int
    credit_accounts: int
    usage_events: int
    admin_weekly_digests: int
    feature_flag_overrides: int
    quota_overrides: int
    parent_links: int


class InstitutionBackupSummary(BaseModel):
    """JSON download yerine UI'da preview için özet response.
    Asıl indirme `/api/v2/admin/institutions/{id}/backup.json` üzerinden raw JSON."""
    institution: InstitutionDetailBrief
    schema_version: int
    exported_at: datetime
    audit_lookback_days: int
    notification_lookback_days: int
    counts: InstitutionBackupCounts
    size_bytes: int


# =============================================================================
# P3 — Users
# =============================================================================


RoleLiteral = Literal[
    "super_admin", "institution_admin", "teacher", "student", "parent",
]


class InstitutionRefBrief(BaseModel):
    """User listesi/detayında kurum referansı."""
    id: int
    name: str
    slug: str


class AdminUserListItem(BaseModel):
    """admin/users tablosu satırı — User + institution_label."""
    id: int
    email: str
    full_name: str
    role: RoleLiteral
    role_label: str
    institution: InstitutionRefBrief | None = None
    is_active: bool
    last_login_at: datetime | None = None
    last_login_ip: str | None = None
    locked_until: datetime | None = None
    failed_login_count: int = 0
    must_change_password: bool = False
    created_at: datetime | None = None


class AdminUserListResponse(BaseModel):
    """GET /api/v2/admin/users yanıtı."""
    items: list[AdminUserListItem]
    total_returned: int
    truncated: bool
    institutions: list[InstitutionRefBrief]
    filter_role: str | None = None
    filter_institution_id: int | None = None
    filter_q: str | None = None


class AdminUserCreateBody(BaseModel):
    full_name: str
    email: str
    role: RoleLiteral
    institution_id: int | None = None


class AdminUserCreateResult(BaseModel):
    """Yeni kullanıcı + tek seferlik geçici şifre (UI dialog "Kopyala")."""
    user: AdminUserListItem
    temp_password: str
    must_change_password: bool = True


class AdminUserEditBody(BaseModel):
    full_name: str
    email: str
    institution_id: int | None = None
    is_active: bool = True


class AdminUserChangeRoleBody(BaseModel):
    new_role: RoleLiteral
    institution_id: int | None = None


class AdminUserDetailResponse(BaseModel):
    """GET /api/v2/admin/users/{id} yanıtı."""
    target: AdminUserListItem
    institutions: list[InstitutionRefBrief]
    recent_audits: list[AuditLogItem]
    password_changed_at: datetime | None = None
    is_self: bool  # rol/delete YASAK göstergesi


class AdminUserMutationResult(BaseModel):
    """Edit/delete/change-role/reset-password sonrası dönen User + flash."""
    user: AdminUserListItem | None = None
    message: str
    temp_password: str | None = None  # reset-password için


# =============================================================================
# P3 — Impersonate
# =============================================================================


class AdminImpersonateBody(BaseModel):
    reason: str  # 10-200 char, server validate eder


class AdminImpersonateResult(BaseModel):
    """Impersonate başarılı yanıt.

    redirect_url: hedef rolün ana sayfası. Backend session set'ler
    (Jinja-compatible SessionMiddleware cookie); frontend location'ı kullanır.
    """
    impersonation_id: int
    actor_id: int
    target_id: int
    target_full_name: str
    target_role: RoleLiteral
    expires_at: datetime
    redirect_url: str


class AdminImpersonateEndResult(BaseModel):
    admin_id: int
    admin_full_name: str
    target_user_id: int | None = None
    redirect_url: str


# =============================================================================
# P3 — Independent teachers list
# =============================================================================


class AdminIndependentTeachersResponse(BaseModel):
    """GET /api/v2/admin/independent-teachers — login-bazlı 4-band."""
    summary: IndependentTeacherActivitySummary
    rows: list[IndependentTeacherRiskRow]


# =============================================================================
# P4 — Audit list (pagination + filter)
# =============================================================================


class AuditActorBrief(BaseModel):
    id: int
    email: str
    full_name: str


class AuditListItem(BaseModel):
    """Audit list satırı — AuditLogItem + actor info + via_admin parsed details."""
    id: int
    action: str
    action_label: str
    actor_id: int | None = None
    actor: AuditActorBrief | None = None
    email_attempted: str | None = None
    target_type: str | None = None
    target_id: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details_parsed: dict | None = None
    via_admin_id: int | None = None
    via_admin: AuditActorBrief | None = None
    created_at: datetime


class AuditListResponse(BaseModel):
    """GET /api/v2/admin/audit yanıtı.

    Pagination: 50 per_page (Jinja birebir).
    """
    items: list[AuditListItem]
    total: int
    page: int
    total_pages: int
    per_page: int
    filter_action: str | None = None
    filter_actor_id: int | None = None
    filter_start_date: str | None = None
    filter_end_date: str | None = None
    all_actions: list[dict]  # [{value, label}, ...]


# =============================================================================
# P4 — System health
# =============================================================================


class CronStatusItem(BaseModel):
    """system_health.CronStatus — Pydantic."""
    job_key: str
    description: str | None = None
    dow_label: str  # "Pzt" / "Her gün" — schedule.dow_label
    time_label: str  # "06:00"
    enabled: bool
    last_run_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    hours_since_run: float | None = None
    health: str  # 'ok' | 'warn' | 'crit' | 'never' | 'disabled'


class DispatcherStatusInfo(BaseModel):
    queued_count: int
    failed_count: int
    oldest_queued_at: datetime | None = None
    oldest_queued_age_hours: float | None = None
    health: str  # 'ok' | 'warn' | 'crit'


class DatabaseStatusInfo(BaseModel):
    file_path: str | None = None
    file_size_mb: float | None = None
    table_counts: dict[str, int]
    health: str


class SystemHealthResponse(BaseModel):
    """GET /api/v2/admin/system-health yanıtı."""
    crons: list[CronStatusItem]
    dispatcher: DispatcherStatusInfo | None = None
    database: DatabaseStatusInfo | None = None
    overall_health: str  # 'ok' | 'warn' | 'crit'


# =============================================================================
# P4 — Announcements
# =============================================================================


AnnouncementSeverityLiteral = Literal["info", "warn", "critical"]
AnnouncementAudienceLiteral = Literal[
    "all", "super_admin", "institution_admin", "teacher", "student", "parent",
]


class AnnouncementItem(BaseModel):
    id: int
    title: str | None = None
    message: str
    severity: AnnouncementSeverityLiteral
    severity_label: str
    audience: AnnouncementAudienceLiteral
    audience_label: str
    starts_at: datetime
    ends_at: datetime | None = None
    dismissible: bool
    is_active_now: bool
    created_by: int | None = None
    created_at: datetime


class AnnouncementCreateBody(BaseModel):
    title: str | None = None
    message: str
    severity: AnnouncementSeverityLiteral = "info"
    audience: AnnouncementAudienceLiteral = "all"
    starts_at: str | None = None  # ISO datetime
    ends_at: str | None = None
    dismissible: bool = True


class AnnouncementSeverityOption(BaseModel):
    value: AnnouncementSeverityLiteral
    label: str


class AnnouncementAudienceOption(BaseModel):
    value: AnnouncementAudienceLiteral
    label: str


class AnnouncementsListResponse(BaseModel):
    """GET /api/v2/admin/announcements yanıtı."""
    items: list[AnnouncementItem]
    severities: list[AnnouncementSeverityOption]
    audiences: list[AnnouncementAudienceOption]


class AnnouncementMutationResult(BaseModel):
    announcement: AnnouncementItem | None = None
    message: str


# =============================================================================
# P4 — KVKK
# =============================================================================


KvkkRequestKindLiteral = Literal["export", "delete", "rectification"]
KvkkRequestStatusLiteral = Literal[
    "pending", "processing", "completed", "cancelled", "rejected",
]


class KvkkSummary(BaseModel):
    """kvkk.request_summary() dict — 5 status sayım + total."""
    total: int
    pending: int = 0
    processing: int = 0
    completed: int = 0
    cancelled: int = 0
    rejected: int = 0


class KvkkRequestUserBrief(BaseModel):
    id: int
    email: str
    full_name: str


class KvkkRequestItem(BaseModel):
    """DataSubjectRequest satırı."""
    id: int
    kind: KvkkRequestKindLiteral
    kind_label: str
    status: KvkkRequestStatusLiteral
    status_label: str
    target_user: KvkkRequestUserBrief | None = None
    requester_user: KvkkRequestUserBrief | None = None
    reason: str | None = None
    admin_note: str | None = None
    process_after: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime


class KvkkDataInventoryItem(BaseModel):
    """services/kvkk.DataInventoryItem — UI envanter tablosu."""
    table_name: str
    label: str
    contains_pii: bool
    retention_days: int | None = None
    legal_basis: str
    purpose: str


class KvkkDashboardResponse(BaseModel):
    """GET /api/v2/admin/kvkk yanıtı."""
    summary: KvkkSummary
    pending_rows: list[KvkkRequestItem]
    recent_rows: list[KvkkRequestItem]
    data_inventory: list[KvkkDataInventoryItem]


class KvkkRejectBody(BaseModel):
    note: str = ""


class KvkkMutationResult(BaseModel):
    request: KvkkRequestItem | None = None
    message: str


# =============================================================================
# P5 — Usage (owner-pattern: institution|user)
# =============================================================================


UsageTabLiteral = Literal["institutions", "independents"]
UsageOwnerTypeLiteral = Literal["institution", "user"]


class UsageAccountInfo(BaseModel):
    """CreditAccount durumu — usage tablosu satırı."""
    plan_code: str
    used_credits: int
    allocated_credits: int
    bonus_credits: int
    total_allocated: int
    remaining_credits: int
    usage_pct: int
    hard_block_enabled: bool
    blocked_until: datetime | None = None


class UsageInstitutionRow(BaseModel):
    institution_id: int
    name: str
    slug: str
    account: UsageAccountInfo


class UsageIndependentRow(BaseModel):
    user_id: int
    full_name: str
    email: str
    account: UsageAccountInfo


class UsageTotals(BaseModel):
    inst_used: int
    inst_alloc: int
    indep_used: int
    indep_alloc: int
    grand_used: int
    grand_alloc: int


class UsageKindCost(BaseModel):
    kind: str
    label: str
    cost: int


class AdminUsageResponse(BaseModel):
    """GET /api/v2/admin/usage yanıtı."""
    period: str
    inst_rows: list[UsageInstitutionRow]
    indep_rows: list[UsageIndependentRow]
    totals: UsageTotals
    kind_costs: list[UsageKindCost]


class UsageBonusBody(BaseModel):
    bonus_amount: int


class UsageMutationResult(BaseModel):
    account: UsageAccountInfo | None = None
    message: str


# =============================================================================
# P5 — Quota
# =============================================================================


class QuotaCell(BaseModel):
    """Bir kurum × quota_key hücresi."""
    key: str
    label: str
    limit: int  # -1 sınırsız, 0 kapalı, N sayı
    current: int
    pct: int
    is_unlimited: bool
    is_at_limit: bool
    has_override: bool
    note: str | None = None


class QuotaInstitutionRow(BaseModel):
    institution_id: int
    name: str
    slug: str
    plan: str
    cells: list[QuotaCell]
    max_pct: int


class QuotaPlanRow(BaseModel):
    plan: str
    teachers: int
    students: int
    institution_admins: int


class AdminQuotaResponse(BaseModel):
    """GET /api/v2/admin/quota yanıtı."""
    rows: list[QuotaInstitutionRow]
    quota_keys: list[str]
    quota_labels: dict[str, str]
    plans: list[QuotaPlanRow]


class QuotaOverrideBody(BaseModel):
    quota_key: str
    override_value: int  # -1 / 0 / 1..1M
    note: str | None = None


class QuotaMutationResult(BaseModel):
    message: str


# =============================================================================
# P5 — Feature flags
# =============================================================================


class FeatureFlagItem(BaseModel):
    id: int
    key: str
    description: str
    enabled_globally: bool
    override_enabled_count: int
    override_disabled_count: int
    override_total: int


class FeatureFlagsListResponse(BaseModel):
    """GET /api/v2/admin/feature-flags yanıtı."""
    flags: list[FeatureFlagItem]


class FeatureFlagOverrideItem(BaseModel):
    id: int
    institution_id: int
    institution_name: str
    enabled: bool
    note: str | None = None


class FeatureFlagInstitutionOption(BaseModel):
    id: int
    name: str


class FeatureFlagDetailResponse(BaseModel):
    """GET /api/v2/admin/feature-flags/{id} yanıtı."""
    id: int
    key: str
    description: str
    enabled_globally: bool
    overrides: list[FeatureFlagOverrideItem]
    available_institutions: list[FeatureFlagInstitutionOption]


class FeatureFlagOverrideBody(BaseModel):
    institution_id: int
    enabled: bool = True
    note: str | None = None


class FeatureFlagMutationResult(BaseModel):
    message: str
    enabled_globally: bool | None = None


# =============================================================================
# P6 — Feature Catalog (Vitrin Kartları)
#
# KURAL: 8 destek servisi (feature_scoring / bandit / diversity / telemetry /
# landing_strategies / mockup_registry / feature_discovery / curator_dashboard)
# HİÇ değişmez; bu şemalar sadece servislerin döndürdüğü Python nesnelerini
# JSON'a serialize eder. Mamdani fuzzy / LinUCB / MMR / Wilson CI birebir korunur.
# =============================================================================


class EnumOption(BaseModel):
    """Filtre dropdown'ları için value+label."""
    value: str
    label: str


class StatusOption(BaseModel):
    """Durum filtresi — badge tonu dahil."""
    value: str
    label: str
    badge: str


class MockupOption(BaseModel):
    """mockup_registry.list_mockups() çıktısı."""
    key: str
    label: str
    description: str


# ---------------------------- Liste sayfası ----------------------------


class FeatureCardScoreInputs(BaseModel):
    """feature_scoring.ScoreBreakdown.inputs — 5 crisp girdi."""
    freshness: float
    priority: float
    tier_strength: float
    completeness: float
    role_match: float


class FeatureCardFiredRule(BaseModel):
    """Ateşlenen fuzzy kuralı (tooltip için)."""
    label: str
    strength: float


class FeatureCardListItem(BaseModel):
    """Liste tablosundaki tek kart + 6 katmanlı zenginleştirme.

    Jinja feature_catalog_list.html satır context'iyle birebir.
    """
    id: int
    slug: str
    title: str
    tagline: str
    accent_color: str
    domain: str
    domain_label: str
    tier: str
    tier_label: str
    status: str
    status_label: str
    status_badge: str
    strategic_priority: int
    manual_pin: bool
    manual_hide: bool
    demo_slug: str | None = None
    is_landing: bool = False
    # Katman 5 — fuzzy skor (yalnız PUBLISHED + mockup + not hidden kartlarda)
    score: int | None = None
    score_inputs: FeatureCardScoreInputs | None = None
    fired_rules: list[FeatureCardFiredRule] = []
    # Katman 6 — telemetri
    impression: int = 0
    view: int = 0
    demo_click: int = 0
    cta_click: int = 0
    # Katman 7 — bandit (öğrenme)
    bandit_obs: int = 0
    bandit_mean: float | None = None
    # Katman 8 — çeşitlilik (yalnız landing kartlarında)
    neighbor_sim: float | None = None


class FeatureCatalogListResponse(BaseModel):
    """GET /api/v2/admin/feature-catalog yanıtı."""
    cards: list[FeatureCardListItem]
    counts: dict[str, int]
    discovery_pending: int
    landing_card_count: int
    overall_diversity: float
    learning_count: int
    domains: list[EnumOption]
    tiers: list[EnumOption]
    statuses: list[StatusOption]
    status_filter: str | None = None
    domain_filter: str | None = None
    tier_filter: str | None = None
    q: str = ""


# ---------------------------- Kart formu / detay ----------------------------


class FeatureCardFormMeta(BaseModel):
    """Form dropdown verileri (domains/tiers/statuses/roles/mockups)."""
    domains: list[EnumOption]
    tiers: list[EnumOption]
    statuses: list[EnumOption]
    roles: list[str]
    mockups: list[MockupOption]


class FeatureCardFull(BaseModel):
    """Kart düzenleme formu — 26 alan + audit zaman damgaları."""
    id: int
    slug: str
    title: str
    tagline: str
    description_md: str
    icon: str
    accent_color: str
    category_icon: str
    category_label: str
    demo_duration_label: str | None = None
    mockup_type: str | None = None
    target_roles: list[str]
    benefits: list[str]
    pain_points: list[str]
    demo_slug: str | None = None
    domain: str
    tier: str
    status: str
    introduced_at: datetime | None = None
    introduced_in_commit: str | None = None
    pr_url: str | None = None
    strategic_priority: int
    manual_pin: bool
    pin_until: datetime | None = None
    manual_hide: bool
    cta_label: str
    cta_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FeatureCardFormResponse(BaseModel):
    """GET /api/v2/admin/feature-catalog/new (card=None) veya /{id}."""
    card: FeatureCardFull | None = None
    meta: FeatureCardFormMeta


class FeatureCardBody(BaseModel):
    """Kart create/update gövdesi — Jinja Form alanlarıyla aynı semantik."""
    slug: str = ""
    title: str = ""
    tagline: str = ""
    description_md: str = ""
    icon: str = "sparkles"
    accent_color: str = "#3b82f6"
    category_icon: str = "✨"
    category_label: str = ""
    demo_duration_label: str = ""
    mockup_type: str | None = None
    target_roles: list[str] = []
    benefits: list[str] = []
    pain_points: list[str] = []
    demo_slug: str = ""
    domain: str = "genel"
    tier: str = "enhancement"
    status: str = "draft"
    introduced_at: str | None = None
    introduced_in_commit: str = ""
    pr_url: str = ""
    strategic_priority: int = 3
    manual_pin: bool = False
    pin_until: str | None = None
    manual_hide: bool = False
    cta_label: str = "Detayları gör"
    cta_url: str = ""


class FeatureCardStatusBody(BaseModel):
    status: str


class FeatureCardPinBody(BaseModel):
    pinned: bool
    pin_until: str | None = None


class FeatureCardMutationResult(BaseModel):
    message: str
    card_id: int | None = None
    slug: str | None = None


# ---------------------------- Onay kuyruğu (discovery) ----------------------------


class DiscoveryCardItem(BaseModel):
    """Onay kuyruğundaki aday (kesif-* DRAFT)."""
    id: int
    slug: str
    title: str
    tagline: str
    introduced_at: datetime | None = None
    introduced_in_commit: str | None = None
    manual_hide: bool
    is_migration: bool
    source_ref: str | None = None
    raw_subject: str | None = None


class DiscoveryQueueResponse(BaseModel):
    """GET /api/v2/admin/feature-catalog/discovery-queue."""
    cards: list[DiscoveryCardItem]
    counts: dict[str, int]
    source: str = ""
    show_rejected: bool = False


class DiscoveryBulkBody(BaseModel):
    action: Literal["reject", "delete"]
    ids: list[int]


class DiscoveryMutationResult(BaseModel):
    message: str
    affected: int | None = None


# ---------------------------- A/B deneyler ----------------------------


class ExperimentVariantBrief(BaseModel):
    """Liste/detay başlığında variant özeti."""
    slug: str
    label: str
    strategy: str
    weight: int
    is_control: bool = False


class ExperimentListItem(BaseModel):
    id: int
    slug: str
    name: str
    status: str
    status_label: str
    status_badge: str
    hypothesis: str | None = None
    start_at: datetime | None = None
    variants: list[ExperimentVariantBrief]


class ExperimentListResponse(BaseModel):
    experiments: list[ExperimentListItem]


class ExperimentStrategyOption(BaseModel):
    key: str
    label: str
    description: str


class ExperimentFormMeta(BaseModel):
    """Yeni deney formu — strateji registry."""
    strategies: list[ExperimentStrategyOption]


class ExperimentVariantStat(BaseModel):
    """experiments.compute_stats() per-variant çıktısı + strateji etiketi."""
    slug: str
    label: str
    strategy: str
    strategy_label: str
    weight: int
    is_control: bool
    impression: int
    view: int
    demo_click: int
    cta_click: int
    total_clicks: int
    ctr: float
    ctr_low: float
    ctr_high: float
    lift_pct: float | None = None
    vs_control_significant: bool


class ExperimentDetail(BaseModel):
    id: int
    slug: str
    name: str
    status: str
    status_label: str
    status_badge: str
    hypothesis: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    variants: list[ExperimentVariantBrief]


class ExperimentDetailResponse(BaseModel):
    experiment: ExperimentDetail
    stats: list[ExperimentVariantStat]
    has_any_data: bool


class ExperimentCreateBody(BaseModel):
    name: str
    slug: str = ""
    hypothesis: str = ""
    ctrl_strategy: str = "hybrid_full"
    test_strategy: str = "fuzzy_only"
    weight_ctrl: int = 50
    weight_test: int = 50


class ExperimentStatusBody(BaseModel):
    status: str


class ExperimentMutationResult(BaseModel):
    message: str
    experiment_id: int | None = None
    slug: str | None = None


# ---------------------------- Dashboard (curator) ----------------------------


class DashboardSummary(BaseModel):
    total: int
    published: int
    draft: int
    hidden: int
    landing: int
    queue_pending: int
    active_experiment: int


class DashboardLandingHealth(BaseModel):
    landing_count: int
    diversity_pct: int
    diversity_score: float
    learning_count: int


class DashboardWindowMetrics(BaseModel):
    events: int
    impressions: int
    views: int
    demo_clicks: int
    cta_clicks: int
    total_clicks: int
    ctr_pct: float
    new_discoveries: int
    bandit_updates: int
    window_days: int


class DashboardExperimentVariant(BaseModel):
    slug: str
    label: str
    is_control: bool
    ctr: float
    total_clicks: int
    impression: int
    lift_pct: float | None = None
    vs_control_significant: bool


class DashboardExperiment(BaseModel):
    id: int
    name: str
    slug: str
    started_days_ago: int
    total_impressions: int
    has_significance: bool
    variants: list[DashboardExperimentVariant]


class DashboardAnomaly(BaseModel):
    severity: str
    title: str
    hint: str
    action_url: str
    action_label: str


class DashboardAuditItem(BaseModel):
    action: str
    action_label: str
    target_id: int | None = None
    target_slug: str | None = None
    actor_id: int | None = None
    when: datetime | None = None
    ago_seconds: int
    ago_label: str


class FeatureCatalogDashboardResponse(BaseModel):
    """GET /api/v2/admin/feature-catalog/dashboard — curator_dashboard çıktısı."""
    summary: DashboardSummary
    landing_health: DashboardLandingHealth
    last_7d: DashboardWindowMetrics
    experiment: DashboardExperiment | None = None
    anomalies: list[DashboardAnomaly]
    recent_audit: list[DashboardAuditItem]
    window_days: int
    generated_at: datetime


# =============================================================================
# P7a — Ticari Pano: Analitik çekirdek (Aksiyon Merkezi / Tahmin / Kohort)
#
# KURAL: 3 analitik servisi (action_center / revenue_forecast / revenue_cohort)
# ve institution_360.create_action HİÇ değişmez; bu şemalar dönen dataclass/dict
# yapılarını JSON'a serialize eder. Owner-pattern (institution|user) korunur.
# =============================================================================


# ---------------------------- Aksiyon Merkezi ----------------------------


class ActionSignalItem(BaseModel):
    """action_center.ActionSignal."""
    kind: str
    severity: str
    score: int
    title: str
    description: str


class SuggestedActionItem(BaseModel):
    """action_center.SuggestedAction (icon emoji veri olarak gelir; UI Lucide map'ler)."""
    kind: str
    summary: str
    label: str
    icon: str
    color: str


class ActionCenterItem(BaseModel):
    """action_center.ActionItem — kurum + sinyaller + öneriler."""
    institution_id: int
    institution_name: str
    plan: str
    plan_label: str
    monthly_price_try: int
    total_score: int
    severity: str
    primary_signal: ActionSignalItem
    other_signals: list[ActionSignalItem]
    suggested_actions: list[SuggestedActionItem]
    last_action_at: datetime | None = None
    last_action_summary: str | None = None


class ActionCenterResponse(BaseModel):
    """GET /api/v2/admin/revenue/action-center."""
    generated_at: datetime
    items: list[ActionCenterItem]
    total_count: int
    severity_counts: dict[str, int]


class QuickActionBody(BaseModel):
    institution_id: int
    kind: str
    summary: str
    result: str = "pending"
    follow_up_days: int = 0


class RevenueMutationResult(BaseModel):
    message: str


# ---------------------------- Tahmin (forecast) ----------------------------


class AtRiskInstitutionItem(BaseModel):
    """revenue_forecast.AtRiskInstitution."""
    institution_id: int
    name: str
    plan: str
    monthly_price_try: int
    health_score: int | None = None
    severity: str
    owner_type: str
    detail_url: str


class RiskAtMrr(BaseModel):
    total_at_risk_mrr: int
    critical_mrr: int
    risk_mrr: int
    critical_count: int
    risk_count: int
    institutions: list[AtRiskInstitutionItem]


class MrrProjection(BaseModel):
    current_mrr: int
    horizon_days: int
    trial_conversion_rate: float
    monthly_churn_rate: float
    trial_ending_count: int
    expected_trial_conversions_mrr: int
    expected_churn_mrr: int
    expected_at_risk_loss_mrr: int
    projected_mrr_status_quo: int
    projected_mrr_with_intervention: int
    delta_mrr: int
    intervention_save_rate: float
    at_risk_critical_count: int
    at_risk_risk_count: int


class ScenarioHorizon(BaseModel):
    horizon_days: int
    status_quo_mrr: int
    intervention_mrr: int
    delta_mrr: int


class ScenarioComparison(BaseModel):
    current_mrr: int
    save_rate: float
    horizons: list[ScenarioHorizon]


class RevenueForecastResponse(BaseModel):
    """GET /api/v2/admin/revenue/forecast."""
    risk: RiskAtMrr
    proj_30: MrrProjection
    proj_60: MrrProjection
    proj_90: MrrProjection
    scenario: ScenarioComparison
    save_rate: float
    save_rate_pct: int


# ---------------------------- Kohort & LTV ----------------------------


class CohortRetentionCell(BaseModel):
    month: int
    count: int | None = None
    pct: float | None = None
    color: str
    future: bool


class CohortRow(BaseModel):
    cohort_key: str
    cohort_label: str
    signup_count: int
    signup_month_age: int
    retention: list[CohortRetentionCell]


class CohortMatrix(BaseModel):
    cohorts: list[CohortRow]
    horizon_months: int
    months_back: int
    total_signups: int


class PlanChurnSummary(BaseModel):
    window_days: int
    signup_count: int
    trial_expired_count: int
    trial_converted_count: int
    trial_conversion_pct: int | None = None
    upgrade_count: int
    downgrade_count: int
    cancel_count: int
    net_movement: int


class PlanLtvItem(BaseModel):
    plan: str
    label: str
    monthly_price_try: int
    active_count: int
    avg_age_months: float
    estimated_ltv_try: int


class LtvEstimate(BaseModel):
    plans: list[PlanLtvItem]
    total_ltv_try: int
    paying_count: int
    avg_ltv_per_paying: int


class RevenueCohortResponse(BaseModel):
    """GET /api/v2/admin/revenue/cohort."""
    matrix: CohortMatrix
    churn: PlanChurnSummary
    ltv: LtvEstimate
    months_back: int
    horizon: int
    churn_days: int


# =============================================================================
# P7b — Ticari Pano: 360 görünümler + CRM (Owner-pattern)
#
# KURAL: institution_360 / revenue_owner / owner_contact / owner_tags /
# health_score_v2 servisleri HİÇ değişmez; bu şemalar dönen dataclass/dict/ORM
# nesnelerini JSON'a serialize eder. owner_type ("institution"|"user") korunur.
# =============================================================================


OwnerTypeLiteral = Literal["institution", "user"]


# ---------------------------- Ortak: enum option + CRM/tag/contact ----------------------------


class CrmEnumOption(BaseModel):
    """CrmActionKind/Result — value+label (+ icon kind için, color result için)."""
    value: str
    label: str
    color: str | None = None


class CrmNoteItem(BaseModel):
    id: int
    content: str
    pinned: bool
    created_at: datetime | None = None
    created_by_name: str | None = None


class CrmActionItem(BaseModel):
    id: int
    kind: str
    kind_label: str
    summary: str
    notes: str | None = None
    result: str
    result_label: str
    result_color: str
    follow_up_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    created_by_name: str | None = None


class OwnerTagItem(BaseModel):
    id: int
    kind: str
    label: str
    color: str
    icon: str
    description: str
    note: str | None = None


class OwnerTagOption(BaseModel):
    value: str
    label: str
    color: str
    icon: str
    description: str


class OwnerContactData(BaseModel):
    responsible_person_name: str | None = None
    responsible_person_title: str | None = None
    billing_email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    linkedin_url: str | None = None
    website: str | None = None
    address: str | None = None
    note: str | None = None
    updated_at: datetime | None = None


class PlanChangeItem(BaseModel):
    id: int
    from_plan: str | None = None
    to_plan: str | None = None
    reason: str
    occurred_at: datetime | None = None


# ---------------------------- Sağlık skoru 2.0 ----------------------------


class HealthComponentItem(BaseModel):
    code: str
    label: str
    weight_pct: int
    value_pct: int
    contribution: int
    note: str | None = None


class HealthScoreV2Data(BaseModel):
    score: int
    band: str
    band_label: str
    band_color: str
    band_emoji: str
    components: list[HealthComponentItem]
    active_teacher_count: int
    active_student_count: int


class HealthTriggerItem(BaseModel):
    code: str
    title: str
    detail: str
    severity: str


class HealthHistoryPoint(BaseModel):
    snapshot_date: str
    score: int
    band: str


# ---------------------------- Kurum 360 ----------------------------


class Institution360Admin(BaseModel):
    id: int
    name: str
    email: str | None = None


class Institution360Identity(BaseModel):
    id: int
    name: str
    slug: str
    contact_email: str | None = None
    is_active: bool
    plan: str
    plan_label: str
    plan_monthly_price_try: int
    trial_ends_at: datetime | None = None
    post_trial_plan: str | None = None
    subscription_kind: str | None = None
    subscription_period_end: datetime | None = None
    subscription_pause_until: datetime | None = None
    performance_guarantee: bool = False
    created_at: datetime | None = None
    admins: list[Institution360Admin]


class Institution360Health(BaseModel):
    score: int | None = None
    level: str
    emoji: str
    color: str
    label: str


class Institution360Usage(BaseModel):
    days: int
    active_teacher_count: int
    total_teacher_count: int
    teacher_active_pct: int | None = None
    active_student_count: int
    total_student_count: int
    student_active_pct: int | None = None
    notification_sent: int
    notification_failed: int
    study_sessions: int


class Institution360Billing(BaseModel):
    last_paid_at: datetime | None = None
    last_paid_amount_try: int | None = None
    next_due_at: datetime | None = None
    next_due_amount_try: int | None = None
    overdue_count: int
    overdue_total_try: int
    lifetime_paid_try: int


class Risk360Item(BaseModel):
    kind: str
    severity: str
    title: str
    message: str
    weight: int


class CrmMeta(BaseModel):
    """Form dropdown'ları: action kinds + results + tag kinds + offer kinds."""
    action_kinds: list[CrmEnumOption]
    action_results: list[CrmEnumOption]
    tag_kinds: list[OwnerTagOption]
    offer_kinds: list[EnumOption] = []


class InstitutionRevenue360Response(BaseModel):
    """GET /api/v2/admin/revenue/institutions/{id}."""
    identity: Institution360Identity
    health: Institution360Health
    usage_30d: Institution360Usage
    billing: Institution360Billing
    risks: list[Risk360Item]
    crm_notes: list[CrmNoteItem]
    crm_actions: list[CrmActionItem]
    health_v2: HealthScoreV2Data | None = None
    health_triggers: list[HealthTriggerItem]
    health_history: list[HealthHistoryPoint]
    owner_tags: list[OwnerTagItem]
    owner_contact: OwnerContactData | None = None
    plan_changes: list[PlanChangeItem]
    offers: list["OfferItem"] = []
    invoices: list["InvoiceItem"] = []
    meta: CrmMeta


# ---------------------------- Bağımsız öğretmen 360 ----------------------------


class OwnerBrief(BaseModel):
    owner_type: str
    owner_id: int
    name: str
    email: str | None = None
    plan: str
    is_active: bool
    monthly_price_try: int
    trial_ends_at: datetime | None = None


class StudentHealthCounts(BaseModel):
    healthy: int
    watch: int
    risk: int
    critical: int
    unhealthy_total: int
    total: int


class StudentRow(BaseModel):
    id: int
    full_name: str | None = None
    grade_level: int | None = None
    is_active: bool
    band: str
    label: str


class UserRevenue360Response(BaseModel):
    """GET /api/v2/admin/revenue/users/{id}."""
    owner: OwnerBrief
    teacher_band: str
    teacher_login_label: str
    student_count: int
    all_students_total: int
    student_health: StudentHealthCounts
    student_rows: list[StudentRow]
    tasks_planned_30d: int
    tasks_completed_30d: int
    tasks_draft_30d: int
    completion_pct: int
    crm_notes: list[CrmNoteItem]
    crm_actions: list[CrmActionItem]
    health_v2: HealthScoreV2Data | None = None
    score_history: list[HealthHistoryPoint]
    owner_tags: list[OwnerTagItem]
    owner_contact: OwnerContactData | None = None
    plan_changes: list[PlanChangeItem]
    offers: list["OfferItem"] = []
    invoices: list["InvoiceItem"] = []
    meta: CrmMeta


# ---------------------------- Mutation gövdeleri ----------------------------


class CrmNoteBody(BaseModel):
    content: str
    pinned: bool = False


class CrmActionBody(BaseModel):
    kind: str
    summary: str
    notes: str = ""
    result: str = "pending"
    follow_up_at: str | None = None


class CrmActionCompleteBody(BaseModel):
    result: str
    notes: str = ""


class OwnerContactBody(BaseModel):
    responsible_person_name: str = ""
    responsible_person_title: str = ""
    billing_email: str = ""
    phone: str = ""
    whatsapp: str = ""
    linkedin_url: str = ""
    website: str = ""
    address: str = ""
    note: str = ""


class OwnerTagBody(BaseModel):
    kind: str
    note: str = ""


class Revenue360MutationResult(BaseModel):
    message: str


# =============================================================================
# P7c — Teklifler + Aksiyon Şablonları + Fatura Tahsilat
# =============================================================================


class OfferItem(BaseModel):
    """Offer + describe_offer özeti."""
    id: int
    kind: str
    kind_label: str
    title: str
    value: float | None = None
    value_unit: str | None = None
    duration_months: int | None = None
    new_plan: str | None = None
    public_message: str | None = None
    admin_note: str | None = None
    status: str
    status_label: str
    status_color: str
    summary: str
    token: str
    sent_at: datetime | None = None
    responded_at: datetime | None = None
    expires_at: datetime | None = None
    decline_reason: str | None = None
    created_at: datetime | None = None


class OfferBody(BaseModel):
    kind: str
    title: str
    value: float | None = None
    duration_months: int | None = None
    new_plan: str = ""
    public_message: str = ""
    admin_note: str = ""
    expires_in_days: int = 14
    send_now: bool = False


class InvoiceItem(BaseModel):
    invoice_id: int
    owner_type: str
    owner_id: int | None = None
    plan: str
    plan_label: str
    amount_try: int
    status: str
    status_label: str
    due_at: datetime | None = None
    paid_at: datetime | None = None
    days_until_due: int | None = None
    days_overdue: int
    payment_method: str | None = None
    attempt_count: int
    last_reminder_kind: str | None = None
    detail_url: str


class InvoicePostponeBody(BaseModel):
    days: int = 7
    note: str = ""


class InvoiceMarkPaidBody(BaseModel):
    method: str = "manual"
    note: str = ""


class InvoiceCancelBody(BaseModel):
    note: str = ""


class InvoiceReminderBody(BaseModel):
    kind: str = "manual"


class ActionTemplateItem(BaseModel):
    id: int
    name: str
    kind: str
    kind_label: str
    subject: str | None = None
    body: str
    description: str | None = None
    is_active: bool


class ActionTemplatesResponse(BaseModel):
    templates: list[ActionTemplateItem]
    kinds: list[EnumOption]


class ActionTemplateBody(BaseModel):
    name: str
    kind: str
    body: str
    subject: str = ""
    description: str = ""
    is_active: bool | None = None


class ActionTemplateRenderResponse(BaseModel):
    ok: bool = True
    id: int
    name: str
    kind: str
    subject: str
    body: str


class RevenueOfferMutationResult(BaseModel):
    message: str
    offer_id: int | None = None


class InvoiceMutationResult(BaseModel):
    message: str
    invoice_id: int | None = None


class ActionTemplateMutationResult(BaseModel):
    message: str
    template_id: int | None = None


# =============================================================================
# P7d — Toplu Kampanyalar
# =============================================================================


class CampaignFunnel(BaseModel):
    """campaign_stats overall/variant funnel sayımları."""
    targeted: int = 0
    sent: int = 0
    accepted: int = 0
    declined: int = 0
    expired: int = 0
    bounced: int = 0
    total: int = 0
    sent_total: int = 0
    accepted_pct: int | None = None


class CampaignListItem(BaseModel):
    id: int
    name: str
    description: str | None = None
    segment: str
    segment_label: str
    status: str
    status_label: str
    status_color: str
    has_variant_b: bool
    created_at: datetime | None = None
    funnel: CampaignFunnel


class CampaignsListResponse(BaseModel):
    campaigns: list[CampaignListItem]


class CampaignSegmentOption(BaseModel):
    value: str
    label: str
    description: str


class CampaignFormMeta(BaseModel):
    segments: list[CampaignSegmentOption]
    offer_kinds: list[EnumOption]


class CampaignPreviewOwner(BaseModel):
    owner_type: str
    owner_id: int
    name: str
    plan: str
    url: str


class CampaignPreviewBody(BaseModel):
    segment: str
    filter_plan: str = ""


class CampaignPreviewResponse(BaseModel):
    count: int
    inst_count: int
    user_count: int
    preview: list[CampaignPreviewOwner]


class CampaignBody(BaseModel):
    name: str
    segment: str
    filter_plan: str = ""
    description: str = ""
    admin_note: str = ""
    variant_a_kind: str
    variant_a_title: str
    variant_a_value: float | None = None
    variant_a_duration_months: int | None = None
    variant_a_new_plan: str = ""
    variant_a_public_message: str = ""
    has_variant_b: bool = False
    variant_b_kind: str = ""
    variant_b_title: str = ""
    variant_b_value: float | None = None
    variant_b_duration_months: int | None = None
    variant_b_new_plan: str = ""
    variant_b_public_message: str = ""
    offer_expires_in_days: int = 14


class CampaignVariant(BaseModel):
    kind: str
    kind_label: str
    title: str
    value: float | None = None
    duration_months: int | None = None
    new_plan: str | None = None
    public_message: str | None = None


class CampaignDetail(BaseModel):
    id: int
    name: str
    description: str | None = None
    admin_note: str | None = None
    segment: str
    segment_label: str
    segment_filter_plan: str | None = None
    status: str
    status_label: str
    status_color: str
    has_variant_b: bool
    variant_a: CampaignVariant
    variant_b: CampaignVariant | None = None
    offer_expires_in_days: int
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CampaignRecipientItem(BaseModel):
    id: int
    owner_type: str
    owner_id: int | None = None
    owner_name: str
    owner_plan: str | None = None
    owner_url: str
    variant: str
    status: str
    status_label: str
    sent_at: datetime | None = None
    responded_at: datetime | None = None
    offer_id: int | None = None
    offer_token: str | None = None
    error_note: str | None = None


class CampaignStatsFull(BaseModel):
    status: str
    overall: CampaignFunnel
    variant_a: CampaignFunnel
    variant_b: CampaignFunnel | None = None
    has_variant_b: bool
    institution_count: int
    user_count: int


class CampaignDetailResponse(BaseModel):
    campaign: CampaignDetail
    stats: CampaignStatsFull
    recipients: list[CampaignRecipientItem]


class CampaignMutationResult(BaseModel):
    message: str
    campaign_id: int | None = None
    recipient_count: int | None = None
    sent: int | None = None
    errors: int | None = None


# =============================================================================
# G1 — Ticari Ana Dashboard (security-monitor/revenue)
# =============================================================================


class RevenueMrr(BaseModel):
    """revenue_panel.mrr() — kurum-merkezli."""
    total_try: int
    paying_institutions: int
    free_institutions: int
    total_institutions: int
    avg_per_paying: float


class RevenuePlanDist(BaseModel):
    plan: str
    label: str
    count: int
    monthly_price_try: int
    estimated_mrr: int


class RevenueTrialEntry(BaseModel):
    institution_id: int
    institution_name: str
    plan: str
    trial_ends_at: datetime | None = None
    days_left: int
    post_trial_plan: str | None = None


class RevenueChangeSummary(BaseModel):
    days: int
    by_reason: dict[str, int]
    net_growth: int
    signups: int
    upgrades: int
    downgrades: int
    trial_expired: int
    pauses: int


class RevenueDailyChange(BaseModel):
    day: str
    signup: int = 0
    upgrade: int = 0
    downgrade: int = 0
    trial_expired: int = 0
    pause: int = 0
    total: int = 0


class RevenueChurnProxy(BaseModel):
    healthy: int = 0
    watch: int = 0
    risk: int = 0
    critical: int = 0
    unhealthy_total: int = 0
    needs_attention: int | None = None


class RevenuePaymentBucket(BaseModel):
    key: str
    label: str
    count: int
    total_try: int


class RevenuePaymentCalendar(BaseModel):
    buckets: list[RevenuePaymentBucket]
    total_count: int
    total_amount_try: int
    overdue_total_try: int
    upcoming_total_try: int
    days_horizon: int


class RevenueOwnerMrr(BaseModel):
    """revenue_owner.mrr_owner_aware() — kurum + bağımsız öğretmen."""
    total_try: int
    institution_mrr_try: int
    user_mrr_try: int
    total_owners: int
    institution_count: int
    user_count: int
    paying_count: int
    institution_paying_count: int
    user_paying_count: int
    avg_per_paying: float


class RevenueOwnerPlanDist(BaseModel):
    plan: str
    label: str
    count: int
    institution_count: int
    user_count: int
    monthly_price_try: int
    estimated_mrr: int


class RevenueOwnerTrial(BaseModel):
    owner_type: str
    owner_id: int
    name: str
    plan: str
    trial_ends_at: datetime | None = None
    url: str


class RevenueDashboardResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/revenue."""
    generated_at: datetime
    mrr: RevenueMrr
    plan_distribution: list[RevenuePlanDist]
    trial_ending_soon: list[RevenueTrialEntry]
    trial_expired_30d: int
    change_summary_30d: RevenueChangeSummary
    daily_changes_30d: list[RevenueDailyChange]
    churn_proxy: RevenueChurnProxy
    payment_calendar: RevenuePaymentCalendar
    # Owner-aware (segment filtreli)
    mrr_combined: RevenueOwnerMrr | None = None
    plan_dist_combined: list[RevenueOwnerPlanDist]
    trial_combined: list[RevenueOwnerTrial]
    segment: str
    segment_counts: dict[str, int]


class RevenueDrillRow(BaseModel):
    institution_id: int
    institution_name: str
    plan: str
    plan_label: str
    monthly_price_try: int | None = None
    is_active: bool | None = None
    trial_ends_at: datetime | None = None
    post_trial_plan: str | None = None
    reason: str | None = None
    detail_url: str
    health_score: int | None = None
    active_teacher_pct: int | None = None
    active_student_pct: int | None = None
    event_at: datetime | None = None
    event_days_ago: int | None = None


class RevenueDrillResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/revenue/drill."""
    title: str
    icon: str
    key: str
    plan: str | None = None
    count: int
    rows: list[RevenueDrillRow]
    error: str | None = None


class RevenueInvoiceRow(BaseModel):
    id: int
    owner_type: str
    owner_id: int | None = None
    owner_name: str
    owner_url: str
    plan: str
    amount_try: int
    status: str
    status_label: str
    status_color: str
    due_at: datetime | None = None
    paid_at: datetime | None = None
    payment_method: str | None = None


class RevenueInvoiceStatusCount(BaseModel):
    count: int
    total_try: int


class RevenueInvoicesResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/revenue/invoices."""
    rows: list[RevenueInvoiceRow]
    status_counts: dict[str, RevenueInvoiceStatusCount]
    statuses: list[StatusOption]
    status_filter: str | None = None


# =============================================================================
# G2a — Güvenlik Kamarası: Genel Bakış + Sistem + Bildirim + Bütünlük
# =============================================================================


class SecuritySessionItem(BaseModel):
    id: int
    session_token: str
    user_id: int
    user_email: str
    user_full_name: str | None = None
    role: str
    ip: str | None = None
    user_agent: str = ""
    login_at: datetime | None = None
    last_seen_at: datetime | None = None
    idle_seconds: int
    age_seconds: int


class SecuritySuspiciousIp(BaseModel):
    id: int
    ip: str
    fail_count: int
    distinct_email_count: int
    distinct_emails: list[str]
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    is_blocked: bool
    blocked_until: datetime | None = None
    block_reason: str | None = None
    block_note: str | None = None


class SecurityFailedBucket(BaseModel):
    ip: str | None = None
    fail_count: int
    distinct_email_count: int
    last_seen_at: datetime | None = None


class SecurityImpersonationItem(BaseModel):
    id: int
    actor_user_id: int
    actor_email: str | None = None
    actor_full_name: str | None = None
    target_user_id: int
    target_email: str | None = None
    target_full_name: str | None = None
    reason: str | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None
    ip: str | None = None
    is_expired_now: bool
    seconds_left: int
    age_seconds: int


class AttentionItemModel(BaseModel):
    severity: str
    icon: str
    title: str
    description: str
    action_url: str
    action_label: str
    category: str
    ts: datetime | None = None
    score: int
    explainer: str = ""


class AttentionSummaryModel(BaseModel):
    items: list[AttentionItemModel]
    total: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    top_severity: str
    is_clean: bool


class SecuritySummary(BaseModel):
    active_sessions: int
    blocked_ips: int
    watched_ips: int
    failed_24h: int
    critical_24h: int
    super_admin_logins_24h: int


class ErrorSummaryModel(BaseModel):
    open_groups: int
    new_groups_24h: int
    total_events_24h: int
    window_hours: int


class SecurityOverviewResponse(BaseModel):
    """GET /api/v2/admin/security-monitor."""
    generated_at: datetime
    summary: SecuritySummary
    role_counts: dict[str, int]
    active_sessions: list[SecuritySessionItem]
    suspicious_ips: list[SecuritySuspiciousIp]
    failed_login_buckets: list[SecurityFailedBucket]
    critical_audits: list[AuditLogItem]
    super_admin_logins: list[AuditLogItem]
    active_impersonations: list[SecurityImpersonationItem]
    abuse_open_count: int
    system_error_summary: ErrorSummaryModel
    unack_alarm_count: int
    attention: AttentionSummaryModel


class IntegrityMigration(BaseModel):
    status: str
    head: str | None = None
    current: str | None = None
    pending: bool = False
    error: str | None = None


class IntegrityDbFile(BaseModel):
    path: str | None = None
    size_mb: float
    size_bytes: int | None = None
    modified_at: datetime | None = None
    age_seconds: int
    level: str


class IntegrityOrphanFinding(BaseModel):
    kind: str
    label: str
    count: int
    samples: list[dict] = []


class IntegrityOrphans(BaseModel):
    total_findings: int
    findings: list[IntegrityOrphanFinding]


class IntegrityKvkkSample(BaseModel):
    id: int
    kind: str
    status: str
    created_at: datetime | None = None
    age_days: int


class IntegrityKvkk(BaseModel):
    sla_days: int
    overdue_count: int
    open_total: int
    overdue_samples: list[IntegrityKvkkSample]


class IntegrityCronJob(BaseModel):
    job_key: str
    last_run_at: datetime | None = None
    age_hours: int | None = None
    level: str
    last_status: str | None = None
    last_error: str | None = None


class IntegrityCronDrift(BaseModel):
    summary: dict[str, int]
    jobs: list[IntegrityCronJob]


class IntegrityResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/integrity."""
    generated_at: datetime
    migration: IntegrityMigration
    db_file: IntegrityDbFile
    orphans: IntegrityOrphans
    kvkk_sla: IntegrityKvkk
    cron_drift: IntegrityCronDrift


class SystemErrorGroup(BaseModel):
    id: int
    signature: str
    endpoint: str
    method: str
    status_code: int
    exception_type: str
    exception_message: str | None = None
    stack_trace: str | None = None
    count: int
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    age_seconds: int
    resolved_at: datetime | None = None
    last_ip: str | None = None
    last_actor_user_id: int | None = None


class SystemEndpointError(BaseModel):
    endpoint: str
    method: str
    total: int
    groups: int


class SystemSlowRequest(BaseModel):
    id: int
    endpoint: str
    method: str
    status_code: int
    response_time_ms: int
    recorded_at: datetime | None = None
    ip: str | None = None


class SystemHealthDataResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/system."""
    generated_at: datetime
    summary: ErrorSummaryModel
    error_groups: list[SystemErrorGroup]
    endpoint_top: list[SystemEndpointError]
    slow_requests: list[SystemSlowRequest]


class SystemResolveBody(BaseModel):
    note: str = ""


class SystemMutationResult(BaseModel):
    message: str
    error_id: int | None = None


class NotifWindowSummary(BaseModel):
    window_label: str
    window_hours: int
    total: int
    sent: int
    failed: int
    queued: int
    suppressed: int
    success_pct: float | None = None


class NotifMatrix(BaseModel):
    rows: list[str]
    statuses: list[str]
    matrix: dict[str, dict[str, int]]
    rollups: dict[str, dict]
    window_hours: int


class NotifSuppressItem(BaseModel):
    slug: str
    label: str
    count: int


class NotifDailyTrend(BaseModel):
    day: str
    sent: int
    failed: int
    queued: int
    suppressed: int
    total: int
    success_pct: float | None = None


class NotifFailureItem(BaseModel):
    id: int
    queued_at: datetime | None = None
    parent_id: int | None = None
    parent_name: str | None = None
    parent_email: str | None = None
    student_id: int | None = None
    student_name: str | None = None
    kind: str
    channel: str
    attempts: int | None = None
    error: str = ""


class NotificationHealthResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/notifications."""
    generated_at: datetime
    summary_24h: NotifWindowSummary
    summary_7d: NotifWindowSummary
    oldest_queued_minutes: int | None = None
    channel_matrix_24h: NotifMatrix
    kind_matrix_24h: NotifMatrix
    suppress_distribution_24h: list[NotifSuppressItem]
    daily_trend_7d: list[NotifDailyTrend]
    recent_failures_24h: list[NotifFailureItem]


# =============================================================================
# G2b — Güvenlik Kamarası: Aktivite Kamerası (tenant_activity)
# =============================================================================


class ActivityTotals(BaseModel):
    dau: int
    wau: int
    mau: int


class ActivityRoleBreakdownRow(BaseModel):
    role: str
    label: str
    color: str
    icon: str
    today: int
    yesterday: int
    delta: int
    delta_pct: int


class ActivityWow(BaseModel):
    day_labels: list[str]
    this_dates: list[str]
    last_dates: list[str]
    this_series: list[int]
    last_series: list[int]
    this_total: int
    last_total: int
    delta: int
    delta_pct: int
    max_value: int


class ActivitySoloMetric(BaseModel):
    # parent_outreach / discipline / consistency ortak esnek alanlar
    ratio_pct: int | None = None
    sent_count: int | None = None
    total: int | None = None
    avg_per_student_per_week: float | None = None
    total_tasks: int | None = None
    total_students: int | None = None
    weeks: int | None = None
    avg_missing_weeks: float | None = None
    consistent_count: int | None = None
    label: str
    color: str = "slate"


class ActivitySoloSpecial(BaseModel):
    parent_outreach: ActivitySoloMetric
    discipline: ActivitySoloMetric
    consistency: ActivitySoloMetric


class ActivityCriticalSummary(BaseModel):
    stickiness_pct: float
    stickiness_color: str
    stickiness_label: str
    critical_institutions: int
    sharp_drop_count: int
    paying_idle_count: int
    onboarding_stuck_count: int
    champion_count: int


class ActivityHeartbeatRow(BaseModel):
    owner_type: str
    owner_id: int | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    plan: str | None = None
    last_login_at: datetime | None = None
    last_source: str | None = None
    days_since_login: int | None = None
    band: str
    band_color: str
    label: str
    detail_url: str
    student_count: int | None = None


class ActivityHeartbeatSummary(BaseModel):
    healthy: int = 0
    watch: int = 0
    warning: int = 0
    critical: int = 0
    dead: int = 0
    no_login: int = 0
    total: int = 0
    unhealthy: int = 0


class ActivityDecayRow(BaseModel):
    owner_type: str
    owner_id: int | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    plan: str | None = None
    recent_7d: int
    previous_7d: int
    change_pct: int
    band: str
    color: str
    label: str
    detail_url: str


class ActivityPlanActivityCell(BaseModel):
    owner_type: str
    owner_id: int | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    plan: str | None = None
    days_since_login: int | None = None
    label: str
    band_color: str
    detail_url: str


class ActivityPlanActivityMatrix(BaseModel):
    paying_active: list[ActivityPlanActivityCell]
    paying_idle: list[ActivityPlanActivityCell]
    free_active: list[ActivityPlanActivityCell]
    free_idle: list[ActivityPlanActivityCell]
    totals: dict[str, int]
    active_days: int


class ActivitySilentRow(BaseModel):
    owner_type: str
    owner_id: int | None = None
    tenant_id: int | None = None
    tenant_name: str | None = None
    plan: str | None = None
    days_since_login: int | None = None
    detail_url: str | None = None


class ActivityStickiness(BaseModel):
    dau: int
    mau: int
    ratio_pct: float
    band: str
    color: str
    label: str


class ActivityStickinessPoint(BaseModel):
    day: str
    dau: int
    mau: int
    ratio: float


class ActivityRetentionMetric(BaseModel):
    total: int
    active: int
    ratio_pct: int | None = None
    health: str | None = None
    color: str | None = None


class ActivityResurrectedRow(BaseModel):
    user_id: int
    name: str
    email: str | None = None
    role: str | None = None
    institution_id: int | None = None
    previous_last_login: datetime | None = None
    returned_at: datetime | None = None
    gap_days: int


class ActivitySessionBands(BaseModel):
    under_1: int
    min_1_5: int
    min_5_15: int
    min_15_30: int
    over_30: int


class ActivitySessionDuration(BaseModel):
    count: int
    avg_min: float
    median_min: float
    under_1min: int = 0
    under_1_pct: int = 0
    over_30min: int = 0
    over_30_pct: int = 0
    bands: ActivitySessionBands
    days_window: int


class ActivityRatioRow(BaseModel):
    owner_type: str
    owner_id: int | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    plan: str | None = None
    active_teachers: int
    active_students: int
    total_students: int | None = None
    ratio: float | None = None
    band: str
    color: str
    label: str
    detail_url: str


class ActivityPowerUser(BaseModel):
    user_id: int
    name: str
    email: str | None = None
    role: str | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    active_days: int
    activity_pct: int


class ActivityPowerUsers(BaseModel):
    top: list[ActivityPowerUser]
    bottom: list[ActivityPowerUser]
    days_window: int
    total_active_users: int = 0


class ActivityFeaturePopularity(BaseModel):
    key: str
    label: str
    icon: str
    total_events: int
    distinct_institutions: int
    distinct_users: int


class ActivityFeatureDef(BaseModel):
    key: str
    label: str
    icon: str


class ActivityFeatureMatrixCell(BaseModel):
    key: str
    used: bool


class ActivityFeatureMatrixRow(BaseModel):
    owner_type: str
    owner_id: int | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    plan: str | None = None
    cells: list[ActivityFeatureMatrixCell]
    adopted_count: int
    adoption_pct: int
    detail_url: str


class ActivityFeatureMatrix(BaseModel):
    features: list[ActivityFeatureDef]
    rows: list[ActivityFeatureMatrixRow]
    days_window: int


class ActivityMilestone(BaseModel):
    key: str
    label: str
    done: bool | None = None


class ActivityOnboardingRow(BaseModel):
    owner_type: str
    owner_id: int | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    plan: str | None = None
    age_days: int
    milestones: list[ActivityMilestone]
    done_count: int
    total_count: int
    completion_pct: int
    detail_url: str


class ActivityPlanBenchmarkRow(BaseModel):
    owner_type: str = "institution"
    plan: str
    plan_label: str
    monthly_price: int
    institution_count: int
    avg_active_teachers: float
    avg_active_students: float
    avg_feature_adoption: float
    avg_feature_adoption_pct: int
    feature_total: int
    avg_session_min: float


class ActivityChampionRow(BaseModel):
    owner_type: str
    owner_id: int | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    plan: str | None = None
    is_paying: bool
    score: float
    density: float
    active_user_count: int
    feature_adoption: int
    feature_total: int
    age_months: float
    student_teacher_ratio: float | int
    detail_url: str
    is_champion: bool = True


class ActivityHeatmap(BaseModel):
    days_window: int
    matrix: dict[str, dict[str, int]]
    max_value: int
    total: int
    day_labels: list[str]


class ActivityPerTenant(BaseModel):
    tenant_id: int
    tenant_name: str
    plan: str | None = None
    dau: int
    wau: int
    mau: int


class ActivityDauTrendPoint(BaseModel):
    day: str
    dau: int


class ActionSuggestion(BaseModel):
    kind: str
    label: str
    hint: str


class ActivityPanelResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/activity."""
    generated_at: datetime
    segment: str
    totals: ActivityTotals
    per_tenant: list[ActivityPerTenant]
    heatmap: ActivityHeatmap
    dau_trend_14d: list[ActivityDauTrendPoint]
    silent_tenants_7d: list[ActivitySilentRow]
    role_breakdown: list[ActivityRoleBreakdownRow]
    heartbeats: list[ActivityHeartbeatRow]
    heartbeat_summary: ActivityHeartbeatSummary
    wow: ActivityWow
    stickiness: ActivityStickiness
    stickiness_trend_30d: list[ActivityStickinessPoint]
    week1: ActivityRetentionMetric
    day30: ActivityRetentionMetric
    resurrected: list[ActivityResurrectedRow]
    decay_rates: list[ActivityDecayRow]
    plan_activity: ActivityPlanActivityMatrix
    session_duration: ActivitySessionDuration
    teacher_student_ratios: list[ActivityRatioRow]
    power_users: ActivityPowerUsers
    feature_popularity: list[ActivityFeaturePopularity]
    feature_matrix: ActivityFeatureMatrix
    onboarding: list[ActivityOnboardingRow]
    plan_benchmark: list[ActivityPlanBenchmarkRow]
    champions: list[ActivityChampionRow]
    action_suggestions: dict[str, list[ActionSuggestion]]
    solo_special: ActivitySoloSpecial | None = None
    critical_summary: ActivityCriticalSummary


class ActiveUsersDrillRow(BaseModel):
    user_id: int
    name: str
    email: str | None = None
    role: str | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    last_login_at: datetime | None = None


class ActiveUsersDrillResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/activity/active-users."""
    window: str
    window_label: str
    role: str
    role_label: str
    rows: list[ActiveUsersDrillRow]


class HeatmapPattern(BaseModel):
    label: str
    tone: str
    detail: str | None = None


class InstitutionHeatmapResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/activity/heatmap."""
    institution_id: int
    institution_name: str | None = None
    plan: str | None = None
    days_window: int
    matrix: dict[str, dict[str, int]]
    max_value: int
    total: int
    day_labels: list[str]
    patterns: list[HeatmapPattern]


# =============================================================================
# G3 — Güvenlik Kamarası: Oturumlar + Canlı Akış + IP + Impersonation
# =============================================================================


class LiveFeedItem(BaseModel):
    type: str  # audit | alarm
    ts: datetime | None = None
    title: str
    actor_id: int | None = None
    ip: str | None = None
    details: str = ""
    severity: str  # critical | warn | info


class LiveFeedResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/live/feed."""
    since_seconds: int
    items: list[LiveFeedItem]


class IpBlockBody(BaseModel):
    ip: str
    hours: int = 1
    note: str = ""


class IpUnblockBody(BaseModel):
    ip: str


class SecurityActionResult(BaseModel):
    message: str
    ok: bool = True


# =============================================================================
# G4 — Güvenlik Kamarası: Alarmlar + Suistimal
# =============================================================================


class AlarmRuleItem(BaseModel):
    id: int
    key: str
    name: str
    description: str | None = None
    threshold: int
    cooldown_minutes: int
    enabled: bool
    channels: str | None = None
    last_triggered_at: datetime | None = None
    last_value: int | None = None


class AlarmEventItem(BaseModel):
    id: int
    rule_key: str
    rule_name: str
    value: int
    threshold: int
    severity: str
    delivery_status: str | None = None
    triggered_at: datetime | None = None
    acknowledged_at: datetime | None = None
    age_seconds: int


class AlarmsResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/alarms."""
    rules: list[AlarmRuleItem]
    events: list[AlarmEventItem]
    unack_count: int


class AlarmRuleUpdateBody(BaseModel):
    threshold: int
    cooldown_minutes: int
    enabled: bool = False
    channels: str = "email,in_app"


class AlarmScanResult(BaseModel):
    message: str
    triggered: int
    total_rules: int


class AbuseSignalItem(BaseModel):
    id: int
    kind: str
    kind_label: str
    severity: str
    count: int
    window_start: datetime | None = None
    window_end: datetime | None = None
    detected_at: datetime | None = None
    last_seen_at: datetime | None = None
    resolved_at: datetime | None = None
    actor_user_id: int | None = None
    actor_full_name: str | None = None
    actor_email: str | None = None
    tenant_id: int | None = None
    tenant_name: str | None = None
    details: dict = {}


class AbuseMeta(BaseModel):
    kind_labels: dict[str, str]
    kind_descriptions: dict[str, str]
    severity_labels: dict[str, str]
    severity_colors: dict[str, str]
    action_button_labels: dict[str, str]


class AbuseResponse(BaseModel):
    """GET /api/v2/admin/security-monitor/abuse."""
    signals: list[AbuseSignalItem]
    open_count: int
    filter_only_open: bool
    filter_kind: str | None = None
    meta: AbuseMeta


class AbuseScanResult(BaseModel):
    message: str
    summary: dict[str, int]
    total: int


class AbuseResolveBody(BaseModel):
    note: str = ""


class AbuseRemediateResult(BaseModel):
    message: str
    ok: bool
    kind: str
    action: str
    affected_count: int
    note: str


# =============================================================================
# Süper Admin — Sistem ayarları (API anahtarları)
# =============================================================================


class AiSettingItem(BaseModel):
    name: str               # gemini_paid_api_key | gemini_free_api_key | *_model
    kind: str               # secret (maskeli) | config (düz)
    label: str
    is_set: bool
    source: str             # db | env | none | default
    value: str              # secret → maskeli; config → düz değer


class AiSettingsResponse(BaseModel):
    items: list[AiSettingItem]


class SetAiSettingBody(BaseModel):
    name: str               # SECRET_NAMES + CONFIG_NAMES içinden
    value: str              # düz değer (secret ise şifreli saklanır)


# =============================================================================
# Süper Admin — Üyelik/Fiyat yapılandırması (tek kaynak override)
# =============================================================================


class SoloBandIn(BaseModel):
    max_students: int
    monthly: int


class InstitutionTierIn(BaseModel):
    code: str
    label: str
    min_coaches: int
    max_coaches: int | None = None
    per_coach_monthly: int
    white_label: bool = False
    short: str = ""


class PricingConfigBody(BaseModel):
    annual_paid_months: int
    solo_trial_days: int
    solo_free_students: int
    solo_bands: list[SoloBandIn]
    solo_over_cap_per_student: int
    institution_trial_days: int
    institution_free_teachers: int
    institution_free_students: int
    institution_students_per_coach: int
    institution_tiers: list[InstitutionTierIn]


class PricingAdminResponse(BaseModel):
    config: dict          # etkin düzenlenebilir yapı (override dahil)
    defaults: dict        # kod varsayılanı (sıfırlama için)


# ----------------------------- İletişim talepleri -----------------------------


class ContactRequestItem(BaseModel):
    id: int
    created_at: str
    name: str
    email: str
    phone: str | None = None
    institution_name: str | None = None
    coach_count: int | None = None
    message: str | None = None
    source: str
    source_label: str
    status: str
    status_label: str
    handled_by_id: int | None = None
    handled_at: str | None = None
    admin_note: str | None = None


class ContactRequestListResponse(BaseModel):
    items: list[ContactRequestItem]
    counts: dict[str, int]      # status → adet (new/contacted/closed/total)
    status_labels: dict[str, str]


class ContactRequestUpdateBody(BaseModel):
    status: str = Field(..., max_length=20)
    admin_note: str | None = Field(default=None, max_length=2000)


class ContactRequestMutationResult(BaseModel):
    id: int
    status: str
