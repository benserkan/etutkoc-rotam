import { apiServer } from "@/lib/api-server";
import type { ActivityHeatmapResponse } from "@/lib/types/institution";
import { ActivityHeatmapPrintSheet } from "@/components/institution/activity-heatmap-print-sheet";

/**
 * /institution/activity-heatmap/print — A4 landscape yazdırma.
 *
 * Jinja kaynağı: app/templates/institution/activity_heatmap_print.html
 */
export const metadata = { title: "Aktivite Haritası — Yazdır" };
export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<{ weeks?: string }>;
}

export default async function InstitutionActivityHeatmapPrintPage({
  searchParams,
}: PageProps) {
  const sp = await searchParams;
  const weeks = sp.weeks === "12" ? 12 : 4;
  const data = await apiServer<ActivityHeatmapResponse>(
    `/api/v2/institution/activity-heatmap?weeks=${weeks}`,
  );
  return <ActivityHeatmapPrintSheet data={data} weeks={weeks} />;
}
