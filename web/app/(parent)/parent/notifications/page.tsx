import { apiServer } from "@/lib/api-server";
import type { ParentNotificationsResponse } from "@/lib/types/parent";
import { ParentNotificationsClient } from "@/components/parent/parent-notifications-client";

/**
 * /parent/notifications — Bildirim geçmişi.
 *
 * Jinja kaynağı: parent.py:315-325 + notifications.html (67 satır)
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Bildirim Geçmişi — Veli Paneli" };

export default async function ParentNotificationsPage() {
  const data = await apiServer<ParentNotificationsResponse>(
    "/api/v2/parent/notifications",
  );
  return <ParentNotificationsClient initial={data} />;
}
