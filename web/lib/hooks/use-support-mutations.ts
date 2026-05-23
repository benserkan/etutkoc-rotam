"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  SupportRequestCreateBody,
  SupportRequestDetail,
} from "@/lib/types/support";

/**
 * Rol-bazlı talep sistemi mutation hook'ları.
 * Hata kodları: subject_required / body_required / subject_too_long /
 *   body_too_long / request_closed / already_closed / invalid_transition /
 *   not_owner / role_not_allowed / request_not_found / role_required
 */

function errMsg(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.detail?.message ?? fallback;
  return fallback;
}

function showError(e: unknown, fallbackTitle: string) {
  toast.error(fallbackTitle, { description: errMsg(e, "Sunucu hatası.") });
}

type Detail = MutationResponse<SupportRequestDetail>;

export function useCreateSupportRequest() {
  const qc = useQueryClient();
  return useMutation<Detail, ApiError, { body: SupportRequestCreateBody }>({
    mutationFn: ({ body }) =>
      api<Detail>("/api/v2/support/requests", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => showError(e, "Talep oluşturulamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Talebiniz iletildi");
    },
  });
}

export function useReplySupport(requestId: number) {
  const qc = useQueryClient();
  return useMutation<Detail, ApiError, { body: string }>({
    mutationFn: ({ body }) =>
      api<Detail>(`/api/v2/support/requests/${requestId}/reply`, {
        method: "POST",
        body: JSON.stringify({ body }),
      }),
    onError: (e) => showError(e, "Mesaj gönderilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.setQueryData(["support", "detail", String(requestId)], res.data);
    },
  });
}

export function useWithdrawSupport(requestId: number) {
  const qc = useQueryClient();
  return useMutation<Detail, ApiError, void>({
    mutationFn: () =>
      api<Detail>(`/api/v2/support/requests/${requestId}/withdraw`, {
        method: "POST",
      }),
    onError: (e) => showError(e, "Talep geri çekilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.setQueryData(["support", "detail", String(requestId)], res.data);
      toast.success("Talep geri çekildi");
    },
  });
}

export function useReviewSupport(requestId: number) {
  const qc = useQueryClient();
  return useMutation<Detail, ApiError, void>({
    mutationFn: () =>
      api<Detail>(`/api/v2/support/requests/${requestId}/review`, {
        method: "POST",
      }),
    onError: (e) => showError(e, "İncelemeye alınamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.setQueryData(["support", "detail", String(requestId)], res.data);
      toast.success("İncelemeye alındı");
    },
  });
}

export function useEscalateSupport(requestId: number) {
  const qc = useQueryClient();
  return useMutation<Detail, ApiError, { note?: string }>({
    mutationFn: ({ note }) =>
      api<Detail>(`/api/v2/support/requests/${requestId}/escalate`, {
        method: "POST",
        body: JSON.stringify({ note: note ?? null }),
      }),
    onError: (e) => showError(e, "Yönlendirilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.setQueryData(["support", "detail", String(requestId)], res.data);
      toast.success("Talep süper yöneticiye yönlendirildi");
    },
  });
}

export function useResolveSupport(requestId: number) {
  const qc = useQueryClient();
  return useMutation<Detail, ApiError, void>({
    mutationFn: () =>
      api<Detail>(`/api/v2/support/requests/${requestId}/resolve`, {
        method: "POST",
      }),
    onError: (e) => showError(e, "Çözümlenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.setQueryData(["support", "detail", String(requestId)], res.data);
      toast.success("Talep çözümlendi");
    },
  });
}
