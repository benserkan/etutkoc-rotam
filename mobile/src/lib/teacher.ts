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
