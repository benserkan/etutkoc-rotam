import { apiRequest } from "./api";

export interface InstitutionBrief {
  id: number;
  name: string;
  is_active: boolean;
}
export interface InstitutionAggregate {
  teacher_count: number;
  active_teacher_count: number;
  student_count: number;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
}
export interface InstitutionRiskBadge {
  at_risk_count: number;
  at_risk_critical: number;
}
export interface InstitutionInactiveBadge {
  inactive_teacher_count: number;
  inactive_teacher_names: string[];
}
export interface TeacherSummaryItem {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  is_paused: boolean;
  pause_reason: string | null;
  student_count: number;
  weekly_planned: number;
  weekly_completed: number;
  weekly_rate_pct: number | null;
  last_login_days: number | null;
}
export interface InstitutionDashboardResponse {
  institution: InstitutionBrief;
  aggregate: InstitutionAggregate;
  risk: InstitutionRiskBadge;
  inactive: InstitutionInactiveBadge;
  teacher_summaries: TeacherSummaryItem[];
}

export interface ActionCenterItem {
  severity: string; // critical | warn | info
  category: string; // empty_program | low_compliance | at_risk
  title: string;
  description: string;
  teacher_name: string | null;
  count: number;
  suggestion: string;
}
export interface ActionCenterSummary {
  critical: number;
  warn: number;
  info: number;
  total: number;
}
export interface ActionCenterResponse {
  institution: InstitutionBrief;
  summary: ActionCenterSummary;
  items: ActionCenterItem[];
}

export const institutionKeys = {
  dashboard: ["institution", "dashboard"] as const,
  actionCenter: ["institution", "action-center"] as const,
};

export function getInstitutionDashboard(): Promise<InstitutionDashboardResponse> {
  return apiRequest<InstitutionDashboardResponse>(`/api/v2/institution/dashboard`);
}
export function getInstitutionActionCenter(): Promise<ActionCenterResponse> {
  return apiRequest<ActionCenterResponse>(`/api/v2/institution/action-center`);
}
