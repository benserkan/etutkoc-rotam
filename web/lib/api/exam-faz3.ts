/** Deneme analizi Faz 3 — çeldirici analizi + birleşik puan tahmini (koç + öğrenci). */
import { api } from "@/lib/api";
import type { ProgressSource } from "@/lib/api/exam-progress";

export interface DistractorLetter {
  letter: string;
  chosen: number;
  key: number;
  wrong_chosen: number;
  chosen_pct: number;
  key_pct: number;
}

export interface DistractorQuestion {
  subject: string;
  question_no: number | null;
  topic: string | null;
  correct_answer: string | null;
  student_answer: string | null;
  result: string;
  peer_count: number;
  peer_correct_pct: number;
  top_wrong_option: string | null;
  top_wrong_count: number;
  same_as_student: boolean;
}

export interface DistractorResponse {
  exam_id: number;
  answered: number;
  wrong_count: number;
  letters: DistractorLetter[];
  notes: string[];
  peer_count: number;
  peer_min: number;
  questions: DistractorQuestion[];
}

export interface ScoreItem {
  key: string;
  label: string;
  score: number;
  max: number;
  based_on: number[];
  detail: string | null;
  is_student_track: boolean;
}

export interface ScoreEstimateResponse {
  generated_at: string;
  kind: "lgs" | "yks" | null;
  scores: ScoreItem[];
  inputs: {
    id: number;
    title: string;
    exam_date: string;
    section_label: string;
    net: number;
    karne_score: number | null;
  }[];
  calibration: {
    exam_id: number;
    title: string;
    exam_date: string;
    karne_score: number;
    estimate: number;
    diff: number;
  }[];
  warnings: string[];
  disclaimer: string;
}

export const faz3Keys = {
  distractors: (src: "teacher" | "student", examId: number) =>
    src === "teacher"
      ? (["teacher", "me", "exams", String(examId), "distractors"] as const)
      : (["student", "exams", String(examId), "distractors"] as const),
  score: (src: ProgressSource) =>
    src.kind === "teacher"
      ? (["teacher", "me", "students", String(src.studentId), "exams", "score-estimate"] as const)
      : (["student", "exams", "score-estimate"] as const),
};

export function getDistractors(src: "teacher" | "student", examId: number): Promise<DistractorResponse> {
  return api<DistractorResponse>(
    src === "teacher"
      ? `/api/v2/teacher/exams/${examId}/distractors`
      : `/api/v2/student/exams/${examId}/distractors`,
  );
}

export function getScoreEstimate(src: ProgressSource): Promise<ScoreEstimateResponse> {
  return api<ScoreEstimateResponse>(
    src.kind === "teacher"
      ? `/api/v2/teacher/students/${src.studentId}/score-estimate`
      : `/api/v2/student/score-estimate`,
  );
}
