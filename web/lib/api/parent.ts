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
  commentary: (id: number, kind: string) =>
    ["parent", "me", "students", String(id), "commentary", kind] as const,
};

// ---- Rota Veli Asistanı P1 — yorumlayıcı (program | deneme) + seslendirme ----
export type CommentaryKind = "program" | "deneme";

export interface CommentarySection {
  title: string;
  body: string;
}
export interface ParentCommentaryData {
  kind: CommentaryKind;
  kind_label: string;
  sections: CommentarySection[];
  generated_at: string;
  has_audio: boolean;
  audio_content_type: string | null;
}
export interface ParentCommentaryResponse {
  commentary: ParentCommentaryData | null;
  is_stale: boolean;
  ai_available: boolean;
  unavailable_reason: string | null;
  daily_left: number;
}
export interface CommentaryVoiceResult {
  has_audio: boolean;
  audio_content_type: string | null;
  charged: boolean;
}

export function getParentCommentary(studentId: number, kind: CommentaryKind) {
  return api<ParentCommentaryResponse>(
    `/api/v2/parent/students/${studentId}/commentary?kind=${kind}`,
  );
}
export function generateParentCommentary(studentId: number, kind: CommentaryKind) {
  return api<ParentCommentaryResponse>(
    `/api/v2/parent/students/${studentId}/commentary`,
    { method: "POST", body: JSON.stringify({ kind }) },
  );
}
export function generateParentCommentaryVoice(studentId: number, kind: CommentaryKind) {
  return api<CommentaryVoiceResult>(
    `/api/v2/parent/students/${studentId}/commentary/voice`,
    { method: "POST", body: JSON.stringify({ kind }) },
  );
}
/** Ses akış URL'i — generated_at cache-bust parametresi olarak eklenir. */
export function parentCommentaryAudioUrl(
  studentId: number, kind: CommentaryKind, bust: string,
) {
  return `/api/v2/parent/students/${studentId}/commentary/audio?kind=${kind}&v=${encodeURIComponent(bust)}`;
}

// ---- Rota Veli Asistanı P2 — yazılı sohbet ----
export interface ChatMessage {
  id: number;
  role: "veli" | "rota";
  body: string;
  created_at: string;
  /** P3: bu Rota cevabı için ses önbelleği hazır mı (tekrar dinleme kredisiz) */
  has_audio: boolean;
}
export interface ChatChip {
  id: string;
  label: string;
  action: "ask" | "commentary";
  payload: string;
}
export interface ChatGreeting {
  text: string;
  chips: ChatChip[];
}
export interface ParentChatResponse {
  messages: ChatMessage[];
  greeting: ChatGreeting;
  ai_available: boolean;
  unavailable_reason: string | null;
  daily_left: number;
}
export interface ChatAskResult {
  messages: ChatMessage[];
  daily_left: number;
}

export const parentChatKeys = {
  thread: (id: number) => ["parent", "me", "students", String(id), "chat"] as const,
};

export function getParentChat(studentId: number) {
  return api<ParentChatResponse>(`/api/v2/parent/students/${studentId}/chat`);
}
export function askParentChat(studentId: number, message: string) {
  return api<ChatAskResult>(`/api/v2/parent/students/${studentId}/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

// ---- P3: sohbete ses (sesli soru STT + cevap balonu TTS) ----
export interface ChatTranscribeResult {
  text: string;
  stt_daily_left: number;
}
/** Sesli soru → metin; sonuç input kutusuna dolar, otomatik GÖNDERİLMEZ. */
export function transcribeParentChat(
  studentId: number, audioBase64: string, mediaType: string,
) {
  return api<ChatTranscribeResult>(
    `/api/v2/parent/students/${studentId}/chat/transcribe`,
    {
      method: "POST",
      body: JSON.stringify({ audio_base64: audioBase64, media_type: mediaType }),
    },
  );
}
/** Rota cevabının sesi — ilk istekte üretilir (kredi), sonrası önbellekten. */
export function parentChatMessageVoice(studentId: number, messageId: number) {
  return api<CommentaryVoiceResult>(
    `/api/v2/parent/students/${studentId}/chat/${messageId}/voice`,
    { method: "POST" },
  );
}
/** Mesaj immutable → ses bayatlamaz; cache-bust gerekmez. */
export function parentChatAudioUrl(studentId: number, messageId: number) {
  return `/api/v2/parent/students/${studentId}/chat/${messageId}/audio`;
}

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

// ---- P3: Veli → koç talebi (çift yönlü; SupportRequest) ----
export interface ParentCoachRequestBody {
  category: string; // exam_comment | progress_question | other
  subject: string;
  body: string;
}
export function createParentCoachRequest(studentId: number, body: ParentCoachRequestBody) {
  return api<{ data: { id: number }; invalidate: string[] }>(
    `/api/v2/parent/students/${studentId}/coach-request`,
    { method: "POST", body: JSON.stringify(body) },
  );
}
