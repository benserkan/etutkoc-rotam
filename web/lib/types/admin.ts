/**
 * Manuel TypeScript tipleri — `/api/v2/admin/*` için.
 *
 * Pydantic şemaları (`app/routes/api_v2/schemas/admin.py`) ile birebir.
 * Veri yapısı/sorgular `app/routes/admin.py` + `services/tenant_health.py`
 * + `services/audit.py` ile mutlak korunur.
 */

// =============================================================================
// Ortak
// =============================================================================

export type HealthLevel = "healthy" | "watch" | "risk" | "critical";

// =============================================================================
// Dashboard
// =============================================================================

export interface AdminDashboardCounts {
  institutions: number;
  active_institutions: number;
  teachers: number;
  students: number;
  parents: number;
  institution_admins: number;
  super_admins: number;
  independent_teachers: number;
}

export interface HealthSummary {
  healthy: number;
  watch: number;
  risk: number;
  critical: number;
  unhealthy_total: number;
  needs_attention: number;
}

export interface HealthIndicatorItem {
  code: string;
  title: string;
  detail: string;
  weight: number;
}

export interface InstitutionBriefForHealth {
  id: number;
  name: string;
  slug: string;
  plan: string | null;
  is_active: boolean;
}

export interface HealthAssessmentItem {
  institution: InstitutionBriefForHealth;
  score: number;
  level: HealthLevel;
  level_label: string;
  level_emoji: string;
  level_color: string; // "rose" | "amber" | "yellow" | "emerald"
  indicators: HealthIndicatorItem[];
  teacher_count: number;
  student_count: number;
  active_teacher_count_7d: number;
  active_student_count_7d: number;
  last_teacher_login: string | null;
  last_student_login: string | null;
  weekly_completion_rate: number | null;
  teacher_active_pct: number | null;
  student_active_pct: number | null;
}

export interface IndependentTeacherActivitySummary {
  healthy: number;
  watch: number;
  risk: number;
  critical: number;
  unhealthy_total: number;
  total: number;
}

export interface IndependentTeacherBrief {
  id: number;
  full_name: string;
  email: string;
}

export interface IndependentTeacherRiskRow {
  user: IndependentTeacherBrief;
  band: HealthLevel;
  days_since_login: number | null;
  label: string;
  last_login_at: string | null;
}

export interface AuditLogItem {
  id: number;
  actor_id: number | null;
  email_attempted: string | null;
  action: string;
  action_label: string;
  target_type: string | null;
  target_id: number | null;
  ip_address: string | null;
  user_agent: string | null;
  details_json: string | null;
  created_at: string;
  via_admin: number | null;
}

export interface AdminDashboardResponse {
  counts: AdminDashboardCounts;
  failed_logins_24h: number;
  health_summary: HealthSummary;
  top_unhealthy: HealthAssessmentItem[];
  teacher_activity_summary: IndependentTeacherActivitySummary;
  top_teacher_risk: IndependentTeacherRiskRow[];
  recent_audits: AuditLogItem[];
}

// =============================================================================
// P2 — Institutions
// =============================================================================

export type InstitutionSort = "health" | "name" | "created";
export type InstitutionFilterLevel = "unhealthy" | "critical";

export interface InstitutionListItem {
  institution: InstitutionBriefForHealth;
  score: number;
  level: HealthLevel;
  level_label: string;
  level_emoji: string;
  level_color: string;
  indicators: HealthIndicatorItem[];
  teacher_count: number;
  student_count: number;
  teacher_active_pct: number | null;
  student_active_pct: number | null;
  weekly_completion_rate: number | null;
  last_teacher_login: string | null;
  last_student_login: string | null;
}

export interface InstitutionListResponse {
  items: InstitutionListItem[];
  summary: HealthSummary;
  sort: InstitutionSort;
  filter_level: InstitutionFilterLevel | null;
}

export interface InstitutionCreateBody {
  name: string;
  slug?: string | null;
  contact_email?: string | null;
  plan?: string;
}

export interface InstitutionEditBody {
  name: string;
  contact_email?: string | null;
  plan?: string;
  is_active: boolean;
}

export interface InstitutionDetailBrief {
  id: number;
  name: string;
  slug: string;
  contact_email: string | null;
  plan: string;
  is_active: boolean;
  created_at: string | null;
}

export interface InstitutionUserBrief {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  last_login_at: string | null;
}

export interface InstitutionDetailResponse {
  institution: InstitutionDetailBrief;
  health: HealthAssessmentItem;
  institution_admins: InstitutionUserBrief[];
  teachers: InstitutionUserBrief[];
  student_count: number;
}

export interface InstitutionMutationResult {
  institution: InstitutionDetailBrief | null;
  message: string;
  affected_users: number;
}

// =============================================================================
// P2 — Account history (poly)
// =============================================================================

export type AccountOwnerType = "institution" | "user";
export type AccountRecordType = "plan" | "invoice";

export interface AccountHistoryEvent {
  record_type: AccountRecordType;
  record_id: number;
  when: string;
  title: string;
  subtitle: string;
  badge_label: string;
  badge_color: string;
  detail: Record<string, unknown>;
  archived: boolean;
  archived_at: string | null;
  archive_note: string | null;
}

export interface AccountHistoryResponse {
  owner_type: AccountOwnerType;
  owner_id: number;
  owner_name: string | null;
  window_start: string;
  events: AccountHistoryEvent[];
  total_count: number;
  archived_count: number;
  older_count: number;
  include_archived: boolean;
  years: number;
}

export interface AccountArchiveBody {
  record_type: AccountRecordType;
  record_id: number;
  note?: string | null;
}

export interface AccountUnarchiveBody {
  record_type: AccountRecordType;
  record_id: number;
}

export interface AccountBulkArchiveBody {
  owner_type: AccountOwnerType;
  owner_id: number;
  years?: number;
  note?: string | null;
}

export interface AccountArchiveResult {
  ok: boolean;
  record_type: AccountRecordType | null;
  record_id: number | null;
  archived_at: string | null;
  error: string | null;
  plan_count: number;
  invoice_count: number;
  total: number;
  message: string | null;
}

// =============================================================================
// P2 — Backup
// =============================================================================

export interface InstitutionBackupCounts {
  users: number;
  teachers: number;
  students: number;
  books: number;
  sections: number;
  tasks: number;
  task_items: number;
  notifications: number;
  audit_logs: number;
  credit_accounts: number;
  usage_events: number;
  admin_weekly_digests: number;
  feature_flag_overrides: number;
  quota_overrides: number;
  parent_links: number;
}

export interface InstitutionBackupSummary {
  institution: InstitutionDetailBrief;
  schema_version: number;
  exported_at: string;
  audit_lookback_days: number;
  notification_lookback_days: number;
  counts: InstitutionBackupCounts;
  size_bytes: number;
}

// =============================================================================
// P3 — Users
// =============================================================================

export type AdminRole =
  | "super_admin"
  | "institution_admin"
  | "teacher"
  | "student"
  | "parent";

export interface InstitutionRefBrief {
  id: number;
  name: string;
  slug: string;
}

export interface AdminUserListItem {
  id: number;
  email: string;
  full_name: string;
  role: AdminRole;
  role_label: string;
  institution: InstitutionRefBrief | null;
  is_active: boolean;
  last_login_at: string | null;
  last_login_ip: string | null;
  locked_until: string | null;
  failed_login_count: number;
  must_change_password: boolean;
  created_at: string | null;
}

export interface AdminUserListResponse {
  items: AdminUserListItem[];
  total_returned: number;
  truncated: boolean;
  institutions: InstitutionRefBrief[];
  filter_role: string | null;
  filter_institution_id: number | null;
  filter_q: string | null;
}

export interface AdminUserCreateBody {
  full_name: string;
  email: string;
  role: AdminRole;
  institution_id?: number | null;
}

export interface AdminUserCreateResult {
  user: AdminUserListItem;
  temp_password: string;
  must_change_password: boolean;
}

export interface AdminUserEditBody {
  full_name: string;
  email: string;
  institution_id?: number | null;
  is_active: boolean;
}

export interface AdminUserChangeRoleBody {
  new_role: AdminRole;
  institution_id?: number | null;
}

