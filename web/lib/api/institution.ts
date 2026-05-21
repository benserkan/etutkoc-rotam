/**
 * /api/v2/institution/* — Kurum Yöneticisi panel fetcher'ları (Dalga 4 Paket 4).
 *
 * QueryKey sözleşmesi backend `MutationResponse.invalidate` listesindeki
 * "institution:{id}:dashboard" gibi düz string'lerle birebir uyumludur
 * (applyInvalidate, "institution:{id}" → "institution:me" mapping'i yapar).
 *
 * GİZLİLİK NOTU: Bu fetcher'lar /teacher/students/{id}, /teacher/insights vb.
 * detay sayfalarına YÖNLENMEZ — kurum yöneticisinin yetki sınırı içinde kalır.
 */
import { api } from "@/lib/api";
import type {
  ActivityHeatmapResponse,
  AdminDigestDetailResponse,
  AdminDigestListResponse,
  AtRiskResponse,
  BurnoutResponse,
  ActionCenterResponse,
  TeacherScorecardResponse,
  ParentTrustResponse,
  InstitutionAcademicResponse,
  CohortTab,
  CohortsResponse,
  InstitutionComplianceResponse,
  InstitutionDashboardResponse,
  InstitutionGoalsResponse,
  InstitutionRosterResponse,
  InstitutionTeacherListResponse,
  InvitationListResponse,
  QuotaResponse,
  RosterListParams,
  SubscriptionResponse,
  TeacherCardResponse,
  UsageResponse,
} from "@/lib/types/institution";

// =============================================================================
// QueryKey üreticileri
// =============================================================================

export const institutionKeys = {
  root: () => ["institution", "me"] as const,
  dashboard: () => ["institution", "me", "dashboard"] as const,
  teachers: () => ["institution", "me", "teachers"] as const,
  teacher: (id: number) =>
    ["institution", "me", "teachers", String(id)] as const,
  roster: (params: RosterListParams) =>
    [
      "institution",
      "me",
      "roster",
      params.teacher_id != null ? String(params.teacher_id) : "",
      params.grade != null ? String(params.grade) : "",
      params.is_graduate == null ? "" : params.is_graduate ? "g" : "ng",
    ] as const,
  goals: () => ["institution", "me", "goals"] as const,
  atRisk: () => ["institution", "me", "at-risk"] as const,
  burnout: () => ["institution", "me", "burnout"] as const,
  activityHeatmap: (weeks: number) =>
    ["institution", "me", "activity-heatmap", String(weeks)] as const,
  cohorts: (tab: CohortTab) =>
    ["institution", "me", "cohorts", tab] as const,
  compliance: (weeks: number) =>
    ["institution", "me", "compliance", String(weeks)] as const,
  actionCenter: () => ["institution", "me", "action-center"] as const,
  teacherScorecard: (weeks: number) =>
    ["institution", "me", "teacher-scorecard", String(weeks)] as const,
  parentTrust: (days: number) =>
    ["institution", "me", "parent-trust", String(days)] as const,
  academic: (weeks: number) =>
    ["institution", "me", "academic", String(weeks)] as const,
  invitations: () => ["institution", "me", "invitations"] as const,
  adminDigests: () => ["institution", "me", "admin-digest"] as const,
  adminDigest: (id: number) =>
    ["institution", "me", "admin-digest", String(id)] as const,
  subscription: () => ["institution", "me", "subscription"] as const,
  quota: () => ["institution", "me", "quota"] as const,
  usage: (days: number) =>
    ["institution", "me", "usage", String(days)] as const,
};

// =============================================================================
// GET fetcher'ları
// =============================================================================

export function getInstitutionDashboard() {
  return api<InstitutionDashboardResponse>("/api/v2/institution/dashboard");
}

export function getInstitutionTeachers() {
  return api<InstitutionTeacherListResponse>("/api/v2/institution/teachers");
}

export function getInstitutionTeacherCard(id: number) {
  return api<TeacherCardResponse>(`/api/v2/institution/teachers/${id}`);
}

export function getInstitutionRoster(params: RosterListParams = {}) {
  const qs = new URLSearchParams();
  if (params.teacher_id != null) qs.set("teacher_id", String(params.teacher_id));
  if (params.grade != null) qs.set("grade", String(params.grade));
  if (params.is_graduate != null)
    qs.set("is_graduate", String(params.is_graduate));
  const suffix = qs.toString();
  return api<InstitutionRosterResponse>(
    `/api/v2/institution/roster${suffix ? `?${suffix}` : ""}`,
  );
}

export function getInstitutionGoals() {
  return api<InstitutionGoalsResponse>("/api/v2/institution/goals");
}

export function getInstitutionAtRisk() {
  return api<AtRiskResponse>("/api/v2/institution/at-risk");
}

export function getInstitutionBurnout() {
  return api<BurnoutResponse>("/api/v2/institution/burnout");
}

export function getInstitutionActivityHeatmap(weeks: number) {
  return api<ActivityHeatmapResponse>(
    `/api/v2/institution/activity-heatmap?weeks=${weeks}`,
  );
}

export function getInstitutionCohorts(tab: CohortTab) {
  return api<CohortsResponse>(`/api/v2/institution/cohorts?tab=${tab}`);
}

export function getInstitutionCompliance(weeks = 8) {
  return api<InstitutionComplianceResponse>(
    `/api/v2/institution/compliance?weeks=${weeks}`,
  );
}

export function getInstitutionActionCenter() {
  return api<ActionCenterResponse>("/api/v2/institution/action-center");
}

export function getInstitutionTeacherScorecard(weeks = 4) {
  return api<TeacherScorecardResponse>(
    `/api/v2/institution/teacher-scorecard?weeks=${weeks}`,
  );
}

export function getInstitutionParentTrust(days = 30) {
  return api<ParentTrustResponse>(
    `/api/v2/institution/parent-trust?days=${days}`,
  );
}

export function getInstitutionAcademic(weeks = 8) {
  return api<InstitutionAcademicResponse>(
    `/api/v2/institution/academic?weeks=${weeks}`,
  );
}

export function getInstitutionInvitations() {
  return api<InvitationListResponse>("/api/v2/institution/invitations");
}

export function getInstitutionAdminDigests() {
  return api<AdminDigestListResponse>("/api/v2/institution/admin-digest");
}

export function getInstitutionAdminDigestDetail(id: number) {
  return api<AdminDigestDetailResponse>(
    `/api/v2/institution/admin-digest/${id}`,
  );
}

export function getInstitutionSubscription() {
  return api<SubscriptionResponse>("/api/v2/institution/subscription");
}

export function getInstitutionQuota() {
  return api<QuotaResponse>("/api/v2/institution/quota");
}

export function getInstitutionUsage(days = 30) {
  return api<UsageResponse>(`/api/v2/institution/usage?days=${days}`);
}
