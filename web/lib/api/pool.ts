/**
 * Haftalık görev havuzu (dershane modu) — rehber editörü istemcisi.
 * Backend: app/routes/api_v2/pool.py · app/services/pool_mode.py
 *
 * Havuz kalemi tarihsizdir ve REZERV tutmaz; öğrenci kalemi "günün kabına"
 * alınca o güne mevcut görev yazılır. Bu dosya yalnız rehber yüzeyi için.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";

export type PoolUnit = "test" | "soru" | "sayfa" | "deneme" | "etkinlik";
export type PoolSource = "rehber" | "ogrenci" | "deneme" | "devir" | "sablon";
export type PoolApproval = "yok" | "bekliyor" | "onaylandi" | "reddedildi";
export type PeriodStatus = "acik" | "kapandi" | "ara" | "gorusmesiz";

export interface PoolItemOut {
  id: number;
  subject_id: number | null;
  subject_name: string;
  topic_id: number | null;
  topic_name: string | null;
  book_id: number | null;
  book_name: string | null;
  section_id: number | null;
  section_label: string | null;
  label: string | null;
  quantity: number;
  unit: PoolUnit;
  completed: number;
  remaining: number;
  day_hint: string | null;
  source: PoolSource;
  teacher_homework: boolean;
  approval: PoolApproval;
  carry_count: number;
  cup_attempts: number;
  counts: boolean;
  created_by_name: string | null;
  created_at: string | null;
  book_completed: number | null;
  book_total: number | null;
  /** Deneme kalemi (D1b): quantity = deneme adedi, question_count = deneme başına soru. */
  exam_kind?: "brans" | "genel" | null;
  exam_section?: string | null;
  question_count?: number | null;
}

export interface PoolSummaryOut {
  total_units: number;
  done_units: number;
  pct: number;
  items_total: number;
  items_done: number;
  pending_student_items: number;
  days_left: number;
  per_day_needed: number;
  expected_next_on: string | null;
}

export interface PoolPeriodOut {
  id: number;
  opened_on: string;
  expected_next_on: string | null;
  closed_on: string | null;
  status: PeriodStatus;
  status_label: string;
  days_open: number;
  note: string | null;
  summary: PoolSummaryOut;
  items: PoolItemOut[];
}

export interface PoolPeriodBrief {
  parent_summary_sent_at: string | null; // K53
  id: number;
  opened_on: string;
  closed_on: string | null;
  status: PeriodStatus;
  status_label: string;
  total_units: number;
  done_units: number;
  pct: number;
}

export interface PoolSubjectOut {
  id: number;
  name: string;
  is_ayt: boolean;
  item_count: number;
  group: "okul" | "sinav";
  book_count: number;
  deneme_count: number;
}

export interface PoolClassGroupOut {
  id: number;
  name: string;
  positions: Record<string, { topic_id?: number; topic_name?: string | null; updated_on?: string }>;
  lesson_days: Record<string, number[]>;
}

export interface PoolBundleResponse {
  student: {
    id: number;
    full_name: string;
    program_mode: "gun_gun" | "havuz";
    grade_level: number | null;
    is_graduate: boolean;
    track: string | null;
    track_label: string | null;
    needs_track: boolean;
    class_group: string | null;
  };
  period: PoolPeriodOut | null;
  periods: PoolPeriodBrief[];
  subjects: PoolSubjectOut[];
  ayt_locked: boolean;
  locked_ayt_names: string[];
  curriculum_label: string | null;
  /** Maarif 11+: eski TYT/AYT yerine "TYT (Maarif)" grubu — bu okul dersleri, konular ≤ tyt_maarif_max_grade */
  tyt_maarif_subject_ids?: number[];
  tyt_maarif_max_grade?: number;
  missing_subjects: string[];
  class_group: PoolClassGroupOut | null;
  volume: { avg_done_last3: number | null; current_total: number };
  flags: PoolFlagsOut;
  carry_candidates: PoolCarryCandidate[];   // Adım 6: dönem açarken devir adayları (son kapanmış dönem)
  carry_source_period_id: number | null;
  on_break: PoolBreakOut | null;            // K61 ara (tatil)
  periods_total: number;                    // K60
  units: PoolUnit[];
  today: string;
}

