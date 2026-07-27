import { API_BASE, apiRequest } from "@/lib/api";

import rawCoach from "@/assets/guide/coach-guide-content.json";
import rawStudent from "@/assets/guide/student-guide-content.json";
import rawParent from "@/assets/guide/parent-guide-content.json";
import rawBoxes from "@/assets/guide/shot-boxes.json";

/**
 * Rehber (rol bazlı sesli onboarding) — web sözleşmesinin aynısı.
 *
 * İçerik JSON'ları web/components/guide/*.json'dan KOPYALANIR (tek kaynak
 * webdedir; içerik/TTS yeniden üretilince buraya da kopyala + sürümü artır).
 * Varlıklar (shot PNG + MP3) backend /static/guide'dan HTTPS ile akar —
 * uygulama paketine girmez.
 */

export interface GuideBox {
  x: number; // % (0-100)
  y: number;
  w: number;
  h: number;
}

export interface GuideStepDef {
  caption: string;
  shot: string | null;
  target: string | null;
  click: boolean;
  zoom?: boolean;
}

export interface GuideActionDef {
  label: string;
  href: string;
  checkKey: string;
  doneLabel: string;
  hint: string;
  optional?: boolean;
}

export interface GuideChapterDef {
  key: string;
  title: string;
  subtitle: string;
  steps: GuideStepDef[];
  action: GuideActionDef | null;
}

export interface GuideContent {
  guideKey: string;
  narrator: string;
  chapters: GuideChapterDef[];
}

export const GUIDES: Record<string, GuideContent> = {
  [(rawCoach as GuideContent).guideKey]: rawCoach as GuideContent,
  [(rawStudent as GuideContent).guideKey]: rawStudent as GuideContent,
  [(rawParent as GuideContent).guideKey]: rawParent as GuideContent,
};

/** Rol → guide anahtarı (kurum rehberi henüz yok). */
export const GUIDE_KEY_BY_ROLE: Record<string, string> = {
  teacher: "coach_onboarding",
  student: "student_onboarding",
  parent: "parent_onboarding",
};

/** web coach-guide-data.ts ile AYNI tutulmalı (varlık önbellek kırıcı). */
const GUIDE_ASSET_VERSION = "20260727b";

const STATIC_BASE = `${API_BASE}/static/guide`;

export const GUIDE_AVATAR_URL = `${STATIC_BASE}/rota-avatar.png?v=${GUIDE_ASSET_VERSION}`;

export function shotUrl(shot: string): string {
  return `${STATIC_BASE}/shots/${shot}.png?v=${GUIDE_ASSET_VERSION}`;
}

export function audioUrl(chapterKey: string, stepIdx: number): string {
  return `${STATIC_BASE}/audio/${chapterKey}/${stepIdx}.mp3?v=${GUIDE_ASSET_VERSION}`;
}

type BoxMap = Record<string, { targets?: Record<string, GuideBox> }>;

export function boxFor(shot: string | null, target: string | null): GuideBox | null {
  if (!shot || !target) return null;
  const entry = (rawBoxes as BoxMap)[shot];
  return entry?.targets?.[target] ?? null;
}

/** Ses yüklenemezse altyazı süresi tahmini (~2.4 kelime/sn + pay). */
export function estimateDurationMs(caption: string): number {
  const words = caption.trim().split(/\s+/).length;
  return Math.max(4000, Math.round((words / 2.4) * 1000) + 1200);
}

// ---------------------------------------------------------------------------
// API — web lib/api/guide.ts sözleşmesinin aynısı
// ---------------------------------------------------------------------------

export type GuideStatus = "not_started" | "in_progress" | "completed" | "dismissed";

export interface GuideStateModel {
  status: GuideStatus;
  current_chapter: string | null;
  chapters_done: string[];
  steps_watched: Record<string, number[]>;
  completed_at: string | null;
  dismissed_at: string | null;
}

export interface GuideResponse {
  guide_key: string;
  state: GuideStateModel;
  checklist: Record<string, boolean>;
  preexisting: Record<string, boolean>;
  chapters: string[];
}

export type GuideProgressAction =
  | "start"
  | "chapter_done"
  | "watch"
  | "complete"
  | "dismiss"
  | "reset";

export interface GuideProgressResult {
  ok: boolean;
  state: GuideStateModel;
  checklist: Record<string, boolean>;
  preexisting: Record<string, boolean>;
}

export const guideKeys = {
  state: (guideKey: string) => ["me", "guide", guideKey] as const,
};

export function getGuide(guideKey: string): Promise<GuideResponse> {
  return apiRequest(`/api/v2/me/guide/${guideKey}`);
}

export function postGuideProgress(
  guideKey: string,
  body: { action: GuideProgressAction; chapter?: string; step?: number },
): Promise<GuideProgressResult> {
  return apiRequest(`/api/v2/me/guide/${guideKey}/progress`, {
    method: "POST",
    body,
  });
}
