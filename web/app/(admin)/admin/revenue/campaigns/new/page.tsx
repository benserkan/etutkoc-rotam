import { apiServer } from "@/lib/api-server";
import type { CampaignFormMeta } from "@/lib/types/admin";
import { AdminCampaignFormClient } from "@/components/admin/admin-campaign-form-client";

/**
 * /admin/revenue/campaigns/new — Yeni toplu kampanya.
 *
 * Jinja kaynağı: admin.py:5806-5961 + campaign_form.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Yeni Kampanya — Süper Admin" };

export default async function AdminCampaignNewPage() {
  const meta = await apiServer<CampaignFormMeta>(
    "/api/v2/admin/revenue/campaigns/new",
  );
  return <AdminCampaignFormClient meta={meta} />;
}
