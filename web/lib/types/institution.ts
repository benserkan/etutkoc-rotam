/**
 * Manuel TypeScript tipleri — `/api/v2/institution/*` için.
 *
 * Pydantic şemalarıyla (`app/routes/api_v2/schemas/institution.py`) birebir aynı.
 *
 * GİZLİLİK: kurum yöneticisi öğretmenin DETAY verisini (program, notlar, öğrenci
 * günlüğü) GÖREMEZ. Bu modüldeki tipler agrega + isim/sınıf düzeyinde bilgi
 * içerir; UI'da detay sayfasına link YOK.
 */

// =============================================================================
// Ortak — kurum kimliği
// =============================================================================

export interface InstitutionBrief {
  id: number;
  name: string;
  is_active: boolean;
}

// =============================================================================
// D4 Paket 1 — Dashboard + teachers + roster + goals
// =============================================================================

export interface TeacherSummaryItem {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  is_paused: boolean;
  pause_reason: string | null;
  paused_at: string | null;
  student_count: number;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
  last_login_at: string | null;
  last_login_days: number | null;
}

export interface InstitutionAggregateInfo {
  teacher_count: number;
  active_teacher_count: number;
  student_count: number;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
}

export interface InstitutionRiskBadge {
  at_risk_count: number;
  at_risk_critical: number;
}

export interface InstitutionInactiveBadge {
  inactive_teacher_count: number;
  inactive_teacher_names: string[];
}

export interface InstitutionDashboardResponse {
  institution: InstitutionBrief;
  aggregate: InstitutionAggregateInfo;
  risk: InstitutionRiskBadge;
  inactive: InstitutionInactiveBadge;
  teacher_summaries: TeacherSummaryItem[];
}

export interface InstitutionTeacherListResponse {
  institution: InstitutionBrief;
  items: TeacherSummaryItem[];
  total: number;
}

export interface TeacherCreateBody {
  full_name: string;
  email: string;
}

export interface TeacherCreateResult {
  id: number;
  full_name: string;
  email: string;
  temp_password: string;
  must_change_password: boolean;
}

export interface TeacherCardStudentRow {
  id: number;
  full_name: string;
  grade_level: number | null;
  display_grade_label: string | null;
  is_active: boolean;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
}

export interface TeacherCardResponse {
  teacher: TeacherSummaryItem;
  students: TeacherCardStudentRow[];
  total_planned: number;
  total_completed: number;
  overall_rate_pct: number | null;
}

export interface RosterRowItem {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  display_grade_label: string | null;
  teacher_id: number | null;
  teacher_name: string | null;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
  is_active: boolean;
  is_paused: boolean;
}

export interface RosterTeacherOption {
  id: number;
  full_name: string;
}

export interface RosterFilterOptions {
  teachers: RosterTeacherOption[];
  grades: number[];
  has_graduates: boolean;
}

export interface InstitutionRosterResponse {
  institution: InstitutionBrief;
  items: RosterRowItem[];
  total: number;
  filters: RosterFilterOptions;
}

export interface InstitutionGoalsResponse {
  students_with_goals: number;
  students_without_goals: number;
  total_goals: number;
  achieved_goals: number;
  active_goals: number;
  avg_overall_pct: number | null;
}

export interface RosterListParams {
  teacher_id?: number | null;
  grade?: number | null;
  is_graduate?: boolean | null;
}

// =============================================================================
// D4 Paket 2 — Davetiyeler
// =============================================================================

export type InvitationStatus = "pending" | "consumed" | "expired" | "revoked";

export interface InvitationItem {
  id: number;
  token: string;
  full_name: string | null;
  email: string | null;
  role: string;
  status: InvitationStatus;
  created_at: string;
  expires_at: string;
  consumed_at: string | null;
  consumed_by_user_id: number | null;
  revoked_at: string | null;
  is_usable: boolean;
  signup_url: string;
}

