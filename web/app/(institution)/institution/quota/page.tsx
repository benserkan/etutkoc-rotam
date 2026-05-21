import { apiServer } from "@/lib/api-server";
import type { QuotaResponse } from "@/lib/types/institution";
import { QuotaClient } from "@/components/institution/quota-client";

/**
 * /institution/quota — Kurum entity limitleri (Dalga 4 Paket 7).
 *
 * Jinja kaynağı: app/templates/institution/quota_dashboard.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kurum Limitleri" };

export default async function InstitutionQuotaPage() {
  const data = await apiServer<QuotaResponse>("/api/v2/institution/quota");
  return <QuotaClient initial={data} />;
}
