import { apiServer } from "@/lib/api-server";
import type { FeatureFlagsListResponse } from "@/lib/types/admin";
import { AdminFeatureFlagsClient } from "@/components/admin/admin-feature-flags-client";

/**
 * /admin/feature-flags — Özellik anahtarları listesi.
 *
 * Jinja kaynağı: admin.py:1633-1660 + feature_flags_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Özellik Anahtarları — Süper Admin" };

export default async function AdminFeatureFlagsPage() {
  const data = await apiServer<FeatureFlagsListResponse>(
    "/api/v2/admin/feature-flags",
  );
  return <AdminFeatureFlagsClient initial={data} />;
}
