import { apiServer } from "@/lib/api-server";
import type { SystemHealthResponse } from "@/lib/types/admin";
import { AdminSystemHealthClient } from "@/components/admin/admin-system-health-client";

/**
 * /admin/system-health — Cron + dispatcher + DB sağlık paneli.
 *
 * Jinja kaynağı: admin.py:3072-3088 + system_health.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Sistem Sağlığı — Süper Admin" };

export default async function AdminSystemHealthPage() {
  const data = await apiServer<SystemHealthResponse>(
    "/api/v2/admin/system-health",
  );
  return <AdminSystemHealthClient initial={data} />;
}
