"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  AcademicYearAssignBody,
  AcademicYearAssignResult,
  AcademicYearCreateBody,
  AcademicYearDetailResponse,
  AcademicYearPatchBody,
  CsvCommitBody,
  CsvCommitResult,
  GradeAdvanceApplyBody,
  GradeAdvanceApplyResult,
  PhaseCreateBody,
  PhaseItem,
  PhasePatchBody,
  ResetProgramConfirmBody,
  ResetProgramResult,
} from "@/lib/types/academic";
import type { DeletedRef } from "@/lib/types/library";

/**
 * Akademik yıl / grade-advance / CSV mutation hook'ları (Paket 10).
 *
 * Hata kodları:
 *   - year_not_found / phase_not_found / student_not_found
 *   - invalid_start_year / invalid_date_range / invalid_phase_kind
 *   - has_students (yıl silinemez)
 *   - duplicate_name (yıl adı çakışması)
 *   - confirm_name_mismatch (reset-program çift onay başarısız)
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
  const code = errorCode(e);
  switch (code) {
    case "year_not_found":
    case "phase_not_found":
    case "student_not_found":
      return "Bulunamadı";
    case "invalid_start_year":
      return "Yıl aralığı dışında";
    case "invalid_date_range":
      return "Tarih aralığı hatalı";
    case "invalid_phase_kind":
      return "Dönem tipi geçersiz";
    case "has_students":
      return "Yıla bağlı öğrenci var";
    case "duplicate_name":
      return "Aynı isim zaten var";
    case "confirm_name_mismatch":
      return "Onay adı eşleşmedi";
    case "name_required":
      return "Eksik bilgi";
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
// Academic years
// =============================================================================

export function useCreateAcademicYear() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AcademicYearDetailResponse>,
    ApiError,
    { body: AcademicYearCreateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<AcademicYearDetailResponse>>(
        "/api/v2/teacher/academic/years",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Akademik yıl oluşturulamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(`${res.data.name} yıl kaydı oluşturuldu`);
    },
  });
}

export function usePatchAcademicYear(yearId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AcademicYearDetailResponse>,
    ApiError,
    { body: AcademicYearPatchBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<AcademicYearDetailResponse>>(
        `/api/v2/teacher/academic/years/${encodeURIComponent(String(yearId))}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Akademik yıl güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Yıl güncellendi");
    },
  });
}

export function useDeleteAcademicYear(yearId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<DeletedRef>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<DeletedRef>>(
        `/api/v2/teacher/academic/years/${encodeURIComponent(String(yearId))}`,
        { method: "DELETE" },
      ),
    onError: (e) => showError(e, "Yıl silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Yıl silindi");
    },
  });
}

// =============================================================================
// Phases
// =============================================================================

export function useCreatePhase(yearId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<PhaseItem>,
    ApiError,
    { body: PhaseCreateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<PhaseItem>>(
        `/api/v2/teacher/academic/years/${encodeURIComponent(String(yearId))}/phases`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Dönem eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(`'${res.data.name}' dönemi eklendi`);
    },
  });
}

export function usePatchPhase(yearId: number, phaseId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<PhaseItem>,
    ApiError,
    { body: PhasePatchBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<PhaseItem>>(
        `/api/v2/teacher/academic/years/${encodeURIComponent(
          String(yearId),
        )}/phases/${encodeURIComponent(String(phaseId))}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Dönem güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Dönem güncellendi");
    },
  });
}

export function useDeletePhase(yearId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<DeletedRef>,
    ApiError,
    { phaseId: number }
  >({
    mutationFn: ({ phaseId }) =>
      api<MutationResponse<DeletedRef>>(
        `/api/v2/teacher/academic/years/${encodeURIComponent(
          String(yearId),
        )}/phases/${encodeURIComponent(String(phaseId))}`,
        { method: "DELETE" },
      ),
    onError: (e) => showError(e, "Dönem silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Dönem silindi");
    },
  });
}

// =============================================================================
// Student assignment
// =============================================================================

export function useAssignStudentsToYear(yearId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AcademicYearAssignResult>,
    ApiError,
    { body: AcademicYearAssignBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<AcademicYearAssignResult>>(
        `/api/v2/teacher/academic/years/${encodeURIComponent(
          String(yearId),
        )}/students`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Atama güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const { assigned_count, removed_count, unchanged_count } = res.data;
      toast.success("Atama güncellendi", {
        description: `${assigned_count} eklendi · ${removed_count} çıkarıldı · ${unchanged_count} değişmedi`,
      });
    },
  });
}

// =============================================================================
// Grade advance
// =============================================================================

export function useGradeAdvanceApply() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<GradeAdvanceApplyResult>,
    ApiError,
    { body: GradeAdvanceApplyBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<GradeAdvanceApplyResult>>(
        "/api/v2/teacher/grade-advance/apply",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Sınıf yükseltme başarısız"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const {
        advanced_count,
        preserved_reservations_count,
        skipped_invalid,
        skipped_track_missing,
      } = res.data;
      const bits: string[] = [];
      bits.push(`${advanced_count} öğrenci yükseltildi`);
      if (preserved_reservations_count > 0) {
        bits.push(`${preserved_reservations_count} rezerv korundu`);
      }
      if (skipped_invalid.length + skipped_track_missing.length > 0) {
        bits.push(
          `${skipped_invalid.length + skipped_track_missing.length} atlandı`,
        );
      }
      toast.success("Sınıf yükseltme tamam", {
        description: bits.join(" · "),
      });
    },
  });
}

export function useResetProgram(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ResetProgramResult>,
    ApiError,
    { body: ResetProgramConfirmBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<ResetProgramResult>>(
        `/api/v2/teacher/grade-advance/students/${encodeURIComponent(
          String(studentId),
        )}/reset-program`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "Program sıfırlanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const { deleted_tasks, cleared_reservations } = res.data;
      toast.success("Program sıfırlandı", {
        description: `${deleted_tasks} görev silindi · ${cleared_reservations} rezerv temizlendi`,
      });
    },
  });
}

// =============================================================================
// CSV import (preview + commit)
// =============================================================================

export function useCsvImportPreview() {
  // Önizleme yan etkisi yok — DB'ye yazmaz, sadece parse sonucu döner.
  // Bu yüzden invalidate çağrısı YOK; aşağıdaki kural bilerek susturuldu.
  // eslint-disable-next-line lgs/missing-invalidate -- preview yan etkisiz
  return useMutation<
    import("@/lib/types/academic").CsvPreviewResponse,
    ApiError,
    { body: CsvCommitBody }
  >({
    mutationFn: ({ body }) =>
      api<import("@/lib/types/academic").CsvPreviewResponse>(
        "/api/v2/teacher/csv/import/students/preview",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "CSV önizleme başarısız"),
    onSuccess: () => {},
  });
}

export function useCsvImportCommit() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<CsvCommitResult>,
    ApiError,
    { body: CsvCommitBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<CsvCommitResult>>(
        "/api/v2/teacher/csv/import/students/commit",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (e) => showError(e, "CSV içe aktarma başarısız"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const { created_count, skipped_count } = res.data;
      toast.success(
        `${created_count} öğrenci eklendi${skipped_count > 0 ? ` · ${skipped_count} atlandı` : ""}`,
      );
    },
  });
}
