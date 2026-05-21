import { apiServer } from "@/lib/api-server";
import type { InstitutionGoalsResponse } from "@/lib/types/institution";
import { GoalsClient } from "@/components/institution/goals-client";

/**
 * /institution/goals — Kurum geneli hedef özeti.
 *
 * Jinja kaynağı: app/templates/goals/institution_summary.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Hedef Analizi" };

export default async function InstitutionGoalsPage() {
  const data = await apiServer<InstitutionGoalsResponse>(
    "/api/v2/institution/goals",
  );
  return <GoalsClient initial={data} />;
}
