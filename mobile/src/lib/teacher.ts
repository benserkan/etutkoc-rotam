import { apiRequest } from "./api";
import type { ExamRow, ExamSummary } from "./student";

export type WarningLevel = "red" | "amber" | "green";

// --- Öğrenci listesi ---
export interface TeacherStudentListItem {
  id: number;
  full_name: string;
  email: string;
  grade_level: number | null;
  is_active: boolean;
  last_login_at: string | null;
  worst_warning_level: WarningLevel;
  worst_warning_title: string | null;
  worst_warning_detail: string | null;
  today_gorev_total: number;
  today_gorev_done: number;
  week_pct: number; // 0..1
  has_pending_request: boolean;
}
export interface TeacherStudentListResponse {
  items: TeacherStudentListItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// --- Öğrenci detayı (lean overview) ---
export interface WarningItem {
  level: string;
  code: string;
  title: string;
  detail: string;
  link: string;
  link_label: string;
}
export interface GorevBreakdown {
  gorev_total: number;
  gorev_done: number;
  gorev_pct: number;
  test_planned: number;
  test_completed: number;
  deneme_planned: number;
  deneme_completed: number;
  deneme_count: number;
  deneme_done: number;
  etkinlik_count: number;
  etkinlik_done: number;
}
export interface TeacherStudentDetail {
  student: {
    id: number;
    full_name: string;
    email: string;
    grade_level: number | null;
    is_active: boolean;
    display_grade_label: string | null;
    track_label: string | null;
    last_login_at: string | null;
  };
  worst_warning_level: WarningLevel;
  warning_items: WarningItem[];
  pending_request_count: number;
  has_active_program: boolean;
  gorev_today: GorevBreakdown | null;
  gorev_week: GorevBreakdown | null;
}

export const teacherKeys = {
  students: (q?: string) => ["teacher", "students", q ?? ""] as const,
  student: (id: number) => ["teacher", "student", id] as const,
};

export function getTeacherStudents(q?: string): Promise<TeacherStudentListResponse> {
  const qs = q && q.trim() ? `?q=${encodeURIComponent(q.trim())}&page_size=100` : "?page_size=100";
  return apiRequest<TeacherStudentListResponse>(`/api/v2/teacher/students${qs}`);
}
export function getTeacherStudent(id: number): Promise<TeacherStudentDetail> {
  return apiRequest<TeacherStudentDetail>(`/api/v2/teacher/students/${id}`);
}

// --- Denemeler (koç sonuç girer) ---
export interface ExamSectionOption {
  value: string;
  label: string;
}
export interface TeacherExamsResponse {
  summary: ExamSummary;
  rows: ExamRow[];
  section_options: ExamSectionOption[];
}
export interface ExamSubjectInput {
  name: string;
  correct: number;
  wrong: number;
  blank: number;
}
export interface TeacherExamCreateBody {
  title: string;
  exam_date: string;
  section: string;
  total_correct: number;
  total_wrong: number;
  total_blank: number;
  subjects?: ExamSubjectInput[];
  note?: string | null;
}
export function getTeacherStudentExams(id: number): Promise<TeacherExamsResponse> {
  return apiRequest<TeacherExamsResponse>(`/api/v2/teacher/students/${id}/exams`);
}
export function createTeacherExam(id: number, body: TeacherExamCreateBody): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${id}/exams`, { method: "POST", body });
}
export function deleteTeacherExam(examId: number): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/exams/${examId}`, { method: "DELETE" });
}

