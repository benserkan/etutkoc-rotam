import { apiRequest } from "./api";

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
