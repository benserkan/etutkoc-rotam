import { apiRequest } from "./api";

// ETÜTKOÇ /api/v2/parent — veli paneli (mobilde kullanılan alt küme).

export type WarningLevel = "red" | "amber" | "green";

export interface ParentChildSummary {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  is_graduate: boolean;
  display_grade_label: string | null;
  academic_year: string | null;
  exam_label: string | null;
  exam_target: string;
  relation: string | null;
  is_primary: boolean;
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
  latest_exam_title: string | null;
  latest_exam_date: string | null;
  latest_exam_net: number | null;
  latest_exam_section: string | null;
  latest_exam_count: number;
}

export interface ParentDashboardResponse {
  children: ParentChildSummary[];
}

// --- Bildirimler ---
export interface ParentNotificationItem {
  id: number;
  kind: string;
  channel: string;
  status: string;
  subject: string | null;
  student_name: string | null;
  sent_at: string | null;
  queued_at: string | null;
}
export interface ParentNotificationsResponse {
  items: ParentNotificationItem[];
  total: number;
}

// --- Çocuk haftası (read-only) ---
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
  weekday: number; // 0=Pazartesi
  tasks: ParentWeekTask[];
  task_count: number;
  planned_total: number;
  completed_total: number;
  gorev_total: number;
  gorev_done: number;
  test_planned: number;
  test_completed: number;
  deneme_count: number;
  etkinlik_count: number;
}
export interface ParentWeekResponse {
  student: { id: number; full_name: string };
  start: string;
  end: string;
  prev_start: string;
  next_start: string;
  days: ParentWeekDay[];
}

// --- Haftalık rapor (doyurucu analiz) ---
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
  planned: number;
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
  student: { id: number; full_name: string };
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

export const parentKeys = {
  dashboard: () => ["parent", "dashboard"] as const,
  child: (id: number) => ["parent", "child", id] as const,
  childWeek: (id: number, start?: string) => ["parent", "child", id, "week", start ?? "current"] as const,
  weeklyReport: (id: number, start?: string | null) =>
    ["parent", "child", id, "weekly-report", start ?? "default"] as const,
  notifications: () => ["parent", "notifications"] as const,
};

export function getParentDashboard(): Promise<ParentDashboardResponse> {
  return apiRequest<ParentDashboardResponse>("/api/v2/parent/dashboard");
}
export function getParentNotifications(): Promise<ParentNotificationsResponse> {
  return apiRequest<ParentNotificationsResponse>("/api/v2/parent/notifications");
}
export function getParentChildWeek(id: number, start?: string): Promise<ParentWeekResponse> {
  const qs = start ? `?start=${encodeURIComponent(start)}` : "";
  return apiRequest<ParentWeekResponse>(`/api/v2/parent/students/${id}/week${qs}`);
}
export function getParentWeeklyReport(id: number, weekStart?: string | null): Promise<WeeklyReportResponse> {
  const qs = weekStart ? `?week_start=${encodeURIComponent(weekStart)}` : "";
  return apiRequest<WeeklyReportResponse>(`/api/v2/parent/students/${id}/weekly-report${qs}`);
}
