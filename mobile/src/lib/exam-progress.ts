/**
 * Deneme analizi Faz 2 + 3 (mobil) — web ile aynı uçlar:
 * gelişim raporu, hedef net, seans gündemi, öğrenciyle paylaşım,
 * genel ortalama, çeldirici analizi, puan tahmini.
 * studentId verilirse koç ucu, null ise öğrencinin kendi ucu.
 */
import { apiRequest } from "@/lib/api";

// ---------------------------------------------------------------- tipler

export interface ProgressStats {
  count: number;
  first_net: number;
  last_net: number;
  best_net: number;
  avg_net: number;
  avg_last3: number;
  change: number;
  slope: number | null;
  last_date: string;
  days_since_last: number;
}

export interface ProgressSubject {
  name: string;
  first: number | null;
  last: number | null;
  change: number | null;
  slope: number | null;
  target: number | null;
  gap: number | null;
}

export interface ProgressTarget {
  target_net: number;
  target_date: string | null;
  subjects: Record<string, number>;
  note: string | null;
  basis: string | null;
  basis_net: number | null;
  gap: number | null;
  progress_pct: number | null;
  weeks_left: number | null;
  exams_needed_at_pace: number | null;
  per_week_needed: number | null;
}

export interface ProgressAction {
  key: string;
  kind: string;
  priority: number;
  title: string;
  detail: string;
  exam_id: number | null;
  queued: boolean;
}

export interface ExamProgressResponse {
  section: string | null;
  section_label: string | null;
  stats: ProgressStats | null;
  subjects: ProgressSubject[];
  target: ProgressTarget | null;
  commentary: { tone: "good" | "warn" | "info"; text: string }[];
  actions: ProgressAction[];
}

export interface ExamShareInfo {
  note: string | null;
  shared_at: string;
  shared_by_name: string | null;
}

export interface DistractorResponse {
  exam_id: number;
  answered: number;
  wrong_count: number;
  letters: { letter: string; chosen: number; key: number; wrong_chosen: number; chosen_pct: number; key_pct: number }[];
  notes: string[];
  peer_count: number;
  peer_min: number;
  questions: {
    subject: string;
    question_no: number | null;
    topic: string | null;
    correct_answer: string | null;
    student_answer: string | null;
    peer_correct_pct: number;
    top_wrong_option: string | null;
    top_wrong_count: number;
    same_as_student: boolean;
  }[];
}

export interface ScoreEstimateResponse {
  kind: "lgs" | "yks" | null;
  scores: { key: string; label: string; score: number; max: number; detail: string | null; is_student_track: boolean }[];
  inputs: { id: number; title: string; exam_date: string; section_label: string; net: number; karne_score: number | null }[];
  calibration: { exam_id: number; title: string; karne_score: number; estimate: number; diff: number }[];
  warnings: string[];
  disclaimer: string;
}

// ---------------------------------------------------------------- anahtarlar

const who = (studentId: number | null) => (studentId == null ? "me" : String(studentId));

export const examProgressKeys = {
  all: (studentId: number | null) => ["exam-progress", who(studentId)] as const,
  progress: (studentId: number | null, section: string | null) =>
    ["exam-progress", who(studentId), "report", section ?? "auto"] as const,
  shares: (studentId: number | null) => ["exam-progress", who(studentId), "shares"] as const,
  score: (studentId: number | null) => ["exam-progress", who(studentId), "score"] as const,
  distractors: (studentId: number | null, examId: number) =>
    ["exam-progress", who(studentId), "distractors", examId] as const,
};

// ---------------------------------------------------------------- okuma

export function getExamProgress(studentId: number | null, section: string | null): Promise<ExamProgressResponse> {
  const q = section ? `?section=${encodeURIComponent(section)}` : "";
  return apiRequest<ExamProgressResponse>(
    studentId == null ? `/api/v2/student/exam-progress${q}` : `/api/v2/teacher/students/${studentId}/exam-progress${q}`,
  );
}

export function getExamShares(studentId: number | null): Promise<{ shares: Record<string, ExamShareInfo> }> {
  return apiRequest(
    studentId == null ? "/api/v2/student/exam-shares" : `/api/v2/teacher/students/${studentId}/exam-shares`,
  );
}

export function getScoreEstimate(studentId: number | null): Promise<ScoreEstimateResponse> {
  return apiRequest<ScoreEstimateResponse>(
    studentId == null ? "/api/v2/student/score-estimate" : `/api/v2/teacher/students/${studentId}/score-estimate`,
  );
}

export function getDistractors(studentId: number | null, examId: number): Promise<DistractorResponse> {
  return apiRequest<DistractorResponse>(
    studentId == null ? `/api/v2/student/exams/${examId}/distractors` : `/api/v2/teacher/exams/${examId}/distractors`,
  );
}

// ---------------------------------------------------------------- koç işlemleri

export function setExamTarget(
  studentId: number,
  body: { section: string; target_net: number | null; target_date?: string | null; note?: string | null },
): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${studentId}/exam-targets`, { method: "POST", body });
}

export function addAgendaItems(
  studentId: number,
  items: { text: string; key?: string | null; exam_id?: number | null; source?: string }[],
): Promise<{ added: number }> {
  return apiRequest(`/api/v2/teacher/students/${studentId}/agenda-queue`, { method: "POST", body: { items } });
}

export function shareExamWithStudent(examId: number, note: string, notify: boolean): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/exams/${examId}/share-student`, { method: "POST", body: { note, notify } });
}

export function unshareExam(examId: number): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/exams/${examId}/unshare-student`, { method: "POST" });
}

export function setExamAverages(
  examId: number,
  body: { label?: string | null; total?: number | null; subjects?: Record<string, number | null> },
): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/exams/${examId}/averages`, { method: "POST", body });
}

// ---------------------------------------------------------------- biçim

export function fmtNet(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(2).replace(".", ",");
}

export function fmtSigned(n: number): string {
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${fmtNet(Math.abs(n))}`;
}

export function fmtTRDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}.${y}`;
}

export function parseNum(v: string): number | null {
  const n = Number(v.replace(",", "."));
  return v.trim() === "" || Number.isNaN(n) ? null : n;
}
