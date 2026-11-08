// Takip listesi + ölçüm listesi fetcher'ları (süper admin).
import { api } from "@/lib/api";
import type {
  FollowUpListResponse,
  MetricDetailResponse,
  MetricsResponse,
} from "@/lib/types/follow-ups";

export type FollowUpStatusFilter = "open" | "closed" | "all";

// Backend invalidate: "admin:follow-ups" / "admin:metrics" → bu öneklerle eşleşir.
export const followUpKeys = {
  all: ["admin", "follow-ups"] as const,
  list: (status: FollowUpStatusFilter) => ["admin", "follow-ups", status] as const,
};

export const metricKeys = {
  all: ["admin", "metrics"] as const,
  list: () => ["admin", "metrics", "list"] as const,
  detail: (key: string, days: number) => ["admin", "metrics", "detail", key, String(days)] as const,
};

export function getFollowUps(status: FollowUpStatusFilter = "open"): Promise<FollowUpListResponse> {
  return api<FollowUpListResponse>(`/api/v2/admin/follow-ups?status=${status}`);
}

export function getMetrics(): Promise<MetricsResponse> {
  return api<MetricsResponse>("/api/v2/admin/metrics");
}

export function getMetricDetail(key: string, days = 90): Promise<MetricDetailResponse> {
  return api<MetricDetailResponse>(
    `/api/v2/admin/metrics/${encodeURIComponent(key)}?days=${days}`,
  );
}
