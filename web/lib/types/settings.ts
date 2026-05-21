/**
 * Manuel TypeScript tipleri — `/api/v2/teacher/settings/*` ve `/teacher/usage/*` için.
 *
 * Pydantic şemalarıyla (`app/routes/api_v2/schemas/settings.py`) birebir aynı.
 */

export interface CronJobInfo {
  title: string;
  what: string;
  applies: string;
  default_hint: string;
}

export interface CronScheduleItem {
  id: number;
  job_key: string;
  description: string | null;
  hour: number;
  minute: number;
  day_of_week: number | null;
  interval_minutes: number | null;
  enabled: boolean;
  last_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  time_label: string;
  tr_time_label: string;
  dow_label: string;
  info: CronJobInfo | null;
}

export interface EmailConfigStatus {
  enabled: boolean;
  smtp_host: string | null;
  smtp_port: number | null;
  from_address: string | null;
}

export interface TeacherProfileBrief {
  id: number;
  full_name: string;
  email: string | null;
  role: string;
  institution_id: number | null;
  plan: string | null;
}

export interface TeacherSettingsResponse {
  teacher: TeacherProfileBrief;
  email_config: EmailConfigStatus;
  cron_schedules: CronScheduleItem[];
}

export interface TestEmailBody {
  to?: string | null;
}

export interface TestEmailResult {
  sent: boolean;
  to: string;
  message: string;
}

export interface CronSchedulePatchBody {
  hour?: number | null;
  minute?: number | null;
  day_of_week?: number | null;
  enabled?: boolean | null;
  clear_day_of_week?: boolean;
}

export interface CronRunNowResult {
  summary: string;
  sent: number;
  suppressed: number;
}

// =============================================================================
// Usage
// =============================================================================

export interface UsagePeriodAccount {
  period: string;
  plan_code: string;
  allocated_credits: number;
  used_credits: number;
  bonus_credits: number;
  remaining_credits: number;
  usage_pct: number;
  hard_block_enabled: boolean;
  blocked_until: string | null;
  warn_80_sent_at: string | null;
  is_currently_blocked: boolean;
}

export interface UsageBreakdownItem {
  kind: string;
  label: string;
  credits: number;
  cost_per_call: number;
}

export interface UsageDailyPoint {
  date: string;
  credits: number;
}

export interface UsageEventItem {
  id: number;
  kind: string;
  label: string;
  credits: number;
  occurred_at: string;
  actor_user_id: number | null;
  metadata: Record<string, unknown> | null;
}

export interface PlanAllocationItem {
  plan_code: string;
  monthly_credits: number;
}

export interface TeacherUsageResponse {
  is_independent: boolean;
  institution_id: number | null;
  account: UsagePeriodAccount | null;
  breakdown: UsageBreakdownItem[];
  daily_series: UsageDailyPoint[];
  recent_events: UsageEventItem[];
  plan_allocations: PlanAllocationItem[];
  kind_costs: UsageBreakdownItem[];
}
