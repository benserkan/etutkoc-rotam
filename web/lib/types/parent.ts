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
  is_active: boolean;   // false → koçluk sona erdi (rozet)
  today_planned: number;
  today_completed: number;
  week_planned: number;
  week_completed: number;
  week_completion_rate: number | null;
  // GÖREV-bazlı (her madde 1 görev; deneme/test/etkinlik AYRI)
  today_gorev_total: number;
  today_gorev_done: number;
  week_gorev_total: number;
  week_gorev_done: number;
  week_gorev_rate: number | null;
  week_test_planned: number;
  week_test_completed: number;
  rate_7d: number | null;
  consistency_7d: number | null;
  warning_level: WarningLevel;
  // Son deneme özet
  latest_exam_title: string | null;
  latest_exam_date: string | null;
  latest_exam_net: number | null;
  latest_exam_section: string | null;
  latest_exam_count: number;
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
  gorev_total: number;
  gorev_done: number;
}

export interface ParentWeekInfo {
  planned: number;
  completed: number;
  rate: number | null;
  gorev_total: number;
  gorev_done: number;
  gorev_rate: number | null;
  test_planned: number;            // yalnız soru bankası (deneme HARİÇ)
  test_completed: number;
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
  // GÖREV-bazlı (her madde 1 görev; deneme/test/etkinlik AYRI)
  gorev_total: number;
  gorev_done: number;
  test_planned: number;            // yalnız soru bankası (deneme HARİÇ)
  test_completed: number;
  deneme_count: number;
  etkinlik_count: number;
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
// Haftalık rapor (doyurucu analiz) — web + mobil paylaşır
// =============================================================================

export interface WeeklyReportDaily {
  date: string;
  weekday: number; // 0=Pazartesi
  gorev_done: number;
  gorev_total: number;
  pct: number;
  test_completed: number;
  test_planned: number;
}

export interface WeeklyReportSubject {
  subject_name: string;
  planned: number; // bu hafta planlanan test
  completed: number;
  pct: number;
}

export interface WeeklyReportExam {
  title: string;
  exam_date: string | null;
  section_label: string;
  net: number;
  total_correct: number;
  total_wrong: number;
  total_blank: number;
}

export type WeeklyComparisonDirection = "up" | "down" | "flat" | "none";

export interface WeeklyReportComparison {
  this_completion_pct: number;
  last_completion_pct: number | null;
  completion_delta: number | null;
  this_test_completed: number;
  last_test_completed: number | null;
  test_delta: number | null;
  this_gorev_done: number;
  last_gorev_done: number | null;
  direction: WeeklyComparisonDirection;
}

export interface WeeklyReportNote {
  body: string;
  teacher_name: string | null;
  created_at: string | null;
}

export type WeeklyVerdictLevel = "good" | "warn" | "bad";

export interface WeeklyReportResponse {
  student: ParentStudentRef;
  start: string;
  end: string;
  prev_start: string;
  next_start: string;
  gorev_done: number;
  gorev_total: number;
  completion_pct: number;
  test_completed: number;
  test_planned: number;
  active_days: number;
  daily: WeeklyReportDaily[];
  subjects: WeeklyReportSubject[];
  most_completed_subject: string | null;
  most_neglected_subject: string | null;
  most_neglected_pct: number | null;
  comparison: WeeklyReportComparison;
  exams: WeeklyReportExam[];
  exam_trend_delta: number | null;
  exam_trend_section: string | null;
  teacher_notes: WeeklyReportNote[];
  verdict_level: WeeklyVerdictLevel;
  verdict_text: string;
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
  // E-posta tarafı (default açık, opt-out)
  daily_summary_enabled: boolean;
  weekly_report_enabled: boolean;
  empty_day_alert_enabled: boolean;
  drop_alert_enabled: boolean;
  new_program_alert_enabled: boolean;
  teacher_note_enabled: boolean;
  exam_approaching_enabled: boolean;
  // WhatsApp tarafı (default kapalı, opt-in — KVKK)
  daily_summary_wa_enabled: boolean;
  weekly_report_wa_enabled: boolean;
  empty_day_alert_wa_enabled: boolean;
  drop_alert_wa_enabled: boolean;
  new_program_alert_wa_enabled: boolean;
  teacher_note_wa_enabled: boolean;
  exam_approaching_wa_enabled: boolean;
  // 18 yaş altı öğrenciye doğrudan WA için veli onayı
  child_whatsapp_consent: boolean;
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
  // E-posta
  daily_summary: boolean;
  weekly_report: boolean;
  empty_day: boolean;
  new_program: boolean;
  drop_alert: boolean;
  teacher_note: boolean;
  exam_approaching: boolean;
  // WhatsApp
  daily_summary_wa: boolean;
  weekly_report_wa: boolean;
  empty_day_wa: boolean;
  new_program_wa: boolean;
  drop_alert_wa: boolean;
  teacher_note_wa: boolean;
  exam_approaching_wa: boolean;
  child_whatsapp_consent: boolean;
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
  // P1 — cep telefonu (SMS ile doğrulanır; backend opsiyonel kabul, yeni
  // istemcide zorunlu gönderilir)
  phone?: string;
  // P0 — opsiyonel iletişim tercih matrisi (aktivasyon ekranındaki seçimler)
  notification_preferences?: Record<string, boolean>;
  quiet_start?: string;
  quiet_end?: string;
  child_whatsapp_consent?: boolean;
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

// =============================================================================
// M4 — Seans hareketleri (veli görünümü)
// =============================================================================

export type ParentSessionStatus = "done" | "postponed" | "cancelled" | "no_show";
export type ParentSessionChannel = "in_person" | "online" | "phone";
export type ParentPaymentMethod = "cash" | "transfer" | "other";

export interface ParentSessionItem {
  id: number;
  session_date: string;            // "YYYY-MM-DD"
  status: ParentSessionStatus;
  status_label: string;
  duration_min: number | null;
  channel: ParentSessionChannel | null;
  channel_label: string | null;
}

export interface ParentPaymentItem {
  id: number;
  paid_at: string;
  amount: number;
  method: ParentPaymentMethod;
  method_label: string;
  period_month: string | null;
  note: string | null;
}

export interface ParentBillingMonth {
  period_month: string;            // "YYYY-MM"
  period_label: string;            // "Mart 2026"
  sessions_done: number;
  session_fee: number;
  accrued: number;
  paid: number;
  balance: number;
}

export interface ParentBillingSummary {
  session_fee: number;
  total_accrued: number;
  total_paid: number;
  open_balance: number;
  months: ParentBillingMonth[];
  payments: ParentPaymentItem[];
}

export interface ParentSessionsResponse {
  student_id: number;
  student_name: string;
  sessions: ParentSessionItem[];
  billing: ParentBillingSummary;
}
