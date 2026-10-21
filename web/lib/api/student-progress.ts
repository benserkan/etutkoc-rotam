/**
 * Öğrenci "Gelişim" sayfası (2026-10-21) — koçun öğrenci detayındaki göstergelerle AYNI hesap.
 * Backend: GET /student/analytics · GET /student/weekly-progress (app/routes/api_v2/student_progress.py).
 */
import { api } from "@/lib/api";
import type { TeacherStudentAnalyticsResponse } from "@/lib/types/teacher";
import type { WeeklyProgressResponse } from "@/lib/api/weekly-progress";

export const studentProgressKeys = {
  analytics: () => ["student", "me", "analytics"] as const,
  weekly: () => ["student", "me", "weekly-progress"] as const,
};

export function getStudentAnalytics(): Promise<TeacherStudentAnalyticsResponse> {
  return api<TeacherStudentAnalyticsResponse>("/api/v2/student/analytics");
}

export function getStudentWeeklyProgress(): Promise<WeeklyProgressResponse> {
  return api<WeeklyProgressResponse>("/api/v2/student/weekly-progress");
}
