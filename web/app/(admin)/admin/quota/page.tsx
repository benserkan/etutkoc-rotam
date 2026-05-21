import { apiServer } from "@/lib/api-server";
import type { AdminQuotaResponse } from "@/lib/types/admin";
import { AdminQuotaClient } from "@/components/admin/admin-quota-client";

/**
 * /admin/quota — Kurum limitleri + override yönetimi.
 *
 * Jinja kaynağı: admin.py:2922-2986 + quota_dashboard.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kurum Limitleri — Süper Admin" };

export default async function AdminQuotaPage() {
  const data = await apiServer<AdminQuotaResponse>("/api/v2/admin/quota");
  return <AdminQuotaClient initial={data} />;
}
