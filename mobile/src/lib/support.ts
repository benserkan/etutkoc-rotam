import { apiRequest } from "./api";

export interface SupportMessage {
  id: number;
  sender_id: number | null;
  sender_name: string;
  sender_role: string | null;
  is_me: boolean;
  body: string;
  created_at: string;
}
export interface SupportAttachment {
  id: number;
  filename: string;
  content_type: string;
  is_image: boolean;
}
export interface SupportListItem {
  id: number;
  subject: string;
  category: string;
  category_label: string;
  status: string;
  status_label: string;
  audience: string;
  audience_label: string;
  requester_id: number;
  requester_name: string;
  requester_role: string;
  target_user_id: number | null;
  target_user_name: string | null;
  institution_id: number | null;
  institution_name: string | null;
  created_at: string;
  last_activity_at: string;
  message_count: number;
  last_message_preview: string | null;
  handled_by_name: string | null;
  can_manage?: boolean;
}
export interface SupportDetail extends SupportListItem {
  messages: SupportMessage[];
  attachments: SupportAttachment[];
}
export interface SupportCategoryOption {
  value: string;
  label: string;
}
export interface SupportListResponse {
  items: SupportListItem[];
  pending_count: number;
  categories: SupportCategoryOption[];
}

export const supportKeys = {
  mine: ["support", "mine"] as const,
  inbox: ["support", "inbox"] as const,
  detail: (id: number) => ["support", "detail", id] as const,
};

export function getMyRequests(): Promise<SupportListResponse> {
  return apiRequest<SupportListResponse>(`/api/v2/support/requests`);
}
export function getSupportInbox(): Promise<SupportListResponse> {
  return apiRequest<SupportListResponse>(`/api/v2/support/inbox`);
}
export function getSupportRequest(id: number): Promise<SupportDetail> {
  return apiRequest<SupportDetail>(`/api/v2/support/requests/${id}`);
}
export function createSupportRequest(body: {
  category: string;
  subject: string;
  body: string;
}): Promise<unknown> {
  return apiRequest(`/api/v2/support/requests`, { method: "POST", body });
}
export function replySupportRequest(id: number, body: string): Promise<unknown> {
  return apiRequest(`/api/v2/support/requests/${id}/reply`, { method: "POST", body: { body } });
}
export function withdrawSupportRequest(id: number): Promise<unknown> {
  return apiRequest(`/api/v2/support/requests/${id}/withdraw`, { method: "POST" });
}
export function reviewSupportRequest(id: number): Promise<unknown> {
  return apiRequest(`/api/v2/support/requests/${id}/review`, { method: "POST" });
}
export function resolveSupportRequest(id: number): Promise<unknown> {
  return apiRequest(`/api/v2/support/requests/${id}/resolve`, { method: "POST" });
}
