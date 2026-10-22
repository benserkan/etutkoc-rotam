import { apiRequest } from "./api";

/** Program geçmişi (web ile aynı sözleşme): gün gün haftalar + havuz dönemleri + mod geçişleri. */
export interface HistoryWeek {
  start: string;
  end: string;
  week_kind: "program" | "takvim";
  program_id: number | null;
  cut: boolean;
  current: boolean;
  gorev_total: number;
  gorev_done: number;
  test_planned: number;
  test_completed: number;
  deneme_units: number;
  deneme_done: number;
  pct: number;
  days_with_tasks: number;
}

export interface HistoryPeriod {
  id: number;
  opened_on: string;
  closed_on: string | null;
  expected_next_on: string | null;
  status: string;
  status_label: string;
  total_units: number;
  done_units: number;
  pct: number;
  items_total: number;
  items_done: number;
  subjects: { subject: string; total: number; done: number; pct: number }[];
}

export interface HistoryEntry {
  kind: "week" | "period" | "switch";
  week: HistoryWeek | null;
  period: HistoryPeriod | null;
  period_current: boolean;
  switch: { date: string; from_label: string; to_label: string; to_mode: string; note: string | null } | null;
}

export interface ProgramHistoryResponse {
  student_id: number;
  program_mode: string;
  program_mode_label: string;
  entries: HistoryEntry[];
  weeks_count: number;
  periods_count: number;
}

export const programHistoryKeys = {
  teacher: (studentId: number) => ["teacher", "student", studentId, "program-history"] as const,
  student: () => ["student", "program-history"] as const,
};

export function getTeacherProgramHistory(studentId: number): Promise<ProgramHistoryResponse> {
  return apiRequest<ProgramHistoryResponse>(`/api/v2/teacher/students/${studentId}/program-history`);
}

export function getStudentProgramHistory(): Promise<ProgramHistoryResponse> {
  return apiRequest<ProgramHistoryResponse>("/api/v2/student/program-history");
}