export interface PoolCarryCandidate {
  item_id: number;
  subject_name: string;
  title: string;
  unit: PoolUnit;
  remaining: number;
  quantity: number;
  carry_count: number;
  third_carry: boolean; // K58: bu devirle 3. kez → kaçınılan sinyali; miktar yeniden yazılır
  teacher_homework: boolean;
}

export interface PoolBreakOut {
  period_id: number;
  since: string;
  note: string | null;
}

/** Havuz erken uyarı sinyali (pool_flags, Adım 4 — K40–K51). */
export interface PoolFlagOut {
  code: string;
  level: "red" | "amber" | "green";
  layer: string; // P dönem · K katılım · T tempo · D doğruluk · E deneme · A kaçınma · Z desen · G iyi
  title: string;
  detail: string;
  evidence: { label: string; value: string }[];
  coach_only: boolean;
}

export interface PoolFlagsOut {
  headline: string;
  level: "red" | "amber" | "green";
  primary: PoolFlagOut[]; // K48: en çok 1 ana kart
  secondary: PoolFlagOut[];
  good: PoolFlagOut[];
  paper_student: boolean; // K40
}

export interface PoolTopicSource {
  book_id: number;
  book_name: string;
  section_id: number;
  section_label: string;
  total: number;
  remaining: number;
  completed: number;
  recommended: boolean;
}

export interface PoolTopicOut {
  topic_id: number;
  name: string;
  unit_name: string | null;
  status: string;
  remaining: number;
  tests_solved: number;
  accuracy_pct: number | null;
  last_assigned_on: string | null;
  is_last: boolean;
  is_class_position: boolean;
  grade_level: number | null;
  sources: PoolTopicSource[];
}

export interface PoolTopicsResponse {
  subject_id: number;
  subject_name: string;
  topics: PoolTopicOut[];
}

export interface PoolItemBody {
  subject_id: number;
  topic_id?: number | null;
  book_id?: number | null;
  section_id?: number | null;
  label?: string | null;
  quantity?: number | null;
  unit: PoolUnit;
  day_hint?: string | null;
  teacher_homework?: boolean;
  source?: "rehber" | "deneme" | "sablon";
  exam_result_id?: number | null;
}

export interface ParseChip {
  kind: "subject" | "topic" | "book" | "section" | "quantity" | "unit" | "text";
  id: number | null;
  label: string;
  confident: boolean;
}

/** Belirsiz ayrıştırmada "Bunu mu demek istedin?" seçeneği (konu ya da yalnız ders). */
export interface ParseOption {
  subject_id: number;
  subject_name: string;
  topic_id: number | null;
  topic_name: string | null;
  grade_level: number | null;
  unit_name: string | null;
  book_id: number | null;
  section_id: number | null;
  label: string | null;
}

export interface ParseResponse {
  chips: ParseChip[];
  draft: PoolItemBody | null;
  warning: string | null;
  options?: ParseOption[];
  base?: { quantity: number | null; unit: PoolUnit } | null;
}

export const UNIT_LABELS: Record<PoolUnit, string> = {
  test: "test",
  soru: "soru",
  sayfa: "sayfa",
  deneme: "deneme",
  etkinlik: "etkinlik",
};

export const SOURCE_LABELS: Record<PoolSource, string> = {
  rehber: "Rehber",
  ogrenci: "Öğrenci ekledi",
  deneme: "Denemeden",
  devir: "Devir",
  sablon: "Şablondan",
};

export const poolKeys = {
  bundle: (id: number) => ["teacher", "me", "students", String(id), "pool"] as const,
  topics: (id: number, subjectId: number) =>
    ["teacher", "me", "students", String(id), "pool", "topics", String(subjectId)] as const,
};

const base = (id: number) => `/api/v2/teacher/students/${encodeURIComponent(String(id))}`;

export function getPool(studentId: number): Promise<PoolBundleResponse> {
  return api(`${base(studentId)}/pool`);
}

export function getPoolTopics(studentId: number, subjectId: number): Promise<PoolTopicsResponse> {
  return api(`${base(studentId)}/pool/topics?subject_id=${encodeURIComponent(String(subjectId))}`);
}

