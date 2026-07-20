/** Bağımsız çalışma kayıtları — API v2 tipleri (backend schemas/self_study.py aynası). */

export type SelfStudySource = "student" | "coach";
export type SelfStudyStatus = "pending" | "approved" | "rejected";

export interface SelfStudyEntryItem {
  id: number;
  student_book_id: number;
  book_id: number;
  book_name: string;
  subject_name: string;
  section_id: number;
  section_label: string;
  test_count: number;
  applied_count: number;
  source: SelfStudySource;
  source_label: string;
  status: SelfStudyStatus;
  status_label: string;
  note: string | null;
  period_start: string | null;
  period_end: string | null;
  created_by_name: string | null;
  created_at: string;
  reviewed_at: string | null;
  review_note: string | null;
}

export interface SelfStudyListResponse {
  items: SelfStudyEntryItem[];
  pending_count: number;
}

export interface SelfStudyCreateItem {
  student_book_id: number;
  section_id: number;
  test_count: number;
}

export interface SelfStudyCreateBody {
  items: SelfStudyCreateItem[];
  note?: string | null;
  period_start?: string | null;
  period_end?: string | null;
}

export interface SelfStudySkippedItem {
  section_id: number;
  section_label: string;
  reason: string;
}

export interface SelfStudyCreateResult {
  created: SelfStudyEntryItem[];
  skipped: SelfStudySkippedItem[];
  applied_total: number;
  pending_total: number;
}

export interface SelfStudyReviewBody {
  approve: boolean;
  review_note?: string | null;
}

export interface SelfStudyDeleteResult {
  deleted_id: number;
  reverted_count: number;
}

export interface SelfStudyOptionSection {
  section_id: number;
  label: string;
  test_count: number;
  completed_count: number;
  reserved_count: number;
  remaining: number;
}

export interface SelfStudyOptionBook {
  student_book_id: number;
  book_id: number;
  book_name: string;
  subject_name: string;
  book_type_label: string;
  sections: SelfStudyOptionSection[];
}

export interface SelfStudyOptionsResponse {
  books: SelfStudyOptionBook[];
}
