"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import { uploadInstitutionLogo } from "@/lib/api/admin";
import type {
  AccountArchiveBody,
  AccountArchiveResult,
  AccountBulkArchiveBody,
  AccountUnarchiveBody,
  AdminImpersonateBody,
  AdminImpersonateEndResult,
  AdminImpersonateResult,
  AdminUserChangeRoleBody,
  AdminUserCreateBody,
  AdminUserCreateResult,
  AdminUserEditBody,
  AdminUserMutationResult,
  AnnouncementCreateBody,
  AnnouncementMutationResult,
  DiscoveryBulkBody,
  DiscoveryMutationResult,
  DiscoveryScanResult,
  ExperimentCreateBody,
  ExperimentMutationResult,
  ExperimentStatusBody,
  FeatureCardBody,
  FeatureCardMutationResult,
  FeatureCardPinBody,
  FeatureCardStatusBody,
  FeatureFlagMutationResult,
  FeatureFlagOverrideBody,
  QuickActionBody,
  RevenueMutationResult,
  CrmActionBody,
  CrmActionCompleteBody,
  CrmNoteBody,
  OwnerContactBody,
  OwnerTagBody,
  OwnerType,
  Revenue360MutationResult,
  ActionTemplateBody,
  ActionTemplateMutationResult,
  InvoiceCancelBody,
  InvoiceMarkPaidBody,
  InvoiceMutationResult,
  InvoicePostponeBody,
  InvoiceReminderBody,
  OfferBody,
  RevenueOfferMutationResult,
  CampaignBody,
  CampaignMutationResult,
  CampaignPreviewBody,
  CampaignPreviewResponse,
  SystemMutationResult,
  SecurityActionResult,
  AlarmRuleUpdateBody,
  AlarmScanResult,
  AbuseScanResult,
  AbuseRemediateResult,
  InstitutionCreateBody,
  InstitutionEditBody,
  InstitutionMutationResult,
  KvkkMutationResult,
  KvkkRejectBody,
  QuotaMutationResult,
  QuotaOverrideBody,
  UsageBonusBody,
  UsageMutationResult,
  AiSettingsResponse,
  SetAiSettingBody,
  PricingAdminResponse,
  PricingConfig,
  ContactRequestMutationResult,
  OnboardInstitutionBody,
  OnboardInstitutionResult,
} from "@/lib/types/admin";

/**
 * Süper Admin mutation hook'ları (Dalga 6 P2+).
 *
 * Sözleşme:
 *   - Mutation onSuccess'te `applyInvalidate(qc, res.invalidate)` ile
 *     "admin:dashboard", "admin:institutions", "admin:account-history" prefix'leri
 *     yeniden bayatlatılır
 *   - Hata kodları (slug_taken, name_required, vb.) Türkçe başlıkla toast
 */

function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.detail?.message ?? fallback;
  return fallback;
}

function errorCode(e: unknown): string | undefined {
  if (e instanceof ApiError) return e.detail?.code;
  return undefined;
}

