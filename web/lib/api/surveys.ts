/**
 * Anket sistemi fetcher'ları + queryKey'ler.
 *
 * invalidate sözleşmesi: backend "teacher:{tid}:students:{sid}:surveys" ve
 * "student:surveys" düz string'leri döner; applyInvalidate `:` ile split eder.
 */
import { api } from "@/lib/api";
import type {
  CareerSynthesisCacheResponse,
  StudentSurveyFillResponse,
  StudentSurveysResponse,
  SurveyAssignmentDetail,
  SurveyCatalogResponse,
  TeacherStudentSurveysResponse,
} from "@/lib/types/survey";

export const surveyKeys = {
  catalog: () => ["teacher", "me", "survey-catalog"] as const,
  // backend invalidate: teacher:{tid}:students:{sid}:surveys — prefix uyumu
  // için kısa anahtar yeterli (her koç kendi cache'inde).
  studentSurveys: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "surveys"] as const,
  assignment: (assignmentId: number) =>
    ["teacher", "me", "survey-assignment", String(assignmentId)] as const,
  studentList: () => ["student", "surveys"] as const,
  studentFill: (assignmentId: number) =>
    ["student", "surveys", String(assignmentId)] as const,
  careerSynthesis: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "career-synthesis"] as const,
} as const;

export function getCareerSynthesis(
  studentId: number,
): Promise<CareerSynthesisCacheResponse> {
  return api<CareerSynthesisCacheResponse>(
    `/api/v2/teacher/students/${studentId}/career-synthesis`,
  );
}

export function getSurveyCatalog(): Promise<SurveyCatalogResponse> {
  return api<SurveyCatalogResponse>("/api/v2/teacher/surveys/catalog");
}

export function getTeacherStudentSurveys(
  studentId: number,
): Promise<TeacherStudentSurveysResponse> {
  return api<TeacherStudentSurveysResponse>(
    `/api/v2/teacher/students/${studentId}/surveys`,
  );
}

export function getSurveyAssignment(
  assignmentId: number,
): Promise<SurveyAssignmentDetail> {
  return api<SurveyAssignmentDetail>(
    `/api/v2/teacher/surveys/assignments/${assignmentId}`,
  );
}

export function getStudentSurveys(): Promise<StudentSurveysResponse> {
  return api<StudentSurveysResponse>("/api/v2/student/surveys");
}

export function getStudentSurveyFill(
  assignmentId: number,
): Promise<StudentSurveyFillResponse> {
  return api<StudentSurveyFillResponse>(
    `/api/v2/student/surveys/${assignmentId}`,
  );
}
