import { apiRequest } from "./api";

// ETÜTKOÇ /api/v2/student — web tipleriyle aynı (yalnız mobilde kullanılan alt küme).

export interface StudentTaskItem {
  id: number;
  book_id: number | null;
  book_name: string;
  book_type?: string | null;
  subject_id?: number | null;
  subject_name?: string | null;
  section_id: number | null;
  section_label: string | null;
  topic_name: string | null;
  planned: number;
  completed: number;
  is_full: boolean;
  correct: number | null;
  wrong: number | null;
}

export type TaskStatus = "pending" | "in_progress" | "completed" | string;

export interface StudentTask {
  id: number;
  title: string;
  type: string;
  status: TaskStatus;
  date: string;
  period: "morning" | "noon" | "evening" | null;
  items: StudentTaskItem[];
  planned_count: number;
  completed_count: number;
  pct: number;
  solved_count?: number | null;
  is_future_blocked: boolean;
  is_past: boolean;
  has_pending_request: boolean;
  work_block_id?: number | null;
  work_block_unit?: string | null;
}

export interface DaySummary {
  total_tasks: number;
  planned_count: number;
  completed_count: number;
  pct: number; // GÖREV tamamlama 0..1
  gorev_total: number;
  gorev_done: number;
  test_planned: number;
  test_completed: number;
  deneme_count: number;
  etkinlik_count: number;
}

export interface CanRequestMatrix {
  change: boolean;
  replace: boolean;
  remove: boolean;
  question: boolean;
  add: boolean;
}

export interface StudentDayResponse {
  date: string;
  is_today: boolean;
  is_future: boolean;
  is_past: boolean;
  prev_date: string;
  next_date: string;
  tasks: StudentTask[];
  summary: DaySummary;
  day_note: string;
  can_request: CanRequestMatrix;
}

export type RequestType = "change" | "replace" | "remove" | "question" | "add";
export type RequestStatus = "pending" | "approved" | "rejected" | "withdrawn" | "resolved";

export interface StudentRequestItem {
  id: number;
  type: RequestType;
  status: RequestStatus;
  task_id: number | null;
  task_title: string | null;
  task_date: string | null;
  message: string | null;
  proposed_book_name: string | null;
  proposed_section_label: string | null;
  proposed_count: number | null;
  proposed_date: string | null;
  teacher_response: string | null;
  created_at: string;
  responded_at: string | null;
}

export interface StudentRequestListResponse {
  items: StudentRequestItem[];
  total: number;
  pending_count: number;
}

export interface StudentWeekDay {
  date: string;
  dow_label: string;
  is_today: boolean;
  is_future: boolean;
  is_past: boolean;
  gorev_total: number;
  gorev_done: number;
  test_planned: number;
  test_completed: number;
  deneme_count: number;
  etkinlik_count: number;
  tasks: StudentTask[];
}

export interface StudentWeekResponse {
  start_date: string;
  end_date: string;
  prev_start: string;
  next_start: string;
  days: StudentWeekDay[];
  total_gorev: number;
  total_gorev_done: number;
  total_test_planned: number;
  total_test_completed: number;
  total_pct: number;
}

// Denemeler (salt-okuma; koç girer)
export interface ExamSubjectRow {
  name: string;
  correct: number;
  wrong: number;
  blank: number;
  net: number;
}
export interface ExamRow {
  id: number;
  title: string;
  exam_date: string;
  section: string;
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
export interface ExamSummary {
  count: number;
  avg_net: number;
  best_net: number;
  last_net: number | null;
  first_net: number | null;
  trend_delta: number | null;
}
export interface StudentExamsResponse {
  summary: ExamSummary;
  rows: ExamRow[];
}

export const studentKeys = {
  day: (date?: string) => ["student", "day", date ?? "today"] as const,
  week: (start?: string) => ["student", "week", start ?? "current"] as const,
  exams: () => ["student", "exams"] as const,
  requests: (filter?: string) => ["student", "requests", filter ?? "all"] as const,
};

export function getStudentExams(): Promise<StudentExamsResponse> {
  return apiRequest<StudentExamsResponse>("/api/v2/student/exams");
}

// --- Öğrenci → koç talepleri ---
export function getStudentRequests(filter?: "pending" | "answered"): Promise<StudentRequestListResponse> {
  const qs = filter ? `?status=${filter}` : "";
  return apiRequest<StudentRequestListResponse>(`/api/v2/student/requests${qs}`);
}
export function withdrawRequest(requestId: number): Promise<unknown> {
  return apiRequest(`/api/v2/student/requests/${requestId}/withdraw`, { method: "POST", body: {} });
}
export function requestQuestion(taskId: number, message: string): Promise<unknown> {
  return apiRequest(`/api/v2/student/tasks/${taskId}/requests/question`, {
    method: "POST",
    body: { message },
  });
}
export function requestChange(taskId: number, proposed_count: number, message?: string): Promise<unknown> {
  return apiRequest(`/api/v2/student/tasks/${taskId}/requests/change`, {
    method: "POST",
    body: { proposed_count, message: message || null },
  });
}
export function requestRemove(taskId: number, message?: string): Promise<unknown> {
  return apiRequest(`/api/v2/student/tasks/${taskId}/requests/remove`, {
    method: "POST",
    body: { message: message || null },
  });
}

export function getStudentDay(date?: string): Promise<StudentDayResponse> {
  const qs = date ? `?date=${encodeURIComponent(date)}` : "";
  return apiRequest<StudentDayResponse>(`/api/v2/student/day${qs}`);
}

export function getStudentWeek(start?: string): Promise<StudentWeekResponse> {
  const qs = start ? `?start=${encodeURIComponent(start)}` : "";
  return apiRequest<StudentWeekResponse>(`/api/v2/student/week${qs}`);
}

// MutationResponse — backend invalidate prefix listesi döner; mobilde basitçe
// ilgili query'leri elle invalidate ediyoruz (web applyInvalidate karşılığı sade).
export function completeTask(
  taskId: number,
  body?: { solved_count?: number; correct?: number | null; wrong?: number | null },
): Promise<unknown> {
  return apiRequest(`/api/v2/student/tasks/${taskId}/complete`, { method: "POST", body: body ?? {} });
}
export function uncompleteTask(taskId: number): Promise<unknown> {
  return apiRequest(`/api/v2/student/tasks/${taskId}/uncomplete`, { method: "POST", body: {} });
}

// Tek kalemin kısmi tamamlanması + doğru/yanlış (kitap kalemi: completed=test,
// D/Y=soru; kitapsız deneme: completed=soru, D+Y≤completed).
export function setItemCompleted(
  taskId: number,
  itemId: number,
  body: { completed: number; correct?: number | null; wrong?: number | null },
): Promise<unknown> {
  return apiRequest(`/api/v2/student/tasks/${taskId}/items/${itemId}/set-completed`, {
    method: "POST",
    body,
  });
}
