import { apiServer } from "@/lib/api-server";
import type { CampaignDetailResponse } from "@/lib/types/admin";
import { AdminCampaignDetailClient } from "@/components/admin/admin-campaign-detail-client";

/**
 * /admin/revenue/campaigns/[id] — Kampanya detay (funnel + A/B + recipient).
 *
 * Jinja kaynağı: admin.py:5965-6154 + campaign_detail.html
 */
export const dynamic = "force-dynamic";

export default async function AdminCampaignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await apiServer<CampaignDetailResponse>(
    `/api/v2/admin/revenue/campaigns/${id}`,
  );
  return <AdminCampaignDetailClient initial={data} campaignId={Number(id)} />;
}
