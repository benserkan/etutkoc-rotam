"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  CronRunNowResult,
  CronSchedulePatchBody,
  CronScheduleItem,
  TestEmailBody,
  TestEmailResult,
} from "@/lib/types/settings";

/**
 * Öğretmen ayarları mutation hook'ları (Dalga 3 Paket 9).
 *
 * Backend kodları:
 *   - cron_not_found
 *   - invalid_hour / invalid_minute / invalid_day_of_week
 *   - email_required
 *   - cron_run_failed
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
    case "cron_not_found":
      return "Zamanlama bulunamadı";
    case "invalid_hour":
    case "invalid_minute":
    case "invalid_day_of_week":
      return "Geçersiz zaman bilgisi";
    case "email_required":
      return "E-posta adresi gerekli";
    case "cron_run_failed":
      return "Manuel tetikleme hatası";
    default:
      return fallback;
  }
}

function showError(e: unknown, fallbackTitle: string) {
  toast.error(errorTitle(e, fallbackTitle), {
    description: errorMessage(e, "Sunucu hatası."),
  });
}

export function useTestEmail() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TestEmailResult>,
    ApiError,
    { body: TestEmailBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<TestEmailResult>>(
        "/api/v2/teacher/settings/test-email",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Test e-postası gönderilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      if (res.data.sent) {
        toast.success("Test e-postası gönderildi", {
          description: res.data.message,
        });
      } else {
        toast.warning("Test e-postası gönderilemedi", {
          description: res.data.message,
        });
      }
    },
  });
}

export function usePatchCronSchedule(scheduleId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<CronScheduleItem>,
    ApiError,
    { body: CronSchedulePatchBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<CronScheduleItem>>(
        `/api/v2/teacher/settings/cron/${encodeURIComponent(
          String(scheduleId),
        )}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Zamanlama güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Zamanlama güncellendi", {
        description: `${res.data.job_key} → ${res.data.time_label} (${res.data.dow_label})`,
      });
    },
  });
}

export function useRunCronNow() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<CronRunNowResult>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<CronRunNowResult>>(
        "/api/v2/teacher/settings/cron/run-now",
        { method: "POST", body: "{}" },
      ),
    onError: (err) => showError(err, "Manuel tetikleme başarısız"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const { summary, sent, suppressed } = res.data;
      const dispBits: string[] = [];
      if (sent > 0) dispBits.push(`${sent} bildirim gönderildi`);
      if (suppressed > 0) dispBits.push(`${suppressed} bastırıldı`);
      const dispLabel =
        dispBits.length > 0 ? dispBits.join(" · ") : "yeni gönderim yok";
      toast.success("Manuel tarama tamamlandı", {
        description: `${summary} → ${dispLabel}`,
      });
    },
  });
}
