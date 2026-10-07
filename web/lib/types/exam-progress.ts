/** Deneme analizi Faz 2 — gelişim raporu, hedef, gündem kuyruğu, paylaşım. */

export interface ProgressExamPoint {
  id: number;
  title: string;
  exam_date: string;
  net: number;
  correct: number;
  wrong: number;
  blank: number;
  questions: number;
}

export interface ProgressStats {
  count: number;
  first_net: number;
  last_net: number;
  best_net: number;
  avg_net: number;
  avg_last3: number;
  change: number;
  slope: number | null;
  last_date: string;
  days_since_last: number;
}

export interface ProgressSubject {
  name: string;
  nets: (number | null)[];
  first: number | null;
  last: number | null;
  avg: number | null;
  change: number | null;
  slope: number | null;
  last_correct: number | null;
  last_wrong: number | null;
  last_blank: number | null;
  target: number | null;
  gap: number | null;
}

export interface ProgressTarget {
  target_net: number;
  target_date: string | null;
  subjects: Record<string, number>;
  note: string | null;
  set_by_name: string | null;
  updated_at: string | null;
  basis: string | null;
  basis_net: number | null;
  gap: number | null;
  progress_pct: number | null;
  weeks_left: number | null;
  exams_needed_at_pace: number | null;
  per_week_needed: number | null;
}

export type ProgressTone = "good" | "warn" | "info";

export interface ProgressComment {
  tone: ProgressTone;
  text: string;
}

export interface ProgressAction {
  key: string;
  kind: string;
  priority: number;
  title: string;
  detail: string;
  subject: string | null;
  topic_id: number | null;
  exam_id: number | null;
  queued: boolean;
}

export interface ProgressOpportunity {
  topic_id: number;
  topic_name: string;
  subject_name: string;
  wrong: number;
  blank: number;
  total: number;
  net_gain_per_exam: number;
}

export interface ExamProgressResponse {
  section: string | null;
  section_label: string | null;
  section_options: { value: string; label: string; count: number; kind?: string; section?: string | null }[];
  /** seçili seri (genel/branş) */
  series?: string | null;
  is_branch?: boolean;
  /** hedef net yalnız genel deneme serisinde */
  target_allowed?: boolean;
  student_name: string | null;
  generated_at: string;
  exams: ProgressExamPoint[];
  stats: ProgressStats | null;
  subjects: ProgressSubject[];
  target: ProgressTarget | null;
  commentary: ProgressComment[];
  actions: ProgressAction[];
  opportunities: ProgressOpportunity[];
}

export interface ExamTargetBody {
  section: string;
  target_net: number | null;
  target_date?: string | null;
  subjects?: Record<string, number | null> | null;
  note?: string | null;
}

export interface ExamTargetsResponse {
  targets: Record<string, ProgressTarget>;
  invalidate?: string[];
}

export interface AgendaQueueItem {
  id: string;
  key: string | null;
  text: string;
  source: string;
  exam_id: number | null;
  created_at: string | null;
}

export interface AgendaQueueResponse {
  items: AgendaQueueItem[];
  added: number;
  invalidate?: string[];
}

export interface ExamShareInfo {
  note: string | null;
  shared_at: string;
  first_shared_at: string | null;
  shared_by_name: string | null;
}

export interface ExamSharesResponse {
  shares: Record<string, ExamShareInfo>;
}

export interface ExamShareResult {
  exam_id: number;
  share: ExamShareInfo | null;
  notified: boolean;
  invalidate?: string[];
}
