"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import { getGuide, guideKeys, postGuideProgress } from "@/lib/api/guide";
import type { GuideProgressBody, GuideProgressResult } from "@/lib/types/guide";

/** Rehber durumu — pencere odağa gelince tazelenir ("şimdi sen yap" dönüşü). */
export function useGuide(guideKey: string, enabled = true) {
  return useQuery({
    queryKey: guideKeys.state(guideKey),
    queryFn: () => getGuide(guideKey),
    enabled,
    staleTime: 15_000,
    refetchOnWindowFocus: true,
  });
}

export function useGuideProgress(guideKey: string) {
  const qc = useQueryClient();
  return useMutation<GuideProgressResult, ApiError, GuideProgressBody>({
    mutationFn: (body) => postGuideProgress(guideKey, body),
    onSuccess: (res) => {
      // Anında güncelle + prefix bayatlat (odak dönüşünde checklist tazelenir)
      qc.setQueryData(guideKeys.state(guideKey), (prev: unknown) => {
        if (!prev || typeof prev !== "object") return prev;
        return {
          ...prev,
          state: res.state,
          checklist: res.checklist,
          preexisting: res.preexisting,
        };
      });
      applyInvalidate(qc, res.invalidate);
    },
  });
}
