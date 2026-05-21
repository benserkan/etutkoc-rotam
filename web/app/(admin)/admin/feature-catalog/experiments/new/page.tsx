import { apiServer } from "@/lib/api-server";
import type { ExperimentFormMeta } from "@/lib/types/admin";
import { AdminFeatureExperimentFormClient } from "@/components/admin/admin-feature-experiment-form-client";

/**
 * /admin/feature-catalog/experiments/new — Yeni A/B deney formu.
 *
 * Jinja kaynağı: admin.py:2358-2381 + feature_experiments_form.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Yeni A/B Deneyi — Süper Admin" };

export default async function AdminFeatureExperimentNewPage() {
  const meta = await apiServer<ExperimentFormMeta>(
    "/api/v2/admin/feature-catalog/experiments/new",
  );
  return <AdminFeatureExperimentFormClient meta={meta} />;
}
