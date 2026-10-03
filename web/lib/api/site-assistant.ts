import { api } from "@/lib/api";

/** Site asistanı "Rota" (2026-10-03) — sitenin her yerinde tek asistan. */

export interface AssistantAction {
  type: "link" | "handoff" | "select_plan" | "open";
  label?: string | null;
  href?: string | null;
  plan?: string | null;
  section?: "ai" | "cancel" | null;
}

export interface AssistantState {
  audience: "public" | "teacher" | "student" | "parent" | "institution_admin" | "super_admin";
  greeting: string;
  chips: { id: string; label: string }[];
  ai_left: number;
  whatsapp: string;
  logged_in: boolean;
  user_name: string | null;
}

export interface AssistantMessage {
  role: "user" | "assistant";
  text: string;
}

export interface AssistantAnswer {
  answer: string;
  action: AssistantAction | null;
  source: "rule" | "ai" | "fallback" | "limit";
  ai_left: number;
}

export interface AssistantHandoffResult {
  ok: boolean;
  message: string;
  whatsapp_url: string;
}

export const assistantKeys = {
  state: (page: string) => ["assistant", "state", page] as const,
  admin: (days: number, audience: string, onlyHandoff: boolean) =>
    ["admin", "assistant", days, audience, onlyHandoff] as const,
};

export function getAssistantState(page: string, sessionKey: string): Promise<AssistantState> {
  const q = new URLSearchParams({ page, session_key: sessionKey });
  return api<AssistantState>(`/api/v2/assistant?${q.toString()}`);
}

export function askAssistant(body: {
  session_key: string;
  page: string;
  chip?: string;
  label?: string;
  question?: string;
  history?: AssistantMessage[];
}): Promise<AssistantAnswer> {
  return api<AssistantAnswer>("/api/v2/assistant/ask", { method: "POST", body: JSON.stringify(body) });
}

export function handoffAssistant(body: {
  session_key: string;
  page: string;
  message: string;
  transcript: AssistantMessage[];
  name?: string;
  phone?: string;
  email?: string;
  website?: string;
}): Promise<AssistantHandoffResult> {
  return api<AssistantHandoffResult>("/api/v2/assistant/handoff", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface AdminAssistantRow {
  id: number;
  created_at: string;
  audience: string;
  audience_label: string;
  page: string | null;
  question: string;
  answer: string | null;
  source: string;
  handoff: boolean;
  user_id: number | null;
  user_name: string | null;
}

export interface AdminAssistantResponse {
  days: number;
  total: number;
  ai_count: number;
  handoff_count: number;
  by_audience: Record<string, number>;
  top_questions: { question: string; count: number }[];
  items: AdminAssistantRow[];
}

export function getAdminAssistant(days: number, audience: string, onlyHandoff: boolean) {
  const q = new URLSearchParams({ days: String(days) });
  if (audience) q.set("audience", audience);
  if (onlyHandoff) q.set("only_handoff", "true");
  return api<AdminAssistantResponse>(`/api/v2/admin/assistant/messages?${q.toString()}`);
}

// --- Sayfalar arası köprü (ör. Paketim sayfasındaki "Asistana sor" düğmesi)
export const ROTA_OPEN = "rota:open";
export const ROTA_SELECT_PLAN = "rota:select-plan";
export const ROTA_OPEN_SECTION = "rota:open-section";

/** Asistanı aç; soru verilirse sorar. chip verilirse yapay zekâsız hazır cevap. */
export function openRotaAssistant(question?: string, chip?: string) {
  window.dispatchEvent(new CustomEvent(ROTA_OPEN, { detail: { question, chip } }));
}
