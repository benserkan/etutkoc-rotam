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
  return runBookJob<StructureReadResult>(
    "/api/v2/teacher/library/book-structure/read-jobs",
    filesToFormData(files),
  );
}

/** "Kapak + içindekiler" tek yükleme (1 PDF ya da ≤8 görsel). */
export function coachScanBook(files: File[], forceRead = false): Promise<BookScanResult> {
  const fd = filesToFormData(files);
  if (forceRead) fd.append("force_read", "true");
  return runBookJob<BookScanResult>("/api/v2/teacher/library/book-structure/scan-jobs", fd);
}

interface BookJobPoll {
  job: { status: string; error_code: string | null; error_message: string | null };
  result: unknown;
}

/**
 * Okuma arka plan işi olarak başlar, sonuç yoklanır (2026-10-29). Okuma 2 dk'yı
 * aşabildiği için tek istekte beklemek Cloudflare'in 100 sn sınırına takılırdı.
 * Çağıranlar için imza aynı: sonuç gelince çözülür, hata ApiError olarak düşer.
 */
async function runBookJob<T>(url: string, fd: FormData): Promise<T> {
  const job = await multipart<{ id: number }>(url, fd);
  const deadline = Date.now() + 8 * 60_000;
  let misses = 0;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 2000));
    let d: BookJobPoll;
    try {
      d = await api<BookJobPoll>(`/api/v2/me/ai-jobs/${job.id}`);
      misses = 0;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw e;
      if (++misses > 5) throw e; // ağ sürekli düşüyor
      continue;
    }
    if (d.job.status === "done" && d.result) return d.result as T;
    if (d.job.status === "failed") {
      throw new ApiError(422, {
        error: "validation",
        code: d.job.error_code ?? "failed",
        message: d.job.error_message ?? "Okuma tamamlanamadı.",
      });
    }
  }
  throw new ApiError(504, {
    error: "timeout",
    code: "scan_timeout",
    message: "Okuma beklenenden uzun sürdü. Biraz sonra tekrar dene.",
  });
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

/**
 * Tam kitap yükleme — PARÇALI (2026-10-29). Cloudflare tek istekte en çok
 * 100 MB kabul eder; kitaplar 450 MB'a kadar çıkabildiği için dosya sunucunun
 * bildirdiği boyutta (32 MB) parçalarla gönderilir. Kopan parça bir kez daha
 * aynı konumdan denenir. Son parçadan sonra olağan tarama işi başlar.
 */
export async function adminCreateScanJob(
  file: File,
  tocPages: number,
  pageOffset: number | null,
  onProgress?: (pct: number) => void,
): Promise<MutationResponse<BookScanJobItem>> {
  const start = new FormData();
  start.append("filename", file.name || "kitap.pdf");
  start.append("total_size", String(file.size));
  const up = await multipart<{ upload_id: string; chunk_size: number }>(
    "/api/v2/admin/book-catalog/scan-uploads",
    start,
  );
  const base = `/api/v2/admin/book-catalog/scan-uploads/${up.upload_id}`;
  for (let off = 0; off < file.size; off += up.chunk_size) {
    const part = file.slice(off, Math.min(file.size, off + up.chunk_size));
    for (let attempt = 0; ; attempt++) {
      const fd = new FormData();
      fd.append("offset", String(off));
      fd.append("file", part, "part");
      try {
        await multipart<{ received: number }>(`${base}/chunk`, fd);
        break;
      } catch (e) {
        if (attempt >= 2 || (e instanceof ApiError && e.status < 500 && e.status !== 0)) throw e;
        await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
      }
    }
    onProgress?.(Math.round((Math.min(file.size, off + up.chunk_size) / file.size) * 100));
  }
  const fin = new FormData();
  fin.append("toc_pages", String(tocPages));
  if (pageOffset != null) fin.append("page_offset", String(pageOffset));
  return multipart<MutationResponse<BookScanJobItem>>(`${base}/finish`, fin);
}

export function adminDeleteScanJob(id: number): Promise<MutationResponse<unknown>> {
  return api<MutationResponse<unknown>>(
    `/api/v2/admin/book-catalog/scan-jobs/${id}/delete`,
    { method: "POST" },
  );
}
