import { apiRequest } from "./api";

// Click-to-WhatsApp — koç/kurum yöneticisi öğrenciye/veliye mesaj (wa.me linki).
// Backend yetki matrisi: koç → kendi öğrencisi + velisi; kurum → kurum içi.

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
  can_message?: boolean;
  sms_verification_live?: boolean;
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

export const messagingKeys = {
  templates: (category: string | null) => ["messaging", "templates", category ?? ""] as const,
  target: (userId: number) => ["messaging", "target", String(userId)] as const,
};

export function getMessagingTemplates(category: string | null = null): Promise<WaTemplatesListResponse> {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  return apiRequest<WaTemplatesListResponse>(`/api/v2/messaging/templates${qs}`);
}
export function getMessagingTarget(userId: number): Promise<WaTargetBrief> {
  return apiRequest<WaTargetBrief>(`/api/v2/messaging/target/${userId}`);
}
export function buildWaLink(body: WaLinkRequestBody): Promise<WaLinkResult> {
  return apiRequest<WaLinkResult>(`/api/v2/messaging/wa-link`, { method: "POST", body });
}
