"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  SelfStudyCreateBody,
  SelfStudyCreateResult,
  SelfStudyDeleteResult,
  SelfStudyEntryItem,
  SelfStudyReviewBody,
} from "@/lib/types/self-study";

/** Bağımsız çalışma kayıtları mutation hook'ları (öğrenci beyanı + koç girişi/onayı). */

const ERROR_LABELS: Record<string, string> = {
  self_study_not_found: "Kayıt bulunamadı — silinmiş olabilir.",
  no_items: "En az bir bölüme 1+ test girmelisin.",
  too_many_items: "Tek seferde en fazla 100 bölüm girilebilir.",
  not_pending: "Bu kayıt zaten sonuçlanmış.",
  no_capacity:
    "Bu bölümde uygulanacak boş kapasite kalmamış (tümü çözülmüş/rezerve).",
  manual_reduce_exceeds:
    "Yalnız elle/bağımsız girilen kısım azaltılabilir — görevle çözülenler görev üzerinden düzeltilir.",
  exceeds_available: "Bölümdeki boş kapasiteden fazla test girilemez.",
  role_required: "Bu işlem için yetkin yok.",
};

function showError(e: unknown, fallbackTitle: string) {
  const code = e instanceof ApiError ? e.detail?.code : undefined;
  const msg =
    (code && ERROR_LABELS[code]) ||
    (e instanceof ApiError ? e.detail?.message : undefined) ||
    "Sunucu hatası.";
  toast.error(fallbackTitle, { description: msg });
}

function summarizeCreate(res: SelfStudyCreateResult, isCoach: boolean) {
  const parts: string[] = [];
  if (isCoach && res.applied_total > 0)
    parts.push(`${res.applied_total} test ilerlemeye işlendi`);
  if (!isCoach && res.pending_total > 0)
    parts.push(`${res.pending_total} test koç onayına gönderildi`);
  if (res.skipped.length > 0)
    parts.push(
      `${res.skipped.length} bölüm atlandı: ${res.skipped
        .map((s) => s.section_label)
        .join(", ")}`,
    );
  return parts.join(" · ") || undefined;
}

// ---------------------------------------------------------------------------
// Koç
// ---------------------------------------------------------------------------

export function useCoachSelfStudyCreate(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SelfStudyCreateResult>,
    unknown,
    SelfStudyCreateBody
  >({
    mutationFn: (body) =>
      api(`/api/v2/teacher/students/${studentId}/self-study`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Bağımsız çalışma kaydedildi", {
        description: summarizeCreate(res.data, true),
      });
    },
    onError: (e) => showError(e, "Kayıt yapılamadı"),
  });
}

export function useReviewSelfStudy() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SelfStudyEntryItem>,
    unknown,
    { entryId: number; body: SelfStudyReviewBody }
  >({
    mutationFn: ({ entryId, body }) =>
      api(`/api/v2/teacher/self-study/${entryId}/review`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      if (res.data.status === "approved") {
        toast.success("Beyan onaylandı", {
          description: `${res.data.applied_count} test ilerlemeye işlendi.`,
        });
      } else {
        toast.success("Beyan reddedildi");
      }
    },
    onError: (e) => showError(e, "İşlem yapılamadı"),
  });
}

export function useDeleteSelfStudyEntry() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SelfStudyDeleteResult>,
    unknown,
    { entryId: number }
  >({
    mutationFn: ({ entryId }) =>
      api(`/api/v2/teacher/self-study/${entryId}`, { method: "DELETE" }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kayıt silindi", {
        description:
          res.data.reverted_count > 0
            ? `${res.data.reverted_count} test ilerlemeden geri alındı.`
            : undefined,
      });
    },
    onError: (e) => showError(e, "Silinemedi"),
  });
}

// ---------------------------------------------------------------------------
// Öğrenci
// ---------------------------------------------------------------------------

export function useDeclareSelfStudy() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SelfStudyCreateResult>,
    unknown,
    SelfStudyCreateBody
  >({
    mutationFn: (body) =>
      api("/api/v2/student/self-study", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Bildirimin koçuna gönderildi", {
        description: summarizeCreate(res.data, false),
      });
    },
    onError: (e) => showError(e, "Bildirilemedi"),
  });
}

export function useWithdrawSelfStudy() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SelfStudyDeleteResult>,
    unknown,
    { entryId: number }
  >({
    mutationFn: ({ entryId }) =>
      api(`/api/v2/student/self-study/${entryId}`, { method: "DELETE" }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Bildirim geri çekildi");
    },
    onError: (e) => showError(e, "Geri çekilemedi"),
  });
}