// --- Seanslar (koç kaydeder) ---
export interface CoachingSessionRow {
  id: number;
  session_date: string;
  status: string;
  status_label: string;
  duration_min: number | null;
  channel: string | null;
  channel_label: string | null;
  agenda: string;
  next_change: string | null;
  coach_note: string | null;
  mood: number | null;
  tags: string[];
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
export interface SessionCreateBody {
  session_date: string;
  status?: string;
  duration_min?: number | null;
  channel?: string | null;
  agenda: string;
  next_change?: string | null;
  coach_note?: string | null;
  mood?: number | null;
  tags?: string[];
  capture_source?: string | null;
}
export function getTeacherStudentSessions(id: number): Promise<StudentSessionListResponse> {
  return apiRequest<StudentSessionListResponse>(`/api/v2/teacher/students/${id}/sessions`);
}
export function createTeacherSession(id: number, body: SessionCreateBody): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${id}/sessions`, { method: "POST", body });
}

export const teacherDetailKeys = {
  exams: (id: number) => ["teacher", "student", id, "exams"] as const,
  sessions: (id: number) => ["teacher", "student", id, "sessions"] as const,
};

// --- Tahsilat ---
export type BillingStatus = "no_rate" | "paid" | "partial" | "pending";
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
export interface PaymentCreateBody {
  amount: number;
  paid_at: string;
  method?: "cash" | "transfer" | "other";
  period_month?: string | null;
  note?: string | null;
}
export const teacherBillingKeys = {
  month: (m: string) => ["teacher", "billing", m] as const,
};
export function getTeacherBilling(month?: string): Promise<BillingMonthResponse> {
  const qs = month ? `?month=${encodeURIComponent(month)}` : "";
  return apiRequest<BillingMonthResponse>(`/api/v2/teacher/billing${qs}`);
}
export function setStudentRate(studentId: number, sessionFee: number): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${studentId}/rate`, {
    method: "POST",
    body: { session_fee: sessionFee },
  });
}
export function createStudentPayment(studentId: number, body: PaymentCreateBody): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${studentId}/payments`, { method: "POST", body });
}

// ====== Program (haftalık görünüm + görev ekle) ======
export interface TeacherTaskItemRow {
  id: number;
  book_id: number | null;
  book_name: string;
  book_type: string | null;
  subject_name: string | null;
  section_label: string | null;
  planned_count: number;
  completed_count: number;
}
export interface TeacherTaskRow {
  id: number;
  date: string;
  type: string;
  status: string;
  title: string;
  period: string | null;
  is_draft: boolean;
  items: TeacherTaskItemRow[];
  planned_count: number;
  completed_count: number;
  pct: number;
  solved_count: number | null;
}
// Kural-tabanlı öneri (AI DEĞİL): koçun geçmiş planları + öğrencinin atanmış
// kitap/bölümleri + geride kalma + tekrar zorluğundan türetilir. Uydurma yok.
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
export interface TeacherWeekDay {
  date: string;
  dow_label: string;
  is_today: boolean;
  is_future: boolean;
  is_past: boolean;
  tasks_count: number;
  planned: number;
  completed: number;
  pct: number;
  test_planned: number;
  test_completed: number;
  deneme_count: number;
  etkinlik_count: number;
  tasks: TeacherTaskRow[];
  draft_count: number;
  // Öneri motoru alanları (opsiyonel — backend week response'unda gelir)
  suggestions?: TeacherSuggestionInline[];
  maturity_value?: number;
  maturity_label?: string;
  weeks_observed?: number;
  days_observed?: number;
}
export interface TeacherWeekResponse {
  student_id: number;
  start_date: string;
  end_date: string;
  prev_start: string;
  next_start: string;
  days: TeacherWeekDay[];
  total_planned: number;
  total_completed: number;
  total_pct: number;
}
export interface TaskItemBody {
  book_id?: number | null;
  section_id?: number | null;
  label?: string | null;
  planned_count: number;
}
export interface TaskCreateBody {
  date: string;
  type?: string; // test | video | ozet | tekrar | other
  title: string;
  period?: string | null;
  items: TaskItemBody[];
}
export function getTeacherStudentWeek(id: number, start?: string): Promise<TeacherWeekResponse> {
  const qs = start ? `?start=${encodeURIComponent(start)}` : "";
  return apiRequest<TeacherWeekResponse>(`/api/v2/teacher/students/${id}/week${qs}`);
}
// Öneri kabul/ret (kural-tabanlı motor — kabul gerçek görev oluşturur, ret sistemin
// öğrenmesini sağlar). Endpoint'ler haftalık planı bayatlar → ProgramTab refetch eder.
export function acceptTeacherSuggestion(id: number, body: { date: string; book_id: number; section_id: number; planned_count: number }): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/insights/students/${id}/suggestions/accept`, { method: "POST", body });
}
export function rejectTeacherSuggestion(id: number, body: { date: string; book_id: number; section_id: number }): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/insights/students/${id}/suggestions/reject`, { method: "POST", body });
}
export function acceptAllTeacherSuggestions(id: number, body: { date: string; items: { book_id: number; section_id: number; planned_count: number }[] }): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/insights/students/${id}/suggestions/accept-all`, { method: "POST", body });
}
export function createTeacherTask(id: number, body: TaskCreateBody): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${id}/tasks`, { method: "POST", body });
}
export function deleteTeacherTask(taskId: number): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/tasks/${taskId}`, { method: "DELETE" });
}

