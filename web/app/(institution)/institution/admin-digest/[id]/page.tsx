import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { AdminDigestDetailResponse } from "@/lib/types/institution";
import { AdminDigestDetailClient } from "@/components/institution/admin-digest-detail-client";

/**
 * /institution/admin-digest/[id] — Tek bir özet kaydının detayı.
 *
 * Jinja kaynağı: app/templates/institution/admin_digest_detail.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Haftalık Özet Detayı" };

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function InstitutionAdminDigestDetailPage({
  params,
}: PageProps) {
  const { id } = await params;
  const parsed = Number(id);
  if (!Number.isFinite(parsed) || parsed <= 0) notFound();

  let data: AdminDigestDetailResponse;
  try {
    data = await apiServer<AdminDigestDetailResponse>(
      `/api/v2/institution/admin-digest/${parsed}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  return <AdminDigestDetailClient initial={data} digestId={parsed} />;
}
