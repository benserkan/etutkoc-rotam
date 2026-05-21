/**
 * Manuel TypeScript tipleri — `/api/v2/parent/*` için.
 *
 * Pydantic şemalarıyla (`app/routes/api_v2/schemas/parent.py`) birebir aynı.
 * Veri yapısı `app/services/parent_view.py`'deki dict çıktılarıyla mutlak korunur.
 *
 * GİZLİLİK: Veli sadece görev tamamlama metrikleri / istikrar / projeksiyon
 * görür. Asla deneme net sayısı / konu bazında doğru-yanlış / öğrenci-öğretmen
 * mesajı gösterilmez.
 */

// =============================================================================
// Ortak
// =============================================================================

export type ParentRelation = "anne" | "baba" | "vasi" | "diger";
export type WarningLevel = "red" | "amber" | "green";

// =============================================================================
// Dashboard
// =============================================================================

export interface ParentChildSummary {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  is_graduate: boolean;
  display_grade_label: string | null;
  academic_year: string | null;
  exam_date: string | null;
  exam_label: string | null;
  exam_target: string;
  relation: ParentRelation | null;
  is_primary: boolean;
  today_planned: number;
  today_completed: number;
  week_planned: number;
  week_completed: number;
  week_completion_rate: number | null;
  rate_7d: number | null;
  consistency_7d: number | null;
  warning_level: WarningLevel;
}

export interface ParentDashboardResponse {
  children: ParentChildSummary[];
}

// =============================================================================
// Student detail
// =============================================================================

export interface ParentStudentInfo {
  id: number;
  full_name: string;
  grade_level: number | null;
  is_graduate: boolean;
  display_grade_label: string | null;
  academic_year: string | null;
  exam_date: string | null;
  exam_label: string | null;
  exam_target: string;
}

export interface ParentTodayInfo {
  planned: number;
  completed: number;
}

export interface ParentWeekInfo {
  planned: number;
  completed: number;
  rate: number | null;
}

export interface ParentSubjectItem {
  subject_id: number | null;
  name: string;
  percent_done: number;
}

export interface ParentTrendPoint {
  date: string;
  label: string;
  completed: number;
  planned: number;
}

export interface ParentProjectionInfo {
  total_tests: number;
  completed_tests: number;
  remaining_tests: number;
  rate_per_day: number | null;
  days_left_to_exam: number | null;
  expected_completed_by_exam: number;
  gap: number;
  status: WarningLevel;
}

export interface ParentTeacherNoteItem {
  id: number;
  body: string;
  teacher_name: string | null;
  created_at: string | null;
  delivered_at: string | null;
}

export interface ParentStudentOverviewResponse {
  student: ParentStudentInfo;
  today: ParentTodayInfo;
  week: ParentWeekInfo;
  rate_7d_pct: number | null;
  rate_30d_pct: number | null;
  consistency_7d_pct: number | null;
  warning_level: WarningLevel;
  subjects: ParentSubjectItem[];
  trend: ParentTrendPoint[];
  projection: ParentProjectionInfo;
  teacher_notes: ParentTeacherNoteItem[];
}

// =============================================================================
// Week
// =============================================================================

export interface ParentWeekBookItem {
  book_name: string | null;
  subject_name: string | null;
  subject_id: number | null;
  section_label: string | null;
  topic_name: string | null;
  planned_count: number;
  completed_count: number;
}

export interface ParentWeekTask {
  id: number;
  title: string;
  type: string | null;
  status: string | null;
  book_items: ParentWeekBookItem[];
}

export interface ParentWeekDay {
  date: string;
  weekday: number;
  tasks: ParentWeekTask[];
  task_count: number;
  planned_total: number;
  completed_total: number;
}

export interface ParentStudentRef {
  id: number;
  full_name: string;
}

export interface ParentWeekResponse {
  student: ParentStudentRef;
  start: string;
  end: string;
  prev_start: string;
  next_start: string;
  days: ParentWeekDay[];
}

// =============================================================================
// Notifications
// =============================================================================

export type ParentNotificationKind =
  | "daily_summary"
  | "empty_day"
  | "weekly_report"
  | "new_program"
  | "drop_alert"
  | "teacher_note"
  | "invitation"
  | "otp"
  | "exam_approaching";

export type ParentNotificationChannel = "email" | "whatsapp" | "sms";
export type ParentNotificationStatus =
  | "queued"
  | "sent"
  | "failed"
  | "suppressed";

export interface ParentNotificationItem {
  id: number;
  kind: ParentNotificationKind | string;
  channel: ParentNotificationChannel | string;
  status: ParentNotificationStatus | string;
  subject: string | null;
  student_name: string | null;
  sent_at: string | null;
  queued_at: string | null;
}

export interface ParentNotificationsResponse {
  items: ParentNotificationItem[];
  total: number;
}

// =============================================================================
// Settings
// =============================================================================

export interface ParentPreferencesInfo {
  daily_summary_enabled: boolean;
  weekly_report_enabled: boolean;
  empty_day_alert_enabled: boolean;
  drop_alert_enabled: boolean;
  new_program_alert_enabled: boolean;
  teacher_note_enabled: boolean;
  exam_approaching_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  unsubscribed_at: string | null;
}

export interface ParentWhatsAppInfo {
  enabled: boolean;
  phone: string | null;
  verified_at: string | null;
  pending_verify: boolean;
  pending_phone: string | null;
  pending_expires_at: string | null;
  dev_test_code: string | null;
}

export interface ParentChildLink {
  student_id: number;
  full_name: string;
  relation: ParentRelation | null;
  relation_label: string;
  is_primary: boolean;
  muted: boolean;
}

export interface ParentSettingsResponse {
  preferences: ParentPreferencesInfo;
  whatsapp: ParentWhatsAppInfo;
  children: ParentChildLink[];
}

// =============================================================================
// Mutation bodies
// =============================================================================

export interface ParentPreferencesBody {
  daily_summary: boolean;
  weekly_report: boolean;
  empty_day: boolean;
  new_program: boolean;
  drop_alert: boolean;
  teacher_note: boolean;
  exam_approaching: boolean;
  quiet_start: string;
  quiet_end: string;
}

export interface ParentMuteBody {
  muted: boolean;
}

export interface ParentWhatsAppStartBody {
  phone: string;
}

export interface ParentWhatsAppVerifyBody {
  code: string;
}

// =============================================================================
// Invitation flow (public)
// =============================================================================

export interface ParentInvitationInfo {
  token: string;
  invited_email: string;
  student_full_name: string;
  invited_by_full_name: string;
  relation: ParentRelation;
  relation_label: string;
  is_primary: boolean;
  expires_at: string;
}

export interface ParentInvitationAcceptBody {
  full_name: string;
  password: string;
  password_confirm: string;
  kvkk_accept: boolean;
}

export interface ParentInvitationAcceptResult {
  user_id: number;
  full_name: string;
  email: string;
  is_new_account: boolean;
  redirect_url: string;
}

// =============================================================================
// Unsubscribe
// =============================================================================

export type ParentUnsubscribeStatus = "unsubscribed" | "already" | "invalid";

export interface ParentUnsubscribeResult {
  status: ParentUnsubscribeStatus;
}
