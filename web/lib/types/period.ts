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
