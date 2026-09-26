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
}

export interface SkeletonSlot extends SkeletonSlotIn {
  id: number;
  subject_name: string;
}

export interface SkeletonResponse {
  exists: boolean;
  name: string | null;
  source: string | null;
  slots: SkeletonSlot[];
  subjects: { id: number; name: string }[];
}

export interface ChipBadge {
  code: string;
  label: string;
  tone: string; // rose | amber | violet | emerald | slate | cyan …
}

export type ChipKind = "thread" | "next" | "new" | "weak";

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
}

export interface GhostCell {
  slot_id: number;
  date: string;
  subject_id: number;
  subject_name: string;
  period: SkeletonPeriod | null;
  position: number;
  is_routine: boolean;
  chips: GhostChip[];
}

export interface GhostsResponse {
  has_skeleton: boolean;
  days: { date: string; ghosts: GhostCell[] }[];
}

export interface GhostAcceptResult {
  task_ids: number[];
  created: number;
}

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
  skeleton: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "skeleton"] as const,
  ghosts: (studentId: number, start: string, end: string) =>
    ["teacher", "me", "students", String(studentId), "skeleton", "ghosts", start, end] as const,
};

const base = (sid: number) => `/api/v2/teacher/students/${sid}/skeleton`;

export function getSkeleton(studentId: number): Promise<SkeletonResponse> {
  return api<SkeletonResponse>(base(studentId));
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
    { name?: string | null; slots: SkeletonSlotIn[] }
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
  return useMutation<MutationResponse<SkeletonResponse>, ApiError, { start: string; end: string }>({
    mutationFn: (body) =>
      api(`${base(studentId)}/from-week`, { method: "POST", body: JSON.stringify(body) }),
    onError: (e) => showErr(e, "Bu hafta iskelete çevrilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Bu hafta iskelet yapıldı", {
        description: `${res.data.slots.length} satır — düzenleyebilirsin.`,
      });
    },
  });
}

export function useDeleteSkeleton(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<SkeletonResponse>, ApiError, void>({
    mutationFn: () => api(`${base(studentId)}/delete`, { method: "POST" }),
    onError: (e) => showErr(e, "İskelet silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("İskelet silindi");
    },
  });
}

export interface GhostAcceptBody {
  slot_id: number;
  date: string;
  section_id: number;
  count: number;
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
  return useMutation<MutationResponse<GhostAcceptResult>, ApiError, { date: string }>({
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
