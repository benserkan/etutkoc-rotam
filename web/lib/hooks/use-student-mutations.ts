"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import { studentKeys } from "@/lib/api/student";
import type {
  FocusSession,
  GoalItem,
  ReviewCardItem,
  StudentDayResponse,
  StudentRequestItem,
  StudentTask,
} from "@/lib/types/student";

/**
 * Öğrenci paneli mutation hook'ları.
 *
 * Sözleşme:
 *   - Her mutation, başarıda backend'in MutationResponse.invalidate listesini
 *     applyInvalidate ile uygular (R-006 OOB swap karşılığı).
 *   - Tikleme akışları AGRESİF optimistic: kullanıcı tıkladığı anda UI hedef
 *     state'i gösterir. 422 / 4xx hatasında onError önceki snapshot'a rollback.
 *   - 422 RESERVE_OVER_CAPACITY mesajı toast'a iletilir; UI mantığı yine doğru
 *     state'e döner.
 */

// =============================================================================
// Yardımcılar
// =============================================================================

/** Day cache'i içinde tek görevi update et — array içinde sırasını koru. */
function patchTaskInDayCache(
  qc: ReturnType<typeof useQueryClient>,
  dateIso: string,
  taskId: number,
  patch: (t: StudentTask) => StudentTask,
): StudentDayResponse | undefined {
  const key = studentKeys.day(dateIso);
  const prev = qc.getQueryData<StudentDayResponse>(key);
  if (!prev) return undefined;
  const next: StudentDayResponse = {
    ...prev,
    tasks: prev.tasks.map((t) => (t.id === taskId ? patch(t) : t)),
  };
  // Summary'yi de yeniden hesapla — UI üst banner için
  const planned = next.tasks.reduce((s, t) => s + t.planned_count, 0);
  const completed = next.tasks.reduce((s, t) => s + t.completed_count, 0);
  next.summary = {
    ...next.summary,
    planned_count: planned,
    completed_count: completed,
    pct: planned > 0 ? completed / planned : 0,
  };
  qc.setQueryData(key, next);
  return prev;
}

/** ApiError mesajından kullanıcıya gösterilecek metin çek. */
function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.detail?.message ?? fallback;
  return fallback;
}

interface MutationContext {
  previous: StudentDayResponse | undefined;
}

// =============================================================================
// COMPLETE TASK
// =============================================================================

interface TaskMutationParams {
  task: StudentTask;
}

export function useCompleteTask(dateIso: string) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentTask>, ApiError, TaskMutationParams, MutationContext>({
    mutationKey: ["student", "mutate-task", dateIso, "complete"],
    mutationFn: ({ task }) =>
      api<MutationResponse<StudentTask>>(
        `/api/v2/student/tasks/${task.id}/complete`,
        { method: "POST" },
      ),
    onMutate: async ({ task }) => {
      await qc.cancelQueries({ queryKey: studentKeys.day(dateIso) });
      const previous = patchTaskInDayCache(qc, dateIso, task.id, (t) => ({
        ...t,
        status: "completed",
        completed_count: t.planned_count,
        pct: 1,
        items: t.items.map((it) => ({
          ...it,
          completed: it.planned,
          is_full: it.planned > 0,
        })),
      }));
      return { previous };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(studentKeys.day(dateIso), ctx.previous);
      toast.error("Tamamlanamadı", { description: errorMessage(err, "Sunucu hatası.") });
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
  });
}

// =============================================================================
// UNCOMPLETE TASK
// =============================================================================

export function useUncompleteTask(dateIso: string) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentTask>, ApiError, TaskMutationParams, MutationContext>({
    mutationKey: ["student", "mutate-task", dateIso, "uncomplete"],
    mutationFn: ({ task }) =>
      api<MutationResponse<StudentTask>>(
        `/api/v2/student/tasks/${task.id}/uncomplete`,
        { method: "POST" },
      ),
    onMutate: async ({ task }) => {
      await qc.cancelQueries({ queryKey: studentKeys.day(dateIso) });
      const previous = patchTaskInDayCache(qc, dateIso, task.id, (t) => ({
        ...t,
        status: "pending",
        completed_count: 0,
        pct: 0,
        items: t.items.map((it) => ({ ...it, completed: 0, is_full: false })),
      }));
      return { previous };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(studentKeys.day(dateIso), ctx.previous);
      toast.error("Geri alınamadı", { description: errorMessage(err, "Sunucu hatası.") });
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
  });
}

