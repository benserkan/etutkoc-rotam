/**
 * QA — Hızlı erişim kartları tipleri (davranıştan öğrenen panel kartları).
 * Backend: app/routes/api_v2/quick_access.py
 */

export type QuickCardState = "suggested" | "established" | "pinned";

export interface QuickCard {
  route_key: string;
  entity_id: number | null;
  href: string;
  /** Entity kartında kişi/kayıt adı (örn. öğrenci adı), sayfa kartında sayfa adı */
  label: string;
  /** Entity kartında sayfa adı (örn. "Haftalık Program") */
  sublabel: string | null;
  state: QuickCardState;
  score: number;
  card_clicks: number;
}

export interface QuickCardsResponse {
  cards: QuickCard[];
}

export interface QuickCardActionResult {
  ok: boolean;
  state: string | null;
  card_clicks: number;
}

export interface QuickCardRef {
  route_key: string;
  entity_id: number | null;
}

export interface PanelVisitEventIn {
  path: string;
  dwell_ms?: number;
}
