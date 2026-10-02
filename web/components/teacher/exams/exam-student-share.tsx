"use client";

/**
 * Denemeyi öğrenciyle paylaş (Faz 2) — koçun ÖĞRENCİYE notu.
 *
 * Koça özel deneme notu (`note`) öğrenciye ve veliye GÖSTERİLMEZ; buradaki not
 * ayrıdır ve öğrencinin Denemelerim ekranında görünür (+ uygulama bildirimi).
 */

import * as React from "react";
import { Send, UserCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { fmtNet, fmtTRDate } from "@/lib/exam-format";
import { useShareExamWithStudent, useUnshareExam } from "@/lib/hooks/use-exam-progress-mutations";
import type { ExamShareInfo } from "@/lib/types/exam-progress";
import type { ExamResultRow } from "@/lib/types/teacher";

export function ExamStudentShareButton({
  row,
  share,
}: {
  row: ExamResultRow;
  share: ExamShareInfo | null;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <>
      {share ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1 rounded border border-cyan-300 bg-cyan-50 px-1.5 py-1 text-[11px] font-medium text-cyan-900 hover:bg-cyan-100 dark:border-cyan-500/40 dark:bg-cyan-500/10 dark:text-cyan-200 dark:hover:bg-cyan-500/20"
          title={`Öğrenciyle paylaşıldı · ${fmtTRDate(share.shared_at.slice(0, 10))} — notu düzenle`}
        >
          <UserCheck className="size-3.5" aria-hidden />
          Öğrencide
        </button>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOpen(true)}
          aria-label="Öğrenciyle paylaş"
          title="Denemeyi öğrenciyle paylaş — öğrenciye not yaz"
        >
          <Send className="size-4 text-cyan-700 dark:text-cyan-400" aria-hidden />
        </Button>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          {open ? <ShareForm row={row} share={share} onDone={() => setOpen(false)} /> : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

function ShareForm({
  row,
  share,
  onDone,
}: {
  row: ExamResultRow;
  share: ExamShareInfo | null;
  onDone: () => void;
}) {
  const [note, setNote] = React.useState(share?.note ?? "");
  const [notify, setNotify] = React.useState(!share);
  const shareMut = useShareExamWithStudent();
  const unshare = useUnshareExam();
  return (
    <>
      <DialogHeader>
        <DialogTitle>Öğrenciyle paylaş</DialogTitle>
        <DialogDescription>
          {row.title} · {fmtTRDate(row.exam_date)} · {fmtNet(row.net)} net. Öğrenci denemeyi zaten görür;
          bu not ona özel değerlendirmendir. Koça özel notun paylaşılmaz.
        </DialogDescription>
      </DialogHeader>
      <label className="block text-sm">
        <span className="mb-1 block text-xs text-muted-foreground">Öğrenciye not</span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={1000}
          rows={5}
          placeholder="Örn. Paragrafta çok iyi gidiyorsun; Matematikte boşları azaltalım, bu hafta problemlere ağırlık veriyoruz."
          className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
          aria-label="Öğrenciye not"
        />
        <span className="mt-0.5 block text-right text-[11px] text-muted-foreground">{note.length}/1000</span>
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={notify}
          onChange={(e) => setNotify(e.target.checked)}
          className="size-4 accent-cyan-700"
        />
        Öğrencinin uygulamasına bildirim gönder
      </label>
      <DialogFooter className="gap-2">
        {share ? (
          <Button
            variant="outline"
            disabled={unshare.isPending}
            onClick={() => unshare.mutate(row.id, { onSuccess: onDone })}
          >
            Paylaşımı geri al
          </Button>
        ) : null}
        <Button
          disabled={shareMut.isPending}
          onClick={() => shareMut.mutate({ examId: row.id, note, notify }, { onSuccess: onDone })}
        >
          <Send className="size-4" aria-hidden />
          {share ? "Notu güncelle" : "Paylaş"}
        </Button>
      </DialogFooter>
    </>
  );
}
