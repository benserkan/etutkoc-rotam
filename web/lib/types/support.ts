/**
 * Rol-bazlı talep sistemi (SupportRequest) tipleri.
 * Backend: app/routes/api_v2/schemas/support.py
 *
 * invalidate prefix'leri: "support:mine" · "support:inbox"
 */

export type SupportStatus =
  | "open"
  | "under_review"
  | "answered"
  | "resolved"
  | "withdrawn";

export interface SupportMessageItem {
  id: number;
  sender_id: number | null;
  sender_name: string;
  sender_role: string | null;
  is_me: boolean;
  body: string;
  created_at: string;
}

export interface SupportRequestListItem {
  id: number;
  subject: string;
  category: string;
  category_label: string;
  status: SupportStatus;
  status_label: string;
  audience: string;
  audience_label: string;
  requester_id: number;
  requester_name: string;
  requester_role: string;
  institution_id: number | null;
  institution_name: string | null;
  created_at: string;
  last_activity_at: string;
  message_count: number;
  last_message_preview: string | null;
  handled_by_name: string | null;
  resolved_at: string | null;
  is_mine: boolean;
  can_escalate: boolean;
}

export interface SupportRequestDetail extends SupportRequestListItem {
  messages: SupportMessageItem[];
}

export interface SupportCategoryOption {
  value: string;
  label: string;
}

export interface SupportListResponse {
  items: SupportRequestListItem[];
  pending_count: number;
  categories: SupportCategoryOption[];
}

export interface SupportRequestCreateBody {
  category: string;
  subject: string;
  body: string;
}

export interface SupportReplyBody {
  body: string;
}
