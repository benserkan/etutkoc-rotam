/**
 * Haftalık İskelet (F1) — kalıptan program.
 * Backend: app/routes/api_v2/weekly_skeleton.py · app/services/skeleton_suggest.py
 *
 * İskelet = hafta günü + (periyot) + ders satırları. Satırı dolmamış
 * gün+periyotta HAYALET hücre görünür (görev DEĞİL, rezerv tutmaz). Hayalete
 * tıklanınca iplik modelinden türeyen konu çipleri gelir; çip = görev.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";

export type SkeletonPeriod = "morning" | "noon" | "evening";

export interface SkeletonSlotIn {
  weekday: number; // 0=Pazartesi … 6=Pazar
  period: SkeletonPeriod | null;
  subject_id: number;
  position: number;
  is_routine: boolean;
  default_count: number | null;
  /** Satırın kaynağı: kitap (rutin kitabı / konu satırında öncelikli kitap) */
  book_id?: number | null;
  /** Kitapsız (serbest metinli) görevden gelen satırın adı */
  label?: string | null;
  /** Kitaba bağlı rutinin ilerleme biçimi */
  routine_mode?: RoutineMode | null;
  /** Okulda/dershanede işlenen ders (çapa) */
  is_anchor?: boolean;
  /** Rutin kapsamı: kitabın tamamı ya da yalnız problemler (null = kitap) */
  routine_scope?: RoutineScope | null;
  /** Konu satırının 2. ana kaynağı (soru bankası) */
  second_book_id?: number | null;
}

export type RoutineScope = "book" | "problems";

/** iki_kaynak: sırayla; ana kaynakta biten konu 2. kaynakta (second_book_id) bitirilir. */
export type RoutineMode = "sirali" | "karma" | "iki_kaynak";

export const ROUTINE_MODE_LABELS: Record<RoutineMode, string> = {
  sirali: "sırayla",
  karma: "karışık",
  iki_kaynak: "sırayla · konu 2. kaynakta biter",
};

export interface SkeletonSlot extends SkeletonSlotIn {
  id: number;
  subject_name: string;
  book_name: string | null;
  second_book_name?: string | null;
}

export interface SkeletonBookOption {
  id: number;
  name: string;
  subject_id: number;
  book_type?: string | null;
  /** Yalnız soru bankası ana / 2. kaynak / problem kaynağı olabilir */
  is_bank?: boolean;
  has_problems?: boolean;
}

export interface CapacityItem {
  weekday: number;
  learned: number | null;
  override: number | null;
  effective: number | null;
}

/** F2-2 dönem: yalnız başlangıç taşır, bir sonraki dönem başlayana kadar geçerli */
export interface SkeletonTerm {
  id: number;
  name: string;
  valid_from: string | null;
  valid_until: string | null;
  slot_count: number;
  is_current: boolean;
  source: string | null;
}

export interface SkeletonResponse {
  exists: boolean;
  id: number | null;
  name: string | null;
  source: string | null;
  valid_from: string | null;
  valid_until: string | null;
  periods: SkeletonTerm[];
  capacity: CapacityItem[];
  slots: SkeletonSlot[];
  subjects: { id: number; name: string }[];
  books: SkeletonBookOption[];
}

export interface ChipBadge {
  code: string;
  label: string;
  tone: string; // rose | amber | violet | emerald | slate | cyan …
}

export type ChipKind = "thread" | "next" | "new" | "weak" | "routine" | "second";

export interface GhostChip {
  rank: number;
  kind: ChipKind;
  section_id: number;
  book_id: number;
  book_name: string;
  section_label: string;
  topic_id: number | null;
  topic_name: string | null;
  count: number;
  remaining: number;
  total: number;
  reason: string;
  badges: ChipBadge[];
  /** Rutin çipi birden çok bölümü kapsayabilir */
  items?:
    | {
        section_id: number;
        section_label: string;
        count: number;
        book_id?: number | null;
        book_name?: string | null;
      }[]
    | null;
  /** 1. kaynakta konu bitti — koçun seçeceği seçeneklerden biri */
  source_choice?: boolean;
}