export interface AdminUserDetailResponse {
  target: AdminUserListItem;
  institutions: InstitutionRefBrief[];
  recent_audits: AuditLogItem[];
  password_changed_at: string | null;
  is_self: boolean;
}

export interface AdminUserMutationResult {
  user: AdminUserListItem | null;
  message: string;
  temp_password: string | null;
}

// =============================================================================
// P3 — Impersonate
// =============================================================================

export interface AdminImpersonateBody {
  reason: string;
}

export interface AdminImpersonateResult {
  impersonation_id: number;
  actor_id: number;
  target_id: number;
  target_full_name: string;
  target_role: AdminRole;
  expires_at: string;
  redirect_url: string;
}

export interface AdminImpersonateEndResult {
  admin_id: number;
  admin_full_name: string;
  target_user_id: number | null;
  redirect_url: string;
}

// =============================================================================
// P3 — Independent teachers
// =============================================================================

export interface AdminIndependentTeachersResponse {
  summary: IndependentTeacherActivitySummary;
  rows: IndependentTeacherRiskRow[];
}

// =============================================================================
// P4 — Audit list
// =============================================================================

export interface AuditActorBrief {
  id: number;
  email: string;
  full_name: string;
}

export interface AuditListItem {
  id: number;
  action: string;
  action_label: string;
  actor_id: number | null;
  actor: AuditActorBrief | null;
  email_attempted: string | null;
  target_type: string | null;
  target_id: number | null;
  ip_address: string | null;
  user_agent: string | null;
  details_parsed: Record<string, unknown> | null;
  via_admin_id: number | null;
  via_admin: AuditActorBrief | null;
  created_at: string;
}

export interface AuditActionOption {
  value: string;
  label: string;
}

export interface AuditListResponse {
  items: AuditListItem[];
  total: number;
  page: number;
  total_pages: number;
  per_page: number;
  filter_action: string | null;
  filter_actor_id: number | null;
  filter_start_date: string | null;
  filter_end_date: string | null;
  all_actions: AuditActionOption[];
}

// =============================================================================
// P4 — System health
// =============================================================================

export type HealthBand = "ok" | "warn" | "crit" | "never" | "disabled";

export interface CronStatusItem {
  job_key: string;
  description: string | null;
  dow_label: string;
  time_label: string;
  enabled: boolean;
  last_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  hours_since_run: number | null;
  health: HealthBand;
}

export interface DispatcherStatusInfo {
  queued_count: number;
  failed_count: number;
  oldest_queued_at: string | null;
  oldest_queued_age_hours: number | null;
  health: "ok" | "warn" | "crit";
}

export interface DatabaseStatusInfo {
  file_path: string | null;
  file_size_mb: number | null;
  table_counts: Record<string, number>;
  health: "ok" | "warn" | "crit";
}

export interface SystemHealthResponse {
  crons: CronStatusItem[];
  dispatcher: DispatcherStatusInfo | null;
  database: DatabaseStatusInfo | null;
  overall_health: "ok" | "warn" | "crit";
}

// =============================================================================
// P4 — Announcements
// =============================================================================

export type AnnouncementSeverity = "info" | "warn" | "critical";
export type AnnouncementAudience =
  | "all"
  | "super_admin"
  | "institution_admin"
  | "teacher"
  | "student"
  | "parent";

export interface AnnouncementItem {
  id: number;
  title: string | null;
  message: string;
  severity: AnnouncementSeverity;
  severity_label: string;
  audience: AnnouncementAudience;
  audience_label: string;
  starts_at: string;
  ends_at: string | null;
  dismissible: boolean;
  is_active_now: boolean;
  created_by: number | null;
  created_at: string;
}

export interface AnnouncementCreateBody {
  title?: string | null;
  message: string;
  severity?: AnnouncementSeverity;
  audience?: AnnouncementAudience;
  starts_at?: string | null;
  ends_at?: string | null;
  dismissible?: boolean;
}

export interface AnnouncementSeverityOption {
  value: AnnouncementSeverity;
  label: string;
}

export interface AnnouncementAudienceOption {
  value: AnnouncementAudience;
  label: string;
}

export interface AnnouncementsListResponse {
  items: AnnouncementItem[];
  severities: AnnouncementSeverityOption[];
  audiences: AnnouncementAudienceOption[];
}

export interface AnnouncementMutationResult {
  announcement: AnnouncementItem | null;
  message: string;
}

// =============================================================================
// P4 — KVKK
// =============================================================================

export type KvkkRequestKind = "export" | "delete" | "rectification";
export type KvkkRequestStatus =
  | "pending"
  | "processing"
  | "completed"
  | "cancelled"
  | "rejected";

export interface KvkkSummary {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  cancelled: number;
  rejected: number;
}

export interface KvkkRequestUserBrief {
  id: number;
  email: string;
  full_name: string;
}

export interface KvkkRequestItem {
  id: number;
  kind: KvkkRequestKind;
  kind_label: string;
  status: KvkkRequestStatus;
  status_label: string;
  target_user: KvkkRequestUserBrief | null;
  requester_user: KvkkRequestUserBrief | null;
  reason: string | null;
  admin_note: string | null;
  process_after: string | null;
  processed_at: string | null;
  created_at: string;
}

export interface KvkkDataInventoryItem {
  table_name: string;
  label: string;
  contains_pii: boolean;
  retention_days: number | null;
  legal_basis: string;
  purpose: string;
}

export interface KvkkDashboardResponse {
  summary: KvkkSummary;
  pending_rows: KvkkRequestItem[];
  recent_rows: KvkkRequestItem[];
  data_inventory: KvkkDataInventoryItem[];
}

export interface KvkkRejectBody {
  note: string;
}

export interface KvkkMutationResult {
  request: KvkkRequestItem | null;
  message: string;
}

// =============================================================================
// P5 — Usage
// =============================================================================

export interface UsageAccountInfo {
  plan_code: string;
  used_credits: number;
  allocated_credits: number;
  bonus_credits: number;
  total_allocated: number;
  remaining_credits: number;
  usage_pct: number;
  hard_block_enabled: boolean;
  blocked_until: string | null;
}

export interface UsageInstitutionRow {
  institution_id: number;
  name: string;
  slug: string;
  account: UsageAccountInfo;
}

export interface UsageIndependentRow {
  user_id: number;
  full_name: string;
  email: string;
  account: UsageAccountInfo;
}

export interface UsageTotals {
  inst_used: number;
  inst_alloc: number;
  indep_used: number;
  indep_alloc: number;
  grand_used: number;
  grand_alloc: number;
}

export interface UsageKindCost {
  kind: string;
  label: string;
  cost: number;
}

export interface AdminUsageResponse {
  period: string;
  inst_rows: UsageInstitutionRow[];
  indep_rows: UsageIndependentRow[];
  totals: UsageTotals;
  kind_costs: UsageKindCost[];
}

export interface UsageBonusBody {
  bonus_amount: number;
}

export interface UsageMutationResult {
  account: UsageAccountInfo | null;
  message: string;
}

// =============================================================================
// P5 — Quota
// =============================================================================

export interface QuotaCell {
  key: string;
  label: string;
  limit: number;
  current: number;
  pct: number;
  is_unlimited: boolean;
  is_at_limit: boolean;
  has_override: boolean;
  note: string | null;
}

export interface QuotaInstitutionRow {
  institution_id: number;
  name: string;
  slug: string;
  plan: string;
  cells: QuotaCell[];
  max_pct: number;
}

export interface QuotaPlanRow {
  plan: string;
  teachers: number;
  students: number;
  institution_admins: number;
}

export interface AdminQuotaResponse {
  rows: QuotaInstitutionRow[];
  quota_keys: string[];
  quota_labels: Record<string, string>;
  plans: QuotaPlanRow[];
}

export interface QuotaOverrideBody {
  quota_key: string;
  override_value: number;
  note?: string | null;
}

export interface QuotaMutationResult {
  message: string;
}

// =============================================================================
// P5 — Feature flags
// =============================================================================

