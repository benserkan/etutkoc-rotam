/**
 * Deneme analizi Faz 2 — gelişim raporu / hedef / gündem kuyruğu / paylaşım.
 *
 * QueryKey sözleşmesi backend invalidate'iyle birebir:
 * "teacher:{tid}:students:{sid}:exam-progress" → ["teacher","me","students",sid,"exam-progress"].
 */
import { api } from "@/lib/api";
import type {
  AgendaQueueResponse,
  ExamProgressResponse,
  ExamSharesResponse,
} from "@/lib/types/exam-progress";

export type ProgressSource =
  | { kind: "teacher"; studentId: number }
  | { kind: "parent"; studentId: number }
  | { kind: "student" };

export const examProgressKeys = {
  progress: (src: ProgressSource, section: string | null, period?: string) =>
    src.kind === "teacher"
      ? ([
          "teacher", "me", "students", String(src.studentId), "exam-progress",
          section ?? "auto", period ?? "current",
        ] as const)
      : src.kind === "parent"
        ? (["parent", "students", String(src.studentId), "exam-progress", section ?? "auto", period ?? "current"] as const)
        : (["student", "exams", "progress", section ?? "auto", period ?? "current"] as const),
  shares: (src: ProgressSource) =>
    src.kind === "teacher"
      ? (["teacher", "me", "students", String(src.studentId), "exam-shares"] as const)
      : (["student", "exams", "shares"] as const),
  queue: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "agenda-queue"] as const,
};

function qs(params: Record<string, string | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

export function getExamProgress(
  src: ProgressSource,
  section: string | null,
  period?: string,
): Promise<ExamProgressResponse> {
  const q = qs({ section, period });
  return api<ExamProgressResponse>(
    src.kind === "teacher"
      ? `/api/v2/teacher/students/${src.studentId}/exam-progress${q}`
      : src.kind === "parent"
        ? `/api/v2/parent/students/${src.studentId}/exam-progress${q}`
        : `/api/v2/student/exam-progress${q}`,
  );
}

export function getExamShares(src: ProgressSource): Promise<ExamSharesResponse> {
  return api<ExamSharesResponse>(
    src.kind === "teacher"
      ? `/api/v2/teacher/students/${src.studentId}/exam-shares`
      : `/api/v2/student/exam-shares`,
  );
}

export function getAgendaQueue(studentId: number): Promise<AgendaQueueResponse> {
  return api<AgendaQueueResponse>(`/api/v2/teacher/students/${studentId}/agenda-queue`);
}

export function progressReportPrintUrl(studentId: number, section: string | null): string {
  return `/teacher/students/${studentId}/exams/report/print${section ? `?section=${section}` : ""}`;
}
