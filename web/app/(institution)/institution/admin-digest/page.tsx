import { apiServer } from "@/lib/api-server";
import type { AdminDigestListResponse } from "@/lib/types/institution";
import { AdminDigestListClient } from "@/components/institution/admin-digest-list-client";

/**
 * /institution/admin-digest — Haftalık özet arşivi + manuel tetik.
 *
 * Jinja kaynağı: app/templates/institution/admin_digest_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Haftalık Yönetici Özeti" };

export default async function InstitutionAdminDigestPage() {
  const data = await apiServer<AdminDigestListResponse>(
    "/api/v2/institution/admin-digest",
  );
  return <AdminDigestListClient initial={data} />;
}
