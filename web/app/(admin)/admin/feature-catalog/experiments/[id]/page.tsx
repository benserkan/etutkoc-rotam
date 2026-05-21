import { apiServer } from "@/lib/api-server";
import type { ExperimentDetailResponse } from "@/lib/types/admin";
import { AdminFeatureExperimentDetailClient } from "@/components/admin/admin-feature-experiment-detail-client";

/**
 * /admin/feature-catalog/experiments/[id] — Deney detay + Wilson CI istatistik.
 *
 * Jinja kaynağı: admin.py:2468-2509 + feature_experiments_detail.html
 */
export const dynamic = "force-dynamic";

export default async function AdminFeatureExperimentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await apiServer<ExperimentDetailResponse>(
    `/api/v2/admin/feature-catalog/experiments/${id}`,
  );
  return (
    <AdminFeatureExperimentDetailClient initial={data} experimentId={Number(id)} />
  );
}
