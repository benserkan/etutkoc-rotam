// P3-P4 — Click-to-WhatsApp API katmanı

import { api } from "@/lib/api";
import type {
  BulkSendBody,
  BulkSendResponse,
  BulkTargetsResponse,
  DispatchLogResponse,
  DispatchStatsResponse,
  WaLinkRequestBody,
  WaLinkResult,
  WaTargetBrief,
  WaTemplatesListResponse,
} from "@/lib/types/messaging";

export const messagingKeys = {
  templates: (category: string | null) =>
    ["messaging", "templates", category ?? ""] as const,
  target: (userId: number) =>
    ["messaging", "target", String(userId)] as const,
  bulkTargets: (group: string) =>
    ["messaging", "bulk-targets", group] as const,
  dispatchStats: () => ["messaging", "dispatch-stats"] as const,
};

export function getMessagingTemplates(category: string | null = null) {
  const qs = new URLSearchParams();
  if (category) qs.set("category", category);
  const url = qs.toString()
    ? `/api/v2/messaging/templates?${qs.toString()}`
    : "/api/v2/messaging/templates";
  return api<WaTemplatesListResponse>(url);
}

export function getMessagingTarget(userId: number) {
  return api<WaTargetBrief>(`/api/v2/messaging/target/${userId}`);
}

export function buildWaLink(body: WaLinkRequestBody) {
  return api<WaLinkResult>("/api/v2/messaging/wa-link", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// P5 — Toplu gönderim

export function getMessagingBulkTargets(group: string) {
  const qs = new URLSearchParams({ group });
  return api<BulkTargetsResponse>(
    `/api/v2/messaging/bulk-targets?${qs.toString()}`,
  );
}

export function buildBulkWaLink(body: BulkSendBody) {
  return api<BulkSendResponse>("/api/v2/messaging/bulk-link", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// P6 — Spam guard + admin audit

export function getMessagingDispatchStats() {
  return api<DispatchStatsResponse>("/api/v2/messaging/dispatch-stats");
}

export function getAdminWhatsAppDispatchLog(
  days = 7,
  senderId: number | null = null,
  limit = 50,
) {
  const qs = new URLSearchParams({
    days: String(days),
    limit: String(limit),
  });
  if (senderId) qs.set("sender_id", String(senderId));
  return api<DispatchLogResponse>(
    `/api/v2/admin/whatsapp-dispatch-log?${qs.toString()}`,
  );
}
