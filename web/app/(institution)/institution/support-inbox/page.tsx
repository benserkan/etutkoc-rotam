import { apiServer } from "@/lib/api-server";
import type { SupportListResponse } from "@/lib/types/support";
import { SupportCenter } from "@/components/support/support-center";
import { DemoHint } from "@/components/demos/demo-hint";

/**
 * /institution/support-inbox — Gelen Talepler (kurumdaki öğretmenlerden).
 *
 * Tenant izolasyonu backend'de: yalnız kendi kurumunun talepleri görünür.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Gelen Talepler" };

export default async function InstitutionSupportInboxPage() {
  const initial = await apiServer<SupportListResponse>("/api/v2/support/inbox");
  return (
    <div className="space-y-4">
      <DemoHint contextKey="requests" role="institution_admin" />
      <SupportCenter
        view="inbox"
        initial={initial}
        title="Gelen Talepler"
        description="Kurumunuzdaki öğretmenlerden gelen talepler. İnceleyip yanıtlayın, çözümleyin."
      />
    </div>
  );
}