export interface InvitationListResponse {
  institution: InstitutionBrief;
  items: InvitationItem[];
  total: number;
  origin: string;
}

export interface InvitationCreateBody {
  full_name?: string | null;
  email?: string | null;
}

// =============================================================================
// D4 Paket 2 — Aktivite ısı haritası
// =============================================================================

export interface HeatmapCellData {
  day: string; // ISO date
  login_count: number;
  tasks_created: number;
  notes_created: number;
  activity_score: number; // 0..1
}

export interface TeacherHeatmapRow {
  teacher_id: number;
  full_name: string;
  cells: HeatmapCellData[];
  last_active_day: string | null;
  days_since_active: number | null;
  total_logins: number;
  total_tasks: number;
  total_notes: number;
  is_inactive: boolean;
  is_new: boolean;
}

export interface ActivityHeatmapResponse {
  institution: InstitutionBrief;
  weeks: number;
  days_count: number;
  inactive_threshold_days: number;
  inactive_count: number;
  teachers: TeacherHeatmapRow[];
}

// =============================================================================
// D4 Paket 2 — Risk listesi
// =============================================================================

export type RiskLevel = "ok" | "medium" | "high" | "critical";

export interface RiskIndicatorItem {
  code: string;
  title: string;
  detail: string;
  weight: number;
}

export interface AtRiskRowItem {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  display_grade_label: string | null;
  is_active: boolean;
  is_paused: boolean;
  pause_reason: string | null;
  teacher_id: number | null;
  teacher_name: string | null;
  score: number;
  level: RiskLevel;
  level_label: string;
  level_emoji: string;
  indicators: RiskIndicatorItem[];
  last_login_days: number | null;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
  is_muted: boolean;
}

export interface AtRiskCountsInfo {
  critical: number;
  high: number;
  medium: number;
}

export interface AtRiskResponse {
  institution: InstitutionBrief;
  counts: AtRiskCountsInfo;
  total_students: number;
  healthy_count: number;
  at_risk: AtRiskRowItem[];
}

// =============================================================================
// D4 Paket 2 — Burnout listesi
// =============================================================================

export type BurnoutLevel = "healthy" | "watch" | "warn" | "critical";

export interface BurnoutSignalItem {
  kind: string;
  severity: string;
  label: string;
  emoji: string;
  detail: string;
  metric: number | null;
}

export interface BurnoutRowItem {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  display_grade_label: string | null;
  teacher_id: number | null;
  teacher_name: string | null;
  risk_score: number;
  risk_level: BurnoutLevel;
  signal_count: number;
  signals: BurnoutSignalItem[];
}

export interface BurnoutResponse {
  institution: InstitutionBrief;
  items: BurnoutRowItem[];
  total: number;
}

// Koça ilet — riskli öğrenci için kurum yöneticisi → koç talebi (aşağı yönlü)
export interface NotifyCoachBody {
  teacher_id: number;
  student_name?: string | null;
  note?: string | null;
  context?: string | null; // "burnout" | "at_risk"
}

export interface NotifyCoachResult {
  request_id: number;
  teacher_id: number;
  teacher_name: string | null;
}

// =============================================================================
// D4 Paket 2 — Kohortlar
// =============================================================================

export type CohortTab = "grade" | "track" | "curriculum" | "exam_target";

export interface CohortStatsItem {
  cohort_key: string;
  cohort_label: string;
  student_count: number;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
  at_risk_count: number;
  at_risk_pct: number | null;
  rate_color: string; // "green" | "amber" | "red" | "slate"
}

export type WoWDirection = "up" | "down" | "flat" | "unknown";

export interface WeekOverWeekInfo {
  this_week_rate: number | null;
  last_week_rate: number | null;
  delta_pct: number | null;
  direction: WoWDirection;
}

export interface CohortTabInfo {
  key: CohortTab;
  label: string;
}

