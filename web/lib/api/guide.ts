/**
 * /api/v2/me/guide/* fetcher'ları.
 *
 * QueryKey sözleşmesi: backend `invalidate: ["me:guide"]` → applyInvalidate
 * ile ["me", "guide"] prefix'i bayatlar.
 */
import { api } from "@/lib/api";
import type { GuideProgressBody, GuideProgressResult, GuideResponse } from "@/lib/types/guide";

export const GUIDE_COACH_ONBOARDING = "coach_onboarding";

export const guideKeys = {
  state: (guideKey: string) => ["me", "guide", guideKey] as const,
};

export function getGuide(guideKey: string): Promise<GuideResponse> {
  return api<GuideResponse>(`/api/v2/me/guide/${guideKey}`);
}

export function postGuideProgress(
  guideKey: string,
  body: GuideProgressBody,
): Promise<GuideProgressResult> {
  return api<GuideProgressResult>(`/api/v2/me/guide/${guideKey}/progress`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
