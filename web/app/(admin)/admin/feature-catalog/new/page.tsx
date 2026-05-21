import { apiServer } from "@/lib/api-server";
import type { FeatureCardFormResponse } from "@/lib/types/admin";
import { AdminFeatureCardFormClient } from "@/components/admin/admin-feature-card-form-client";

/**
 * /admin/feature-catalog/new — Yeni vitrin kartı formu.
 *
 * Jinja kaynağı: admin.py:1958-1988 + feature_catalog_form.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Yeni Vitrin Kartı — Süper Admin" };

export default async function AdminFeatureCardNewPage() {
  const data = await apiServer<FeatureCardFormResponse>(
    "/api/v2/admin/feature-catalog/new",
  );
  return <AdminFeatureCardFormClient initial={data} mode="new" />;
}
