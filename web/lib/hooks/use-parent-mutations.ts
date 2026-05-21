"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  ParentChildLink,
  ParentInvitationAcceptBody,
  ParentInvitationAcceptResult,
  ParentMuteBody,
  ParentPreferencesBody,
  ParentPreferencesInfo,
  ParentWhatsAppInfo,
  ParentWhatsAppStartBody,
  ParentWhatsAppVerifyBody,
} from "@/lib/types/parent";

/**
 * Veli mutation hook'ları (Dalga 5).
 *
 * Sözleşme:
 *   - Login-gerekli mutation'lar `applyInvalidate(qc, res.invalidate)` ile
 *     "parent:me" prefix'ini yeniden bayatlar
 *   - 4xx hatalarında detail.code'a göre Türkçe açıklayıcı toast
 *   - Davet kabul (public, login öncesi) qc.invalidate çağırmaz — yeni session kurulur
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
    case "invalid_quiet_hours":
      return "Sessiz saat geçersiz";
    case "invalid_phone":
      return "Telefon geçersiz";
    case "otp_cooldown":
      return "Bekleyin";
    case "otp_send_failed":
      return "Kod gönderilemedi";
    case "invalid_code":
      return "Kod geçersiz";
    case "no_active_otp":
      return "Aktif kod yok";
    case "otp_too_many_attempts":
      return "Çok fazla deneme";
    case "otp_mismatch":
      return "Kod yanlış";
    case "child_not_found":
      return "Çocuk bulunamadı";
    case "name_required":
      return "Ad eksik";
    case "password_too_short":
      return "Şifre kısa";
    case "password_mismatch":
      return "Şifreler uyumsuz";
    case "kvkk_not_accepted":
      return "Onay eksik";
    case "email_in_use_other_role":
      return "E-posta kullanımda";
    case "not_found":
    case "expired":
    case "consumed":
      return "Davet geçersiz";
    default:
      return fallback;
  }
}

// =============================================================================
// Settings — preferences
// =============================================================================

export function useUpdateParentPreferences() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ParentPreferencesInfo>,
    Error,
    ParentPreferencesBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<ParentPreferencesInfo>>(
        "/api/v2/parent/settings/preferences",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Bildirim tercihleriniz kaydedildi.");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kaydedilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// Settings — child mute
// =============================================================================

export function useToggleChildMute(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ParentChildLink>,
    Error,
    ParentMuteBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<ParentChildLink>>(
        `/api/v2/parent/settings/students/${studentId}/mute`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        res.data.muted
          ? `${res.data.full_name} için bildirimler kapatıldı.`
          : `${res.data.full_name} için bildirimler tekrar açıldı.`,
      );
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İşlem başarısız"), {
        description: errorMessage(e, "Bildirim durumu değiştirilemedi."),
      });
    },
  });
}

// =============================================================================
// Settings — WhatsApp OTP flow
// =============================================================================

export function useWhatsAppStart() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ParentWhatsAppInfo>,
    Error,
    ParentWhatsAppStartBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<ParentWhatsAppInfo>>(
        "/api/v2/parent/settings/whatsapp/start",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const phone = res.data.pending_phone ?? "telefonunuza";
      toast.success(`Doğrulama kodu ${phone} numarasına gönderildi.`);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kod gönderilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useWhatsAppVerify() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ParentWhatsAppInfo>,
    Error,
    ParentWhatsAppVerifyBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<ParentWhatsAppInfo>>(
        "/api/v2/parent/settings/whatsapp/verify",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        `WhatsApp doğrulandı: ${res.data.phone ?? ""}. Bildirimleri WhatsApp'tan da alacaksınız.`,
      );
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Doğrulama başarısız"), {
        description: errorMessage(e, "Kod yanlış veya süresi dolmuş olabilir."),
      });
    },
  });
}

export function useWhatsAppDisable() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<ParentWhatsAppInfo>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<ParentWhatsAppInfo>>(
        "/api/v2/parent/settings/whatsapp/disable",
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("WhatsApp kanalı kapatıldı.");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kapatılamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// Public — invitation accept (login öncesi)
// =============================================================================

export function useAcceptParentInvitation(token: string) {
  // qc.invalidate çağırmıyoruz — accept JWT cookie kurar, sayfa /parent'a
  // navigate edildiğinde fresh fetch zaten yapılır.
  // eslint-disable-next-line lgs/missing-invalidate
  return useMutation<
    ParentInvitationAcceptResult,
    Error,
    ParentInvitationAcceptBody
  >({
    mutationFn: (body) =>
      api<ParentInvitationAcceptResult>(
        `/api/v2/parent/invitation/${encodeURIComponent(token)}/accept`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => {
      toast.error(errorTitle(e, "Hesap oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}
