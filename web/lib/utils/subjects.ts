/**
 * Subject (ders) yardımcıları.
 *
 * Aynı ders adı (örn. "Matematik") farklı curriculum_model'lerde ayrı kayıttır
 * (LGS Matematik vs Maarif Lise Matematik). UI'da bunları gruplayarak +
 * hedef sınıf seviyesine göre filtreleyerek duplicate kaosunu önleriz.
 */
import {
  CURRICULUM_MODEL_LABELS_TR,
  CURRICULUM_MODEL_ORDER,
  type CurriculumModel,
  type SubjectRef,
} from "@/lib/types/library";

export interface SubjectGroup {
  /** "lgs", "maarif_lise", "klasik_lise" veya null (Diğer/sınıflandırılmamış) */
  key: CurriculumModel | null;
  label: string;
  subjects: SubjectRef[];
}

/** Sınav-bazlı kanonik ders mi (TYT/AYT, model-bağımsız)? */
export function isExamSubject(s: SubjectRef): boolean {
  return s.curriculum_model == null && s.exam_section != null;
}

/**
 * Subjects'i gruplar. Sıralama:
 * Sınav (TYT/AYT) → LGS → Maarif Lise → Klasik Lise → Diğer (null).
 * Sınav dersleri YKS koçluğunun omurgası → en üstte. Boş gruplar yer almaz.
 */
export function groupSubjectsByCurriculum(
  subjects: readonly SubjectRef[],
): SubjectGroup[] {
  const exam: SubjectRef[] = [];
  const buckets = new Map<CurriculumModel | null, SubjectRef[]>();
  for (const s of subjects) {
    if (isExamSubject(s)) {
      exam.push(s);
      continue;
    }
    const key = (s.curriculum_model as CurriculumModel | null) ?? null;
    const arr = buckets.get(key);
    if (arr) arr.push(s);
    else buckets.set(key, [s]);
  }
  const groups: SubjectGroup[] = [];
  if (exam.length > 0) {
    groups.push({ key: null, label: "Sınav Müfredatı (TYT / AYT)", subjects: exam });
  }
  for (const cm of CURRICULUM_MODEL_ORDER) {
    const arr = buckets.get(cm);
    if (arr && arr.length > 0) {
      groups.push({
        key: cm,
        label: CURRICULUM_MODEL_LABELS_TR[cm],
        subjects: arr,
      });
    }
  }
  const other = buckets.get(null);
  if (other && other.length > 0) {
    groups.push({
      key: null,
      label: "Diğer / Sınıflandırılmamış",
      subjects: other,
    });
  }
  return groups;
}

/**
 * Bir subject belirli bir sınıf seviyesini kapsıyor mu?
 *
 * Mantık:
 *   - min/max yoksa subject "tüm seviyeler" — eşleşir.
 *   - graduate=true ise yalnız "Mezun" hedefini kapsar (ek olarak).
 *   - Aksi halde min ≤ grade ≤ max aralığı.
 */
export function subjectCoversGrade(
  s: SubjectRef,
  grade: number,
): boolean {
  if (s.min_grade_level === null && s.max_grade_level === null) return true;
  const min = s.min_grade_level ?? 5;
  const max = s.max_grade_level ?? 12;
  return grade >= min && grade <= max;
}

export function subjectCoversGraduate(s: SubjectRef): boolean {
  return s.available_for_graduate;
}

/**
 * Hedef sınıf aralığına göre subject filtresi.
 *
 * - `gradeMin`/`gradeMax` ikisi null ise tüm dersleri döndürür.
 * - `graduateOnly=true` ise yalnız mezun için uygun dersler.
 * - Aralık verilirse [gradeMin, gradeMax] ile kesişen dersler.
 */
export function filterSubjectsByGrade(
  subjects: readonly SubjectRef[],
  gradeMin: number | null,
  gradeMax: number | null,
  graduateOnly: boolean,
): SubjectRef[] {
  if (graduateOnly) {
    return subjects.filter((s) => subjectCoversGraduate(s));
  }
  if (gradeMin === null && gradeMax === null) {
    return [...subjects];
  }
  const lo = gradeMin ?? gradeMax ?? 5;
  const hi = gradeMax ?? gradeMin ?? 12;
  return subjects.filter((s) => {
    // min/max yoksa "tüm seviyeler" — daima eşleşir
    if (s.min_grade_level === null && s.max_grade_level === null) return true;
    const smin = s.min_grade_level ?? 5;
    const smax = s.max_grade_level ?? 12;
    // [lo,hi] ile [smin,smax] kesişiyor mu?
    return smin <= hi && smax >= lo;
  });
}
