import { apiRequest } from "./api";

/**
 * Haftalık görev havuzu (dershane modu) — öğrenci yüzeyi.
 * Backend: app/routes/api_v2/pool_student.py. Kap = o güne mevcut görev →
 * işaretleme Bugün ekranındaki olağan akışla (D/Y/B) yapılır.
 */

export type PoolUnit = "test" | "soru" | "sayfa" | "deneme" | "etkinlik";

export interface StudentPoolItem {
  id: number;
  subject_id: number | null;
  subject_name: string;
  title: string;
  book_name: string | null;
  quantity: number;
  unit: PoolUnit;
  done: number;
  remaining: number;
  day_hint: string | null;
  source: "rehber" | "ogrenci" | "deneme" | "devir" | "sablon";
  teacher_homework: boolean;
  approval: "yok" | "bekliyor" | "onaylandi" | "reddedildi";
  counts: boolean;
  in_cup_today: boolean;
  cup_task_id: number | null;
  suggested: boolean;
}

export interface StudentCupTask {
  task_id: number;
  item_id: number | null;
  title: string;
  status: string;
  planned: number;
  completed: number;
  can_return: boolean;
}

export interface StudentPoolSummary {
  pct: number;
  total_units: number;
  done_units: number;
  items_total: number;
  items_done: number;
  days_left: number;
  per_day_needed: number;
  expected_next_on: string | null;
  pace: "onde" | "yolunda" | "geride" | "belirsiz";
  pace_note: string;
}

export interface StudentPoolResponse {
  mode: "gun_gun" | "havuz";
  period_id: number | null;
  opened_on: string | null;
  summary: StudentPoolSummary | null;
  items: StudentPoolItem[];
  cup: StudentCupTask[];
  projection: { date: string; units: number }[];
  lesson_today: string[];
  subjects: { id: number; name: string; group?: "okul" | "sinav"; is_ayt?: boolean; book_count?: number }[];
  student_id?: number;
  grade_level?: number | null;
  /** K41/K46/K48: yönlendirme cümleleri — kırmızı yok, yargı yok. */
  hints: { code: string; title: string; note: string }[];
  /** K60: önceki dönemler (öğrenci görür; yargı yok). */
  previous: { id: number; opened_on: string; closed_on: string | null; status: string; status_label: string; total_units: number; done_units: number; pct: number }[];
  /** K61: ara (tatil). */
  on_break: { period_id: number; since: string; note: string | null } | null;
  units: PoolUnit[];
  today: string;
}

export const UNIT_LABELS: Record<PoolUnit, string> = {
  test: "test", soru: "soru", sayfa: "sayfa", deneme: "deneme", etkinlik: "etkinlik",
};

export const poolKeys = {
  parent: (studentId: number) => ["parent", "child", studentId, "pool"] as const,
  daily: () => ["teacher", "pool", "daily"] as const,
  pool: ["student", "pool"] as const,
  topics: (subjectId: number) => ["student", "pool", "topics", subjectId] as const,
  books: (subjectId: number) => ["student", "pool", "books", subjectId] as const,
};

export function getStudentPool(): Promise<StudentPoolResponse> {
  return apiRequest<StudentPoolResponse>("/api/v2/student/pool");
}

interface Mut { data: StudentPoolResponse; invalidate: string[] }

export function cupAdd(item_id: number, count?: number | null): Promise<Mut> {
  return apiRequest<Mut>("/api/v2/student/pool/cup", { method: "POST", body: { item_id, count: count ?? null } });
}

export function cupReturn(task_id: number): Promise<Mut> {
  return apiRequest<Mut>(`/api/v2/student/pool/cup/${task_id}/return`, { method: "POST" });
}

export interface StudentPoolItemBody {
  subject_id: number;
  topic_id?: number | null;
  book_id?: number | null;
  section_id?: number | null;
  page_from?: number | null;
  page_to?: number | null;
  label?: string | null;
  quantity?: number | null;
  unit: PoolUnit;
  teacher_homework?: boolean;
}

export function addStudentPoolItem(body: StudentPoolItemBody): Promise<Mut> {
  return apiRequest<Mut>("/api/v2/student/pool/items", { method: "POST", body });
}

