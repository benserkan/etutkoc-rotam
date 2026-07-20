import { apiRequest } from "@/lib/api";

/** Bağımsız çalışma kayıtları — web lib/types/self-study.ts sözleşmesinin aynısı. */

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
  source: "student" | "coach";
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

export interface SelfStudyCreateItem {
  student_book_id: number;
  section_id: number;
  test_count: number;
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

export const selfStudyKeys = {
  list: ["student", "self-study"] as const,
  options: ["student", "self-study", "options"] as const,
};

export function getMySelfStudy(): Promise<SelfStudyListResponse> {
  return apiRequest<SelfStudyListResponse>("/api/v2/student/self-study");
}

export function getSelfStudyOptions(): Promise<SelfStudyOptionsResponse> {
  return apiRequest<SelfStudyOptionsResponse>("/api/v2/student/self-study/options");
}

export function declareSelfStudy(body: {
  items: SelfStudyCreateItem[];
  note?: string | null;
}): Promise<{ data: SelfStudyCreateResult }> {
  return apiRequest("/api/v2/student/self-study", { method: "POST", body });
}

export function withdrawSelfStudy(entryId: number): Promise<unknown> {
  return apiRequest(`/api/v2/student/self-study/${entryId}`, { method: "DELETE" });
}
