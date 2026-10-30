/**
 * Konusuz test görevleri → müfredat konusu (2026-10-16).
 *
 * Koç "Diğer" etkinliğine "2 test" yazınca içindeki testler hiçbir tabloya
 * giremiyordu (Açı Seçkin Kurs saha bulgusu). Bu modül:
 *   · görev formunda konu önerisi (task-topic-suggest)
 *   · dersin alt konuları (elle seçim)
 *   · koçun konusuz test görevleri + toplu bağlama
 */
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";

export interface TopicOption {
  topic_id: number;
  name: string;
  grade_level: number | null;
  parent_name: string | null;
  /** Yalnız dersin sınav karşılığından (TYT) geldiyse dolu */
  subject_name: string | null;
}

export interface TopicSuggestion {
  subject_id: number | null;
  subject_name: string | null;
  test_count: number | null;
  /** test | soru | sayfa — test_count'ın birimi */
  count_unit?: CountUnit | null;
  topic: TopicOption | null;
  confident: boolean;
  options: TopicOption[];
  reason: string;
}

export interface SubjectTopicsResponse {
  subject_id: number;
  subject_name: string;
  topics: TopicOption[];
}

export interface UnlinkedTask {
  task_id: number;
  student_id: number;
  student_name: string;
  date: string;
  title: string;
  notes: string | null;
  status: string;
  is_draft: boolean;
  subject_id: number | null;
  subject_name: string | null;
  suggestion: TopicSuggestion;
}

export interface UnlinkedTasksResponse {
  total: number;
  completed: number;
  students: number;
  items: UnlinkedTask[];
}

export interface ConvertItem {
  task_id: number;
  topic_id: number;
  planned_count: number;
  unit?: CountUnit | null;
}

export interface ConvertResponse {
  converted: number;
  failed: number;
  results: { task_id: number; ok: boolean; code: string | null; message: string | null }[];
}

export const taskTopicKeys = {
  unlinked: (studentId: number | null) =>
    ["teacher", "me", "unlinked-test-tasks", studentId === null ? "all" : String(studentId)] as const,
  subjectTopics: (studentId: number, subjectId: number) =>
    ["teacher", "me", "students", String(studentId), "subject-topics", String(subjectId)] as const,
  suggest: (studentId: number, subjectId: number, text: string, notes: string) =>
    ["teacher", "me", "students", String(studentId), "task-topic-suggest", String(subjectId), text, notes] as const,
};

export type CountUnit = "test" | "soru" | "sayfa";

/** "2 test", "3 adet test", "30 soru", "4 sayfa" — backend `extract_count` aynası.
 *  Öncelik test > soru > sayfa; "40 soruluk deneme" soru sayılmaz. */
const UNIT_PATTERNS: [CountUnit, RegExp, number][] = [
  ["test", /(\d{1,2})\s*(?:adet\s*)?(?:yaprak\s*)?tes(?:t|tler)?\b/i, 30],
  ["soru", /(\d{1,3})\s*(?:adet\s*)?soru(?:lar)?\b/i, 300],
  ["sayfa", /(\d{1,3})\s*(?:sayfa(?:lar)?|sf)\b/i, 200],
];

export const COUNT_UNIT_MAX: Record<CountUnit, number> = { test: 30, soru: 300, sayfa: 200 };

export function extractCount(
  ...texts: (string | null | undefined)[]
): { count: number; unit: CountUnit } | null {
  for (const [unit, rx, max] of UNIT_PATTERNS) {
    for (const t of texts) {
      if (!t) continue;
      const m = rx.exec(t);
      if (m) {
        const n = Number(m[1]);
        if (n >= 1 && n <= max) return { count: n, unit };
      }
    }
  }
  return null;
}

/** Geriye uyum: yalnız sayı. */
export function extractTestCount(...texts: (string | null | undefined)[]): number | null {
  return extractCount(...texts)?.count ?? null;
}

/** Görev kalemi `unit` alanı: test → null (varsayılan). */
export function itemUnit(unit: CountUnit | null | undefined): "soru" | "sayfa" | null {
  return unit === "soru" || unit === "sayfa" ? unit : null;
}

export function getTaskTopicSuggest(
  studentId: number,
  body: { subject_id: number; text: string; notes: string | null },
): Promise<TopicSuggestion> {
  return api<TopicSuggestion>(`/api/v2/teacher/students/${studentId}/task-topic-suggest`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getSubjectTopics(studentId: number, subjectId: number): Promise<SubjectTopicsResponse> {
  return api<SubjectTopicsResponse>(
    `/api/v2/teacher/students/${studentId}/subject-topics?subject_id=${subjectId}`,
  );
}

export function getUnlinkedTestTasks(studentId: number | null): Promise<UnlinkedTasksResponse> {
  const qs = studentId === null ? "" : `?student_id=${studentId}`;
  return api<UnlinkedTasksResponse>(`/api/v2/teacher/unlinked-test-tasks${qs}`);
}

export function useConvertUnlinkedTasks() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<ConvertResponse>, ApiError, { items: ConvertItem[] }>({
    mutationFn: (body) =>
      api<MutationResponse<ConvertResponse>>(`/api/v2/teacher/unlinked-test-tasks/convert`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (err) => toast.error(err.message || "Görevler konuya bağlanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const { converted, failed } = res.data;
      if (failed > 0) {
        toast.warning(`${converted} görev bağlandı, ${failed} görev bağlanamadı.`);
      } else {
        toast.success(`${converted} görev konuya bağlandı — tablolara yansıdı.`);
      }
    },
  });
}

export function topicOptionLabel(o: TopicOption): string {
  const parts = [o.name];
  if (o.grade_level) parts.push(`${o.grade_level}. sınıf`);
  if (o.subject_name) parts.push(o.subject_name);
  return parts.join(" · ");
}
