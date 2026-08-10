/**
 * Ortak Kitap Kataloğu + kitap yapısı okuma (içindekiler foto/PDF) tipleri.
 *
 * Pydantic şemalarıyla birebir: `app/routes/api_v2/schemas/library.py`
 * (StructureRead* + Catalog* + AdminCatalog*).
 */
import type { LibraryBookType } from "./library";

// =============================================================================
// Okuma motoru (içindekiler → yapı taslağı)
// =============================================================================

export interface StructureReadSection {
  label: string;
  /** null = içindekilerde yazmıyor — koç/admin elle doldurur (UYDURULMAZ). */
  test_count: number | null;
  /** Çift okuma çelişkisi — önizlemede amber vurgulanır. */
  suspect: boolean;
}

export interface StructureReadResult {
  book_title: string | null;
  publisher: string | null;
  subject_hint: string | null;
  grade_hint: number | null;
  sections: StructureReadSection[];
  warnings: string[];
  /** 2 = çift okuma · 1 = doğrulama okuması düştü (tek okuma). */
  read_count: number;
  /** Koç ucunda kalan günlük hak; admin sınırsız (null). */
  reads_left_today: number | null;
}

// =============================================================================
// Katalog kayıtları
// =============================================================================

export type CatalogStatus = "pending" | "verified" | "hidden";

export const CATALOG_STATUS_LABELS_TR: Record<CatalogStatus, string> = {
  pending: "Onay bekliyor",
  verified: "Yayında",
  hidden: "Gizli",
};

export const CATALOG_SOURCE_LABELS_TR: Record<string, string> = {
  admin_seed: "Admin girişi",
  coach_contribution: "Koç katkısı",
  ai_read: "AI okuması",
};

export interface CatalogSectionItem {
  label: string;
  test_count: number;
  order: number;
  topic_id: number | null;
  topic_name: string | null;
}

export interface CatalogEntryBrief {
  id: number;
  name: string;
  publisher: string | null;
  type: LibraryBookType;
  subject_id: number | null;
  subject_name: string | null;
  target_grade_min: number | null;
  target_grade_max: number | null;
  target_graduate: boolean;
  section_count: number;
  total_tests: number;
  /** Müfredat eşli bölüm sayısı — koç kitabına eşleştirme hazır gelir. */
  mapped_count: number;
  usage_count: number;
  status: CatalogStatus | string;
  source?: string | null;
  created_at: string;
}

export interface CatalogEntryDetail extends CatalogEntryBrief {
  sections: CatalogSectionItem[];
}

export interface CatalogSearchResponse {
  items: CatalogEntryBrief[];
  total: number;
}

export interface CoverIdentifyResult {
  book_title: string | null;
  publisher: string | null;
  subject_hint: string | null;
  grade_hint: number | null;
  exam_hint: string | null;
  catalog_matches: CatalogEntryBrief[];
  reads_left_today: number | null;
}

// =============================================================================
// Katkı (koç) + admin gövdeleri
// =============================================================================

export interface ContributeSectionItem {
  label: string;
  test_count: number;
  topic_id?: number | null;
}

export interface CatalogContributeBody {
  name: string;
  publisher?: string | null;
  type: LibraryBookType;
  subject_id?: number | null;
  target_grade_min?: number | null;
  target_grade_max?: number | null;
  target_graduate?: boolean;
  sections: ContributeSectionItem[];
}

export interface CatalogContributeResult {
  status: "pending" | "already_in_catalog";
  entry_id: number | null;
}

export interface AdminCatalogCreateBody extends CatalogContributeBody {
  /** true → doğrudan yayında (verified); false → onay kuyruğu. */
  publish?: boolean;
}

export interface AdminCatalogUpdateBody {
  name?: string | null;
  publisher?: string | null;
  type?: LibraryBookType | null;
  subject_id?: number | null;
  target_grade_min?: number | null;
  target_grade_max?: number | null;
  target_graduate?: boolean | null;
  /** Verilirse bölümler TAMAMEN yer değiştirir. */
  sections?: ContributeSectionItem[] | null;
}

export interface AdminCatalogListResponse {
  items: CatalogEntryBrief[];
  total: number;
  verified_count: number;
  pending_count: number;
  hidden_count: number;
}
