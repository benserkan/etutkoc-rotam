"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  AdminDigestSendResult,
  InvitationCreateBody,
  InvitationItem,
  SubscriptionStatusInfo,
  TeacherCreateBody,
  TeacherCreateResult,
  TeacherSummaryItem,
} from "@/lib/types/institution";

/**
 * Kurum Yöneticisi mutation hook'ları (Dalga 4 Paket 4).
 *
 * Sözleşme:
 *   - Tüm mutation'lar başarıda backend'in MutationResponse.invalidate listesini
 *     applyInvalidate ile uygular (R-006 OOB swap karşılığı).
 *   - 4xx hatalarında detail.code'a göre Türkçe açıklayıcı toast başlığı + mesaj.
 *
 * Jinja parite:
 *   - Yeni öğretmen: tek seferlik temp_password yanıt (dialog kapanmadan göster + kopyala)
 *   - Hesap deactivate/activate (login engelli)
 *   - Pause/resume alerts (uyarı sustur — login açık)
 *   - Onay metinleri Jinja ile birebir aynı
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
    case "email_exists":
      return "E-posta zaten kayıtlı";
    case "name_required":
      return "Ad zorunlu";
    case "invalid_email":
      return "Geçersiz e-posta";
    case "teacher_not_found":
      return "Öğretmen bulunamadı";
    case "institution_inactive":
      return "Kurum aktif değil";
    case "role_required":
      return "Yetkiniz yok";
    case "invitation_not_found":
      return "Davetiye bulunamadı";
    case "invitation_not_usable":
      return "Davetiye kullanılamaz";
    case "quota_exceeded":
      return "Kuota aşıldı";
    case "digest_not_found":
      return "Özet bulunamadı";
    case "digest_send_failed":
      return "Özet gönderilemedi";
    case "summer_window_required":
      return "Yaz penceresi gerekli";
    case "pause_not_allowed":
      return "Pause uygulanamaz";
    default:
      return fallback;
  }
}

// =============================================================================
// Öğretmen oluştur — geçici şifre yanıtta tek seferlik
// =============================================================================

export function useCreateInstitutionTeacher() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherCreateResult>,
    Error,
    TeacherCreateBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<TeacherCreateResult>>(
        "/api/v2/institution/teachers",
        {
          method: "POST",
          body: JSON.stringify(body),
        },
      ),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
    onError: (e) => {
      toast.error(errorTitle(e, "Öğretmen eklenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// Hesap kapat / aç
// =============================================================================

export function useDeactivateInstitutionTeacher() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<TeacherSummaryItem>, Error, number>({
    mutationFn: (id) =>
      api<MutationResponse<TeacherSummaryItem>>(
        `/api/v2/institution/teachers/${id}/deactivate`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        `${res.data.full_name} pasifleştirildi (verisi korundu).`,
      );
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İşlem başarısız"), {
        description: errorMessage(e, "Öğretmen pasifleştirilemedi."),
      });
    },
  });
}

export function useActivateInstitutionTeacher() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<TeacherSummaryItem>, Error, number>({
    mutationFn: (id) =>
      api<MutationResponse<TeacherSummaryItem>>(
        `/api/v2/institution/teachers/${id}/activate`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(`${res.data.full_name} aktifleştirildi.`);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İşlem başarısız"), {
        description: errorMessage(e, "Öğretmen aktifleştirilemedi."),
      });
    },
  });
}

// =============================================================================
// Uyarı sustur / aç (is_paused — login açık)
// =============================================================================

export function usePauseTeacherAlerts() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<TeacherSummaryItem>, Error, number>({
    mutationFn: (id) =>
      api<MutationResponse<TeacherSummaryItem>>(
        `/api/v2/institution/teachers/${id}/pause-alerts`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        `${res.data.full_name} pasif — uyarıları susturuldu.`,
      );
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İşlem başarısız"), {
        description: errorMessage(e, "Uyarılar susturulamadı."),
      });
    },
  });
}

export function useResumeTeacherAlerts() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<TeacherSummaryItem>, Error, number>({
    mutationFn: (id) =>
      api<MutationResponse<TeacherSummaryItem>>(
        `/api/v2/institution/teachers/${id}/resume-alerts`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(`${res.data.full_name} aktif — uyarıları açıldı.`);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İşlem başarısız"), {
        description: errorMessage(e, "Uyarılar açılamadı."),
      });
    },
  });
}

// =============================================================================
// Davetiye oluştur / iptal et
// =============================================================================

export function useCreateInstitutionInvitation() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<InvitationItem>,
    Error,
    InvitationCreateBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<InvitationItem>>(
        "/api/v2/institution/invitations",
        {
          method: "POST",
          body: JSON.stringify(body),
        },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      if (res.data.email) {
        toast.success(
          `Davetiye oluşturuldu — link tabloda. E-posta: ${res.data.email}`,
        );
      } else {
        toast.success(
          "Davetiye oluşturuldu — link tabloda. Açık davetiye (e-posta yok).",
        );
      }
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Davetiye oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useRevokeInstitutionInvitation() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<InvitationItem>, Error, number>({
    mutationFn: (id) =>
      api<MutationResponse<InvitationItem>>(
        `/api/v2/institution/invitations/${id}/revoke`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Davetiye iptal edildi.");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İptal başarısız"), {
        description: errorMessage(e, "Davetiye iptal edilemedi."),
      });
    },
  });
}

// =============================================================================
// Admin Weekly Digest — "Şimdi gönder"
// =============================================================================

export function useSendAdminDigestNow() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<AdminDigestSendResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<AdminDigestSendResult>>(
        "/api/v2/institution/admin-digest/send-now",
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Özet üretilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// Abonelik aksiyonları (Paket 7)
// =============================================================================

export function useSwitchAcademicYear() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<SubscriptionStatusInfo>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<SubscriptionStatusInfo>>(
        "/api/v2/institution/subscription/switch-academic-year",
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Akademik yıl planına geçildi.");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Geçiş başarısız"), {
        description: errorMessage(e, "Akademik yıla geçilemedi."),
      });
    },
  });
}

export function usePauseForSummer() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<SubscriptionStatusInfo>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<SubscriptionStatusInfo>>(
        "/api/v2/institution/subscription/pause",
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Yaz pause moduna geçildi.");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Pause uygulanamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useResumeFromPause() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<SubscriptionStatusInfo>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<SubscriptionStatusInfo>>(
        "/api/v2/institution/subscription/resume",
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Akademik yıl planına geri dönüldü.");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Devam başarısız"), {
        description: errorMessage(e, "Pause'dan çıkılamadı."),
      });
    },
  });
}

export function useEnableGuarantee() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<SubscriptionStatusInfo>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<SubscriptionStatusInfo>>(
        "/api/v2/institution/subscription/guarantee/enable",
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("60 gün performans garantisi aktive edildi.");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Aktivasyon başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}