// =============================================================================
// SET ITEM COMPLETED (kısmi tikleme)
//
// Debounce: hızlı `+/-` tıklamasında her tık tek API isteği değil, son değer
// 300ms sonra gönderilir. Optimistic update her tık'ta anında çalışır.
// =============================================================================

interface SetItemParams {
  task: StudentTask;
  itemId: number;
  completed: number;
}

export function useSetItemCompleted(dateIso: string) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentTask>, ApiError, SetItemParams, MutationContext>({
    mutationKey: ["student", "mutate-task", dateIso, "set-item"],
    mutationFn: ({ task, itemId, completed }) =>
      api<MutationResponse<StudentTask>>(
        `/api/v2/student/tasks/${task.id}/items/${itemId}/set-completed`,
        { method: "POST", body: JSON.stringify({ completed }) },
      ),
    onMutate: async ({ task, itemId, completed }) => {
      await qc.cancelQueries({ queryKey: studentKeys.day(dateIso) });
      const previous = patchTaskInDayCache(qc, dateIso, task.id, (t) => {
        const items = t.items.map((it) =>
          it.id === itemId
            ? {
                ...it,
                completed: Math.max(0, Math.min(completed, it.planned)),
                is_full: completed >= it.planned && it.planned > 0,
              }
            : it,
        );
        const planned = items.reduce((s, it) => s + it.planned, 0);
        const done = items.reduce((s, it) => s + it.completed, 0);
        const status: StudentTask["status"] =
          done === 0 ? "pending" : done >= planned ? "completed" : "partial";
        return {
          ...t,
          items,
          completed_count: done,
          status,
          pct: planned > 0 ? done / planned : 0,
        };
      });
      return { previous };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(studentKeys.day(dateIso), ctx.previous);
      toast.error("Güncellenemedi", { description: errorMessage(err, "Sunucu hatası.") });
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
  });
}

/** Hook + debounce — gerçek API çağrısı 300ms sonra fakat optimistic anında. */
export function useDebouncedSetItem(dateIso: string, delayMs = 300) {
  const mut = useSetItemCompleted(dateIso);
  const qc = useQueryClient();
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestRef = React.useRef<SetItemParams | null>(null);

  // Optimistic update anında uygula (her +/- tıklamasında):
  const apply = React.useCallback(
    (params: SetItemParams) => {
      patchTaskInDayCache(qc, dateIso, params.task.id, (t) => {
        const items = t.items.map((it) =>
          it.id === params.itemId
            ? {
                ...it,
                completed: Math.max(0, Math.min(params.completed, it.planned)),
                is_full: params.completed >= it.planned && it.planned > 0,
              }
            : it,
        );
        const planned = items.reduce((s, it) => s + it.planned, 0);
        const done = items.reduce((s, it) => s + it.completed, 0);
        const status: StudentTask["status"] =
          done === 0 ? "pending" : done >= planned ? "completed" : "partial";
        return {
          ...t,
          items,
          completed_count: done,
          status,
          pct: planned > 0 ? done / planned : 0,
        };
      });
      latestRef.current = params;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        if (latestRef.current) mut.mutate(latestRef.current);
      }, delayMs);
    },
    [qc, dateIso, mut, delayMs],
  );

  React.useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return { apply, mutation: mut };
}

// =============================================================================
// REQUEST mutations (change / replace / remove / question / add / withdraw)
// =============================================================================

interface ChangeBody {
  task: StudentTask;
  proposed_count: number;
  message?: string;
}

