/**
 * Ödeme API fetcher'ları (Paket Ö1 + Ö2a).
 *
 * Endpoint sözleşmesi:
 *   GET  /api/v2/payment/provider-status        → PaymentProviderStatus
 *   POST /api/v2/payment/init                   → PaymentInitResponse (koç self-serve)
 *   GET  /api/v2/payment/transactions/{tx_id}   → PaymentResult
 *   GET  /api/v2/payment/history                → PaymentHistoryResponse
 *
 *   Süper admin link yönetimi:
 *   POST /api/v2/payment/admin/links            → PaymentLinkItem (oluştur)
 *   GET  /api/v2/payment/admin/links            → PaymentLinkListResponse
 *   POST /api/v2/payment/admin/links/{id}/cancel→ PaymentLinkItem
 *
 *   Public link akışı:
 *   GET  /api/v2/payment/link/{token}           → PaymentLinkPublicInfo
 *   POST /api/v2/payment/link/{token}/checkout  → PaymentInitResponse
 */
import { api } from "@/lib/api";
import type {
  PaymentHistoryResponse,
  PaymentLinkListResponse,
  PaymentLinkPublicInfo,
  PaymentProviderStatus,
  PaymentResult,
} from "@/lib/types/payment";

export const paymentKeys = {
  root: () => ["payment"] as const,
  providerStatus: () => ["payment", "provider-status"] as const,
  transaction: (txId: number) => ["payment", "transaction", String(txId)] as const,
  history: () => ["payment", "history"] as const,
  // Admin
  adminLinks: (status: string | null, ownerType: string | null) =>
    ["admin", "payment-links", status ?? "", ownerType ?? ""] as const,
  // Public link
  linkInfo: (token: string) => ["payment", "link", token] as const,
};

export function getPaymentProviderStatus() {
  return api<PaymentProviderStatus>("/api/v2/payment/provider-status");
}

export function getPaymentTransaction(txId: number) {
  return api<PaymentResult>(`/api/v2/payment/transactions/${txId}`);
}

export function getPaymentHistory() {
  return api<PaymentHistoryResponse>("/api/v2/payment/history");
}

export function getAdminPaymentLinks(
  statusFilter: string | null = null,
  ownerType: string | null = null,
  ownerId: number | null = null,
) {
  const qs = new URLSearchParams();
  if (statusFilter) qs.set("status_filter", statusFilter);
  if (ownerType) qs.set("target_owner_type", ownerType);
  if (ownerId) qs.set("target_owner_id", String(ownerId));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return api<PaymentLinkListResponse>(`/api/v2/payment/admin/links${suffix}`);
}

export function getPaymentLinkInfo(token: string) {
  return api<PaymentLinkPublicInfo>(
    `/api/v2/payment/link/${encodeURIComponent(token)}`,
  );
}
