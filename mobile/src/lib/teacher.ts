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
export interface TeacherExamCreateBody {
  title: string;
  exam_date: string;
  section: string;
  total_correct: number;
  total_wrong: number;
  total_blank: number;
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
  max_students: number | null;
  monthly: number;
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
