/**
 * Ödeme mutation hook'ları (Paket Ö2b).
 *
 * Backend zarfsız (PaymentLinkItem doğrudan döner) — onSuccess'te manuel
 * `qc.invalidateQueries(["admin","payment-links"])` çağrılır. Standart admin
 * MutationResponse zarfı kullanılmıyor; payment akışı external API + finansal,
 * kendine özgü hata kodları var.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { paymentKeys } from "@/lib/api/payment";
import type {
  PaymentInitBody,
  PaymentInitResponse,
  PaymentLinkCreateBody,
  PaymentLinkItem,
} from "@/lib/types/payment";

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
    case "payment_provider_unavailable":
      return "Ödeme sağlayıcı kullanılamıyor";
    case "payment_plan_invalid":
      return "Geçersiz paket";
    case "payment_amount_invalid":
      return "Tutar geçersiz";
    case "payment_cycle_invalid":
      return "Geçersiz dönem";
    case "payment_input_invalid":
      return "Eksik giriş";
    case "payment_link_unusable":
      return "Link artık geçerli değil";
    case "link_owner_invalid":
      return "Hedef türü geçersiz";
    case "link_target_not_found":
      return "Hedef bulunamadı (kurum/kullanıcı)";
    case "link_amount_invalid":
      return "Tutar 0'dan büyük olmalı";
    case "link_cycle_invalid":
      return "Dönem monthly veya annual olmalı";
    case "link_token_collision":
      return "Token üretilemedi (tekrar deneyin)";
    case "link_not_found":
      return "Link bulunamadı";
    case "link_not_active":
      return "Yalnız aktif linkler iptal edilebilir";
    case "link_payment_forbidden":
      return "Bu linki ödemeye yetkili değilsiniz";
    case "role_required":
      return "Bu işlem için yetki yok";
    default:
      return fallback;
  }
}

/**
 * Süper admin: ödeme linki oluştur.
 */
export function useCreatePaymentLink() {
  const qc = useQueryClient();
  return useMutation<PaymentLinkItem, Error, PaymentLinkCreateBody>({
    mutationFn: (body) =>
      api<PaymentLinkItem>("/api/v2/payment/admin/links", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "payment-links"] });
      toast.success("Ödeme linki oluşturuldu");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Link oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata."),
      });
    },
  });
}

/**
 * Süper admin: aktif linki iptal et.
 */
export function useCancelPaymentLink() {
  const qc = useQueryClient();
  return useMutation<PaymentLinkItem, Error, number>({
    mutationFn: (linkId) =>
      api<PaymentLinkItem>(
        `/api/v2/payment/admin/links/${linkId}/cancel`,
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "payment-links"] });
      toast.success("Link iptal edildi");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İptal başarısız"), {
        description: errorMessage(e, "Link iptal edilemedi."),
      });
    },
  });
}

/**
 * Koç self-serve: paket için Iyzico checkout başlat.
 * Başarıda kullanıcıyı paymentPageUrl'a yönlendiririz.
 *
 * onSuccess: pending PaymentTransaction yazıldı, history sayfasında görünsün
 * diye `payment:history` invalidate edilir.
 */
export function useInitPaymentCheckout() {
  const qc = useQueryClient();
  return useMutation<PaymentInitResponse, Error, PaymentInitBody>({
    mutationFn: (body) =>
      api<PaymentInitResponse>("/api/v2/payment/init", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: paymentKeys.history() });
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Ödeme başlatılamadı"), {
        description: errorMessage(e, "Ödeme sayfası açılamadı."),
      });
    },
  });
}

/**
 * Kurum/koç: linkten Iyzico checkout başlat.
 *
 * onSuccess: link info değişti (status hala active ama pending tx var), link
 * sayfası yeniden ziyaret edilirse taze görünsün.
 */
export function useLinkCheckout(token: string) {
  const qc = useQueryClient();
  return useMutation<PaymentInitResponse, Error, void>({
    mutationFn: () =>
      api<PaymentInitResponse>(
        `/api/v2/payment/link/${encodeURIComponent(token)}/checkout`,
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: paymentKeys.linkInfo(token) });
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Ödeme başlatılamadı"), {
        description: errorMessage(e, "Linkten ödeme açılamadı."),
      });
    },
  });
}
