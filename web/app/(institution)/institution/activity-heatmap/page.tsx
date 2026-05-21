import { apiServer } from "@/lib/api-server";
import type { ActivityHeatmapResponse } from "@/lib/types/institution";
import { ActivityHeatmapClient } from "@/components/institution/activity-heatmap-client";

/**
 * /institution/activity-heatmap — Öğretmen aktivite haritası.
 *
 * Jinja kaynağı: app/templates/institution/activity_heatmap.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Öğretmen Aktivite Haritası" };

interface PageProps {
  searchParams: Promise<{ weeks?: string }>;
}

export default async function InstitutionActivityHeatmapPage({
  searchParams,
}: PageProps) {
  const sp = await searchParams;
  const weeks = sp.weeks === "12" ? 12 : 4;
  const data = await apiServer<ActivityHeatmapResponse>(
    `/api/v2/institution/activity-heatmap?weeks=${weeks}`,
  );
  return <ActivityHeatmapClient initial={data} weeks={weeks} />;
}
