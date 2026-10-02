"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  AgendaQueueResponse,
  ExamShareResult,
  ExamTargetBody,
  ExamTargetsResponse,
} from "@/lib/types/exam-progress";

function errMsg(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.message || fallback;
  return fallback;
}

export function useSetExamTarget(studentId: number) {
  const qc = useQueryClient();
  return useMutation<ExamTargetsResponse, ApiError, ExamTargetBody>({
    mutationFn: (body) =>
      api<ExamTargetsResponse>(`/api/v2/teacher/students/${studentId}/exam-targets`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res, body) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(body.target_net == null ? "Hedef kaldırıldı" : "Hedef net kaydedildi");
    },
    onError: (e) => toast.error(errMsg(e, "Hedef kaydedilemedi")),
  });
}

export type AgendaAddItem = {
  text: string;
  key?: string | null;
  exam_id?: number | null;
  source?: string;
};

export function useAddAgendaItems(studentId: number) {
  const qc = useQueryClient();
  return useMutation<AgendaQueueResponse, ApiError, AgendaAddItem[]>({
    mutationFn: (items) =>
      api<AgendaQueueResponse>(`/api/v2/teacher/students/${studentId}/agenda-queue`, {
        method: "POST",
        body: JSON.stringify({ items }),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        res.added > 0
          ? `${res.added} madde sıradaki seansın gündemine eklendi`
          : "Bu maddeler zaten seans gündeminde",
        { description: "Yeni seans açarken işaretli gelir (Seanslar sekmesi)." },
      );
    },
    onError: (e) => toast.error(errMsg(e, "Seans gündemine eklenemedi")),
  });
}

export function useRemoveAgendaItems(studentId: number) {
  const qc = useQueryClient();
  return useMutation<AgendaQueueResponse, ApiError, { ids: string[]; silent?: boolean }>({
    mutationFn: ({ ids }) =>
      api<AgendaQueueResponse>(`/api/v2/teacher/students/${studentId}/agenda-queue/remove`, {
        method: "POST",
        body: JSON.stringify({ ids }),
      }),
    onSuccess: (res, v) => {
      applyInvalidate(qc, res.invalidate);
      if (!v.silent) toast.success("Gündemden çıkarıldı");
    },
    onError: (e, v) => {
      if (!v.silent) toast.error(errMsg(e, "Çıkarılamadı"));
    },
  });
}

export function useShareExamWithStudent() {
  const qc = useQueryClient();
  return useMutation<ExamShareResult, ApiError, { examId: number; note: string; notify: boolean }>({
    mutationFn: ({ examId, note, notify }) =>
      api<ExamShareResult>(`/api/v2/teacher/exams/${examId}/share-student`, {
        method: "POST",
        body: JSON.stringify({ note, notify }),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Öğrenciyle paylaşıldı", {
        description: res.notified
          ? "Öğrenci Denemelerim ekranında görür; uygulamasına bildirim gitti."
          : "Öğrenci Denemelerim ekranında görür.",
      });
    },
    onError: (e) => toast.error(errMsg(e, "Paylaşılamadı")),
  });
}

export function useUnshareExam() {
  const qc = useQueryClient();
  return useMutation<ExamShareResult, ApiError, number>({
    mutationFn: (examId) =>
      api<ExamShareResult>(`/api/v2/teacher/exams/${examId}/unshare-student`, { method: "POST" }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Paylaşım geri alındı");
    },
    onError: (e) => toast.error(errMsg(e, "Geri alınamadı")),
  });
}
