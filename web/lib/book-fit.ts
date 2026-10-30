/**
 * Kitabın hedef sınıfı öğrenciye uyuyor mu? Backend `book_assign.grade_fits` aynası.
 * Uymayan atama ENGELLENMEZ, yalnız uyarılır (saha 2026-10-30: Arı "Paragrafın Ritmi"
 * TYT baskısı 8. sınıf öğrenciye atanınca öğrencide "TYT Türkçe" dersi altında çıktı).
 */
export interface BookGradeTarget {
  target_grade_min: number | null;
  target_grade_max: number | null;
  target_graduate: boolean;
}

export interface StudentGrade {
  grade_level: number | null;
  is_graduate?: boolean;
}

export function bookFitsStudent(book: BookGradeTarget, s: StudentGrade): boolean {
  const lo = book.target_grade_min;
  const hi = book.target_grade_max;
  if (lo == null && hi == null && !book.target_graduate) return true;
  if (s.is_graduate) return Boolean(book.target_graduate);
  if (s.grade_level == null) return true;
  return (lo ?? 1) <= s.grade_level && s.grade_level <= (hi ?? 12);
}