export function useRequestChange(dateIso: string) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentRequestItem>, ApiError, ChangeBody>({
    mutationKey: ["student", "mutate-request", dateIso, "change"],
    mutationFn: ({ task, proposed_count, message }) =>
      api<MutationResponse<StudentRequestItem>>(
        `/api/v2/student/tasks/${task.id}/requests/change`,
        { method: "POST", body: JSON.stringify({ proposed_count, message }) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Talebin koçuna gönderildi");
    },
    onError: (err) => {
      toast.error("Talep gönderilemedi", { description: errorMessage(err, "Sunucu hatası.") });
    },
  });
}

interface ReplaceBody {
  task: StudentTask;
  new_book_id: number;
  new_section_id: number;
  new_count: number;
  message?: string;
}

export function useRequestReplace(dateIso: string) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentRequestItem>, ApiError, ReplaceBody>({
    mutationKey: ["student", "mutate-request", dateIso, "replace"],
    mutationFn: ({ task, ...body }) =>
      api<MutationResponse<StudentRequestItem>>(
        `/api/v2/student/tasks/${task.id}/requests/replace`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kaynak değişikliği talebin koçuna gönderildi");
    },
    onError: (err) => {
      toast.error("Talep gönderilemedi", { description: errorMessage(err, "Sunucu hatası.") });
    },
  });
}

interface RemoveBody {
  task: StudentTask;
  message?: string;
}

export function useRequestRemove(dateIso: string) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentRequestItem>, ApiError, RemoveBody>({
    mutationKey: ["student", "mutate-request", dateIso, "remove"],
    mutationFn: ({ task, message }) =>
      api<MutationResponse<StudentRequestItem>>(
        `/api/v2/student/tasks/${task.id}/requests/remove`,
        { method: "POST", body: JSON.stringify({ message }) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Görev çıkar talebin gönderildi");
    },
    onError: (err) => {
      toast.error("Talep gönderilemedi", { description: errorMessage(err, "Sunucu hatası.") });
    },
  });
}

interface QuestionBody {
  task: StudentTask;
  message: string;
}

export function useRequestQuestion(dateIso: string) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentRequestItem>, ApiError, QuestionBody>({
    mutationKey: ["student", "mutate-request", dateIso, "question"],
    mutationFn: ({ task, message }) =>
      api<MutationResponse<StudentRequestItem>>(
        `/api/v2/student/tasks/${task.id}/requests/question`,
        { method: "POST", body: JSON.stringify({ message }) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Sorun koçuna iletildi");
    },
    onError: (err) => {
      toast.error("Soru gönderilemedi", { description: errorMessage(err, "Sunucu hatası.") });
    },
  });
}

interface AddBody {
  target_date: string;
  book_id: number;
  section_id: number;
  proposed_count: number;
  message?: string;
}

export function useRequestAdd() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentRequestItem>, ApiError, AddBody>({
    mutationKey: ["student", "mutate-request", "add"],
    mutationFn: ({ target_date, ...body }) =>
      api<MutationResponse<StudentRequestItem>>(
        `/api/v2/student/days/${target_date}/requests/add`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Yeni görev önerisi koçuna gönderildi");
    },
    onError: (err) => {
      toast.error("Talep gönderilemedi", { description: errorMessage(err, "Sunucu hatası.") });
    },
  });
}

export function useWithdrawRequest() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<StudentRequestItem>, ApiError, { requestId: number }>({
    mutationKey: ["student", "mutate-request", "withdraw"],
    mutationFn: ({ requestId }) =>
      api<MutationResponse<StudentRequestItem>>(
        `/api/v2/student/requests/${requestId}/withdraw`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Talep geri çekildi");
    },
    onError: (err) => {
      toast.error("Geri çekilemedi", { description: errorMessage(err, "Sunucu hatası.") });
    },
  });
}

// =============================================================================
// Focus (Pomodoro) mutations — Paket 7
// =============================================================================

interface FocusStartBody {
  planned_minutes: number;
  kind: "work" | "short_break" | "long_break";
  label?: string | null;
}

export function useFocusStart() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<FocusSession>, ApiError, FocusStartBody>({
    mutationKey: ["student", "mutate-focus", "start"],
    mutationFn: (body) =>
      api<MutationResponse<FocusSession>>("/api/v2/student/focus/start", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Odak seansı başladı");
    },
    onError: (err) => {
      toast.error("Başlatılamadı", { description: errorMessage(err, "Sunucu hatası.") });
    },
  });
}

