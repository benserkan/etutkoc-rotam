/**
 * Manuel TypeScript tipleri — `/api/v2/teacher/*` için.
 *
 * Pydantic şemalarıyla (`app/routes/api_v2/schemas/teacher.py`) birebir aynı.
 *
 * Bu modül SADECE okuma + mutation body/result tiplerini içerir — hook
 * imzalarında kullanılır. Mutation hook'ları Paket 7'de eklenir.
 */
import type { TaskStatus, TaskType, BookType } from "@/lib/types/student";

export type { TaskStatus, TaskType, BookType };

// =============================================================================
// Ortak literal'lar
// =============================================================================

export type WarningLevel = "green" | "amber" | "red";
export type RiskLevel = "ok" | "medium" | "high" | "critical";
export type RequestType = "change" | "replace" | "remove" | "question" | "add";
export type RequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "withdrawn"
  | "resolved";
export type Track = "sayisal" | "ea" | "sozel" | "dil";
export type GraduateMode = "full_time" | "dershane";
export type ParentRelation = "anne" | "baba" | "vasi" | "diger";

// =============================================================================
// TR etiketler — UI'da enum.value göstermek yerine
// =============================================================================

export const WARNING_LABELS_TR: Record<WarningLevel, string> = {
  green: "Yolunda",
  amber: "Uyarı",
  red: "Kritik",
};

export const RISK_LABELS_TR: Record<RiskLevel, string> = {
  ok: "İyi",
  medium: "Orta",
  high: "Yüksek",
  critical: "Kritik",
};

export const REQUEST_TYPE_LABELS_TR: Record<RequestType, string> = {
  change: "Sayı değiştir",
  replace: "Kaynağı değiştir",
  remove: "Çıkar",
  question: "Soru",
  add: "Ekle",
};

export const REQUEST_STATUS_LABELS_TR: Record<RequestStatus, string> = {
  pending: "Bekliyor",
  approved: "Onaylandı",
  rejected: "Reddedildi",
  withdrawn: "Geri çekildi",
  resolved: "Cevaplandı",
};

export const TRACK_LABELS_TR: Record<Track, string> = {
  sayisal: "Sayısal",
  ea: "Eşit Ağırlık",
  sozel: "Sözel",
  dil: "Dil",
};

export const GRADUATE_MODE_LABELS_TR: Record<GraduateMode, string> = {
  full_time: "Tam zamanlı",
  dershane: "Dershane",
};

export const PARENT_RELATION_LABELS_TR: Record<ParentRelation, string> = {
  anne: "Anne",
  baba: "Baba",
  vasi: "Vasi",
  diger: "Diğer",
};

// =============================================================================
// Dashboard
// =============================================================================

export interface RiskRow {
  student_id: number;
  full_name: string;
  level: RiskLevel;
  reasons: string[];
}

export interface DashboardRequest {
  id: number;
  student_id: number;
  student_name: string;
  type: RequestType;
  task_id: number | null;
  task_title: string | null;
  created_at: string;
}

export interface TeacherDashboardResponse {
  student_count: number;
  active_student_count: number;
  at_risk_count: number;
  at_risk_critical: number;

  pending_requests_count: number;

  today_planned: number;
  today_completed: number;
  week_planned: number;
  week_completed: number;
  week_completion_rate: number;

  fleet_red: number;
  fleet_amber: number;
  fleet_green: number;

  top_5_at_risk: RiskRow[];
  recent_requests: DashboardRequest[];
}

// =============================================================================
// Öğrenci listesi + detay
// =============================================================================

export interface TeacherStudentListItem {
  id: number;
  full_name: string;
  email: string;
  grade_level: number | null;
  is_active: boolean;
  last_login_at: string | null;
  worst_warning_level: WarningLevel;
  today_planned: number;
  today_completed: number;
  week_pct: number;
  has_pending_request: boolean;
}

