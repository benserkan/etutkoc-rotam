/**
 * /api/v2/admin/* — Süper Admin paneli fetcher'ları (Dalga 6).
 *
 * QueryKey sözleşmesi: backend `MutationResponse.invalidate` listesindeki
 * "admin:*" prefix'i ile uyumlu. Sonraki paketlerde mutation hook'ları
 * eklenince applyInvalidate ile yeniden bayatlanır.
 */
import { api } from "@/lib/api";
import type {
  AccountHistoryResponse,
  AccountOwnerType,
  AdminBadgesResponse,
  AdminDashboardResponse,
  AdminIndependentTeachersResponse,
  AdminQuotaResponse,
  AdminUsageResponse,
  AdminUserDetailResponse,
  AdminUserListResponse,
  ActionCenterResponse,
  ActionTemplatesResponse,
  ActionTemplateRenderResponse,
  AnnouncementsListResponse,
  AuditListResponse,
  CampaignDetailResponse,
  CampaignFormMeta,
  CampaignsListResponse,
  DiscoveryQueueResponse,
  InstitutionRevenue360Response,
  RevenueCohortResponse,
  RevenueDashboardResponse,
  RevenueDrillResponse,
  RevenueForecastResponse,
  RevenueInvoicesResponse,
  UserRevenue360Response,
  ExperimentDetailResponse,
  ExperimentFormMeta,
  ExperimentListResponse,
  FeatureCardFormResponse,
  FeatureCatalogDashboardResponse,
  FeatureCatalogListResponse,
  FeatureFlagDetailResponse,
  FeatureFlagsListResponse,
  InstitutionBackupSummary,
  InstitutionDetailResponse,
  InstitutionFilterLevel,
  InstitutionListResponse,
  InstitutionSort,
  KvkkDashboardResponse,
  SystemHealthResponse,
  SecurityOverviewResponse,
  IntegrityResponse,
  SystemHealthDataResponse,
  NotificationHealthResponse,
  ActivityPanelResponse,
  ActiveUsersDrillResponse,
  InstitutionHeatmapResponse,
  LiveFeedResponse,
  AlarmsResponse,
  AbuseResponse,
  AiSettingsResponse,
  PricingAdminResponse,
  ContactRequestListResponse,
} from "@/lib/types/admin";

// =============================================================================
// QueryKey üreticileri
// =============================================================================

