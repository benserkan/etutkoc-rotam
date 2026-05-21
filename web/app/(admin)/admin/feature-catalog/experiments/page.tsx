import { apiServer } from "@/lib/api-server";
import type { ExperimentListResponse } from "@/lib/types/admin";
import { AdminFeatureExperimentsClient } from "@/components/admin/admin-feature-experiments-client";

/**
 * /admin/feature-catalog/experiments — A/B deney listesi.
 *
 * Jinja kaynağı: admin.py:2323-2355 + feature_experiments_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "A/B Deneyleri — Süper Admin" };

export default async function AdminFeatureExperimentsPage() {
  const data = await apiServer<ExperimentListResponse>(
    "/api/v2/admin/feature-catalog/experiments",
  );
  return <AdminFeatureExperimentsClient initial={data} />;
}
