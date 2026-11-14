// "Bugünün mesajları" — WhatsApp mesaj önerileri (2026-11-14)

import { api } from "@/lib/api";

export type SuggestionAudience = "parent" | "student" | "coach";

export interface SuggestionTarget {
  user_id: number;
  full_name: string;
  relation_label: string;
  phone_masked: string | null;
  can_message: boolean;
}

export interface SuggestionItem {
  group_id: number;
  group_name: string;
  student_id: number;
  student_name: string;
  key: string;
  audience: SuggestionAudience;
  kind: "problem" | "positive" | "reminder" | "report" | string;
  kind_label: string;
  title: string;
  reason: string;
  text: string;
  has_report: boolean;
  targets: SuggestionTarget[];
}

export interface SuggestionsResponse {
  sent_today: number;
  items: SuggestionItem[];
  students_checked: number;
}

export const messageSuggestionKeys = {
  list: (studentId: number | null) =>
    ["teacher", "me", "message-suggestions", studentId ?? "all"] as const,
  all: ["teacher", "me", "message-suggestions"] as const,
};

export function getMessageSuggestions(studentId: number | null): Promise<SuggestionsResponse> {
  const q = studentId ? `?student_id=${studentId}` : "";
  return api<SuggestionsResponse>(`/api/v2/teacher/message-suggestions${q}`);
}

export function sendMessageSuggestion(body: {
  student_id: number;
  audience: SuggestionAudience;
  key: string;
  text: string;
  target_user_id: number | null;
}): Promise<{ wa_url: string; target_name: string | null; sent_today: number }> {
  return api(`/api/v2/teacher/message-suggestions/send`, { method: "POST", body: JSON.stringify(body) });
}

export function skipMessageSuggestion(body: {
  student_id: number;
  audience: SuggestionAudience;
  key: string;
}): Promise<{ ok: boolean }> {
  return api(`/api/v2/teacher/message-suggestions/skip`, { method: "POST", body: JSON.stringify(body) });
}

// ---- Kurum yöneticisi → koç ("Koçlara mesajlar")
export const instMessageSuggestionKeys = {
  all: ["institution", "me", "message-suggestions"] as const,
};

export function getInstMessageSuggestions(): Promise<SuggestionsResponse> {
  return api<SuggestionsResponse>(`/api/v2/institution/message-suggestions`);
}

export function sendInstMessageSuggestion(body: {
  coach_id: number;
  key: string;
  text: string;
}): Promise<{ wa_url: string; target_name: string | null; sent_today: number }> {
  return api(`/api/v2/institution/message-suggestions/send`, { method: "POST", body: JSON.stringify(body) });
}

export function skipInstMessageSuggestion(body: { coach_id: number; key: string }): Promise<{ ok: boolean }> {
  return api(`/api/v2/institution/message-suggestions/skip`, { method: "POST", body: JSON.stringify(body) });
}
