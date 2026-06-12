import { apiRequest } from "./api";

// Anket sistemi — web lib/types/survey.ts ile aynı sözleşme (öğrenci alt kümesi
// + koç sonuç görüntüleme).

export interface SurveyTemplateBrief {
  id: number;
  code: string;
  title: string;
  description: string;
  category: string;
  category_label: string;
  scoring_type: "dimensions" | "wheel" | "qualitative";
  question_count: number;
  estimated_minutes: number;
  source_attribution: string;
}

export interface SurveyQuestionModel {
  id: number;
  order_no: number;
  text: string;
  qtype: "likert5" | "slider10" | "choice" | "open";
  dimension_key: string | null;
  options: Array<{ value: string; label: string }>;
}

export interface SurveyDimensionScore {
  key: string;
  label: string;
  description: string;
  score_pct: number;
  level: "high" | "mid" | "low";
  level_label: string;
  high_is_good: boolean;
  comment: string;
}

export interface SurveyQualitativeBlock {
  key: string;
  label: string;
  description: string;
  entries: Array<{ question: string; answer: string }>;
}

export interface SurveyResultModel {
  scoring_type: "dimensions" | "wheel" | "qualitative";
  dimensions: SurveyDimensionScore[];
  top_dimensions: string[];
  qualitative: SurveyQualitativeBlock[];
  open_answers: Array<{ question: string; answer: string }>;
  report_note: string;
  source_attribution: string;
  disclaimer: string;
}

export interface SurveyAssignmentRow {
  id: number;
  template: SurveyTemplateBrief;
  status: "pending" | "in_progress" | "completed" | "cancelled";
  status_label: string;
  note: string;
  assigned_at: string;
  started_at: string | null;
  completed_at: string | null;
  teacher_name: string | null;
  student_name: string | null;
  answered_count: number;
}

export interface StudentSurveysResponse {
  pending: SurveyAssignmentRow[];
  completed: SurveyAssignmentRow[];
}

export interface StudentSurveyFillResponse {
  assignment: SurveyAssignmentRow;
  questions: SurveyQuestionModel[];
  answers: Record<string, number | string>;
  result: SurveyResultModel | null;
  disclaimer: string;
}

export interface StudentSurveySaveResult {
  ok: boolean;
  status: string;
  completed: boolean;
  missing_question_ids: number[];
}

export interface SurveyAssignmentDetail {
  assignment: SurveyAssignmentRow;
  result: SurveyResultModel | null;
}

export interface TeacherStudentSurveysResponse {
  assignments: SurveyAssignmentRow[];
  catalog: SurveyTemplateBrief[];
  categories: Record<string, string>;
}

export const surveyKeys = {
  studentList: ["student", "surveys"] as const,
  studentFill: (id: number) => ["student", "surveys", String(id)] as const,
  teacherStudent: (sid: number) =>
    ["teacher", "student", String(sid), "surveys"] as const,
  teacherAssignment: (aid: number) =>
    ["teacher", "survey-assignment", String(aid)] as const,
} as const;

// --- Öğrenci ---

export function getStudentSurveys(): Promise<StudentSurveysResponse> {
  return apiRequest(`/api/v2/student/surveys`);
}

export function getStudentSurveyFill(
  assignmentId: number,
): Promise<StudentSurveyFillResponse> {
  return apiRequest(`/api/v2/student/surveys/${assignmentId}`);
}

export function saveSurveyAnswers(
  assignmentId: number,
  answers: Record<string, number | string>,
  complete: boolean,
): Promise<{ data: StudentSurveySaveResult }> {
  return apiRequest(`/api/v2/student/surveys/${assignmentId}/answers`, {
    method: "POST",
    body: { answers, complete },
  });
}

// --- Koç ---

export function getTeacherStudentSurveys(
  studentId: number,
): Promise<TeacherStudentSurveysResponse> {
  return apiRequest(`/api/v2/teacher/students/${studentId}/surveys`);
}

export function getSurveyAssignment(
  assignmentId: number,
): Promise<SurveyAssignmentDetail> {
  return apiRequest(`/api/v2/teacher/surveys/assignments/${assignmentId}`);
}

export function assignSurvey(
  studentId: number,
  templateId: number,
  note: string,
): Promise<{ data: { assignment_id: number } }> {
  return apiRequest(`/api/v2/teacher/students/${studentId}/surveys`, {
    method: "POST",
    body: { template_id: templateId, note },
  });
}