// ====== Öğrencinin atanmış kitapları + bölümleri (görev ekleme seçici) ======
export interface StudentBookSectionRow {
  section_id: number;
  label: string;
  topic_name: string | null;
  test_count: number;
  completed_count: number;
  reserved_count: number;
}
export interface StudentBookRow {
  student_book_id: number;
  book_id: number;
  book_name: string;
  book_type: string;
  book_type_label_tr: string;
  subject_id: number;
  subject_name: string;
  section_count: number;
  sections: StudentBookSectionRow[];
}
export interface StudentBookListResponse {
  items: StudentBookRow[];
  total: number;
}
export function getTeacherStudentBooks(id: number): Promise<StudentBookListResponse> {
  return apiRequest<StudentBookListResponse>(`/api/v2/teacher/students/${id}/books`);
}

// Müfredat-tam ders havuzu (etkinlik görevleri için — kitap zorunlu değil).
export interface SubjectBrief {
  id: number;
  name: string;
}
export interface AllSubjectsResponse {
  items: SubjectBrief[];
}
export function getTeacherStudentAllSubjects(id: number): Promise<AllSubjectsResponse> {
  return apiRequest<AllSubjectsResponse>(`/api/v2/teacher/students/${id}/all-subjects`);
}

// Sesli dikte → düz metin (alan doldurma). Ses saklanmaz; rıza + kredi gerekir.
export interface TranscribeResponse {
  text: string;
}
export function transcribeSession(
  id: number,
  body: { audio_base64: string; media_type: string },
): Promise<TranscribeResponse> {
  return apiRequest<TranscribeResponse>(`/api/v2/teacher/students/${id}/sessions/transcribe`, {
    method: "POST",
    body,
  });
}

