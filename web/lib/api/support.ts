/**
 * Rol-bazlı talep sistemi (SupportRequest) — fetcher'lar + queryKey'ler.
 *
 * Tek /support yüzeyi; davranış rol'den türer (backend). queryKey'ler:
 *   ["support","mine", status?]  · ["support","inbox", status?] · ["support","detail", id]
 */
import { api, ApiError, type MutationResponse } from "@/lib/api";
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

/** Dosya eki yükleme — multipart/form-data (api() JSON sarmalayıcısı kullanılamaz). */
export async function uploadSupportAttachment(
  id: number,
  file: File,
): Promise<MutationResponse<SupportRequestDetail>> {
  const fd = new FormData();
  fd.append("file", file);
  // eslint-disable-next-line lgs/no-bare-fetch -- multipart yükleme; api() JSON sarmalayıcısı FormData ile uyumsuz
  const r = await fetch(
    `/api/v2/support/requests/${encodeURIComponent(String(id))}/attachments`,
    { method: "POST", credentials: "include", body: fd },
  );
  if (!r.ok) {
    let detail = { error: "error", message: "Dosya yüklenemedi" };
    try {
      const b = await r.json();
      if (b?.detail && typeof b.detail === "object") detail = b.detail;
    } catch {
      /* yoksay */
    }
    throw new ApiError(r.status, detail);
  }
  return r.json() as Promise<MutationResponse<SupportRequestDetail>>;
}
