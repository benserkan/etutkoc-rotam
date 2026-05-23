import { apiServer } from "@/lib/api-server";
import type { SupportListResponse } from "@/lib/types/support";
import { SupportCenter } from "@/components/support/support-center";

/**
 * /institution/support — Taleplerim (Kurum Yöneticisi → Süper Yönetici).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Taleplerim" };

export default async function InstitutionSupportPage() {
  const initial = await apiServer<SupportListResponse>("/api/v2/support/requests");
  return (
    <SupportCenter
      view="mine"
      initial={initial}
      canCreate
      title="Taleplerim"
      description="Süper yöneticiye ilettiğiniz talepler ve yanıtları."
    />
  );
}