// ---------------------------------------------------------------- kalem ekleme kaynakları (2026-10-22)
// Öğrenci de koç gibi kitabının bölümünden ya da müfredat konusundan ekler (web ile aynı uçlar).
export interface PoolTopic {
  topic_id: number;
  name: string;
  unit_name: string | null;
  status: string;
  grade_level: number | null;
  is_last: boolean;
  sources: { book_id: number; section_id: number }[];
}

export interface PoolBookSection {
  section_id: number;
  label: string;
  test_count: number;
  completed: number;
  remaining: number;
  in_pool: number;
  available: number;
  topic_name: string | null;
  is_last: boolean;
}

export interface PoolBook {
  book_id: number;
  name: string;
  type_label: string;
  is_deneme: boolean;
  total_tests: number;
  completed: number;
  sections: PoolBookSection[];
}

export function getStudentPoolTopics(subjectId: number): Promise<{ subject_id: number; subject_name: string; topics: PoolTopic[] }> {
  return apiRequest(`/api/v2/student/pool/topics?subject_id=${subjectId}`);
}

export function getStudentPoolBooks(subjectId: number): Promise<{ subject_id: number; subject_name: string; books: PoolBook[] }> {
  return apiRequest(`/api/v2/student/pool/books?subject_id=${subjectId}`);
}

export function closePoolDay(date?: string): Promise<Mut> {
  return apiRequest<Mut>("/api/v2/student/pool/close-day", { method: "POST", body: { date: date ?? null } });
}


// ---------------------------------------------------------------- K52 veli salt-okuma

export interface ParentPoolItem {
  id: number;
  subject_name: string;
  title: string;
  quantity: number;
  unit: string;
  done: number;
  remaining: number;
  teacher_homework: boolean;
  in_cup_today: boolean;
}

export interface ParentPoolResponse {
  mode: "gun_gun" | "havuz";
  period_id: number | null;
  opened_on: string | null;
  expected_next_on: string | null;
  days_open: number | null;
  summary: StudentPoolSummary | null;
  items: ParentPoolItem[];
  cup: { title: string; status: string }[];
  previous: { id: number; opened_on: string; closed_on: string | null; status: string; status_label: string; total_units: number; done_units: number; pct: number }[];
  on_break: { period_id: number; since: string; note: string | null } | null;
  today: string;
}

export function getParentStudentPool(studentId: number): Promise<ParentPoolResponse> {
  return apiRequest<ParentPoolResponse>(`/api/v2/parent/students/${studentId}/pool`);
}

// ---------------------------------------------------------------- K48/K50 koç günlük liste

export interface PoolFlag {
  code: string;
  level: "red" | "amber" | "green";
  layer: string;
  title: string;
  detail: string;
  evidence: { label: string; value: string }[];
  coach_only: boolean;
}

export interface PoolDailyRow {
  student_id: number;
  student_name: string;
  class_group: string | null;
  session_today: boolean;
  appointment_time: string | null;
  appointment_id: number | null;
  period_id: number | null;
  days_open: number | null;
  expected_next_on: string | null;
  pct: number | null;
  level: "red" | "amber" | "green";
  headline: string;
  primary: PoolFlag | null;
  primary_snoozed: boolean;
  extra: PoolFlag[];
  good: PoolFlag[];
  paper_student: boolean;
}

export interface PoolDailyResponse {
  today: string;
  rows: PoolDailyRow[];
  counts: { students: number; sessions_today: number; red: number; amber: number; snoozed: number };
}

export function getPoolDaily(): Promise<PoolDailyResponse> {
  return apiRequest<PoolDailyResponse>("/api/v2/teacher/pool/daily");
}

/** Gördüm/Ertele — pano uyarı akışıyla ortak WarningState (3 gün). */
export function ackPoolWarning(student_id: number, code: string): Promise<unknown> {
  return apiRequest("/api/v2/teacher/dashboard/warnings/ack", { method: "POST", body: { student_id, code, snooze_days: 3 } });
}

export function unackPoolWarning(student_id: number, code: string): Promise<unknown> {
  return apiRequest("/api/v2/teacher/dashboard/warnings/unack", { method: "POST", body: { student_id, code } });
}

// ---------------------------------------------------------------- dönem penceresi (geçmiş dönem içi, 2026-10-13)
// Web `lib/api/pool.ts` ile aynı sözleşme; sunucu yüzeye göre süzer (öğrenci: kaçınma sayacı yok,
// veli: onay bekleyen kalem yok).