export interface FeatureFlagItem {
  id: number;
  key: string;
  description: string;
  enabled_globally: boolean;
  override_enabled_count: number;
  override_disabled_count: number;
  override_total: number;
}

export interface FeatureFlagsListResponse {
  flags: FeatureFlagItem[];
}

export interface FeatureFlagOverrideItem {
  id: number;
  institution_id: number;
  institution_name: string;
  enabled: boolean;
  note: string | null;
}

export interface FeatureFlagInstitutionOption {
  id: number;
  name: string;
}

export interface FeatureFlagDetailResponse {
  id: number;
  key: string;
  description: string;
  enabled_globally: boolean;
  overrides: FeatureFlagOverrideItem[];
  available_institutions: FeatureFlagInstitutionOption[];
}

export interface FeatureFlagOverrideBody {
  institution_id: number;
  enabled?: boolean;
  note?: string | null;
}

export interface FeatureFlagMutationResult {
  message: string;
  enabled_globally: boolean | null;
}

// =============================================================================
// P6 — Feature Catalog (Vitrin Kartları)
// =============================================================================

export interface EnumOption {
  value: string;
  label: string;
}

export interface StatusOption {
  value: string;
  label: string;
  badge: string;
}

export interface MockupOption {
  key: string;
  label: string;
  description: string;
}

export interface FeatureCardScoreInputs {
  freshness: number;
  priority: number;
  tier_strength: number;
  completeness: number;
  role_match: number;
}

export interface FeatureCardFiredRule {
  label: string;
  strength: number;
}

export interface FeatureCardListItem {
  id: number;
  slug: string;
  title: string;
  tagline: string;
  accent_color: string;
  domain: string;
  domain_label: string;
  tier: string;
  tier_label: string;
  status: string;
  status_label: string;
  status_badge: string;
  strategic_priority: number;
  manual_pin: boolean;
  manual_hide: boolean;
  demo_slug: string | null;
  is_landing: boolean;
  score: number | null;
  score_inputs: FeatureCardScoreInputs | null;
  fired_rules: FeatureCardFiredRule[];
  impression: number;
  view: number;
  demo_click: number;
  cta_click: number;
  bandit_obs: number;
  bandit_mean: number | null;
  neighbor_sim: number | null;
}

export interface FeatureCatalogListResponse {
  cards: FeatureCardListItem[];
  counts: Record<string, number>;
  discovery_pending: number;
  landing_card_count: number;
  overall_diversity: number;
  learning_count: number;
  domains: EnumOption[];
  tiers: EnumOption[];
  statuses: StatusOption[];
  status_filter: string | null;
  domain_filter: string | null;
  tier_filter: string | null;
  q: string;
}

export interface FeatureCardFormMeta {
  domains: EnumOption[];
  tiers: EnumOption[];
  statuses: EnumOption[];
  roles: string[];
  mockups: MockupOption[];
}

