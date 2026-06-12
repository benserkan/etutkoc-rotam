"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import { surveyKeys } from "@/lib/api/surveys";
import type {
  CareerSynthesisCacheResponse,
  StudentSurveySaveResult,
  SurveyAssignBody,
  SurveyAssignResult,
} from "@/lib/types/survey";

/**
 * Anket sistemi mutation hook'ları.
 * Hata kodları: survey_not_found / survey_already_assigned / survey_completed /
 *   assignment_not_found / student_not_found / role_required
 */

const ERROR_LABELS: Record<string, string> = {
  survey_not_found: "Anket bulunamadı.",
  survey_already_assigned:
    "Bu anket öğrencide zaten bekliyor — önce mevcut atama tamamlanmalı veya iptal edilmeli.",
  survey_completed: "Bu anket zaten tamamlandı.",
  assignment_not_found: "Anket ataması bulunamadı.",
  student_not_found: "Öğrenci bulunamadı.",
  not_enough_data:
    "Kariyer sentezi için önce Mesleki İlgi ve Beceri Seti anketleri tamamlanmalı.",
  plan_upgrade_required:
    "Bu yapay zekâ özelliği ücretli pakette kullanılabilir — paketinizi yükseltin.",
  consent_required: "AI özellikleri için önce açık rıza vermelisiniz.",
  ai_credit_exhausted:
    "Bu ay için yapay zekâ kredin bitti. Paketini yükselterek devam edebilirsin.",
  ai_unavailable: "AI servisi şu an kullanılamıyor — birazdan tekrar deneyin.",
};

function showError(e: unknown, fallbackTitle: string) {
  const code = e instanceof ApiError ? e.detail?.code : undefined;
  const msg =
    (code && ERROR_LABELS[code]) ||
    (e instanceof ApiError ? e.detail?.message : undefined) ||
    "Sunucu hatası.";
  toast.error(fallbackTitle, { description: msg });
}

export function useAssignSurvey(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<SurveyAssignResult>,
    ApiError,
    { body: SurveyAssignBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<SurveyAssignResult>>(
        `/api/v2/teacher/students/${studentId}/surveys`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Anket gönderilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Anket öğrenciye gönderildi", {
        description: "Öğrenci panelinden ve mobilden doldurabilir.",
      });
    },
  });
}

export function useCancelSurveyAssignment() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ ok: boolean }>,
    ApiError,
    { assignmentId: number }
  >({
    mutationFn: ({ assignmentId }) =>
      api<MutationResponse<{ ok: boolean }>>(
        `/api/v2/teacher/surveys/assignments/${assignmentId}/cancel`,
        { method: "POST" },
      ),
    onError: (e) => showError(e, "Atama iptal edilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Anket ataması iptal edildi");
    },
  });
}

export function useGenerateCareerSynthesis(studentId: number) {
  const qc = useQueryClient();
  // Yanıt MutationResponse zarfı DEĞİL (KS4 deseni) — cache setQueryData ile güncellenir.
  // eslint-disable-next-line lgs/missing-invalidate -- yanıt doğrudan cache'e yazılır
  return useMutation<CareerSynthesisCacheResponse, ApiError, void>({
    mutationFn: () =>
      api<CareerSynthesisCacheResponse>(
        `/api/v2/teacher/students/${studentId}/career-synthesis`,
        { method: "POST" },
      ),
    onError: (e) => showError(e, "Kariyer sentezi üretilemedi"),
    onSuccess: (res) => {
      qc.setQueryData(surveyKeys.careerSynthesis(studentId), res);
      toast.success("Kariyer sentezi hazır", {
        description: "Sonuç kaydedildi — tekrar görüntülemek kredi gerektirmez.",
      });
    },
  });
}

export function useSaveSurveyAnswers(assignmentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<StudentSurveySaveResult>,
    ApiError,
    { answers: Record<string, number | string>; complete: boolean }
  >({
    mutationFn: ({ answers, complete }) =>
      api<MutationResponse<StudentSurveySaveResult>>(
        `/api/v2/student/surveys/${assignmentId}/answers`,
        { method: "POST", body: JSON.stringify({ answers, complete }) },
      ),
    onError: (e) => showError(e, "Cevaplar kaydedilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      if (res.data.completed) {
        toast.success("Anket tamamlandı", {
          description: "Sonucun koçunla paylaşıldı — birlikte değerlendireceksiniz.",
        });
      } else if (res.data.ok) {
        toast.success("Cevapların kaydedildi");
      }
    },
  });
}
