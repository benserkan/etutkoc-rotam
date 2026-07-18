"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BookX, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { archiveExamWrongs } from "@/lib/api/exam-import";
import { applyInvalidate } from "@/lib/invalidate";
import { cn } from "@/lib/utils";

/**
 * Faz 3 köprüsü: denemenin yanlışlarını TEK TIKLA Yanlış Soru Arşivine aktarır
 * (idempotent — ikinci basış mükerrer üretmez). Koç dialog/satırında
 * studentId verilir; öğrenci yüzeyinde verilmez (kendi arşivi).
 */
export function ArchiveExamWrongsButton({
  examId,
  studentId = null,
  wrongCount,
  compact = false,
  className,
}: {
  examId: number;
  studentId?: number | null;
  /** Denemedeki yanlış sayısı — 0 ise buton hiç görünmez. */
  wrongCount: number;
  /** true → yalnız ikon (liste satırı); false → ikon + etiket (dialog). */
  compact?: boolean;
  className?: string;
}) {
  const qc = useQueryClient();
  const [busy, setBusy] = React.useState(false);
  const [done, setDone] = React.useState(false);
  if (wrongCount <= 0) return null;

  async function run() {
    setBusy(true);
    try {
      const res = await archiveExamWrongs(examId, studentId);
      applyInvalidate(qc, res.invalidate);
      const d = res.data;
      setDone(true);
      const parts = [`${d.created} yanlış arşive eklendi`];
      if (d.skipped_existing > 0) parts.push(`${d.skipped_existing} zaten vardı`);
      if (d.skipped_no_topic > 0) {
        parts.push(
          `${d.skipped_no_topic} soru konusuz olduğundan atlandı — "Satırları düzelt" ile bağlayınca aktarılabilir`,
        );
      }
      toast.success("Yanlış Soru Arşivi", { description: parts.join(" · ") });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Aktarım başarısız.";
      toast.error("Arşive eklenemedi", { description: msg });
    } finally {
      setBusy(false);
    }
  }

  if (compact) {
    return (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => void run()}
        disabled={busy}
        aria-label="Yanlışları Soru Arşivine ekle"
        title={`${wrongCount} yanlışı Yanlış Soru Arşivine ekle (tekrar çözme kuyruğuna girer)`}
        className={className}
      >
        {busy ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <BookX className={cn("size-4", done ? "text-emerald-600" : "text-rose-600")} aria-hidden />
        )}
      </Button>
    );
  }
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => void run()}
      disabled={busy || done}
      className={cn(
        "gap-1.5 border-rose-300 text-rose-700 hover:bg-rose-500/10 hover:text-rose-800 dark:border-rose-500/40 dark:text-rose-300",
        className,
      )}
    >
      {busy ? (
        <Loader2 className="size-4 animate-spin" aria-hidden />
      ) : (
        <BookX className="size-4" aria-hidden />
      )}
      {done
        ? "Arşive eklendi"
        : `${wrongCount} yanlışı Soru Arşivine ekle`}
    </Button>
  );
}
