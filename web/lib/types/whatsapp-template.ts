// P2 — WhatsApp şablon registry frontend tipleri

export type WaTemplateCategory =
  | "veli"
  | "ogrenci"
  | "kurum_ogretmen"
  | "kurum_veli"
  | "kurum_ogrenci"
  | "admin_yonetici"
  | "admin_sistem";

export type WaTemplateTargetRole =
  | "teacher"
  | "institution_admin"
  | "super_admin"
  | "any";

export interface WaTemplateVar {
  key: string;
  label_tr: string;
  example: string;
}

export interface WaTemplateItem {
  id: number;
  key: string;
  category: WaTemplateCategory | string;
  category_label_tr: string;
  target_role: WaTemplateTargetRole | string;
  target_role_label_tr: string;
  name_tr: string;
  description: string;
  content_template: string;
  variables: WaTemplateVar[];
  requires_date: boolean;
  allow_bulk: boolean;
  allow_freeform_note: boolean;
  sort_order: number;
  is_active: boolean;
  updated_at: string;
  updated_by_name: string | null;
}

export interface WaTemplateListResponse {
  items: WaTemplateItem[];
  total: number;
  categories: Record<string, string>;
  target_roles: Record<string, string>;
}

export interface WaTemplateCreateBody {
  key: string;
  category: string;
  target_role: string;
  name_tr: string;
  description: string;
  content_template: string;
  variables: WaTemplateVar[];
  requires_date: boolean;
  allow_bulk: boolean;
  allow_freeform_note: boolean;
  sort_order: number;
  is_active: boolean;
}

// Update body: key haricinde her şey
export type WaTemplateUpdateBody = Omit<WaTemplateCreateBody, "key">;

export interface WaTemplatePreviewBody {
  content_template: string;
  variables: Record<string, string>;
  variable_defs: WaTemplateVar[];
}

export interface WaTemplatePreviewResult {
  rendered: string;
  warnings: string[];
  used_keys: string[];
  missing_keys: string[];
  unknown_keys: string[];
}

export interface WaTemplateToggleResult {
  message: string;
  is_active: boolean;
}

export interface WaTemplateDeleteResult {
  message: string;
}
