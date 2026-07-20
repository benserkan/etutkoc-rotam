"use client";

import * as React from "react";
import { Check, Loader2, TentTree, Trash2, Undo2, X } from "lucide-react";

import type {
  SelfStudyCreateBody,
  SelfStudyEntryItem,
  SelfStudyOptionBook,
} from "@/lib/types/self-study";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/**
 * Bağımsız çalışma — paylaşılan giriş dialogu + kayıt listesi.
 * Koç (doğrudan giriş + onay/silme) ve öğrenci (beyan + geri çekme) aynı
 * bileşenleri kullanır; fark yalnız metin ve aksiyonlarda.
 */

const STATUS_TONE: Record<string, string> = {
  pending:
    "bg-amber-500/10 border-amber-500/30 text-amber-800 dark:text-amber-200",
  approved:
    "bg-emerald-500/10 border-emerald-500/30 text-emerald-800 dark:text-emerald-200",
  rejected: "bg-rose-500/10 border-rose-500/30 text-rose-800 dark:text-rose-200",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function SelfStudyStatusChip({ item }: { item: SelfStudyEntryItem }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        STATUS_TONE[item.status] ?? "border-border text-muted-foreground",
      )}
    >
      {item.status_label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Giriş dialogu (kitap → bölüm başına test sayısı → not/dönem)
// ---------------------------------------------------------------------------

export function SelfStudyEntryDialog({
  open,
  onOpenChange,
  books,
  mode,
  isPending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  books: SelfStudyOptionBook[];
  mode: "coach" | "student";
  isPending: boolean;
  onSubmit: (body: SelfStudyCreateBody) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TentTree className="size-5 text-cyan-600 dark:text-cyan-400" aria-hidden />
            Bağımsız çalışma {mode === "coach" ? "girişi" : "bildir"}
          </DialogTitle>
        </DialogHeader>
        {open ? (
          <SelfStudyEntryForm
            books={books}
            mode={mode}
            isPending={isPending}
            onSubmit={onSubmit}
            onCancel={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function SelfStudyEntryForm({
  books,
  mode,
  isPending,
  onSubmit,
  onCancel,
}: {
  books: SelfStudyOptionBook[];
  mode: "coach" | "student";
  isPending: boolean;
  onSubmit: (body: SelfStudyCreateBody) => void;
  onCancel: () => void;
}) {
  const [bookId, setBookId] = React.useState<number | null>(null);
  const [counts, setCounts] = React.useState<Record<number, number>>({});
  const [note, setNote] = React.useState("");
  const [periodStart, setPeriodStart] = React.useState("");
  const [periodEnd, setPeriodEnd] = React.useState("");

  const book = books.find((b) => b.student_book_id === bookId) ?? null;
  const totalEntered = Object.values(counts).reduce((s, v) => s + (v || 0), 0);

  // Ders bazlı gruplu seçenekler
  const grouped = React.useMemo(() => {
    const map = new Map<string, SelfStudyOptionBook[]>();
    for (const b of books) {
      const arr = map.get(b.subject_name);
      if (arr) arr.push(b);
      else map.set(b.subject_name, [b]);
    }
    return Array.from(map.entries());
  }, [books]);

  function pickBook(id: number | null) {
    setBookId(id);
    setCounts({});
  }

  function setCount(sectionId: number, v: number, max: number) {
    setCounts((prev) => ({
      ...prev,
      [sectionId]: Math.max(0, Math.min(v, max)),
    }));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!book) return;
    const items = book.sections
      .filter((s) => (counts[s.section_id] || 0) > 0)
      .map((s) => ({
        student_book_id: book.student_book_id,
        section_id: s.section_id,
        test_count: counts[s.section_id],
      }));
    if (items.length === 0) return;
    onSubmit({
      items,
      note: note.trim() || null,
      period_start: periodStart || null,
      period_end: periodEnd || null,
    });
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {mode === "coach"
          ? "Programa girmeden (tatil, kurs, kendi çalışması) çözülen testleri işle — kayıt izli tutulur, kitap ilerlemesi ve öneriler güncellenir."
          : "Programında olmadan kendi başına çözdüğün testleri bildir — koçun onaylayınca ilerlemene işlenir."}
      </p>

      <div className="space-y-1.5">
        <label htmlFor="ss-book" className="text-sm font-medium">
          Kitap
        </label>
        <select
          id="ss-book"
          value={bookId === null ? "" : String(bookId)}
          onChange={(e) => pickBook(e.target.value ? Number(e.target.value) : null)}
          className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">— Kitap seç —</option>
          {grouped.map(([subject, arr]) => (
            <optgroup key={subject} label={subject}>
              {arr.map((b) => (
                <option key={b.student_book_id} value={b.student_book_id}>
                  {b.book_name} · {b.book_type_label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {book ? (
        <div className="max-h-[38vh] overflow-y-auto rounded-md border border-border divide-y divide-border">
          {book.sections.map((s) => {
            const val = counts[s.section_id] || 0;
            const disabled = s.remaining <= 0;
            return (
              <div
                key={s.section_id}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 text-sm",
                  disabled && "opacity-50",
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate">{s.label}</p>
                  <p className="text-[11px] text-muted-foreground tabular-nums">
                    {s.remaining} boş / {s.test_count} test
                    {s.reserved_count > 0 ? ` · ${s.reserved_count} planda` : ""}
                    {s.completed_count > 0 ? ` · ${s.completed_count} çözülmüş` : ""}
                  </p>
                </div>
                {disabled ? (
                  <span className="text-[11px] text-muted-foreground">kapasite yok</span>
                ) : (
                  <>
                    <input
                      type="number"
                      min={0}
                      max={s.remaining}
                      value={val === 0 ? "" : val}
                      placeholder="0"
                      onChange={(e) =>
                        setCount(s.section_id, Number(e.target.value) || 0, s.remaining)
                      }
                      className="h-8 w-16 rounded border border-input bg-background px-1.5 text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label={`${s.label} çözülen test`}
                    />
                    <button
                      type="button"
                      onClick={() => setCount(s.section_id, s.remaining, s.remaining)}
                      className="rounded border border-border px-1.5 py-1 text-[11px] hover:bg-muted"
                    >
                      Tümü
                    </button>
                  </>
                )}
              </div>
            );
          })}
        </div>
      ) : null}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label htmlFor="ss-pstart" className="text-sm font-medium">
            Dönem (başlangıç)
          </label>
          <input
            id="ss-pstart"
            type="date"
            value={periodStart}
            onChange={(e) => setPeriodStart(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="ss-pend" className="text-sm font-medium">
            Dönem (bitiş)
          </label>
          <input
            id="ss-pend"
            type="date"
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="ss-note" className="text-sm font-medium">
          Not <span className="font-normal text-muted-foreground">(isteğe bağlı)</span>
        </label>
        <textarea
          id="ss-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          maxLength={500}
          placeholder={
            mode === "coach"
              ? "Örn: Köyde internetsiz dönemde kendi çalıştı."
              : "Örn: Köydeydim, internet yoktu — kendi çalıştım."
          }
          className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <div className="flex items-center justify-between gap-2 pt-1 border-t border-border">
        <p className="text-xs text-muted-foreground tabular-nums">
          {totalEntered > 0 ? `Toplam ${totalEntered} test` : "Bölümlere test sayısı gir"}
        </p>
        <div className="flex items-center gap-2">
          <Button type="button" variant="ghost" onClick={onCancel} disabled={isPending}>
            İptal
          </Button>
          <Button type="submit" disabled={isPending || totalEntered === 0 || !book}>
            {isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            {mode === "coach" ? "İlerlemeye işle" : "Koça gönder"}
          </Button>
        </div>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Kayıt listesi (satır + aksiyonlar)
// ---------------------------------------------------------------------------

export function SelfStudyEntryRow({
  item,
  onApprove,
  onReject,
  onDelete,
  onWithdraw,
  isBusy,
}: {
  item: SelfStudyEntryItem;
  onApprove?: () => void;
  onReject?: () => void;
  onDelete?: () => void;
  onWithdraw?: () => void;
  isBusy?: boolean;
}) {
  const period =
    item.period_start || item.period_end
      ? `${fmtDate(item.period_start)} – ${fmtDate(item.period_end)}`
      : null;
  return (
    <li className="flex flex-wrap items-start gap-2 py-2 text-sm">
      <div className="min-w-0 flex-1">
        <p className="truncate">
          <span className="font-medium">{item.book_name}</span>
          <span className="text-muted-foreground"> · {item.section_label}</span>
        </p>
        <p className="text-xs text-muted-foreground">
          <span className="tabular-nums font-medium text-foreground">
            {item.status === "approved" ? item.applied_count : item.test_count} test
          </span>
          {item.status === "approved" && item.applied_count < item.test_count ? (
            <span> (istenen {item.test_count} — kapasiteye kırpıldı)</span>
          ) : null}
          {" · "}
          {item.source_label}
          {" · "}
          {fmtDate(item.created_at)}
          {period ? ` · dönem ${period}` : ""}
        </p>
        {item.note ? (
          <p className="text-xs text-muted-foreground italic mt-0.5">“{item.note}”</p>
        ) : null}
        {item.status === "rejected" && item.review_note ? (
          <p className="text-xs text-rose-700 dark:text-rose-300 mt-0.5">
            Koç notu: {item.review_note}
          </p>
        ) : null}
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <SelfStudyStatusChip item={item} />
        {onApprove && item.status === "pending" ? (
          <Button
            size="sm"
            className="h-7 bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white"
            onClick={onApprove}
            disabled={isBusy}
          >
            <Check className="size-3.5" aria-hidden /> Onayla
          </Button>
        ) : null}
        {onReject && item.status === "pending" ? (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-rose-600 hover:text-rose-700 dark:text-rose-400"
            onClick={onReject}
            disabled={isBusy}
          >
            <X className="size-3.5" aria-hidden /> Reddet
          </Button>
        ) : null}
        {onWithdraw && item.status === "pending" ? (
          <Button
            size="sm"
            variant="ghost"
            className="h-7"
            onClick={onWithdraw}
            disabled={isBusy}
          >
            <Undo2 className="size-3.5" aria-hidden /> Geri çek
          </Button>
        ) : null}
        {onDelete ? (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-muted-foreground"
            onClick={onDelete}
            disabled={isBusy}
            aria-label="Kaydı sil"
          >
            <Trash2 className="size-3.5" aria-hidden />
          </Button>
        ) : null}
      </div>
    </li>
  );
}
