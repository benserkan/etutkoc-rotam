import { apiServer } from "@/lib/api-server";
import type { FeatureCardFormResponse } from "@/lib/types/admin";
import { AdminFeatureCardFormClient } from "@/components/admin/admin-feature-card-form-client";

/**
 * /admin/feature-catalog/[id] — Vitrin kartı düzenleme formu.
 *
 * Jinja kaynağı: admin.py:2565-2603 + feature_catalog_form.html
 */
export const dynamic = "force-dynamic";

export default async function AdminFeatureCardEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await apiServer<FeatureCardFormResponse>(
    `/api/v2/admin/feature-catalog/${id}`,
  );
  return <AdminFeatureCardFormClient initial={data} mode="edit" />;
}
