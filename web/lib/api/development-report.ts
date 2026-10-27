/**
 * Öğrenci Gelişim Raporu (360°) — backend app/services/development_report.py.
 * Rapor SAKLANMAZ; her istekte güncel veriden kurulur. QueryKey backend invalidate'iyle:
 * "teacher:{tid}:students:{sid}:development-report" → ["teacher","me","students",sid,"development-report"].
 */
import { api } from "@/lib/api";

export type DRTone = "good" | "warn" | "bad" | "info";

export interface DRItem {
  key: string;
  tone: DRTone;
  title: string;
  text: string;
  agenda: string;
  source: string;
  priority: number;
  cta_label: string | null;
  cta_href: string | null;
  queued: boolean;
}

export interface DRAction {
  key: string;
  title: string;
  detail: string;
  source: "weekly" | "exam" | "data";
  priority: number;
  agenda: string;
  cta_label: string | null;
  cta_href: string | null;
  queued: boolean;
  exam_id?: number | null;
}

export interface DRWeekRow {
  start: string;
  end: string;
  label: string;
  kind: string;
  cut: boolean;
  days: number;
  current: boolean;
  in_baseline: boolean;
  compare_days: number | null;
  gorev_done: number;
  gorev_total: number;
  gorev_pct: number | null;
  test_done: number;
  test_planned: number;
  ontime_pct: number | null;
  night_pct: number | null;
  empty_days: number;
  accuracy_pct: number | null;
  tests_with_result: number;
  tests_done_items: number;
  exam_nets: number[];
  exam_titles: string[];
  /** Tüm genel serilerin o haftaki denemeleri (seri etiketiyle). */
  exam_marks?: { series_label: string | null; title: string; net: number; questions: number | null }[];
}

export interface DRExamSeries {
  series: string | null;
  label: string | null;
  exams: { id: number; title: string; exam_date: string; net: number; questions?: number | null }[];
  stats: DRExamStats | null;
  target: { target_net: number; gap: number | null; basis_net: number } | null;
  subjects: { name: string; nets: (number | null)[]; first: number | null; last: number | null; change: number | null; slope: number | null }[];
  /** Soru sayısı denemeden denemeye değişiyor (okul denemesi) → net yüzdesi öne alınır. */
  varying_questions: boolean;
}

export interface DRCompare {
  key: string;
  name: string;
  hint: string;
  unit: string;
  direction: number;
  value: number | null;
  value_label: string;
  prev: number | null;
  prev_label: string;
  status: string;
  low: number | null;
  high: number | null;
  trend: boolean;
  trend_run: number;
  verdict: string;
}

export interface DRDay {
  date: string;
  day: string;
  label: string;
  state: "future" | "today" | "none" | "done" | "partial" | "missed";
  total: number;
  done: number;
  missing: { title: string; tests: number | null }[];
  first_tick: string | null;
}

export interface DRExamStats {
  count: number;
  first_net: number;
  last_net: number;
  best_net: number;
  avg_net: number;
  avg_last3: number;
  change: number;
  slope: number | null;
  last_date: string;
  days_since_last: number;
}

export interface DRReport {
  student_name: string;
  generated_at: string;
  activity: { last_tick_at: string | null; last_exam_at: string | null };
  has_program: boolean;
  headline: { level: "good" | "watch" | "risk"; text: string };
  this_week: {
    week: {
      start: string;
      end: string;
      label: string;
      day_index: number;
      days: number;
      ended: boolean;
      kind: string;
      compare_days: number;
    };
    row: DRWeekRow | null;
    days: DRDay[];
    projection: { slope_per_week: number | null; band_low: number | null; band_high: number | null } | null;
    compare: DRCompare[];
  } | null;
  weeks: DRWeekRow[];
  journey: {
    weeks: number;
    first_week: string | null;
    start_gorev_pct: number | null;
    recent_gorev_pct: number | null;
    start_tests_per_week: number | null;
    recent_tests_per_week: number | null;
    tests_total: number;
    median_gorev_pct: number | null;
    best_week: { value: number; label: string } | null;
    worst_week: { value: number; label: string } | null;
    slope_per_week: number | null;
    exam: DRExamStats | null;
    exam_label: string | null;
    target: { target_net: number; gap: number | null; basis_net: number } | null;
  } | null;
  exam: {
    series: string | null;
    section_label: string | null;
    exams: { id: number; title: string; exam_date: string; net: number }[];
    subjects: { name: string; nets: (number | null)[]; first: number | null; last: number | null; change: number | null; slope: number | null }[];
    stats: DRExamStats | null;
  };
  exam_series?: DRExamSeries[];
  state: DRItem[];
  strengths: DRItem[];
  opportunities: DRItem[];
  risks: DRItem[];
  actions: DRAction[];
  data_quality: {
    tests_done: number;
    tests_with_result: number;
    result_coverage_pct: number | null;
    program_deneme: Record<"brans" | "genel", { given: number; solved: number; result: number }>;
    exam_count: number;
  };
  queue_count: number;
}

export const developmentReportKeys = {
  report: (studentId: number, series: string | null, period?: string) =>
    ["teacher", "me", "students", String(studentId), "development-report", series ?? "auto", period ?? "current"] as const,
};

export function getDevelopmentReport(studentId: number, series: string | null, period?: string): Promise<DRReport> {
  const p = new URLSearchParams();
  if (series) p.set("series", series);
  if (period) p.set("period", period);
  const q = p.toString();
  return api<DRReport>(`/api/v2/teacher/students/${studentId}/development-report${q ? `?${q}` : ""}`);
}
