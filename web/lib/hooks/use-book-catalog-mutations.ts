"use client";

/**
 * Ortak Kitap Kataloğu mutation hook'ları (süper admin + koç).
 *
 * Okuma uçları (read/identify) sunucuda iş yapan ama cache'i etkilemeyen
 * "taslak üretici" çağrılardır — invalidate yoktur (önizleme deseni).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import {
  adminCatalogAction,
  adminCreateCatalogEntry,
  adminReadStructure,
  adminUpdateCatalogEntry,
  coachContributeCatalog,
  coachIdentifyCover,
  coachReadStructure,
} from "@/lib/api/book-catalog";
import type {
  AdminCatalogCreateBody,
  AdminCatalogUpdateBody,
  CatalogContributeBody,
  CatalogContributeResult,
  CatalogEntryDetail,
  CoverIdentifyResult,
  StructureReadResult,
} from "@/lib/types/book-catalog";

const READ_ERROR_TITLES: Record<string, string> = {
  not_a_toc: "İçindekiler sayfası bulunamadı",
  daily_read_limit: "Günlük okuma hakkın doldu",
  file_too_large: "Dosya çok büyük",
  invalid_media_type: "Desteklenmeyen dosya türü",
  too_many_files: "Çok fazla fotoğraf",
  mixed_files: "PDF tek başına yüklenmeli",
  no_files: "Dosya seçilmedi",
  ai_provider_error: "AI servisi şu an yanıt vermiyor",
};

function readErrorToast(e: ApiError, fallback: string) {
  const code = (e.detail as { code?: string } | undefined)?.code ?? "";
  const msg = (e.detail as { message?: string } | undefined)?.message;
  toast.error(READ_ERROR_TITLES[code] ?? fallback, { description: msg });
}

// =============================================================================
// Okuma motoru (taslak üretici — invalidate yok)
// =============================================================================

export function useReadStructure(scope: "coach" | "admin") {
  // eslint-disable-next-line lgs/missing-invalidate -- salt taslak üretimi; sunucu durumunu değiştirmez (önizleme deseni)
  return useMutation<StructureReadResult, ApiError, File[]>({
    mutationFn: (files) =>
      scope === "admin" ? adminReadStructure(files) : coachReadStructure(files),
    onError: (e) => readErrorToast(e, "İçindekiler okunamadı"),
  });
}

export function useIdentifyCover() {
  // eslint-disable-next-line lgs/missing-invalidate -- salt tanıma; sunucu durumunu değiştirmez
  return useMutation<CoverIdentifyResult, ApiError, File>({
    mutationFn: (file) => coachIdentifyCover(file),
    onError: (e) => readErrorToast(e, "Kapak okunamadı"),
  });
}

// =============================================================================
// Koç: katkı
// =============================================================================

export function useContributeCatalog() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<CatalogContributeResult>,
    ApiError,
    CatalogContributeBody
  >({
    mutationFn: (body) => coachContributeCatalog(body),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      if (res.data.status === "pending") {
        toast.success("Kitap yapısı kataloğa önerildi", {
          description: "Onaylanınca diğer koçlar tek tıkla kullanabilecek. Teşekkürler!",
        });
      }
      // already_in_catalog → sessiz (kitap zaten katalogda, mesaj gürültüsü olmasın)
    },
    onError: () => {
      // Katkı best-effort — koçun kitap oluşturma akışını asla bozmaz.
    },
  });
}

// =============================================================================
// Süper admin: CRUD + moderasyon
// =============================================================================

export function useAdminCatalogCreate() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<CatalogEntryDetail>,
    ApiError,
    AdminCatalogCreateBody
  >({
    mutationFn: (body) => adminCreateCatalogEntry(body),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        res.data.status === "verified"
          ? "Kitap kataloğa eklendi (yayında)"
          : "Kitap kataloğa eklendi (onay kuyruğu)",
      );
    },
    onError: (e) => {
      const code = (e.detail as { code?: string } | undefined)?.code;
      toast.error(
        code === "already_in_catalog"
          ? "Bu kitap katalogda zaten var"
          : "Kitap eklenemedi",
        { description: (e.detail as { message?: string } | undefined)?.message },
      );
    },
  });
}

export function useAdminCatalogUpdate() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<CatalogEntryDetail>,
    ApiError,
    { id: number; body: AdminCatalogUpdateBody }
  >({
    mutationFn: ({ id, body }) => adminUpdateCatalogEntry(id, body),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Katalog kaydı güncellendi");
    },
    onError: (e) => {
      toast.error("Kayıt güncellenemedi", {
        description: (e.detail as { message?: string } | undefined)?.message,
      });
    },
  });
}

const ACTION_LABELS: Record<string, string> = {
  verify: "Kayıt yayına alındı — koçlar artık kullanabilir",
  hide: "Kayıt yayından kaldırıldı",
  delete: "Kayıt silindi",
};

export function useAdminCatalogAction() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<unknown>,
    ApiError,
    { id: number; action: "verify" | "hide" | "delete" }
  >({
    mutationFn: ({ id, action }) => adminCatalogAction(id, action),
    onSuccess: (res, vars) => {
      applyInvalidate(qc, res.invalidate);
      // Rozet (book_catalog_pending) tazelensin
      void qc.invalidateQueries({ queryKey: ["admin", "badges"] });
      toast.success(ACTION_LABELS[vars.action] ?? "İşlem tamam");
    },
    onError: (e) => {
      const code = (e.detail as { code?: string } | undefined)?.code;
      toast.error(
        code === "entry_in_use"
          ? "Kayıt koçlar tarafından kullanılmış — silmek yerine yayından kaldır"
          : "İşlem yapılamadı",
        { description: (e.detail as { message?: string } | undefined)?.message },
      );
    },
  });
}
