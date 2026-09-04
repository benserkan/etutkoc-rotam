/**
 * Ders → Konu performansı (P1) — koç / öğrenci / veli 3 yüzey ortak.
 * Backend: GET .../topic-performance (teacher/student/parent).
 */
import { api } from "@/lib/api";
import type { PeriodFilterMeta } from "@/lib/types/period";

export interface TopicPerfRow {
  topic_id: number | null;
  topic_name: string;
  tests_solved: number;
  correct: number;
  wrong: number;
  answered: number;
  accuracy_pct: number | null;
  last_solved_at: string | null;
}
export interface SubjectPerfRow {
  subject_id: number;
  subject_name: string;
  tests_solved: number;
  correct: number;
  wrong: number;
  answered: number;
  accuracy_pct: number | null;
  topics: TopicPerfRow[];
}
export interface TopicPerformanceOverall {
  tests_solved: number;
  correct: number;
  wrong: number;
  answered: number;
  accuracy_pct: number | null;
  subject_count: number;
  topic_count: number;
}
export interface TopicPerformanceResponse {
  overall: TopicPerformanceOverall;
  subjects: SubjectPerfRow[];
  /** P3 — hangi sınıf dönemine göre süzüldü. */
  period?: PeriodFilterMeta | null;
}

export const topicPerfKeys = {
  teacher: (studentId: number, period?: string) =>
    ["teacher", "student", studentId, "topic-performance", period ?? "current"] as const,
  student: (period?: string) =>
    ["student", "topic-performance", period ?? "current"] as const,
  parent: (studentId: number, period?: string) =>
    ["parent", "student", studentId, "topic-performance", period ?? "current"] as const,
};

/** P3: `period` verilmezse backend GÜNCEL dönemi uygular. */
function periodQuery(period?: string): string {
  return period ? `?period=${encodeURIComponent(period)}` : "";
}

export function getTeacherTopicPerformance(studentId: number, period?: string) {
  return api<TopicPerformanceResponse>(
    `/api/v2/teacher/students/${studentId}/topic-performance${periodQuery(period)}`,
  );
}
export function getStudentTopicPerformance(period?: string) {
  return api<TopicPerformanceResponse>(
    `/api/v2/student/topic-performance${periodQuery(period)}`,
  );
}
export function getParentTopicPerformance(studentId: number, period?: string) {
  return api<TopicPerformanceResponse>(
    `/api/v2/parent/students/${studentId}/topic-performance${periodQuery(period)}`,
  );
}
