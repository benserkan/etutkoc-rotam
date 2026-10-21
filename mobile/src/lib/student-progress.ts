/**
 * Öğrenci Gelişim (2026-10-21) — web /student/progress ile aynı uçlar:
 * GET /student/analytics · GET /student/weekly-progress · GET /student/topic-performance.
 * PDF: POST /student/pdf-link → 15 dk geçerli imzalı bağlantı (telefonun tarayıcısında açılır).
 */
import { Linking } from "react-native";

import { API_BASE, apiRequest } from "./api";

export interface ProgSummary {
  rate_7d: number;
  rate_30d: number;
  consistency_7d_pct: number;
  hit_rate_7d_pct: number;
  active_days_30: number;
  longest_streak_30: number;
}
export interface ProgProjection {
  exam_label: string | null;
  days_left: number | null;
  total_tests: number;
  completed: number;
  remaining: number;
  projected_completable: number;
  gap: number;
  rate_per_day: number;
  required_rate: number;
  status: "green" | "amber" | "red";
}
export interface ProgSubjectWork {
  subject_id: number;
  name: string;
  total: number;
  accuracy_pct: number | null;
  coverage_pct: number | null;
  started_topics: number;
  total_topics: number;
  next_topic: string | null;
}
export interface ProgCurriculum {
  focus_grade: number | null;
  coverage_pct: number;
  started_topics: number;
  total_topics: number;
  projected_coverage_pct: number | null;
  target_label?: string | null;
}
export interface StudentAnalytics {
  summary: ProgSummary;
  projection: ProgProjection;
  activity_calendar: { date: string; weekday: number; active: boolean; has_plan: boolean }[];
  dow_all?: { weekday: number; label: string; hit_pct: number | null }[];
  exam_trend: { title: string; exam_date: string | null; section_label: string; net: number }[];
  exam_trend_delta: number | null;
  exam_trend_section: string | null;
  subject_work?: ProgSubjectWork[];
  curriculum?: ProgCurriculum | null;
}

export interface WPCard {
  key: string;
  name: string;
  value: number | null;
  value_label: string;
  status: string;
  low: number | null;
  high: number | null;
  verdict: string;
}
export interface WPDay {
  date: string;
  day: string;
  label: string;
  state: "future" | "today" | "none" | "done" | "partial" | "missed";
  total: number;
  done: number;
  missing: { title: string }[];
}
export interface StudentWeeklyProgress {
  has_program: boolean;
  week: { kind?: string; start: string; label: string; day_index: number; days: number; ended: boolean } | null;
  headline: Record<string, WPCard>;
  projection: { projected_pct: number | null; band_low: number | null; band_high: number | null } | null;
  days: WPDay[];
  chart: { label: string; range: string; value: number | null; current: boolean }[];
  period_summary: { weeks: number; median: number | null; band_low: number | null; band_high: number | null } | null;
}
export interface TopicFocusRow {
  topic_name: string;
  subject_name?: string | null;
  accuracy_pct: number | null;
  level?: string;
  exam_only?: boolean;
  wrong: number;
}

export const progressKeys = {
  analytics: ["student", "progress", "analytics"] as const,
  weekly: ["student", "progress", "weekly"] as const,
  focus: ["student", "progress", "topic-focus"] as const,
};

export const getStudentAnalytics = () => apiRequest<StudentAnalytics>("/api/v2/student/analytics");
export const getStudentWeeklyProgress = () => apiRequest<StudentWeeklyProgress>("/api/v2/student/weekly-progress");
export async function getStudentTopicFocus(): Promise<TopicFocusRow[]> {
  const r = await apiRequest<{ focus?: TopicFocusRow[] }>("/api/v2/student/topic-performance");
  return r.focus ?? [];
}

export type PdfKind = "day" | "week" | "exams";

/** PDF'i telefonun tarayıcısında/PDF görüntüleyicisinde açar (oradan paylaş/kaydet). */
export async function openStudentPdf(kind: PdfKind, date?: string): Promise<void> {
  const r = await apiRequest<{ url: string }>("/api/v2/student/pdf-link", {
    method: "POST",
    body: { kind, date: date ?? null },
  });
  await Linking.openURL(`${API_BASE}${r.url}`);
}
