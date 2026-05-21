import { apiServer } from "@/lib/api-server";
import type { AtRiskResponse } from "@/lib/types/institution";
import { AtRiskClient } from "@/components/institution/at-risk-client";

/**
 * /institution/at-risk — Risk altındaki öğrenciler (privacy korumalı).
 *
 * Jinja kaynağı: app/templates/institution/at_risk_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Risk Paneli" };

export default async function InstitutionAtRiskPage() {
  const data = await apiServer<AtRiskResponse>("/api/v2/institution/at-risk");
  return <AtRiskClient initial={data} />;
}
