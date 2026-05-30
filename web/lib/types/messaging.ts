// P3-P4 — Click-to-WhatsApp tipleri

export interface WaTemplateVarBrief {
  key: string;
  label_tr: string;
  example: string;
}

export interface WaTemplateBrief {
  id: number;
  key: string;
  category: string;
  category_label_tr: string;
  name_tr: string;
  description: string;
  content_template: string;
  variables: WaTemplateVarBrief[];
  requires_date: boolean;
  allow_bulk: boolean;
  allow_freeform_note: boolean;
}

export interface WaTemplatesListResponse {
  items: WaTemplateBrief[];
  total: number;
  categories: Record<string, string>;
}

export interface WaTargetBrief {
  user_id: number;
  full_name: string;
  role: string;
  phone_masked: string;
  phone_verified: boolean;
}

export interface WaLinkRequestBody {
  template_id: number;
  target_user_id: number;
  variables: Record<string, string>;
  freeform_note?: string;
}

export interface WaLinkResult {
  wa_url: string;
  rendered_text: string;
  target_name: string;
  target_phone_masked: string;
  character_count: number;
  long_text: boolean;
  warnings: string[];
  log_id: number | null;
}

// ===== P5 — Toplu gönderim =====

export interface BulkTargetCandidate {
  user_id: number;
  full_name: string;
  role: string;
  phone_masked: string;
  phone_verified: boolean;
}

export interface BulkGroupOption {
  key: string;
  label_tr: string;
}

export interface BulkTargetsResponse {
  group_key: string;
  group_label_tr: string;
  eligible: BulkTargetCandidate[];
  no_phone: BulkTargetCandidate[];
  total: number;
  available_groups: BulkGroupOption[];
}

export interface BulkSendBody {
  template_id: number;
  target_user_ids: number[];
  variables: Record<string, string>;
  mode: "sequential" | "broadcast";
  freeform_note?: string;
}

export interface BulkDispatchItem {
  target_user_id: number;
  target_name: string;
  wa_url: string;
  phone_masked: string;
}

export interface BulkSkippedItem {
  target_user_id: number;
  target_name: string;
  reason: string;
}

export interface BulkSendResponse {
  mode: "sequential" | "broadcast";
  rendered_text: string;
  items: BulkDispatchItem[];
  skipped: BulkSkippedItem[];
  total_dispatched: number;
  total_skipped: number;
  long_text: boolean;
  warnings: string[];
}

// ===== P6 — Spam guard + admin audit =====

export interface DispatchStatsResponse {
  today_count: number;
  week_count: number;
  week_start_iso: string;
  warning_level: "ok" | "yogun" | "cok_yogun";
  warning_message: string | null;
}

export interface DispatchLogItem {
  id: number;
  sender_user_id: number;
  sender_name: string;
  sender_role: string;
  target_user_id: number | null;
  target_name: string;
  target_role: string | null;
  template_key: string;
  template_name_tr: string | null;
  character_count: number;
  created_at: string;
}

export interface TopSenderItem {
  sender_user_id: number;
  sender_name: string;
  sender_role: string;
  count: number;
}

export interface DispatchLogSummary {
  total_today: number;
  total_week: number;
  total_period: number;
  top_senders: TopSenderItem[];
}

export interface DispatchLogResponse {
  items: DispatchLogItem[];
  total: number;
  summary: DispatchLogSummary;
  days: number;
  sender_filter_id: number | null;
}
