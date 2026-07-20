/**
 * Bağımsız çalışma kayıtları — tipli fetcher'lar + queryKey üreticileri.
 *
 * invalidate sözleşmesi (backend MutationResponse.invalidate):
 *   öğrenci  → "student:self-study" (+ "student:books")
 *   koç      → "teacher:{tid}:students:{sid}:self-study" (+ ...:books)
 */
import { api } from "@/lib/api";
import type {
  SelfStudyListResponse,
  SelfStudyOptionsResponse,
} from "@/lib/types/self-study";

export const selfStudyKeys = {
  studentList: () => ["student", "self-study"] as const,
  studentOptions: () => ["student", "self-study", "options"] as const,
  teacherList: (teacherId: number | "me", studentId: number) =>
    ["teacher", String(teacherId), "students", String(studentId), "self-study"] as const,
} as const;

export function getStudentSelfStudy(): Promise<SelfStudyListResponse> {
  return api<SelfStudyListResponse>("/api/v2/student/self-study");
}

export function getStudentSelfStudyOptions(): Promise<SelfStudyOptionsResponse> {
  return api<SelfStudyOptionsResponse>("/api/v2/student/self-study/options");
}

export function getTeacherSelfStudy(
  studentId: number,
): Promise<SelfStudyListResponse> {
  return api<SelfStudyListResponse>(
    `/api/v2/teacher/students/${studentId}/self-study`,
  );
}
