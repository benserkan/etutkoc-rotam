import { apiServer } from "@/lib/api-server";
import type { CommHealthOverview } from "@/lib/types/admin";
import { CommunicationHealthClient } from "@/components/admin/communication-health-client";

/**
 * /admin/communication-health — İletişim Sağlığı (Faz 2c).
 *
 * Tüm kanalların (e-posta/push/whatsapp/sms) sağlığı + filtreli gönderim listesi.
 * Kaynak: communication_logs (comm_log servisi).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "İletişim Sağlığı — Süper Admin" };

export default async function CommunicationHealthPage() {
  const initial = await apiServer<CommHealthOverview>(
    "/api/v2/admin/communication-health?days=7",
  );
  return <CommunicationHealthClient initial={initial} />;
}