export interface GhostCell {
  slot_id: number;
  date: string;
  subject_id: number;
  subject_name: string;
  period: SkeletonPeriod | null;
  position: number;
  is_routine: boolean;
  book_id: number | null;
  book_name: string | null;
  label: string | null;
  routine_mode: RoutineMode | null;
  routine_scope?: RoutineScope | null;
  second_book_id?: number | null;
  second_book_name?: string | null;
  /** 1. kaynakta konu bitti: koç 2. kaynak / sıradaki konu arasında seçer */
  source_choice?: boolean;
  is_anchor: boolean;
  chips: GhostChip[];
}

export interface GhostsResponse {
  has_skeleton: boolean;
  days: { date: string; ghosts: GhostCell[] }[];
}

export interface RoutinePreviewTask {
  date: string;
  subject_name: string;
  title: string;
  planned: number;
  is_activity: boolean;
  /** Günlük rutin adedi olağandışı (ROUTINE_WARN_COUNT üstü) */
  too_many: boolean;
  items: { book_name: string | null; section_label: string | null; count: number }[];
}

export interface GhostAcceptResult {
  task_ids: number[];
  created: number;
  preview?: RoutinePreviewTask[];
}

/** Bu adedin üstündeki günlük rutin olağandışı sayılır (backend ile aynı). */
export const ROUTINE_WARN_COUNT = 6;

export interface GhostAcceptanceReport {
  actions: number;
  accepted: number;
  other: number;
  dismissed: number;
  acceptance_pct: number | null;
  by_rank: Record<string, number>;
  by_kind: Record<string, number>;
}

export const skeletonKeys = {
  acceptance: (days: number) => ["teacher", "me", "skeleton-acceptance", days] as const,
  skeleton: (studentId: number, skeletonId?: number | null) =>
    ["teacher", "me", "students", String(studentId), "skeleton", "one", skeletonId ?? "current"] as const,
  ghosts: (studentId: number, start: string, end: string) =>
    ["teacher", "me", "students", String(studentId), "skeleton", "ghosts", start, end] as const,
};

const base = (sid: number) => `/api/v2/teacher/students/${sid}/skeleton`;

export function getSkeleton(studentId: number, skeletonId?: number | null): Promise<SkeletonResponse> {
  const q = skeletonId ? `?skeleton_id=${skeletonId}` : "";
  return api<SkeletonResponse>(`${base(studentId)}${q}`);
}

export function getGhosts(studentId: number, start: string, end: string): Promise<GhostsResponse> {
  const q = new URLSearchParams({ start, end });
  return api<GhostsResponse>(`${base(studentId)}/ghosts?${q.toString()}`);
}

/** Koçun tüm öğrencilerindeki hayalet eylemleri (F1c başarı ölçüsü). */
export function getSkeletonAcceptance(days = 30): Promise<GhostAcceptanceReport> {
  return api<GhostAcceptanceReport>(`/api/v2/teacher/skeleton/acceptance?days=${days}`);
}

function showErr(e: unknown, title: string) {
  toast.error(title, { description: e instanceof ApiError ? e.message : "Sunucu hatası." });
}

function showWarnings(res: { warnings?: string[] }, title: string) {
  const w = res.warnings ?? [];
  if (w.length === 0) toast.success(title);
  else toast.warning(title, { description: w.join(" · ") });
}

export function useSaveSkeleton(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SkeletonResponse>,
    ApiError,
    {
      skeleton_id?: number | null;
      name?: string | null;
      slots: SkeletonSlotIn[];
      day_capacity?: Record<string, number | null> | null;
    }
  >({
    mutationFn: (body) =>
      api(base(studentId), { method: "POST", body: JSON.stringify(body) }),
    onError: (e) => showErr(e, "İskelet kaydedilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("İskelet kaydedildi");
    },
  });
}

export function useSkeletonFromWeek(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SkeletonResponse>,
    ApiError,
    {
      start: string;
      end: string;
      mode?: "replace" | "new";
      skeleton_id?: number | null;
      name?: string | null;
    }
  >({
    mutationFn: (body) =>
      api(`${base(studentId)}/from-week`, { method: "POST", body: JSON.stringify(body) }),
    onError: (e) => showErr(e, "Bu hafta iskelete çevrilemedi"),
    onSuccess: (res, vars) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(vars.mode === "new" ? "Yeni dönem başladı" : "Bu hafta iskelet yapıldı", {
        description: `${res.data.name ?? ""} · ${res.data.slots.length} satır — düzenleyebilirsin.`,
      });
    },
  });
}

