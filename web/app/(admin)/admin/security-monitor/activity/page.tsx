import { apiServer } from "@/lib/api-server";
import type { ActivityPanelResponse, ActivitySegment } from "@/lib/types/admin";
import { SecurityActivityClient } from "@/components/admin/security-activity-client";

/**
 * /admin/security-monitor/activity — Aktivite Kamerası (G2b).
 *
 * Jinja kaynağı: admin.py:3295-3371 + security_monitor_activity.html (1616).
 * Segment URL state (?segment=); 6 sekme client-side. Tüm sekmelerin verisi
 * tek çağrıda gelir (Jinja paritesi).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Aktivite Kamerası — Süper Admin" };

const VALID: ActivitySegment[] = ["all", "institution", "solo"];

export default async function SecurityActivityPage({
  searchParams,
}: {
  searchParams: Promise<{ segment?: string; tab?: string }>;
}) {
  const sp = await searchParams;
  const segment: ActivitySegment = VALID.includes(sp.segment as ActivitySegment)
    ? (sp.segment as ActivitySegment)
    : "all";
  const data = await apiServer<ActivityPanelResponse>(
    `/api/v2/admin/security-monitor/activity?segment=${segment}`,
  );
  return <SecurityActivityClient initial={data} segment={segment} initialTab={sp.tab} />;
}
