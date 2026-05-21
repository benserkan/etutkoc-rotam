import { apiServer } from "@/lib/api-server";
import type { UsageResponse } from "@/lib/types/institution";
import { UsageClient } from "@/components/institution/usage-client";

/**
 * /institution/usage — Aylık kredi kullanımı (Dalga 4 Paket 7).
 *
 * Jinja kaynağı: app/templates/institution/usage_dashboard.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kredi Kullanımı" };

export default async function InstitutionUsagePage() {
  const data = await apiServer<UsageResponse>(
    "/api/v2/institution/usage?days=30",
  );
  return <UsageClient initial={data} />;
}