export function useDeleteSkeleton(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<SkeletonResponse>, ApiError, { skeleton_id?: number | null }>({
    mutationFn: (body) =>
      api(`${base(studentId)}/delete`, { method: "POST", body: JSON.stringify(body ?? {}) }),
    onError: (e) => showErr(e, "Dönem silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Dönem silindi");
    },
  });
}

/** Yeni dönem: boş ya da başka bir dönemin kopyası. */
export function useCreatePeriod(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SkeletonResponse>,
    ApiError,
    { valid_from: string; name?: string | null; copy_from_id?: number | null }
  >({
    mutationFn: (body) =>
      api(`${base(studentId)}/periods`, { method: "POST", body: JSON.stringify(body) }),
    onError: (e) => showErr(e, "Dönem açılamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Yeni dönem açıldı", { description: res.data.name ?? undefined });
    },
  });
}

/** Dönem adı / başlangıcı. */
export function useUpdatePeriod(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SkeletonResponse>,
    ApiError,
    { skeleton_id: number; name?: string | null; valid_from?: string | null; clear_start?: boolean }
  >({
    mutationFn: ({ skeleton_id, ...body }) =>
      api(`${base(studentId)}/periods/${skeleton_id}`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => showErr(e, "Dönem güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Dönem güncellendi");
    },
  });
}

/** "01.07.2026" biçimi (dönem şeridi). */
export function fmtDay(iso: string | null): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

export function periodRange(p: { valid_from: string | null; valid_until: string | null }): string {
  const a = p.valid_from ? fmtDay(p.valid_from) : "baştan";
  const b = p.valid_until ? fmtDay(p.valid_until) : "süresiz";
  return `${a} – ${b}`;
}

export interface GhostAcceptBody {
  slot_id: number;
  date: string;
  section_id?: number | null;
  count?: number;
  items?: { section_id: number; count: number }[] | null;
  as_activity?: boolean;
  chip_rank?: number | null;
  chip_kind?: string | null;
  chip_count?: number | null;
}

export function useAcceptGhost(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<GhostAcceptResult>, ApiError, GhostAcceptBody>({
    mutationFn: (body) =>
      api(`${base(studentId)}/ghosts/accept`, { method: "POST", body: JSON.stringify(body) }),
    onError: (e) => showErr(e, "Görev yazılamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      showWarnings(res, "Görev eklendi");
    },
  });
}

