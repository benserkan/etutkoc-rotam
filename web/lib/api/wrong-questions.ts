/**
 * Yanlış Soru Arşivi — tipli fetcher'lar + queryKey üreticileri.
 *
 * invalidate sözleşmesi (backend MutationResponse.invalidate):
 *   öğrenci  → "student:wrong-questions"
 *   koç      → "teacher:{tid}:students:{sid}:wrong-questions"
 */
import { api, ApiError, type MutationResponse } from "@/lib/api";
import type {
  WrongQuestionCreateFields,
  WrongQuestionItem,
  WrongQuestionListResponse,
  WrongQuestionSummaryResponse,
} from "@/lib/types/wrong-question";

export const wrongQuestionKeys = {
  studentList: (filter?: string) =>
    ["student", "wrong-questions", filter ?? "all"] as const,
  teacherList: (teacherId: number | "me", studentId: number, filter?: string) =>
    ["teacher", String(teacherId), "students", String(studentId),
      "wrong-questions", filter ?? "all"] as const,
} as const;

export interface StudentWrongListFilters {
  status?: "acik" | "kapandi";
  subject_id?: number;
  error_type?: string;
  source_kind?: string;
  due?: boolean;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "" && v !== false) sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export function getStudentWrongQuestions(
  f: StudentWrongListFilters = {},
): Promise<WrongQuestionListResponse> {
  return api<WrongQuestionListResponse>(
    `/api/v2/student/wrong-questions${qs({ ...f })}`,
  );
}

export function getStudentWrongQuestion(id: number): Promise<WrongQuestionItem> {
  return api<WrongQuestionItem>(`/api/v2/student/wrong-questions/${id}`);
}

export function studentWrongImageUrl(wqId: number, imageId: number): string {
  return `/api/v2/student/wrong-questions/${wqId}/images/${imageId}`;
}

export function teacherWrongImageUrl(wqId: number, imageId: number): string {
  return `/api/v2/teacher/wrong-questions/${wqId}/images/${imageId}`;
}

export function getTeacherStudentWrongQuestions(
  studentId: number,
  f: { status?: string; error_type?: string } = {},
): Promise<WrongQuestionListResponse> {
  return api<WrongQuestionListResponse>(
    `/api/v2/teacher/students/${studentId}/wrong-questions${qs({ ...f })}`,
  );
}

export function getTeacherStudentWrongSummary(
  studentId: number,
): Promise<WrongQuestionSummaryResponse> {
  return api<WrongQuestionSummaryResponse>(
    `/api/v2/teacher/students/${studentId}/wrong-questions/summary`,
  );
}

async function multipart<T>(url: string, fd: FormData): Promise<T> {
  // eslint-disable-next-line lgs/no-bare-fetch -- multipart yükleme; api() JSON sarmalayıcısı FormData ile uyumsuz
  const r = await fetch(url, { method: "POST", credentials: "include", body: fd });
  if (!r.ok) {
    let detail = { error: "error", message: "Yükleme başarısız" };
    try {
      const b = await r.json();
      if (b?.detail && typeof b.detail === "object") detail = b.detail;
    } catch {
      /* yoksay */
    }
    throw new ApiError(r.status, detail);
  }
  return r.json() as Promise<T>;
}

/** Yanlış soru ekle — 0..N fotoğraf + opsiyonel bağlam alanları (multipart). */
export function createStudentWrongQuestion(
  fields: WrongQuestionCreateFields,
  photos: File[],
): Promise<MutationResponse<WrongQuestionItem>> {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) {
    if (v !== undefined && v !== null && v !== "") fd.append(k, String(v));
  }
  for (const p of photos) fd.append("photos", p);
  return multipart<MutationResponse<WrongQuestionItem>>(
    "/api/v2/student/wrong-questions", fd,
  );
}

/** Mevcut kayda fotoğraf ekle (kind: question | solution). */
export function addStudentWrongImage(
  wqId: number,
  file: File,
  kind: "question" | "solution",
): Promise<MutationResponse<WrongQuestionItem>> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("kind", kind);
  return multipart<MutationResponse<WrongQuestionItem>>(
    `/api/v2/student/wrong-questions/${wqId}/images`, fd,
  );
}
