// WhatsApp Üyelik Teklifi — süper admin tipleri (Paket 2)

export interface MembershipHavaleInfo {
  enabled: boolean;
  iban: string;
  name: string;
  note: string;
}

export interface MembershipPlanOption {
  code: string;
  label: string;
  audience: string; // "solo" | "institution"
  monthly: number;
  annual: number;
}

export interface MembershipOfferListItem {
  id: number;
  token: string;
  public_url: string;
  target_user_id: number | null;
  target_name: string | null;
  target_phone: string | null;
  offer_type: string; // "new" | "renewal"
  plan_code: string;
  plan_label: string;
  cycle: string; // "monthly" | "annual"
  amount: number | null;
  status: string;
  status_label: string;
  completion: string | null;
  completion_label: string;
  title: string | null;
  message: string | null;
  created_at: string;
  viewed: boolean;
}

export interface MembershipOfferListResponse {
  items: MembershipOfferListItem[];
  plan_options: MembershipPlanOption[];
}

export interface CreateMembershipOfferBody {
  target_user_id?: number | null;
  offer_type: string;
  plan_code: string;
  cycle: string;
  amount?: number | null;
  title?: string | null;
  message?: string | null;
  expires_in_days?: number | null;
}

export interface MembershipOfferCreated {
  id: number;
  token: string;
  public_url: string;
  plan_code: string;
  offer_type: string;
  cycle: string;
  amount: number | null;
  target_user_id: number | null;
  status: string;
}

export interface MembershipHavaleBody {
  iban: string;
  name: string;
  note: string;
}
