/**
 * Öğretmen AI içgörü + tanılama + öneri panel GET sarmalayıcıları (Paket 9).
 *
 * QueryKey sözleşmesi backend `invalidate` listesindeki
 *   "teacher:{id}:insights:overview"
 *   "teacher:{id}:insights:student:{student_id}"
 * ile birebir prefix uyumlu.
 */
import { api } from "@/lib/api";
import type {
  FleetInsightsResponse,
  StudentDiagnosticsResponse,
  StudentSuggestionsAheadResponse,
  StudentSuggestionsPanelResponse,
} from "@/lib/types/insights";

export const insightsKeys = {
  overview: () => ["teacher", "me", "insights", "overview"] as const,
  student: (studentId: number) =>
    ["teacher", "me", "insights", "student", String(studentId)] as const,
  studentDiagnostics: (studentId: number) =>
    [
      "teacher",
      "me",
      "insights",
      "student",
      String(studentId),
      "diagnostics",
    ] as const,
  studentSuggestionsAhead: (studentId: number) =>
    [
      "teacher",
      "me",
      "insights",
      "student",
      String(studentId),
      "ahead",
    ] as const,
  studentSuggestionsForDay: (studentId: number, date: string) =>
    [
      "teacher",
      "me",
      "insights",
      "student",
      String(studentId),
      "day",
      date,
    ] as const,
} as const;

export function getInsightsOverview(): Promise<FleetInsightsResponse> {
  return api<FleetInsightsResponse>("/api/v2/teacher/insights/overview");
}

export function getStudentDiagnostics(
  studentId: number,
): Promise<StudentDiagnosticsResponse> {
  return api<StudentDiagnosticsResponse>(
    `/api/v2/teacher/insights/students/${encodeURIComponent(String(studentId))}/diagnostics`,
  );
}

export function getStudentSuggestionsAhead(
  studentId: number,
): Promise<StudentSuggestionsAheadResponse> {
  return api<StudentSuggestionsAheadResponse>(
    `/api/v2/teacher/insights/students/${encodeURIComponent(String(studentId))}/suggestions/ahead`,
  );
}

export function getStudentSuggestionsForDay(
  studentId: number,
  date: string,
): Promise<StudentSuggestionsPanelResponse> {
  const qs = new URLSearchParams({ date });
  return api<StudentSuggestionsPanelResponse>(
    `/api/v2/teacher/insights/students/${encodeURIComponent(String(studentId))}/suggestions?${qs.toString()}`,
  );
}