export interface TeacherStudentListResponse {
  items: TeacherStudentListItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface StudentBriefProfile {
  id: number;
  full_name: string;
  email: string;
  grade_level: number | null;
  is_active: boolean;
  is_graduate: boolean;
  institution_id: number | null;
  teacher_id: number | null;
  last_login_at: string | null;
  created_at: string | null;
  // Paket 3.5b — header rozetleri için (Jinja student_detail.html:5-75 parite)
  display_grade_label?: string | null;
  track?: Track | null;
  track_label?: string | null;
  track_required?: boolean;
  track_missing?: boolean;
  curriculum_model?: "lgs" | "klasik_lise" | "maarif_lise" | null;
  curriculum_label?: string | null;
  exam_target?: string | null;
  exam_label?: string | null;
  exam_date?: string | null;
  graduate_mode?: GraduateMode | null;
  academic_year_name?: string | null;
}

export interface StudentProgramSummary {
  today_planned: number;
  today_completed: number;
  today_pct: number;
  week_planned: number;
  week_completed: number;
  week_pct: number;
  consistency_7d: number;
  hit_rate_7d: number;
  rate_7d?: number;
}

export interface StudentActivePhase {
  kind: "regular" | "winter_break" | "summer_camp" | "exam_prep" | string;
  kind_label: string;
  kind_badge: string;
  name: string;
  start_date: string;
  end_date: string;
}

export interface TeacherStudentDetailResponse {
  student: StudentBriefProfile;
  program_summary: StudentProgramSummary;
  worst_warning_level: WarningLevel;
  warnings: string[];
  pending_request_count: number;
  // Paket 3.5b
  active_phase?: StudentActivePhase | null;
  week_anchor?: string | null;
  anchor_is_manual?: boolean;
}

export interface SetWeekAnchorBody {
  // "clear" → manuel anchor sıfırla; YYYY-MM-DD → set
  anchor: string;
}

export interface SetWeekAnchorResult {
  anchor: string | null;
  is_manual: boolean;
}

// =============================================================================
// Polling + me
// =============================================================================

export interface TeacherBadgesResponse {
  pending_request_count: number;
  at_risk_count: number;
  checked_at: string;
}

export interface TeacherMeResponse {
  id: number;
  full_name: string;
  email: string;
  institution_id: number | null;
  plan: string | null;
  student_count: number;
  active_student_count: number;
}

// =============================================================================
// Görev (öğretmen perspektifi)
// =============================================================================

export interface TeacherTaskItem {
  id: number;
  book_id: number;
  book_name: string;
  subject_id: number | null;
  subject_name: string | null;
  section_id: number;
  section_label: string | null;
  topic_name: string | null;
  planned_count: number;
  completed_count: number;
  section_total_tests: number;
  section_reserved_count: number;
  section_completed_count: number;
  section_remaining: number;
}

export interface TaskSingleItemEditBody {
  date: string;
  scheduled_hour: number | null;
  type: TaskType;
  book_id: number;
  section_id: number;
  planned_count: number;
  notes?: string | null;
  link_url?: string | null;
}

export interface TeacherTask {
  id: number;
  student_id: number;
  date: string;
  type: TaskType;
  status: TaskStatus;
  title: string;
  scheduled_hour: string | null;
  order: number;
  is_draft: boolean;
  notes: string | null;
  items: TeacherTaskItem[];
  planned_count: number;
  completed_count: number;
  pct: number;
  has_pending_request: boolean;
}

export interface TeacherWeekNote {
  id: number;
  body: string;
  order: number;
  is_done: boolean;
}

export interface TeacherStudentDayResponse {
  student_id: number;
  date: string;
  is_today: boolean;
  is_future: boolean;
  is_past: boolean;
  prev_date: string;
  next_date: string;
  tasks: TeacherTask[];
  today_planned: number;
  today_completed: number;
  today_pct: number;
}

export interface TeacherDaySubjectSummary {
  subject_id: number;
  subject_name: string;
  task_count: number;
  tests: number;
  denemeler: number;
}

export interface TeacherSuggestionInline {
  book_id: number;
  book_name: string;
  book_type: string;
  section_id: number;
  section_label: string;
  subject_id: number;
  subject_name: string;
  topic_name: string | null;
  planned_count: number;
  remaining: number;
  confidence: number;
  confidence_label: string;
  score: number;
  reasons: string[];
}

export interface TeacherActivePhase {
  kind: string;
  kind_label: string;
  kind_badge: string;
  capacity_multiplier: number;
  is_no_school: boolean;
}

export interface TeacherStudentWeekDay {
  date: string;
  dow_label: string;
  is_today: boolean;
  is_future: boolean;
  is_past: boolean;
  tasks_count: number;
  planned: number;
  completed: number;
  pct: number;
  tasks: TeacherTask[];
  // Paket 3.5a parity (server defaults exist for backward compat)
  draft_count?: number;
  subject_summary?: TeacherDaySubjectSummary[];
  suggestions?: TeacherSuggestionInline[];
}

export interface TeacherStudentWeekResponse {
  student_id: number;
  start_date: string;
  end_date: string;
  prev_start: string;
  next_start: string;
  week_start_anchor: string;
  days: TeacherStudentWeekDay[];
  total_planned: number;
  total_completed: number;
  total_pct: number;
  notes: TeacherWeekNote[];
  // Paket 3.5a parity
  week_anchor?: string | null;
  anchor_is_manual?: boolean;
  week_draft_total?: number;
  maturity_value?: number;
  maturity_label?: string;
  weeks_observed?: number;
  days_observed?: number;
  active_phase?: TeacherActivePhase | null;
  track_required?: boolean;
  track_missing?: boolean;
  track_label?: string | null;
}

// =============================================================================
// Paket 3.5a — Mutation body'leri + ek response tipleri
// =============================================================================

export interface WeekNoteAddBody {
  week_start: string;
  body: string;
}

export interface WeekNoteToggleResult {
  id: number;
  is_done: boolean;
}

export interface PublishDayBody {
  task_date: string;
}

export interface PublishWeekBody {
  week_start: string;
}

export interface PublishResult {
  published_count: number;
  week_draft_total: number;
}

export interface TasksReorderBody {
  task_date: string;
  task_ids: number[];
}

export interface TasksReorderResult {
  reordered_count: number;
}

export interface NotifyParentsBody {
  week_start: string;
}

export interface NotifyParentsResult {
  fired: number;
  skipped_recent: number;
  no_tasks: boolean;
  message: string;
}

// Sidebar — 3 seviyeli

export interface SidebarSection {
  id: number;
  label: string;
  topic_name: string | null;
  total: number;
  completed: number;
  reserved: number;
  remaining: number;
}

export interface SidebarBook {
  id: number;
  name: string;
  type: string;
  total: number;
  completed: number;
  reserved: number;
  remaining: number;
  sections: SidebarSection[];
}

export interface SidebarSubjectSummary {
  total: number;
  completed: number;
  reserved: number;
  remaining: number;
  books_count: number;
}

export interface SidebarSubject {
  id: number;
  name: string;
  summary: SidebarSubjectSummary;
  books: SidebarBook[];
}

export interface SidebarResponse {
  subjects: SidebarSubject[];
  focused_subject_id: number | null;
  grand_total: number;
  grand_completed: number;
  grand_reserved: number;
  grand_remaining: number;
}

// Cascade form

export interface BookOption {
  id: number;
  name: string;
}

export interface BookOptionsResponse {
  items: BookOption[];
  subject_id: number | null;
}

export interface SectionOption {
  id: number;
  label: string;
  topic_name: string | null;
  remaining: number;
  total: number;
}

export interface SectionOptionsResponse {
  items: SectionOption[];
  is_deneme: boolean;
}

export interface SectionStatsResponse {
  section_id: number;
  section_label: string;
  book_name: string;
  topic_name: string | null;
  total: number;
  completed: number;
  reserved: number;
  remaining: number;
}

export interface ReviewStruggleChip {
  card_id: number;
  topic_name: string;
  state: string;
  lapse_count: number;
  score: number;
  reasons: string[];
}

export interface ReviewStruggleResponse {
  items: ReviewStruggleChip[];
  target_date: string;
  subject_id: number;
}

// =============================================================================
// Mutation body'leri — Paket 7'de kullanılacak (şimdilik referans)
// =============================================================================

export interface TaskItemBody {
  book_id: number;
  section_id: number;
  planned_count: number;
}

export interface TaskCreateBody {
  date: string;
  type?: TaskType;
  title: string;
  scheduled_hour?: number | null;
  // null/undefined: backend smart varsayılan (gelecek tarihler taslak).
  // true/false: açık değer.
  is_draft?: boolean | null;
  notes?: string | null;
  items: TaskItemBody[];
}

export interface TaskPatchBody {
  title?: string | null;
  type?: TaskType | null;
  scheduled_hour?: number | null;
  order?: number | null;
  is_draft?: boolean | null;
  notes?: string | null;
}

export interface TaskItemPatchBody {
  planned_count: number;
}

export interface BulkTaskItem {
  date: string;
  type?: TaskType;
  title: string;
  scheduled_hour?: number | null;
  is_draft?: boolean;
  notes?: string | null;
  items: TaskItemBody[];
}

export interface BulkTasksBody {
  tasks: BulkTaskItem[];
}

export interface BulkResult {
  created_count: number;
  task_ids: number[];
}

// =============================================================================
// Talepler (öğretmen perspektifi)
// =============================================================================

export interface TeacherRequestListItem {
  id: number;
  student_id: number;
  student_name: string;
  type: RequestType;
  status: RequestStatus;
  task_id: number | null;
  task_title: string | null;
  task_date: string | null;
  message: string | null;
  proposed_count: number | null;
  proposed_date: string | null;
  teacher_response: string | null;
  created_at: string;
  responded_at: string | null;
}

export interface TeacherRequestListResponse {
  items: TeacherRequestListItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  pending_count: number;
}

export interface TeacherRequestDetail {
  id: number;
  student_id: number;
  student_name: string;
  student_email: string;
  type: RequestType;
  status: RequestStatus;
  task_id: number | null;
  task_title: string | null;
  task_date: string | null;
  message: string | null;
  teacher_response: string | null;
  proposed_book_id: number | null;
  proposed_book_name: string | null;
  proposed_section_id: number | null;
  proposed_section_label: string | null;
  proposed_count: number | null;
  proposed_date: string | null;
  current_items: TeacherTaskItem[];
  created_at: string;
  updated_at: string;
  responded_at: string | null;
}

export interface RequestApproveBody {
  response?: string | null;
}

export interface RequestRejectBody {
  reason: string;
}

export interface RequestRespondBody {
  response: string;
}

// =============================================================================
// Students CRUD (Paket 4 backend) — body/result tipleri
// =============================================================================

export interface StudentCreateBody {
  full_name: string;
  email: string;
  grade_level?: number | null;
  is_graduate?: boolean;
  track?: Track | null;
  graduate_mode?: GraduateMode | null;
  academic_year_id?: number | null;
}

export interface StudentPatchBody {
  full_name?: string | null;
  grade_level?: number | null;
  is_graduate?: boolean | null;
  track?: Track | null;
  graduate_mode?: GraduateMode | null;
  academic_year_id?: number | null;
}

export interface StudentCreateResult {
  id: number;
  full_name: string;
  email: string;
  grade_level: number | null;
  is_graduate: boolean;
  is_active: boolean;
  temp_password: string;
}

export interface StudentBookSectionProgressRow {
  section_id: number;
  label: string;
  order: number;
  topic_id: number | null;
  topic_name: string | null;
  test_count: number;
  completed_count: number;
  reserved_count: number;
}

export interface StudentBookListItem {
  student_book_id: number;
  book_id: number;
  book_name: string;
  book_type: BookType;
  book_type_label_tr: string;
  publisher: string | null;
  subject_id: number;
  subject_name: string;
  section_count: number;
  section_total_tests: number;
  section_reserved_total: number;
  section_completed_total: number;
  has_reservations: boolean;
  sections: StudentBookSectionProgressRow[];
}

export interface StudentBookListResponse {
  items: StudentBookListItem[];
  total: number;
}

export interface StudentBookAssignBody {
  book_id: number;
}

export interface StudentBookBulkAssignBody {
  book_ids: number[];
}

export interface StudentBookBulkAssignResult {
  assigned: StudentBookListItem[];
  assigned_count: number;
  skipped_already_ids: number[];
  skipped_invalid_ids: number[];
}

export interface ParentLinkItem {
  link_id: number;
  parent_id: number;
  parent_email: string;
  parent_full_name: string;
  relation: ParentRelation;
  is_primary: boolean;
  muted: boolean;
  created_at: string;
}

export interface PendingParentInvitation {
  invitation_id: number;
  invited_email: string;
  relation: ParentRelation;
  is_primary: boolean;
  expires_at: string;
  created_at: string;
}

export interface StudentParentsResponse {
  links: ParentLinkItem[];
  pending_invitations: PendingParentInvitation[];
}

export interface ParentInviteBody {
  parent_email: string;
  relation?: ParentRelation;
  is_primary?: boolean;
}

export interface ParentInviteResult {
  invitation_id: number;
  invited_email: string;
  expires_at: string;
}

// =============================================================================
// Öğretmenin kendi kitapları (atama UI için listeleme)
// =============================================================================

export interface TeacherBookListItem {
  id: number;
  name: string;
  type: string;
  subject_id: number;
  subject_name: string | null;
  section_count: number;
}

export interface TeacherBookListResponse {
  items: TeacherBookListItem[];
  total: number;
}

// =============================================================================
// Paket 3.5c — Sınıf Yükselt / Hedefler / Tekrar / DNA / Odak
// =============================================================================

// --- Promote ---

export type GradeChoice =
  | "5" | "6" | "7" | "8" | "9" | "10" | "11" | "12" | "graduate";

export interface PromoteYearOption {
  id: number;
  name: string;
  start_year: number | null;
}

export interface PromoteChoice {
  value: string;
  label: string;
}

export interface PromoteFormResponse {
  student_id: number;
  student_name: string;
  current_grade_label: string;
  current_track: Track | null;
  current_track_label: string | null;
  current_curriculum_model: string | null;
  current_curriculum_label: string | null;
  current_exam_label: string;
  current_graduate_mode: GraduateMode | null;
  current_academic_year_name: string | null;
  entry_year_grade9: number | null;
  is_graduate: boolean;
  years: PromoteYearOption[];
  suggested_year_id: number | null;
  suggested_grade: string;
  grade_choices: PromoteChoice[];
  track_choices: PromoteChoice[];
  graduate_mode_choices: PromoteChoice[];
  maarif_first_grade9_year: number;
}

export interface PromoteBody {
  grade: GradeChoice;
  academic_year_id?: number | null;
  track?: Track | null;
  graduate_mode?: GraduateMode | null;
  entry_year_grade9?: number | null;
}

export interface PromoteResult {
  student_id: number;
  new_grade_label: string;
  new_curriculum_label: string;
  new_track_label: string | null;
  new_graduate_mode_label: string | null;
  new_academic_year_name: string | null;
  message: string;
}

// --- Focus (Odak) ---

export type FocusKind = "work" | "short_break" | "long_break";

export interface FocusSessionRow {
  id: number;
  kind: FocusKind;
  started_at: string;
  ended_at: string | null;
  planned_minutes: number;
  actual_minutes: number;
  interrupted: boolean;
  label: string | null;
}

export interface FocusBadge {
  kind: string;
  title: string;
  emoji: string;
  description: string;
  earned_at: string;
}

export interface TeacherFocusResponse {
  student_id: number;
  student_name: string;
  today_work_sessions: number;
  today_work_minutes: number;
  today_break_minutes: number;
  today_interrupted_count: number;
  streak_days: number;
  longest_streak: number;
  points_total: number;
  work_minutes_30d: number;
  badges: FocusBadge[];
  recent_sessions: FocusSessionRow[];
}

// --- DNA + Burnout ---

export type DnaChronotype = "morning" | "afternoon" | "evening" | "night" | "unknown";
export type DnaTrendDirection = "up" | "down" | "flat" | "insufficient";
export type BurnoutRiskLevel = "healthy" | "watch" | "warn" | "critical";
export type BurnoutSeverity = "low" | "medium" | "high";

export interface DnaSubjectRow {
  subject_id: number | null;
  subject_name: string;
  planned: number;
  completed: number;
  completion_rate: number;
}

export interface DnaTrendInfo {
  direction: DnaTrendDirection;
  this_week_completed: number;
  last_week_completed: number;
  delta_pct: number | null;
}

export interface BurnoutSignalRow {
  kind: string;
  severity: BurnoutSeverity;
  label: string;
  emoji: string;
  detail: string;
  metric: number | null;
}

export interface TeacherDnaResponse {
  student_id: number;
  student_name: string;
  window_days: number;
  has_enough_data: boolean;
  total_completed: number;
  total_planned: number;
  completion_rate: number;
  chronotype: DnaChronotype;
  peak_hour: number | null;
  peak_day_idx: number | null;
  peak_day_name: string | null;
  heatmap: number[][];
  morning_count: number;
  afternoon_count: number;
  evening_count: number;
  night_count: number;
  weekend_count: number;
  weekday_count: number;
  by_subject: DnaSubjectRow[];
  trend: DnaTrendInfo | null;
  hour_data_confidence: number;
  batch_completion_count: number;
  fallback_scheduled_count: number;
  burnout_risk_score: number;
  burnout_risk_level: BurnoutRiskLevel;
  burnout_signals: BurnoutSignalRow[];
  parent_count: number;
  parent_message_preview: string;
}

export interface DnaNotifyParentBody {
  body: string;
}

export interface DnaNotifyParentResult {
  note_id: number;
  student_id: number;
  parent_count: number;
}

// --- Review (FSRS) ---

export type ReviewState = "new" | "learning" | "review" | "relearning";

export interface ReviewBreakdownInfo {
  new: number;
  learning: number;
  review: number;
  relearning: number;
  due_now: number;
  total: number;
}

export interface ReviewCardRow {
  id: number;
  topic_id: number;
  topic_name: string;
  subject_id: number | null;
  subject_name: string | null;
  state: ReviewState;
  state_label: string;
  due_at: string | null;
  last_reviewed_at: string | null;
  last_rating: number | null;
  review_count: number;
  lapse_count: number;
  stability: number;
  difficulty: number;
}

export interface StruggleSectionOption {
  id: number;
  book_id: number;
  book_name: string;
  label: string;
  test_count: number;
}

export interface StruggleCardRow {
  topic_id: number;
  topic_name: string;
  subject_id: number;
  subject_name: string;
  card_id: number;
  state: ReviewState;
  state_label: string;
  difficulty: number;
  stability: number;
  lapse_count: number;
  review_count: number;
  score: number;
  reasons: string[];
  sections: StruggleSectionOption[];
}

export interface ReviewSubjectOption {
  id: number;
  name: string;
}

export interface TeacherReviewResponse {
  student_id: number;
  student_name: string;
  grade_label: string;
  exam_label: string;
  breakdown: ReviewBreakdownInfo;
  cards: ReviewCardRow[];
  subjects: ReviewSubjectOption[];
  struggle_cards: StruggleCardRow[];
}

export interface ReviewSeedBody {
  subject_id: number;
}

export interface ReviewSeedResult {
  subject_id: number;
  subject_name: string;
  added: number;
  skipped_existing: number;
}

// --- Goals (Hedefler) ---

export type GoalKind = "exam_target" | "subject" | "topic" | "weekly" | "daily" | "custom";
export type GoalStatus = "active" | "achieved" | "abandoned";

export interface GoalNodeRow {
  id: number;
  parent_id: number | null;
  kind: GoalKind;
  kind_label: string;
  kind_emoji: string;
  status: GoalStatus;
  title: string;
  description: string | null;
  target_value: number | null;
  current_value: number | null;
  unit: string | null;
  target_date: string | null;
  is_auto_generated: boolean;
  progress_pct: number | null;
  aggregated_pct: number | null;
  achieved_count: number;
  total_count: number;
  achieved_at: string | null;
  created_at: string;
  children: GoalNodeRow[];
}

export interface GoalTopicProgressRow {
  section_id: number;
  section_label: string;
  book_id: number;
  book_name: string;
  completed_tests: number;
  target_tests: number;
  progress_pct: number;
}

export interface GoalSubjectProgressRow {
  subject_id: number;
  subject_name: string;
  total_completed: number;
  total_target: number;
  progress_pct: number;
  topics: GoalTopicProgressRow[];
}

export interface GoalSummaryInfo {
  total: number;
  active: number;
  achieved: number;
  abandoned: number;
  overall_pct: number | null;
  next_target_date: string | null;
}

export interface TeacherGoalsResponse {
  student_id: number;
  student_name: string;
  subjects: GoalSubjectProgressRow[];
  topic_count: number;
  overall_pct: number;
  roots: GoalNodeRow[];
  summary: GoalSummaryInfo;
  finished_topic_count: number;
  kind_options: PromoteChoice[];
}

export interface TeacherGoalCreateBody {
  title: string;
  kind: GoalKind;
  parent_id?: number | null;
  description?: string | null;
  target_value?: number | null;
  current_value?: number | null;
  unit?: string | null;
  target_date?: string | null;
}

export interface TeacherGoalUpdateBody {
  title?: string | null;
  description?: string | null;
  target_value?: number | null;
  current_value?: number | null;
  unit?: string | null;
  target_date?: string | null;
}

export interface TeacherGoalActionResult {
  goal_id: number;
  student_id: number;
  status?: GoalStatus;
  deleted?: boolean;
}

// =============================================================================
// Paket 3.5d.1 — Analitik / Veliye Not / Fleet
// =============================================================================

export interface AnalyticsTrendPoint {
  date: string;
  label: string;
  completed: number;
  planned: number;
}

export interface AnalyticsSubjectRow {
  subject_id: number;
  name: string;
  total: number;
  completed: number;
  reserved: number;
  remaining: number;
  percent_done: number;
  percent_reserved: number;
  last_completed_at: string | null;
}

export interface TeacherStudentAnalyticsResponse {
  student_id: number;
  student_name: string;
  window_days: number;
  trend: AnalyticsTrendPoint[];
  subjects: AnalyticsSubjectRow[];
}

export interface ParentNoteBody {
  body: string;
}

export interface ParentNoteResult {
  note_id: number;
  fired: number;
  parent_count: number;
}

export interface TeacherBurnoutFleetRow {
  student_id: number;
  full_name: string;
  risk_score: number;
  risk_level: BurnoutRiskLevel;
  signal_count: number;
  is_active: boolean;
}

export interface TeacherBurnoutFleetResponse {
  rows: TeacherBurnoutFleetRow[];
  healthy_count: number;
  watch_count: number;
  warn_count: number;
  critical_count: number;
}

export interface TeacherReviewFleetRow {
  student_id: number;
  full_name: string;
  due_now: number;
  total: number;
  is_active: boolean;
}

export interface TeacherReviewFleetResponse {
  rows: TeacherReviewFleetRow[];
  total_due: number;
  total_cards: number;
}

// =============================================================================
// Paket 3.5d.2 — Dashboard warnings + reset-password + password-change
// =============================================================================

export interface DashboardWarningRow {
  student_id: number;
  student_name: string;
  level: WarningLevel;
  title: string;
  detail: string;
  is_paused: boolean;
}

export interface DashboardWarningsFeedResponse {
  rows: DashboardWarningRow[];
  total: number;
}

export interface StudentResetPasswordResult {
  student_id: number;
  email: string;
  temp_password: string;
  full_name: string;
}

export interface PasswordChangeBody {
  current_password?: string;
  new_password: string;
  confirm_password: string;
}

export interface PasswordChangeResult {
  must_change_password: boolean;
  password_changed_at: string;
}

// =============================================================================
// KP4a — Deneme sınavı sonuçları (Akademik Çıktı)
// =============================================================================

export type ExamSectionValue =
  | "lgs"
  | "tyt"
  | "ayt_say"
  | "ayt_ea"
  | "ayt_soz"
  | "ayt_dil";

export interface ExamSectionOption {
  value: ExamSectionValue;
  label: string;
}

export interface ExamSubjectInput {
  name: string;
  correct: number;
  wrong: number;
  blank: number;
}

export interface ExamCreateBody {
  title: string;
  exam_date: string;
  section: ExamSectionValue;
  total_correct?: number;
  total_wrong?: number;
  total_blank?: number;
  subjects?: ExamSubjectInput[];
  note?: string | null;
}

export interface ExamSubjectRow {
  name: string;
  correct: number;
  wrong: number;
  blank: number;
  net: number;
}

export interface ExamResultRow {
  id: number;
  title: string;
  exam_date: string;
  section: ExamSectionValue;
  section_label: string;
  total_correct: number;
  total_wrong: number;
  total_blank: number;
  total_questions: number;
  net: number;
  subjects: ExamSubjectRow[];
  note: string | null;
  created_at: string;
  created_by_name: string | null;
}

export interface ExamListSummary {
  count: number;
  avg_net: number;
  best_net: number;
  last_net: number | null;
  first_net: number | null;
  trend_delta: number | null;
}

export interface StudentExamListResponse {
  summary: ExamListSummary;
  rows: ExamResultRow[];
  section_options: ExamSectionOption[];
}

// =============================================================================
// KS1 — Koçluk seansı / değerlendirme kaydı
// =============================================================================

export type SessionStatus = "done" | "postponed" | "cancelled" | "no_show";
export type SessionChannel = "in_person" | "online" | "phone";

export interface SessionPrefillSubject {
  name: string;
  percent_done: number;
}

export interface SessionPrefillExam {
  title: string;
  exam_date: string;
  section_label: string;
  net: number;
  net_pct: number | null;
}

export interface SessionPrefillResponse {
  week_planned: number;
  week_completed: number;
  week_completion_pct: number | null;
  recent_rate: number;
  behind_subjects: SessionPrefillSubject[];
  latest_exam: SessionPrefillExam | null;
  exam_count: number;
}

export interface CoachingSessionCreateBody {
  session_date: string;
  status: SessionStatus;
  duration_min?: number | null;
  channel?: SessionChannel | null;
  agenda: string;
  next_change?: string | null;
  coach_note?: string | null;
  mood?: number | null;
  tags?: string[];
  capture_source?: string;
}

export interface CoachingSessionRow {
  id: number;
  session_date: string;
  status: SessionStatus;
  status_label: string;
  duration_min: number | null;
  channel: SessionChannel | null;
  channel_label: string | null;
  agenda: string;
  next_change: string | null;
  coach_note: string | null;
  mood: number | null;
  tags: string[];
  auto_snapshot: SessionPrefillResponse | null;
  capture_source: string;
  created_at: string;
}

export interface CoachingSessionSummary {
  total: number;
  done_count: number;
  postponed_count: number;
  cancelled_count: number;
  no_show_count: number;
  last_session_date: string | null;
}

export interface StudentSessionListResponse {
  summary: CoachingSessionSummary;
  rows: CoachingSessionRow[];
}

export interface AiConsentResponse {
  consented: boolean;
  consent_at: string | null;
  ai_premium: boolean;
  plan_code: string | null;
}

export interface TeacherPlanOption {
  code: string;
  label: string;
  short_description: string;
  price_monthly_try: number;
  tier_rank: number;
  ai_included: boolean;
  is_current: boolean;
  is_upgrade: boolean;
}

export interface TeacherPlanResponse {
  plan_code: string;
  plan_label: string;
  is_solo: boolean;
  ai_premium: boolean;
  trial_active: boolean;
  trial_days_left: number | null;
  options: TeacherPlanOption[];
  note: string | null;
  status: string;              // trialing | active | past_due | free | managed
  student_count: number;
  solo_monthly_price: number;  // öğrenci bandına göre Solo aylık (₺)
  annual_paid_months: number;
  sales_email: string;
  subscription_status: string | null;   // active | canceled | past_due | null
  subscription_period_end: string | null;
  subscription_cycle: string | null;
}

export interface PlanUpgradeBody {
  plan: string;
}

export interface SubscriptionRequestBody {
  plan: string;    // solo_pro | solo_elite
  cycle: string;   // monthly | academic_year
}

export interface SubscriptionRequestResult {
  ok: boolean;
  message: string;
  already_pending: boolean;
}

export interface TrialStatusResponse {
  is_solo: boolean;
  plan_code: string;
  plan_label: string;
  trial_active: boolean;
  days_left: number | null;
  trial_critical: boolean;
  student_count: number;
  student_limit: number;   // -1 = sınırsız
  over_limit: boolean;
  paywall: boolean;
  subscription_status: string | null;
  past_due: boolean;
  upgrade_target: string | null;
}

export interface SessionDraftResponse {
  agenda: string;
  coach_note: string;
  next_change: string;
  mood: number | null;
  tags: string[];
}

export interface TranscribeResponse {
  text: string;
}

export interface CoachingInsightResponse {
  summary: string;
  agenda_suggestions: string[];
  psychological_tips: string[];
  watch_outs: string[];
  based_on_sessions: number;
  generated_at: string | null;
}

export interface CoachingInsightCacheResponse {
  insight: CoachingInsightResponse | null;
  is_stale: boolean;
}

// =============================================================================
// KS2 — Tahsilat
// =============================================================================

export type PaymentMethod = "cash" | "transfer" | "other";
export type BillingStatus = "no_rate" | "paid" | "partial" | "pending";

export interface PaymentRow {
  id: number;
  amount: number;
  paid_at: string;
  method: PaymentMethod;
  method_label: string;
  period_month: string | null;
  note: string | null;
  created_at: string;
}

export interface StudentPaymentsResponse {
  rows: PaymentRow[];
  total_paid: number;
}

export interface PaymentCreateBody {
  amount: number;
  paid_at: string;
  method?: PaymentMethod;
  period_month?: string | null;
  note?: string | null;
}

export interface BillingStudentRow {
  student_id: number;
  student_name: string;
  session_fee: number | null;
  done_sessions: number;
  accrued: number | null;
  paid: number;
  balance: number | null;
  status: BillingStatus;
}

export interface BillingTotals {
  accrued: number;
  paid: number;
  balance: number;
}

export interface BillingMonthResponse {
  month: string;
  rows: BillingStudentRow[];
  totals: BillingTotals;
}
