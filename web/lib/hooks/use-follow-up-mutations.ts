"use client";

/** Takip listesi + ölçüm listesi mutation hook'ları (süper admin). */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type { FollowUpBody, FollowUpItem, FollowUpPatchBody } from "@/lib/types/follow-ups";

function onError(err: unknown) {
  const msg =
    err instanceof ApiError ? err.detail.message || "İşlem yapılamadı." : "İşlem yapılamadı.";
  toast.error(msg);
}

function post<T>(path: string, body: unknown): Promise<MutationResponse<T>> {
  return api<MutationResponse<T>>(path, { method: "POST", body: JSON.stringify(body ?? {}) });
}

const BASE = "/api/v2/admin/follow-ups";

export function useCreateFollowUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: FollowUpBody) => post<FollowUpItem>(BASE, body),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Takip listesine eklendi.");
    },
    onError,
  });
}

export function useUpdateFollowUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: FollowUpPatchBody }) =>
      post<FollowUpItem>(`${BASE}/${id}`, body),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Güncellendi.");
    },
    onError,
  });
}

export function useCompleteFollowUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, note, next_due }: { id: number; note?: string; next_due?: string | null }) =>
      post<{ item: FollowUpItem; next: FollowUpItem | null }>(`${BASE}/${id}/complete`, {
        note: note || null,
        next_due: next_due || null,
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const nxt = res.data.next;
      toast.success(
        nxt
          ? `Tamamlandı. Sıradaki ${new Date(nxt.effective_due).toLocaleDateString("tr-TR")} tarihinde açılacak.`
          : "Tamamlandı.",
      );
    },
    onError,
  });
}

export function useSnoozeFollowUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, days, until }: { id: number; days?: number; until?: string }) =>
      post<FollowUpItem>(`${BASE}/${id}/snooze`, { days: days ?? null, until: until ?? null }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        `Ertelendi: ${new Date(res.data.effective_due).toLocaleDateString("tr-TR")}`,
      );
    },
    onError,
  });
}

export function useCancelFollowUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) =>
      post<FollowUpItem>(`${BASE}/${id}/cancel`, { note: note || null }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("İptal edildi.");
    },
    onError,
  });
}

export function useReopenFollowUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, due_on }: { id: number; due_on?: string }) =>
      post<FollowUpItem>(`${BASE}/${id}/reopen`, { due_on: due_on ?? null }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Yeniden açıldı.");
    },
    onError,
  });
}

export function useCheckFollowUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => post<FollowUpItem>(`${BASE}/${id}/check`, {}),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
    onError,
  });
}

export function useDeleteFollowUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => post<{ deleted: boolean }>(`${BASE}/${id}/delete`, {}),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Silindi.");
    },
    onError,
  });
}

export function useCollectMetrics() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => post<Record<string, number | string>>("/api/v2/admin/metrics/collect", {}),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Bugünün ölçümü alındı.");
    },
    onError,
  });
}
