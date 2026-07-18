/**
 * Deneme PDF içe aktarma — API v2 tipleri (schemas/exam_import.py aynası).
 */

export type ImportTopicSource = "alias" | "auto" | "ai" | "none" | "kayitli";
export type ImportResultValue = "dogru" | "yanlis" | "bos";

export interface ImportDraftRow {
  exam_part: string | null;
  subject_raw: string | null;
  subject_id: number | null;
  subject_name: string | null;
  /** Okul-müfredat sınavında sunum grubu (sınıf dersinin adı); yoksa null */
  display_subject?: string | null;
  question_no: number | null;
  topic_raw: string | null;
  topic_id: number | null;
  topic_name: string | null;
  topic_source: ImportTopicSource | null;
  correct_answer: string | null;
  student_answer: string | null;
  result: ImportResultValue | null;
  is_suspect: boolean;
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

export interface ImportMatchStats {
  alias: number;
  auto: number;
  ai: number;
  none: number;
}

export interface SectionChoice {
  value: string;
  label: string;
}

export interface TopicChoice {
  id: number;
  name: string;
  subject_name: string;
}

export interface ExamImportDraft {
  title: string | null;
  exam_date: string | null;
  grade_hint: number | null;
  universe: "tyt" | "ayt" | "lgs" | "okul";
  section: string;
  section_label: string;
  scope: "full" | "brans";
  confidence: "high" | "medium" | "low";
  parts: ImportPart[];
  subjects: ImportDraftSubject[];
  rows: ImportDraftRow[];
  checks: ImportCheck[];
  suspect_count: number;
  match_stats: ImportMatchStats;
  duplicate_exam_id: number | null;
  score_info: Record<string, unknown> | null;
  topic_choices: TopicChoice[];
  section_choices: SectionChoice[];
  credits_charged: number;
}

export interface ConfirmRow {
  subject_raw: string | null;
  question_no: number | null;
  topic_raw: string | null;
  topic_id: number | null;
  correct_answer: string | null;
  student_answer: string | null;
  result: ImportResultValue;
  is_suspect: boolean;
  manually_edited: boolean;
}

export interface ExamImportConfirmBody {
  title: string;
  exam_date: string;
  section: string;
  scope?: string | null;
  grade_hint?: number | null;
  note?: string | null;
  force?: boolean;
  score_info?: Record<string, unknown> | null;
  rows: ConfirmRow[];
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

// ============================================================================
// Konu × deneme analizi (Faz 2)
// ============================================================================

export interface AnalysisSectionOption {
  value: string;
  label: string;
  count: number;
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
  section_options: AnalysisSectionOption[];
  exams: AnalysisExamMeta[];
  topics: AnalysisTopicRow[];
  opportunities: AnalysisOpportunity[];
  forgotten: AnalysisTrendTopic[];
  improved: AnalysisTrendTopic[];
  unmatched_questions: number;
  analyzed_question_count: number;
}

/** Seçici köprü: denemenin bir yanlış sorusu (arşiv durumu işaretli). */
export interface ExamWrongRow {
  question_id: number;
  question_no: number | null;
  subject: string | null;
  topic_id: number | null;
  topic_name: string | null;
  topic_label_raw: string | null;
  correct_answer: string | null;
  student_answer: string | null;
  archived: boolean;
}

export interface ExamWrongRowsResponse {
  exam_id: number;
  title: string;
  rows: ExamWrongRow[];
  error_types: { value: string; label: string }[];
}

export interface WrongBridgeItem {
  question_id: number;
  error_type?: string | null;
}

/** İçe aktarmada kullanıcı beyanı (BEYAN ESAS — tespit bekçiye döner). */
export interface ImportDeclaration {
  declaredSection?: string | null;
  declaredGrade?: number | null;
}

/** Deneme → Yanlış Soru Arşivi köprüsü sonucu (Faz 3, idempotent). */
export interface WrongBridgeResult {
  created: number;
  skipped_existing: number;
  skipped_no_topic: number;
  total_wrong: number;
}