export interface PoolPeriodDetailItem {
  id: number;
  subject_id: number | null;
  subject_name: string;
  title: string;
  topic_name: string | null;
  book_name: string | null;
  section_label: string | null;
  label: string | null;
  quantity: number;
  unit: PoolUnit;
  completed: number;
  session_marked: number;
  done: number;
  remaining: number;
  source: string;
  teacher_homework: boolean;
  approval: string;
  counts: boolean;
  carry_count: number;
  cup_attempts: number;
  cup_returns: number;
  carried_out: boolean;
  exam_linked: boolean;
  day_hint: string | null;
  removed: boolean;
  removed_at: string | null;
  created_by_name: string | null;
}

export interface PoolPeriodDayTask {
  task_id: number;
  item_id: number | null;
  title: string;
  status: "pending" | "partial" | "completed" | "cancelled";
  type: string;
  planned: number | null;
  done: number;
  correct: number | null;
  wrong: number | null;
  blank: number | null;
  period: string | null;
  itemless: boolean;
}

export interface PoolPeriodDay {
  date: string;
  weekday: number;
  tasks: PoolPeriodDayTask[];
  done_units: number;
}

export interface PoolPeriodDetailResponse {
  period: {
    id: number; opened_on: string; closed_on: string | null; status: string; status_label: string; note: string | null;
    total_units: number; done_units: number; pct: number; items_total: number; items_done: number;
    session_marked_units: number; carried_in: number; carried_out: number; has_session: boolean;
    parent_summary_sent_at: string | null; subjects: { subject: string; total: number; done: number; pct: number }[];
  };
  items: PoolPeriodDetailItem[];
  removed_items: PoolPeriodDetailItem[];
  days: PoolPeriodDay[];
  audience: "teacher" | "student" | "parent";
  today: string;
}

export const poolPeriodKeys = {
  student: (periodId: number) => ["student", "me", "pool", "period", String(periodId)] as const,
  parent: (studentId: number, periodId: number) => ["parent", "me", "students", String(studentId), "pool", "period", String(periodId)] as const,
};

export function getStudentPoolPeriod(periodId: number): Promise<PoolPeriodDetailResponse> {
  return apiRequest<PoolPeriodDetailResponse>(`/api/v2/student/pool/periods/${periodId}`);
}

export function getParentPoolPeriod(studentId: number, periodId: number): Promise<PoolPeriodDetailResponse> {
  return apiRequest<PoolPeriodDetailResponse>(`/api/v2/parent/students/${studentId}/pool/periods/${periodId}`);
}

// ---------------------------------------------------------------- koç: havuz İZLE görünümü (2026-10-14)
// Web editörünün "İzle" modunun mobil karşılığı: paket (dönem + özet + uyarılar) + dönem ayrıntısı (kalemler + gün gün).

export interface TeacherPoolBundle {
  student: { id: number; full_name: string; program_mode: "gun_gun" | "havuz" };
  period: {
    id: number;
    opened_on: string;
    expected_next_on: string | null;
    days_open: number;
    summary: {
      total_units: number; done_units: number; pct: number; items_total: number; items_done: number;
      pending_student_items: number; days_left: number; per_day_needed: number; expected_next_on: string | null;
    };
  } | null;
  flags: { headline: string; level: string; primary: PoolFlag[]; secondary: PoolFlag[]; good: PoolFlag[]; paper_student: boolean };
  today: string;
}

export const teacherPoolKeys = {
  bundle: (studentId: number) => ["teacher", "me", "students", String(studentId), "pool"] as const,
  period: (studentId: number, periodId: number) => ["teacher", "me", "students", String(studentId), "pool", "period", String(periodId)] as const,
};

export function getTeacherPool(studentId: number): Promise<TeacherPoolBundle> {
  return apiRequest<TeacherPoolBundle>(`/api/v2/teacher/students/${studentId}/pool`);
}

export function getTeacherPoolPeriod(studentId: number, periodId: number): Promise<PoolPeriodDetailResponse> {
  return apiRequest<PoolPeriodDetailResponse>(`/api/v2/teacher/students/${studentId}/pool/periods/${periodId}`);
}

export function approveTeacherPoolItem(studentId: number, itemId: number, approved: boolean): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/students/${studentId}/pool/items/${itemId}/approve`, { method: "POST", body: { approved } });
}
