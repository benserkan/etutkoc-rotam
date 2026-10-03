import { Platform } from "react-native";

import { API_BASE, apiRequest } from "@/lib/api";
import { mobilePathToCatalogPath } from "@/lib/quick-access";
import { storageGet, storageSet } from "@/lib/storage";

/**
 * Rota — sitenin ve uygulamanın TEK asistanı (2026-10-03; web site-assistant paritesi).
 * Aynı backend (/api/v2/assistant). Kanal ios/android → sunucu kart/web
 * ödemesinden ve fiyattan söz etmez (App Store 3.1.1).
 */

export const assistantChannel = Platform.OS === "ios" ? "ios" : "android";
export const ROTA_AVATAR = `${API_BASE}/static/guide/rota-avatar.png`;

export interface AssistantAction {
  type: "link" | "handoff" | "select_plan" | "open";
  label?: string | null;
  href?: string | null;
  plan?: string | null;
  section?: string | null;
}
export interface AssistantState {
  audience: string;
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
  source: string;
  ai_left: number;
}

const KEY_STORE = "etk_assistant_key";
let keyCache: string | null = null;

export async function getSessionKey(): Promise<string> {
  if (keyCache) return keyCache;
  try {
    let k = await storageGet(KEY_STORE);
    if (!k || !/^[A-Za-z0-9_-]{8,64}$/.test(k)) {
      const abc = "abcdefghijklmnopqrstuvwxyz0123456789";
      k = "m" + Array.from({ length: 31 }, () => abc[Math.floor(Math.random() * abc.length)]).join("");
      await storageSet(KEY_STORE, k);
    }
    keyCache = k;
  } catch {
    keyCache = "m" + Math.random().toString(36).slice(2, 20);
  }
  return keyCache;
}

export const assistantKeys = {
  state: (page: string) => ["assistant", assistantChannel, page] as const,
};

export async function getAssistantState(page: string): Promise<AssistantState> {
  const key = await getSessionKey();
  const q = `page=${encodeURIComponent(page)}&session_key=${key}&channel=${assistantChannel}`;
  return apiRequest<AssistantState>(`/api/v2/assistant?${q}`);
}

export async function askAssistant(body: {
  page: string;
  chip?: string;
  label?: string;
  question?: string;
  history: AssistantMessage[];
}): Promise<AssistantAnswer> {
  const key = await getSessionKey();
  return apiRequest<AssistantAnswer>("/api/v2/assistant/ask", {
    method: "POST",
    body: { ...body, session_key: key, channel: assistantChannel },
  });
}

export async function handoffAssistant(body: {
  page: string;
  message: string;
  transcript: AssistantMessage[];
  name?: string;
  phone?: string;
  email?: string;
}): Promise<{ ok: boolean; message: string; whatsapp_url: string }> {
  const key = await getSessionKey();
  return apiRequest("/api/v2/assistant/handoff", { method: "POST", body: { ...body, session_key: key } });
}

/** Ekran → sorunun sorulduğu sayfa (web yolu; sunucu buna göre hazır soru seçer). */
export function pageForScreen(pathname: string, params: Record<string, string | string[] | undefined>): string {
  const direct = mobilePathToCatalogPath(pathname, params);
  if (direct) return direct;
  const map: Record<string, string> = {
    "/welcome": "/",
    "/login": "/login",
    "/signup": "/signup/teacher",
    "/teacher-plan": "/teacher/plan",
    "/teacher-appointments": "/teacher/appointments",
    "/teacher/profile": "/me/account",
    "/student/exams": "/student/exams",
    "/student-wrong-questions": "/student/wrong-questions",
    "/student-surveys": "/student/surveys",
    "/student-appointments": "/student/appointments",
    "/student/profile": "/me/account",
    "/parent/dashboard": "/parent",
    "/parent/profile": "/parent/settings",
    "/institution/dashboard": "/institution",
    "/institution/analiz": "/institution",
    "/institution/profile": "/me/account",
  };
  return map[pathname] ?? pathname;
}

/** Bilgi tabanındaki web bağlantısı → uygulama ekranı (karşılığı yoksa null; düğme çıkmaz). */
export function mobileHrefFor(href: string): string | null {
  const path = href.split("?")[0];
  const map: Record<string, string> = {
    "/signup/teacher": "/signup",
    "/student/day": "/student/today",
    "/student/week": "/student/week",
    "/student/books": "/student-books",
    "/student/wrong-questions": "/student-wrong-questions",
    "/student/exams": "/student/exams",
    "/student/topics": "/topic-performance?source=student",
    "/student/review": "/student-review",
    "/student/surveys": "/student-surveys",
    "/student/appointments": "/student-appointments",
    "/student/requests": "/student/requests",
    "/student/guide": "/guide",
    "/parent": "/parent/dashboard",
    "/parent/support": "/parent/support",
    "/parent/settings": "/parent/profile",
    "/parent/guide": "/guide",
    "/teacher/students": "/teacher/students",
    "/teacher/dashboard": "/teacher/students",
    "/teacher/billing": "/teacher/billing",
    "/teacher/requests": "/teacher/requests",
    "/teacher/support": "/teacher/support",
    "/teacher/appointments": "/teacher-appointments",
    "/teacher/plan": "/teacher-plan",
    "/teacher/guide": "/guide",
    "/institution": "/institution/dashboard",
    "/institution/action-center": "/institution/action-center",
    "/institution/support-inbox": "/institution/support",
    "/institution/invitations": "/institution-invitations",
  };
  return map[path] ?? null;
}
