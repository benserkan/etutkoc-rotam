/**
 * Deneme PDF içe aktarma — multipart fetcher'lar (koç + öğrenci yüzeyi).
 *
 * İki aşama: analyze (PDF → önizleme taslağı; KREDİ burada düşer) →
 * confirm (düzeltilmiş satırlar + aynı PDF kanıt olarak → ExamResult).
 * Sunucu tarafında taslak durumu yok — dosya client state'inde tutulur ve
 * confirm'de yeniden gönderilir.
 */
import { api, ApiError, type MutationResponse } from "@/lib/api";
import type {
  ExamImportConfirmBody,
  ExamImportConfirmResult,
  ExamImportDraft,
  ExamTopicAnalysisResponse,
  ExamWrongRowsResponse,
  ImportDeclaration,
  WrongBridgeItem,
  WrongBridgeResult,
} from "@/lib/types/exam-import";

/** Seçici köprü: denemenin yanlış soruları (arşiv durumu işaretli). */
export function getExamWrongRows(
  examId: number,
  studentId?: number | null,
): Promise<ExamWrongRowsResponse> {
  return api<ExamWrongRowsResponse>(
    studentId != null
      ? `/api/v2/teacher/exams/${examId}/wrong-rows`
      : `/api/v2/student/exams/${examId}/wrong-rows`,
  );
}

/** Denemenin SEÇİLEN yanlışlarını Yanlış Soru Arşivine aktar (Faz 3).
 *  İdempotent — aynı seçim mükerrer üretmez. Koç (studentId dolu) / öğrenci. */
export function archiveExamWrongs(
  examId: number,
  studentId?: number | null,
  items?: WrongBridgeItem[],
): Promise<MutationResponse<WrongBridgeResult>> {
  return api<MutationResponse<WrongBridgeResult>>(
    studentId != null
      ? `/api/v2/teacher/exams/${examId}/wrong-to-archive`
      : `/api/v2/student/exams/${examId}/wrong-to-archive`,
    { method: "POST", body: JSON.stringify(items ? { items } : {}) },
  );
}

/** Konu × deneme analizi (Faz 2) — koç (studentId verilir) / öğrenci (null). */
export function getExamTopicAnalysis(
  studentId: number | null,
  section?: string | null,
): Promise<ExamTopicAnalysisResponse> {
  const qs = section ? `?section=${encodeURIComponent(section)}` : "";
  return api<ExamTopicAnalysisResponse>(
    studentId != null
      ? `/api/v2/teacher/students/${studentId}/exam-topic-analysis${qs}`
      : `/api/v2/student/exam-topic-analysis${qs}`,
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

function appendDeclaration(fd: FormData, decl?: ImportDeclaration): void {
  if (decl?.declaredSection) fd.append("declared_section", decl.declaredSection);
  if (decl?.declaredGrade != null) {
    fd.append("declared_grade", String(decl.declaredGrade));
  }
}

/** Koç: öğrencisinin deneme PDF'ini analiz et (kredi düşer, kayıt YAPMAZ). */
export function teacherAnalyzeExamPdf(
  studentId: number,
  file: File,
  decl?: ImportDeclaration,
): Promise<ExamImportDraft> {
  const fd = new FormData();
  fd.append("file", file);
  appendDeclaration(fd, decl);
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

/** Koç: kayıtlı (PDF'ten aktarılmış) denemeyi satır düzenleme için aç.
 *  Yeni Gemini okuması yok → kredi düşmez; eşleşmemiş konular güncel
 *  taksonomi/sözlükle yeniden denenir. */
export function getExamImportRows(examId: number): Promise<ExamImportDraft> {
  return api<ExamImportDraft>(`/api/v2/teacher/exams/${examId}/import-rows`);
}

/** Koç: düzeltilen satırlarla denemeyi YENİDEN kaydet (net/kırılım yeniden hesaplanır). */
export function updateExamImportRows(
  examId: number,
  body: ExamImportConfirmBody,
): Promise<MutationResponse<ExamImportConfirmResult>> {
  return api<MutationResponse<ExamImportConfirmResult>>(
    `/api/v2/teacher/exams/${examId}/import-rows`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** Öğrenci: kendi deneme PDF'ini analiz et (kredi KOÇUN havuzundan). */
export function studentAnalyzeExamPdf(
  file: File,
  decl?: ImportDeclaration,
): Promise<ExamImportDraft> {
  const fd = new FormData();
  fd.append("file", file);
  appendDeclaration(fd, decl);
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
