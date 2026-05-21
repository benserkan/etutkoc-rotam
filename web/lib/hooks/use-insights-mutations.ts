"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  SuggestionAcceptAllBody,
  SuggestionAcceptAllResult,
  SuggestionAcceptBody,
  SuggestionAcceptResult,
  SuggestionRejectBody,
  SuggestionRejectResult,
} from "@/lib/types/insights";

/**
 * Öneri kabul/red mutation hook'ları (Dalga 3 Paket 9).
 *
 * Backend MutationResponse.invalidate listesi ile prefix bazlı invalidation.
 * Hata kodları (HTTPException.detail.code):
 *   - reservation_failed: kapasite/kilit sorunu
 *   - student_not_found: cross-tenant kontrolü
 *   - invalid_book_section / invalid_planned_count / invalid_date
 */

function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.detail?.message ?? fallback;
  return fallback;
}

function errorCode(e: unknown): string | undefined {
  if (e instanceof ApiError) return e.detail?.code;
  return undefined;
}

function errorTitle(e: unknown, fallback: string): string {
  const code = errorCode(e);
  switch (code) {
    case "reservation_failed":
      return "Kapasite yetersiz";
    case "student_not_found":
      return "Öğrenci bulunamadı";
    case "invalid_book_section":
      return "Kitap veya bölüm geçersiz";
    case "invalid_planned_count":
      return "Adet en az 1 olmalı";
    case "invalid_date":
      return "Tarih formatı geçersiz";
    default:
      return fallback;
  }
}

function showError(e: unknown, fallbackTitle: string) {
  toast.error(errorTitle(e, fallbackTitle), {
    description: errorMessage(e, "Sunucu hatası."),
  });
}

export function useAcceptSuggestion(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SuggestionAcceptResult>,
    ApiError,
    { body: SuggestionAcceptBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<SuggestionAcceptResult>>(
        `/api/v2/teacher/insights/students/${encodeURIComponent(
          String(studentId),
        )}/suggestions/accept`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Öneri eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Öneri programa eklendi");
    },
  });
}

export function useRejectSuggestion(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SuggestionRejectResult>,
    ApiError,
    { body: SuggestionRejectBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<SuggestionRejectResult>>(
        `/api/v2/teacher/insights/students/${encodeURIComponent(
          String(studentId),
        )}/suggestions/reject`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Öneri reddedilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Öneri reddedildi");
    },
  });
}

export function useAcceptAllSuggestions(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SuggestionAcceptAllResult>,
    ApiError,
    { body: SuggestionAcceptAllBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<SuggestionAcceptAllResult>>(
        `/api/v2/teacher/insights/students/${encodeURIComponent(
          String(studentId),
        )}/suggestions/accept-all`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Toplu kabul başarısız"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const { created_count, errors } = res.data;
      if (created_count > 0 && errors.length === 0) {
        toast.success(`${created_count} öneri eklendi`);
      } else if (created_count > 0) {
        toast.warning(
          `${created_count} öneri eklendi, ${errors.length} öneri atlandı`,
          { description: errors.slice(0, 2).join("\n") },
        );
      } else if (errors.length > 0) {
        toast.error("Hiçbir öneri eklenemedi", {
          description: errors.slice(0, 2).join("\n"),
        });
      } else {
        toast.info("Eklenecek öneri yok");
      }
    },
  });
}
