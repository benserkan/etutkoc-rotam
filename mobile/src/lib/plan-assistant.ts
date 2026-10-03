import { Platform } from "react-native";

import { apiRequest } from "@/lib/api";

/** Paket asistanı — web ile aynı uçlar; kanal = ios | android (web ödemesinden söz edilmez). */
export interface PlanAssistantAction {
  type: "select_plan" | "handoff" | "open";
  label?: string | null;
  plan?: string | null;
  section?: string | null;
}
export interface PlanAssistantState {
  greeting: string;
  chips: { id: string; label: string }[];
  daily_left: number;
  suggested_plan: string | null;
}
export interface PlanAssistantMessage {
  role: "user" | "assistant";
  text: string;
}
export interface PlanAssistantAnswer {
  answer: string;
  action: PlanAssistantAction | null;
  source: "rule" | "ai" | "fallback";
  daily_left: number;
}

export const planChannel = Platform.OS === "ios" ? "ios" : "android";
export const planAssistantKeys = { state: ["teacher", "plan", "assistant", planChannel] as const };

export function getPlanAssistant(): Promise<PlanAssistantState> {
  return apiRequest<PlanAssistantState>(`/api/v2/teacher/plan-assistant?channel=${planChannel}`);
}
export function askPlanAssistant(body: {
  chip?: string;
  question?: string;
  history?: PlanAssistantMessage[];
}): Promise<PlanAssistantAnswer> {
  return apiRequest<PlanAssistantAnswer>(`/api/v2/teacher/plan-assistant/ask`, {
    method: "POST",
    body: { ...body, channel: planChannel },
  });
}
export function handoffPlanAssistant(body: {
  message: string;
  transcript: PlanAssistantMessage[];
}): Promise<{ ok: boolean; request_id: number; message: string }> {
  return apiRequest(`/api/v2/teacher/plan-assistant/handoff`, { method: "POST", body });
}
