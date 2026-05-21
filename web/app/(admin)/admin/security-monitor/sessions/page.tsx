import { apiServer } from "@/lib/api-server";
import type { SecurityOverviewResponse } from "@/lib/types/admin";
import { SecuritySessionsClient } from "@/components/admin/security-sessions-client";

/**
 * /admin/security-monitor/sessions — Oturumlar & IP'ler (G3).
 *
 * Jinja kaynağı: admin.py:5373-5403 + security_monitor_sessions.html (321).
 * Veri = G2a overview (get_security_dashboard_data + active_impersonations'ın
 * üst kümesi) — yeni GET endpoint açılmadı, overview yeniden kullanılır.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Oturumlar & IP — Süper Admin" };

export default async function SecuritySessionsPage() {
  const data = await apiServer<SecurityOverviewResponse>(
    "/api/v2/admin/security-monitor",
  );
  return <SecuritySessionsClient initial={data} />;
}
