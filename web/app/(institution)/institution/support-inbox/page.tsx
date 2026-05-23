import { apiServer } from "@/lib/api-server";
import type { SupportListResponse } from "@/lib/types/support";
import { SupportCenter } from "@/components/support/support-center";

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
    <SupportCenter
      view="inbox"
      initial={initial}
      title="Gelen Talepler"
      description="Kurumunuzdaki öğretmenlerden gelen talepler. İnceleyip yanıtlayın, çözümleyin."
    />
  );
}
