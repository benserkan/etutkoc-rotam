/**
 * Manuel TypeScript tipleri — `/api/v2/teacher/library/*` için.
 *
 * Pydantic şemalarıyla (`app/routes/api_v2/schemas/library.py`) birebir aynı.
 */

export type LibraryBookType =
  | "soru_bankasi"
  | "fasikul"
  | "konu_anlatimli"
  | "brans_denemesi"
  | "genel_deneme";

export const LIBRARY_BOOK_TYPE_LABELS_TR: Record<LibraryBookType, string> = {
  soru_bankasi: "Soru bankası",
  fasikul: "Fasikül",
  konu_anlatimli: "Konu anlatımlı",
  brans_denemesi: "Branş denemesi",
  genel_deneme: "Genel deneme",
};

// =============================================================================
// Yardımcı listeler
// =============================================================================

export type CurriculumModel = "lgs" | "maarif_lise" | "klasik_lise";

export const CURRICULUM_MODEL_LABELS_TR: Record<CurriculumModel, string> = {
  lgs: "LGS Müfredatı (5-8)",
  maarif_lise: "Maarif Modeli (9-12)",
  klasik_lise: "Klasik Lise (11-12, son nesil)",
};

export const CURRICULUM_MODEL_ORDER: CurriculumModel[] = [
  "lgs",
  "maarif_lise",
  "klasik_lise",
];

export interface SubjectRef {
  id: number;
  name: string;
  is_builtin: boolean;
  curriculum_model: string | null;
  exam_section: string | null;
  min_grade_level: number | null;
  max_grade_level: number | null;
  available_for_graduate: boolean;
}

export interface SubjectListResponse {
  items: SubjectRef[];
}

export interface TopicRef {
  id: number;
  name: string;
  subject_id: number;
  is_builtin: boolean;
  order: number;
  grade_level: number | null;
}

export interface TopicListResponse {
  items: TopicRef[];
}

// Müfredat eşleştirme (Faz 0)
export interface MappingSuggestionRow {
  section_id: number;
  label: string;
  order: number;
  current_topic_id: number | null;
  current_topic_name: string | null;
  suggested_topic_id: number | null;
  suggested_topic_name: string | null;
  source: "mapped" | "auto" | "ai" | "none";
  confidence: "high" | "medium" | "low" | null;
}

export interface MappingSuggestionsResponse {
  book_id: number;
  book_name: string;
  subject_name: string | null;
  total_sections: number;
  mapped_count: number;
  suggested_count: number;
  ai_used: boolean;
  candidate_topics: TopicRef[];
  rows: MappingSuggestionRow[];
}

export interface ApplyMappingItem {
  section_id: number;
  topic_id: number | null;
}

export interface ApplyMappingResult {
  changed: number;
  mapped_count: number;
  total_sections: number;
}

// =============================================================================
// Books
// =============================================================================

export interface LibraryBookListItem {
  id: number;
  name: string;
  publisher: string | null;
  type: LibraryBookType;
  subject_id: number;
  subject_name: string | null;
  avg_questions_per_test: number | null;
  target_grade_min: number | null;
  target_grade_max: number | null;
  target_graduate: boolean;
  section_count: number;
  total_tests: number;
  assigned_student_count: number;
  created_at: string;
}

export interface LibraryBookListResponse {
  items: LibraryBookListItem[];
  total: number;
}

export interface LibrarySectionItem {
  id: number;
  label: string;
  test_count: number;
  order: number;
  topic_id: number | null;
  topic_name: string | null;
  reserved_total: number;
  completed_total: number;
  has_progress: boolean;
}

export interface LibraryAssignedStudentRef {
  student_id: number;
  full_name: string;
  has_progress: boolean;
}

export interface LibraryBookDetailResponse {
  id: number;
  name: string;
  publisher: string | null;
  type: LibraryBookType;
  subject_id: number;
  subject_name: string | null;
  avg_questions_per_test: number | null;
  target_grade_min: number | null;
  target_grade_max: number | null;
  target_graduate: boolean;
  created_at: string;
  sections: LibrarySectionItem[];
  assigned_students: LibraryAssignedStudentRef[];
  total_tests: number;
}