interface FocusStopBody {
  sessionId: number;
  actual_minutes?: number | null;
  interrupted?: boolean;
}

export function useFocusStop() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<FocusSession>, ApiError, FocusStopBody>({
    mutationKey: ["student", "mutate-focus", "stop"],
    mutationFn: ({ sessionId, ...body }) =>
      api<MutationResponse<FocusSession>>(
        `/api/v2/student/focus/${sessionId}/stop`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Seans bitti");
    },
    onError: (err) => {
      toast.error("Bitirilemedi", { description: errorMessage(err, "Sunucu hatası.") });
    },
  });
}

export function useFocusCancel() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<FocusSession>, ApiError, { sessionId: number }>({
    mutationKey: ["student", "mutate-focus", "cancel"],
    mutationFn: ({ sessionId }) =>
      api<MutationResponse<FocusSession>>(
        `/api/v2/student/focus/${sessionId}/cancel`,
        { method: "POST" },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Seans yarıda kaldı");
    },
    onError: (err) => {
      toast.error("İptal edilemedi", { description: errorMessage(err, "Sunucu hatası.") });
    },
  });
}

// =============================================================================
// Review (FSRS) mutation — Paket 7
// =============================================================================

interface ReviewRateBody {
  cardId: number;
  rating: 1 | 2 | 3 | 4;
}

export function useReviewRate() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<ReviewCardItem>, ApiError, ReviewRateBody>({
    mutationKey: ["student", "mutate-review", "rate"],
    mutationFn: ({ cardId, rating }) =>
      api<MutationResponse<ReviewCardItem>>(
        `/api/v2/student/review/${cardId}/rate`,
        { method: "POST", body: JSON.stringify({ rating }) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
    onError: (err) => {
      toast.error("Değerlendirme kaydedilemedi", {
        description: errorMessage(err, "Sunucu hatası."),
      });
    },
  });
}

// =============================================================================
// Goals mutations — Paket 7
// =============================================================================

interface GoalCreateBody {
  title: string;
  kind: "weekly" | "daily" | "custom" | "topic";
  description?: string | null;
  target_value?: number | null;
  current_value?: number | null;
  unit?: string | null;
  target_date?: string | null;
}

export function useGoalCreate() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<GoalItem>, ApiError, GoalCreateBody>({
    mutationKey: ["student", "mutate-goal", "create"],
    mutationFn: (body) =>
      api<MutationResponse<GoalItem>>("/api/v2/student/goals", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Hedef oluşturuldu");
    },
    onError: (err) => {
      toast.error("Hedef oluşturulamadı", {
        description: errorMessage(err, "Sunucu hatası."),
      });
    },
  });
}

interface GoalProgressBody {
  goalId: number;
  current_value: number;
}

export function useGoalProgress() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<GoalItem>, ApiError, GoalProgressBody>({
    mutationKey: ["student", "mutate-goal", "progress"],
    mutationFn: ({ goalId, current_value }) =>
      api<MutationResponse<GoalItem>>(
        `/api/v2/student/goals/${goalId}/progress`,
        { method: "POST", body: JSON.stringify({ current_value }) },
      ),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
    onError: (err) => {
      toast.error("Güncellenemedi", {
        description: errorMessage(err, "Sunucu hatası."),
      });
    },
  });
}

interface GoalToggleBody {
  goalId: number;
  achieved: boolean;
}

export function useGoalToggle() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<GoalItem>, ApiError, GoalToggleBody>({
    mutationKey: ["student", "mutate-goal", "toggle"],
    mutationFn: ({ goalId, achieved }) =>
      api<MutationResponse<GoalItem>>(
        `/api/v2/student/goals/${goalId}/toggle`,
        { method: "POST", body: JSON.stringify({ achieved }) },
      ),
    onSuccess: (res, vars) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(vars.achieved ? "Hedef tamamlandı 🎉" : "Hedef aktif edildi");
    },
    onError: (err) => {
      toast.error("Değiştirilemedi", {
        description: errorMessage(err, "Sunucu hatası."),
      });
    },
  });
}
