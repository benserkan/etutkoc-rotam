import { apiServer } from "@/lib/api-server";
import type { SupportListResponse } from "@/lib/types/support";
import { SupportCenter } from "@/components/support/support-center";

/**
 * /teacher/support — Destek/Talep.
 *
 * Bağımsız koç → Süper Yönetici; kuruma bağlı öğretmen → kendi Kurum Yöneticisi
 * (muhatap rolden otomatik türer). Öğrenci↔koç program talepleri ayrıdır
 * (/teacher/requests).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Destek" };

export default async function TeacherSupportPage() {
  const initial = await apiServer<SupportListResponse>("/api/v2/support/requests");
  return (
    <SupportCenter
      view="mine"
      initial={initial}
      canCreate
      title="Destek / Talep"
      description="Sistem yöneticinize veya kurum yöneticinize talep iletin; yanıtları buradan takip edin."
    />
  );
}
