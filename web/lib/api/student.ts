/**
 * Öğrenci paneli endpoint'lerinin tipli sarmalayıcıları.
 *
 * KIRMIZI ÇİZGİLER:
 *   - `lib/api.ts:api()` üzerinden — `cache: no-store` default + 401 auto-refresh.
 *   - QueryKey'ler `:` ayraçlı (backend MutationResponse.invalidate ile uyumlu).
 *     Örn. `student:{user_id}:day:{date}` → applyInvalidate `['student', '{id}', 'day', '{date}']`.
 *
 * Bu modül SADECE okuma (GET) sarmalayıcıları içerir. Mutation hook'ları
 * Paket 6'da gelir (gün kartında tikleme + modal akışları).
 */
import { api } from "@/lib/api";
import type {
  BookGridResponse,
  BookSectionsResponse,
  DnaResponse,
  FocusResponse,
  GoalListResponse,
  PendingBadgesResponse,
  ReviewResponse,
  StudentBooksResponse,
  StudentDayResponse,
  StudentRequestListResponse,
  StudentWeekResponse,
} from "@/lib/types/student";

// =============================================================================
// QueryKey üreticileri — useQuery için.
//
// invalidate sözleşmesi backend'de "student:{id}:day:{date}" gibi düz string.
// Frontend prefix-match için `[ 'student', id, 'day', date ]` array key kullanır;
// applyInvalidate `:` ile split eder. Birebir uyumlu kalmaları kritik (R-006).
// =============================================================================

export const studentKeys = {
  day: (date: string) => ["student", "me", "day", date] as const,
  week: (start: string) => ["student", "me", "week", start] as const,
  books: () => ["student", "me", "books"] as const,
  bookGrid: (bookId: number) => ["student", "me", "book-grid", String(bookId)] as const,
  bookSections: (bookId: number) =>
    ["student", "me", "book-sections", String(bookId)] as const,
  badges: () => ["badges", "student", "me", "pending"] as const,
  requests: (status?: string) => ["student", "me", "requests", status ?? "all"] as const,
  sidebar: () => ["student", "me", "sidebar"] as const,
  summary: (date: string) => ["student", "me", "summary", date] as const,
  focus: () => ["student", "me", "focus"] as const,
  dna: () => ["student", "me", "dna"] as const,
  review: () => ["student", "me", "review"] as const,
  goals: () => ["student", "me", "goals"] as const,
} as const;

// =============================================================================
// GET sarmalayıcıları
// =============================================================================

export function getStudentDay(date?: string): Promise<StudentDayResponse> {
  const q = date ? `?date=${encodeURIComponent(date)}` : "";
  return api<StudentDayResponse>(`/api/v2/student/day${q}`);
}

/** Gün notu otomatik kayıt (debounced). Buton yok — yazdıkça çağrılır. */
export function saveStudentDayNote(
  date: string,
  body: string,
): Promise<{ date: string; body: string; updated_at: string | null }> {
  return api(`/api/v2/student/day-note`, {
    method: "PUT",
    body: JSON.stringify({ date, body }),
  });
}

export function getStudentWeek(start?: string): Promise<StudentWeekResponse> {
  const q = start ? `?start=${encodeURIComponent(start)}` : "";
  return api<StudentWeekResponse>(`/api/v2/student/week${q}`);
}

export function getStudentBooks(): Promise<StudentBooksResponse> {
  return api<StudentBooksResponse>("/api/v2/student/books");
}

export function getStudentBookGrid(bookId: number): Promise<BookGridResponse> {
  return api<BookGridResponse>(
    `/api/v2/student/book-grid?book_id=${encodeURIComponent(String(bookId))}`,
  );
}

/**
 * "Kaynağı değiştir" / "Yeni görev iste" modali için ünite cascade.
 * Eşdeğer Jinja `/student/book-sections` — Next.js JSON karşılığı.
 */
export function getStudentBookSections(
  bookId: number,
): Promise<BookSectionsResponse> {
  return api<BookSectionsResponse>(
    `/api/v2/student/book-sections?book_id=${encodeURIComponent(String(bookId))}`,
  );
}

export function getStudentBadges(): Promise<PendingBadgesResponse> {
  return api<PendingBadgesResponse>("/api/v2/student/badges");
}

export function getStudentRequests(
  status?: "pending" | "answered" | "all",
): Promise<StudentRequestListResponse> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return api<StudentRequestListResponse>(`/api/v2/student/requests${q}`);
}

export function getStudentFocus(): Promise<FocusResponse> {
  return api<FocusResponse>("/api/v2/student/focus");
}

export function getStudentDna(): Promise<DnaResponse> {
  return api<DnaResponse>("/api/v2/student/dna");
}

export function getStudentReview(): Promise<ReviewResponse> {
  return api<ReviewResponse>("/api/v2/student/review");
}

export function getStudentGoals(): Promise<GoalListResponse> {
  return api<GoalListResponse>("/api/v2/student/goals");
}
