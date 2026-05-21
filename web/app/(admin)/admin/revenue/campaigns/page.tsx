import { apiServer } from "@/lib/api-server";
import type { CampaignsListResponse } from "@/lib/types/admin";
import { AdminCampaignsClient } from "@/components/admin/admin-campaigns-client";

/**
 * /admin/revenue/campaigns — Toplu kampanya listesi.
 *
 * Jinja kaynağı: admin.py:5766-5803 + campaigns_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kampanyalar — Süper Admin" };

export default async function AdminCampaignsPage() {
  const data = await apiServer<CampaignsListResponse>(
    "/api/v2/admin/revenue/campaigns",
  );
  return <AdminCampaignsClient initial={data} />;
}
