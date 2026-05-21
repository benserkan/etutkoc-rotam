import { apiServer } from "@/lib/api-server";
import type { FeatureCatalogDashboardResponse } from "@/lib/types/admin";
import { AdminFeatureCatalogDashboardClient } from "@/components/admin/admin-feature-catalog-dashboard-client";

/**
 * /admin/feature-catalog/dashboard — Vitrin yönetim paneli (curator).
 *
 * Jinja kaynağı: admin.py:2299-2316 + feature_catalog_dashboard.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Vitrin Yönetimi — Süper Admin" };

export default async function AdminFeatureCatalogDashboardPage() {
  const data = await apiServer<FeatureCatalogDashboardResponse>(
    "/api/v2/admin/feature-catalog/dashboard",
  );
  return <AdminFeatureCatalogDashboardClient initial={data} />;
}
