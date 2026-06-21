/**
 * Ödeme tipleri (Paket Ö1 + Ö2a).
 *
 * Backend: /api/v2/payment/* — Iyzico Checkout Form + PaymentLink (kurumsal).
 */

export type PaymentStatus =
  | "pending"
  | "3ds_pending"
  | "succeeded"
  | "failed"
  | "expired"
  | "refunded";

export type PaymentCycle = "monthly" | "annual" | "one_time";

export type PaymentProvider = "iyzico" | "shopier" | "manual";

export interface PaymentProviderStatus {
  available: boolean;
  sandbox: boolean;
}

export interface PaymentInitBody {
  plan_code: string;
  cycle: "monthly" | "annual";
}

export interface PaymentInitResponse {
  transaction_id: number;
  payment_page_url: string;
  iyzico_token: string;
  amount: number;
  currency: string;
  plan_code: string;
  cycle: string;
}

export interface PaymentResult {
  transaction_id: number;
  status: PaymentStatus;
  status_label: string;
  status_reason: string | null;
  plan_code: string;
  cycle: string;
  amount: number;
  currency: string;
  created_at: string;
  completed_at: string | null;
}

export interface PaymentHistoryItem {
  id: number;
  provider: PaymentProvider;
  plan_code: string;
  cycle: string;
  amount: number;
  currency: string;
  status: PaymentStatus;
  status_label: string;
  created_at: string;
  completed_at: string | null;
}

export interface PaymentHistoryResponse {
  items: PaymentHistoryItem[];
  total: number;
}

// =====================================================================
// PaymentLink — süper admin kurum/koç için ödeme linki oluşturur
// =====================================================================

export type PaymentLinkOwnerType = "institution" | "user";

export type PaymentLinkStatus =
  | "active"
  | "consumed"
  | "expired"
  | "cancelled";

export interface PaymentLinkCreateBody {
  target_owner_type: PaymentLinkOwnerType;
  target_owner_id: number;
  plan_code: string;
  cycle: "monthly" | "annual";
  amount: number;
  description?: string | null;
  expires_in_days?: number | null;
}

export interface PaymentLinkItem {
  id: number;
  token: string;
  public_url: string;
  target_owner_type: PaymentLinkOwnerType;
  target_owner_id: number;
  target_owner_name: string | null;
  plan_code: string;
  cycle: string;
  amount: number;
  currency: string;
  description: string | null;
  status: PaymentLinkStatus;
  status_label: string;
  expires_at: string | null;
  consumed_at: string | null;
  consumed_by_user_id: number | null;
  consumed_by_user_name: string | null;
  consumed_transaction_id: number | null;
  created_by_admin_id: number | null;
  created_at: string;
}

export interface PaymentLinkListResponse {
  items: PaymentLinkItem[];
  total: number;
}

export interface PaymentLinkPublicInfo {
  token: string;
  target_owner_type: PaymentLinkOwnerType;
  target_owner_name: string;
  plan_code: string;
  plan_label: string;
  cycle: string;
  cycle_label: string;
  amount: number;
  currency: string;
  description: string | null;
  status: PaymentLinkStatus;
  status_label: string;
  expires_at: string | null;
  is_usable: boolean;
  can_pay: boolean;
  requires_login: boolean;
  provider_available: boolean;
  havale: PaymentLinkHavale | null;
}

export interface PaymentLinkHavale {
  enabled: boolean;
  iban: string;
  name: string;
  note: string;
}
