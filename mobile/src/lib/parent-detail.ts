import { apiRequest } from "./api";
import type { WarningLevel } from "./parent";

export interface ParentStudentInfo {
  id: number;
  full_name: string;
  grade_level: number | null;
  is_graduate: boolean;
  display_grade_label: string | null;
  academic_year: string | null;
  exam_date: string | null;
  exam_label: string | null;
  exam_target: string;
}
export interface ParentTodayInfo {
  planned: number;
  completed: number;
  gorev_total: number;
  gorev_done: number;
}
export interface ParentWeekInfo {
  planned: number;
  completed: number;
  rate: number | null;
  gorev_total: number;
  gorev_done: number;
  gorev_rate: number | null;
  test_planned: number;
  test_completed: number;
}
export interface ParentSubjectItem {
  subject_id: number | null;
  name: string;
  percent_done: number;
}
export interface ParentProjectionInfo {
  total_tests: number;
  completed_tests: number;
  remaining_tests: number;
  rate_per_day: number | null;
  days_left_to_exam: number | null;
  expected_completed_by_exam: number;
  gap: number;
  status: WarningLevel;
}
export interface ParentTeacherNoteItem {
  id: number;
  body: string;
  teacher_name: string | null;
  created_at: string | null;
  delivered_at: string | null;
}
export interface ParentStudentOverview {
  student: ParentStudentInfo;
  today: ParentTodayInfo;
  week: ParentWeekInfo;
  rate_7d_pct: number | null;
  rate_30d_pct: number | null;
  consistency_7d_pct: number | null;
  warning_level: WarningLevel;
  subjects: ParentSubjectItem[];
  projection: ParentProjectionInfo;
  teacher_notes: ParentTeacherNoteItem[];
}

export function getParentChild(id: number): Promise<ParentStudentOverview> {
  return apiRequest<ParentStudentOverview>(`/api/v2/parent/students/${id}`);
}
