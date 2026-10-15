import { apiRequest } from "./api";

// Ders → Konu performansı (P1) — koç / öğrenci / veli ortak.
export interface TopicPerfRow {
  topic_id: number | null;
  topic_name: string;
  tests_solved: number;
  correct: number;
  wrong: number;
  answered: number;
  accuracy_pct: number | null;
  last_solved_at: string | null;
  // 2026-10-14 — veri kalitesi + deneme kıyası + seviye (web ile aynı sözleşme)
  blank?: number;
  tests_with_result?: number;
  session_tests?: number;
  exam_answered?: number;
  exam_correct?: number;
  exam_accuracy_pct?: number | null;
  level?: "zayif" | "dikkat" | "iyi" | "veri_yok";
  loss_score?: number;
  subject_id?: number | null;
  subject_name?: string | null;
  exam_only?: boolean;
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
  blank?: number;
  tests_with_result?: number;
  session_tests?: number;
  weak_topics?: number;
}
export interface TopicPerformanceOverall {
  tests_solved: number;
  correct: number;
  wrong: number;
  answered: number;
  accuracy_pct: number | null;
  subject_count: number;
  topic_count: number;
  blank?: number;
  tests_with_result?: number;
  session_tests?: number;
  result_coverage_pct?: number | null;
  weak_topics?: number;
}
export interface TopicPerformanceResponse {
  overall: TopicPerformanceOverall;
  subjects: SubjectPerfRow[];
  /** "Nerede kaybediyor" — zayıf/dikkat konular kayıp sırasıyla */
  focus?: TopicPerfRow[];
}

export type TopicPerfSource = "teacher" | "student" | "parent";

export const topicPerfKeys = {
  teacher: (id: number) => ["teacher", "student", id, "topic-performance"] as const,
  student: () => ["student", "topic-performance"] as const,
  parent: (id: number) => ["parent", "student", id, "topic-performance"] as const,
};

export function getTopicPerformance(source: TopicPerfSource, studentId?: number): Promise<TopicPerformanceResponse> {
  if (source === "student") return apiRequest<TopicPerformanceResponse>(`/api/v2/student/topic-performance`);
  if (source === "parent") return apiRequest<TopicPerformanceResponse>(`/api/v2/parent/students/${studentId}/topic-performance`);
  return apiRequest<TopicPerformanceResponse>(`/api/v2/teacher/students/${studentId}/topic-performance`);
}
