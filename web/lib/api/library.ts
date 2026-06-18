/**
 * Öğretmen kitap kütüphanesi GET sarmalayıcıları (Paket 8).
 *
 * QueryKey sözleşmesi backend `invalidate` listesindeki
 *   "teacher:{id}:library:books"
 *   "teacher:{id}:library:books:{book_id}"
 *   "teacher:{id}:library:templates"
 *   "teacher:{id}:library:book-sets"
 *   "teacher:{id}:library:book-sets:{set_id}"
 * ile birebir prefix uyumlu.
 */
import { api } from "@/lib/api";
import type {
  BookSetDetailResponse,
  BookSetListResponse,
  BookTemplateListResponse,
  LibraryBookDetailResponse,
  MappingSuggestionsResponse,
  LibraryBookListResponse,
  SubjectListResponse,
  TopicListResponse,
} from "@/lib/types/library";

// =============================================================================
// QueryKey üreticileri
// =============================================================================

export const libraryKeys = {
  subjects: () => ["teacher", "me", "library", "subjects"] as const,
  topics: (subjectId: number) =>
    ["teacher", "me", "library", "subjects", String(subjectId), "topics"] as const,

  books: (params: LibraryBooksListParams) =>
    [
      "teacher",
      "me",
      "library",
      "books",
      params.q ?? "",
      params.type ?? "",
      params.subject_id !== undefined ? String(params.subject_id) : "",
      params.grade_level !== undefined ? String(params.grade_level) : "",
    ] as const,
  book: (id: number) =>
    ["teacher", "me", "library", "books", String(id)] as const,
  mappingSuggestions: (id: number, ai: boolean) =>
    ["teacher", "me", "library", "books", String(id), "mapping", ai ? "ai" : "auto"] as const,

  templates: () => ["teacher", "me", "library", "templates"] as const,

  bookSets: () => ["teacher", "me", "library", "book-sets"] as const,
  bookSet: (id: number) =>
    ["teacher", "me", "library", "book-sets", String(id)] as const,
} as const;

export interface LibraryBooksListParams {
  q?: string;
  subject_id?: number;
  type?: string;
  grade_level?: number;
}

// =============================================================================
// GET sarmalayıcıları
// =============================================================================

function buildQuery(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export function getLibrarySubjects(): Promise<SubjectListResponse> {
  return api<SubjectListResponse>("/api/v2/teacher/library/subjects");
}

export function getLibraryTopics(subjectId: number): Promise<TopicListResponse> {
  return api<TopicListResponse>(
    `/api/v2/teacher/library/subjects/${encodeURIComponent(String(subjectId))}/topics`,
  );
}

export function getLibraryBooks(
  params: LibraryBooksListParams,
): Promise<LibraryBookListResponse> {
  const qs = buildQuery({
    q: params.q,
    subject_id: params.subject_id,
    type: params.type,
    grade_level: params.grade_level,
  });
  return api<LibraryBookListResponse>(`/api/v2/teacher/library/books${qs}`);
}

export function getLibraryBook(id: number): Promise<LibraryBookDetailResponse> {
  return api<LibraryBookDetailResponse>(
    `/api/v2/teacher/library/books/${encodeURIComponent(String(id))}`,
  );
}

export function getBookMappingSuggestions(
  id: number,
  ai: boolean,
): Promise<MappingSuggestionsResponse> {
  const qs = ai ? "?ai=true" : "";
  return api<MappingSuggestionsResponse>(
    `/api/v2/teacher/library/books/${encodeURIComponent(String(id))}/mapping-suggestions${qs}`,
  );
}

export function getLibraryTemplates(): Promise<BookTemplateListResponse> {
  return api<BookTemplateListResponse>("/api/v2/teacher/library/templates");
}

export function getLibraryBookSets(): Promise<BookSetListResponse> {
  return api<BookSetListResponse>("/api/v2/teacher/library/book-sets");
}

export function getLibraryBookSet(id: number): Promise<BookSetDetailResponse> {
  return api<BookSetDetailResponse>(
    `/api/v2/teacher/library/book-sets/${encodeURIComponent(String(id))}`,
  );
}
