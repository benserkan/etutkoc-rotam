import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { AdminUserDetailResponse } from "@/lib/types/admin";
import { AdminUserDetailClient } from "@/components/admin/admin-user-detail-client";

/**
 * /admin/users/[id] — Kullanıcı detayı.
 *
 * Jinja kaynağı: admin.py:848-887 + user_detail.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kullanıcı Detayı — Süper Admin" };

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function AdminUserDetailPage({ params }: PageProps) {
  const { id } = await params;
  const uid = Number(id);
  if (!Number.isFinite(uid) || uid <= 0) notFound();

  let data: AdminUserDetailResponse;
  try {
    data = await apiServer<AdminUserDetailResponse>(
      `/api/v2/admin/users/${uid}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return <AdminUserDetailClient initial={data} userId={uid} />;
}
