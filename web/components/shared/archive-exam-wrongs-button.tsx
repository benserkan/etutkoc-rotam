"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BookX, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import { archiveExamWrongs, getExamWrongRows } from "@/lib/api/exam-import";
import { applyInvalidate } from "@/lib/invalidate";
import type { ExamWrongRowsResponse } from "@/lib/types/exam-import";
import { cn } from "@/lib/utils";

/**
 * Faz 3 köprüsü — SEÇİCİ aktarım (2026-07-19 kararı): denemenin TÜM
 * yanlışlarını yığmak arşivi şişirir; arşiv SEÇİLMİŞ, tekrar etmeye değer
 * sorular içindir. Buton bir seçim dialogu açar: kullanıcı soruları işaretler,
 * istersen hata türü atar; seçilenler arşive girip aralıklı tekrar kuyruğunda
 * yeniden çözülür. İdempotent — aynı soru ikinci kez eklenmez.
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
  const [open, setOpen] = React.useState(false);
  if (wrongCount <= 0) return null;
  return (
    <>
      {compact ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOpen(true)}
          aria-label="Yanlışlardan arşive soru seç"
          title="Yanlışlardan seçtiklerini Soru Arşivine ekle (tekrar kuyruğuna girer)"
          className={className}
        >
          <BookX className="size-4 text-rose-600" aria-hidden />
        </Button>
      ) : (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setOpen(true)}
          className={cn(
            "gap-1.5 border-rose-300 text-rose-700 hover:bg-rose-500/10 hover:text-rose-800 dark:border-rose-500/40 dark:text-rose-300",
            className,
          )}
        >
          <BookX className="size-4" aria-hidden />
          Yanlışlardan arşive soru seç
        </Button>
      )}
      {open ? (
        <ArchiveWrongsDialog
          examId={examId}
          studentId={studentId}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}

function ArchiveWrongsDialog({
  examId,
  studentId,
  onClose,
}: {
  examId: number;
  studentId: number | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [data, setData] = React.useState<ExamWrongRowsResponse | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [errorTypes, setErrorTypes] = React.useState<Record<number, string>>({});
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    let alive = true;
    getExamWrongRows(examId, studentId)
      .then((d) => { if (alive) setData(d); })
      .catch((e) => {
        if (alive) {
          setLoadError(e instanceof ApiError ? e.message : "Liste yüklenemedi.");
        }
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- yalnız mount'ta (dialog açıkken remount)
  }, []);

  const selectable = (data?.rows ?? []).filter(
    (r) => !r.archived && r.topic_id != null,
  );
  const noTopicCount = (data?.rows ?? []).filter(
    (r) => !r.archived && r.topic_id == null,
  ).length;

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit() {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      const res = await archiveExamWrongs(
        examId, studentId,
        [...selected].map((id) => ({
          question_id: id,
          error_type: errorTypes[id] || null,
        })),
      );
      applyInvalidate(qc, res.invalidate);
      const d = res.data;
      toast.success("Soru Arşivi", {
        description:
          `${d.created} soru arşive eklendi — aralıklı tekrar kuyruğunda ` +
          "yeniden çözülecek.",
      });
      onClose();
    } catch (e) {
      toast.error("Arşive eklenemedi", {
        description: e instanceof ApiError ? e.message : "Aktarım başarısız.",
      });
      setBusy(false);
    }
  }

  // ders bazlı grupla
  const groups = new Map<string, typeof selectable>();
  for (const r of data?.rows ?? []) {
    const key = r.subject ?? "Diğer";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(r);
  }

  return (
    <Dialog open onOpenChange={(v) => { if (!v && !busy) onClose(); }}>
      <DialogContent className="flex max-h-[85vh] max-w-2xl flex-col overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4">
          <DialogTitle className="flex items-center gap-2 text-base">
            <BookX className="size-4 text-rose-600" aria-hidden />
            Yanlışlardan arşive soru seç
          </DialogTitle>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {loadError ? (
            <p className="text-sm text-rose-700 dark:text-rose-300">{loadError}</p>
          ) : !data ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="size-6 animate-spin text-rose-500" aria-hidden />
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Arşiv, <b>seçilmiş</b> sorular içindir — hepsini eklemek şart
                değil. Tekrar çözmeye değer bulduklarını işaretle; istersen hata
                türünü de seç. Eklenenler <b>aralıklı tekrar kuyruğuna</b> girer
                (iki aralıklı doğru çözümle kapanır).
              </p>
              <div className="flex gap-3 text-xs">
                <button
                  type="button"
                  className="text-rose-700 underline dark:text-rose-300"
                  onClick={() =>
                    setSelected(new Set(selectable.map((r) => r.question_id)))
                  }
                >
                  Tümünü seç ({selectable.length})
                </button>
                <button
                  type="button"
                  className="text-muted-foreground underline"
                  onClick={() => setSelected(new Set())}
                >
                  Temizle
                </button>
              </div>
              {[...groups.entries()].map(([gname, rows]) => (
                <section key={gname}>
                  <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {gname}
                  </h4>
                  <ul className="space-y-1">
                    {rows.map((r) => {
                      const disabled = r.archived || r.topic_id == null;
                      const isSel = selected.has(r.question_id);
                      return (
                        <li
                          key={r.question_id}
                          className={cn(
                            "flex items-center gap-2 rounded-md border px-2 py-1.5",
                            isSel
                              ? "border-rose-300 bg-rose-50 dark:border-rose-500/40 dark:bg-rose-500/10"
                              : "border-border",
                            disabled && "opacity-60",
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={isSel}
                            disabled={disabled}
                            onChange={() => toggle(r.question_id)}
                            aria-label={`Soru ${r.question_no ?? "?"} seç`}
                            className="size-4 accent-rose-600"
                          />
                          <div className="min-w-0 flex-1 text-xs">
                            <span className="font-medium text-foreground">
                              Soru {r.question_no ?? "?"}
                            </span>{" "}
                            <span className="text-muted-foreground">
                              · {r.topic_name ?? r.topic_label_raw ?? "—"}
                              {r.correct_answer && r.student_answer
                                ? ` · ${r.student_answer}→${r.correct_answer}`
                                : ""}
                            </span>
                          </div>
                          {r.archived ? (
                            <span className="shrink-0 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-300">
                              arşivde
                            </span>
                          ) : r.topic_id == null ? (
                            <span
                              className="shrink-0 rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300"
                              title='Konusuz soru arşive giremez — "Satırları düzelt" ile konuya bağla'
                            >
                              konusuz
                            </span>
                          ) : isSel ? (
                            <select
                              value={errorTypes[r.question_id] ?? ""}
                              onChange={(e) =>
                                setErrorTypes((p) => ({
                                  ...p,
                                  [r.question_id]: e.target.value,
                                }))
                              }
                              aria-label="Hata türü"
                              className="h-7 shrink-0 rounded border border-border bg-card px-1 text-[11px] text-foreground"
                            >
                              <option value="">Hata türü?</option>
                              {data.error_types.map((t) => (
                                <option key={t.value} value={t.value}>
                                  {t.label}
                                </option>
                              ))}
                            </select>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
              {noTopicCount > 0 ? (
                <p className="text-[11px] text-amber-800 dark:text-amber-300">
                  {`${noTopicCount} soru konuya bağlı olmadığından seçilemez — "Satırları düzelt" ile konuya bağlayınca eklenebilir.`}
                </p>
              ) : null}
            </div>
          )}
        </div>
        <div className="shrink-0 border-t border-border bg-card px-5 py-3">
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={busy}>
              Vazgeç
            </Button>
            <Button
              onClick={() => void submit()}
              disabled={busy || selected.size === 0}
              className="gap-1.5 bg-rose-600 text-white hover:bg-rose-700 hover:text-white"
            >
              {busy ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <BookX className="size-4" aria-hidden />
              )}
              Seçilenleri arşive ekle ({selected.size})
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
