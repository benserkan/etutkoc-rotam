/**
 * Sınıf dönemi filtresi (P3) — konu performansı, deneme listesi/trendi ve
 * deneme konu analizi aynı meta bloğunu döner; UI tek bir seçici çizer.
 *
 * `applied=false` → süzme yok (dönem kaydı yok ya da "tüm zamanlar" seçili);
 * bu durumda seçici gösterilmez, eski davranış birebir korunur.
 */
export interface PeriodOption {
  id: number;
  label: string; // "9. Sınıf (2026-2027)"
  grade_label: string; // "9. Sınıf"
  started_on: string;
  ended_on: string | null;
  is_current: boolean;
}

export interface PeriodFilterMeta {
  applied: boolean;
  active_key: string; // "all" | "<period_id>"
  active_label: string | null;
  started_on: string | null;
  ended_on: string | null;
  options: PeriodOption[];
}

/** Koç dönem yönetimi (P2 backend + P3 arayüz). */
export interface GradePeriodItem {
  id: number;
  grade_level: number | null;
  is_graduate: boolean;
  grade_label: string;
  curriculum_model: string | null;
  curriculum_label: string | null;
  track: string | null;
  academic_year_id: number | null;
  academic_year_name: string | null;
  started_on: string;
  ended_on: string | null;
  is_current: boolean;
  task_count: number;
  exam_count: number;
}

export interface GradePeriodListResponse {
  student_id: number;
  periods: GradePeriodItem[];
}

/** P5 — sınıf geçişi önizlemesi (8→9 gibi model değişimlerinde sihirbaz). */
export interface TransitionPreview {
  student_id: number;
  current_grade_label: string;
  current_curriculum: string | null;
  current_curriculum_label: string | null;
  target_grade_label: string;
  target_curriculum: string | null;
  target_curriculum_label: string | null;
  model_changes: boolean;
  needs_wizard: boolean;
  period_boundary: string;
  previous_period_label: string | null;
  previous_task_count: number;
  previous_exam_count: number;
  archive_candidates: {
    book_id: number;
    book_name: string;
    subject_name?: string | null;
    assigned_on?: string | null;
    total_tests: number;
    completed_tests: number;
    reserved_tests: number;
  }[];
  notes: string[];
}