export function useAcceptRoutine(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<GhostAcceptResult>,
    ApiError,
    { date: string; end?: string }
  >({
    mutationFn: (body) =>
      api(`${base(studentId)}/ghosts/accept-routine`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => showErr(e, "Rutinler yazılamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      showWarnings(res, `${res.data.created} rutin görev eklendi`);
    },
  });
}

/** Rutin yazma ÖNİZLEMESİ — sunucu yazma döngüsünü çalıştırıp geri alır. */
export function useRoutinePreview(studentId: number) {
  // Önizleme yan etkisiz (sunucuda işlem geri alınır) → invalidate YOK.
  // eslint-disable-next-line lgs/missing-invalidate -- preview yan etkisiz
  return useMutation<
    MutationResponse<GhostAcceptResult>,
    ApiError,
    { date: string; end?: string }
  >({
    mutationFn: (body) =>
      api(`${base(studentId)}/ghosts/accept-routine`, {
        method: "POST",
        body: JSON.stringify({ ...body, dry_run: true }),
      }),
    onError: (e) => showErr(e, "Önizleme alınamadı"),
  });
}

export function useGhostAction(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<GhostAcceptResult>,
    ApiError,
    { slot_id: number; date: string; action: "dismissed" | "restore" }
  >({
    mutationFn: (body) =>
      api(`${base(studentId)}/ghosts/action`, { method: "POST", body: JSON.stringify(body) }),
    onError: (e) => showErr(e, "İşlem yapılamadı"),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
  });
}

export const WEEKDAY_LABELS = [
  "Pazartesi",
  "Salı",
  "Çarşamba",
  "Perşembe",
  "Cuma",
  "Cumartesi",
  "Pazar",
];

export const SKELETON_PERIOD_LABELS: Record<string, string> = {
  morning: "Sabah",
  noon: "Öğle",
  evening: "Akşam",
};

// ---------------------------------------------------------------- konuyu yay (F2-3)

export interface SpreadItem {
  section_id: number;
  section_label: string;
  book_id: number;
  book_name: string;
  count: number;
}

export interface SpreadDay {
  date: string;
  capacity: number | null;
  planned: number;
  anchor_reserve: number;
  free: number | null;
  items: SpreadItem[];
}

export interface SpreadSkip {
  date: string;
  capacity: number | null;
  planned: number;
  anchor_reserve: number;
  reason: string;
}

export interface SpreadPreview {
  topic_id: number | null;
  section_id: number | null;
  subject_id: number | null;
  per_day: number;
  start: string;
  window_end: string | null;
  stop_reason: string | null;
  total_remaining: number;
  leftover: number;
  days: SpreadDay[];
  skipped: SpreadSkip[];
}

export interface SpreadParams {
  topicId: number | null;
  sectionId: number | null;
  start: string;
  perDay: number;
  /** Önizleme başlığı ("Kuvvet ve Hareket") */
  title: string;
}

export function getSpreadPreview(
  studentId: number,
  p: { topicId: number | null; sectionId: number | null; start: string; perDay: number },
): Promise<SpreadPreview> {
  const q = new URLSearchParams({ start: p.start, per_day: String(p.perDay) });
  if (p.topicId) q.set("topic_id", String(p.topicId));
  else if (p.sectionId) q.set("section_id", String(p.sectionId));
  return api<SpreadPreview>(`/api/v2/teacher/students/${studentId}/topic-spread?${q.toString()}`);
}

export function useApplySpread(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<GhostAcceptResult>,
    ApiError,
    { days: { date: string; items: { section_id: number; count: number }[] }[] }
  >({
    mutationFn: (body) =>
      api(`/api/v2/teacher/students/${studentId}/topic-spread`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => showErr(e, "Yayılamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      showWarnings(res, `${res.data.created} görev yazıldı`);
    },
  });
}

/** "Cuma 02.10" */
export function dayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  const wd = (d.getDay() + 6) % 7;
  const [, m, dd] = iso.split("-");
  return `${WEEKDAY_LABELS[wd]} ${dd}.${m}`;
}

/** ISO tarihe gün ekle ("YYYY-MM-DD"). */
export function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

// --- İskeleti başka öğrencilere kopyala (2026-09-27) ---------------------------

export interface SkeletonCopyBookRef {
  id: number;
  name: string;
}

export interface SkeletonCopyCandidate {
  student_id: number;
  full_name: string;
  grade_label: string;
  class_group: string | null;
  period_count: number;
  period_starts: (string | null)[];
  current_period_name: string | null;
  current_slot_count: number;
  missing_books: SkeletonCopyBookRef[];
}

export interface SkeletonCopyCandidatesResponse {
  source_skeleton_id: number;
  source_name: string;
  source_valid_from: string | null;
  source_slot_count: number;
  source_books: SkeletonCopyBookRef[];
  candidates: SkeletonCopyCandidate[];
}

export interface SkeletonCopyResult {
  students: {
    student_id: number;
    full_name: string;
    skeleton_id: number;
    slot_count: number;
    books_assigned: number;
    slots_without_book: number;
  }[];
  skipped_invalid_ids: number[];
}

export const skeletonCopyKey = (studentId: number, skeletonId: number) =>
  ["teacher", "me", "students", String(studentId), "skeleton", "copy-candidates", skeletonId] as const;

export function getSkeletonCopyCandidates(
  studentId: number,
  skeletonId: number,
): Promise<SkeletonCopyCandidatesResponse> {
  return api(`${base(studentId)}/copy-candidates?skeleton_id=${skeletonId}`);
}

export function useCopySkeleton(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SkeletonCopyResult>,
    ApiError,
    {
      skeleton_id: number;
      target_ids: number[];
      mode: "new" | "replace";
      valid_from?: string | null;
      name?: string | null;
      assign_missing_books: boolean;
    }
  >({
    mutationFn: (body) =>
      api(`${base(studentId)}/copy`, { method: "POST", body: JSON.stringify(body) }),
    onError: (e) => showErr(e, "İskelet kopyalanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const n = res.data.students.length;
      const books = res.data.students.reduce((a, s) => a + s.books_assigned, 0);
      toast.success(`İskelet ${n} öğrenciye kopyalandı`, {
        description: books > 0 ? `${books} eksik kitap öğrencilere atandı.` : undefined,
      });
    },
  });
}
