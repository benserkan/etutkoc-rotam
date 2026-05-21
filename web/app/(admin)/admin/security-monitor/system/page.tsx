import { apiServer } from "@/lib/api-server";
import type { SystemHealthDataResponse } from "@/lib/types/admin";
import { SecuritySystemClient } from "@/components/admin/security-system-client";

/**
 * /admin/security-monitor/system — Sistem sağlığı kamerası (G2a).
 *
 * Jinja kaynağı: error_capture panel + security_monitor_system.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Sistem Sağlığı — Süper Admin" };

export default async function SecuritySystemPage() {
  const data = await apiServer<SystemHealthDataResponse>(
    "/api/v2/admin/security-monitor/system",
  );
  return <SecuritySystemClient initial={data} />;
}
