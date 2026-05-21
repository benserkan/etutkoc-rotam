import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { FeatureFlagDetailResponse } from "@/lib/types/admin";
import { AdminFeatureFlagDetailClient } from "@/components/admin/admin-feature-flag-detail-client";

/**
 * /admin/feature-flags/[id] — Flag detayı + override yönetimi.
 *
 * Jinja kaynağı: admin.py:1663-1698 + feature_flag_detail.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Özellik Anahtarı — Süper Admin" };

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function AdminFeatureFlagDetailPage({
  params,
}: PageProps) {
  const { id } = await params;
  const fid = Number(id);
  if (!Number.isFinite(fid) || fid <= 0) notFound();

  let data: FeatureFlagDetailResponse;
  try {
    data = await apiServer<FeatureFlagDetailResponse>(
      `/api/v2/admin/feature-flags/${fid}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return <AdminFeatureFlagDetailClient initial={data} flagId={fid} />;
}
