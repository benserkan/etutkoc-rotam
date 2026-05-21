import { apiServer } from "@/lib/api-server";
import type { NotificationHealthResponse } from "@/lib/types/admin";
import { SecurityNotificationsClient } from "@/components/admin/security-notifications-client";

/**
 * /admin/security-monitor/notifications — Bildirim teslimat sağlığı (G2a).
 *
 * Jinja kaynağı: notification_health panel + security_monitor_notifications.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Bildirim Sağlığı — Süper Admin" };

export default async function SecurityNotificationsPage() {
  const data = await apiServer<NotificationHealthResponse>(
    "/api/v2/admin/security-monitor/notifications",
  );
  return <SecurityNotificationsClient initial={data} />;
}
