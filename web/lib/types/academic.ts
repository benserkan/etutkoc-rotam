/**
 * Manuel TypeScript tipleri — `/api/v2/teacher/academic` +
 * `/api/v2/teacher/grade-advance` + `/api/v2/teacher/csv` için.
 *
 * Pydantic şemalarıyla (`app/routes/api_v2/schemas/academic.py`) birebir aynı.
 */

export type PhaseKind = "regular" | "winter_break" | "summer_camp" | "exam_prep";
export type ExamTarget = "lgs" | "yks" | "none";
export type Track = "sayisal" | "ea" | "sozel" | "dil";
export type GraduateMode = "full_time" | "dershane";

// =============================================================================
// Academic year + phase
// =============================================================================

export interface PhaseItem {
  id: number;
  name: string;
  start_date: string; // YYYY-MM-DD
  end_date: string;
  kind: PhaseKind;
  kind_label: string;
  kind_badge: string;
  notes: string | null;
  capacity_multiplier: number;
  is_no_school: boolean;
}

export interface AcademicYearListItem {
  id: number;
  name: string;
  start_year: number | null;
  exam_target: ExamTarget;
  exam_label: string;
  is_active: boolean;
  phase_count: number;
  student_count: number;
  created_at: string;
}

export interface AcademicYearListResponse {
  items: AcademicYearListItem[];
  current_start_year: number;
}

export interface AcademicYearAssignedStudent {
  student_id: number;
  full_name: string;
  grade_level: number | null;
  is_graduate: boolean;
}

export interface AcademicYearDetailResponse {
  id: number;
  name: string;
  start_year: number | null;
  exam_target: ExamTarget;
  exam_label: string;
  is_active: boolean;
  created_at: string;
  phases: PhaseItem[];
  assigned_students: AcademicYearAssignedStudent[];
}

export interface AcademicYearCreateBody {
  start_year: number;
}

export interface AcademicYearPatchBody {
  name?: string | null;
  start_year?: number | null;
  exam_target?: ExamTarget | null;
  is_active?: boolean | null;
}

export interface PhaseCreateBody {
  name: string;
  start_date: string;
  end_date: string;
  kind?: PhaseKind;
  notes?: string | null;
}

export interface PhasePatchBody {
  name?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  kind?: PhaseKind | null;
  notes?: string | null;
}

export interface AcademicYearAssignBody {
  student_ids: number[];
}

export interface AcademicYearAssignResult {
  assigned_count: number;
  removed_count: number;
  unchanged_count: number;
}

export interface AcademicYearListChoiceItem {
  start_year: number;
  name: string;
  label: string;
  exists: boolean;
}

export interface AcademicYearChoicesResponse {
  items: AcademicYearListChoiceItem[];
  current_start_year: number;
}

// =============================================================================
// Grade advance
// =============================================================================

export interface GradeAdvancePreviewItem {
  student_id: number;
  full_name: string;
  current_grade_level: number | null;
  current_is_graduate: boolean;
  current_academic_year_id: number | null;
  current_academic_year_name: string | null;
  suggested_grade_level: number | null;
  suggested_is_graduate: boolean;
  requires_track: boolean;
  has_track: boolean;
  has_reservations: boolean;
  has_completed_progress: boolean;
  blocker_notes: string[];
}

export interface GradeAdvancePreviewResponse {
  students: GradeAdvancePreviewItem[];
  suggested_year_id: number | null;
  suggested_year_name: string | null;
}

export interface GradeAdvanceApplyItem {
  student_id: number;
  new_grade_level: number | null;
  new_is_graduate: boolean;
  new_track?: Track | null;
  new_graduate_mode?: GraduateMode | null;
}

export interface GradeAdvanceApplyBody {
  items: GradeAdvanceApplyItem[];
  target_academic_year_id?: number | null;
}

export interface GradeAdvanceApplyResult {
  advanced_count: number;
  skipped_invalid: string[];
  skipped_track_missing: string[];
  preserved_reservations_count: number;
}

export interface ResetProgramConfirmBody {
  confirm_full_name: string;
}

export interface ResetProgramResult {
  student_id: number;
  deleted_tasks: number;
  deleted_task_book_items: number;
  cleared_reservations: number;
  deleted_suggestion_feedback: number;
}

// =============================================================================
// CSV
// =============================================================================

export interface CsvParsedRow {
  row_num: number;
  full_name: string | null;
  email: string | null;
  grade_level: number | null;
  track: Track | null;
  is_graduate: boolean;
  graduate_mode: GraduateMode | null;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  raw: Record<string, unknown>;
}

export interface CsvPreviewResponse {
  rows: CsvParsedRow[];
  valid_count: number;
  invalid_count: number;
  header_errors: string[];
  total_rows: number;
}

export interface CsvCommitBody {
  csv_text: string;
}

export interface CsvCreatedStudent {
  row_num: number;
  student_id: number;
  full_name: string;
  email: string;
  grade_label: string;
  temp_password: string;
}

export interface CsvCommitResult {
  created: CsvCreatedStudent[];
  skipped_existing_email: CsvParsedRow[];
  skipped_invalid: CsvParsedRow[];
  created_count: number;
  skipped_count: number;
  header_errors: string[];
}
