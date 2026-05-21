import { apiServer } from "@/lib/api-server";
import type { SecurityOverviewResponse } from "@/lib/types/admin";
import { SecurityOverviewClient } from "@/components/admin/security-overview-client";

/**
 * /admin/security-monitor — Güvenlik Kamarası genel bakış (G2a).
 *
 * Jinja kaynağı: admin.py:3240-3277 + security_monitor.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Güvenlik Kamarası — Süper Admin" };

export default async function SecurityOverviewPage() {
  const data = await apiServer<SecurityOverviewResponse>(
    "/api/v2/admin/security-monitor",
  );
  return <SecurityOverviewClient initial={data} />;
}
