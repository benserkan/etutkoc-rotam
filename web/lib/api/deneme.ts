/**
 * Deneme görevleri (D1) — koçun "Deneme" formu.
 * Backend: app/routes/api_v2/deneme_tasks.py · kurallar app/services/deneme_service.py
 * Kural: 1 kalem = 1 deneme; "×2" = 1 görev, 2 kalem.
 */
import { api } from "@/lib/api";

export interface DenemeSubjectOption {
  id: number;
  name: string;
  exam_section: string | null;
  standard_question_count: number | null;
  deneme_book_count: number;
}

export interface DenemeBookOption {
  book_id: number;
  name: string;
  type: "brans_denemesi" | "genel_deneme" | string;
  subject_id: number;
  question_count: number | null;
  question_source: "label" | "book" | "standard" | "none" | string;
  remaining_total: number;
  next_sections: { section_id: number; label: string; remaining: number }[];
}

export interface DenemeGenelPreset {
  key: string;
  label: string;
  exam_section: string;
  question_count: number;
}

export interface DenemeTemplate {
  kind: "brans" | "genel";
  label: string;
  count: number;
  question_count: number;
  subject_id: number | null;
  exam_section: string | null;
  book_id: number | null;
  uses: number;
}

export interface DenemeOptionsResponse {
  subjects: DenemeSubjectOption[];
  books: DenemeBookOption[];
  genel_presets: DenemeGenelPreset[];
  templates: DenemeTemplate[];
  max_count: number;
}

export interface DenemeTaskBody {
  date: string;
  period?: string | null;
  scheduled_hour?: number | null;
  is_draft?: boolean | null;
  kind: "brans" | "genel";
  count: number;
  question_count?: number | null;
  subject_id?: number | null;
  book_id?: number | null;
  genel_key?: string | null;
  name?: string | null;
  notes?: string | null;
}

export const denemeKeys = {
  options: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "deneme-options"] as const,
  analysis: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "deneme-analysis"] as const,
};

export function getDenemeOptions(studentId: number): Promise<DenemeOptionsResponse> {
  return api<DenemeOptionsResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/deneme-options`,
  );
}

/** Şablon çipinin gövdesi — tek tıkla görev. */
export function templateToBody(
  t: DenemeTemplate,
  base: Pick<DenemeTaskBody, "date" | "period" | "scheduled_hour">,
  genelPresets: DenemeGenelPreset[],
): DenemeTaskBody {
  if (t.kind === "genel") {
    const preset =
      genelPresets.find((p) => p.exam_section === t.exam_section) ?? genelPresets[0];
    return {
      ...base,
      kind: "genel",
      count: t.count,
      question_count: t.question_count,
      genel_key: preset?.key ?? null,
      book_id: t.book_id,
    };
  }
  return {
    ...base,
    kind: "brans",
    count: t.count,
    question_count: t.question_count,
    subject_id: t.book_id ? null : t.subject_id,
    book_id: t.book_id,
  };
}

// --- D4 — program denemesi analizi (backend app/services/deneme_analysis.py) ---

export interface DenemeAnalysisPoint {
  exam_id: number;
  date: string;
  title: string;
  net: number;
  questions: number | null;
  /** net ÷ soru × 100 — farklı soru sayılı denemeler kıyaslanabilsin */
  net_pct: number | null;
  correct: number;
  wrong: number;
  blank: number;
  duration_minutes: number | null;
}

export interface DenemeAnalysisSeries {
  key: string;
  label: string;
  kind: "genel" | "brans";
  subject: string | null;
  section: string;
  count: number;
  correct: number;
  wrong: number;
  blank: number;
  accuracy_pct: number | null;
  blank_rate_pct: number | null;
  avg_net_pct: number | null;
  last_net_pct: number | null;
  min_per_question: number | null;
  timed_count: number;
  /** Öğrencinin normal aralığı (net %'nin çeyrekler arası bandı, ≥4 deneme) */
  normal_low: number | null;
  normal_high: number | null;
  last_position: "below" | "within" | "above" | null;
  decline_run: number;
  slope: number | null;
  direction: "up" | "down" | "flat" | null;
  projected_net_pct: number | null;
  pending: number;
  test_accuracy_pct: number | null;
  test_answered: number | null;
  genel_accuracy_pct: number | null;
  genel_exams: number | null;
  legacy_rows: number | null;
  legacy_accuracy_pct: number | null;
  combined_accuracy_pct: number | null;
  // Ek açılar (2026-10-20)
  best_net_pct?: number | null;
  best_date?: string | null;
  worst_net_pct?: number | null;
  worst_date?: string | null;
  /** Eğilim doğrusundan sapmaların std. sapması (net % puanı) — küçük = tutarlı */
  stdev_net_pct?: number | null;
  consistency?: "high" | "mid" | "low" | null;
  /** Son k denemenin ortalaması − önceki k denemenin ortalaması (net % puanı) */
  momentum?: number | null;
  momentum_window?: number | null;
  penalty?: number;
  avg_net?: number | null;
  avg_questions?: number | null;
  /** Deneme başına yanlışların götürdüğü net (yanlış × (1 + 1/ceza)) */
  lost_wrong_per_exam?: number | null;
  lost_blank_per_exam?: number | null;
  first_date?: string | null;
  last_date?: string | null;
  avg_gap_days?: number | null;
  days_since_last?: number | null;
  points: DenemeAnalysisPoint[];
}

export interface DenemeOverviewPick {
  key: string;
  label: string;
  value: number;
}

export interface DenemeOverview {
  exams: number;
  subjects: number;
  questions: number;
  correct: number;
  wrong: number;
  blank: number;
  accuracy_pct: number | null;
  blank_rate_pct: number | null;
  avg_net_pct: number | null;
  lost_wrong: number;
  lost_blank: number;
  strongest: DenemeOverviewPick | null;
  weakest: DenemeOverviewPick | null;
  rising: DenemeOverviewPick | null;
  falling: DenemeOverviewPick | null;
  steadiest: DenemeOverviewPick | null;
  weeks: { week_start: string; count: number; subjects: number; avg_net_pct: number | null }[];
}

export interface DenemeAnalysisResponse {
  overview?: DenemeOverview | null;
  generated_for: string;
  compare_days: number;
  summary: { with_result: number; pending: number; series_count: number; branch_series: number };
  series: DenemeAnalysisSeries[];
  flags: { code: string; series: string; level: "info" | "warn"; text: string }[];
}

export function getDenemeAnalysis(studentId: number): Promise<DenemeAnalysisResponse> {
  return api<DenemeAnalysisResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/deneme-analysis`,
  );
}
