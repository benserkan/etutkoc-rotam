"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  DataDeleteRequestBody,
  DataDeleteResponse,
  PasswordChangeBody,
  PasswordChangeResult,
  PhoneMutationResult,
  StartPhoneVerificationBody,
  VerifyPhoneBody,
} from "@/lib/types/me";

interface SimpleOk {
  message: string;
}

function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.detail?.message ?? fallback;
  return fallback;
}

function errorCode(e: unknown): string | undefined {
  if (e instanceof ApiError) return e.detail?.code;
  return undefined;
}

export function usePasswordChange() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<PasswordChangeResult>,
    ApiError,
    { body: PasswordChangeBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<PasswordChangeResult>>(
        "/api/v2/me/password-change",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => {
      const code = errorCode(err);
      const map: Record<string, string> = {
        account_locked: errorMessage(err, "Hesap geçici olarak kilitli."),
        wrong_current_password: "Mevcut şifre yanlış.",
        password_mismatch: "Yeni şifreler birbiriyle eşleşmiyor.",
        password_weak: errorMessage(err, "Şifre politikayı karşılamıyor."),
        password_same: "Yeni şifre eski şifreyle aynı olamaz.",
        password_breached: errorMessage(
          err,
          "Bu şifre internet sızıntılarında geçiyor — başka bir şifre seçin.",
        ),
      };
      toast.error(map[code ?? ""] ?? errorMessage(err, "Şifre değiştirilemedi"));
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Şifre güncellendi");
    },
  });
}

export function useRequestDataDelete() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<DataDeleteResponse>,
    ApiError,
    { body: DataDeleteRequestBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<DataDeleteResponse>>("/api/v2/me/data-delete", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (err) => {
      const code = errorCode(err);
      if (code === "confirmation_required") {
        toast.error("Silme talebini onaylamanız gerekiyor.");
        return;
      }
      toast.error(errorMessage(err, "Silme talebi oluşturulamadı"));
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Silme talebi alındı — 30 gün boyunca iptal edebilirsiniz.");
    },
  });
}

export function useCancelDataDelete() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SimpleOk>,
    ApiError,
    { requestId: number }
  >({
    mutationFn: ({ requestId }) =>
      api<MutationResponse<SimpleOk>>(
        `/api/v2/me/data-delete/${requestId}/cancel`,
        { method: "POST" },
      ),
    onError: (err) => toast.error(errorMessage(err, "Talep iptal edilemedi")),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Silme talebi iptal edildi");
    },
  });
}

// ============================================================================
// P1 — Telefon doğrulama (SMS OTP)
// ============================================================================

const PHONE_ERROR_LABELS: Record<string, string> = {
  invalid_phone: "Geçersiz telefon numarası.",
  cooldown_active: "Çok hızlı yeni kod istediniz. Birkaç saniye bekleyin.",
  sms_send_failed: "SMS gönderilemedi. Birkaç dakika sonra tekrar deneyin.",
  invalid_code_format: "Kod 6 haneli olmalı.",
  no_pending_verification: "Bekleyen doğrulama yok. Önce kod gönderin.",
  expired: "Kod süresi doldu. Yeni kod isteyin.",
  too_many_attempts: "Çok fazla hatalı deneme. Yeni kod isteyin.",
  otp_mismatch: "Kod hatalı.",
  secondary_slot_parent_only:
    "İkinci telefon yalnız veli hesaplarına özeldir.",
};

function phoneErrorMessage(err: ApiError): string {
  const code = errorCode(err);
  return (code && PHONE_ERROR_LABELS[code]) || errorMessage(err, "İşlem başarısız oldu");
}

export function usePhoneStart() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PhoneMutationResult>, ApiError, StartPhoneVerificationBody>({
    mutationFn: (body) =>
      api<MutationResponse<PhoneMutationResult>>("/api/v2/me/phone/start", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (err) => toast.error(phoneErrorMessage(err)),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "Doğrulama kodu gönderildi.");
    },
  });
}

export function usePhoneSave() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PhoneMutationResult>, ApiError, StartPhoneVerificationBody>({
    mutationFn: (body) =>
      api<MutationResponse<PhoneMutationResult>>("/api/v2/me/phone/save", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (err) => toast.error(phoneErrorMessage(err)),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "Telefon numarası kaydedildi.");
    },
  });
}

export function usePhoneSecondarySave() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PhoneMutationResult>, ApiError, StartPhoneVerificationBody>({
    mutationFn: (body) =>
      api<MutationResponse<PhoneMutationResult>>("/api/v2/me/phone-secondary/save", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (err) => toast.error(phoneErrorMessage(err)),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "İkinci telefon numarası kaydedildi.");
    },
  });
}

export function usePhoneVerify() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PhoneMutationResult>, ApiError, VerifyPhoneBody>({
    mutationFn: (body) =>
      api<MutationResponse<PhoneMutationResult>>("/api/v2/me/phone/verify", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (err) => toast.error(phoneErrorMessage(err)),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "Telefon doğrulandı.");
    },
  });
}

export function usePhoneDelete() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PhoneMutationResult>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<PhoneMutationResult>>("/api/v2/me/phone/delete", {
        method: "POST",
      }),
    onError: (err) => toast.error(phoneErrorMessage(err)),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "Telefon kaldırıldı.");
    },
  });
}

export function usePhoneSecondaryStart() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PhoneMutationResult>, ApiError, StartPhoneVerificationBody>({
    mutationFn: (body) =>
      api<MutationResponse<PhoneMutationResult>>(
        "/api/v2/me/phone-secondary/start",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => toast.error(phoneErrorMessage(err)),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "Doğrulama kodu gönderildi.");
    },
  });
}

export function usePhoneSecondaryVerify() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PhoneMutationResult>, ApiError, VerifyPhoneBody>({
    mutationFn: (body) =>
      api<MutationResponse<PhoneMutationResult>>(
        "/api/v2/me/phone-secondary/verify",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => toast.error(phoneErrorMessage(err)),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "İkinci telefon doğrulandı.");
    },
  });
}

export function usePhoneSecondaryDelete() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PhoneMutationResult>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<PhoneMutationResult>>(
        "/api/v2/me/phone-secondary/delete",
        { method: "POST" },
      ),
    onError: (err) => toast.error(phoneErrorMessage(err)),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "İkinci telefon kaldırıldı.");
    },
  });
}
