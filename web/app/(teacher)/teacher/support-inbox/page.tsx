import { apiServer } from "@/lib/api-server";
import type { SupportListResponse } from "@/lib/types/support";
import { SupportCenter } from "@/components/support/support-center";

/**
 * /teacher/support-inbox — Gelen Talepler (kurum yöneticisinden).
 *
 * Kurum yöneticisi, riskli öğrenci için "Koça ilet" ile koça müdahale talebi
 * açar (aşağı yönlü SupportRequest, audience=teacher). Koç bunları burada görür,
 * yanıtlar, çözümler. Bağımsız koçun kutusu boştur (hedef alınamaz).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Gelen Talepler" };

export default async function TeacherSupportInboxPage() {
  const initial = await apiServer<SupportListResponse>("/api/v2/support/inbox");
  return (
    <SupportCenter
      view="inbox"
      initial={initial}
      title="Gelen Talepler"
      description="Kurum yöneticinizden gelen müdahale talepleri (riskli öğrenci vb.). İnceleyip yanıtlayın, çözümleyin."
    />
  );
}