export function parsePoolText(
  studentId: number,
  body: { text: string; subject_id?: number | null },
): Promise<ParseResponse> {
  return api(`${base(studentId)}/pool/parse`, { method: "POST", body: JSON.stringify(body) });
}

function errMsg(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.detail.message || fallback;
  return fallback;
}

type Bundle = MutationResponse<PoolBundleResponse>;

function useBundleMutation<TBody>(
  studentId: number,
  path: (b: TBody) => string,
  okTitle: string | null,
  failTitle: string,
) {
  const qc = useQueryClient();
  return useMutation<Bundle, ApiError, TBody>({
    mutationFn: (body) =>
      api(path(body), {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      }),
    onError: (e) => toast.error(failTitle, { description: errMsg(e, "Tekrar dene.") }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.setQueryData(poolKeys.bundle(studentId), res.data);
      if (okTitle) toast.success(okTitle);
    },
  });
}

export function useSetProgramMode(studentId: number) {
  return useBundleMutation<{ mode: "gun_gun" | "havuz" }>(
    studentId, () => `${base(studentId)}/program-mode`, "Program modu değişti", "Mod değiştirilemedi",
  );
}

// ---------------------------------------------------------------- 2026-10-15 mod geçişi

export interface ModeSwitchTask {
  task_id: number;
  date: string;
  title: string;
  planned: number;
  completed: number;
  is_draft: boolean;
  is_cup: boolean;
}

export interface ModeSwitchPreview {
  from_mode: "gun_gun" | "havuz";
  to_mode: "gun_gun" | "havuz";
  effective_on: string;
  allowed: boolean;
  blocker: string | null;
  blocker_message: string | null;
  delete_tasks: ModeSwitchTask[];
  keep_partial: ModeSwitchTask[];
  release_tests: number;
  dead_reserve_tests: number;
  pool_leftover_items: number;
  pool_leftover_units: number;
  notes: string[];
}

export interface ModeChange {
  id: number;
  from_mode: string;
  to_mode: string;
  from_label: string;
  to_label: string;
  effective_on: string;
  trigger: string;
  trigger_label: string;
  changed_by_name: string | null;
  note: string | null;
  summary: Record<string, number>;
  created_at: string | null;
}

export const modeSwitchKeys = {
  preview: (id: number, to: string, on: string) =>
    ["teacher", "me", "students", String(id), "pool", "mode-preview", to, on] as const,
  history: (id: number) => ["teacher", "me", "students", String(id), "pool", "mode-history"] as const,
};

export function getModeSwitchPreview(studentId: number, to: "gun_gun" | "havuz", effectiveOn: string): Promise<ModeSwitchPreview> {
  const q = new URLSearchParams({ to, effective_on: effectiveOn });
  return api(`${base(studentId)}/program-mode/preview?${q.toString()}`);
}

export function getModeHistory(studentId: number): Promise<{ current_mode: string; items: ModeChange[] }> {
  return api(`${base(studentId)}/program-mode/history`);
}

export function useSwitchProgramMode(studentId: number) {
  return useBundleMutation<{
    to_mode: "gun_gun" | "havuz"; effective_on?: string; open_first_period?: boolean;
    expected_next_on?: string | null; note?: string | null;
  }>(
    studentId, () => `${base(studentId)}/program-mode/switch`, "Program modu değişti", "Mod değiştirilemedi",
  );
}

export function useOpenPeriod(studentId: number) {
  return useBundleMutation<{
    opened_on: string; expected_next_on?: string | null; note?: string | null;
    carry?: { item_id: number; quantity: number | null }[];
  }>(
    studentId, () => `${base(studentId)}/pool/periods`, "Dönem açıldı", "Dönem açılamadı",
  );
}

export function useClosePeriod(studentId: number) {
  return useBundleMutation<{ period_id: number; closed_on: string; status: "kapandi" | "ara" | "gorusmesiz"; note?: string | null }>(
    studentId,
    (b) => `${base(studentId)}/pool/periods/${b.period_id}/close`,
    "Dönem kapatıldı",
    "Dönem kapatılamadı",
  );
}

export function useSetExpected(studentId: number) {
  return useBundleMutation<{ period_id: number; opened_on: string; expected_next_on: string | null }>(
    studentId,
    (b) => `${base(studentId)}/pool/periods/${b.period_id}/expected`,
    "Beklenen seans günü güncellendi",
    "Gün güncellenemedi",
  );
}