export interface CohortsResponse {
  institution: InstitutionBrief;
  active_tab: CohortTab;
  tabs: CohortTabInfo[];
  cohorts: CohortStatsItem[];
  wow: WeekOverWeekInfo;
}

// =============================================================================
// D4 Paket 3 — Admin Weekly Digest
// =============================================================================

export type AdminDigestStatus =
  | "sent"
  | "failed"
  | "log_only"
  | "pending"
  | "skipped_no_admin";

export interface AdminDigestSummary {
  id: number;
  institution_id: number;
  week_start_date: string; // ISO date
  week_end_date: string;
  send_status: AdminDigestStatus;
  recipient_count: number;
  sent_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface AdminDigestListResponse {
  institution: InstitutionBrief;
  items: AdminDigestSummary[];
  total: number;
}

/** Payload — `app/services/admin_digest.py:build_weekly_digest_payload` çıktısı. */
export interface AdminDigestPayloadTotals {
  student_count: number;
  teacher_count: number;
  inactive_teacher_count: number;
}

export interface AdminDigestPayloadCompletion {
  this_week_rate: number | null;
  last_week_rate: number | null;
  delta_pct: number | null;
  direction: WoWDirection;
}

export interface AdminDigestPayloadAtRisk {
  critical: number;
  high: number;
  medium: number;
  total: number;
}

export interface AdminDigestPayloadHighlight {
  best_grade_label: string | null;
  best_grade_rate: number | null;
  worst_grade_label: string | null;
  worst_grade_rate: number | null;
}

export interface AdminDigestInactiveTeacherEntry {
  id: number;
  name: string;
  email: string;
}

export interface AdminDigestCohortEntry {
  label: string;
  n: number;
  rate: number | null;
  color: string;
}

export interface AdminDigestPayload {
  institution_id: number;
  institution_name: string;
  week_start: string;
  week_end: string;
  totals: AdminDigestPayloadTotals;
  completion: AdminDigestPayloadCompletion;
  at_risk: AdminDigestPayloadAtRisk;
  highlight: AdminDigestPayloadHighlight;
  inactive_teachers: AdminDigestInactiveTeacherEntry[];
  grade_cohorts: AdminDigestCohortEntry[];
  track_cohorts: AdminDigestCohortEntry[];
}

export interface AdminDigestDetailResponse extends AdminDigestSummary {
  payload: AdminDigestPayload | null;
  recipient_emails: string[];
}

export interface AdminDigestSendResult {
  digest: AdminDigestSummary;
  message: string;
}

// =============================================================================
// D4 Paket 7 — Subscription
// =============================================================================

export type SubscriptionKind = "monthly" | "academic_year" | "paused";

export interface SubscriptionStatusInfo {
  kind: SubscriptionKind;
  kind_label: string;
  period_end: string | null;
  pause_until: string | null;
  in_summer_window: boolean;
  can_pause: boolean;
  can_resume: boolean;
  can_switch_to_academic_year: boolean;
  days_until_period_end: number | null;
  performance_guarantee: boolean;
  guarantee_extended_at: string | null;
}

export interface GuaranteeEvaluationInfo {
  eligible: boolean;
  period_started_at: string | null;
  days_into_period: number | null;
  period_total_days: number;
  average_completion_rate: number | null;
  threshold: number;
  triggered: boolean;
  already_extended: boolean;
  can_extend: boolean;
  note: string;
  student_count: number;
  total_planned_questions: number;
  total_completed_questions: number;
  is_provisional: boolean;
}

export interface InstitutionPlanOption {
  code: string;
  label: string;
  coaches: string;       // koç aralığı
  price_label: string;   // "10.000 ₺/ay" | "Özel teklif"
}

export interface SubscriptionResponse {
  institution: InstitutionBrief;
  plan: string;
  plan_label: string;
  status: SubscriptionStatusInfo;
  guarantee_evaluation: GuaranteeEvaluationInfo;
  available_plans: InstitutionPlanOption[];
  pending_upgrade_request: boolean;
  requested_plan_label: string | null;
}

export interface SubscriptionUpgradeRequestBody {
  plan?: string | null;
  note?: string | null;
}

export interface SubscriptionRequestResult {
  ok: boolean;
  message: string;
  already_pending: boolean;
}

// =============================================================================
// D4 Paket 7 — Quota
// =============================================================================

export interface QuotaInfoItem {
  key: string;
  label: string;
  limit: number; // -1 sınırsız, 0 kapalı
  current: number;
  pct: number;
  is_unlimited: boolean;
  is_at_limit: boolean;
  is_warn: boolean;
  has_override: boolean;
  override_note: string | null;
}

export interface PlanQuotaItem {
  plan: string;
  teachers: number;
  students: number;
  institution_admins: number;
}

export interface QuotaResponse {
  institution: InstitutionBrief;
  plan: string;
  summary: QuotaInfoItem[];
  plans: PlanQuotaItem[];
  warn_pct: number;
}

// =============================================================================
// D4 Paket 7 — Usage / Credits
// =============================================================================

export interface UsageAccountInfo {
  period_year_month: string;
  plan_code: string;
  allocated_credits: number;
  bonus_credits: number;
  total_allocated: number;
  used_credits: number;
  remaining_credits: number;
  usage_pct: number;
  hard_block_enabled: boolean;
  blocked_until: string | null;
}

export interface UsageBreakdownEntry {
  kind: string;
  label: string;
  credits: number;
}

export interface UsageDailyPoint {
  day: string; // ISO date
  credits: number;
}

export interface UsageEventItem {
  id: number;
  occurred_at: string;
  kind: string;
  kind_label: string;
  credits: number;
  actor_user_id: number | null;
}

export interface UsageResponse {
  institution: InstitutionBrief;
  account: UsageAccountInfo;
  breakdown: UsageBreakdownEntry[];
  series: UsageDailyPoint[];
  events: UsageEventItem[];
  warn_threshold_pct: number;
}

// ---------------------------- Program Uyum Panosu (2026-05-20) ----------------------------

export interface ComplianceSummary {
  rate: number | null;
  rate_color: string;
  last_week_rate: number | null;
  delta: number | null;
  planned: number;
  completed: number;
  accuracy: number | null;
  student_count: number;
  empty_count: number;
  week_start: string;
  week_end: string;
}

export interface ComplianceTrendPoint {
  week_start: string;
  rate: number | null;
  planned: number;
  completed: number;
}

export interface ComplianceTeacherRow {
  teacher_id: number | null;
  teacher_name: string;
  student_count: number;
  empty_students: number;
  planned: number;
  completed: number;
  rate: number | null;
  rate_color: string;
  accuracy: number | null;
}

export interface ComplianceStudentRow {
  student_name: string;
  teacher_name: string;
  planned: number;
  completed: number;
  rate: number | null;
  rate_color: string;
  accuracy: number | null;
}

export interface ComplianceEmptyRow {
  teacher_id: number | null;
  teacher_name: string;
  count: number;
  sample_students: string[];
}

export interface InstitutionComplianceResponse {
  institution: InstitutionBrief;
  summary: ComplianceSummary;
  trend: ComplianceTrendPoint[];
  teachers: ComplianceTeacherRow[];
  attention_students: ComplianceStudentRow[];
  empty_program: ComplianceEmptyRow[];
}

// ---------------------------- Müdahale Merkezi (KP1, 2026-05-20) ----------------------------

export interface ActionCenterItem {
  severity: string;
  category: string;
  title: string;
  description: string;
  teacher_name: string | null;
  count: number;
  suggestion: string;
}

export interface ActionCenterSummary {
  critical: number;
  warn: number;
  info: number;
  total: number;
}

export interface ActionCenterResponse {
  institution: InstitutionBrief;
  summary: ActionCenterSummary;
  items: ActionCenterItem[];
}

// ---------------------------- Öğretmen Etkililik Karnesi (KP2, 2026-05-20) ----------------------------

export interface TeacherScorecardRow {
  teacher_id: number | null;
  teacher_name: string;
  student_count: number;
  completion_rate: number | null;
  accuracy: number | null;
  discipline_per_student_week: number;
  discipline_pct: number;
  risk_students: number;
  score: number;
  score_color: string;
  score_label: string;
}

export interface TeacherScorecardSummary {
  teacher_count: number;
  avg_score: number;
  top_name: string | null;
  top_score: number | null;
  weeks: number;
}

export interface TeacherScorecardResponse {
  institution: InstitutionBrief;
  summary: TeacherScorecardSummary;
  teachers: TeacherScorecardRow[];
}

// ---------------------------- Veli Güveni Görünürlüğü (KP3, 2026-05-20) ----------------------------

export interface ParentTrustSummary {
  total_students: number;
  covered_students: number;
  coverage_pct: number | null;
  parent_count: number;
  active_parents: number;
  pending_invites: number;
  notif_sent: number;
  notif_failed: number;
  notif_suppressed: number;
  notif_success_pct: number | null;
  days: number;
}

export interface ParentTrustChannel {
  channel: string;
  channel_label: string;
  sent: number;
  failed: number;
  suppressed: number;
  success_pct: number | null;
}

export interface ParentTrustResponse {
  institution: InstitutionBrief;
  summary: ParentTrustSummary;
  channels: ParentTrustChannel[];
}

export interface ParentTrustNotificationItem {
  id: number;
  status: string;            // sent/failed/suppressed/queued
  status_label: string;
  kind: string;
  kind_label: string;
  channel: string;
  channel_label: string;
  subject: string | null;
  error: string | null;
  student_name: string | null;
  parent_email: string | null;
  parent_name: string | null;
  created_at: string;
  sent_at: string | null;
}

export interface ParentTrustNotificationListResponse {
  items: ParentTrustNotificationItem[];
  days: number;
  total_count: number;
}

// =============================================================================
// KP4b — Kurum Akademik Çıktı Panosu
// =============================================================================

export interface AcademicSummary {
  total_students: number;
  students_with_exam: number;
  coverage_pct: number | null;
  no_exam_count: number;
  total_exams: number;
  recent_exams: number;
  avg_net_pct: number | null;
  net_pct_color: string;
  delta: number | null;
  weeks: number;
}

export interface AcademicSectionRow {
  section: string;
  section_label: string;
  exam_count: number;
  student_count: number;
  avg_net: number;
  avg_net_pct: number | null;
  net_pct_color: string;
}

export interface AcademicTrendPoint {
  week_start: string;
  avg_net_pct: number | null;
  exam_count: number;
}

export interface AcademicTeacherRow {
  teacher_id: number | null;
  teacher_name: string;
  student_count: number;
  exam_count: number;
  avg_net_pct: number | null;
  net_pct_color: string;
  last_exam_date: string | null;
}

export interface AcademicMoverRow {
  student_name: string;
  teacher_name: string;
  first_net_pct: number;
  last_net_pct: number;
  delta: number;
  exam_count: number;
}

export interface AcademicNoExamRow {
  teacher_id: number | null;
  teacher_name: string;
  count: number;
  sample_students: string[];
}

export interface InstitutionAcademicResponse {
  institution: InstitutionBrief;
  summary: AcademicSummary;
  sections: AcademicSectionRow[];
  trend: AcademicTrendPoint[];
  teachers: AcademicTeacherRow[];
  improving: AcademicMoverRow[];
  declining: AcademicMoverRow[];
  no_exam_program: AcademicNoExamRow[];
}

export interface InstitutionBadgesResponse {
  support_inbox_pending: number;
  support_answered: number;
  checked_at: string;
}
