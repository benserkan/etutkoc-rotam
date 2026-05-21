import { apiServer } from "@/lib/api-server";
import type { FeatureCatalogListResponse } from "@/lib/types/admin";
import { AdminFeatureCatalogClient } from "@/components/admin/admin-feature-catalog-client";

/**
 * /admin/feature-catalog — Vitrin kartları listesi.
 *
 * Jinja kaynağı: admin.py:1847-1955 + feature_catalog_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Vitrin Kartları — Süper Admin" };

export default async function AdminFeatureCatalogPage() {
  const data = await apiServer<FeatureCatalogListResponse>(
    "/api/v2/admin/feature-catalog",
  );
  return <AdminFeatureCatalogClient initial={data} />;
}
