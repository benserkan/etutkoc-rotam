"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, LogOut, Download, Trash2, RotateCcw } from "lucide-react";

import { api, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type { KvkkStatus } from "@/lib/types/me";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface Props {
  /** Server Component'in fetch ettiği snapshot — KVKK butonları için. */
  kvkk: KvkkStatus;
}

/**
 * /me/account sayfası için interaktif kısım.
 *
 * Sade tutulmuştur — yalnızca Dalga 0 canlı testi için yeterli akışlar:
 *   - Çıkış yap
 *   - Verimi indir
 *   - Silme talebi aç (onay diyaloğu ile)
 *   - Bekleyen silmeyi iptal et
 *
 * Mutation success'te:
 *   1. Backend MutationResponse.invalidate listesi okunur
 *   2. applyInvalidate(qc, keys) → TanStack Query etkilenen key'leri yeniden çeker
 *   3. router.refresh() → Server Component (sayfa) da güncel veriyle re-render olur
 */
export function MeActions({ kvkk }: Props) {
  const router = useRouter();
  const qc = useQueryClient();

  // ===== logout =====
  const logout = useMutation({
    mutationFn: () => api<{ ok: boolean }>("/api/v2/auth/logout", { method: "POST" }),
    onSuccess: () => {
      qc.clear();
      toast.success("Oturum kapatıldı");
      router.push("/login");
      router.refresh();
    },
    onError: () => {
      toast.error("Çıkış sırasında hata — yine de yönlendiriliyorsunuz.");
      router.push("/login");
    },
  });

  // ===== delete request =====
  const requestDelete = useMutation({
    mutationFn: (reason: string) =>
      api<MutationResponse<unknown>>("/api/v2/me/data-delete", {
        method: "POST",
        body: JSON.stringify({ confirm: true, reason: reason.trim() || null }),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Silme talebiniz alındı.", {
        description: "30 gün içinde iptal edebilirsiniz; aksi takdirde verileriniz anonimleştirilecek.",
      });
      router.refresh();
    },
    onError: () => toast.error("Silme talebi açılamadı."),
  });

  // ===== cancel pending delete =====
  const cancelDelete = useMutation({
    mutationFn: (id: number) =>
      api<MutationResponse<{ ok: boolean }>>(`/api/v2/me/data-delete/${id}/cancel`, {
        method: "POST",
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Silme talebi iptal edildi.");
      router.refresh();
    },
    onError: () => toast.error("İptal edilemedi."),
  });

  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [deleteReason, setDeleteReason] = React.useState("");

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        asChild   // anchor — yeni sekmede indir
      >
        <a href="/api/v2/me/data-export" download>
          <Download /> Verimi indir
        </a>
      </Button>

      {kvkk.has_pending_delete && kvkk.pending_delete_request_id ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => cancelDelete.mutate(kvkk.pending_delete_request_id!)}
          disabled={cancelDelete.isPending}
        >
          {cancelDelete.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />}
          Silmeyi iptal et
        </Button>
      ) : (
        <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" className="text-destructive">
              <Trash2 /> Hesabımı sil
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Hesabımı sil</DialogTitle>
              <DialogDescription>
                Talebiniz 30 gün sonra uygulanır. Bu süre içinde istediğiniz an
                iptal edebilirsiniz. Anonimleştirme sonrası hesabınız geri yüklenemez.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <label htmlFor="reason" className="text-sm font-medium">
                Sebep (opsiyonel)
              </label>
              <textarea
                id="reason"
                value={deleteReason}
                onChange={(e) => setDeleteReason(e.target.value)}
                rows={3}
                maxLength={500}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="İsterseniz neden silmek istediğinizi yazın…"
              />
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setDeleteOpen(false)}>
                Vazgeç
              </Button>
              <Button
                variant="destructive"
                disabled={requestDelete.isPending}
                onClick={() => {
                  requestDelete.mutate(deleteReason, {
                    onSettled: () => {
                      setDeleteOpen(false);
                      setDeleteReason("");
                    },
                  });
                }}
              >
                {requestDelete.isPending ? <Loader2 className="animate-spin" /> : null}
                Onaylıyorum, talep aç
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      <Button
        variant="ghost"
        size="sm"
        onClick={() => logout.mutate()}
        disabled={logout.isPending}
      >
        {logout.isPending ? <Loader2 className="animate-spin" /> : <LogOut />}
        Çıkış yap
      </Button>
    </div>
  );
}