export interface FeatureCardFull {
  id: number;
  slug: string;
  title: string;
  tagline: string;
  description_md: string;
  icon: string;
  accent_color: string;
  category_icon: string;
  category_label: string;
  demo_duration_label: string | null;
  mockup_type: string | null;
  target_roles: string[];
  benefits: string[];
  pain_points: string[];
  demo_slug: string | null;
  domain: string;
  tier: string;
  status: string;
  introduced_at: string | null;
  introduced_in_commit: string | null;
  pr_url: string | null;
  strategic_priority: number;
  manual_pin: boolean;
  pin_until: string | null;
  manual_hide: boolean;
  cta_label: string;
  cta_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface FeatureCardFormResponse {
  card: FeatureCardFull | null;
  meta: FeatureCardFormMeta;
}

export interface FeatureCardBody {
  slug?: string;
  title?: string;
  tagline?: string;
  description_md?: string;
  icon?: string;
  accent_color?: string;
  category_icon?: string;
  category_label?: string;
  demo_duration_label?: string;
  mockup_type?: string | null;
  target_roles?: string[];
  benefits?: string[];
  pain_points?: string[];
  demo_slug?: string;
  domain?: string;
  tier?: string;
  status?: string;
  introduced_at?: string | null;
  introduced_in_commit?: string;
  pr_url?: string;
  strategic_priority?: number;
  manual_pin?: boolean;
  pin_until?: string | null;
  manual_hide?: boolean;
  cta_label?: string;
  cta_url?: string;
}

export interface FeatureCardStatusBody {
  status: string;
}

export interface FeatureCardPinBody {
  pinned: boolean;
  pin_until?: string | null;
}

export interface FeatureCardMutationResult {
  message: string;
  card_id: number | null;
  slug: string | null;
}

export interface DiscoveryCardItem {
  id: number;
  slug: string;
  title: string;
  tagline: string;
  introduced_at: string | null;
  introduced_in_commit: string | null;
  manual_hide: boolean;
  is_migration: boolean;
  source_ref: string | null;
  raw_subject: string | null;
}

export interface DiscoveryQueueResponse {
  cards: DiscoveryCardItem[];
  counts: Record<string, number>;
  source: string;
  show_rejected: boolean;
}

export interface DiscoveryBulkBody {
  action: "reject" | "delete";
  ids: number[];
}

export interface DiscoveryMutationResult {
  message: string;
  affected: number | null;
}

export interface ExperimentVariantBrief {
  slug: string;
  label: string;
  strategy: string;
  weight: number;
  is_control: boolean;
}

export interface ExperimentListItem {
  id: number;
  slug: string;
  name: string;
  status: string;
  status_label: string;
  status_badge: string;
  hypothesis: string | null;
  start_at: string | null;
  variants: ExperimentVariantBrief[];
}

export interface ExperimentListResponse {
  experiments: ExperimentListItem[];
}

export interface ExperimentStrategyOption {
  key: string;
  label: string;
  description: string;
}

export interface ExperimentFormMeta {
  strategies: ExperimentStrategyOption[];
}

export interface ExperimentVariantStat {
  slug: string;
  label: string;
  strategy: string;
  strategy_label: string;
  weight: number;
  is_control: boolean;
  impression: number;
  view: number;
  demo_click: number;
  cta_click: number;
  total_clicks: number;
  ctr: number;
  ctr_low: number;
  ctr_high: number;
  lift_pct: number | null;
  vs_control_significant: boolean;
}

export interface ExperimentDetail {
  id: number;
  slug: string;
  name: string;
  status: string;
  status_label: string;
  status_badge: string;
  hypothesis: string | null;
  start_at: string | null;
  end_at: string | null;
  variants: ExperimentVariantBrief[];
}

export interface ExperimentDetailResponse {
  experiment: ExperimentDetail;
  stats: ExperimentVariantStat[];
  has_any_data: boolean;
}

export interface ExperimentCreateBody {
  name: string;
  slug?: string;
  hypothesis?: string;
  ctrl_strategy?: string;
  test_strategy?: string;
  weight_ctrl?: number;
  weight_test?: number;
}

export interface ExperimentStatusBody {
  status: string;
}

export interface ExperimentMutationResult {
  message: string;
  experiment_id: number | null;
  slug: string | null;
}

export interface DashboardSummary {
  total: number;
  published: number;
  draft: number;
  hidden: number;
  landing: number;
  queue_pending: number;
  active_experiment: number;
}

export interface DashboardLandingHealth {
  landing_count: number;
  diversity_pct: number;
  diversity_score: number;
  learning_count: number;
}

export interface DashboardWindowMetrics {
  events: number;
  impressions: number;
  views: number;
  demo_clicks: number;
  cta_clicks: number;
  total_clicks: number;
  ctr_pct: number;
  new_discoveries: number;
  bandit_updates: number;
  window_days: number;
}

export interface DashboardExperimentVariant {
  slug: string;
  label: string;
  is_control: boolean;
  ctr: number;
  total_clicks: number;
  impression: number;
  lift_pct: number | null;
  vs_control_significant: boolean;
}

export interface DashboardExperiment {
  id: number;
  name: string;
  slug: string;
  started_days_ago: number;
  total_impressions: number;
  has_significance: boolean;
  variants: DashboardExperimentVariant[];
}

export interface DashboardAnomaly {
  severity: string;
  title: string;
  hint: string;
  action_url: string;
  action_label: string;
}

export interface DashboardAuditItem {
  action: string;
  action_label: string;
  target_id: number | null;
  target_slug: string | null;
  actor_id: number | null;
  when: string | null;
  ago_seconds: number;
  ago_label: string;
}

export interface FeatureCatalogDashboardResponse {
  summary: DashboardSummary;
  landing_health: DashboardLandingHealth;
  last_7d: DashboardWindowMetrics;
  experiment: DashboardExperiment | null;
  anomalies: DashboardAnomaly[];
  recent_audit: DashboardAuditItem[];
  window_days: number;
  generated_at: string;
}

// =============================================================================
// P7a — Ticari Pano: Analitik çekirdek
// =============================================================================

export interface ActionSignalItem {
  kind: string;
  severity: string;
  score: number;
  title: string;
  description: string;
}

export interface SuggestedActionItem {
  kind: string;
  summary: string;
  label: string;
  icon: string;
  color: string;
}

export interface ActionCenterItem {
  institution_id: number;
  institution_name: string;
  plan: string;
  plan_label: string;
  monthly_price_try: number;
  total_score: number;
  severity: string;
  primary_signal: ActionSignalItem;
  other_signals: ActionSignalItem[];
  suggested_actions: SuggestedActionItem[];
  last_action_at: string | null;
  last_action_summary: string | null;
}

export interface ActionCenterResponse {
  generated_at: string;
  items: ActionCenterItem[];
  total_count: number;
  severity_counts: Record<string, number>;
}

export interface QuickActionBody {
  institution_id: number;
  kind: string;
  summary: string;
  result?: string;
  follow_up_days?: number;
}

export interface RevenueMutationResult {
  message: string;
}

export interface AtRiskInstitutionItem {
  institution_id: number;
  name: string;
  plan: string;
  monthly_price_try: number;
  health_score: number | null;
  severity: string;
  owner_type: string;
  detail_url: string;
}

export interface RiskAtMrr {
  total_at_risk_mrr: number;
  critical_mrr: number;
  risk_mrr: number;
  critical_count: number;
  risk_count: number;
  institutions: AtRiskInstitutionItem[];
}

export interface MrrProjection {
  current_mrr: number;
  horizon_days: number;
  trial_conversion_rate: number;
  monthly_churn_rate: number;
  trial_ending_count: number;
  expected_trial_conversions_mrr: number;
  expected_churn_mrr: number;
  expected_at_risk_loss_mrr: number;
  projected_mrr_status_quo: number;
  projected_mrr_with_intervention: number;
  delta_mrr: number;
  intervention_save_rate: number;
  at_risk_critical_count: number;
  at_risk_risk_count: number;
}

export interface ScenarioHorizon {
  horizon_days: number;
  status_quo_mrr: number;
  intervention_mrr: number;
  delta_mrr: number;
}

export interface ScenarioComparison {
  current_mrr: number;
  save_rate: number;
  horizons: ScenarioHorizon[];
}

export interface RevenueForecastResponse {
  risk: RiskAtMrr;
  proj_30: MrrProjection;
  proj_60: MrrProjection;
  proj_90: MrrProjection;
  scenario: ScenarioComparison;
  save_rate: number;
  save_rate_pct: number;
}

export interface CohortRetentionCell {
  month: number;
  count: number | null;
  pct: number | null;
  color: string;
  future: boolean;
}

export interface CohortRow {
  cohort_key: string;
  cohort_label: string;
  signup_count: number;
  signup_month_age: number;
  retention: CohortRetentionCell[];
}

export interface CohortMatrix {
  cohorts: CohortRow[];
  horizon_months: number;
  months_back: number;
  total_signups: number;
}

export interface PlanChurnSummary {
  window_days: number;
  signup_count: number;
  trial_expired_count: number;
  trial_converted_count: number;
  trial_conversion_pct: number | null;
  upgrade_count: number;
  downgrade_count: number;
  cancel_count: number;
  net_movement: number;
}

export interface PlanLtvItem {
  plan: string;
  label: string;
  monthly_price_try: number;
  active_count: number;
  avg_age_months: number;
  estimated_ltv_try: number;
}

export interface LtvEstimate {
  plans: PlanLtvItem[];
  total_ltv_try: number;
  paying_count: number;
  avg_ltv_per_paying: number;
}

export interface RevenueCohortResponse {
  matrix: CohortMatrix;
  churn: PlanChurnSummary;
  ltv: LtvEstimate;
  months_back: number;
  horizon: number;
  churn_days: number;
}

// =============================================================================
// P7b — Ticari Pano: 360 + CRM (Owner-pattern)
// =============================================================================

export type OwnerType = "institution" | "user";

export interface CrmEnumOption {
  value: string;
  label: string;
  color?: string | null;
}

export interface CrmNoteItem {
  id: number;
  content: string;
  pinned: boolean;
  created_at: string | null;
  created_by_name: string | null;
}

export interface CrmActionItem {
  id: number;
  kind: string;
  kind_label: string;
  summary: string;
  notes: string | null;
  result: string;
  result_label: string;
  result_color: string;
  follow_up_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  created_by_name: string | null;
}

export interface OwnerTagItem {
  id: number;
  kind: string;
  label: string;
  color: string;
  icon: string;
  description: string;
  note: string | null;
}

export interface OwnerTagOption {
  value: string;
  label: string;
  color: string;
  icon: string;
  description: string;
}

export interface OwnerContactData {
  responsible_person_name: string | null;
  responsible_person_title: string | null;
  billing_email: string | null;
  phone: string | null;
  whatsapp: string | null;
  linkedin_url: string | null;
  website: string | null;
  address: string | null;
  note: string | null;
  updated_at: string | null;
}

export interface PlanChangeItem {
  id: number;
  from_plan: string | null;
  to_plan: string | null;
  reason: string;
  occurred_at: string | null;
}

export interface HealthComponentItem {
  code: string;
  label: string;
  weight_pct: number;
  value_pct: number;
  contribution: number;
  note: string | null;
}

export interface HealthScoreV2Data {
  score: number;
  band: string;
  band_label: string;
  band_color: string;
  band_emoji: string;
  components: HealthComponentItem[];
  active_teacher_count: number;
  active_student_count: number;
}

export interface HealthTriggerItem {
  code: string;
  title: string;
  detail: string;
  severity: string;
}

export interface HealthHistoryPoint {
  snapshot_date: string;
  score: number;
  band: string;
}

export interface CrmMeta {
  action_kinds: CrmEnumOption[];
  action_results: CrmEnumOption[];
  tag_kinds: OwnerTagOption[];
  offer_kinds: EnumOption[];
}

export interface Institution360Admin {
  id: number;
  name: string;
  email: string | null;
}

export interface Institution360Identity {
  id: number;
  name: string;
  slug: string;
  contact_email: string | null;
  is_active: boolean;
  plan: string;
  plan_label: string;
  plan_monthly_price_try: number;
  trial_ends_at: string | null;
  post_trial_plan: string | null;
  subscription_kind: string | null;
  subscription_period_end: string | null;
  subscription_pause_until: string | null;
  performance_guarantee: boolean;
  created_at: string | null;
  admins: Institution360Admin[];
}

export interface Institution360Health {
  score: number | null;
  level: string;
  emoji: string;
  color: string;
  label: string;
}

export interface Institution360Usage {
  days: number;
  active_teacher_count: number;
  total_teacher_count: number;
  teacher_active_pct: number | null;
  active_student_count: number;
  total_student_count: number;
  student_active_pct: number | null;
  notification_sent: number;
  notification_failed: number;
  study_sessions: number;
}

export interface Institution360Billing {
  last_paid_at: string | null;
  last_paid_amount_try: number | null;
  next_due_at: string | null;
  next_due_amount_try: number | null;
  overdue_count: number;
  overdue_total_try: number;
  lifetime_paid_try: number;
}

export interface Risk360Item {
  kind: string;
  severity: string;
  title: string;
  message: string;
  weight: number;
}

export interface InstitutionRevenue360Response {
  identity: Institution360Identity;
  health: Institution360Health;
  usage_30d: Institution360Usage;
  billing: Institution360Billing;
  risks: Risk360Item[];
  crm_notes: CrmNoteItem[];
  crm_actions: CrmActionItem[];
  health_v2: HealthScoreV2Data | null;
  health_triggers: HealthTriggerItem[];
  health_history: HealthHistoryPoint[];
  owner_tags: OwnerTagItem[];
  owner_contact: OwnerContactData | null;
  plan_changes: PlanChangeItem[];
  offers: OfferItem[];
  invoices: InvoiceItem[];
  meta: CrmMeta;
}

export interface OwnerBrief {
  owner_type: string;
  owner_id: number;
  name: string;
  email: string | null;
  plan: string;
  is_active: boolean;
  monthly_price_try: number;
  trial_ends_at: string | null;
}

export interface StudentHealthCounts {
  healthy: number;
  watch: number;
  risk: number;
  critical: number;
  unhealthy_total: number;
  total: number;
}

export interface StudentRow {
  id: number;
  full_name: string | null;
  grade_level: number | null;
  is_active: boolean;
  band: string;
  label: string;
}

export interface UserRevenue360Response {
  owner: OwnerBrief;
  teacher_band: string;
  teacher_login_label: string;
  student_count: number;
  all_students_total: number;
  student_health: StudentHealthCounts;
  student_rows: StudentRow[];
  tasks_planned_30d: number;
  tasks_completed_30d: number;
  tasks_draft_30d: number;
  completion_pct: number;
  crm_notes: CrmNoteItem[];
  crm_actions: CrmActionItem[];
  health_v2: HealthScoreV2Data | null;
  score_history: HealthHistoryPoint[];
  owner_tags: OwnerTagItem[];
  owner_contact: OwnerContactData | null;
  plan_changes: PlanChangeItem[];
  offers: OfferItem[];
  invoices: InvoiceItem[];
  meta: CrmMeta;
}

export interface CrmNoteBody {
  content: string;
  pinned?: boolean;
}

export interface CrmActionBody {
  kind: string;
  summary: string;
  notes?: string;
  result?: string;
  follow_up_at?: string | null;
}

export interface CrmActionCompleteBody {
  result: string;
  notes?: string;
}

export interface OwnerContactBody {
  responsible_person_name?: string;
  responsible_person_title?: string;
  billing_email?: string;
  phone?: string;
  whatsapp?: string;
  linkedin_url?: string;
  website?: string;
  address?: string;
  note?: string;
}

export interface OwnerTagBody {
  kind: string;
  note?: string;
}

export interface Revenue360MutationResult {
  message: string;
}

// =============================================================================
// P7c — Teklifler + Aksiyon Şablonları + Fatura Tahsilat
// =============================================================================

export interface OfferItem {
  id: number;
  kind: string;
  kind_label: string;
  title: string;
  value: number | null;
  value_unit: string | null;
  duration_months: number | null;
  new_plan: string | null;
  public_message: string | null;
  admin_note: string | null;
  status: string;
  status_label: string;
  status_color: string;
  summary: string;
  token: string;
  sent_at: string | null;
  responded_at: string | null;
  expires_at: string | null;
  decline_reason: string | null;
  created_at: string | null;
}

export interface OfferBody {
  kind: string;
  title: string;
  value?: number | null;
  duration_months?: number | null;
  new_plan?: string;
  public_message?: string;
  admin_note?: string;
  expires_in_days?: number;
  send_now?: boolean;
}

export interface InvoiceItem {
  invoice_id: number;
  owner_type: string;
  owner_id: number | null;
  plan: string;
  plan_label: string;
  amount_try: number;
  status: string;
  status_label: string;
  due_at: string | null;
  paid_at: string | null;
  days_until_due: number | null;
  days_overdue: number;
  payment_method: string | null;
  attempt_count: number;
  last_reminder_kind: string | null;
  detail_url: string;
}

export interface InvoicePostponeBody {
  days?: number;
  note?: string;
}

export interface InvoiceMarkPaidBody {
  method?: string;
  note?: string;
}

export interface InvoiceCancelBody {
  note?: string;
}

export interface InvoiceReminderBody {
  kind?: string;
}

export interface ActionTemplateItem {
  id: number;
  name: string;
  kind: string;
  kind_label: string;
  subject: string | null;
  body: string;
  description: string | null;
  is_active: boolean;
}

export interface ActionTemplatesResponse {
  templates: ActionTemplateItem[];
  kinds: EnumOption[];
}

export interface ActionTemplateBody {
  name: string;
  kind: string;
  body: string;
  subject?: string;
  description?: string;
  is_active?: boolean | null;
}

export interface ActionTemplateRenderResponse {
  ok: boolean;
  id: number;
  name: string;
  kind: string;
  subject: string;
  body: string;
}

export interface RevenueOfferMutationResult {
  message: string;
  offer_id: number | null;
}

export interface InvoiceMutationResult {
  message: string;
  invoice_id: number | null;
}

export interface ActionTemplateMutationResult {
  message: string;
  template_id: number | null;
}

// =============================================================================
// P7d — Toplu Kampanyalar
// =============================================================================

export interface CampaignFunnel {
  targeted: number;
  sent: number;
  accepted: number;
  declined: number;
  expired: number;
  bounced: number;
  total: number;
  sent_total: number;
  accepted_pct: number | null;
}

export interface CampaignListItem {
  id: number;
  name: string;
  description: string | null;
  segment: string;
  segment_label: string;
  status: string;
  status_label: string;
  status_color: string;
  has_variant_b: boolean;
  created_at: string | null;
  funnel: CampaignFunnel;
}

export interface CampaignsListResponse {
  campaigns: CampaignListItem[];
}

export interface CampaignSegmentOption {
  value: string;
  label: string;
  description: string;
}

export interface CampaignFormMeta {
  segments: CampaignSegmentOption[];
  offer_kinds: EnumOption[];
}

export interface CampaignPreviewOwner {
  owner_type: string;
  owner_id: number;
  name: string;
  plan: string;
  url: string;
}

export interface CampaignPreviewBody {
  segment: string;
  filter_plan?: string;
}

export interface CampaignPreviewResponse {
  count: number;
  inst_count: number;
  user_count: number;
  preview: CampaignPreviewOwner[];
}

export interface CampaignBody {
  name: string;
  segment: string;
  filter_plan?: string;
  description?: string;
  admin_note?: string;
  variant_a_kind: string;
  variant_a_title: string;
  variant_a_value?: number | null;
  variant_a_duration_months?: number | null;
  variant_a_new_plan?: string;
  variant_a_public_message?: string;
  has_variant_b?: boolean;
  variant_b_kind?: string;
  variant_b_title?: string;
  variant_b_value?: number | null;
  variant_b_duration_months?: number | null;
  variant_b_new_plan?: string;
  variant_b_public_message?: string;
  offer_expires_in_days?: number;
}

export interface CampaignVariant {
  kind: string;
  kind_label: string;
  title: string;
  value: number | null;
  duration_months: number | null;
  new_plan: string | null;
  public_message: string | null;
}

export interface CampaignDetail {
  id: number;
  name: string;
  description: string | null;
  admin_note: string | null;
  segment: string;
  segment_label: string;
  segment_filter_plan: string | null;
  status: string;
  status_label: string;
  status_color: string;
  has_variant_b: boolean;
  variant_a: CampaignVariant;
  variant_b: CampaignVariant | null;
  offer_expires_in_days: number;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface CampaignRecipientItem {
  id: number;
  owner_type: string;
  owner_id: number | null;
  owner_name: string;
  owner_plan: string | null;
  owner_url: string;
  variant: string;
  status: string;
  status_label: string;
  sent_at: string | null;
  responded_at: string | null;
  offer_id: number | null;
  offer_token: string | null;
  error_note: string | null;
}

export interface CampaignStatsFull {
  status: string;
  overall: CampaignFunnel;
  variant_a: CampaignFunnel;
  variant_b: CampaignFunnel | null;
  has_variant_b: boolean;
  institution_count: number;
  user_count: number;
}

export interface CampaignDetailResponse {
  campaign: CampaignDetail;
  stats: CampaignStatsFull;
  recipients: CampaignRecipientItem[];
}

export interface CampaignMutationResult {
  message: string;
  campaign_id: number | null;
  recipient_count?: number | null;
  sent?: number | null;
  errors?: number | null;
}

// =============================================================================
// G1 — Ticari Ana Dashboard (security-monitor/revenue)
// =============================================================================

export interface RevenueMrr {
  total_try: number;
  paying_institutions: number;
  free_institutions: number;
  total_institutions: number;
  avg_per_paying: number;
}

export interface RevenuePlanDist {
  plan: string;
  label: string;
  count: number;
  monthly_price_try: number;
  estimated_mrr: number;
}

export interface RevenueTrialEntry {
  institution_id: number;
  institution_name: string;
  plan: string;
  trial_ends_at: string | null;
  days_left: number;
  post_trial_plan: string | null;
}

export interface RevenueChangeSummary {
  days: number;
  by_reason: Record<string, number>;
  net_growth: number;
  signups: number;
  upgrades: number;
  downgrades: number;
  trial_expired: number;
  pauses: number;
}

export interface RevenueDailyChange {
  day: string;
  signup: number;
  upgrade: number;
  downgrade: number;
  trial_expired: number;
  pause: number;
  total: number;
}

export interface RevenueChurnProxy {
  healthy: number;
  watch: number;
  risk: number;
  critical: number;
  unhealthy_total: number;
  needs_attention: number | null;
}

export interface RevenuePaymentBucket {
  key: string;
  label: string;
  count: number;
  total_try: number;
}

export interface RevenuePaymentCalendar {
  buckets: RevenuePaymentBucket[];
  total_count: number;
  total_amount_try: number;
  overdue_total_try: number;
  upcoming_total_try: number;
  days_horizon: number;
}

export interface RevenueOwnerMrr {
  total_try: number;
  institution_mrr_try: number;
  user_mrr_try: number;
  total_owners: number;
  institution_count: number;
  user_count: number;
  paying_count: number;
  institution_paying_count: number;
  user_paying_count: number;
  avg_per_paying: number;
}

export interface RevenueOwnerPlanDist {
  plan: string;
  label: string;
  count: number;
  institution_count: number;
  user_count: number;
  monthly_price_try: number;
  estimated_mrr: number;
}

export interface RevenueOwnerTrial {
  owner_type: string;
  owner_id: number;
  name: string;
  plan: string;
  trial_ends_at: string | null;
  url: string;
}

export interface RevenueDashboardResponse {
  generated_at: string;
  mrr: RevenueMrr;
  plan_distribution: RevenuePlanDist[];
  trial_ending_soon: RevenueTrialEntry[];
  trial_expired_30d: number;
  change_summary_30d: RevenueChangeSummary;
  daily_changes_30d: RevenueDailyChange[];
  churn_proxy: RevenueChurnProxy;
  payment_calendar: RevenuePaymentCalendar;
  mrr_combined: RevenueOwnerMrr | null;
  plan_dist_combined: RevenueOwnerPlanDist[];
  trial_combined: RevenueOwnerTrial[];
  segment: string;
  segment_counts: Record<string, number>;
}

export interface RevenueDrillRow {
  institution_id: number;
  institution_name: string;
  plan: string;
  plan_label: string;
  monthly_price_try: number | null;
  is_active: boolean | null;
  trial_ends_at: string | null;
  post_trial_plan: string | null;
  reason: string | null;
  detail_url: string;
  health_score: number | null;
  active_teacher_pct: number | null;
  active_student_pct: number | null;
  event_at: string | null;
  event_days_ago: number | null;
}

export interface RevenueDrillResponse {
  title: string;
  icon: string;
  key: string;
  plan: string | null;
  count: number;
  rows: RevenueDrillRow[];
  error: string | null;
}

export interface RevenueInvoiceRow {
  id: number;
  owner_type: string;
  owner_id: number | null;
  owner_name: string;
  owner_url: string;
  plan: string;
  amount_try: number;
  status: string;
  status_label: string;
  status_color: string;
  due_at: string | null;
  paid_at: string | null;
  payment_method: string | null;
}

export interface RevenueInvoiceStatusCount {
  count: number;
  total_try: number;
}

export interface RevenueInvoicesResponse {
  rows: RevenueInvoiceRow[];
  status_counts: Record<string, RevenueInvoiceStatusCount>;
  statuses: StatusOption[];
  status_filter: string | null;
}

// =============================================================================
// G2a — Güvenlik Kamarası: Genel Bakış + Bütünlük + Sistem + Bildirim
// =============================================================================

export interface SecuritySessionItem {
  id: number;
  session_token: string;
  user_id: number;
  user_email: string;
  user_full_name: string | null;
  role: string;
  ip: string | null;
  user_agent: string;
  login_at: string | null;
  last_seen_at: string | null;
  idle_seconds: number;
  age_seconds: number;
}

export interface SecuritySuspiciousIp {
  id: number;
  ip: string;
  fail_count: number;
  distinct_email_count: number;
  distinct_emails: string[];
  first_seen_at: string | null;
  last_seen_at: string | null;
  is_blocked: boolean;
  blocked_until: string | null;
  block_reason: string | null;
  block_note: string | null;
}

export interface SecurityFailedBucket {
  ip: string | null;
  fail_count: number;
  distinct_email_count: number;
  last_seen_at: string | null;
}

export interface SecurityImpersonationItem {
  id: number;
  actor_user_id: number;
  actor_email: string | null;
  actor_full_name: string | null;
  target_user_id: number;
  target_email: string | null;
  target_full_name: string | null;
  reason: string | null;
  started_at: string | null;
  expires_at: string | null;
  ip: string | null;
  is_expired_now: boolean;
  seconds_left: number;
  age_seconds: number;
}

export interface AttentionItemModel {
  severity: string;
  icon: string;
  title: string;
  description: string;
  action_url: string;
  action_label: string;
  category: string;
  ts: string | null;
  score: number;
  explainer: string;
}

export interface AttentionSummaryModel {
  items: AttentionItemModel[];
  total: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
  top_severity: string;
  is_clean: boolean;
}

export interface SecuritySummary {
  active_sessions: number;
  blocked_ips: number;
  watched_ips: number;
  failed_24h: number;
  critical_24h: number;
  super_admin_logins_24h: number;
}

export interface ErrorSummaryModel {
  open_groups: number;
  new_groups_24h: number;
  total_events_24h: number;
  window_hours: number;
}

export interface SecurityOverviewResponse {
  generated_at: string;
  summary: SecuritySummary;
  role_counts: Record<string, number>;
  active_sessions: SecuritySessionItem[];
  suspicious_ips: SecuritySuspiciousIp[];
  failed_login_buckets: SecurityFailedBucket[];
  critical_audits: AuditLogItem[];
  super_admin_logins: AuditLogItem[];
  active_impersonations: SecurityImpersonationItem[];
  abuse_open_count: number;
  system_error_summary: ErrorSummaryModel;
  unack_alarm_count: number;
  attention: AttentionSummaryModel;
}

export interface IntegrityMigration {
  status: string;
  head: string | null;
  current: string | null;
  pending: boolean;
  error: string | null;
}

export interface IntegrityDbFile {
  path: string | null;
  size_mb: number;
  size_bytes: number | null;
  modified_at: string | null;
  age_seconds: number;
  level: string;
}

export interface IntegrityOrphanFinding {
  kind: string;
  label: string;
  count: number;
  samples: Record<string, unknown>[];
}

export interface IntegrityOrphans {
  total_findings: number;
  findings: IntegrityOrphanFinding[];
}

export interface IntegrityKvkkSample {
  id: number;
  kind: string;
  status: string;
  created_at: string | null;
  age_days: number;
}

export interface IntegrityKvkk {
  sla_days: number;
  overdue_count: number;
  open_total: number;
  overdue_samples: IntegrityKvkkSample[];
}

export interface IntegrityCronJob {
  job_key: string;
  last_run_at: string | null;
  age_hours: number | null;
  level: string;
  last_status: string | null;
  last_error: string | null;
}

export interface IntegrityCronDrift {
  summary: Record<string, number>;
  jobs: IntegrityCronJob[];
}

export interface IntegrityResponse {
  generated_at: string;
  migration: IntegrityMigration;
  db_file: IntegrityDbFile;
  orphans: IntegrityOrphans;
  kvkk_sla: IntegrityKvkk;
  cron_drift: IntegrityCronDrift;
}

export interface SystemErrorGroup {
  id: number;
  signature: string;
  endpoint: string;
  method: string;
  status_code: number;
  exception_type: string;
  exception_message: string | null;
  stack_trace: string | null;
  count: number;
  first_seen_at: string | null;
  last_seen_at: string | null;
  age_seconds: number;
  resolved_at: string | null;
  last_ip: string | null;
  last_actor_user_id: number | null;
}

export interface SystemEndpointError {
  endpoint: string;
  method: string;
  total: number;
  groups: number;
}

export interface SystemSlowRequest {
  id: number;
  endpoint: string;
  method: string;
  status_code: number;
  response_time_ms: number;
  recorded_at: string | null;
  ip: string | null;
}

export interface SystemHealthDataResponse {
  generated_at: string;
  summary: ErrorSummaryModel;
  error_groups: SystemErrorGroup[];
  endpoint_top: SystemEndpointError[];
  slow_requests: SystemSlowRequest[];
}

export interface SystemMutationResult {
  message: string;
  error_id: number | null;
}

export interface NotifWindowSummary {
  window_label: string;
  window_hours: number;
  total: number;
  sent: number;
  failed: number;
  queued: number;
  suppressed: number;
  success_pct: number | null;
}

export interface NotifMatrix {
  rows: string[];
  statuses: string[];
  matrix: Record<string, Record<string, number>>;
  rollups: Record<string, { total: number; success_pct: number | null }>;
  window_hours: number;
}

export interface NotifSuppressItem {
  slug: string;
  label: string;
  count: number;
}

export interface NotifDailyTrend {
  day: string;
  sent: number;
  failed: number;
  queued: number;
  suppressed: number;
  total: number;
  success_pct: number | null;
}

export interface NotifFailureItem {
  id: number;
  queued_at: string | null;
  parent_id: number | null;
  parent_name: string | null;
  parent_email: string | null;
  student_id: number | null;
  student_name: string | null;
  kind: string;
  channel: string;
  attempts: number | null;
  error: string;
}

export interface NotificationHealthResponse {
  generated_at: string;
  summary_24h: NotifWindowSummary;
  summary_7d: NotifWindowSummary;
  oldest_queued_minutes: number | null;
  channel_matrix_24h: NotifMatrix;
  kind_matrix_24h: NotifMatrix;
  suppress_distribution_24h: NotifSuppressItem[];
  daily_trend_7d: NotifDailyTrend[];
  recent_failures_24h: NotifFailureItem[];
}

// =============================================================================
// G2b — Güvenlik Kamarası: Aktivite Kamerası
// =============================================================================

export type ActivitySegment = "all" | "institution" | "solo";

export interface ActivityTotals {
  dau: number;
  wau: number;
  mau: number;
}

export interface ActivityRoleBreakdownRow {
  role: string;
  label: string;
  color: string;
  icon: string;
  today: number;
  yesterday: number;
  delta: number;
  delta_pct: number;
}

export interface ActivityWow {
  day_labels: string[];
  this_dates: string[];
  last_dates: string[];
  this_series: number[];
  last_series: number[];
  this_total: number;
  last_total: number;
  delta: number;
  delta_pct: number;
  max_value: number;
}

export interface ActivitySoloMetric {
  ratio_pct: number | null;
  sent_count: number | null;
  total: number | null;
  avg_per_student_per_week: number | null;
  total_tasks: number | null;
  total_students: number | null;
  weeks: number | null;
  avg_missing_weeks: number | null;
  consistent_count: number | null;
  label: string;
  color: string;
}

export interface ActivitySoloSpecial {
  parent_outreach: ActivitySoloMetric;
  discipline: ActivitySoloMetric;
  consistency: ActivitySoloMetric;
}

export interface ActivityCriticalSummary {
  stickiness_pct: number;
  stickiness_color: string;
  stickiness_label: string;
  critical_institutions: number;
  sharp_drop_count: number;
  paying_idle_count: number;
  onboarding_stuck_count: number;
  champion_count: number;
}

export interface ActivityHeartbeatRow {
  owner_type: string;
  owner_id: number | null;
  institution_id: number | null;
  institution_name: string | null;
  plan: string | null;
  last_login_at: string | null;
  last_source: string | null;
  days_since_login: number | null;
  band: string;
  band_color: string;
  label: string;
  detail_url: string;
  student_count: number | null;
}

export interface ActivityHeartbeatSummary {
  healthy: number;
  watch: number;
  warning: number;
  critical: number;
  dead: number;
  no_login: number;
  total: number;
  unhealthy: number;
}

export interface ActivityDecayRow {
  owner_type: string;
  owner_id: number | null;
  institution_id: number | null;
  institution_name: string | null;
  plan: string | null;
  recent_7d: number;
  previous_7d: number;
  change_pct: number;
  band: string;
  color: string;
  label: string;
  detail_url: string;
}

export interface ActivityPlanActivityCell {
  owner_type: string;
  owner_id: number | null;
  institution_id: number | null;
  institution_name: string | null;
  plan: string | null;
  days_since_login: number | null;
  label: string;
  band_color: string;
  detail_url: string;
}

export interface ActivityPlanActivityMatrix {
  paying_active: ActivityPlanActivityCell[];
  paying_idle: ActivityPlanActivityCell[];
  free_active: ActivityPlanActivityCell[];
  free_idle: ActivityPlanActivityCell[];
  totals: Record<string, number>;
  active_days: number;
}

export interface ActivitySilentRow {
  owner_type: string;
  owner_id: number | null;
  tenant_id: number | null;
  tenant_name: string | null;
  plan: string | null;
  days_since_login: number | null;
  detail_url: string | null;
}

export interface ActivityStickiness {
  dau: number;
  mau: number;
  ratio_pct: number;
  band: string;
  color: string;
  label: string;
}

export interface ActivityStickinessPoint {
  day: string;
  dau: number;
  mau: number;
  ratio: number;
}

export interface ActivityRetentionMetric {
  total: number;
  active: number;
  ratio_pct: number | null;
  health: string | null;
  color: string | null;
}

export interface ActivityResurrectedRow {
  user_id: number;
  name: string;
  email: string | null;
  role: string | null;
  institution_id: number | null;
  previous_last_login: string | null;
  returned_at: string | null;
  gap_days: number;
}

export interface ActivitySessionBands {
  under_1: number;
  min_1_5: number;
  min_5_15: number;
  min_15_30: number;
  over_30: number;
}

export interface ActivitySessionDuration {
  count: number;
  avg_min: number;
  median_min: number;
  under_1min: number;
  under_1_pct: number;
  over_30min: number;
  over_30_pct: number;
  bands: ActivitySessionBands;
  days_window: number;
}

export interface ActivityRatioRow {
  owner_type: string;
  owner_id: number | null;
  institution_id: number | null;
  institution_name: string | null;
  plan: string | null;
  active_teachers: number;
  active_students: number;
  total_students: number | null;
  ratio: number | null;
  band: string;
  color: string;
  label: string;
  detail_url: string;
}

export interface ActivityPowerUser {
  user_id: number;
  name: string;
  email: string | null;
  role: string | null;
  institution_id: number | null;
  institution_name: string | null;
  active_days: number;
  activity_pct: number;
}

export interface ActivityPowerUsers {
  top: ActivityPowerUser[];
  bottom: ActivityPowerUser[];
  days_window: number;
  total_active_users: number;
}

export interface ActivityFeaturePopularity {
  key: string;
  label: string;
  icon: string;
  total_events: number;
  distinct_institutions: number;
  distinct_users: number;
}

export interface ActivityFeatureDef {
  key: string;
  label: string;
  icon: string;
}

export interface ActivityFeatureMatrixCell {
  key: string;
  used: boolean;
}

export interface ActivityFeatureMatrixRow {
  owner_type: string;
  owner_id: number | null;
  institution_id: number | null;
  institution_name: string | null;
  plan: string | null;
  cells: ActivityFeatureMatrixCell[];
  adopted_count: number;
  adoption_pct: number;
  detail_url: string;
}

export interface ActivityFeatureMatrix {
  features: ActivityFeatureDef[];
  rows: ActivityFeatureMatrixRow[];
  days_window: number;
}

export interface ActivityMilestone {
  key: string;
  label: string;
  done: boolean | null;
}

export interface ActivityOnboardingRow {
  owner_type: string;
  owner_id: number | null;
  institution_id: number | null;
  institution_name: string | null;
  plan: string | null;
  age_days: number;
  milestones: ActivityMilestone[];
  done_count: number;
  total_count: number;
  completion_pct: number;
  detail_url: string;
}

export interface ActivityPlanBenchmarkRow {
  owner_type: string;
  plan: string;
  plan_label: string;
  monthly_price: number;
  institution_count: number;
  avg_active_teachers: number;
  avg_active_students: number;
  avg_feature_adoption: number;
  avg_feature_adoption_pct: number;
  feature_total: number;
  avg_session_min: number;
}

export interface ActivityChampionRow {
  owner_type: string;
  owner_id: number | null;
  institution_id: number | null;
  institution_name: string | null;
  plan: string | null;
  is_paying: boolean;
  score: number;
  density: number;
  active_user_count: number;
  feature_adoption: number;
  feature_total: number;
  age_months: number;
  student_teacher_ratio: number;
  detail_url: string;
  is_champion: boolean;
}

export interface ActivityHeatmap {
  days_window: number;
  matrix: Record<string, Record<string, number>>;
  max_value: number;
  total: number;
  day_labels: string[];
}

export interface ActivityPerTenant {
  tenant_id: number;
  tenant_name: string;
  plan: string | null;
  dau: number;
  wau: number;
  mau: number;
}

export interface ActivityDauTrendPoint {
  day: string;
  dau: number;
}

export interface ActionSuggestion {
  kind: string;
  label: string;
  hint: string;
}

export interface ActivityPanelResponse {
  generated_at: string;
  segment: ActivitySegment;
  totals: ActivityTotals;
  per_tenant: ActivityPerTenant[];
  heatmap: ActivityHeatmap;
  dau_trend_14d: ActivityDauTrendPoint[];
  silent_tenants_7d: ActivitySilentRow[];
  role_breakdown: ActivityRoleBreakdownRow[];
  heartbeats: ActivityHeartbeatRow[];
  heartbeat_summary: ActivityHeartbeatSummary;
  wow: ActivityWow;
  stickiness: ActivityStickiness;
  stickiness_trend_30d: ActivityStickinessPoint[];
  week1: ActivityRetentionMetric;
  day30: ActivityRetentionMetric;
  resurrected: ActivityResurrectedRow[];
  decay_rates: ActivityDecayRow[];
  plan_activity: ActivityPlanActivityMatrix;
  session_duration: ActivitySessionDuration;
  teacher_student_ratios: ActivityRatioRow[];
  power_users: ActivityPowerUsers;
  feature_popularity: ActivityFeaturePopularity[];
  feature_matrix: ActivityFeatureMatrix;
  onboarding: ActivityOnboardingRow[];
  plan_benchmark: ActivityPlanBenchmarkRow[];
  champions: ActivityChampionRow[];
  action_suggestions: Record<string, ActionSuggestion[]>;
  solo_special: ActivitySoloSpecial | null;
  critical_summary: ActivityCriticalSummary;
}

export interface ActiveUsersDrillRow {
  user_id: number;
  name: string;
  email: string | null;
  role: string | null;
  institution_id: number | null;
  institution_name: string | null;
  last_login_at: string | null;
}

export interface ActiveUsersDrillResponse {
  window: string;
  window_label: string;
  role: string;
  role_label: string;
  rows: ActiveUsersDrillRow[];
}

export interface HeatmapPattern {
  label: string;
  tone: string;
  detail: string | null;
}

export interface InstitutionHeatmapResponse {
  institution_id: number;
  institution_name: string | null;
  plan: string | null;
  days_window: number;
  matrix: Record<string, Record<string, number>>;
  max_value: number;
  total: number;
  day_labels: string[];
  patterns: HeatmapPattern[];
}

// =============================================================================
// G3 — Güvenlik Kamarası: Oturumlar + Canlı + IP + Impersonation
// =============================================================================

export interface LiveFeedItem {
  type: string;
  ts: string | null;
  title: string;
  actor_id: number | null;
  ip: string | null;
  details: string;
  severity: string;
}

export interface LiveFeedResponse {
  since_seconds: number;
  items: LiveFeedItem[];
}

export interface SecurityActionResult {
  message: string;
  ok: boolean;
}

// =============================================================================
// G4 — Güvenlik Kamarası: Alarmlar + Suistimal
// =============================================================================

export interface AlarmRuleItem {
  id: number;
  key: string;
  name: string;
  description: string | null;
  threshold: number;
  cooldown_minutes: number;
  enabled: boolean;
  channels: string | null;
  last_triggered_at: string | null;
  last_value: number | null;
}

export interface AlarmEventItem {
  id: number;
  rule_key: string;
  rule_name: string;
  value: number;
  threshold: number;
  severity: string;
  delivery_status: string | null;
  triggered_at: string | null;
  acknowledged_at: string | null;
  age_seconds: number;
}

export interface AlarmsResponse {
  rules: AlarmRuleItem[];
  events: AlarmEventItem[];
  unack_count: number;
}

export interface AlarmRuleUpdateBody {
  threshold: number;
  cooldown_minutes: number;
  enabled: boolean;
  channels: string;
}

export interface AlarmScanResult {
  message: string;
  triggered: number;
  total_rules: number;
}

export interface AbuseSignalItem {
  id: number;
  kind: string;
  kind_label: string;
  severity: string;
  count: number;
  window_start: string | null;
  window_end: string | null;
  detected_at: string | null;
  last_seen_at: string | null;
  resolved_at: string | null;
  actor_user_id: number | null;
  actor_full_name: string | null;
  actor_email: string | null;
  tenant_id: number | null;
  tenant_name: string | null;
  details: Record<string, unknown>;
}

export interface AbuseMeta {
  kind_labels: Record<string, string>;
  kind_descriptions: Record<string, string>;
  severity_labels: Record<string, string>;
  severity_colors: Record<string, string>;
  action_button_labels: Record<string, string>;
}

export interface AbuseResponse {
  signals: AbuseSignalItem[];
  open_count: number;
  filter_only_open: boolean;
  filter_kind: string | null;
  meta: AbuseMeta;
}

export interface AbuseScanResult {
  message: string;
  summary: Record<string, number>;
  total: number;
}

export interface AbuseRemediateResult {
  message: string;
  ok: boolean;
  kind: string;
  action: string;
  affected_count: number;
  note: string;
}

// =============================================================================
// Süper Admin — Sistem ayarları (API anahtarları)
// =============================================================================

export interface AiSettingItem {
  name: string; // gemini_paid_api_key | gemini_free_api_key | *_model
  kind: string; // secret | config
  label: string;
  is_set: boolean;
  source: string; // db | env | none | default
  value: string; // secret → maskeli; config → düz
}

export interface AiSettingsResponse {
  items: AiSettingItem[];
}

export interface SetAiSettingBody {
  name: string;
  value: string;
}

// Üyelik/fiyat yapılandırması (tek kaynak override)
export interface SoloBandCfg {
  max_students: number;
  monthly: number;
}
export interface InstitutionTierCfg {
  code: string;
  label: string;
  min_coaches: number;
  max_coaches: number | null;
  per_coach_monthly: number;
  white_label: boolean;
  short: string;
}
export interface PricingConfig {
  annual_paid_months: number;
  solo_trial_days: number;
  solo_free_students: number;
  solo_bands: SoloBandCfg[];
  solo_over_cap_per_student: number;
  institution_trial_days: number;
  institution_free_teachers: number;
  institution_free_students: number;
  institution_students_per_coach: number;
  institution_tiers: InstitutionTierCfg[];
}
export interface PricingAdminResponse {
  config: PricingConfig;
  defaults: PricingConfig;
}
