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
