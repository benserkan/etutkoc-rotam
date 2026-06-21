import { api } from "@/lib/api";
import type { CampaignLinkListResponse } from "@/lib/types/campaign-link";

export const campaignLinkKeys = {
  list: () => ["admin", "me", "campaign-links"] as const,
};

export function getCampaignLinks(): Promise<CampaignLinkListResponse> {
  return api<CampaignLinkListResponse>("/api/v2/admin/campaign-links");
}
