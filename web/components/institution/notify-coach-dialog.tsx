"use client";

import * as React from "react";
import { Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useNotifyCoach } from "@/lib/hooks/use-institution-mutations";

export interface NotifyCoachTarget {
  student_name: string;
  teacher_id: number;
  teacher_name: string | null;
}

/**
 * Koça ilet diyaloğu — tükenmişlik + risk panolarında paylaşılır.
 *
 * Gizlilik tasarımı: yönetici öğrenci detayına inemez; müdahale kolu KOÇtur.
 * Bu diyalog ilgili koça aşağı yönlü müdahale talebi açar (koçun "Gelen Talepler"
 * kutusuna düşer). Yalnız öğrencinin adı + isteğe bağlı not iletilir.
 */
export function NotifyCoachDialog({
  target,
  context,
  onClose,
}: {
  target: NotifyCoachTarget | null;
  context: "burnout" | "at_risk";
  onClose: () => void;
}) {
  const notify = useNotifyCoach();
  const [note, setNote] = React.useState("");
  // Hedef değişince notu sıfırla (render sırasında ayarlama — React önerisi:
  // "adjusting state when a prop changes"; effect + cascading render yerine).
  const [lastTarget, setLastTarget] = React.useState(target);
  if (target !== lastTarget) {
    setLastTarget(target);
    setNote("");
  }

  function submit() {
    if (!target) return;
    notify.mutate(
      {
        teacher_id: target.teacher_id,
        student_name: target.student_name,
        note: note.trim() || null,
        context,
      },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <Dialog open={target !== null} onOpenChange={(v) => (!v ? onClose() : undefined)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Koça ilet</DialogTitle>
          <DialogDescription>
            {target?.teacher_name ? (
              <>
                <strong>{target.student_name}</strong> için sorumlu koç{" "}
                <strong>{target.teacher_name}</strong>’a müdahale talebi
                gönderilecek. Koç bunu “Gelen Talepler”de görecek.
              </>
            ) : (
              "Sorumlu koça müdahale talebi gönderilecek."
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="notify-coach-note">
            Not (isteğe bağlı)
          </label>
          <textarea
            id="notify-coach-note"
            className="w-full min-h-[88px] resize-y rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder="Örn. Son haftalarda tempo düştü; görüşüp programı hafifletmesini rica edin."
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={5000}
          />
          <p className="text-xs text-muted-foreground">
            Gizlilik: yalnız öğrencinin adı koça iletilir; çalışma detayını koç
            kendi panelinde görür.
          </p>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={notify.isPending}>
            Vazgeç
          </Button>
          <Button onClick={submit} disabled={notify.isPending}>
            <Send className="size-3.5" aria-hidden />
            {notify.isPending ? "Gönderiliyor…" : "Talep gönder"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
