/**
 * Öğrenci detayı — haftalık ilerleme (backend app/services/weekly_progress.py).
 * Kıyas: geçmiş program haftalarının AYNI GÜNÜNE KADAR; "genelde" = taban haftaların
 * çeyrekler arası bandı (ortalama değil).
 */
import { api } from "@/lib/api";
import type { DenemeAnalysisResponse } from "@/lib/api/deneme";

/** info: kıyas yapılmayan bilgi kartı (talep/devir, yanlış arşivi, dengeli ders dağılımı) */
export type WPStatus = "insufficient" | "normal" | "below" | "critical" | "above" | "high" | "low" | "info";

export interface WPCard {
  key: string;
  name: string;
  hint: string;
  group: "gelisim" | "ilerleme" | "risk";
  unit: string;
  /** +1 yüksek iyi · -1 düşük iyi · 0 nötr (yük) */
  direction: number;
  value: number | null;
  value_label: string;
  prev: number | null;
  prev_label: string;
  status: WPStatus;
  low: number | null;
  high: number | null;
  /** Taban haftaların aynı noktadaki değerleri (cetveldeki gri noktalar) */
  baseline: number[];
  trend_run: number;
  trend: boolean;
  verdict: string;
}

export interface WPDay {
  date: string;
  day: string;
  label: string;
  state: "future" | "today" | "none" | "done" | "partial" | "missed";
  total: number;
  done: number;
  missing: { title: string; tests: number | null }[];
  first_tick: string | null;
}

export interface WeeklyProgressResponse {
  has_program: boolean;
  week: {
    program_id: number;
    /** program | takvim (programsız görev günleri) | donem (havuz dönemi) */
    kind?: "program" | "takvim" | "donem";
    start: string;
    end: string;
    label: string;
    day_index: number;
    days: number;
    ended: boolean;
    today_label: string;
    compare_days: number;
    usual_start: string;
    marks_next_day?: boolean;
    next_day_mark_time?: string | null;
  } | null;
  headline: Record<string, WPCard>;
  projection: {
    same_point_pct: number | null;
    projected_pct: number | null;
    band_low: number | null;
    band_high: number | null;
    position: "below" | "within" | "above" | null;
    last4: number[];
    slope_per_week: number | null;
    load: number;
  } | null;
  days: WPDay[];
  chart: { label: string; range: string; value: number | null; current: boolean; in_baseline: boolean }[];
  period_summary: {
    weeks: number;
    median: number | null;
    best: { value: number; label: string } | null;
    worst: { value: number; label: string } | null;
    band_low: number | null;
    band_high: number | null;
    decline_run: number;
  } | null;
  groups: { key: string; name: string; desc: string }[];
  cards: WPCard[];
  actions: { key: string; title: string; why: string; cta_label: string; cta_href: string; agenda: string }[];
  deneme: DenemeAnalysisResponse | null;
  /** Haftanın 1. günü (kıyas yok): geçen haftanın tam sonucu, aynı kartlar. */
  last_week?: { label: string; start: string; end: string; kind?: string; cards: WPCard[] } | null;
  /** Genel sekmesinin üstü — yalnız koç görür. */
  overview?: WPOverview | null;
}

export type WPTone = "warn" | "info" | "ok" | "good";

export interface WPOverview {
  reliability: { key: string; tone: WPTone; title: string; text: string; agenda: string | null }[];
  exam: {
    series_label: string;
    count: number;
    last_net: number;
    last_date: string;
    prev_net: number | null;
    diff: number | null;
    slope: number | null;
    slope_window: number;
    avg_last3: number;
    tone: WPTone;
    text: string;
  } | null;
  target: {
    target_net: number;
    target_date: string | null;
    gap: number;
    weeks_left: number | null;
    per_week_needed: number | null;
    pace_per_week: number | null;
    realistic: boolean | null;
    tone: WPTone;
    text: string;
    agenda: string | null;
  } | null;
}

export const weeklyProgressKeys = {
  detail: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "weekly-progress"] as const,
};

export function getWeeklyProgress(studentId: number): Promise<WeeklyProgressResponse> {
  return api<WeeklyProgressResponse>(
    `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/weekly-progress`,
  );
}
