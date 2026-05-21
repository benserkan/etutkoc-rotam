import { apiServer } from "@/lib/api-server";
import type { KvkkDashboardResponse } from "@/lib/types/admin";
import { AdminKvkkClient } from "@/components/admin/admin-kvkk-client";

/**
 * /admin/kvkk — KVKK denetim paneli.
 *
 * Jinja kaynağı: admin.py:3125-3234 + kvkk_dashboard.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "KVKK — Süper Admin" };

export default async function AdminKvkkPage() {
  const data = await apiServer<KvkkDashboardResponse>("/api/v2/admin/kvkk");
  return <AdminKvkkClient initial={data} />;
}