export const adminKeys = {
  root: () => ["admin"] as const,
  badges: () => ["admin", "badges"] as const,
  dashboard: () => ["admin", "dashboard"] as const,
  institutions: (
    sort: InstitutionSort,
    filterLevel: InstitutionFilterLevel | null,
  ) =>
    [
      "admin",
      "institutions",
      sort,
      filterLevel ?? "",
    ] as const,
  institution: (id: number) =>
    ["admin", "institutions", String(id)] as const,
  institutionBackup: (id: number) =>
    ["admin", "institutions", String(id), "backup"] as const,
  accountHistory: (
    ownerType: AccountOwnerType,
    ownerId: number,
    years: number,
    includeArchived: boolean,
  ) =>
    [
      "admin",
      "account-history",
      ownerType,
      String(ownerId),
      String(years),
      includeArchived ? "1" : "0",
    ] as const,
  users: (
    role: string | null,
    institutionId: number | null,
    q: string | null,
  ) =>
    [
      "admin",
      "users",
      role ?? "",
      institutionId != null ? String(institutionId) : "",
      q ?? "",
    ] as const,
  user: (id: number) => ["admin", "users", String(id)] as const,
  independentTeachers: () => ["admin", "independent-teachers"] as const,
  audit: (
    action: string | null,
    actorId: number | null,
    startDate: string | null,
    endDate: string | null,
    page: number,
  ) =>
    [
      "admin",
      "audit",
      action ?? "",
      actorId != null ? String(actorId) : "",
      startDate ?? "",
      endDate ?? "",
      String(page),
    ] as const,
  systemHealth: () => ["admin", "system-health"] as const,
  announcements: () => ["admin", "announcements"] as const,
  kvkk: () => ["admin", "kvkk"] as const,
  usage: () => ["admin", "usage"] as const,
  quota: () => ["admin", "quota"] as const,
  featureFlags: () => ["admin", "feature-flags"] as const,
  featureFlag: (id: number) =>
    ["admin", "feature-flags", String(id)] as const,
  // P6 — Feature Catalog
  featureCatalog: (
    statusFilter: string | null,
    domainFilter: string | null,
    tierFilter: string | null,
    q: string | null,
  ) =>
    [
      "admin",
      "feature-catalog",
      statusFilter ?? "",
      domainFilter ?? "",
      tierFilter ?? "",
      q ?? "",
    ] as const,
  featureCard: (id: number) =>
    ["admin", "feature-catalog", "detail", String(id)] as const,
  featureCardNew: () => ["admin", "feature-catalog", "detail", "new"] as const,
  featureCatalogDashboard: () =>
    ["admin", "feature-catalog", "dashboard"] as const,
  featureCatalogDiscovery: (source: string | null, showRejected: boolean) =>
    [
      "admin",
      "feature-catalog",
      "discovery",
      source ?? "",
      showRejected ? "1" : "0",
    ] as const,
  featureExperiments: () =>
    ["admin", "feature-catalog", "experiments"] as const,
  featureExperimentNew: () =>
    ["admin", "feature-catalog", "experiments", "new"] as const,
  featureExperiment: (id: number) =>
    ["admin", "feature-catalog", "experiments", String(id)] as const,
  // P7a — Revenue analitik
  revenueActionCenter: () => ["admin", "revenue", "action-center"] as const,
  revenueForecast: (saveRate: number) =>
    ["admin", "revenue", "forecast", String(saveRate)] as const,
  revenueCohort: (monthsBack: number, horizon: number, churnDays: number) =>
    [
      "admin",
      "revenue",
      "cohort",
      String(monthsBack),
      String(horizon),
      String(churnDays),
    ] as const,
  // P7b — 360 görünümler
  revenueInstitution360: (id: number) =>
    ["admin", "revenue", "360", "institutions", String(id)] as const,
  revenueUser360: (id: number) =>
    ["admin", "revenue", "360", "users", String(id)] as const,
  revenueActionTemplates: () =>
    ["admin", "revenue", "action-templates"] as const,
  revenueCampaigns: () => ["admin", "revenue", "campaigns"] as const,
  revenueCampaign: (id: number) =>
    ["admin", "revenue", "campaigns", String(id)] as const,
  revenueDashboard: (segment: string) =>
    ["admin", "security-monitor", "revenue", segment] as const,
  revenueInvoices: (statusFilter: string | null) =>
    ["admin", "security-monitor", "revenue", "invoices", statusFilter ?? ""] as const,
  // G2a — Güvenlik Kamarası: genel bakış + bütünlük + sistem + bildirim
  securityOverview: () => ["admin", "security", "overview"] as const,
  securityIntegrity: () => ["admin", "security", "integrity"] as const,
  securitySystem: () => ["admin", "security", "system"] as const,
  securityNotifications: () => ["admin", "security", "notifications"] as const,
  // G2b — Aktivite Kamerası
  securityActivity: (segment: string) =>
    ["admin", "security", "activity", segment] as const,
  securityActivityUsers: (
    window: string,
    role: string,
    institutionId: number | null,
  ) =>
    [
      "admin",
      "security",
      "activity",
      "active-users",
      window,
      role,
      institutionId != null ? String(institutionId) : "",
    ] as const,
  securityActivityHeatmap: (institutionId: number) =>
    ["admin", "security", "activity", "heatmap", String(institutionId)] as const,
  // G3 — Oturumlar + Canlı akış
  securitySessions: () => ["admin", "security", "sessions"] as const,
  securityLiveFeed: (sinceSeconds: number) =>
    ["admin", "security", "live", String(sinceSeconds)] as const,
  // G4 — Alarmlar + Suistimal
  securityAlarms: () => ["admin", "security", "alarms"] as const,
  securityAbuse: (onlyOpen: boolean, kind: string | null) =>
    ["admin", "security", "abuse", onlyOpen ? "1" : "0", kind ?? ""] as const,
  aiSettings: () => ["admin", "settings", "ai"] as const,
  pricing: () => ["admin", "settings", "pricing"] as const,
  contactRequests: (status: string | null) =>
    ["admin", "contact-requests", status ?? ""] as const,
};

