import { apiServer } from "@/lib/api-server";
import type { InstitutionDashboardResponse } from "@/lib/types/institution";
import { DashboardClient } from "@/components/institution/dashboard-client";

/**
 * /institution — Server Component initial fetch + Client interaktif.
 *
 * Jinja kaynağı: app/templates/institution/dashboard.html
 *
 * R-007: cache "no-store" + dynamic = "force-dynamic" — App Router cache yok.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Kurum panosu",
};

export default async function InstitutionDashboardPage() {
  const data = await apiServer<InstitutionDashboardResponse>(
    "/api/v2/institution/dashboard",
  );
  return <DashboardClient initial={data} />;
}
