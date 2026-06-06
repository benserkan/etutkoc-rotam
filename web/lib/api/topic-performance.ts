/**
 * Ders → Konu performansı (P1) — koç / öğrenci / veli 3 yüzey ortak.
 * Backend: GET .../topic-performance (teacher/student/parent).
 */
import { api } from "@/lib/api";

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

export const topicPerfKeys = {
  teacher: (studentId: number) => ["teacher", "student", studentId, "topic-performance"] as const,
  student: () => ["student", "topic-performance"] as const,
  parent: (studentId: number) => ["parent", "student", studentId, "topic-performance"] as const,
};

export function getTeacherTopicPerformance(studentId: number) {
  return api<TopicPerformanceResponse>(`/api/v2/teacher/students/${studentId}/topic-performance`);
}
export function getStudentTopicPerformance() {
  return api<TopicPerformanceResponse>(`/api/v2/student/topic-performance`);
}
export function getParentTopicPerformance(studentId: number) {
  return api<TopicPerformanceResponse>(`/api/v2/parent/students/${studentId}/topic-performance`);
}