// =============================================================================
// GET fetcher'ları
// =============================================================================

export function getAdminDashboard() {
  return api<AdminDashboardResponse>("/api/v2/admin/dashboard");
}

export function getAdminBadges() {
  return api<AdminBadgesResponse>("/api/v2/admin/badges");
}

export function getAdminAiSettings() {
  return api<AiSettingsResponse>("/api/v2/admin/settings/ai");
}

export function getAdminPricing() {
  return api<PricingAdminResponse>("/api/v2/admin/settings/pricing");
}

export function getAdminContactRequests(status: string | null = null) {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return api<ContactRequestListResponse>(`/api/v2/admin/contact-requests${qs}`);
}

export function getAdminInstitutions(
  sort: InstitutionSort = "health",
  filterLevel: InstitutionFilterLevel | null = null,
) {
  const qs = new URLSearchParams();
  qs.set("sort", sort);
  if (filterLevel) qs.set("filter_level", filterLevel);
  return api<InstitutionListResponse>(
    `/api/v2/admin/institutions?${qs.toString()}`,
  );
}

export function getAdminInstitution(id: number) {
  return api<InstitutionDetailResponse>(`/api/v2/admin/institutions/${id}`);
}

export function getAdminInstitutionBackup(id: number) {
  return api<InstitutionBackupSummary>(
    `/api/v2/admin/institutions/${id}/backup`,
  );
}

export function getAdminAccountHistory(
  ownerType: AccountOwnerType,
  ownerId: number,
  years = 3,
  includeArchived = false,
) {
  const qs = new URLSearchParams();
  qs.set("years", String(years));
  if (includeArchived) qs.set("include_archived", "1");
  return api<AccountHistoryResponse>(
    `/api/v2/admin/account-history/${ownerType}/${ownerId}?${qs.toString()}`,
  );
}

/** Backup JSON dosyasını indirme URL'i. */
export function adminInstitutionBackupDownloadUrl(id: number): string {
  return `/api/v2/admin/institutions/${id}/backup.json`;
}

// =============================================================================
// P3 — Users fetchers
// =============================================================================

export function getAdminUsers(
  role: string | null = null,
  institutionId: number | null = null,
  q: string | null = null,
) {
  const qs = new URLSearchParams();
  if (role) qs.set("role", role);
  if (institutionId != null) qs.set("institution_id", String(institutionId));
  if (q) qs.set("q", q);
  const suffix = qs.toString();
  return api<AdminUserListResponse>(
    `/api/v2/admin/users${suffix ? `?${suffix}` : ""}`,
  );
}

export function getAdminUser(id: number) {
  return api<AdminUserDetailResponse>(`/api/v2/admin/users/${id}`);
}

export function getAdminIndependentTeachers() {
  return api<AdminIndependentTeachersResponse>(
    "/api/v2/admin/independent-teachers",
  );
}

// =============================================================================
// P4 — Audit / system-health / announcements / kvkk fetchers
// =============================================================================

export function getAdminAudit(
  action: string | null = null,
  actorId: number | null = null,
  startDate: string | null = null,
  endDate: string | null = null,
  page = 1,
) {
  const qs = new URLSearchParams();
  if (action) qs.set("action", action);
  if (actorId != null) qs.set("actor_id", String(actorId));
  if (startDate) qs.set("start_date", startDate);
  if (endDate) qs.set("end_date", endDate);
  if (page > 1) qs.set("page", String(page));
  const suffix = qs.toString();
  return api<AuditListResponse>(
    `/api/v2/admin/audit${suffix ? `?${suffix}` : ""}`,
  );
}

export function getAdminSystemHealth() {
  return api<SystemHealthResponse>("/api/v2/admin/system-health");
}

export function getAdminAnnouncements() {
  return api<AnnouncementsListResponse>("/api/v2/admin/announcements");
}

export function getAdminKvkk() {
  return api<KvkkDashboardResponse>("/api/v2/admin/kvkk");
}