export function useAddPoolItem(studentId: number) {
  return useBundleMutation<PoolItemBody>(
    studentId, () => `${base(studentId)}/pool/items`, "Havuza eklendi", "Kalem eklenemedi",
  );
}

/** Deneme formundan havuza deneme kalemi (D1b) — kaba alınınca her deneme ayrı satır. */
export function useAddPoolDeneme(studentId: number) {
  return useBundleMutation<{
    kind: "brans" | "genel";
    count: number;
    question_count?: number | null;
    subject_id?: number | null;
    book_id?: number | null;
    genel_key?: string | null;
    name?: string | null;
  }>(studentId, () => `${base(studentId)}/pool/deneme-items`, "Havuza deneme eklendi", "Deneme eklenemedi");
}

export function useDeletePoolItem(studentId: number) {
  return useBundleMutation<{ item_id: number }>(
    studentId, (b) => `${base(studentId)}/pool/items/${b.item_id}/delete`, "Kalem kaldırıldı", "Kalem kaldırılamadı",
  );
}

export function useSetPoolItemQuantity(studentId: number) {
  return useBundleMutation<{ item_id: number; quantity: number }>(
    studentId, (b) => `${base(studentId)}/pool/items/${b.item_id}/quantity`, "Miktar güncellendi", "Miktar değiştirilemedi",
  );
}

export function useApprovePoolItem(studentId: number) {
  return useBundleMutation<{ item_id: number; approved: boolean }>(
    studentId, (b) => `${base(studentId)}/pool/items/${b.item_id}/approve`, null, "Onay işlenemedi",
  );
}

export function useSetClassPosition(studentId: number) {
  return useBundleMutation<{ subject_id: number; topic_id: number | null }>(
    studentId, () => `${base(studentId)}/pool/class-group/position`, "Şube konumu yazıldı", "Konum yazılamadı",
  );
}

export function useSetLessonDays(studentId: number) {
  return useBundleMutation<{ lessons: Record<string, number[]> }>(
    studentId, () => `${base(studentId)}/pool/class-group/lesson-days`, "Ders programı kaydedildi", "Program kaydedilemedi",
  );
}

// ---------------------------------------------------------------- seans ekranı (K18–K22)

export interface SessionExamTopic { topic_id: number; name: string; wrong: number }

export interface SessionExamStrip {
  exam_id: number;
  title: string;
  exam_date: string;
  net: number;
  delta: number | null;
  prev_title: string | null;
  in_period: boolean;
  wrong_topics: SessionExamTopic[];
  studied_but_wrong: SessionExamTopic[];
}

export interface SessionItemOut extends PoolItemOut {
  session_marked: number;
  done_units: number;
  avoided: boolean;
  avoided_reason: string | null;
  /** Seansta konu kapatma: kalemin konusu (kendi ya da kitap bölümünün eşli konusu) */
  closure_topic_id?: number | null;
  topic_closed?: boolean;
}

export interface PoolSessionResponse {
  student: PoolBundleResponse["student"];
  period: PoolPeriodOut | null;
  headline: string;
  items: SessionItemOut[];
  avoided: SessionItemOut[];
  pending_student_items: SessionItemOut[];
  exam: SessionExamStrip | null;
  previous_session: {
    id: number; session_date: string; agenda: string; coach_note: string | null;
    next_change: string | null; mood: number | null;
  } | null;
  agenda_queue: { id: string; text: string; source: string | null }[];
  flags: PoolFlagsOut;
  today: string;
}

export const poolSessionKey = (id: number) =>
  ["teacher", "me", "students", String(id), "pool", "session"] as const;

export function getPoolSession(studentId: number): Promise<PoolSessionResponse> {
  return api(`${base(studentId)}/pool/session`);
}

export function useSessionMark(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<PoolSessionResponse>, ApiError, { item_id: number; count: number }>({
    mutationFn: (b) =>
      api(`${base(studentId)}/pool/items/${b.item_id}/session-mark`, {
        method: "POST", body: JSON.stringify({ count: b.count }),
      }),
    onError: (e) => toast.error("İşaret kaydedilemedi", { description: errMsg(e, "Tekrar dene.") }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.setQueryData(poolSessionKey(studentId), res.data);
    },
  });
}

