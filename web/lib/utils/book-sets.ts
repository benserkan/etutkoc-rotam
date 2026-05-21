/**
 * Kitap seti (BookSet) hedef sınıf yardımcıları.
 *
 * Set'in `target_grade_min/max/target_graduate` alanlarıyla bir öğrencinin
 * sınıf seviyesi karşılaştırılır. UI'da set picker'da "Önerilen" / "Diğer
 * sınıflar" gruplaması bu fonksiyonla yapılır.
 */
import type { BookSetListItem } from "@/lib/types/library";

/**
 * Bir setin "Tüm seviyeler" (hedef alanları boş) olup olmadığı.
 */
export function setIsAllLevels(s: BookSetListItem): boolean {
  return (
    s.target_grade_min === null &&
    s.target_grade_max === null &&
    !s.target_graduate
  );
}

/**
 * Öğrenci için bir set "önerilen" sayılır mı?
 *
 * Kurallar:
 *   - Tüm seviyeler setleri her zaman önerilen (uyumsuzluk yok).
 *   - Mezun öğrenci: yalnız `target_graduate=true` setler önerilen.
 *   - Sınıflı öğrenci (s ∈ 5-12): set aralığı varsa `min ≤ s ≤ max`
 *     olmalı (target_min/max'in biri null ise diğer uçtan açık aralık).
 *     `target_graduate=true` set sınıflı öğrenci için önerilen değil.
 */
export function setRecommendedForStudent(
  s: BookSetListItem,
  studentGradeLevel: number | null,
  studentIsGraduate: boolean,
): boolean {
  if (setIsAllLevels(s)) return true;

  if (studentIsGraduate) {
    return s.target_graduate === true;
  }

  // Sınıflı öğrenci
  if (studentGradeLevel === null) {
    // Sınıfı bilinmiyorsa "Tüm seviyeler" dışındakileri önerme
    return false;
  }
  if (s.target_graduate && !(s.target_grade_min !== null || s.target_grade_max !== null)) {
    // Yalnız mezun seti — sınıflı öğrenciye önerme
    return false;
  }
  const min = s.target_grade_min ?? 4;
  const max = s.target_grade_max ?? 12;
  return studentGradeLevel >= min && studentGradeLevel <= max;
}
