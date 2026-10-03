import { api } from "@/lib/api";

export interface PlanAssistantAction {
  type: "select_plan" | "handoff" | "open";
  label?: string | null;
  plan?: string | null;
  section?: "ai" | "cancel" | null;
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

export const planAssistantKeys = {
  state: () => ["teacher", "me", "plan", "assistant"] as const,
};

export function getPlanAssistant(): Promise<PlanAssistantState> {
  return api<PlanAssistantState>("/api/v2/teacher/plan-assistant");
}

export function askPlanAssistant(body: {
  chip?: string;
  question?: string;
  history?: PlanAssistantMessage[];
}): Promise<PlanAssistantAnswer> {
  return api<PlanAssistantAnswer>("/api/v2/teacher/plan-assistant/ask", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function handoffPlanAssistant(body: {
  message: string;
  transcript: PlanAssistantMessage[];
}): Promise<{ ok: boolean; request_id: number; message: string }> {
  return api("/api/v2/teacher/plan-assistant/handoff", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
