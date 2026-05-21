import { apiServer } from "@/lib/api-server";
import type { AtRiskResponse } from "@/lib/types/institution";
import { AtRiskPrintSheet } from "@/components/institution/at-risk-print-sheet";

/**
 * /institution/at-risk/print — A4 portrait yazdırma.
 *
 * Jinja kaynağı: app/templates/institution/at_risk_print.html
 */
export const metadata = { title: "Risk Altındaki Öğrenciler — Yazdır" };
export const dynamic = "force-dynamic";

export default async function InstitutionAtRiskPrintPage() {
  const data = await apiServer<AtRiskResponse>("/api/v2/institution/at-risk");
  return <AtRiskPrintSheet data={data} />;
}
