"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import {
  addStudentWrongImage,
  createStudentWrongQuestion,
} from "@/lib/api/wrong-questions";
import type {
  WrongQuestionAttemptBody,
  WrongQuestionCreateFields,
  WrongQuestionItem,
  WrongQuestionUpdateBody,
} from "@/lib/types/wrong-question";

/**
 * Yanlış Soru Arşivi mutation hook'ları (öğrenci + koç).
 * Hata kodları backend wrong_question_service.WrongQuestionError'dan gelir.
 */

const ERROR_LABELS: Record<string, string> = {
  wrong_question_not_found: "Kayıt bulunamadı — silinmiş olabilir.",
  invalid_image_type: "Yalnız JPEG/PNG/WebP fotoğraf yüklenebilir.",
  image_too_large: "Fotoğraf çok büyük (en fazla 6 MB).",
  too_many_images: "Bir soruya en fazla 4 fotoğraf eklenebilir.",
  empty_image: "Boş dosya yüklenemez.",
  invalid_error_type: "Geçersiz hata türü.",
  invalid_rating: "Geçersiz değerlendirme.",
  book_not_assigned: "Bu kitap sana atanmamış.",
  section_not_found: "Bölüm bulunamadı.",
  topic_not_found: "Konu bulunamadı.",
  task_not_found: "Görev bulunamadı.",
  role_required: "Bu işlem için yetkin yok.",
};

function showError(e: unknown, fallbackTitle: string) {
  const code = e instanceof ApiError ? e.detail?.code : undefined;
  const msg =
    (code && ERROR_LABELS[code]) ||
    (e instanceof ApiError ? e.detail?.message : undefined) ||
    "Sunucu hatası.";
  toast.error(fallbackTitle, { description: msg });
}

// ---------------------------------------------------------------------------
// Öğrenci
// ---------------------------------------------------------------------------

export function useCreateWrongQuestion() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<WrongQuestionItem>,
    unknown,
    { fields: WrongQuestionCreateFields; photos: File[] }
  >({
    mutationFn: ({ fields, photos }) =>
      createStudentWrongQuestion(fields, photos),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Yanlış arşive eklendi", {
        description:
          "Yarın yeniden çözmen için karşına gelecek — kapanana kadar takipte.",
      });
    },
    onError: (e) => showError(e, "Yanlış eklenemedi"),
  });
}

export function useUpdateWrongQuestion() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<WrongQuestionItem>,
    unknown,
    { id: number; body: WrongQuestionUpdateBody }
  >({
    mutationFn: ({ id, body }) =>
      api(`/api/v2/student/wrong-questions/${id}`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kayıt güncellendi");
    },
    onError: (e) => showError(e, "Güncellenemedi"),
  });
}

export function useAttemptWrongQuestion() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<WrongQuestionItem>,
    unknown,
    { id: number; body: WrongQuestionAttemptBody }
  >({
    mutationFn: ({ id, body }) =>
      api(`/api/v2/student/wrong-questions/${id}/attempt`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const d = res.data;
      if (d.status === "kapandi") {
        toast.success("Soru kapandı! 🎉", {
          description: "Aralıklı iki doğru çözüm — bu açık artık kapalı.",
        });
      } else if (d.correct_streak > 0) {
        toast.success("Kaydedildi", {
          description: "Bir doğru daha — bir sonraki aralıklı çözümde kapanır.",
        });
      } else {
        toast.info("Kaydedildi", {
          description: "Sorun değil — sistem bu soruyu daha sık karşına getirecek.",
        });
      }
    },
    onError: (e) => showError(e, "Kaydedilemedi"),
  });
}

export function useAddWrongImage() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<WrongQuestionItem>,
    unknown,
    { id: number; file: File; kind: "question" | "solution" }
  >({
    mutationFn: ({ id, file, kind }) => addStudentWrongImage(id, file, kind),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Fotoğraf eklendi");
    },
    onError: (e) => showError(e, "Fotoğraf eklenemedi"),
  });
}

export function useDeleteWrongQuestion() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<{ deleted: boolean }>, unknown, { id: number }>({
    mutationFn: ({ id }) =>
      api(`/api/v2/student/wrong-questions/${id}`, { method: "DELETE" }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kayıt silindi");
    },
    onError: (e) => showError(e, "Silinemedi"),
  });
}

// ---------------------------------------------------------------------------
// Koç
// ---------------------------------------------------------------------------

export function useSetCoachNote() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<WrongQuestionItem>,
    unknown,
    { id: number; coach_note: string | null }
  >({
    mutationFn: ({ id, coach_note }) =>
      api(`/api/v2/teacher/wrong-questions/${id}/coach-note`, {
        method: "POST",
        body: JSON.stringify({ coach_note }),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Koç açıklaması kaydedildi", {
        description: "Öğrenci, soruyu yeniden çözerken açıklamanı görecek.",
      });
    },
    onError: (e) => showError(e, "Açıklama kaydedilemedi"),
  });
}
