/** Anket sistemi tipleri — backend schemas/survey.py birebir karşılığı. */

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

export interface SurveyCatalogResponse {
  items: SurveyTemplateBrief[];
  categories: Record<string, string>;
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

export interface SurveyAssignmentDetail {
  assignment: SurveyAssignmentRow;
  result: SurveyResultModel | null;
}

export interface TeacherStudentSurveysResponse {
  assignments: SurveyAssignmentRow[];
  catalog: SurveyTemplateBrief[];
  categories: Record<string, string>;
}

export interface SurveyAssignBody {
  template_id: number;
  note?: string;
}

export interface SurveyAssignResult {
  ok: boolean;
  assignment_id: number;
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

export interface CareerSuggestion {
  title: string;
  field: string;
  why: string;
  example_departments: string[];
}

export interface CareerSynthesisModel {
  summary: string;
  career_suggestions: CareerSuggestion[];
  strengths: string[];
  agenda: string[];
  watch_outs: string[];
  based_on_surveys: string[];
  exam_count: number;
  generated_at: string | null;
}

export interface CareerSynthesisCacheResponse {
  insight: CareerSynthesisModel | null;
  is_stale: boolean;
  ready: boolean;
  missing_surveys: string[];
  disclaimer: string;
}

export interface StudentSurveySaveResult {
  ok: boolean;
  status: string;
  completed: boolean;
  missing_question_ids: number[];
}
