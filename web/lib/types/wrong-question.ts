/**
 * Yanlış Soru Arşivi — API v2 tipleri (backend schemas/wrong_question.py aynası).
 */

export interface WrongQuestionImageRef {
  id: number;
  kind: "question" | "solution";
  content_type: string;
  size_bytes: number;
}

export interface WrongQuestionItem {
  id: number;
  status: "acik" | "kapandi";
  source_kind: "gorev" | "deneme" | "diger";
  error_type: string | null;
  error_type_label: string | null;
  subject_id: number | null;
  subject_name: string | null;
  topic_id: number | null;
  topic_name: string | null;
  book_name: string | null;
  section_label: string | null;
  note: string | null;
  coach_note: string | null;
  ai_question_text: string | null;
  ai_hint: string | null;
  difficulty_guess: string | null;
  correct_streak: number;
  attempts_count: number;
  due_at: string | null;
  is_due: boolean;
  closed_at: string | null;
  created_at: string;
  images: WrongQuestionImageRef[];
}

export interface WrongQuestionCounts {
  total: number;
  open: number;
  closed: number;
  due: number;
}

export interface WrongQuestionListResponse {
  items: WrongQuestionItem[];
  counts: WrongQuestionCounts;
  error_type_labels: Record<string, string>;
}

export interface WrongQuestionUpdateBody {
  subject_id?: number | null;
  topic_id?: number | null;
  error_type?: string | null;
  note?: string | null;
  clear_note?: boolean;
}

export interface WrongQuestionAttemptBody {
  rating: 1 | 2 | 3 | 4;
}

export interface TopicAccumulation {
  topic_id: number;
  topic_name: string;
  subject_name: string | null;
  open_count: number;
  closed_count: number;
}

export interface WrongQuestionSummaryResponse {
  counts: WrongQuestionCounts;
  by_topic: TopicAccumulation[];
  by_error_type: Record<string, number>;
  error_type_labels: Record<string, string>;
  closed_last_30d: number;
  added_last_30d: number;
}

/** Yakalama formu — multipart alanları (hepsi opsiyonel; sıfır sürtünme). */
export interface WrongQuestionCreateFields {
  source_kind?: "gorev" | "deneme" | "diger";
  book_section_id?: number;
  task_id?: number;
  subject_id?: number;
  topic_id?: number;
  error_type?: string;
  note?: string;
}
