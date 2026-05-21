import { apiServer } from "@/lib/api-server";
import type { LiveFeedResponse } from "@/lib/types/admin";
import { SecurityLiveClient } from "@/components/admin/security-live-client";

/**
 * /admin/security-monitor/live — Canlı Olay Akışı (G3).
 *
 * Jinja kaynağı: admin.py:5345-5370 + security_monitor_live.html + _live_feed.html.
 * Client poll (refetchInterval) ile 5s'de bir akış tazelenir.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Canlı Akış — Süper Admin" };

export default async function SecurityLivePage() {
  const data = await apiServer<LiveFeedResponse>(
    "/api/v2/admin/security-monitor/live/feed?since_seconds=600",
  );
  return <SecurityLiveClient initial={data} />;
}