// =============================================================================
// P5 — Usage / quota / feature-flags fetchers
// =============================================================================

export function getAdminUsage() {
  return api<AdminUsageResponse>("/api/v2/admin/usage");
}

export function getAdminQuota() {
  return api<AdminQuotaResponse>("/api/v2/admin/quota");
}

export function getAdminFeatureFlags() {
  return api<FeatureFlagsListResponse>("/api/v2/admin/feature-flags");
}

export function getAdminFeatureFlag(id: number) {
  return api<FeatureFlagDetailResponse>(`/api/v2/admin/feature-flags/${id}`);
}

// =============================================================================
// P6 — Feature Catalog fetchers
// =============================================================================

export function getAdminFeatureCatalog(
  statusFilter: string | null = null,
  domainFilter: string | null = null,
  tierFilter: string | null = null,
  q: string | null = null,
) {
  const qs = new URLSearchParams();
  if (statusFilter) qs.set("status_filter", statusFilter);
  if (domainFilter) qs.set("domain_filter", domainFilter);
  if (tierFilter) qs.set("tier_filter", tierFilter);
  if (q) qs.set("q", q);
  const suffix = qs.toString();
  return api<FeatureCatalogListResponse>(
    `/api/v2/admin/feature-catalog${suffix ? `?${suffix}` : ""}`,
  );
}

export function getAdminFeatureCardNew() {
  return api<FeatureCardFormResponse>("/api/v2/admin/feature-catalog/new");
}

export function getAdminFeatureCard(id: number) {
  return api<FeatureCardFormResponse>(`/api/v2/admin/feature-catalog/${id}`);
}

export function getAdminFeatureCatalogDashboard() {
  return api<FeatureCatalogDashboardResponse>(
    "/api/v2/admin/feature-catalog/dashboard",
  );
}

export function getAdminFeatureCatalogDiscovery(
  source: string | null = null,
  showRejected = false,
) {
  const qs = new URLSearchParams();
  if (source) qs.set("source", source);
  if (showRejected) qs.set("show_rejected", "1");
  const suffix = qs.toString();
  return api<DiscoveryQueueResponse>(
    `/api/v2/admin/feature-catalog/discovery-queue${suffix ? `?${suffix}` : ""}`,
  );
}

export function getAdminFeatureExperiments() {
  return api<ExperimentListResponse>(
    "/api/v2/admin/feature-catalog/experiments",
  );
}

export function getAdminFeatureExperimentNew() {
  return api<ExperimentFormMeta>(
    "/api/v2/admin/feature-catalog/experiments/new",
  );
}

export function getAdminFeatureExperiment(id: number) {
  return api<ExperimentDetailResponse>(
    `/api/v2/admin/feature-catalog/experiments/${id}`,
  );
}

// =============================================================================
// P7a — Revenue analitik fetchers
// =============================================================================

export function getAdminRevenueActionCenter() {
  return api<ActionCenterResponse>("/api/v2/admin/revenue/action-center");
}

export function getAdminRevenueForecast(saveRate = 0.5) {
  return api<RevenueForecastResponse>(
    `/api/v2/admin/revenue/forecast?save_rate=${saveRate}`,
  );
}

export function getAdminRevenueCohort(
  monthsBack = 12,
  horizon = 12,
  churnDays = 90,
) {
  const qs = new URLSearchParams();
  qs.set("months_back", String(monthsBack));
  qs.set("horizon", String(horizon));
  qs.set("churn_days", String(churnDays));
  return api<RevenueCohortResponse>(
    `/api/v2/admin/revenue/cohort?${qs.toString()}`,
  );
}

export function getAdminRevenueInstitution360(id: number) {
  return api<InstitutionRevenue360Response>(
    `/api/v2/admin/revenue/institutions/${id}`,
  );
}

export function getAdminRevenueUser360(id: number) {
  return api<UserRevenue360Response>(`/api/v2/admin/revenue/users/${id}`);
}

