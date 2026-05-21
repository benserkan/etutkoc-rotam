"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  AddBooksToSetBody,
  AddBooksToSetResult,
  AiSuggestBody,
  AiSuggestResult,
  ApplyTemplateBody,
  ApplyTemplateResult,
  AssignmentsPatchBody,
  AssignmentsResult,
  BookCreateBody,
  BookPatchBody,
  BookSetCreateBody,
  BookSetDetailResponse,
  BookSetPatchBody,
  BookTemplateListItem,
  BulkCatalogResult,
  DeletedRef,
  LibraryBookDetailResponse,
  LibrarySectionItem,
  SaveAsTemplateBody,
  SectionCreateBody,
  SectionPatchBody,
  SectionsBulkFromCatalogBody,
} from "@/lib/types/library";

/**
 * Kitap kütüphanesi mutation hook'ları (Dalga 3 Paket 8).
 *
 * Tüm mutation'lar başarıda backend'in MutationResponse.invalidate listesini
 * applyInvalidate ile uygular (R-006 OOB swap karşılığı). 4xx hatalarında
 * `detail.code`'a göre kullanıcı dostu toast üretilir.
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
    case "has_progress":
      return "İlerleme var, işlem yapılamadı";
    case "sections_exist":
      return "Mevcut ünite var";
    case "invalid_section_count":
      return "Geçersiz test sayısı";
    case "ai_disabled_for_plan":
      return "AI özelliği planda kapalı";
    case "ai_credit_exhausted":
      return "AI kredisi bitti";
    case "ai_provider_error":
      return "AI servisi yanıt vermedi";
    case "name_required":
    case "label_required":
    case "no_sections":
    case "no_topics":
    case "invalid_type":
    case "invalid_subject":
    case "invalid_topic":
    case "invalid_test_count":
      return "Eksik veya hatalı bilgi";
    case "book_not_found":
    case "template_not_found":
    case "book_set_not_found":
    case "section_not_found":
    case "subject_not_found":
    case "book_set_item_not_found":
      return "Bulunamadı";
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
// Books CRUD
// =============================================================================

export function useCreateBook() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<LibraryBookDetailResponse>,
    ApiError,
    { body: BookCreateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<LibraryBookDetailResponse>>(
        "/api/v2/teacher/library/books",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Kitap oluşturulamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kitap oluşturuldu");
    },
  });
}

export function usePatchBook(bookId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<LibraryBookDetailResponse>,
    ApiError,
    { body: BookPatchBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<LibraryBookDetailResponse>>(
        `/api/v2/teacher/library/books/${bookId}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Kitap güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kitap güncellendi");
    },
  });
}

export function useDeleteBook(bookId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<DeletedRef>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<DeletedRef>>(
        `/api/v2/teacher/library/books/${bookId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Kitap silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kitap silindi");
    },
  });
}

// =============================================================================
// Sections
// =============================================================================

export function useCreateSection(bookId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<LibrarySectionItem>,
    ApiError,
    { body: SectionCreateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<LibrarySectionItem>>(
        `/api/v2/teacher/library/books/${bookId}/sections`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Bölüm eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Bölüm eklendi");
    },
  });
}

export function useBulkSectionsFromCatalog(bookId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<BulkCatalogResult>,
    ApiError,
    { body: SectionsBulkFromCatalogBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<BulkCatalogResult>>(
        `/api/v2/teacher/library/books/${bookId}/sections/bulk-from-catalog`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Toplu konu eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const r = res.data;
      toast.success(
        `${r.added_count} bölüm eklendi` +
          (r.skipped_existing_count > 0
            ? ` · ${r.skipped_existing_count} mevcut atlandı`
            : ""),
      );
    },
  });
}

export function usePatchSection(bookId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<LibrarySectionItem>,
    ApiError,
    { sectionId: number; body: SectionPatchBody }
  >({
    mutationFn: ({ sectionId, body }) =>
      api<MutationResponse<LibrarySectionItem>>(
        `/api/v2/teacher/library/books/${bookId}/sections/${sectionId}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Bölüm güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
    },
  });
}

export function useDeleteSection(bookId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<DeletedRef>,
    ApiError,
    { sectionId: number }
  >({
    mutationFn: ({ sectionId }) =>
      api<MutationResponse<DeletedRef>>(
        `/api/v2/teacher/library/books/${bookId}/sections/${sectionId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Bölüm silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Bölüm silindi");
    },
  });
}

export function useClearSections(bookId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<DeletedRef>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<DeletedRef>>(
        `/api/v2/teacher/library/books/${bookId}/clear-sections`,
        { method: "POST" },
      ),
    onError: (err) => showError(err, "Bölümler temizlenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Tüm bölümler silindi");
    },
  });
}

// =============================================================================
// AI suggest
// =============================================================================

export function useAiSuggestSections(bookId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AiSuggestResult>,
    ApiError,
    { body: AiSuggestBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<AiSuggestResult>>(
        `/api/v2/teacher/library/books/${bookId}/ai-suggest`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "AI önerisi alınamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(`✨ AI ${res.data.added_section_count} ünite önerdi`);
    },
  });
}

// =============================================================================
// Assignments
// =============================================================================

export function useAssignBookToStudents(bookId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AssignmentsResult>,
    ApiError,
    { body: AssignmentsPatchBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<AssignmentsResult>>(
        `/api/v2/teacher/library/books/${bookId}/assignments`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Atamalar güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const r = res.data;
      const skipped = r.skipped_with_progress.length;
      toast.success(
        `Eklendi: ${r.assigned_count} · Kaldırıldı: ${r.removed_count}` +
          (skipped > 0
            ? ` · ${skipped} öğrenci rezerv olduğu için korundu`
            : ""),
      );
    },
  });
}

// =============================================================================
// Templates
// =============================================================================

export function useSaveAsTemplate(bookId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<BookTemplateListItem>,
    ApiError,
    { body: SaveAsTemplateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<BookTemplateListItem>>(
        `/api/v2/teacher/library/books/${bookId}/save-as-template`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Şablon kaydedilemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Şablon olarak kaydedildi");
    },
  });
}

export function useApplyTemplate(bookId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<ApplyTemplateResult>,
    ApiError,
    { body: ApplyTemplateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<ApplyTemplateResult>>(
        `/api/v2/teacher/library/books/${bookId}/apply-template`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Şablon uygulanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(`${res.data.added_count} bölüm eklendi`);
    },
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<DeletedRef>,
    ApiError,
    { templateId: number }
  >({
    mutationFn: ({ templateId }) =>
      api<MutationResponse<DeletedRef>>(
        `/api/v2/teacher/library/templates/${templateId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Şablon silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Şablon silindi");
    },
  });
}

export function useVerifyTemplate() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<BookTemplateListItem>,
    ApiError,
    { templateId: number }
  >({
    mutationFn: ({ templateId }) =>
      api<MutationResponse<BookTemplateListItem>>(
        `/api/v2/teacher/library/templates/${templateId}/verify`,
        { method: "POST" },
      ),
    onError: (err) => showError(err, "Şablon doğrulanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Şablon doğrulandı");
    },
  });
}

// =============================================================================
// Book sets
// =============================================================================

export function useCreateBookSet() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<BookSetDetailResponse>,
    ApiError,
    { body: BookSetCreateBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<BookSetDetailResponse>>(
        "/api/v2/teacher/library/book-sets",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Set oluşturulamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Set oluşturuldu");
    },
  });
}

export function usePatchBookSet(setId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<BookSetDetailResponse>,
    ApiError,
    { body: BookSetPatchBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<BookSetDetailResponse>>(
        `/api/v2/teacher/library/book-sets/${setId}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Set güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Set güncellendi");
    },
  });
}

export function useDeleteBookSet(setId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<DeletedRef>, ApiError, void>({
    mutationFn: () =>
      api<MutationResponse<DeletedRef>>(
        `/api/v2/teacher/library/book-sets/${setId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Set silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Set silindi");
    },
  });
}

export function useAddBooksToSet(setId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<AddBooksToSetResult>,
    ApiError,
    { body: AddBooksToSetBody }
  >({
    mutationFn: ({ body }) =>
      api<MutationResponse<AddBooksToSetResult>>(
        `/api/v2/teacher/library/book-sets/${setId}/books`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onError: (err) => showError(err, "Kitap eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const r = res.data;
      toast.success(
        `${r.added_count} kitap eklendi` +
          (r.skipped_existing_count > 0
            ? ` · ${r.skipped_existing_count} zaten setteydi`
            : ""),
      );
    },
  });
}

export function useRemoveBookFromSet(setId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<DeletedRef>,
    ApiError,
    { bookId: number }
  >({
    mutationFn: ({ bookId }) =>
      api<MutationResponse<DeletedRef>>(
        `/api/v2/teacher/library/book-sets/${setId}/books/${bookId}`,
        { method: "DELETE" },
      ),
    onError: (err) => showError(err, "Kitap kaldırılamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kitap setten kaldırıldı");
    },
  });
}
