import { apiServer } from "@/lib/api-server";
import type { InstitutionRevenue360Response } from "@/lib/types/admin";
import { AdminInstitution360Client } from "@/components/admin/admin-institution-360-client";

/**
 * /admin/revenue/institutions/[id] — Kurum 360.
 *
 * Jinja kaynağı: admin.py:4217-4326 + institution_360.html
 */
export const dynamic = "force-dynamic";

export default async function AdminInstitution360Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await apiServer<InstitutionRevenue360Response>(
    `/api/v2/admin/revenue/institutions/${id}`,
  );
  return <AdminInstitution360Client initial={data} institutionId={Number(id)} />;
}
