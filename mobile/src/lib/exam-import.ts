/**
 * Deneme PDF içe aktarma + konu analizi + YSA köprüsü — mobil fetcher'lar (Faz 4).
 *
 * Web sözleşmesiyle birebir aynı uçlar:
 *   analyze  → multipart PDF (KREDİ 6, koç havuzu — YSA deseni)
 *   confirm  → payload JSON + aynı PDF (kanıt; kredi düşmez)
 *   topic-analysis → salt-okuma konu×deneme analizi (kredi yok)
 *   wrong-to-archive → yanlışları tek tıkla Yanlış Soru Arşivine (idempotent)
 *
 * Mobil akış SADELEŞTİRİLMİŞ önizleme kullanır: satır-düzeyi düzenleme web
 * panelindedir ("Satırları düzelt"); mobilde başlık/tarih/tür/oturum seçilir,
 * satırlar okunduğu gibi kaydedilir.
 *
 * PDF seçimi expo-document-picker ister (NATİVE modül — eski kurulumlarda
 * yoktur). OTA güvenliği: dinamik require + try/catch; modül yoksa akış
 * "uygulama güncellemesi gerekli" der, ANALİZ/ARŞİV özellikleri etkilenmez.
 */
import { API_BASE, ApiError, apiRequest, getAccessToken } from "./api";

// --- Tipler (web lib/types/exam-import.ts alt kümesi) ---

export interface ImportPart {
  part: string | null;
  section: string;
  section_label: string;
  question_count: number;
}
export interface ImportCheck {
  code: string;
  label: string;
  ok: boolean;
  detail: string | null;
}
export interface ImportDraftSubject {
  name: string;
  part: string | null;
  questions: number;
  correct: number;
  wrong: number;
  blank: number;
  net: number;
  doc_net: number | null;
}
export interface ImportDraftRow {
  exam_part: string | null;
  subject_raw: string | null;
  question_no: number | null;
  topic_raw: string | null;
  topic_id: number | null;
  correct_answer: string | null;
  student_answer: string | null;
  result: string | null;
  is_suspect: boolean;
}
export interface SectionChoice {
  value: string;
  label: string;
}
export interface ExamImportDraft {
  title: string | null;
  exam_date: string | null;
  grade_hint: number | null;
  section: string;
  section_label: string;
  confidence: string;
  scope: string;
  parts: ImportPart[];
  subjects: ImportDraftSubject[];
  rows: ImportDraftRow[];
  checks: ImportCheck[];
  suspect_count: number;
  match_stats: { alias: number; auto: number; ai: number; none: number };
  duplicate_exam_id: number | null;
  score_info: Record<string, unknown> | null;
  section_choices: SectionChoice[];
  credits_charged: number;
}
export interface ExamImportConfirmResult {
  exam_id: number;
  title: string;
  exam_date: string;
  section: string;
  section_label: string;
  net: number;
  total_correct: number;
  total_wrong: number;
  total_blank: number;
  question_count: number;
  matched_topic_count: number;
  wrong_topic_ids: number[];
}
export interface WrongBridgeResult {
  created: number;
  skipped_existing: number;
  skipped_no_topic: number;
  total_wrong: number;
}

export interface AnalysisExamMeta {
  id: number;
  title: string;
  exam_date: string;
  net: number;
}
export interface AnalysisCell {
  exam_id: number;
  total: number;
  correct: number;
  wrong: number;
  blank: number;
  accuracy: number;
}
export interface AnalysisTopicRow {
  topic_id: number;
  topic_name: string;
  subject_name: string;
  total: number;
  correct: number;
  wrong: number;
  blank: number;
  accuracy: number;
  exams_seen: number;
  cells: AnalysisCell[];
}
export interface AnalysisOpportunity {
  topic_id: number;
  topic_name: string;
  subject_name: string;
  total: number;
  wrong: number;
  blank: number;
  accuracy: number;
  net_gain_per_exam: number;
}
export interface AnalysisTrendTopic {
  topic_id: number;
  topic_name: string;
  subject_name: string;
  first_accuracy: number;
  last_accuracy: number;
}
export interface ExamTopicAnalysisResponse {
  section: string | null;
  section_label: string | null;
  exams: AnalysisExamMeta[];
  topics: AnalysisTopicRow[];
  opportunities: AnalysisOpportunity[];
  forgotten: AnalysisTrendTopic[];
  improved: AnalysisTrendTopic[];
  unmatched_questions: number;
  analyzed_question_count: number;
}

