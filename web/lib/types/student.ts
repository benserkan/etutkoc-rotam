/**
 * Manuel TypeScript tipleri — `/api/v2/student/*` için.
 *
 * Pydantic şemalarıyla (`app/routes/api_v2/schemas/student.py`) birebir aynı.
 * Codegen pipeline'ı (openapi-typescript) Dalga sonunda aktif edildiğinde bu
 * dosya `lib/types/api.d.ts` ile değiştirilebilir; şimdilik elle yazılmış
 * sözleşme — okuma ucu için tipli, mutation ucu için Paket 6'da daraltılacak.
 */

// =============================================================================
// Görev (Task)
// =============================================================================

export type TaskType = "test" | "video" | "ozet" | "tekrar" | "other";
export type TaskStatus = "pending" | "partial" | "completed" | "cancelled";
export type BookType =
  | "soru_bankasi"
  | "fasikul"
  | "konu_anlatimli"
  | "brans_denemesi"
  | "genel_deneme";

export interface StudentTaskItem {
  id: number;
  book_id: number;
  book_name: string;
  section_id: number | null;
  section_label: string | null;
  topic_name: string | null;
  planned: number;
  completed: number;
  is_full: boolean;
  max_completable: number;
  // Opsiyonel sonuç — "Tamam + sayıyla" sheet'inden gelir; null girilmedi.
  correct: number | null;
  wrong: number | null;
}

export type TaskPeriod = "morning" | "noon" | "evening";

export interface StudentTask {
  id: number;
  title: string;
  type: TaskType;
  status: TaskStatus;
  date: string;                    // "YYYY-MM-DD"
  scheduled_hour: string | null;   // "HH:MM" veya null
  period: TaskPeriod | null;       // M6 — opsiyonel periyot
  items: StudentTaskItem[];
  planned_count: number;
  completed_count: number;
  pct: number;                     // 0..1
  is_future_blocked: boolean;
  is_past: boolean;
  has_pending_request: boolean;
}

// =============================================================================
// Gün özeti + sidebar + projeksiyon
// =============================================================================

export interface DaySummary {
  total_tasks: number;
  total_items: number;
  planned_count: number;
  completed_count: number;
  pct: number;                     // 0..1 — GÖREV tamamlama (deneme soruları test'e karışmaz)
  // GÖREV-bazlı kırılım (her madde 1 görev; deneme/test/etkinlik AYRI)
  gorev_total: number;
  gorev_done: number;
  test_planned: number;            // yalnız soru bankası (deneme HARİÇ)
  test_completed: number;
  deneme_count: number;
  etkinlik_count: number;
}

export interface ResourceBook {
  student_book_id: number;
  book_id: number;
  book_name: string;
  book_type: BookType;
  total_tests: number;
  reserved_tests: number;
  completed_tests: number;
  remaining_tests: number;
}

export interface ResourceSubjectGroup {
  subject_id: number;
  subject_name: string;
  total_tests: number;
  reserved_tests: number;
  completed_tests: number;
  remaining_tests: number;
  books: ResourceBook[];
}

export interface ResourceSidebar {
  total_tests: number;
  reserved_tests: number;
  completed_tests: number;
  remaining_tests: number;
  subjects: ResourceSubjectGroup[];
}

// GET /api/v2/student/book-sections?book_id=… cascade
export interface BookSectionOption {
  id: number;
  label: string;
  topic_name: string | null;
  remaining: number;
  total: number;
}

export interface BookSectionsResponse {
  book_id: number;
  is_deneme: boolean;
  items: BookSectionOption[];
}

export type ProjectionMethod = "naive" | "dow_weighted";
export type ProjectionConfidence = "low" | "medium" | "high";
export type DowKey =
  | "monday" | "tuesday" | "wednesday" | "thursday"
  | "friday" | "saturday" | "sunday";

export interface ProjectionPanel {
  exam_date: string | null;
  days_left: number | null;
  effective_days: number;
  buffer_days: number;
  methodology: ProjectionMethod;
  confidence_level: ProjectionConfidence;
  rate_per_day: number;
  projected_completable: number;
  gap: number;
  required_rate: number;
  dow_hit_rates: Record<DowKey, number | null>;
  dow_hit_measured: Record<DowKey, boolean>;
}

