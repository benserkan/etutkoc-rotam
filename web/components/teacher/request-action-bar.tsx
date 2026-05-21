"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import {
  useApproveRequest,
  useRejectRequest,
  useRespondRequest,
} from "@/lib/hooks/use-teacher-mutations";
import type { TeacherRequestDetail } from "@/lib/types/teacher";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

interface Props {
  req: TeacherRequestDetail;
}

type ModalKind = null | "approve" | "reject" | "respond";

/**
 * Talep detay sayfasının aksiyon çubuğu — Onayla / Reddet / Cevapla butonları
 * + ilgili modal'lar.
 *
 * Yalnız PENDING talepler için aktif. QUESTION tipinde "Onayla" gizlenir,
 * "Cevapla" gösterilir.
 */
export function RequestActionBar({ req }: Props) {
  const router = useRouter();
  const [modal, setModal] = React.useState<ModalKind>(null);

  const approveMut = useApproveRequest(req.id);
  const rejectMut = useRejectRequest(req.id);
  const respondMut = useRespondRequest(req.id);

  if (req.status !== "pending") {
    return (
      <p className="text-sm text-muted-foreground">
        Bu talep zaten yanıtlandı.
      </p>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {req.type !== "question" ? (
        <Button
          onClick={() => setModal("approve")}
          disabled={approveMut.isPending}
        >
          {approveMut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          Onayla
        </Button>
      ) : null}

      {req.type === "question" ? (
        <Button
          onClick={() => setModal("respond")}
          disabled={respondMut.isPending}
        >
          {respondMut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          Cevapla
        </Button>
      ) : (
        <Button
          variant="outline"
          onClick={() => setModal("reject")}
          disabled={rejectMut.isPending}
        >
          {rejectMut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          Reddet
        </Button>
      )}

      <Dialog open={modal === "approve"} onOpenChange={(o) => !o && setModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Talebi onayla</DialogTitle>
          </DialogHeader>
          <ResponseForm
            label="Kısa not (opsiyonel)"
            placeholder="Onayladım. Başarılar!"
            submitLabel="Onayla"
            isPending={approveMut.isPending}
            requireValue={false}
            onCancel={() => setModal(null)}
            onSubmit={(v) =>
              approveMut.mutate(
                { body: { response: v || null } },
                {
                  onSuccess: () => {
                    setModal(null);
                    router.refresh();
                  },
                },
              )
            }
          />
        </DialogContent>
      </Dialog>

      <Dialog open={modal === "reject"} onOpenChange={(o) => !o && setModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Talebi reddet</DialogTitle>
          </DialogHeader>
          <ResponseForm
            label="Red gerekçesi (zorunlu)"
            placeholder="Şu an program değişikliği yapamayız çünkü…"
            submitLabel="Reddet"
            isPending={rejectMut.isPending}
            requireValue
            onCancel={() => setModal(null)}
            onSubmit={(v) =>
              rejectMut.mutate(
                { body: { reason: v } },
                {
                  onSuccess: () => {
                    setModal(null);
                    router.refresh();
                  },
                },
              )
            }
          />
        </DialogContent>
      </Dialog>

      <Dialog open={modal === "respond"} onOpenChange={(o) => !o && setModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Soruya cevap ver</DialogTitle>
          </DialogHeader>
          <ResponseForm
            label="Cevap"
            placeholder="Önce konu özetine bak, sonra test çöz."
            submitLabel="Gönder"
            isPending={respondMut.isPending}
            requireValue
            onCancel={() => setModal(null)}
            onSubmit={(v) =>
              respondMut.mutate(
                { body: { response: v } },
                {
                  onSuccess: () => {
                    setModal(null);
                    router.refresh();
                  },
                },
              )
            }
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ResponseForm({
  label,
  placeholder,
  submitLabel,
  isPending,
  requireValue,
  onSubmit,
  onCancel,
}: {
  label: string;
  placeholder: string;
  submitLabel: string;
  isPending: boolean;
  requireValue: boolean;
  onSubmit: (value: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = value.trim();
    if (requireValue && !v) {
      setError("Bu alan zorunlu.");
      return;
    }
    setError(null);
    onSubmit(v);
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <label className="text-sm font-medium">{label}</label>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        rows={4}
        className={cn(
          "w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      />
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={isPending}>
          İptal
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