export interface PickedPdf {
  uri: string;
  name: string;
  mimeType: string;
}

// --- PDF seçimi (native modül guard'lı — OTA güvenli) ---

/** null = kullanıcı vazgeçti · "unavailable" = eski kurulum (yeni build gerek). */
export async function pickExamPdf(): Promise<PickedPdf | null | "unavailable"> {
  let picker: typeof import("expo-document-picker");
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- OTA
    // güvenliği: native modül eski kurulumda yoksa import ANINDA patlamasın
    picker = require("expo-document-picker");
  } catch {
    return "unavailable";
  }
  try {
    const res = await picker.getDocumentAsync({
      type: "application/pdf",
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (res.canceled || !res.assets?.length) return null;
    const a = res.assets[0];
    return {
      uri: a.uri,
      name: a.name || "deneme.pdf",
      mimeType: a.mimeType || "application/pdf",
    };
  } catch {
    return "unavailable";
  }
}

// --- Multipart yardımcı (wrong-questions deseniyle aynı) ---

async function uploadMultipart<T>(path: string, form: FormData): Promise<T> {
  const token = await getAccessToken();
  // content-type VERİLMEZ — RN FormData boundary'yi kendisi kurar.
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: token ? { authorization: `Bearer ${token}` } : {},
    body: form,
  });
  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail = (data as { detail?: unknown })?.detail ?? data;
    const code = (detail as { code?: string })?.code ?? `http_${res.status}`;
    const message =
      (detail as { message?: string })?.message ??
      (typeof detail === "string" ? detail : "Yükleme başarısız.");
    throw new ApiError(res.status, code, message, data);
  }
  return data as T;
}

function pdfFormPart(form: FormData, pdf: PickedPdf): void {
  // RN dosya objesi: { uri, name, type } — RN FormData tipi web'den farklı
  form.append("file", {
    uri: pdf.uri,
    name: pdf.name,
    type: pdf.mimeType,
  } as unknown as Blob);
}

// --- Fetcher'lar (studentId dolu = koç yüzeyi, yoksa öğrenci kendi) ---

export function analyzeExamPdf(
  pdf: PickedPdf,
  studentId?: number | null,
): Promise<ExamImportDraft> {
  const fd = new FormData();
  pdfFormPart(fd, pdf);
  return uploadMultipart<ExamImportDraft>(
    studentId != null
      ? `/api/v2/teacher/students/${studentId}/exams/import-analyze`
      : "/api/v2/student/exams/import-analyze",
    fd,
  );
}

export interface ConfirmPayload {
  title: string;
  exam_date: string;
  section: string;
  scope?: string | null;
  grade_hint?: number | null;
  score_info?: Record<string, unknown> | null;
  force?: boolean;
  rows: {
    subject_raw: string | null;
    question_no: number | null;
    topic_raw: string | null;
    topic_id: number | null;
    correct_answer: string | null;
    student_answer: string | null;
    result: string;
    is_suspect: boolean;
  }[];
}

export function confirmExamImport(
  payload: ConfirmPayload,
  pdf: PickedPdf | null,
  studentId?: number | null,
): Promise<{ data: ExamImportConfirmResult; invalidate?: string[] }> {
  const fd = new FormData();
  fd.append("payload", JSON.stringify(payload));
  if (pdf) pdfFormPart(fd, pdf);
  return uploadMultipart(
    studentId != null
      ? `/api/v2/teacher/students/${studentId}/exams/import-confirm`
      : "/api/v2/student/exams/import-confirm",
    fd,
  );
}

export function getExamTopicAnalysis(
  studentId: number | null,
  section?: string | null,
): Promise<ExamTopicAnalysisResponse> {
  const qs = section ? `?section=${encodeURIComponent(section)}` : "";
  return apiRequest<ExamTopicAnalysisResponse>(
    studentId != null
      ? `/api/v2/teacher/students/${studentId}/exam-topic-analysis${qs}`
      : `/api/v2/student/exam-topic-analysis${qs}`,
  );
}

export function archiveExamWrongs(
  examId: number,
  studentId?: number | null,
): Promise<{ data: WrongBridgeResult; invalidate?: string[] }> {
  return apiRequest(
    studentId != null
      ? `/api/v2/teacher/exams/${examId}/wrong-to-archive`
      : `/api/v2/student/exams/${examId}/wrong-to-archive`,
    { method: "POST" },
  );
}
