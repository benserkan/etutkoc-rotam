import { apiServer } from "@/lib/api-server";
import type { DemoSessionListResponse } from "@/lib/types/admin";
import { AdminDemoSessionsClient } from "@/components/admin/admin-demo-sessions-client";

/**
 * /admin/demo-sessions — M5 ext
 *
 * Süper admin tarafından oluşturulan demo ekosistemlerin listesi. Her seans
 * bir kart olarak gösterilir; "Sil" tıklayınca seansa ait tüm kullanıcı +
 * kurum + örnek veri cascade temizlenir (yalnız is_demo=True kayıtlar).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Demo Hesaplar — Süper Admin" };

export default async function DemoSessionsPage() {
  const data = await apiServer<DemoSessionListResponse>(
    "/api/v2/admin/demo-sessions",
  );
  return <AdminDemoSessionsClient initial={data} />;
}
