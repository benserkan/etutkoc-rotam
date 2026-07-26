/** Rehber (rol bazlı onboarding guide) tipleri. */

export type GuideStatus = "not_started" | "in_progress" | "completed" | "dismissed";

export interface GuideStateModel {
  status: GuideStatus;
  current_chapter: string | null;
  chapters_done: string[];
  /** Bölüm anahtarı → sonuna kadar izlenen adım indeksleri (kaldığı yerden devam) */
  steps_watched: Record<string, number[]>;
  completed_at: string | null;
  dismissed_at: string | null;
}

export interface GuideResponse {
  guide_key: string;
  state: GuideStateModel;
  /** Bölüm anahtarı → REHBER BAŞLADIKTAN SONRA yapılan gerçek eylem */
  checklist: Record<string, boolean>;
  /** Bölüm anahtarı → rehberden ÖNCE zaten mevcut veri ("zaten yapmışsın") */
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

export interface GuideProgressBody {
  action: GuideProgressAction;
  chapter?: string;
  step?: number;
}

export interface GuideProgressResult {
  ok: boolean;
  state: GuideStateModel;
  checklist: Record<string, boolean>;
  preexisting: Record<string, boolean>;
  invalidate: string[];
}
