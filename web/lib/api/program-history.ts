import { api } from "@/lib/api";
import type { PoolHistoryRow } from "@/lib/api/pool";

/** Program geçmişi: gün gün haftalar + havuz dönemleri + mod geçişleri (yeni → eski). */
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

export interface HistorySwitch {
  date: string;
  from_label: string;
  to_label: string;
  to_mode: string;
  note: string | null;
}

export interface HistoryEntry {
  kind: "week" | "period" | "switch";
  week: HistoryWeek | null;
  period: PoolHistoryRow | null;
  period_current: boolean;
  switch: HistorySwitch | null;
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
  teacher: (studentId: number) => ["teacher", "me", "students", String(studentId), "program-history"] as const,
  student: () => ["student", "program-history"] as const,
};

export function getTeacherProgramHistory(studentId: number): Promise<ProgramHistoryResponse> {
  return api<ProgramHistoryResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/program-history`,
  );
}

export function getStudentProgramHistory(): Promise<ProgramHistoryResponse> {
  return api<ProgramHistoryResponse>("/api/v2/student/program-history");
}
