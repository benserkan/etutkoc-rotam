import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { InstitutionDetailResponse } from "@/lib/types/admin";
import { AdminInstitutionDetailClient } from "@/components/admin/admin-institution-detail-client";

/**
 * /admin/institutions/[id] — Kurum detayı.
 *
 * Jinja kaynağı: admin.py:326-377 + institution_detail.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kurum Detayı — Süper Admin" };

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function AdminInstitutionDetailPage({
  params,
}: PageProps) {
  const { id } = await params;
  const iid = Number(id);
  if (!Number.isFinite(iid) || iid <= 0) notFound();

  let data: InstitutionDetailResponse;
  try {
    data = await apiServer<InstitutionDetailResponse>(
      `/api/v2/admin/institutions/${iid}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return <AdminInstitutionDetailClient initial={data} institutionId={iid} />;
}