function errorTitle(e: unknown, fallback: string): string {
  const code = errorCode(e);
  switch (code) {
    case "name_required":
      return "Kurum adı zorunlu";
    case "slug_taken":
      return "Slug zaten kullanılıyor";
    case "institution_not_found":
      return "Kurum bulunamadı";
    case "user_not_found":
      return "Kullanıcı bulunamadı";
    case "invalid_owner_type":
      return "Geçersiz sahip türü";
    case "name_or_email_required":
      return "Ad ve e-posta zorunlu";
    case "invalid_role":
      return "Geçersiz rol";
    case "email_taken":
      return "E-posta zaten kayıtlı";
    case "institution_required":
      return "Kurum seçimi zorunlu";
    case "cannot_change_own_role":
      return "Kendi rolünü değiştiremezsin";
    case "cannot_delete_self":
      return "Kendi hesabını silemezsin";
    case "cannot_impersonate_self":
      return "Kendin olarak sahte oturum açamazsın";
    case "cannot_impersonate_super_admin":
      return "Diğer süper admin olarak oturum açamazsın";
    case "target_inactive":
      return "Pasif kullanıcı";
    case "invalid_reason":
      return "Gerekçe geçersiz";
    case "no_impersonation_session":
      return "Sahte oturum yok";
    case "message_required":
      return "Mesaj zorunlu";
    case "invalid_datetime":
      return "Tarih formatı hatalı";
    case "announcement_not_found":
      return "Duyuru bulunamadı";
    case "kvkk_request_not_found":
      return "Talep bulunamadı";
    case "only_delete_can_be_applied":
      return "Yalnız silme talepleri uygulanabilir";
    case "kvkk_already_closed":
      return "Bu talep zaten kapatıldı";
    case "account_not_found":
      return "Hesap bulunamadı";
    case "invalid_bonus_amount":
      return "Bonus 1-100000 arasında olmalı";
    case "invalid_quota_key":
      return "Geçersiz kuota anahtarı";
    case "invalid_override_value":
      return "Geçersiz limit değeri";
    case "override_not_found":
      return "Override bulunamadı";
    case "flag_not_found":
      return "Flag bulunamadı";
    case "feature_card_invalid":
      return "Kart bilgileri geçersiz";
    case "card_not_found":
      return "Kart bulunamadı";
    case "experiment_not_found":
      return "Deney bulunamadı";
    case "weights_invalid":
      return "Ağırlık toplamı 100 olmalı";
    case "invalid_status":
      return "Geçersiz durum";
    case "no_ids":
      return "Aday seçilmedi";
    case "invalid_action_kind":
      return "Geçersiz aksiyon tipi";
    case "content_required":
      return "Not içeriği boş olamaz";
    case "summary_required":
      return "Özet boş olamaz";
    case "note_not_found":
      return "Not bulunamadı";
    case "action_not_found":
      return "Aksiyon bulunamadı";
    case "tag_not_found":
      return "Etiket bulunamadı";
    case "invalid_tag_kind":
      return "Geçersiz etiket türü";
    case "teacher_not_found":
      return "Bağımsız öğretmen bulunamadı";
    case "invalid_result":
      return "Geçersiz sonuç";
    case "invalid_offer_kind":
      return "Geçersiz teklif türü";
    case "offer_not_found":
      return "Teklif bulunamadı";
    case "offer_send_failed":
      return "Teklif gönderilemedi";
    case "offer_cancel_failed":
      return "Teklif iptal edilemedi";
    case "invoice_not_found":
      return "Fatura bulunamadı";
    case "invoice_not_eligible":
      return "Bu fatura için uygun değil";
    case "invoice_already_paid":
      return "Fatura zaten ödendi";
    case "reminder_failed":
      return "Hatırlatma gönderilemedi";
    case "template_invalid":
      return "Şablon geçersiz";
    case "template_not_found":
      return "Şablon bulunamadı";
    case "invalid_segment":
      return "Geçersiz segment";
    case "campaign_invalid":
      return "Kampanya bilgileri geçersiz";
    case "campaign_not_found":
      return "Kampanya bulunamadı";
    case "campaign_launch_failed":
      return "Kampanya başlatılamadı";
    case "campaign_pause_failed":
      return "Kampanya duraklatılamadı";
    case "campaign_resume_failed":
      return "Kampanya devam ettirilemedi";
    case "campaign_complete_failed":
      return "Kampanya tamamlanamadı";
    case "campaign_cancel_failed":
      return "Kampanya iptal edilemedi";
    case "error_not_found":
      return "Hata kaydı bulunamadı";
    case "session_not_found":
      return "Oturum bulunamadı";
    case "ip_required":
      return "IP boş olamaz";
    case "ip_not_found":
      return "IP kaydı yok";
    case "impersonation_not_found":
      return "Sahte oturum bulunamadı";
    case "alarm_not_found":
      return "Alarm bulunamadı";
    case "alarm_rule_not_found":
      return "Alarm kuralı bulunamadı";
    case "abuse_signal_not_found":
      return "Sinyal bulunamadı";
    case "remediation_failed":
      return "Aksiyon uygulanamadı";
    default:
      return fallback;
  }
}

// =============================================================================
// Institutions — create / edit / delete
// =============================================================================

export function useCreateInstitution() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<InstitutionMutationResult>,
    Error,
    InstitutionCreateBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<InstitutionMutationResult>>(
        "/api/v2/admin/institutions",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kurum oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useEditInstitution(institutionId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<InstitutionMutationResult>,
    Error,
    InstitutionEditBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<InstitutionMutationResult>>(
        `/api/v2/admin/institutions/${institutionId}`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Güncelleme başarısız"), {
        description: errorMessage(e, "Kurum güncellenemedi."),
      });
    },
  });
}

export function useDeleteInstitution(institutionId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<InstitutionMutationResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<InstitutionMutationResult>>(
        `/api/v2/admin/institutions/${institutionId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Silme başarısız"), {
        description: errorMessage(e, "Kurum silinemedi."),
      });
    },
  });
}

/** Kurum logosu yükle (co-branding, multipart). */
export function useUploadInstitutionLogo(institutionId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<InstitutionMutationResult>, Error, File>({
    mutationFn: (file) => uploadInstitutionLogo(institutionId, file),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Logo yüklenemedi"), {
        description: errorMessage(e, "Logo yüklenemedi."),
      });
    },
  });
}

/** Kurum logosunu kaldır (varsayılan platform markasına döner). */
export function useDeleteInstitutionLogo(institutionId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<InstitutionMutationResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<InstitutionMutationResult>>(
        `/api/v2/admin/institutions/${institutionId}/logo/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kaldırma başarısız"), {
        description: errorMessage(e, "Logo kaldırılamadı."),
      });
    },
  });
}

// =============================================================================
// Account history — archive / unarchive / bulk
// =============================================================================

