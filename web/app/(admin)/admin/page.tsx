import { apiServer } from "@/lib/api-server";
import type { AdminDashboardResponse } from "@/lib/types/admin";
import { AdminDashboardClient } from "@/components/admin/admin-dashboard-client";

/**
 * /admin — Süper admin dashboard.
 *
 * Jinja kaynağı: admin.py:150-211 (admin_dashboard) + dashboard.html (476 satır)
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Süper Admin Paneli" };

export default async function AdminDashboardPage() {
  const data = await apiServer<AdminDashboardResponse>(
    "/api/v2/admin/dashboard",
  );
  return <AdminDashboardClient initial={data} />;
}
