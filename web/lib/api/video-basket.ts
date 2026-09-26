/**
 * Video Sepeti — koç öğrenci başına YouTube oynatma listesi hazırlar,
 * videolar konu gruplarına ayrılır, haftalık ızgaraya sürüklenir.
 * Backend: app/routes/api_v2/video_basket.py
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";

export type VideoRole = "anlatim" | "soru" | "tekrar" | "diger";
export type VideoStatus = "waiting" | "planned" | "watched";

export interface VideoItem {
  id: number;
  youtube_id: string;
  title: string;
  url: string;
  channel_title: string | null;
  duration_min: number | null;
  role: VideoRole;
  role_label: string;
  order: number;
  status: VideoStatus;
  task_id: number | null;
  task_date: string | null;
}

export interface VideoGroup {
  group_key: string;
  label: string;
  topic_id: number | null;
  topic_name: string | null;
  subject_id: number | null;
  subject_name: string | null;
  playlist_title: string | null;
  source_id: number | null;
  total_min: number;
  waiting_count: number;
  items: VideoItem[];
}

export interface VideoSource {
  id: number;
  name: string;
  title: string | null;
  label: string | null;
  url: string;
  subject_id: number | null;
  subject_name: string | null;
  video_count: number;
  created_at: string | null;
  last_used_at: string | null;
  in_basket: number;
  waiting: number;
}

export interface VideoBasketResponse {
  youtube_configured: boolean;
  groups: VideoGroup[];
  sources: VideoSource[];
  waiting_count: number;
  day_warn_minutes: number;
}

export interface VideoImportResult {
  added: number;
  skipped_existing: number;
  groups: number;
  playlist_title: string | null;
  truncated: boolean;
  unmatched_groups: number;
  source_id: number | null;
}

export interface VideoPlaceResult {
  task_ids: number[];
  day_minutes: number;
}

/** Sürükle-bırak taşıyıcısı: sepetten ızgaraya. */
export const VIDEO_MIME = "text/x-video-basket";
export interface VideoDragPayload {
  itemIds: number[];
  label: string;
}

export const videoBasketKeys = {
  basket: (studentId: number) =>
    ["teacher", "me", "students", String(studentId), "video-basket"] as const,
};

export function getVideoBasket(studentId: number): Promise<VideoBasketResponse> {
  return api<VideoBasketResponse>(`/api/v2/teacher/students/${studentId}/video-basket`);
}

function err(e: unknown, title: string) {
  const msg = e instanceof ApiError ? e.message : "Sunucu hatası.";
  toast.error(title, { description: msg });
}

export function useImportVideos(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<VideoImportResult>,
    ApiError,
    { url?: string | null; source_id?: number | null; subject_id?: number | null }
  >({
    mutationFn: (body) =>
      api(`/api/v2/teacher/students/${studentId}/video-basket/import`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => {
      // Uzun listede bağlantı kopabilir ama sunucu işi bitirmiş olabilir →
      // sepeti hemen ve biraz sonra yeniden çek; kullanıcı F5'e muhtaç kalmasın.
      const key = videoBasketKeys.basket(studentId);
      const refresh = () => qc.invalidateQueries({ queryKey: key });
      refresh();
      setTimeout(refresh, 8000);
      setTimeout(refresh, 25000);
      if (e instanceof ApiError && e.detail?.error !== "unknown") {
        err(e, "Videolar alınamadı");
      } else {
        toast.warning("Yanıt gecikti", {
          description:
            "Liste arka planda alınmış olabilir — sepet birkaç saniye içinde kendini yeniler. Videolar görünmezse tekrar dene.",
        });
      }
    },
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const r = res.data;
      if (r.added === 0) {
        toast.info("Yeni video yok", {
          description: r.skipped_existing
            ? `${r.skipped_existing} video zaten sepette.`
            : undefined,
        });
        return;
      }
      const extra: string[] = [];
      if (r.skipped_existing) extra.push(`${r.skipped_existing} video zaten vardı`);
      if (r.unmatched_groups) extra.push(`${r.unmatched_groups} grubun konusu bulunamadı — adını kontrol et`);
      if (r.truncated) extra.push("liste uzun, ilk 300 video alındı");
      toast.success(`${r.added} video · ${r.groups} konu grubu eklendi`, {
        description: extra.join(" · ") || undefined,
      });
    },
  });
}

