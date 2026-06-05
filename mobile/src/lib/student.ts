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
}

export const studentKeys = {
  day: (date?: string) => ["student", "day", date ?? "today"] as const,
  week: (start?: string) => ["student", "week", start ?? "current"] as const,
};

export function getStudentDay(date?: string): Promise<StudentDayResponse> {
  const qs = date ? `?date=${encodeURIComponent(date)}` : "";
  return apiRequest<StudentDayResponse>(`/api/v2/student/day${qs}`);
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