export function getAdminActionTemplateRender(
  templateId: number, ownerType: string, ownerId: number,
) {
  return api<ActionTemplateRenderResponse>(
    `/api/v2/admin/revenue/action-templates/${templateId}/render?owner_type=${ownerType}&owner_id=${ownerId}`,
  );
}

export function getAdminActionTemplates() {
  return api<ActionTemplatesResponse>(
    "/api/v2/admin/revenue/action-templates",
  );
}

export function getAdminCampaigns() {
  return api<CampaignsListResponse>("/api/v2/admin/revenue/campaigns");
}

export function getAdminCampaignFormMeta() {
  return api<CampaignFormMeta>("/api/v2/admin/revenue/campaigns/new");
}

export function getAdminCampaign(id: number) {
  return api<CampaignDetailResponse>(`/api/v2/admin/revenue/campaigns/${id}`);
}

export function getAdminRevenueDashboard(segment = "all") {
  return api<RevenueDashboardResponse>(
    `/api/v2/admin/security-monitor/revenue?segment=${segment}`,
  );
}

export function getAdminRevenueDrill(key: string, plan?: string | null) {
  const qs = new URLSearchParams();
  qs.set("key", key);
  if (plan) qs.set("plan", plan);
  return api<RevenueDrillResponse>(
    `/api/v2/admin/security-monitor/revenue/drill?${qs.toString()}`,
  );
}

export function getAdminRevenueInvoices(statusFilter?: string | null) {
  const qs = new URLSearchParams();
  if (statusFilter) qs.set("status_filter", statusFilter);
  const suffix = qs.toString();
  return api<RevenueInvoicesResponse>(
    `/api/v2/admin/security-monitor/revenue/invoices${suffix ? `?${suffix}` : ""}`,
  );
}

// =============================================================================
// G2a — Güvenlik Kamarası fetchers
// =============================================================================

export function getAdminSecurityOverview() {
  return api<SecurityOverviewResponse>("/api/v2/admin/security-monitor");
}

export function getAdminSecurityIntegrity() {
  return api<IntegrityResponse>("/api/v2/admin/security-monitor/integrity");
}

export function getAdminSecuritySystem() {
  return api<SystemHealthDataResponse>("/api/v2/admin/security-monitor/system");
}

export function getAdminSecurityNotifications() {
  return api<NotificationHealthResponse>(
    "/api/v2/admin/security-monitor/notifications",
  );
}

// =============================================================================
// G2b — Aktivite Kamerası fetchers
// =============================================================================

export function getAdminSecurityActivity(segment = "all") {
  return api<ActivityPanelResponse>(
    `/api/v2/admin/security-monitor/activity?segment=${segment}`,
  );
}

export function getAdminSecurityActivityUsers(
  window = "dau",
  role = "",
  institutionId: number | null = null,
) {
  const qs = new URLSearchParams();
  qs.set("window", window);
  if (role) qs.set("role", role);
  if (institutionId != null) qs.set("institution_id", String(institutionId));
  return api<ActiveUsersDrillResponse>(
    `/api/v2/admin/security-monitor/activity/active-users?${qs.toString()}`,
  );
}

export function getAdminSecurityActivityHeatmap(institutionId: number) {
  return api<InstitutionHeatmapResponse>(
    `/api/v2/admin/security-monitor/activity/heatmap?institution_id=${institutionId}`,
  );
}

// =============================================================================
// G3 — Canlı akış fetcher
// =============================================================================

export function getAdminSecurityLiveFeed(sinceSeconds = 600) {
  return api<LiveFeedResponse>(
    `/api/v2/admin/security-monitor/live/feed?since_seconds=${sinceSeconds}`,
  );
}

// =============================================================================
// G4 — Alarmlar + Suistimal fetchers
// =============================================================================

export function getAdminSecurityAlarms() {
  return api<AlarmsResponse>("/api/v2/admin/security-monitor/alarms");
}

export function getAdminSecurityAbuse(onlyOpen = true, kind: string | null = null) {
  const qs = new URLSearchParams();
  qs.set("only_open", onlyOpen ? "1" : "0");
  if (kind) qs.set("kind", kind);
  return api<AbuseResponse>(
    `/api/v2/admin/security-monitor/abuse?${qs.toString()}`,
  );
}
