/**
 * Deneme analizi · Genel Bakış — backend app/services/exam_overview.py (tek merkez).
 * Anahtarlar "…:exams" önekinin altında: deneme ekle/sil/düzelt mevcut bayatlatmayla tazelenir.
 */
import { api } from "@/lib/api";
import type { ProgressSource } from "@/lib/api/exam-progress";
import type { PeriodFilterMeta } from "@/lib/types/period";

export interface OvSeriesOption {
  value: string;
  label: string;
  count: number;
  kind: "genel" | "brans";
  section: string;
}

export interface OvLast {
  id: number;
  title: string;
  date: string;
  section_label: string;
  net: number;
  correct: number;
  wrong: number;
  blank: number;
  questions: number;
  penalty: number;
  delta: number | null;
  prev_net: number | null;
  is_record: boolean;
  avg_last3: number;
  karne_score: number | null;
  estimate: number | null;
  calibration_mae: number | null;
}

export interface OvLossSubject {
  name: string;
  lost_wrong: number;
  lost_blank: number;
  lost: number;
  wrong: number;
  blank: number;
  questions: number;
}

export interface OvLoss {
  total: number;
  from_wrong: number;
  from_blank: number;
  wrong_cost: number;
  subjects: OvLossSubject[];
  others: { count: number; lost_wrong: number; lost_blank: number; lost: number } | null;
  note: string | null;
}

export interface OvPoint {
  id: number;
  date: string;
  label: string;
  net: number;
  correct: number;
  wrong: number;
  blank: number;
  title: string;
}

export interface OvReading {
  tone: "good" | "warn" | "info";
  title: string;
  text: string;
}

export interface OvTrend {
  points: OvPoint[];
  first_net: number;
  last_net: number;
  best_net: number;
  worst_net: number;
  avg_net: number;
  slope: number | null;
  projection: number | null;
  band_low: number | null;
  band_high: number | null;
  target: number | null;
  readings: OvReading[];
}

export interface OvCell {
  net: number;
  correct: number;
  wrong: number;
  blank: number;
  questions: number;
  ratio: number | null;
}

export interface OvSubjectRow {
  name: string;
  questions: number;
  cells: (OvCell | null)[];
  change: number | null;
  reading: string;
  total_wrong: number;
  total_blank: number;
  blank_share: number;
  chronic_blank: boolean;
}

export interface OvOpportunity {
  topic_id: number;
  topic_name: string;
  subject_name: string;
  total: number;
  wrong: number;
  blank: number;
  accuracy: number;
  net_gain_per_exam: number;
}

export interface OvTrendTopic {
  topic_id: number;
  topic_name: string;
  subject_name: string;
  first_accuracy: number;
  last_accuracy: number;
}

export interface OvHeatRow {
  topic_id: number;
  topic_name: string;
  subject_name: string;
  total: number;
  accuracy: number;
  cells: ({ correct: number; total: number; accuracy: number } | null)[];
}

export interface OvTopics {
  exams: { id: number; label: string; date: string }[];
  opportunities: OvOpportunity[];
  opportunities_sum: number;
  opportunities_total: number;
  forgotten: OvTrendTopic[];
  improved: OvTrendTopic[];
  heatmap: OvHeatRow[];
  analyzed: number;
  unmatched: number;
  pdf_exams: number;
}

export interface OvBehavior {
  subjects: {
    name: string;
    wrong: number;
    blank: number;
    questions: number;
    wrong_share: number;
    tendency: "riskli" | "cekingen" | "dengeli" | null;
  }[];
  series: { label: string; date: string; wrong: number; blank: number }[];
  total_wrong: number;
  total_blank: number;
  reading: string | null;
}

export interface OvScore {
  scores: { key: string; label: string; score: number; max: number; based_on: number[]; detail?: string }[];
  calibration: { exam_id: number; title: string; exam_date: string; karne_score: number; estimate: number; diff: number }[];
  warnings: string[];
  kind: string | null;
}

export interface OvAgendaItem {
  key: string;
  title: string;
  subject: string;
  text: string;
  agenda: string;
}

export interface ExamOverviewResponse {
  series: string | null;
  series_label: string | null;
  series_options: OvSeriesOption[];
  is_general: boolean;
  count: number;
  period: PeriodFilterMeta | null;
  last: OvLast | null;
  loss: OvLoss | null;
  trend: OvTrend | null;
  subjects: OvSubjectRow[];
  topics: OvTopics | null;
  behavior: OvBehavior | null;
  score: OvScore | null;
  agenda: OvAgendaItem[];
}

export const examOverviewKeys = {
  overview: (src: ProgressSource, series: string | null, period?: string) =>
    src.kind === "teacher"
      ? (["teacher", "me", "students", String(src.studentId), "exams", "overview", series ?? "auto", period ?? "current"] as const)
      : src.kind === "parent"
        ? (["parent", "students", String(src.studentId), "exams", "overview", series ?? "auto", period ?? "current"] as const)
        : (["student", "exams", "overview", series ?? "auto", period ?? "current"] as const),
};

export function getExamOverview(
  src: ProgressSource,
  series: string | null,
  period?: string,
): Promise<ExamOverviewResponse> {
  const p = new URLSearchParams();
  if (series) p.set("series", series);
  if (period) p.set("period", period);
  const q = p.toString() ? `?${p}` : "";
  return api<ExamOverviewResponse>(
    src.kind === "teacher"
      ? `/api/v2/teacher/students/${src.studentId}/exam-overview${q}`
      : src.kind === "parent"
        ? `/api/v2/parent/students/${src.studentId}/exam-overview${q}`
        : `/api/v2/student/exam-overview${q}`,
  );
}