// ====== Öğrenci davet (oluştur) ======
export interface StudentCreateBody {
  full_name: string;
  email: string;
  grade_level?: number | null;
  is_graduate?: boolean;
  track?: string | null;
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
export function createTeacherStudent(body: StudentCreateBody): Promise<{ data: StudentCreateResult }> {
  return apiRequest<{ data: StudentCreateResult }>(`/api/v2/teacher/students`, { method: "POST", body });
}

// ====== Paket / abonelik ======
export interface TeacherPlanOption {
  code: string;
  label: string;
  short_description?: string;
  price_monthly_try: number;
  max_students: number | null;
  tier_rank?: number;
  ai_included?: boolean;
  is_current?: boolean;
  is_upgrade?: boolean;
  is_recommended?: boolean;
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
  status: string;
  student_count: number;
  solo_monthly_price: number;
  recommended_plan: string;
  annual_paid_months: number;
  sales_email: string;
  subscription_status: string | null;
  subscription_period_end: string | null;
  subscription_cycle: string | null;
  post_trial_plan: string | null;
  post_trial_plan_label: string | null;
  post_trial_plan_credits: number | null;
  ai_credits_used: number;
  ai_credits_allocated: number;
  has_pending_subscription_request: boolean;
}
export const teacherMiscKeys = {
  week: (id: number, start?: string) => ["teacher", "student", id, "week", start ?? "current"] as const,
  studentBooks: (id: number) => ["teacher", "student", id, "books"] as const,
  plan: ["teacher", "plan"] as const,
};
export function getTeacherPlan(): Promise<TeacherPlanResponse> {
  return apiRequest<TeacherPlanResponse>(`/api/v2/teacher/plan`);
}
export function upgradeTeacherPlan(plan: string): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/plan/upgrade`, { method: "POST", body: { plan } });
}
export interface SubscriptionRequestResult {
  ok: boolean;
  already_pending: boolean;
  message: string;
}
export function requestTeacherSubscription(plan?: string, cycle?: string): Promise<SubscriptionRequestResult> {
  return apiRequest<SubscriptionRequestResult>(`/api/v2/teacher/subscription-request`, {
    method: "POST",
    body: { plan: plan ?? null, cycle: cycle ?? null },
  });
}

// ====== Öğrenci aktif / pasif ======
export function deactivateTeacherStudent(id: number): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${id}/deactivate`, { method: "POST", body: {} });
}
export function reactivateTeacherStudent(id: number): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${id}/reactivate`, { method: "POST", body: {} });
}

// ====== Koç — öğrenci talepleri (TaskRequest yönetimi) ======
export type TeacherRequestType = "change" | "replace" | "remove" | "question" | "add";
export type TeacherRequestStatus = "pending" | "approved" | "rejected" | "withdrawn" | "resolved";
export interface TeacherRequestListItem {
  id: number;
  student_id: number;
  student_name: string;
  type: TeacherRequestType;
  status: TeacherRequestStatus;
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
export const teacherRequestKeys = {
  list: (status: string) => ["teacher", "requests", status] as const,
};
export function getTeacherRequests(status = "pending"): Promise<TeacherRequestListResponse> {
  return apiRequest<TeacherRequestListResponse>(
    `/api/v2/teacher/requests?status=${encodeURIComponent(status)}&page_size=100`,
  );
}
export function approveTeacherRequest(id: number, response?: string): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/requests/${id}/approve`, {
    method: "POST",
    body: { response: response ?? null },
  });
}
export function rejectTeacherRequest(id: number, reason: string): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/requests/${id}/reject`, { method: "POST", body: { reason } });
}
export function respondTeacherRequest(id: number, response: string): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/requests/${id}/respond`, { method: "POST", body: { response } });
}