export function useAccountHistoryArchive() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AccountArchiveResult>,
    Error,
    AccountArchiveBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<AccountArchiveResult>>(
        "/api/v2/admin/account-history/archive",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      if (res.data.ok) {
        toast.success(res.data.message ?? "Kayıt arşivlendi");
      } else {
        toast.error("Arşivleme başarısız", {
          description: res.data.error ?? "Bilinmeyen hata",
        });
      }
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Arşivleme başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useAccountHistoryUnarchive() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AccountArchiveResult>,
    Error,
    AccountUnarchiveBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<AccountArchiveResult>>(
        "/api/v2/admin/account-history/unarchive",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      if (res.data.ok) {
        toast.success(res.data.message ?? "Arşivden çıkarıldı");
      } else {
        toast.error("Çıkarma başarısız", {
          description: res.data.error ?? "Bilinmeyen hata",
        });
      }
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Çıkarma başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useAccountHistoryBulkArchive() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AccountArchiveResult>,
    Error,
    AccountBulkArchiveBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<AccountArchiveResult>>(
        "/api/v2/admin/account-history/bulk-archive",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message ?? "Toplu arşivleme tamamlandı");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Toplu arşivleme başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P3 — Users
// =============================================================================

export function useCreateAdminUser() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AdminUserCreateResult>,
    Error,
    AdminUserCreateBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<AdminUserCreateResult>>("/api/v2/admin/users", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      // Toast yerine dialog ile temp_password gösterilecek — caller handles
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kullanıcı oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useEditAdminUser(userId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AdminUserMutationResult>,
    Error,
    AdminUserEditBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<AdminUserMutationResult>>(
        `/api/v2/admin/users/${userId}`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Güncelleme başarısız"), {
        description: errorMessage(e, "Kullanıcı güncellenemedi."),
      });
    },
  });
}

export function useResetUserPassword(userId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AdminUserMutationResult>,
    Error,
    void
  >({
    mutationFn: () =>
      api<MutationResponse<AdminUserMutationResult>>(
        `/api/v2/admin/users/${userId}/reset-password`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      // Toast yerine dialog ile temp_password gösterilecek — caller handles
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Şifre sıfırlanamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useChangeUserRole(userId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AdminUserMutationResult>,
    Error,
    AdminUserChangeRoleBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<AdminUserMutationResult>>(
        `/api/v2/admin/users/${userId}/change-role`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Rol değişimi başarısız"), {
        description: errorMessage(e, "Rol değiştirilemedi."),
      });
    },
  });
}

export function useActivateUserPlan(userId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AdminUserMutationResult>,
    Error,
    { plan: string; cycle?: string }
  >({
    mutationFn: (body) =>
      api<MutationResponse<AdminUserMutationResult>>(
        `/api/v2/admin/users/${userId}/activate-plan`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Aktivasyon başarısız"), {
        description: errorMessage(e, "Plan aktive edilemedi."),
      });
    },
  });
}

