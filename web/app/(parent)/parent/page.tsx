import { apiServer } from "@/lib/api-server";
import type { ParentDashboardResponse } from "@/lib/types/parent";
import { ParentDashboardClient } from "@/components/parent/parent-dashboard-client";

/**
 * /parent — Veli paneli dashboard.
 *
 * Jinja kaynağı: app/templates/parent/dashboard.html (107 satır)
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Veli Paneli" };

export default async function ParentDashboardPage() {
  const data = await apiServer<ParentDashboardResponse>(
    "/api/v2/parent/dashboard",
  );
  return <ParentDashboardClient initial={data} />;
}
