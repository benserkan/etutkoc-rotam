import { apiServer } from "@/lib/api-server";
import type { RevenueDashboardResponse } from "@/lib/types/admin";
import { AdminRevenueDashboardClient } from "@/components/admin/admin-revenue-dashboard-client";

/**
 * /admin/security-monitor/revenue — Ticari Pano ana dashboard.
 *
 * Jinja kaynağı: admin.py:3374-3426 + security_monitor_revenue.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Ticari Pano — Süper Admin" };

export default async function AdminRevenueDashboardPage() {
  const data = await apiServer<RevenueDashboardResponse>(
    "/api/v2/admin/security-monitor/revenue?segment=all",
  );
  return <AdminRevenueDashboardClient initial={data} />;
}
