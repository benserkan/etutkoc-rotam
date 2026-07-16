/**
 * Deneme PDF içe aktarma — multipart fetcher'lar (koç + öğrenci yüzeyi).
 *
 * İki aşama: analyze (PDF → önizleme taslağı; KREDİ burada düşer) →
 * confirm (düzeltilmiş satırlar + aynı PDF kanıt olarak → ExamResult).
 * Sunucu tarafında taslak durumu yok — dosya client state'inde tutulur ve
 * confirm'de yeniden gönderilir.
 */
import { ApiError, type MutationResponse } from "@/lib/api";
import type {
  ExamImportConfirmBody,
  ExamImportConfirmResult,
  ExamImportDraft,
} from "@/lib/types/exam-import";

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

/** Koç: öğrencisinin deneme PDF'ini analiz et (kredi düşer, kayıt YAPMAZ). */
export function teacherAnalyzeExamPdf(
  studentId: number,
  file: File,
): Promise<ExamImportDraft> {
  const fd = new FormData();
  fd.append("file", file);
  return multipart<ExamImportDraft>(
    `/api/v2/teacher/students/${studentId}/exams/import-analyze`, fd,
  );
}

/** Koç: düzeltilmiş taslağı kaydet (kredi düşmez; PDF kanıt olarak saklanır). */
export function teacherConfirmExamImport(
  studentId: number,
  body: ExamImportConfirmBody,
  file: File | null,
): Promise<MutationResponse<ExamImportConfirmResult>> {
  const fd = new FormData();
  fd.append("payload", JSON.stringify(body));
  if (file) fd.append("file", file);
  return multipart<MutationResponse<ExamImportConfirmResult>>(
    `/api/v2/teacher/students/${studentId}/exams/import-confirm`, fd,
  );
}

/** Öğrenci: kendi deneme PDF'ini analiz et (kredi KOÇUN havuzundan). */
export function studentAnalyzeExamPdf(file: File): Promise<ExamImportDraft> {
  const fd = new FormData();
  fd.append("file", file);
  return multipart<ExamImportDraft>("/api/v2/student/exams/import-analyze", fd);
}

export function studentConfirmExamImport(
  body: ExamImportConfirmBody,
  file: File | null,
): Promise<MutationResponse<ExamImportConfirmResult>> {
  const fd = new FormData();
  fd.append("payload", JSON.stringify(body));
  if (file) fd.append("file", file);
  return multipart<MutationResponse<ExamImportConfirmResult>>(
    "/api/v2/student/exams/import-confirm", fd,
  );
}
