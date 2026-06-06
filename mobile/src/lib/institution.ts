import { apiRequest } from "./api";

export interface InstitutionBrief {
  id: number;
  name: string;
  is_active: boolean;
}
export interface InstitutionAggregate {
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
export interface TeacherSummaryItem {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  is_paused: boolean;
  pause_reason: string | null;
  paused_at?: string | null;
  student_count: number;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
  last_login_at?: string | null;
  last_login_days: number | null;
}
export interface InstitutionDashboardResponse {
  institution: InstitutionBrief;
  aggregate: InstitutionAggregate;
  risk: InstitutionRiskBadge;
  inactive: InstitutionInactiveBadge;
  teacher_summaries: TeacherSummaryItem[];
}

export interface ActionCenterItem {
  severity: string; // critical | warn | info
  category: string; // empty_program | low_compliance | at_risk
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

// ===== Koç detayı (öğretmen kartı) =====
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
export interface InstitutionTeacherListResponse {
  institution: InstitutionBrief;
  items: TeacherSummaryItem[];
  total: number;
}

// ===== Davetiyeler =====
export interface InvitationItem {
  id: number;
  token: string;
  full_name: string | null;
  email: string | null;
  role: string;
  status: string;
  created_at: string;
  expires_at: string | null;
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

// ===== Program uyumu =====
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
}
export interface ComplianceTeacherRow {
  teacher_id: number;
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
  teacher_name: string;
  empty_count: number;
  sample_student: string | null;
}
export interface InstitutionComplianceResponse {
  institution: InstitutionBrief;
  summary: ComplianceSummary;
  trend: ComplianceTrendPoint[];
  teachers: ComplianceTeacherRow[];
  attention_students: ComplianceStudentRow[];
  empty_program: ComplianceEmptyRow[];
}

// ===== Akademik çıktı =====
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
  section_label?: string;
  exam_count: number;
  student_count: number;
  avg_net: number | null;
  avg_net_pct: number | null;
  net_pct_color: string;
}
export interface AcademicTrendPoint {
  week_start: string;
  avg_net_pct: number | null;
}
export interface AcademicTeacherRow {
  teacher_id: number;
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
  first_net_pct: number | null;
  last_net_pct: number | null;
  delta: number | null;
  exam_count: number;
}
export interface AcademicNoExamRow {
  teacher_name: string;
  no_exam_count: number;
  sample_student: string | null;
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

// ===== Risk paneli =====
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
  level: string;
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

// ===== Kohort =====
export interface CohortTabInfo {
  key: string;
  label: string;
}
export interface CohortStatsItem {
  cohort_key: string;
  cohort_label: string;
  student_count: number;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
  at_risk_count: number;
  at_risk_pct: number | null;
  rate_color: string;
}
export interface WeekOverWeekInfo {
  this_week_rate: number | null;
  last_week_rate: number | null;
  delta_pct: number | null;
  direction: string;
}
export interface CohortsResponse {
  institution: InstitutionBrief;
  active_tab: string;
  tabs: CohortTabInfo[];
  cohorts: CohortStatsItem[];
  wow: WeekOverWeekInfo;
}

// ===== Aktivite haritası =====
export interface HeatmapCellData {
  day: string;
  login_count: number;
  tasks_created: number;
  notes_created: number;
  activity_score: number;
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

// ===== Tükenmişlik =====
export interface BurnoutSignalItem {
  kind: string;
  severity: string;
  label: string;
  emoji: string;
  detail: string;
  metric?: string | null;
}
export interface BurnoutRowItem {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  display_grade_label: string | null;
  teacher_id: number | null;
  teacher_name: string | null;
  risk_score: number;
  risk_level: string;
  signal_count: number;
  signals: BurnoutSignalItem[];
}
export interface BurnoutResponse {
  institution: InstitutionBrief;
  items: BurnoutRowItem[];
  total: number;
}

// ===== Öğretmen karnesi =====
export interface TeacherScorecardSummary {
  teacher_count: number;
  avg_score: number | null;
  top_name: string | null;
  top_score: number | null;
  weeks: number;
}
export interface TeacherScorecardRow {
  teacher_id: number;
  teacher_name: string;
  student_count: number;
  completion_rate: number | null;
  accuracy: number | null;
  discipline_per_student_week: number | null;
  discipline_pct: number | null;
  risk_students: number;
  score: number | null;
  score_color: string;
  score_label: string;
}
export interface TeacherScorecardResponse {
  institution: InstitutionBrief;
  summary: TeacherScorecardSummary;
  teachers: TeacherScorecardRow[];
}

// ===== Hedef analizi =====
export interface InstitutionGoalsResponse {
  students_with_goals: number;
  students_without_goals: number;
  total_goals: number;
  achieved_goals: number;
  active_goals: number;
  avg_overall_pct: number | null;
}

// ===== Haftalık özet (admin digest) =====
export interface AdminDigestSummary {
  id: number;
  institution_id: number;
  week_start_date: string;
  week_end_date: string;
  send_status: string;
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
export interface AdminDigestCohortEntry {
  label: string;
  n: number;
  rate: number | null;
  color: string;
}
export interface AdminDigestPayload {
  institution_name?: string;
  totals: { student_count: number; teacher_count: number; inactive_teacher_count: number };
  completion: { this_week_rate: number | null; last_week_rate: number | null; delta_pct: number | null; direction: string };
  at_risk: { critical: number; high: number; medium: number; total: number };
  highlight: { best_grade_label: string | null; best_grade_rate: number | null; worst_grade_label: string | null; worst_grade_rate: number | null };
  inactive_teachers: { id: number; name: string; email: string }[];
  grade_cohorts: AdminDigestCohortEntry[];
}
export interface AdminDigestDetailResponse extends AdminDigestSummary {
  payload: AdminDigestPayload | null;
  recipient_emails: string[];
}

// ===== Veli güveni =====
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

// ===== Kredi kullanımı =====
export interface UsageAccountInfo {
  period_year_month: string;
  plan_code: string;
  allocated_credits: number;
  bonus_credits: number;
  total_allocated: number;
  used_credits: number;
  remaining_credits: number;
  usage_pct: number | null;
  hard_block_enabled: boolean;
  blocked_until: string | null;
  first_event_at: string | null;
  last_event_at: string | null;
  total_event_count: number;
}
export interface UsageBreakdownEntry {
  kind: string;
  kind_label: string;
  credits: number;
  event_count: number;
}
export interface UsageDailyPoint {
  day: string;
  credits: number;
}
export interface UsageEventItem {
  id: number;
  occurred_at: string;
  kind: string;
  kind_label: string;
  credits: number;
  actor_user_id: number | null;
  actor_name: string | null;
  balance_after: number | null;
}
export interface UsageResponse {
  institution: InstitutionBrief;
  account: UsageAccountInfo;
  breakdown: UsageBreakdownEntry[];
  series: UsageDailyPoint[];
  events: UsageEventItem[];
  warn_threshold_pct: number;
}

// ===== Limitler (kota) =====
export interface QuotaInfoItem {
  key: string;
  label: string;
  limit: number;
  current: number;
  pct: number | null;
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

// ===== Üyelik / hesap ayarları =====
export interface SubscriptionStatusInfo {
  kind: string;
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
export interface InstitutionPlanOption {
  code: string;
  label: string;
  description?: string | null;
  coach_range?: string | null;
}
export interface SubscriptionResponse {
  institution: InstitutionBrief;
  plan: string;
  plan_label: string;
  status: SubscriptionStatusInfo;
  available_plans: InstitutionPlanOption[];
  pending_upgrade_request: boolean;
  requested_plan_label: string | null;
}

// ===== Aktivite akışı =====
export interface ActivityStreamItem {
  id: string;
  occurred_at: string;
  type: string;
  category: string;
  is_commercial: boolean;
  title: string;
  subtitle: string | null;
  actor_name: string | null;
  actor_email: string | null;
  actor_role: string | null;
  target_label: string | null;
  detail_url: string | null;
  institution_id: number | null;
  institution_name: string | null;
}
export interface ActivityStreamResponse {
  items: ActivityStreamItem[];
  counts: Record<string, number>;
  days: number;
}

export const institutionKeys = {
  dashboard: ["institution", "dashboard"] as const,
  actionCenter: ["institution", "action-center"] as const,
  teachers: ["institution", "teachers"] as const,
  teacherCard: (id: number) => ["institution", "teacher-card", id] as const,
  invitations: ["institution", "invitations"] as const,
  compliance: ["institution", "compliance"] as const,
  academic: ["institution", "academic"] as const,
  atRisk: ["institution", "at-risk"] as const,
  cohorts: (tab: string) => ["institution", "cohorts", tab] as const,
  heatmap: (weeks: number) => ["institution", "heatmap", weeks] as const,
  burnout: ["institution", "burnout"] as const,
  scorecard: ["institution", "scorecard"] as const,
  goals: ["institution", "goals"] as const,
  digestList: ["institution", "digest-list"] as const,
  digest: (id: number) => ["institution", "digest", id] as const,
  parentTrust: ["institution", "parent-trust"] as const,
  usage: ["institution", "usage"] as const,
  quota: ["institution", "quota"] as const,
  subscription: ["institution", "subscription"] as const,
  activityStream: (days: number) => ["institution", "activity-stream", days] as const,
};

export function getInstitutionDashboard(): Promise<InstitutionDashboardResponse> {
  return apiRequest<InstitutionDashboardResponse>(`/api/v2/institution/dashboard`);
}
export function getInstitutionActionCenter(): Promise<ActionCenterResponse> {
  return apiRequest<ActionCenterResponse>(`/api/v2/institution/action-center`);
}
export function getInstitutionTeachers(): Promise<InstitutionTeacherListResponse> {
  return apiRequest<InstitutionTeacherListResponse>(`/api/v2/institution/teachers`);
}
export function getInstitutionTeacherCard(id: number): Promise<TeacherCardResponse> {
  return apiRequest<TeacherCardResponse>(`/api/v2/institution/teachers/${id}`);
}
export function getInstitutionInvitations(): Promise<InvitationListResponse> {
  return apiRequest<InvitationListResponse>(`/api/v2/institution/invitations`);
}
export function createInstitutionInvitation(body: {
  full_name?: string;
  email?: string;
}): Promise<{ data: InvitationItem }> {
  return apiRequest(`/api/v2/institution/invitations`, { method: "POST", body });
}
export function revokeInstitutionInvitation(id: number): Promise<unknown> {
  return apiRequest(`/api/v2/institution/invitations/${id}/revoke`, { method: "POST" });
}
export function getInstitutionCompliance(weeks = 8): Promise<InstitutionComplianceResponse> {
  return apiRequest<InstitutionComplianceResponse>(`/api/v2/institution/compliance?weeks=${weeks}`);
}
export function getInstitutionAcademic(weeks = 8): Promise<InstitutionAcademicResponse> {
  return apiRequest<InstitutionAcademicResponse>(`/api/v2/institution/academic?weeks=${weeks}`);
}
export function getInstitutionAtRisk(): Promise<AtRiskResponse> {
  return apiRequest<AtRiskResponse>(`/api/v2/institution/at-risk`);
}
export function getInstitutionCohorts(tab = "grade"): Promise<CohortsResponse> {
  return apiRequest<CohortsResponse>(`/api/v2/institution/cohorts?tab=${tab}`);
}
export function getInstitutionHeatmap(weeks = 4): Promise<ActivityHeatmapResponse> {
  return apiRequest<ActivityHeatmapResponse>(`/api/v2/institution/activity-heatmap?weeks=${weeks}`);
}
export function getInstitutionBurnout(): Promise<BurnoutResponse> {
  return apiRequest<BurnoutResponse>(`/api/v2/institution/burnout`);
}

// P4b — geçmiş "Koça ilet" müdahaleleri (ad-bazlı eşleşme)
export interface CoachInterventionItem {
  request_id: number;
  student_name: string | null;
  coach_name: string | null;
  created_at: string;
  status: string;
  status_label: string;
}
export interface CoachInterventionsResponse {
  items: CoachInterventionItem[];
}
export function getInstitutionCoachInterventions(): Promise<CoachInterventionsResponse> {
  return apiRequest<CoachInterventionsResponse>(`/api/v2/institution/coach-interventions?days=90`);
}
export function buildInterventionMap(items: CoachInterventionItem[]): Map<string, CoachInterventionItem> {
  const m = new Map<string, CoachInterventionItem>();
  for (const it of items) {
    if (!it.student_name) continue;
    const key = it.student_name.trim().toLocaleLowerCase("tr");
    if (!m.has(key)) m.set(key, it);
  }
  return m;
}
export function getInstitutionScorecard(weeks = 4): Promise<TeacherScorecardResponse> {
  return apiRequest<TeacherScorecardResponse>(`/api/v2/institution/teacher-scorecard?weeks=${weeks}`);
}
export function getInstitutionGoals(): Promise<InstitutionGoalsResponse> {
  return apiRequest<InstitutionGoalsResponse>(`/api/v2/institution/goals`);
}
export function getInstitutionDigestList(): Promise<AdminDigestListResponse> {
  return apiRequest<AdminDigestListResponse>(`/api/v2/institution/admin-digest`);
}
export function getInstitutionDigest(id: number): Promise<AdminDigestDetailResponse> {
  return apiRequest<AdminDigestDetailResponse>(`/api/v2/institution/admin-digest/${id}`);
}
export function sendInstitutionDigestNow(): Promise<unknown> {
  return apiRequest(`/api/v2/institution/admin-digest/send-now`, { method: "POST", body: { force: true } });
}
export function getInstitutionParentTrust(days = 30): Promise<ParentTrustResponse> {
  return apiRequest<ParentTrustResponse>(`/api/v2/institution/parent-trust?days=${days}`);
}
export function getInstitutionUsage(days = 30): Promise<UsageResponse> {
  return apiRequest<UsageResponse>(`/api/v2/institution/usage?days=${days}`);
}
export function getInstitutionQuota(): Promise<QuotaResponse> {
  return apiRequest<QuotaResponse>(`/api/v2/institution/quota`);
}
export function getInstitutionSubscription(): Promise<SubscriptionResponse> {
  return apiRequest<SubscriptionResponse>(`/api/v2/institution/subscription`);
}
export function getInstitutionActivityStream(days = 30): Promise<ActivityStreamResponse> {
  return apiRequest<ActivityStreamResponse>(`/api/v2/institution/activity-stream?days=${days}&limit=200`);
}
export interface SubscriptionRequestResult {
  ok: boolean;
  message: string;
  already_pending: boolean;
}
export function requestInstitutionUpgrade(body: { plan?: string; note?: string }): Promise<{ data: SubscriptionRequestResult }> {
  return apiRequest(`/api/v2/institution/subscription-request`, { method: "POST", body });
}
// Abonelik aksiyonları (P4e) — akademik yıl / yaz duraklat-devam / garanti
export function switchInstitutionAcademicYear(): Promise<unknown> {
  return apiRequest(`/api/v2/institution/subscription/switch-academic-year`, { method: "POST" });
}
export function pauseInstitutionForSummer(): Promise<unknown> {
  return apiRequest(`/api/v2/institution/subscription/pause`, { method: "POST" });
}
export function resumeInstitutionFromPause(): Promise<unknown> {
  return apiRequest(`/api/v2/institution/subscription/resume`, { method: "POST" });
}
export function enableInstitutionGuarantee(): Promise<unknown> {
  return apiRequest(`/api/v2/institution/subscription/guarantee/enable`, { method: "POST" });
}
export function notifyCoach(body: {
  teacher_id: number;
  student_name?: string;
  note?: string;
  context?: string;
}): Promise<unknown> {
  return apiRequest(`/api/v2/institution/notify-coach`, { method: "POST", body });
}
