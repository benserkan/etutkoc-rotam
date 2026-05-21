import { apiServer } from "@/lib/api-server";
import type { AlarmsResponse } from "@/lib/types/admin";
import { SecurityAlarmsClient } from "@/components/admin/security-alarms-client";

/**
 * /admin/security-monitor/alarms — Alarm Ayarları (G4).
 *
 * Jinja kaynağı: admin.py:5230-5342 + security_monitor_alarms.html (186).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Alarm Ayarları — Süper Admin" };

export default async function SecurityAlarmsPage() {
  const data = await apiServer<AlarmsResponse>(
    "/api/v2/admin/security-monitor/alarms",
  );
  return <SecurityAlarmsClient initial={data} />;
}
