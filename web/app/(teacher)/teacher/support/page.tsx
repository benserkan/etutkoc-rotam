import { apiServer } from "@/lib/api-server";
import type { SupportListResponse } from "@/lib/types/support";
import { SupportCenter } from "@/components/support/support-center";
import { DemoHint } from "@/components/demos/demo-hint";

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
    <div className="space-y-4">
      <DemoHint contextKey="support" role="teacher" />
      <SupportCenter
        view="mine"
        initial={initial}
        canCreate
        title="Destek / Talep"
        description="Sistem yöneticinize veya kurum yöneticinize talep iletin; yanıtları buradan takip edin."
      />
    </div>
  );
}
