import { apiServer } from "@/lib/api-server";
import type { CohortTab, CohortsResponse } from "@/lib/types/institution";
import { CohortsClient } from "@/components/institution/cohorts-client";

/**
 * /institution/cohorts — 4 sekme: grade / track / curriculum / exam_target.
 *
 * Jinja kaynağı: app/templates/institution/cohorts.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kohort Karşılaştırma" };

const VALID_TABS: CohortTab[] = ["grade", "track", "curriculum", "exam_target"];

interface PageProps {
  searchParams: Promise<{ tab?: string }>;
}

export default async function InstitutionCohortsPage({
  searchParams,
}: PageProps) {
  const sp = await searchParams;
  const tab: CohortTab = VALID_TABS.includes(sp.tab as CohortTab)
    ? (sp.tab as CohortTab)
    : "grade";
  const data = await apiServer<CohortsResponse>(
    `/api/v2/institution/cohorts?tab=${tab}`,
  );
  return <CohortsClient initial={data} tab={tab} />;
}
