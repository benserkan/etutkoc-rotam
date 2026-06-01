/**
 * Manuel TypeScript tipleri — `/api/v2/me` ve `/api/v2/auth/*` için.
 *
 * Dalga 0'ın son paketinde openapi-typescript codegen pipeline'ı eklenecek;
 * o zaman bu dosya `lib/types/api.d.ts` (generated) ile değişir. Şimdilik
 * Pydantic şemalarıyla (`app/routes/api_v2/schemas/me.py`) birebir aynı şekil.
 */

export type UserRole =
  | "super_admin"
  | "institution_admin"
  | "teacher"
  | "student"
  | "parent";

export type ParentRelation = "anne" | "baba" | "vasi" | "diger";

export type DataRequestKind = "export" | "delete" | "rectify";

export type DataRequestStatus =
  | "pending"
  | "processing"
  | "completed"
  | "cancelled"
  | "rejected";

export interface UserPublic {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  institution_id: number | null;
  is_active: boolean;
  must_change_password: boolean;
  email_verified?: boolean;
  // P1 — cep telefonu SMS ile doğrulandı mı? Banner: false iken her panelin
  // üstünde kapatılamaz "Telefonunuzu doğrulayın" uyarısı kalır.
  phone_verified?: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface InstitutionRef {
  id: number;
  name: string;
  slug: string | null;
  has_logo?: boolean;
  logo_url?: string | null;
}

export interface ParentLinkRef {
  link_id: number;
  counterpart_id: number;
  counterpart_name: string;
  relation: ParentRelation;
  relation_label_tr: string;
  is_primary: boolean;
}

export interface DataRequestSummary {
  id: number;
  kind: DataRequestKind;
  kind_label_tr: string;
  status: DataRequestStatus;
  status_label_tr: string;
  reason: string | null;
  created_at: string;
  process_after: string | null;
  processed_at: string | null;
  can_cancel: boolean;
}

export interface KvkkStatus {
  has_pending_delete: boolean;
  pending_delete_request_id: number | null;
  pending_delete_scheduled_at: string | null;
  can_export: boolean;
}

export interface MyAccountResponse {
  user: UserPublic;
  institution: InstitutionRef | null;
  parent_links: ParentLinkRef[];
  kvkk_status: KvkkStatus;
  recent_requests: DataRequestSummary[];
  phone: MyPhoneInfo | null;
}

// P1 — telefon durumu (her iki slot)
export interface MyPhoneInfo {
  phone: string | null;
  phone_verified_at: string | null;
  phone_pending_verify: boolean;
  phone_pending_phone: string | null;
  phone_pending_expires_at: string | null;
  phone_dev_test_code: string | null;
  phone_secondary: string | null;
  phone_secondary_verified_at: string | null;
  phone_secondary_pending_verify: boolean;
  phone_secondary_pending_phone: string | null;
  phone_secondary_pending_expires_at: string | null;
  phone_secondary_dev_test_code: string | null;
  secondary_slot_available: boolean;
  /** Soft mod: SMS doğrulama operasyonel mi. False iken banner gizlenir +
   *  PhoneCard doğrulama formu yerine "yakında" bilgisi gösterir. */
  verification_available: boolean;
}

export interface StartPhoneVerificationBody {
  phone: string;
}

export interface VerifyPhoneBody {
  code: string;
}

export interface PhoneMutationResult {
  message: string;
  info: MyPhoneInfo;
}

export interface LoginResponse {
  user: UserPublic | null;
  must_change_password: boolean;
  two_factor_required?: boolean;
  challenge?: string | null;
}

/** Role'ün Türkçe okunur etiketi — UI'da role.value gösterimi yerine. */
export const ROLE_LABELS_TR: Record<UserRole, string> = {
  super_admin: "Sistem Yöneticisi",
  institution_admin: "Kurum Yöneticisi",
  teacher: "Öğretmen",
  student: "Öğrenci",
  parent: "Veli",
};

// Paket 3.5d.2 — Şifre değiştirme + data-delete body
export interface DataDeleteRequestBody {
  reason?: string | null;
  confirm: boolean;
}

export interface DataDeleteResponse {
  request_id: number;
  scheduled_at: string;
  can_cancel_until: string;
}

export interface PasswordChangeBody {
  current_password?: string | null;
  new_password: string;
  confirm_password: string;
}

export interface PasswordChangeResult {
  must_change_password: boolean;
  password_changed_at: string;
  role: UserRole;
}
