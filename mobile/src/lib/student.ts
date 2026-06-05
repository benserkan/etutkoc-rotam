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

// --- Kitap + bölüm seçici (kaynak değiştir / yeni görev iste) ---
export interface PickBook {
  book_id: number;
  book_name: string;
  book_type: string;
  remaining_tests: number;
}
export interface PickSubjectGroup {
  subject_id: number;
  subject_name: string;
  books: PickBook[];
}
export interface StudentBooksResponse {
  subjects: PickSubjectGroup[];
}
export interface BookSectionOption {
  id: number;
  label: string;
  topic_name: string | null;
  remaining: number;
  total: number;
}
export interface BookSectionsResponse {
  book_id: number;
  is_deneme: boolean;
  items: BookSectionOption[];
}

export function getStudentBooks(): Promise<StudentBooksResponse> {
  return apiRequest<StudentBooksResponse>("/api/v2/student/books");
}
export function getBookSections(bookId: number): Promise<BookSectionsResponse> {
  return apiRequest<BookSectionsResponse>(`/api/v2/student/book-sections?book_id=${bookId}`);
}
export function requestReplace(
  taskId: number,
  body: { new_book_id: number; new_section_id: number; new_count: number; message?: string },
): Promise<unknown> {
  return apiRequest(`/api/v2/student/tasks/${taskId}/requests/replace`, {
    method: "POST",
    body: { ...body, message: body.message || null },
  });
}
export function requestAdd(
  dayIso: string,
  body: { book_id: number; section_id: number; proposed_count: number; message?: string },
): Promise<unknown> {
  return apiRequest(`/api/v2/student/days/${dayIso}/requests/add`, {
    method: "POST",
    body: { ...body, message: body.message || null },
  });
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

// ====== Günün notu (autosave) ======
export function saveDayNote(date: string, body: string): Promise<unknown> {
  return apiRequest(`/api/v2/student/day-note`, { method: "PUT", body: { date, body } });
}

// ====== Kitaplarım (ilerleme) ======
export type BookType = "soru_bankasi" | "konu_anlatim" | "deneme" | "diger" | string;
export interface ResourceBookItem {
  student_book_id: number;
  book_id: number;
  book_name: string;
  book_type: BookType;
  total_tests: number;
  reserved_tests: number;
  completed_tests: number;
  remaining_tests: number;
}
export interface ResourceSubjectGroup {
  subject_id: number;
  subject_name: string;
  total_tests: number;
  reserved_tests: number;
  completed_tests: number;
  remaining_tests: number;
  books: ResourceBookItem[];
}
export interface StudentBooksProgress {
  total_tests: number;
  reserved_tests: number;
  completed_tests: number;
  remaining_tests: number;
  subjects: ResourceSubjectGroup[];
}
export function getStudentBooksProgress(): Promise<StudentBooksProgress> {
  return apiRequest<StudentBooksProgress>("/api/v2/student/books");
}

// ====== Çalışma DNA ======
export type DnaChronotype = "morning" | "afternoon" | "evening" | "night" | "unknown";
export interface DnaResponse {
  window_days: number;
  has_enough_data: boolean;
  gorev_total: number;
  gorev_done: number;
  test_planned: number;
  test_completed: number;
  completion_rate: number;
  chronotype: DnaChronotype;
  peak_hour: number | null;
  peak_day_idx: number | null;
  peak_day_name: string | null;
  heatmap: number[][]; // 7×24
  morning_count: number;
  afternoon_count: number;
  evening_count: number;
  night_count: number;
  weekend_count: number;
  weekday_count: number;
}
export function getStudentDna(): Promise<DnaResponse> {
  return apiRequest<DnaResponse>("/api/v2/student/dna");
}

// ====== Odak (Pomodoro) ======
export interface FocusSession {
  id: number;
  kind: string;
  planned_minutes: number;
  actual_minutes: number;
  interrupted: boolean;
  label: string | null;
  is_active: boolean;
  elapsed_seconds: number;
}
export interface FocusTodaySummary {
  work_sessions: number;
  work_minutes: number;
  break_minutes: number;
  total_minutes: number;
  interrupted_count: number;
}
export interface FocusResponse {
  active_session: FocusSession | null;
  today: FocusTodaySummary;
  recent_sessions: FocusSession[];
  streak_days: number;
  points: number;
}
export function getStudentFocus(): Promise<FocusResponse> {
  return apiRequest<FocusResponse>("/api/v2/student/focus");
}

// ====== Tekrar (aralıklı tekrar / FSRS) ======
export interface ReviewBreakdown {
  new: number;
  learning: number;
  review: number;
  relearning: number;
  due_now: number;
  total: number;
}
export interface ReviewCardItem {
  id: number;
  topic_id: number;
  topic_name: string;
  subject_name: string | null;
  state: string;
  review_count: number;
}
export interface ReviewResponse {
  due_cards: ReviewCardItem[];
  breakdown: ReviewBreakdown;
}
export function getStudentReview(): Promise<ReviewResponse> {
  return apiRequest<ReviewResponse>("/api/v2/student/review");
}

// ====== Hedefler ======
export interface GoalItem {
  id: number;
  kind: string;
  status: string;
  title: string;
  description: string | null;
  target_value: number | null;
  current_value: number | null;
  unit: string | null;
  target_date: string | null;
  is_auto_generated: boolean;
  progress_pct: number | null;
}
export interface GoalSummary {
  total: number;
  active: number;
  achieved: number;
  abandoned: number;
  overall_pct: number | null;
  next_target_date: string | null;
}
export interface GoalListResponse {
  items: GoalItem[];
  summary: GoalSummary;
}
export function getStudentGoals(): Promise<GoalListResponse> {
  return apiRequest<GoalListResponse>("/api/v2/student/goals");
}

export const studentDevKeys = {
  books: ["student", "books"] as const,
  dna: ["student", "dna"] as const,
  focus: ["student", "focus"] as const,
  review: ["student", "review"] as const,
  goals: ["student", "goals"] as const,
};
