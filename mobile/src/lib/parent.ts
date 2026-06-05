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

export const parentKeys = {
  dashboard: () => ["parent", "dashboard"] as const,
  child: (id: number) => ["parent", "child", id] as const,
  childWeek: (id: number, start?: string) => ["parent", "child", id, "week", start ?? "current"] as const,
  notifications: () => ["parent", "notifications"] as const,
};

export function getParentDashboard(): Promise<ParentDashboardResponse> {
  return apiRequest<ParentDashboardResponse>("/api/v2/parent/dashboard");
}
