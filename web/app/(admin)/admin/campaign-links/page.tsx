import { apiServer } from "@/lib/api-server";
import type { CampaignLinkListResponse } from "@/lib/types/campaign-link";
import { AdminCampaignLinksClient } from "@/components/admin/admin-campaign-links-client";

/**
 * /admin/campaign-links — Süper admin Kampanya / Genel Link (Yol A).
 *
 * Kişiye özel OLMAYAN, tekrar kullanılabilir markalı landing → WhatsApp grubuna
 * paylaş → tıklayan ad+telefon bırakır (lead) → İletişim Talepleri'nde aktive et.
 * Public sayfa: /kampanya/[token].
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Kampanya Linkleri — Süper Admin" };

export default async function AdminCampaignLinksPage() {
  const initial = await apiServer<CampaignLinkListResponse>("/api/v2/admin/campaign-links");
  return <AdminCampaignLinksClient initial={initial} />;
}
