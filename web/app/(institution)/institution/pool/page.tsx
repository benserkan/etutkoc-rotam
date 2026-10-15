import { apiServer } from "@/lib/api-server";
import type { InstitutionPoolOverviewResponse } from "@/lib/types/institution";
import { PoolOverviewClient } from "@/components/institution/pool-overview-client";

/**
 * /institution/pool — Haftalık Havuz Panosu (K54/K55).
 * Şube × son dönem havuz yüzdesi · seansı geciken öğrenci · rehber yükü.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Haftalık Havuz" };

export default async function InstitutionPoolPage() {
  const data = await apiServer<InstitutionPoolOverviewResponse>("/api/v2/institution/pool-overview");
  return <PoolOverviewClient initial={data} />;
}