export interface SessionFinishBody {
  closed_on: string;
  expected_next_on: string | null;
  carry: { item_id: number; quantity: number | null }[];
  record_session: boolean;
  agenda?: string | null;
  coach_note?: string | null;
  next_change?: string | null;
  mood?: number | null;
  switch_to_gun_gun?: boolean;
}

export function useFinishSession(studentId: number) {
  return useBundleMutation<SessionFinishBody>(
    studentId, () => `${base(studentId)}/pool/session/finish`, null, "Seans bitirilemedi",
  );
}


// ---------------------------------------------------------------- K53 veli dönem özeti

export interface PoolParentSummaryResponse {
  period_id: number;
  student_id: number;
  student_name: string;
  opened_on: string;
  closed_on: string;
  opened_label?: string | null;
  closed_label?: string | null;
  days: number;
  pct: number;
  done_units: number;
  total_units: number;
  items_done: number;
  items_total: number;
  subjects: { subject: string; total: number; done: number; items: number; items_done: number; pct: number }[];
  items: { subject: string; name: string; quantity: number; unit: string; done: number; is_done: boolean; teacher_homework: boolean }[];
  carried: { subject: string; name: string; quantity: number; unit: string }[];
  exam: { title: string; date: string; net: number; delta: number | null; prev_title: string | null } | null;
  narrative: string[];
  include_items: boolean;
  include_exam: boolean;
  recipients: { parent_id: number; name: string; email: string | null; will_send: boolean; reason: string | null }[];
  is_sent_snapshot: boolean;
  sent_at: string | null;
}

export const poolParentSummaryKey = (studentId: number, periodId: number) =>
  ["teacher", "me", "students", String(studentId), "pool", "parent-summary", String(periodId)] as const;

export function getPoolParentSummary(studentId: number, periodId: number): Promise<PoolParentSummaryResponse> {
  return api(`${base(studentId)}/pool/periods/${periodId}/parent-summary`);
}

export interface PoolParentSummarySendBody {
  narrative: string[];
  include_items: boolean;
  include_exam: boolean;
}

export function useSendPoolParentSummary(studentId: number, periodId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<{ queued: number; suppressed: number; sent: boolean; sent_at: string | null }>, ApiError, PoolParentSummarySendBody>({
    mutationFn: (b) =>
      api(`${base(studentId)}/pool/periods/${periodId}/parent-summary/send`, { method: "POST", body: JSON.stringify(b) }),
    onError: (e) => toast.error("Özet gönderilemedi", { description: errMsg(e, "Tekrar dene.") }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.invalidateQueries({ queryKey: poolParentSummaryKey(studentId, periodId) });
      qc.invalidateQueries({ queryKey: poolKeys.bundle(studentId) });
      toast.success(res.data.queued > 0 ? `${res.data.queued} veliye gönderildi` : "Hiçbir veliye gitmedi",
        { description: res.data.suppressed ? `${res.data.suppressed} veli tercihinden dolayı almadı.` : undefined });
    },
  });
}

// ---------------------------------------------------------------- K48/K50 günlük görüşme listesi

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
  primary: PoolFlagOut | null;
  primary_snoozed: boolean;
  extra: PoolFlagOut[];
  good: PoolFlagOut[];
  paper_student: boolean;
}

export interface PoolDailyResponse {
  today: string;
  rows: PoolDailyRow[];
  counts: { students: number; sessions_today: number; red: number; amber: number; snoozed: number };
}

export const poolDailyKey = ["teacher", "me", "pool", "daily"] as const;

export function getPoolDaily(): Promise<PoolDailyResponse> {
  return api("/api/v2/teacher/pool/daily");
}


// ---------------------------------------------------------------- K60 dönem geçmişi (sayfalı)

export interface PoolHistoryRow {
  id: number;
  opened_on: string;
  closed_on: string | null;
  expected_next_on: string | null;
  status: string;
  status_label: string;
  note: string | null;
  total_units: number;
  done_units: number;
  pct: number;
  items_total: number;
  items_done: number;
  session_marked_units: number;
  carried_in: number;
  carried_out: number;
  has_session: boolean;
  parent_summary_sent_at: string | null;
  subjects: { subject: string; total: number; done: number; pct: number }[];
}

