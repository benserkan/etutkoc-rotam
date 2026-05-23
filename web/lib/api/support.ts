/**
 * Rol-bazlı talep sistemi (SupportRequest) — fetcher'lar + queryKey'ler.
 *
 * Tek /support yüzeyi; davranış rol'den türer (backend). queryKey'ler:
 *   ["support","mine", status?]  · ["support","inbox", status?] · ["support","detail", id]
 */
import { api } from "@/lib/api";
import type {
  SupportListResponse,
  SupportRequestDetail,
} from "@/lib/types/support";

export const supportKeys = {
  mine: (status?: string) => ["support", "mine", status ?? "all"] as const,
  inbox: (status?: string) => ["support", "inbox", status ?? "all"] as const,
  detail: (id: number) => ["support", "detail", String(id)] as const,
} as const;

function qs(status?: string): string {
  return status ? `?status=${encodeURIComponent(status)}` : "";
}

export function getMySupportRequests(status?: string): Promise<SupportListResponse> {
  return api<SupportListResponse>(`/api/v2/support/requests${qs(status)}`);
}

export function getSupportInbox(status?: string): Promise<SupportListResponse> {
  return api<SupportListResponse>(`/api/v2/support/inbox${qs(status)}`);
}

export function getSupportRequest(id: number): Promise<SupportRequestDetail> {
  return api<SupportRequestDetail>(
    `/api/v2/support/requests/${encodeURIComponent(String(id))}`,
  );
}
