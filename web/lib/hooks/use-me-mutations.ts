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
