import { apiServer } from "@/lib/api-server";
import type { SupportListResponse } from "@/lib/types/support";
import { SupportCenter } from "@/components/support/support-center";

/**
 * /admin/support — Talepler (bağımsız koç + kurum yöneticilerinden gelen).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Talepler" };

export default async function AdminSupportPage() {
  const initial = await apiServer<SupportListResponse>("/api/v2/support/inbox");
  return (
    <SupportCenter
      view="inbox"
      initial={initial}
      title="Talepler"
      description="Bağımsız koçlar ve kurum yöneticilerinden gelen talepler. İnceleyip yanıtlayın, çözümleyin."
    />
  );
}
