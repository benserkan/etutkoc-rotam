"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  AppointmentCreateBody,
  AppointmentMutationResult,
  AppointmentUpdateBody,
  AvailabilityWindowItem,
  SeriesUpdateResult,
} from "@/lib/types/appointment";

/** Randevu sistemi mutation hook'ları (koç + öğrenci). */

const ERROR_LABELS: Record<string, string> = {
  appointment_not_found: "Randevu bulunamadı — silinmiş olabilir.",
  invalid_time: "Saat SS:DD biçiminde olmalı (örn. 17:00).",
  invalid_date: "Tarih geçersiz.",
  past_datetime: "Geçmiş bir tarihe randevu oluşturulamaz.",
  time_conflict: "Bu saatte başka bir görüşme var.",
  not_editable: "Sonuçlanmış randevu düzenlenemez.",
  not_pending: "Bu istek zaten sonuçlanmış.",
  pending_needs_review: "Bekleyen istek önce onaylanmalı ya da reddedilmeli.",
  pending_exists:
    "Bekleyen bir görüşme isteğin zaten var — koçun yanıtlamasını bekle ya da geri çek.",
  slot_unavailable: "Bu saat artık uygun değil — listeden boş bir saat seç.",
  invalid_window: "Bitiş saati başlangıçtan sonra olmalı.",
  invalid_weekday: "Gün seçimi geçersiz.",
  no_coach: "Görüşme isteği için bir koça bağlı olman gerekir.",
  google_not_configured: "Google bağlantısı bu sunucuda henüz açık değil.",
  role_required: "Bu işlem için yetkin yok.",
};

function errCode(err: unknown): string {
  if (err instanceof ApiError) return err.detail?.code ?? "";
  return "";
}

function showErr(err: unknown, fallback: string) {
  const code = errCode(err);
  toast.error(ERROR_LABELS[code] ?? fallback);
}

// ---------------------------------------------------------------------------
// Koç
// ---------------------------------------------------------------------------

export function useCreateAppointment() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AppointmentMutationResult>,
    ApiError,
    AppointmentCreateBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<AppointmentMutationResult>>(
        "/api/v2/teacher/appointments",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showErr(err, "Randevu oluşturulamadı"),
    onSuccess: (res, vars) => {
      applyInvalidate(qc, res.invalidate);
      if (vars.weekly) {
        toast.success("Haftalık görüşme planı kuruldu");
      } else {
        toast.success("Görüşme planlandı — öğrenciye haber verildi");
      }
      if (res.data.google_link_attached) {
        toast.success("Meet linki otomatik oluşturuldu");
      }
    },
  });
}

export function useUpdateAppointment(apptId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AppointmentMutationResult>,
    ApiError,
    AppointmentUpdateBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<AppointmentMutationResult>>(
        `/api/v2/teacher/appointments/${apptId}`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showErr(err, "Randevu güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Randevu güncellendi");
    },
  });
}

export function useSetAppointmentStatus() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AppointmentMutationResult>,
    ApiError,
    { apptId: number; status: "cancelled" | "done" | "no_show" | "scheduled"; reason?: string }
  >({
    mutationFn: ({ apptId, status, reason }) =>
      api<MutationResponse<AppointmentMutationResult>>(
        `/api/v2/teacher/appointments/${apptId}/status`,
        { method: "POST", body: JSON.stringify({ status, reason }) },
      ),
    onError: (err) => showErr(err, "Durum güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Durum güncellendi");
    },
  });
}

export function useApproveAppointment() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AppointmentMutationResult>,
    ApiError,
    { apptId: number }
  >({
    mutationFn: ({ apptId }) =>
      api<MutationResponse<AppointmentMutationResult>>(
        `/api/v2/teacher/appointments/${apptId}/approve`,
        { method: "POST" },
      ),
    onError: (err) => showErr(err, "İstek onaylanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("İstek onaylandı — öğrenciye haber verildi");
    },
  });
}

export function useRejectAppointment() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AppointmentMutationResult>,
    ApiError,
    { apptId: number; reason?: string }
  >({
    mutationFn: ({ apptId, reason }) =>
      api<MutationResponse<AppointmentMutationResult>>(
        `/api/v2/teacher/appointments/${apptId}/reject`,
        { method: "POST", body: JSON.stringify({ reason }) },
      ),
    onError: (err) => showErr(err, "İstek reddedilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("İstek reddedildi");
    },
  });
}

export function useUpdateSeries() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SeriesUpdateResult>,
    ApiError,
    {
      seriesId: number;
      weekday?: number;
      start_time?: string;
      duration_min?: number;
      meeting_link?: string | null;
      active?: boolean;
    }
  >({
    mutationFn: ({ seriesId, ...body }) =>
      api<MutationResponse<SeriesUpdateResult>>(
        `/api/v2/teacher/appointment-series/${seriesId}`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showErr(err, "Haftalık plan güncellenemedi"),
    onSuccess: (res, vars) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        vars.active === false
          ? "Haftalık görüşme planı kapatıldı"
          : "Haftalık plan güncellendi",
      );
    },
  });
}

export function useReplaceAvailability() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ availability: AvailabilityWindowItem[] }>,
    ApiError,
    { windows: AvailabilityWindowItem[] }
  >({
    mutationFn: (body) =>
      api<MutationResponse<{ availability: AvailabilityWindowItem[] }>>(
        "/api/v2/teacher/availability",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showErr(err, "Uygunluk saatleri kaydedilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Uygunluk saatleri kaydedildi");
    },
  });
}

export function useDisconnectGoogle() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<{ ok: boolean }>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<{ ok: boolean }>>(
        "/api/v2/teacher/google/disconnect",
        { method: "POST" },
      ),
    onError: (err) => showErr(err, "Google bağlantısı kesilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Google bağlantısı kaldırıldı");
    },
  });
}

// ---------------------------------------------------------------------------
// Öğrenci
// ---------------------------------------------------------------------------

export function useRequestAppointment() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AppointmentMutationResult>,
    ApiError,
    { date: string; start_time: string; note?: string }
  >({
    mutationFn: (body) =>
      api<MutationResponse<AppointmentMutationResult>>(
        "/api/v2/student/appointments/request",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showErr(err, "Görüşme isteği gönderilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("İsteğin koçuna iletildi — onaylayınca haber vereceğiz");
    },
  });
}

export function useWithdrawAppointment() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ ok: boolean }>,
    ApiError,
    { apptId: number }
  >({
    mutationFn: ({ apptId }) =>
      api<MutationResponse<{ ok: boolean }>>(
        `/api/v2/student/appointments/${apptId}/withdraw`,
        { method: "POST" },
      ),
    onError: (err) => showErr(err, "İstek geri çekilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("İsteğin geri çekildi");
    },
  });
}
