/**
 * Akademik yıl + grade-advance + CSV GET sarmalayıcıları (Paket 10).
 *
 * Backend invalidate prefix'leri:
 *   "teacher:{id}:academic:years"
 *   "teacher:{id}:academic:years:{year_id}"
 *   "teacher:{id}:grade-advance"
 *   "teacher:{id}:students"
 */
import { api } from "@/lib/api";
import type {
  AcademicYearChoicesResponse,
  AcademicYearDetailResponse,
  AcademicYearListResponse,
  GradeAdvancePreviewResponse,
} from "@/lib/types/academic";

export const academicKeys = {
  years: () => ["teacher", "me", "academic", "years"] as const,
  year: (id: number) =>
    ["teacher", "me", "academic", "years", String(id)] as const,
  yearChoices: () =>
    ["teacher", "me", "academic", "years", "choices"] as const,
  gradeAdvancePreview: () =>
    ["teacher", "me", "grade-advance", "preview"] as const,
} as const;

export function getAcademicYears(): Promise<AcademicYearListResponse> {
  return api<AcademicYearListResponse>("/api/v2/teacher/academic/years");
}

export function getAcademicYear(
  id: number,
): Promise<AcademicYearDetailResponse> {
  return api<AcademicYearDetailResponse>(
    `/api/v2/teacher/academic/years/${encodeURIComponent(String(id))}`,
  );
}

export function getAcademicYearChoices(): Promise<AcademicYearChoicesResponse> {
  return api<AcademicYearChoicesResponse>(
    "/api/v2/teacher/academic/years/choices",
  );
}

export function getGradeAdvancePreview(): Promise<GradeAdvancePreviewResponse> {
  return api<GradeAdvancePreviewResponse>(
    "/api/v2/teacher/grade-advance/preview",
  );
}
