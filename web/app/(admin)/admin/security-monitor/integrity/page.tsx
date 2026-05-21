import { apiServer } from "@/lib/api-server";
import type { IntegrityResponse } from "@/lib/types/admin";
import { SecurityIntegrityClient } from "@/components/admin/security-integrity-client";

/**
 * /admin/security-monitor/integrity — Veri bütünlüğü kamerası (G2a).
 *
 * Jinja kaynağı: data_integrity panel + security_monitor_integrity.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Veri Bütünlüğü — Süper Admin" };

export default async function SecurityIntegrityPage() {
  const data = await apiServer<IntegrityResponse>(
    "/api/v2/admin/security-monitor/integrity",
  );
  return <SecurityIntegrityClient initial={data} />;
}