export function useDeleteAdminUser(userId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AdminUserMutationResult>,
    Error,
    void
  >({
    mutationFn: () =>
      api<MutationResponse<AdminUserMutationResult>>(
        `/api/v2/admin/users/${userId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Silme başarısız"), {
        description: errorMessage(e, "Kullanıcı silinemedi."),
      });
    },
  });
}

// =============================================================================
// P3 — Impersonate (no qc invalidate — session change)
// =============================================================================

export function useImpersonateUser(userId: number) {
  // eslint-disable-next-line lgs/missing-invalidate
  return useMutation<AdminImpersonateResult, Error, AdminImpersonateBody>({
    mutationFn: (body) =>
      api<AdminImpersonateResult>(
        `/api/v2/admin/users/${userId}/impersonate`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => {
      toast.error(errorTitle(e, "Sahte oturum açılamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useEndImpersonation() {
  // eslint-disable-next-line lgs/missing-invalidate
  return useMutation<AdminImpersonateEndResult, Error, void>({
    mutationFn: () =>
      api<AdminImpersonateEndResult>("/api/v2/admin/impersonate/end", {
        method: "POST",
      }),
    onError: (e) => {
      toast.error(errorTitle(e, "Sahte oturum kapatılamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P4 — Announcements
// =============================================================================

export function useCreateAnnouncement() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AnnouncementMutationResult>,
    Error,
    AnnouncementCreateBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<AnnouncementMutationResult>>(
        "/api/v2/admin/announcements",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Duyuru oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useDeleteAnnouncement(announcementId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AnnouncementMutationResult>,
    Error,
    void
  >({
    mutationFn: () =>
      api<MutationResponse<AnnouncementMutationResult>>(
        `/api/v2/admin/announcements/${announcementId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Duyuru silinemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// İletişim talepleri
// =============================================================================

export interface ContactRequestUpdateBody {
  status: string;
  admin_note?: string;
}

export function useUpdateContactRequest(requestId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ContactRequestMutationResult>,
    Error,
    ContactRequestUpdateBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<ContactRequestMutationResult>>(
        `/api/v2/admin/contact-requests/${requestId}`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Talep güncellendi");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Güncelleme başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

/**
 * Talepten Aktivasyona — tek transaction'da kurum + yönetici + ödeme linki +
 * e-posta. Backend `contact-requests/{id}/onboard`.
 */
export function useOnboardInstitution(requestId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<OnboardInstitutionResult>,
    Error,
    OnboardInstitutionBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<OnboardInstitutionResult>>(
        `/api/v2/admin/contact-requests/${requestId}/onboard`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      // Toast değil — sonuç dialog'da gösterilir (temp_password + link)
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Aktivasyon başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata."),
      });
    },
  });
}

// =============================================================================
// P4 — KVKK
// =============================================================================

export function useKvkkApply(requestId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<KvkkMutationResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<KvkkMutationResult>>(
        `/api/v2/admin/kvkk/requests/${requestId}/apply`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Uygulama başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useKvkkReject(requestId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<KvkkMutationResult>,
    Error,
    KvkkRejectBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<KvkkMutationResult>>(
        `/api/v2/admin/kvkk/requests/${requestId}/reject`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Reddetme başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P5 — Usage
// =============================================================================

export function useHardBlockToggle(institutionId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<UsageMutationResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<UsageMutationResult>>(
        `/api/v2/admin/usage/institution/${institutionId}/hard-block`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İşlem başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useAddBonus(ownerType: "institution" | "user", ownerId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<UsageMutationResult>,
    Error,
    UsageBonusBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<UsageMutationResult>>(
        `/api/v2/admin/usage/${ownerType}/${ownerId}/bonus`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Bonus eklenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P5 — Quota
// =============================================================================

export function useSetQuotaOverride(institutionId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<QuotaMutationResult>,
    Error,
    QuotaOverrideBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<QuotaMutationResult>>(
        `/api/v2/admin/quota/${institutionId}/override`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Özel limit kaydedilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useRemoveQuotaOverride(overrideId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<QuotaMutationResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<QuotaMutationResult>>(
        `/api/v2/admin/quota/overrides/${overrideId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Override silinemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P5 — Feature flags
// =============================================================================

export function useToggleFeatureFlag(flagId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<FeatureFlagMutationResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<FeatureFlagMutationResult>>(
        `/api/v2/admin/feature-flags/${flagId}/toggle`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Toggle başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useAddFeatureFlagOverride(flagId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<FeatureFlagMutationResult>,
    Error,
    FeatureFlagOverrideBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<FeatureFlagMutationResult>>(
        `/api/v2/admin/feature-flags/${flagId}/overrides`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Override eklenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useRemoveFeatureFlagOverride(overrideId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<FeatureFlagMutationResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<FeatureFlagMutationResult>>(
        `/api/v2/admin/feature-flags/overrides/${overrideId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Override silinemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P6 — Feature Catalog (kartlar + onay kuyruğu + A/B deneyler)
// =============================================================================

export function useCreateFeatureCard() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<FeatureCardMutationResult>,
    Error,
    FeatureCardBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<FeatureCardMutationResult>>(
        "/api/v2/admin/feature-catalog",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kart oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useUpdateFeatureCard(cardId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<FeatureCardMutationResult>,
    Error,
    FeatureCardBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<FeatureCardMutationResult>>(
        `/api/v2/admin/feature-catalog/${cardId}`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kart güncellenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useSetFeatureCardStatus(cardId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<FeatureCardMutationResult>,
    Error,
    FeatureCardStatusBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<FeatureCardMutationResult>>(
        `/api/v2/admin/feature-catalog/${cardId}/status`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Durum değiştirilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useSetFeatureCardPin(cardId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<FeatureCardMutationResult>,
    Error,
    FeatureCardPinBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<FeatureCardMutationResult>>(
        `/api/v2/admin/feature-catalog/${cardId}/pin`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Sabitleme başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useDeleteFeatureCard(cardId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<FeatureCardMutationResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<FeatureCardMutationResult>>(
        `/api/v2/admin/feature-catalog/${cardId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kart silinemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useRejectDiscoveryCard() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<DiscoveryMutationResult>,
    Error,
    number
  >({
    mutationFn: (cardId) =>
      api<MutationResponse<DiscoveryMutationResult>>(
        `/api/v2/admin/feature-catalog/${cardId}/reject`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Reddetme başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useBulkDiscovery() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<DiscoveryMutationResult>,
    Error,
    DiscoveryBulkBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<DiscoveryMutationResult>>(
        "/api/v2/admin/feature-catalog/discovery-queue/bulk",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Toplu işlem başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

/** "Şimdi tara" — migration + commit'leri tarayıp yeni keşif kartı açar. */
export function useScanDiscovery() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<DiscoveryScanResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<DiscoveryScanResult>>(
        "/api/v2/admin/feature-catalog/discovery-queue/scan",
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        res.data.created > 0 ? `${res.data.created} yeni kart açıldı` : "Tarama tamam",
        { description: res.data.message },
      );
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Tarama başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useCreateExperiment() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ExperimentMutationResult>,
    Error,
    ExperimentCreateBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<ExperimentMutationResult>>(
        "/api/v2/admin/feature-catalog/experiments",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Deney oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useSetExperimentStatus(experimentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ExperimentMutationResult>,
    Error,
    ExperimentStatusBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<ExperimentMutationResult>>(
        `/api/v2/admin/feature-catalog/experiments/${experimentId}/status`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Durum değiştirilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P7a — Revenue: Aksiyon Merkezi hızlı aksiyon
// =============================================================================

export function useRevenueQuickAction() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<RevenueMutationResult>,
    Error,
    QuickActionBody
  >({
    mutationFn: (body) =>
      api<MutationResponse<RevenueMutationResult>>(
        "/api/v2/admin/revenue/action-center/quick-action",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Aksiyon eklenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P7b — 360 + CRM (owner-aware)
// =============================================================================

export function useAddCrmNote(ownerType: OwnerType, ownerId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<Revenue360MutationResult>, Error, CrmNoteBody>({
    mutationFn: (body) =>
      api<MutationResponse<Revenue360MutationResult>>(
        `/api/v2/admin/revenue/${ownerType}/${ownerId}/crm/notes`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Not eklenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function usePinCrmNote() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<Revenue360MutationResult>, Error, number>({
    mutationFn: (noteId) =>
      api<MutationResponse<Revenue360MutationResult>>(
        `/api/v2/admin/revenue/crm/notes/${noteId}/pin`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İşlem başarısız"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useDeleteCrmNote() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<Revenue360MutationResult>, Error, number>({
    mutationFn: (noteId) =>
      api<MutationResponse<Revenue360MutationResult>>(
        `/api/v2/admin/revenue/crm/notes/${noteId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Not silinemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useAddCrmAction(ownerType: OwnerType, ownerId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<Revenue360MutationResult>, Error, CrmActionBody>({
    mutationFn: (body) =>
      api<MutationResponse<Revenue360MutationResult>>(
        `/api/v2/admin/revenue/${ownerType}/${ownerId}/crm/actions`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Aksiyon eklenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useCompleteCrmAction() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<Revenue360MutationResult>,
    Error,
    { actionId: number; body: CrmActionCompleteBody }
  >({
    mutationFn: ({ actionId, body }) =>
      api<MutationResponse<Revenue360MutationResult>>(
        `/api/v2/admin/revenue/crm/actions/${actionId}/complete`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Tamamlanamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useDeleteCrmAction() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<Revenue360MutationResult>, Error, number>({
    mutationFn: (actionId) =>
      api<MutationResponse<Revenue360MutationResult>>(
        `/api/v2/admin/revenue/crm/actions/${actionId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Aksiyon silinemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useSaveOwnerContact(ownerType: OwnerType, ownerId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<Revenue360MutationResult>, Error, OwnerContactBody>({
    mutationFn: (body) =>
      api<MutationResponse<Revenue360MutationResult>>(
        `/api/v2/admin/revenue/${ownerType}/${ownerId}/contact`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İletişim kaydedilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useAddOwnerTag(ownerType: OwnerType, ownerId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<Revenue360MutationResult>, Error, OwnerTagBody>({
    mutationFn: (body) =>
      api<MutationResponse<Revenue360MutationResult>>(
        `/api/v2/admin/revenue/${ownerType}/${ownerId}/tags`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Etiket eklenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useDeleteOwnerTag() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<Revenue360MutationResult>, Error, number>({
    mutationFn: (tagId) =>
      api<MutationResponse<Revenue360MutationResult>>(
        `/api/v2/admin/revenue/tags/${tagId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Etiket silinemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P7c — Teklifler + Fatura tahsilat + Aksiyon şablonları
// =============================================================================

export function useCreateOffer(ownerType: OwnerType, ownerId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<RevenueOfferMutationResult>, Error, OfferBody>({
    mutationFn: (body) =>
      api<MutationResponse<RevenueOfferMutationResult>>(
        `/api/v2/admin/revenue/${ownerType}/${ownerId}/offers`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Teklif oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useUpdateOffer() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<RevenueOfferMutationResult>, Error, { offerId: number; body: OfferBody }>({
    mutationFn: ({ offerId, body }) =>
      api<MutationResponse<RevenueOfferMutationResult>>(
        `/api/v2/admin/revenue/offers/${offerId}`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Teklif güncellenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useSendOffer() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<RevenueOfferMutationResult>, Error, number>({
    mutationFn: (offerId) =>
      api<MutationResponse<RevenueOfferMutationResult>>(
        `/api/v2/admin/revenue/offers/${offerId}/send`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Teklif gönderilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useCancelOffer() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<RevenueOfferMutationResult>, Error, number>({
    mutationFn: (offerId) =>
      api<MutationResponse<RevenueOfferMutationResult>>(
        `/api/v2/admin/revenue/offers/${offerId}/cancel`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Teklif iptal edilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function usePostponeInvoice() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<InvoiceMutationResult>,
    Error,
    { invoiceId: number; body: InvoicePostponeBody }
  >({
    mutationFn: ({ invoiceId, body }) =>
      api<MutationResponse<InvoiceMutationResult>>(
        `/api/v2/admin/revenue/invoices/${invoiceId}/postpone`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Vade ötelenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useMarkInvoicePaid() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<InvoiceMutationResult>,
    Error,
    { invoiceId: number; body: InvoiceMarkPaidBody }
  >({
    mutationFn: ({ invoiceId, body }) =>
      api<MutationResponse<InvoiceMutationResult>>(
        `/api/v2/admin/revenue/invoices/${invoiceId}/mark-paid`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "İşaretlenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useCancelInvoice() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<InvoiceMutationResult>,
    Error,
    { invoiceId: number; body: InvoiceCancelBody }
  >({
    mutationFn: ({ invoiceId, body }) =>
      api<MutationResponse<InvoiceMutationResult>>(
        `/api/v2/admin/revenue/invoices/${invoiceId}/cancel`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Fatura iptal edilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useSendInvoiceReminder() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<InvoiceMutationResult>,
    Error,
    { invoiceId: number; body: InvoiceReminderBody }
  >({
    mutationFn: ({ invoiceId, body }) =>
      api<MutationResponse<InvoiceMutationResult>>(
        `/api/v2/admin/revenue/invoices/${invoiceId}/send-reminder`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Hatırlatma gönderilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useCreateActionTemplate() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<ActionTemplateMutationResult>, Error, ActionTemplateBody>({
    mutationFn: (body) =>
      api<MutationResponse<ActionTemplateMutationResult>>(
        "/api/v2/admin/revenue/action-templates",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Şablon oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useUpdateActionTemplate(templateId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<ActionTemplateMutationResult>, Error, ActionTemplateBody>({
    mutationFn: (body) =>
      api<MutationResponse<ActionTemplateMutationResult>>(
        `/api/v2/admin/revenue/action-templates/${templateId}`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Şablon güncellenemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useDeleteActionTemplate() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<ActionTemplateMutationResult>, Error, number>({
    mutationFn: (templateId) =>
      api<MutationResponse<ActionTemplateMutationResult>>(
        `/api/v2/admin/revenue/action-templates/${templateId}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Şablon silinemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P7d — Toplu Kampanyalar
// =============================================================================

export function usePreviewCampaign() {
  // Salt-okunur segment önizlemesi — yan etkisi yok, cache bayatlatması gerekmez.
  // eslint-disable-next-line lgs/missing-invalidate
  return useMutation<CampaignPreviewResponse, Error, CampaignPreviewBody>({
    mutationFn: (body) =>
      api<CampaignPreviewResponse>(
        "/api/v2/admin/revenue/campaigns/preview",
        { method: "POST", body: JSON.stringify(body) },
      ),
  });
}

export function useCreateCampaign() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<CampaignMutationResult>, Error, CampaignBody>({
    mutationFn: (body) =>
      api<MutationResponse<CampaignMutationResult>>(
        "/api/v2/admin/revenue/campaigns",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kampanya oluşturulamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

function useCampaignAction(campaignId: number, action: string, fallback: string) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<CampaignMutationResult>, Error, void>({
    mutationFn: () =>
      api<MutationResponse<CampaignMutationResult>>(
        `/api/v2/admin/revenue/campaigns/${campaignId}/${action}`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.invalidateQueries({ queryKey: ["admin", "revenue", "campaigns", String(campaignId)] });
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, fallback), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useLaunchCampaign(id: number) {
  return useCampaignAction(id, "launch", "Kampanya başlatılamadı");
}
export function usePauseCampaign(id: number) {
  return useCampaignAction(id, "pause", "Kampanya duraklatılamadı");
}
export function useResumeCampaign(id: number) {
  return useCampaignAction(id, "resume", "Kampanya devam ettirilemedi");
}
export function useCompleteCampaign(id: number) {
  return useCampaignAction(id, "complete", "Kampanya tamamlanamadı");
}
export function useCancelCampaign(id: number) {
  return useCampaignAction(id, "cancel", "Kampanya iptal edilemedi");
}

// =============================================================================
// G2a — Güvenlik Kamarası: sistem hata grubunu çöz
// =============================================================================

export function useResolveSystemError() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SystemMutationResult>,
    Error,
    { errorId: number; note: string }
  >({
    mutationFn: ({ errorId, note }) =>
      api<MutationResponse<SystemMutationResult>>(
        `/api/v2/admin/security-monitor/system/${errorId}/resolve`,
        { method: "POST", body: JSON.stringify({ note }) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Hata çözülemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// G3 — Güvenlik Kamarası: oturum/IP/impersonation aksiyonları
// =============================================================================

function useSecurityAction<TBody, TResult extends { message: string } = SecurityActionResult>(
  pathFor: (body: TBody) => string,
  body: ((body: TBody) => unknown) | null,
  fallback: string,
) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<TResult>, Error, TBody>({
    mutationFn: (vars) =>
      api<MutationResponse<TResult>>(pathFor(vars), {
        method: "POST",
        ...(body ? { body: JSON.stringify(body(vars)) } : {}),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data.message);
    },
    onError: (e) => {
      toast.error(errorTitle(e, fallback), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useRevokeSession() {
  return useSecurityAction<{ sessionToken: string }>(
    ({ sessionToken }) =>
      `/api/v2/admin/security-monitor/sessions/${encodeURIComponent(sessionToken)}/revoke`,
    null,
    "Oturum kapatılamadı",
  );
}

export function useBlockIp() {
  return useSecurityAction<{ ip: string; hours: number; note: string }>(
    () => "/api/v2/admin/security-monitor/ips/block",
    ({ ip, hours, note }) => ({ ip, hours, note }),
    "IP engellenemedi",
  );
}

export function useUnblockIp() {
  return useSecurityAction<{ ip: string }>(
    () => "/api/v2/admin/security-monitor/ips/unblock",
    ({ ip }) => ({ ip }),
    "IP serbest bırakılamadı",
  );
}

export function useRevokeImpersonation() {
  return useSecurityAction<{ impId: number }>(
    ({ impId }) => `/api/v2/admin/security-monitor/impersonations/${impId}/end`,
    null,
    "Sahte oturum kapatılamadı",
  );
}

// =============================================================================
// G4 — Alarmlar + Suistimal aksiyonları
// =============================================================================

export function useAlarmScan() {
  return useSecurityAction<void, AlarmScanResult>(
    () => "/api/v2/admin/security-monitor/alarms/scan",
    null,
    "Tarama yapılamadı",
  );
}

export function useAlarmAck() {
  return useSecurityAction<{ eventId: number }>(
    ({ eventId }) => `/api/v2/admin/security-monitor/alarms/${eventId}/ack`,
    null,
    "Alarm onaylanamadı",
  );
}

export function useAlarmUpdateRule() {
  return useSecurityAction<{ ruleId: number; body: AlarmRuleUpdateBody }>(
    ({ ruleId }) => `/api/v2/admin/security-monitor/alarms/rules/${ruleId}/update`,
    ({ body }) => body,
    "Kural güncellenemedi",
  );
}

export function useAbuseScan() {
  return useSecurityAction<void, AbuseScanResult>(
    () => "/api/v2/admin/security-monitor/abuse/scan",
    null,
    "Tarama yapılamadı",
  );
}

export function useAbuseResolve() {
  return useSecurityAction<{ signalId: number; note: string }>(
    ({ signalId }) => `/api/v2/admin/security-monitor/abuse/${signalId}/resolve`,
    ({ note }) => ({ note }),
    "Sinyal çözülemedi",
  );
}

export function useAbuseRemediate() {
  return useSecurityAction<{ signalId: number }, AbuseRemediateResult>(
    ({ signalId }) => `/api/v2/admin/security-monitor/abuse/${signalId}/remediate`,
    null,
    "Aksiyon uygulanamadı",
  );
}

// =============================================================================
// Sistem ayarları — API anahtarları
// =============================================================================

export function useSetAiSetting() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<AiSettingsResponse>, ApiError, SetAiSettingBody>({
    mutationFn: (body) =>
      api<MutationResponse<AiSettingsResponse>>("/api/v2/admin/settings/ai", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Ayar kaydedildi");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Ayar kaydedilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useDeleteAiSetting() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<AiSettingsResponse>, ApiError, { name: string }>({
    mutationFn: ({ name }) =>
      api<MutationResponse<AiSettingsResponse>>(`/api/v2/admin/settings/ai/${name}/delete`, {
        method: "POST",
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Ayar silindi");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Ayar silinemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useSavePricing() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PricingAdminResponse>, ApiError, PricingConfig>({
    mutationFn: (body) =>
      api<MutationResponse<PricingAdminResponse>>("/api/v2/admin/settings/pricing", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Fiyatlandırma kaydedildi");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Kaydedilemedi"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

export function useResetPricing() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PricingAdminResponse>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<PricingAdminResponse>>("/api/v2/admin/settings/pricing/reset", { method: "POST" }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Varsayılana sıfırlandı");
    },
    onError: (e) => {
      toast.error(errorTitle(e, "Sıfırlanamadı"), {
        description: errorMessage(e, "Beklenmeyen bir hata oluştu."),
      });
    },
  });
}

// =============================================================================
// P2 — WhatsApp şablon registry mutation hook'ları
// =============================================================================

const WA_TPL_ERROR_LABELS: Record<string, string> = {
  invalid_category: "Geçersiz kategori seçimi.",
  invalid_target_role: "Geçersiz hedef rol seçimi.",
  key_taken: "Bu key zaten kullanılıyor — başka bir key seçin.",
  template_not_found: "Şablon bulunamadı.",
  template_active: "Aktif şablon silinemez. Önce pasife alın.",
};

function waTplErrorTitle(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    const code = e.detail?.code as string | undefined;
    if (code && WA_TPL_ERROR_LABELS[code]) return WA_TPL_ERROR_LABELS[code];
    return e.detail?.message ?? fallback;
  }
  return fallback;
}

export function useCreateWaTemplate() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<import("@/lib/types/whatsapp-template").WaTemplateItem>,
    ApiError,
    import("@/lib/types/whatsapp-template").WaTemplateCreateBody
  >({
    mutationFn: (body) =>
      api<
        MutationResponse<
          import("@/lib/types/whatsapp-template").WaTemplateItem
        >
      >("/api/v2/admin/whatsapp-templates", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Şablon oluşturuldu");
    },
    onError: (e) => toast.error(waTplErrorTitle(e, "Şablon oluşturulamadı")),
  });
}

export function useUpdateWaTemplate(id: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<import("@/lib/types/whatsapp-template").WaTemplateItem>,
    ApiError,
    import("@/lib/types/whatsapp-template").WaTemplateUpdateBody
  >({
    mutationFn: (body) =>
      api<
        MutationResponse<
          import("@/lib/types/whatsapp-template").WaTemplateItem
        >
      >(`/api/v2/admin/whatsapp-templates/${id}`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Şablon güncellendi");
    },
    onError: (e) => toast.error(waTplErrorTitle(e, "Şablon güncellenemedi")),
  });
}

export function useToggleWaTemplate() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<
      import("@/lib/types/whatsapp-template").WaTemplateToggleResult
    >,
    ApiError,
    { id: number }
  >({
    mutationFn: ({ id }) =>
      api<
        MutationResponse<
          import("@/lib/types/whatsapp-template").WaTemplateToggleResult
        >
      >(`/api/v2/admin/whatsapp-templates/${id}/toggle-active`, {
        method: "POST",
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "Durum değişti");
    },
    onError: (e) => toast.error(waTplErrorTitle(e, "Durum değiştirilemedi")),
  });
}

export function useDeleteWaTemplate() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<
      import("@/lib/types/whatsapp-template").WaTemplateDeleteResult
    >,
    ApiError,
    { id: number }
  >({
    mutationFn: ({ id }) =>
      api<
        MutationResponse<
          import("@/lib/types/whatsapp-template").WaTemplateDeleteResult
        >
      >(`/api/v2/admin/whatsapp-templates/${id}/delete`, { method: "POST" }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(res.data?.message ?? "Silindi");
    },
    onError: (e) => toast.error(waTplErrorTitle(e, "Silinemedi")),
  });
}

// =============================================================================
// M5 — Demo Ekosistem Oluştur
// =============================================================================

import type { DemoKind, DemoSeedResult, DemoSessionDeleteResult } from "@/lib/types/admin";

export function useCreateDemoEcosystem() {
  const qc = useQueryClient();
  return useMutation<
    DemoSeedResult,
    ApiError,
    { kind: DemoKind; label?: string | null }
  >({
    mutationFn: ({ kind, label }) =>
      api<DemoSeedResult>("/api/v2/admin/demo-seed", {
        method: "POST",
        body: JSON.stringify({ kind, label: label ?? null }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      qc.invalidateQueries({ queryKey: ["admin", "institutions"] });
      qc.invalidateQueries({ queryKey: ["admin", "demo-sessions"] });
    },
    onError: (e) => {
      const code = e.detail?.code as string | undefined;
      const messages: Record<string, string> = {
        invalid_kind: "Geçersiz demo türü.",
        demo_seed_failed: "Demo oluşturulamadı (sunucu hatası).",
        role_required: "Bu işlem yalnız süper admin içindir.",
      };
      toast.error((code && messages[code]) || "Demo oluşturulamadı");
    },
  });
}

export function useDeleteDemoSession() {
  const qc = useQueryClient();
  return useMutation<DemoSessionDeleteResult, ApiError, { seedId: string }>({
    mutationFn: ({ seedId }) =>
      api<DemoSessionDeleteResult>(
        `/api/v2/admin/demo-sessions/${encodeURIComponent(seedId)}/delete`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      qc.invalidateQueries({ queryKey: ["admin", "institutions"] });
      qc.invalidateQueries({ queryKey: ["admin", "demo-sessions"] });
      const total =
        res.users_deleted +
        res.institutions_deleted +
        res.tasks_deleted +
        res.exams_deleted +
        res.sessions_deleted;
      toast.success(`Demo silindi (${total} kayıt temizlendi)`);
    },
    onError: (e) => {
      const code = e.detail?.code as string | undefined;
      const messages: Record<string, string> = {
        demo_delete_failed: "Demo silinemedi (sunucu hatası).",
        role_required: "Bu işlem yalnız süper admin içindir.",
      };
      toast.error((code && messages[code]) || "Silinemedi");
    },
  });
}
