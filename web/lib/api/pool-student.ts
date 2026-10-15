/**
 * Haftalık görev havuzu — ÖĞRENCİ web istemcisi (mobil `lib/pool.ts` ile aynı sözleşme).
 * Backend: app/routes/api_v2/pool_student.py. Kap = o güne mevcut görev → işaretleme
 * Bugün sayfasındaki olağan akışla (D/Y/B).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";

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
  subject_name?: string | null;
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
  projection: {
    date: string;
    units: number;
    lessons?: string[];
    subjects?: { subject_id: number | null; name: string; units: number }[];
  }[];
  lesson_today: string[];
  subjects: { id: number; name: string; group?: "okul" | "sinav"; is_ayt?: boolean }[];
  /** K41/K46/K48: yönlendirme cümleleri — kırmızı yok, yargı yok. */
  hints: { code: string; title: string; note: string }[];
  /** K60: önceki dönemler (öğrenci görür; yargı yok). */
  previous: { id: number; opened_on: string; closed_on: string | null; status: string; status_label: string; total_units: number; done_units: number; pct: number }[];
  /** K61: ara (tatil) — açık dönem yok, son dönem ara ile kapandı. */
  on_break: { period_id: number; since: string; note: string | null } | null;
  units: PoolUnit[];
  today: string;
  /** Şube ders programı girilmiş mi — dağılım önerisi buna göre */
  lesson_days_set?: boolean;
}

export const UNIT_LABELS: Record<PoolUnit, string> = {
  test: "test", soru: "soru", sayfa: "sayfa", deneme: "deneme", etkinlik: "etkinlik",
};

export const studentPoolKey = ["student", "me", "pool"] as const;

export function getStudentPool(): Promise<StudentPoolResponse> {
  return api("/api/v2/student/pool");
}

function errMsg(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.detail.message || fallback : fallback;
}

function usePoolMutation<TBody>(path: (b: TBody) => string, ok: string | null, fail: string) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentPoolResponse>, ApiError, TBody>({
    mutationFn: (body) => api(path(body), { method: "POST", body: JSON.stringify(body ?? {}) }),
    onError: (e) => toast.error(fail, { description: errMsg(e, "Tekrar dene.") }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.setQueryData(studentPoolKey, res.data);
      if (ok) toast.success(ok);
    },
  });
}

export function useCupAdd() {
  return usePoolMutation<{ item_id: number; count?: number | null }>(
    () => "/api/v2/student/pool/cup", "Kabına eklendi", "Kaba alınamadı",
  );
}

export function useCupReturn() {
  return usePoolMutation<{ task_id: number }>(
    (b) => `/api/v2/student/pool/cup/${b.task_id}/return`, "Havuza döndü", "Geri alınamadı",
  );
}

/** Bugünkü kap görevinin sayısını öğrenci kendisi düzeltir (5 aldı, 3 yapacak) — rehbere talep değil. */
export function useCupResize() {
  return usePoolMutation<{ task_id: number; count: number }>(
    (b) => `/api/v2/student/pool/cup/${b.task_id}/resize`, "Bugünkü sayı güncellendi", "Sayı değiştirilemedi",
  );
}

export function useAddStudentPoolItem() {
  return usePoolMutation<{ subject_id: number; label: string | null; quantity: number | null; unit: PoolUnit; teacher_homework?: boolean }>(
    () => "/api/v2/student/pool/items", "Havuza eklendi — rehberin seansta onaylayacak", "Eklenemedi",
  );
}


// ---------------------------------------------------------------- dönem penceresi (geçmiş dönem içi, 2026-10-13)

export type { PoolPeriodDetailResponse } from "@/lib/api/pool";

export const studentPoolPeriodKey = (periodId: number) => ["student", "me", "pool", "period", String(periodId)] as const;

export function getStudentPoolPeriod(periodId: number): Promise<import("@/lib/api/pool").PoolPeriodDetailResponse> {
  return api(`/api/v2/student/pool/periods/${periodId}`);
}
