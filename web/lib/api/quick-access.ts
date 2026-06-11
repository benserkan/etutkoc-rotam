/**
 * /api/v2/me/quick-cards + /api/v2/me/panel-visits fetcher'ları.
 *
 * QueryKey sözleşmesi: backend `invalidate: ["me:quick-cards"]` →
 * applyInvalidate ile ["me", "quick-cards"] prefix'i bayatlar.
 */
import { api, type MutationResponse } from "@/lib/api";
import type {
  PanelVisitEventIn,
  QuickCardActionResult,
  QuickCardRef,
  QuickCardsResponse,
} from "@/lib/types/quick-access";

export const quickAccessKeys = {
  cards: () => ["me", "quick-cards"] as const,
};

export function getQuickCards(): Promise<QuickCardsResponse> {
  return api<QuickCardsResponse>("/api/v2/me/quick-cards");
}

export function postPanelVisits(
  events: PanelVisitEventIn[],
): Promise<{ accepted: number }> {
  return api<{ accepted: number }>("/api/v2/me/panel-visits", {
    method: "POST",
    body: JSON.stringify({ events }),
  });
}

export function postQuickCardClick(
  ref: QuickCardRef,
): Promise<MutationResponse<QuickCardActionResult>> {
  return api<MutationResponse<QuickCardActionResult>>(
    "/api/v2/me/quick-cards/click",
    { method: "POST", body: JSON.stringify(ref) },
  );
}

export function postQuickCardPin(
  ref: QuickCardRef,
  pinned: boolean,
): Promise<MutationResponse<QuickCardActionResult>> {
  return api<MutationResponse<QuickCardActionResult>>(
    "/api/v2/me/quick-cards/pin",
    { method: "POST", body: JSON.stringify({ ...ref, pinned }) },
  );
}

export function postQuickCardDismiss(
  ref: QuickCardRef,
): Promise<MutationResponse<QuickCardActionResult>> {
  return api<MutationResponse<QuickCardActionResult>>(
    "/api/v2/me/quick-cards/dismiss",
    { method: "POST", body: JSON.stringify(ref) },
  );
}