export interface CanRequestMatrix {
  change: boolean;
  replace: boolean;
  remove: boolean;
  question: boolean;
  add: boolean;
}

// =============================================================================
// Day / Week / Books / Book grid response'ları
// =============================================================================

export interface StudentDayResponse {
  date: string;
  is_today: boolean;
  is_future: boolean;
  is_past: boolean;
  prev_date: string;
  next_date: string;
  tasks: StudentTask[];
  summary: DaySummary;
  sidebar: ResourceSidebar;
  projection: ProjectionPanel | null;
  can_request: CanRequestMatrix;
}

export interface StudentWeekDay {
  date: string;
  dow_label: string;
  is_today: boolean;
  is_future: boolean;
  is_past: boolean;
  tasks_count: number;
  planned: number;
  completed: number;
  pct: number;                     // GÖREV tamamlama (deneme soruları test'e karışmaz)
  gorev_total: number;
  gorev_done: number;
  test_planned: number;            // yalnız soru bankası (deneme HARİÇ)
  test_completed: number;
  deneme_count: number;
  etkinlik_count: number;
  tasks: StudentTask[];
}

export interface StudentWeekResponse {
  start_date: string;
  end_date: string;
  prev_start: string;
  next_start: string;
  days: StudentWeekDay[];
  total_planned: number;
  total_completed: number;
  total_pct: number;               // GÖREV tamamlama
  total_gorev: number;
  total_gorev_done: number;
  total_test_planned: number;
  total_test_completed: number;
}

// =============================================================================
// Week PRINT — A4 yatay yazdırma payload'ı
// =============================================================================

export interface WeekPrintTask {
  title: string;
  is_single_item: boolean;
  book_name: string | null;
  section_label: string | null;
  topic_name: string | null;
  planned_count: number;
  type_label: string | null;
}

export interface WeekPrintDay {
  date: string;
  day_of_month: number;
  month_index: number;
  dow_index: number;             // 0=Pzt..6=Paz
  dow_label: string;
  month_label: string;
  task_count: number;
  history_pct: number | null;
  history_samples: number;
  tasks: WeekPrintTask[];
}

export interface WeekPrintResponse {
  student_name: string;
  grade_level: number | null;
  academic_year_name: string | null;
  exam_label: string | null;
  exam_date: string | null;
  start_date: string;
  end_date: string;
  start_day: number;
  start_month_label: string;
  start_dow_label: string;
  end_day: number;
  end_month_label: string;
  end_year: number;
  days: WeekPrintDay[];
  week_notes: string[];
}

export interface StudentBooksResponse {
  total_tests: number;
  reserved_tests: number;
  completed_tests: number;
  remaining_tests: number;
  subjects: ResourceSubjectGroup[];
}

export type CellState = "DONE" | "RESERVED" | "FREE";

export interface BookCell {
  number: number;
  state: CellState;
  task_id?: number | null;
  task_date?: string | null;
}

export interface BookSectionGrid {
  section_id: number;
  label: string;
  topic_name: string | null;
  test_count: number;
  completed: number;
  reserved: number;
  cells: BookCell[];
}

export interface BookGridResponse {
  student_book_id: number;
  book_id: number;
  book_name: string;
  subject_name: string;
  book_type: BookType;
  total_tests: number;
  total_completed: number;
  total_reserved: number;
  sections: BookSectionGrid[];
}

export interface PendingBadgesResponse {
  pending_count: number;
  today_open_count: number;
  checked_at: string;
}

// =============================================================================
// Talep sistemi (Paket 3)
// =============================================================================

export type RequestType = "change" | "replace" | "remove" | "question" | "add";
export type RequestStatus =
  | "pending" | "approved" | "rejected" | "withdrawn" | "resolved";

export interface StudentRequestItem {
  id: number;
  type: RequestType;
  status: RequestStatus;
  task_id: number | null;
  task_title: string | null;
  task_date: string | null;
  message: string | null;
  proposed_book_id: number | null;
  proposed_book_name: string | null;
  proposed_section_id: number | null;
  proposed_section_label: string | null;
  proposed_count: number | null;
  proposed_date: string | null;
  teacher_response: string | null;
  created_at: string;
  responded_at: string | null;
}

export interface StudentRequestListResponse {
  items: StudentRequestItem[];
  total: number;
  pending_count: number;
}

