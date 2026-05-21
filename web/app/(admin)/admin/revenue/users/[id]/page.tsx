import { apiServer } from "@/lib/api-server";
import type { UserRevenue360Response } from "@/lib/types/admin";
import { AdminUser360Client } from "@/components/admin/admin-user-360-client";

/**
 * /admin/revenue/users/[id] — Bağımsız öğretmen 360.
 *
 * Jinja kaynağı: admin.py:3475-3697 + user_detail_revenue.html
 */
export const dynamic = "force-dynamic";

export default async function AdminUser360Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await apiServer<UserRevenue360Response>(
    `/api/v2/admin/revenue/users/${id}`,
  );
  return <AdminUser360Client initial={data} userId={Number(id)} />;
}
