"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  NotifyParentsBody,
  NotifyParentsResult,
  PublishDayBody,
  PublishResult,
  PublishWeekBody,
  TasksReorderBody,
  TasksReorderResult,
  TeacherWeekNote,
  WeekNoteAddBody,
  WeekNoteToggleResult,
} from "@/lib/types/teacher";
import type { DeletedRef } from "@/lib/types/library";

/**
 * Haftalık plan mutation hook'ları (Paket 3.5a.2).
 *
 * Notlar:
 * - week-notes: add / delete / toggle
 * - publish-day / publish-week → taslakları öğrenci paneline indirir
 * - tasks/reorder → drag-drop sıralama
 * - notify-parents → veliye program duyurusu
 */

function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.detail?.message ?? fallback;
  return fallback;
}

function errorCode(e: unknown): string | undefined {
  if (e instanceof ApiError) return e.detail?.code;
  return undefined;
}

function errorTitle(e: unknown, fallback: string): string {
  switch (errorCode(e)) {
    case "student_not_found":
      return "Öğrenci bulunamadı";
    case "note_not_found":
      return "Not bulunamadı";
    case "body_required":
      return "Not metni boş olamaz";
    case "invalid_date":
    case "invalid_week_start":
    case "invalid_target_date":
      return "Tarih formatı hatalı";
    case "empty_task_ids":
      return "Sıralanacak görev yok";
    default:
      return fallback;
  }
}

function showError(e: unknown, fallbackTitle: string) {
  toast.error(errorTitle(e, fallbackTitle), {
    description: errorMessage(e, "Sunucu hatası."),
  });
}

// =============================================================================
// Week notes
// =============================================================================

export function useAddWeekNote(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TeacherWeekNote>,
    ApiError,
    { body: WeekNoteAddBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<TeacherWeekNote>>(
        `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/week-notes`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Not eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Not eklendi");
    },
  });
}

export function useDeleteWeekNote(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<DeletedRef>,
    ApiError,
    { noteId: number }
  >({
    mutationFn: ({ noteId }) =>
      api<MutationResponse<DeletedRef>>(
        `/api/v2/teacher/students/${encodeURIComponent(
          String(studentId),
        )}/week-notes/${encodeURIComponent(String(noteId))}`,
        { method: "DELETE" },
      ),
    onError: (e) => showError(e, "Not silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Not silindi");
    },
  });
}

export function useToggleWeekNote(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<WeekNoteToggleResult>,
    ApiError,
    { noteId: number }
  >({
    mutationFn: ({ noteId }) =>
      api<MutationResponse<WeekNoteToggleResult>>(
        `/api/v2/teacher/students/${encodeURIComponent(
          String(studentId),
        )}/week-notes/${encodeURIComponent(String(noteId))}/toggle`,
        { method: "POST", body: "{}" },
      ),
    onError: (e) => showError(e, "Not güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
  });
}

// =============================================================================
// Publish day / week
// =============================================================================

export function usePublishDay(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<PublishResult>,
    ApiError,
    { body: PublishDayBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<PublishResult>>(
        `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/publish-day`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Yayınlama başarısız"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        res.data.published_count > 0
          ? `${res.data.published_count} görev yayınlandı`
          : "Yayınlanacak taslak yoktu",
      );
    },
  });
}

export function usePublishWeek(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<PublishResult>,
    ApiError,
    { body: PublishWeekBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<PublishResult>>(
        `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/publish-week`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Hafta yayınlanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        res.data.published_count > 0
          ? `${res.data.published_count} taslak görev yayınlandı`
          : "Yayınlanacak taslak yoktu",
      );
    },
  });
}

// =============================================================================
// Tasks reorder
// =============================================================================

export function useReorderTasks(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<TasksReorderResult>,
    ApiError,
    { body: TasksReorderBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<TasksReorderResult>>(
        `/api/v2/teacher/students/${encodeURIComponent(String(studentId))}/tasks/reorder`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Sıralama kaydedilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
  });
}

// =============================================================================
// Notify parents
// =============================================================================

export function useNotifyParents(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<NotifyParentsResult>,
    ApiError,
    { body: NotifyParentsBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<NotifyParentsResult>>(
        `/api/v2/teacher/students/${encodeURIComponent(
          String(studentId),
        )}/program/notify-parents`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Veliye duyuru gönderilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      if (res.data.no_tasks) {
        toast.info(res.data.message);
      } else if (res.data.fired === 0) {
        toast.warning(res.data.message);
      } else {
        toast.success(res.data.message);
      }
    },
  });
}