export interface BookCreateBody {
  name: string;
  subject_id: number;
  type: LibraryBookType;
  publisher?: string | null;
  avg_questions_per_test?: number | null;
  target_grade_min?: number | null;
  target_grade_max?: number | null;
  target_graduate?: boolean;
  template_id?: number | null;
}

export interface BookPatchBody {
  name?: string | null;
  publisher?: string | null;
  type?: LibraryBookType | null;
  subject_id?: number | null;
  avg_questions_per_test?: number | null;
  target_grade_min?: number | null;
  target_grade_max?: number | null;
  target_graduate?: boolean | null;
}

export interface SectionCreateBody {
  label: string;
  test_count: number;
  topic_id?: number | null;
}

export interface SectionPatchBody {
  label?: string | null;
  test_count?: number | null;
  topic_id?: number | null;
}

export interface BulkCatalogTopicItem {
  topic_id: number;
  test_count: number;
}

export interface SectionsBulkFromCatalogBody {
  items: BulkCatalogTopicItem[];
}

export interface BulkCatalogResult {
  added_count: number;
  skipped_existing_count: number;
}

// =============================================================================
// AI suggest
// =============================================================================

export interface AiSuggestBody {
  grade_hint?: string | null;
}

export interface AiSuggestResult {
  added_section_count: number;
  template_id: number;
  suggestions: LibrarySectionItem[];
}

// =============================================================================
// Assignments
// =============================================================================

export interface AssignmentsPatchBody {
  student_ids: number[];
}

export interface AssignmentsResult {
  assigned_count: number;
  removed_count: number;
  skipped_with_progress: number[];
}

// =============================================================================
// Templates
// =============================================================================

export interface BookTemplateListItem {
  id: number;
  name: string;
  type: LibraryBookType;
  publisher: string | null;
  subject_id: number | null;
  subject_name: string | null;
  target_grade_min: number | null;
  target_grade_max: number | null;
  target_graduate: boolean;
  is_ai_generated: boolean;
  is_verified: boolean;
  section_count: number;
  created_at: string;
}

export interface BookTemplateListResponse {
  items: BookTemplateListItem[];
  total: number;
}

export interface SaveAsTemplateBody {
  template_name?: string | null;
}

export interface ApplyTemplateBody {
  template_id: number;
  overwrite?: boolean;
}

export interface ApplyTemplateResult {
  added_count: number;
  overwrote: boolean;
}

// =============================================================================
// Book sets
// =============================================================================

export interface BookSetMemberRef {
  book_id: number;
  book_name: string;
  book_type: LibraryBookType;
  subject_id: number;
  subject_name: string | null;
  order: number;
}

export interface BookSetGradeBucket {
  grade_level: number | null;
  is_graduate: boolean;
  label_tr: string;
  student_count: number;
}

export interface BookSetListItem {
  id: number;
  name: string;
  notes: string | null;
  book_count: number;
  student_count: number;
  grade_distribution: BookSetGradeBucket[];
  target_grade_min: number | null;
  target_grade_max: number | null;
  target_graduate: boolean;
  target_grade_label_tr: string;
  created_at: string;
}

export interface BookSetListResponse {
  items: BookSetListItem[];
  total: number;
}

export interface BookSetAssignedStudent {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  is_graduate: boolean;
  is_active: boolean;
  grade_label_tr: string;
  assigned_book_count: number;
}

export interface BookSetDetailResponse {
  id: number;
  name: string;
  notes: string | null;
  items: BookSetMemberRef[];
  assigned_students: BookSetAssignedStudent[];
  grade_distribution: BookSetGradeBucket[];
  target_grade_min: number | null;
  target_grade_max: number | null;
  target_graduate: boolean;
  target_grade_label_tr: string;
  created_at: string;
}

export interface BookSetCreateBody {
  name: string;
  notes?: string | null;
  target_grade_min?: number | null;
  target_grade_max?: number | null;
  target_graduate?: boolean;
}

export interface BookSetPatchBody {
  name?: string | null;
  notes?: string | null;
  target_grade_min?: number | null;
  target_grade_max?: number | null;
  target_graduate?: boolean | null;
  clear_target_grade?: boolean;
}

export interface AddBooksToSetBody {
  book_ids: number[];
}

export interface AddBooksToSetResult {
  added_count: number;
  skipped_existing_count: number;
}

// =============================================================================
// Ortak
// =============================================================================

export interface DeletedRef {
  deleted: boolean;
  id: number;
}