export function usePlaceVideos(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<VideoPlaceResult>,
    ApiError,
    { item_ids: number[]; date: string; period?: string | null }
  >({
    mutationFn: (body) =>
      api(`/api/v2/teacher/students/${studentId}/video-basket/place`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => err(e, "Video programa eklenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      const w = res.warnings ?? [];
      if (w.length) toast.warning("Video eklendi — günün video süresi uzun", { description: w.join(" · ") });
      else toast.success("Video programa eklendi (taslak)");
    },
  });
}

export function useUnplaceVideo() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<unknown>, ApiError, { itemId: number }>({
    mutationFn: ({ itemId }) =>
      api(`/api/v2/teacher/video-basket/items/${itemId}/unplace`, { method: "POST" }),
    onError: (e) => err(e, "Video programdan çıkarılamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Video sepete döndü");
    },
  });
}

export function usePatchVideo() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<unknown>,
    ApiError,
    { itemId: number; body: { role?: VideoRole; group_key?: string } }
  >({
    mutationFn: ({ itemId, body }) =>
      api(`/api/v2/teacher/video-basket/items/${itemId}`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => err(e, "Video güncellenemedi"),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
  });
}

export function useDeleteVideo() {
  const qc = useQueryClient();
  return useMutation<MutationResponse<unknown>, ApiError, { itemId: number }>({
    mutationFn: ({ itemId }) =>
      api(`/api/v2/teacher/video-basket/items/${itemId}`, { method: "DELETE" }),
    onError: (e) => err(e, "Video silinemedi"),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
  });
}

export function usePatchVideoGroup(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<unknown>,
    ApiError,
    { group_key: string; label?: string; topic_id?: number | null }
  >({
    mutationFn: (body) =>
      api(`/api/v2/teacher/students/${studentId}/video-basket/groups`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => err(e, "Grup güncellenemedi"),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
  });
}

export function useDeleteVideoGroup(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<{ deleted: number }>, ApiError, { group_key: string }>({
    mutationFn: (body) =>
      api(`/api/v2/teacher/students/${studentId}/video-basket/groups/delete`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => err(e, "Grup silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(`${res.data.deleted} video sepetten silindi`);
    },
  });
}

export function useReorderVideos(studentId: number) {
  const qc = useQueryClient();
  return useMutation<MutationResponse<unknown>, ApiError, { item_ids: number[] }>({
    mutationFn: (body) =>
      api(`/api/v2/teacher/students/${studentId}/video-basket/reorder`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => err(e, "Sıra kaydedilemedi"),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
  });
}

export function useCopyVideos(studentId: number) {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ added: number; skipped_existing: number }>,
    ApiError,
    { target_student_id: number; group_keys?: string[] | null }
  >({
    mutationFn: (body) =>
      api(`/api/v2/teacher/students/${studentId}/video-basket/copy`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => err(e, "Kopyalanamadı"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(`${res.data.added} video kopyalandı`, {
        description: res.data.skipped_existing
          ? `${res.data.skipped_existing} video o öğrencide zaten vardı.`
          : undefined,
      });
    },
  });
}

export function usePatchVideoSource() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<unknown>,
    ApiError,
    { sourceId: number; body: { label?: string; subject_id?: number } }
  >({
    mutationFn: ({ sourceId, body }) =>
      api(`/api/v2/teacher/video-sources/${sourceId}`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => err(e, "Liste güncellenemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Liste güncellendi");
    },
  });
}

export function useDeleteVideoSource() {
  const qc = useQueryClient();
  return useMutation<
    MutationResponse<{ deleted: number; removed_videos: number }>,
    ApiError,
    { sourceId: number; student_id: number; remove_waiting: boolean }
  >({
    mutationFn: ({ sourceId, ...body }) =>
      api(`/api/v2/teacher/video-sources/${sourceId}/delete`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => err(e, "Liste silinemedi"),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kayıtlı liste silindi", {
        description: res.data.removed_videos
          ? `${res.data.removed_videos} bekleyen video sepetten kaldırıldı.`
          : undefined,
      });
    },
  });
}
