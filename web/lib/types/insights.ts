/**
 * Manuel TypeScript tipleri — `/api/v2/teacher/insights/*` için.
 *
 * Pydantic şemalarıyla (`app/routes/api_v2/schemas/insights.py`) birebir aynı.
 */

// =============================================================================
// Fleet overview
// =============================================================================

export interface TopPatternItem {
  book_id: number;
  book_name: string;
  section_id: number;
  section_label: string;
  subject_name: string;
  count: number;
  students: number;
}

export interface StudentMaturityItem {
  student_id: number;
  full_name: string;
  weeks_observed: number;
  days_observed: number;
  maturity_value: number;
  maturity_text: string;
  accepted_count: number;
  rejected_count: number;
  acceptance_rate: number | null;
}

export interface WeekBucketItem {
  start: string; // YYYY-MM-DD
  accepted: number;
  rejected: number;
}

export interface HealthBadge {
  key: string;
  label: string;
  color: string;
}

export interface FleetInsightsResponse {
  teacher_id: number;
  today: string;
  students: StudentMaturityItem[];
  fleet_total_accepted: number;
  fleet_total_rejected: number;
  fleet_acceptance_rate: number | null;
  avg_maturity: number;
  students_with_data: number;
  top_accepted: TopPatternItem[];
  top_rejected: TopPatternItem[];
  weekly_trend: WeekBucketItem[];
  last_activity_at: string | null;
  health_overall: HealthBadge;
  health_activity: HealthBadge;
}

// =============================================================================
// Diagnostics
// =============================================================================

export interface DiagnosticsPatternRow {
  dow: number;
  dow_label: string;
  book_id: number;
  book_name: string;
  subject_name: string;
  section_id: number;
  section_label: string;
  topic_name: string | null;
  freq: number;
  typical_count: number;
  samples: number[];
}

export interface DiagnosticsVolumeRow {
  dow: number;
  dow_label: string;
  task_count: number;
  subject_count: number;
}

export interface DiagnosticsRejectRow {
  dow_label: string;
  book_id: number;
  book_name: string;
  subject_name: string;
  section_id: number;
  section_label: string;
  weight: number;
  count: number;
  blocked: boolean;
}

export interface DiagnosticsStudentRef {
  id: number;
  full_name: string;
}

export interface StudentDiagnosticsResponse {
  student: DiagnosticsStudentRef;
  today: string;
  weeks_observed: number;
  days_observed: number;
  maturity_value: number;
  maturity_label: string;
  maturity_pct: number;
  maturity_base: number;
  maturity_floor_applied: boolean;
  maturity_weeks_constant: number;
  maturity_min_floor: number;
  reject_decay_days: number;
  reject_strong_count: number;
  reject_score_penalty: number;
  pattern_rows: DiagnosticsPatternRow[];
  volume_rows: DiagnosticsVolumeRow[];
  reject_rows: DiagnosticsRejectRow[];
  total_accepted: number;
  total_rejected: number;
}

// =============================================================================
// Suggestion panel
// =============================================================================

export interface SuggestionItem {
  book_id: number;
  book_name: string;
  book_type: string;
  section_id: number;
  section_label: string;
  subject_id: number;
  subject_name: string;
  topic_name: string | null;
  planned_count: number;
  remaining: number;
  confidence: number;
  confidence_label: string;
  score: number;
  reasons: string[];
}

export interface SuggestionDayBundle {
  date: string;
  suggestions: SuggestionItem[];
}

export interface StudentSuggestionsPanelResponse {
  student_id: number;
  target_date: string;
  suggestions: SuggestionItem[];
  maturity_value: number;
  maturity_label: string;
  weeks_observed: number;
  days_observed: number;
  active_phase: string | null;
  track_required: boolean;
  track_missing: boolean;
  track_label: string | null;
}

export interface StudentSuggestionsAheadResponse {
  student_id: number;
  today: string;
  days: SuggestionDayBundle[];
}

// =============================================================================
// Mutation bodies + results
// =============================================================================

export interface SuggestionAcceptBody {
  date: string;
  book_id: number;
  section_id: number;
  planned_count: number;
}

export interface SuggestionRejectBody {
  date: string;
  book_id: number;
  section_id: number;
}

export interface SuggestionAcceptItem {
  book_id: number;
  section_id: number;
  planned_count: number;
}

export interface SuggestionAcceptAllBody {
  date: string;
  items: SuggestionAcceptItem[];
}

export interface SuggestionAcceptResult {
  accepted: boolean;
  task_id: number;
  date: string;
}

export interface SuggestionAcceptAllResult {
  created_count: number;
  errors: string[];
}

export interface SuggestionRejectResult {
  rejected: boolean;
}