export interface PoolHistoryResponse {
  total: number;
  offset: number;
  limit: number;
  rows: PoolHistoryRow[];
}

export const poolHistoryKey = (studentId: number, offset: number, limit: number) =>
  ["teacher", "me", "students", String(studentId), "pool", "history", String(offset), String(limit)] as const;

export function getPoolHistory(studentId: number, offset = 0, limit = 10): Promise<PoolHistoryResponse> {
  return api(`${base(studentId)}/pool/periods?offset=${offset}&limit=${limit}`);
}


// ---------------------------------------------------------------- dönem penceresi (geçmiş dönem içi, 2026-10-13)
// Rehber / öğrenci / veli aynı yanıt şeklini alır; yüzey farkı sunucuda (audience).

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
  completed: number;        // öğrenci kaydı
  session_marked: number;   // rehber seansta işaretledi
  done: number;
  remaining: number;
  source: PoolSource;
  teacher_homework: boolean;
  approval: PoolApproval;
  counts: boolean;
  carry_count: number;
  cup_attempts: number;     // yalnız rehber
  cup_returns: number;      // yalnız rehber
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
  period: PoolHistoryRow;
  items: PoolPeriodDetailItem[];
  removed_items: PoolPeriodDetailItem[];
  days: PoolPeriodDay[];
  audience: "teacher" | "student" | "parent";
  today: string;
}

export const poolPeriodDetailKey = (studentId: number, periodId: number) =>
  ["teacher", "me", "students", String(studentId), "pool", "period", String(periodId)] as const;

export function getPoolPeriodDetail(studentId: number, periodId: number): Promise<PoolPeriodDetailResponse> {
  return api(`${base(studentId)}/pool/periods/${periodId}`);
}


// ---------------------------------------------------------------- dönem silme (2026-10-13)

export interface PoolPeriodDeleteImpact {
  period_id: number;
  deletable: boolean;
  blocked_reason: string | null;
  items: number;
  removed_items: number;
  tasks_kept: number;      // öğrencinin çalıştığı kap görevi → korunur
  tasks_deleted: number;   // hiç dokunulmamış kap görevi → silinir
  done_units: number;
  session_marked_units: number;
  carried_out: number;
  parent_summary_sent: boolean;
}

export const poolPeriodDeleteImpactKey = (studentId: number, periodId: number) =>
  ["teacher", "me", "students", String(studentId), "pool", "delete-impact", String(periodId)] as const;

export function getPoolPeriodDeleteImpact(studentId: number, periodId: number): Promise<PoolPeriodDeleteImpact> {
  return api(`${base(studentId)}/pool/periods/${periodId}/delete-impact`);
}

export function useDeletePoolPeriod(studentId: number) {
  return useBundleMutation<{ period_id: number }>(
    studentId, (b) => `${base(studentId)}/pool/periods/${b.period_id}/delete`, "Dönem silindi", "Dönem silinemedi",
  );
}


// ---------------------------------------------------------------- "Nereden? → Öğrencinin kitapları" (2026-10-13)

export interface PoolBookSectionOut {
  section_id: number;
  label: string;
  test_count: number;
  completed: number;
  remaining: number;   // test − çözülen − gün-gün rezerv
  in_pool: number;     // açık dönemde havuzda bekleyen
  available: number;   // remaining − in_pool
  topic_name: string | null;
  last_on: string | null;
  is_last: boolean;
}

export interface PoolBookOut {
  book_id: number;
  name: string;
  publisher: string | null;
  type: string;
  type_label: string;
  is_deneme: boolean;
  total_tests: number;
  completed: number;
  sections: PoolBookSectionOut[];
}

export interface PoolBooksResponse {
  subject_id: number;
  subject_name: string;
  books: PoolBookOut[];
}

export const poolBooksKey = (studentId: number, subjectId: number) =>
  ["teacher", "me", "students", String(studentId), "pool", "books", String(subjectId)] as const;

export function getPoolBooks(studentId: number, subjectId: number): Promise<PoolBooksResponse> {
  return api(`${base(studentId)}/pool/books?subject_id=${subjectId}`);
}
