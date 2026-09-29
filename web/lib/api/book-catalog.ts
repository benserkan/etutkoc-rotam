/**
 * Ortak Kitap Kataloğu — fetcher'lar (koç + süper admin) + query key'ler.
 *
 * Okuma uçları multipart (içindekiler foto/PDF); kredi DÜŞMEZ, koçta günlük
 * tavan vardır (429 daily_read_limit).
 */
import { api, ApiError, type MutationResponse } from "@/lib/api";
import type {
  AdminCatalogCreateBody,
  AdminCatalogListResponse,
  AdminCatalogUpdateBody,
  BookScanResult,
  BookScanJobDetail,
  BookScanJobItem,
  BookScanJobListResponse,
  CatalogBrowseResponse,
  CatalogContributeBody,
  CatalogContributeResult,
  CatalogEntryDetail,
  CatalogSearchResponse,
  CoverIdentifyResult,
  StructureReadResult,
} from "@/lib/types/book-catalog";
import type { SubjectListResponse } from "@/lib/types/library";

export const bookCatalogKeys = {
  adminList: (status: string | null, q: string) =>
    ["admin", "book-catalog", status ?? "", q] as const,
  adminSubjects: () => ["admin", "book-catalog", "subjects"] as const,
  adminScanJobs: () => ["admin", "book-catalog", "scan-jobs"] as const,
  adminScanJob: (id: number) => ["admin", "book-catalog", "scan-jobs", String(id)] as const,
  coachSearch: (q: string, subjectId: number | null) =>
    ["teacher", "library", "book-catalog", "search", q, subjectId ?? 0] as const,
  coachBrowse: () => ["teacher", "library", "book-catalog", "browse"] as const,
  coachDetail: (id: number) =>
    ["teacher", "library", "book-catalog", String(id)] as const,
};

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

function filesToFormData(files: File[]): FormData {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  return fd;
}

// =============================================================================
// Koç uçları
// =============================================================================

/** İçindekiler foto/PDF → yapı taslağı (çift okuma; kredi düşmez). */
export function coachReadStructure(files: File[]): Promise<StructureReadResult> {
  return multipart<StructureReadResult>(
    "/api/v2/teacher/library/book-structure/read",
    filesToFormData(files),
  );
}

/** "Kapak + içindekiler" tek yükleme (1 PDF ya da ≤8 görsel). */
export function coachScanBook(files: File[], forceRead = false): Promise<BookScanResult> {
  const fd = filesToFormData(files);
  if (forceRead) fd.append("force_read", "true");
  return multipart<BookScanResult>("/api/v2/teacher/library/book-structure/scan", fd);
}

/** Katalog tarayıcısı — yayındaki tüm kayıtlar. */
export function coachBrowseCatalog(): Promise<CatalogBrowseResponse> {
  return api<CatalogBrowseResponse>("/api/v2/teacher/library/book-catalog/browse");
}

/** Kapak fotoğrafı → kitap kimliği + katalog eşleşmeleri. */
export function coachIdentifyCover(file: File): Promise<CoverIdentifyResult> {
  const fd = new FormData();
  fd.append("file", file);
  return multipart<CoverIdentifyResult>(
    "/api/v2/teacher/library/book-structure/identify-cover",
    fd,
  );
}

/** Katalog araması — yalnız yayında (verified) kayıtlar. */
export function coachSearchCatalog(
  q: string,
  subjectId?: number | null,
): Promise<CatalogSearchResponse> {
  const qs = new URLSearchParams({ q });
  if (subjectId != null) qs.set("subject_id", String(subjectId));
  return api<CatalogSearchResponse>(
    `/api/v2/teacher/library/book-catalog/search?${qs.toString()}`,
  );
}

export function coachGetCatalogEntry(id: number): Promise<CatalogEntryDetail> {
  return api<CatalogEntryDetail>(`/api/v2/teacher/library/book-catalog/${id}`);
}

/** Kitap yapısını ortak kataloğa öner (anonim; admin onayı bekler). */
export function coachContributeCatalog(
  body: CatalogContributeBody,
): Promise<MutationResponse<CatalogContributeResult>> {
  return api<MutationResponse<CatalogContributeResult>>(
    "/api/v2/teacher/library/book-catalog/contribute",
    { method: "POST", body: JSON.stringify(body) },
  );
}

// =============================================================================
// Süper admin uçları
// =============================================================================

export function getAdminBookCatalog(
  status: string | null = null,
  q: string = "",
): Promise<AdminCatalogListResponse> {
  const qs = new URLSearchParams();
  if (status) qs.set("status", status);
  if (q) qs.set("q", q);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return api<AdminCatalogListResponse>(`/api/v2/admin/book-catalog${suffix}`);
}

export function getAdminBookCatalogEntry(id: number): Promise<CatalogEntryDetail> {
  return api<CatalogEntryDetail>(`/api/v2/admin/book-catalog/${id}`);
}

export function getAdminCatalogSubjects(): Promise<SubjectListResponse> {
  return api<SubjectListResponse>("/api/v2/admin/book-catalog/subjects");
}

/** Seed aracı: örnek PDF / içindekiler fotoğrafı → yapı taslağı (tavansız). */
export function adminReadStructure(files: File[]): Promise<StructureReadResult> {
  return multipart<StructureReadResult>(
    "/api/v2/admin/book-catalog/read",
    filesToFormData(files),
  );
}

export function adminCreateCatalogEntry(
  body: AdminCatalogCreateBody,
): Promise<MutationResponse<CatalogEntryDetail>> {
  return api<MutationResponse<CatalogEntryDetail>>("/api/v2/admin/book-catalog", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function adminUpdateCatalogEntry(
  id: number,
  body: AdminCatalogUpdateBody,
): Promise<MutationResponse<CatalogEntryDetail>> {
  return api<MutationResponse<CatalogEntryDetail>>(
    `/api/v2/admin/book-catalog/${id}`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function adminCatalogAction(
  id: number,
  action: "verify" | "hide" | "delete",
): Promise<MutationResponse<unknown>> {
  return api<MutationResponse<unknown>>(
    `/api/v2/admin/book-catalog/${id}/${action}`,
    { method: "POST" },
  );
}

// Tam kitap tarama işleri (arka plan)

export function getAdminScanJobs(): Promise<BookScanJobListResponse> {
  return api<BookScanJobListResponse>("/api/v2/admin/book-catalog/scan-jobs");
}

export function getAdminScanJob(id: number): Promise<BookScanJobDetail> {
  return api<BookScanJobDetail>(`/api/v2/admin/book-catalog/scan-jobs/${id}`);
}

export function adminCreateScanJob(
  file: File,
  tocPages: number,
  pageOffset: number | null,
): Promise<MutationResponse<BookScanJobItem>> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("toc_pages", String(tocPages));
  if (pageOffset != null) fd.append("page_offset", String(pageOffset));
  return multipart<MutationResponse<BookScanJobItem>>(
    "/api/v2/admin/book-catalog/scan-jobs",
    fd,
  );
}

export function adminDeleteScanJob(id: number): Promise<MutationResponse<unknown>> {
  return api<MutationResponse<unknown>>(
    `/api/v2/admin/book-catalog/scan-jobs/${id}/delete`,
    { method: "POST" },
  );
}