// =============================================================================
// Focus (Pomodoro) — Paket 4
// =============================================================================

export type PomodoroKind = "work" | "short_break" | "long_break";

export interface FocusSession {
  id: number;
  kind: PomodoroKind;
  started_at: string;
  ended_at: string | null;
  planned_minutes: number;
  actual_minutes: number;
  interrupted: boolean;
  label: string | null;
  is_active: boolean;
  elapsed_seconds: number;
}

export interface FocusTodaySummary {
  work_sessions: number;
  work_minutes: number;
  break_minutes: number;
  total_minutes: number;
  interrupted_count: number;
}

export interface FocusResponse {
  active_session: FocusSession | null;
  today: FocusTodaySummary;
  recent_sessions: FocusSession[];
  streak_days: number;
  points: number;
}

// =============================================================================
// DNA — Paket 4
// =============================================================================

export type DnaChronotype =
  | "morning" | "afternoon" | "evening" | "night" | "unknown";
export type DnaTrendDirection = "up" | "down" | "flat" | "insufficient";
export type BurnoutRiskLevel = "healthy" | "watch" | "warn" | "critical";

export interface DnaSubjectActivity {
  subject_id: number | null;
  subject_name: string;
  planned: number;
  completed: number;
  completion_rate: number;
}

export interface DnaTrend {
  direction: DnaTrendDirection;
  this_week_completed: number;
  last_week_completed: number;
  delta_pct: number | null;
}

export interface BurnoutSignal {
  kind: string;
  severity: "low" | "medium" | "high";
  label: string;
  emoji: string;
  detail: string;
  metric: number | null;
}

export interface DnaResponse {
  window_days: number;
  has_enough_data: boolean;
  total_completed: number;
  total_planned: number;
  completion_rate: number;
  // GÖREV-bazlı gösterim (deneme/test AYRI)
  gorev_total: number;
  gorev_done: number;
  test_planned: number;            // yalnız soru bankası (deneme HARİÇ)
  test_completed: number;
  deneme_count: number;
  etkinlik_count: number;
  chronotype: DnaChronotype;
  peak_hour: number | null;
  peak_day_idx: number | null;
  peak_day_name: string | null;
  heatmap: number[][];
  morning_count: number;
  afternoon_count: number;
  evening_count: number;
  night_count: number;
  weekend_count: number;
  weekday_count: number;
  by_subject: DnaSubjectActivity[];
  trend: DnaTrend | null;
  hour_data_confidence: number;
  burnout_risk_score: number;
  burnout_risk_level: BurnoutRiskLevel;
  burnout_signals: BurnoutSignal[];
}

// =============================================================================
// Review (FSRS) — Paket 4
// =============================================================================

export type ReviewState = "new" | "learning" | "review" | "relearning";

export interface ReviewCardItem {
  id: number;
  topic_id: number;
  topic_name: string;
  subject_name: string | null;
  state: ReviewState;
  due_at: string | null;
  last_reviewed_at: string | null;
  last_rating: number | null;
  stability: number;
  difficulty: number;
  review_count: number;
  lapse_count: number;
}

export interface ReviewBreakdown {
  new: number;
  learning: number;
  review: number;
  relearning: number;
  due_now: number;
  total: number;
}

export interface ReviewResponse {
  due_cards: ReviewCardItem[];
  breakdown: ReviewBreakdown;
}

// =============================================================================
// Goals — Paket 4
// =============================================================================

export type GoalKind =
  | "exam_target" | "subject" | "topic" | "weekly" | "daily" | "custom";
export type GoalStatus = "active" | "achieved" | "abandoned";

export interface GoalItem {
  id: number;
  parent_id: number | null;
  kind: GoalKind;
  status: GoalStatus;
  title: string;
  description: string | null;
  target_value: number | null;
  current_value: number | null;
  unit: string | null;
  target_date: string | null;
  is_auto_generated: boolean;
  progress_pct: number | null;
  achieved_at: string | null;
  created_at: string;
}

export interface GoalSummary {
  total: number;
  active: number;
  achieved: number;
  abandoned: number;
  overall_pct: number | null;
  next_target_date: string | null;
}

export interface GoalListResponse {
  items: GoalItem[];
  summary: GoalSummary;
}
