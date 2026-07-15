import { apiRequest } from "./api";

/**
 * /api/v2/me — hesap durumu + KVKK (hesap silme) uçları.
 *
 * Apple 5.1.1(v): hesap oluşturmayı destekleyen uygulama, hesap SİLMEYİ de
 * uygulama içinden sunmalı. Backend'de mevcut KVKK akışı kullanılır:
 *   POST /me/data-delete            → 30 gün sonra kalıcı silme (iptal edilebilir)
 *   POST /me/data-delete/{id}/cancel → bekleyen talebi iptal
 */

export interface KvkkStatus {
  has_pending_delete: boolean;
  pending_delete_request_id: number | null;
  pending_delete_scheduled_at: string | null;
}

export interface MyAccountResponse {
  user: { id: number; full_name: string; email: string; role: string };
  kvkk_status: KvkkStatus;
}

export const meKeys = {
  account: ["me", "account"] as const,
};

export function getMyAccount(): Promise<MyAccountResponse> {
  return apiRequest<MyAccountResponse>(`/api/v2/me`);
}

export interface DataDeleteResult {
  request_id: number;
  scheduled_at: string;
  can_cancel_until: string;
}

export function requestAccountDelete(reason?: string): Promise<{ data: DataDeleteResult }> {
  return apiRequest<{ data: DataDeleteResult }>(`/api/v2/me/data-delete`, {
    method: "POST",
    body: { confirm: true, reason: reason?.trim() || null },
  });
}

export function cancelAccountDelete(requestId: number): Promise<unknown> {
  return apiRequest(`/api/v2/me/data-delete/${requestId}/cancel`, {
    method: "POST",
    body: {},
  });
}
