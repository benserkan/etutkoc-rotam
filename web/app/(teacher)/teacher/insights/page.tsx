import { apiServer } from "@/lib/api-server";
import type { FleetInsightsResponse } from "@/lib/types/insights";
import { InsightsOverviewClient } from "@/components/teacher/insights-overview-client";

/**
 * /teacher/insights — AI öneri motorunun filo (fleet) içgörü paneli (Paket 9).
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "AI İçgörü",
};

export default async function TeacherInsightsPage() {
  const data = await apiServer<FleetInsightsResponse>(
    "/api/v2/teacher/insights/overview",
  );
  return <InsightsOverviewClient initial={data} />;
}
