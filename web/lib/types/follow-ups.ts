// Takip listesi + ölçüm listesi (süper admin) — 2026-11-08.

export type FollowUpBucket = "overdue" | "today" | "upcoming" | "later" | "done" | "cancelled";
export type FollowUpVerdict =
  | "declined"
  | "improved"
  | "stable"
  | "few_samples"
  | "single_point"
  | "no_data";

export interface FollowUpReportRow {
  owner_type: "system" | "coach";
  owner_id: number;
  owner_label: string;
  base_value: number | null;
  base_on: string | null;
  latest_value: number | null;
  latest_on: string | null;
  sample_n: number | null;
  delta: number | null;
  verdict: FollowUpVerdict;
}

export interface FollowUpReport {
  metric_key: string;
  metric_label: string;
  unit: string;
  owner_type: string;
  baseline_on: string;
  evaluated_on: string;
  min_change: number;
  verdict: FollowUpVerdict;
  summary: string;
  rows: FollowUpReportRow[];
}

export interface FollowUpCheck {
  metric_key: string;
  metric_label: string;
  owner_type: "system" | "coach";
  min_change: number;
}

export interface FollowUpItem {
  id: number;
  key: string | null;
  title: string;
  description: string | null;
  category: string;
  category_label: string;
  priority: "high" | "normal";
  status: "open" | "done" | "cancelled";
  bucket: FollowUpBucket;
  due_on: string;
  snoozed_until: string | null;
  effective_due: string;
  days_left: number;
  recurrence_days: number | null;
  check_kind: string | null;
  check: FollowUpCheck | null;
  baseline_on: string | null;
  report: FollowUpReport | null;
  last_checked_at: string | null;
  notified_on: string | null;
  completed_at: string | null;
  completed_by_name: string | null;
  result_note: string | null;
  previous_id: number | null;
  created_by_name: string | null;
  created_at: string | null;
}

export interface MetricMeta {
  key: string;
  label: string;
  unit: string;
  description: string;
  owners: ("system" | "coach")[];
  higher_is_better: boolean;
  min_sample: number;
}

export interface FollowUpListResponse {
  items: FollowUpItem[];
  counts: { overdue: number; today: number; upcoming: number; later: number; closed: number };
  today: string;
  upcoming_days: number;
  meta: {
    categories: Record<string, string>;
    priorities: Record<string, string>;
    metrics: MetricMeta[];
    owner_types: Record<string, string>;
  };
}

export interface FollowUpBody {
  title: string;
  description?: string | null;
  due_on: string;
  category: string;
  priority: string;
  recurrence_days?: number | null;
  check?: { metric_key: string; owner_type: string; min_change: number } | null;
  baseline_on?: string | null;
}

export interface FollowUpPatchBody extends Partial<FollowUpBody> {
  clear_recurrence?: boolean;
  clear_check?: boolean;
}

export interface MetricPoint {
  on: string;
  value: number | null;
  n?: number | null;
}

export interface MetricSummary extends MetricMeta {
  latest_value: number | null;
  latest_on: string | null;
  sample_n: number | null;
  delta_7d: number | null;
  delta_30d: number | null;
  coach_count: number;
  points: MetricPoint[];
}

export interface MetricsResponse {
  metrics: MetricSummary[];
  today: string;
  history_since: string | null;
}

export interface MetricOwnerSeries {
  owner_type: "system" | "coach";
  owner_id: number;
  owner_label: string;
  latest_value: number | null;
  latest_on: string;
  sample_n: number | null;
  enough_sample: boolean;
  delta_21d: number | null;
  points: MetricPoint[];
}

export interface MetricDetailResponse {
  metric: MetricMeta;
  days: number;
  owners: MetricOwnerSeries[];
  linked_follow_ups: { id: number; title: string; effective_due: string }[];
}
