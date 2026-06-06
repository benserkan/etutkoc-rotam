/**
 * /api/v2/parent/* — Veli paneli fetcher'ları (Dalga 5).
 *
 * QueryKey sözleşmesi: backend `MutationResponse.invalidate` listesindeki
 * "parent:me" prefix'i ile birebir uyumlu (applyInvalidate ile yeniden bayatlanır).
 *
 * GİZLİLİK: Tüm `students/{id}` fetcher'ları KVKK guard'lı — bağ yoksa
 * backend 404 döner (403 değil — "var ama yetkin yok" sızıntısı önlenir).
 */
import { api } from "@/lib/api";
import type {
  ParentDashboardResponse,
  ParentInvitationInfo,
  ParentNotificationsResponse,
  ParentSessionsResponse,
  ParentSettingsResponse,
  ParentStudentOverviewResponse,
  ParentUnsubscribeResult,
  ParentWeekResponse,
  WeeklyReportResponse,
} from "@/lib/types/parent";

// =============================================================================
// QueryKey üreticileri
// =============================================================================

export const parentKeys = {
  root: () => ["parent", "me"] as const,
  dashboard: () => ["parent", "me", "dashboard"] as const,
  student: (id: number) =>
    ["parent", "me", "students", String(id)] as const,
  studentWeek: (id: number, start: string | null) =>
    [
      "parent",
      "me",
      "students",
      String(id),
      "week",
      start ?? "",
    ] as const,
  weeklyReport: (id: number, weekStart: string | null) =>
    [
      "parent",
      "me",
      "students",
      String(id),
      "weekly-report",
      weekStart ?? "",
    ] as const,
  studentSessions: (id: number, months: number) =>
    [
      "parent",
      "me",
      "students",
      String(id),
      "sessions",
      months,
    ] as const,
  notifications: () => ["parent", "me", "notifications"] as const,
  settings: () => ["parent", "me", "settings"] as const,
  // Public — invitation token + unsubscribe token (auth gerekmez)
  invitation: (token: string) =>
    ["parent", "invitation", token] as const,
};

// =============================================================================
// GET fetcher'ları (login-gerekli)
// =============================================================================

export function getParentDashboard() {
  return api<ParentDashboardResponse>("/api/v2/parent/dashboard");
}

export function getParentStudentOverview(studentId: number) {
  return api<ParentStudentOverviewResponse>(
    `/api/v2/parent/students/${studentId}`,
  );
}

export function getParentStudentWeek(
  studentId: number,
  start: string | null = null,
) {
  const qs = start ? `?start=${encodeURIComponent(start)}` : "";
  return api<ParentWeekResponse>(
    `/api/v2/parent/students/${studentId}/week${qs}`,
  );
}

export function getParentWeeklyReport(
  studentId: number,
  weekStart: string | null = null,
) {
  const qs = weekStart
    ? `?week_start=${encodeURIComponent(weekStart)}`
    : "";
  return api<WeeklyReportResponse>(
    `/api/v2/parent/students/${studentId}/weekly-report${qs}`,
  );
}

export function getParentStudentSessions(
  studentId: number,
  months: number = 12,
) {
  return api<ParentSessionsResponse>(
    `/api/v2/parent/students/${studentId}/sessions?months=${months}`,
  );
}

export function getParentNotifications() {
  return api<ParentNotificationsResponse>("/api/v2/parent/notifications");
}

export function getParentSettings() {
  return api<ParentSettingsResponse>("/api/v2/parent/settings");
}

// =============================================================================
// Public — invitation / unsubscribe
// =============================================================================

export function getParentInvitation(token: string) {
  return api<ParentInvitationInfo>(
    `/api/v2/parent/invitation/${encodeURIComponent(token)}`,
  );
}

export function getParentUnsubscribe(token: string) {
  return api<ParentUnsubscribeResult>(
    `/api/v2/parent/unsubscribe/${encodeURIComponent(token)}`,
  );
}

// ---- P2: Veli deneme geçmişi + AI içgörü ----
import type { StudentExamListResponse } from "@/lib/types/teacher";

export interface ParentInsightData {
  summary: string;
  strengths: string[];
  focus_areas: string[];
  parent_tips: string[];
  based_on_exams: number;
  based_on_solved: number;
  generated_at: string;
}
export interface ParentInsightResponse {
  insight: ParentInsightData | null;
  is_stale: boolean;
  ai_available: boolean;
  unavailable_reason: string | null;
}

export const parentP2Keys = {
  exams: (id: number) => ["parent", "me", "students", String(id), "exams"] as const,
  insight: (id: number) => ["parent", "me", "students", String(id), "insight"] as const,
};

export function getParentExams(studentId: number) {
  return api<StudentExamListResponse>(`/api/v2/parent/students/${studentId}/exams`);
}
export function getParentInsight(studentId: number) {
  return api<ParentInsightResponse>(`/api/v2/parent/students/${studentId}/insight`);
}
export function generateParentInsight(studentId: number) {
  return api<ParentInsightResponse>(`/api/v2/parent/students/${studentId}/insight`, {
    method: "POST",
  });
}