// ====== Koç — öğrenci Gelişim izleme (DNA/Odak/Tekrar/Hedef) ======
export interface TeacherDnaSubject { subject_name: string; completion_rate: number; }
export interface TeacherDnaTrend { direction: string; delta_pct: number | null; this_week_completed: number; last_week_completed: number; }
export interface TeacherDnaResponse {
  student_name: string;
  window_days: number;
  has_enough_data: boolean;
  completion_rate: number;
  chronotype: string;
  peak_hour: number | null;
  peak_day_name: string | null;
  morning_count: number;
  afternoon_count: number;
  evening_count: number;
  night_count: number;
  weekday_count: number;
  weekend_count: number;
  by_subject: TeacherDnaSubject[];
  trend: TeacherDnaTrend | null;
}
export interface TeacherFocusSession { id: number; planned_minutes: number; actual_minutes: number; interrupted: boolean; label: string | null; }
export interface TeacherFocusResponse {
  student_name: string;
  today_work_sessions: number;
  today_work_minutes: number;
  streak_days: number;
  longest_streak: number;
  points_total: number;
  recent_sessions: TeacherFocusSession[];
}
export interface TeacherReviewBreakdown { new: number; learning: number; review: number; relearning: number; due_now: number; total: number; }
export interface TeacherStruggleCard { topic_id: number; topic_name: string; subject_name: string; state_label: string; lapse_count: number; }
export interface TeacherReviewSubjectOption { id: number; name: string; }
export interface TeacherReviewResponse {
  student_name: string;
  breakdown: TeacherReviewBreakdown;
  struggle_cards: TeacherStruggleCard[];
  subjects: TeacherReviewSubjectOption[];
}
export interface TeacherGoalNode {
  id: number;
  kind: string;
  kind_label: string;
  status: string;
  title: string;
  target_value: number | null;
  current_value: number | null;
  unit: string | null;
  progress_pct: number | null;
  aggregated_pct: number | null;
  children: TeacherGoalNode[];
}
export interface TeacherGoalSummary { total: number; active: number; achieved: number; overall_pct: number | null; }
export interface TeacherGoalsResponse {
  student_name: string;
  overall_pct: number;
  roots: TeacherGoalNode[];
  summary: TeacherGoalSummary;
}
export interface TeacherGoalCreateBody {
  title: string;
  kind?: string;
  parent_id?: number | null;
  target_value?: number | null;
  unit?: string | null;
  target_date?: string | null;
}
export const teacherDevKeys = {
  dna: (id: number) => ["teacher", "student", id, "dna"] as const,
  focus: (id: number) => ["teacher", "student", id, "focus"] as const,
  review: (id: number) => ["teacher", "student", id, "review"] as const,
  goals: (id: number) => ["teacher", "student", id, "goals"] as const,
  insight: (id: number) => ["teacher", "student", id, "insight"] as const,
  aiConsent: ["teacher", "ai-consent"] as const,
};

// ===== AI Koçluk İçgörüsü (KS4) =====
export interface CoachingInsight {
  summary: string;
  agenda_suggestions: string[];
  psychological_tips: string[];
  watch_outs: string[];
  based_on_sessions: number;
  generated_at?: string | null;
}
export interface CoachingInsightCache {
  insight: CoachingInsight | null;
  is_stale: boolean;
}
export interface AiConsent {
  consented: boolean;
  consent_at?: string | null;
  ai_premium: boolean;
  plan_code?: string | null;
}
export function getTeacherCoachingInsight(id: number): Promise<CoachingInsightCache> {
  return apiRequest<CoachingInsightCache>(`/api/v2/teacher/students/${id}/coaching-insight`);
}
export function generateTeacherCoachingInsight(id: number): Promise<CoachingInsightCache> {
  return apiRequest<CoachingInsightCache>(`/api/v2/teacher/students/${id}/coaching-insight`, { method: "POST" });
}
export function getTeacherAiConsent(): Promise<AiConsent> {
  return apiRequest<AiConsent>(`/api/v2/teacher/ai-consent`);
}
export function setTeacherAiConsent(): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/ai-consent`, { method: "POST" });
}
export function getTeacherStudentDna(id: number): Promise<TeacherDnaResponse> {
  return apiRequest<TeacherDnaResponse>(`/api/v2/teacher/students/${id}/dna`);
}
export function getTeacherStudentFocus(id: number): Promise<TeacherFocusResponse> {
  return apiRequest<TeacherFocusResponse>(`/api/v2/teacher/students/${id}/focus`);
}
export function getTeacherStudentReview(id: number): Promise<TeacherReviewResponse> {
  return apiRequest<TeacherReviewResponse>(`/api/v2/teacher/students/${id}/review`);
}
export function getTeacherStudentGoals(id: number): Promise<TeacherGoalsResponse> {
  return apiRequest<TeacherGoalsResponse>(`/api/v2/teacher/students/${id}/goals`);
}
export function createTeacherGoal(id: number, body: TeacherGoalCreateBody): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${id}/goals`, { method: "POST", body });
}
export interface ReviewSeedResult {
  subject_id: number;
  subject_name: string;
  added: number;
  skipped_existing: number;
}
export function seedTeacherReview(id: number, subjectId: number): Promise<{ data: ReviewSeedResult }> {
  return apiRequest(`/api/v2/teacher/students/${id}/review/seed`, { method: "POST", body: { subject_id: subjectId } });
}
