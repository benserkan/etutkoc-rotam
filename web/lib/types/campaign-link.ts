/**
 * Kampanya / Genel Link tipleri (Yol A) — public markalı landing (grup paylaşımı).
 * Backend: /api/v2/admin/campaign-links (yönetim) + /api/v2/campaign/{token} (public).
 */

export interface CampaignPlanOption {
  code: string;
  label: string;
  audience: string; // solo | institution
  monthly: number | null;
  annual: number | null;
}

export interface CampaignLinkItem {
  id: number;
  token: string;
  name: string;
  audience: string; // coach | institution
  plan_code: string;
  plan_label: string;
  cycle: string;
  amount: number | null;
  title: string | null;
  status: string; // active | paused | archived
  status_label: string;
  view_count: number;
  lead_count: number;
  public_url: string;
  expires_at: string | null;
  created_at: string;
}

export interface CampaignLinkListResponse {
  items: CampaignLinkItem[];
  plan_options: CampaignPlanOption[];
}

export interface CreateCampaignLinkBody {
  name: string;
  plan_code: string;
  cycle: string;
  amount?: number | null;
  title?: string | null;
  message?: string | null;
  audience?: string | null;
  expires_in_days?: number | null;
}
