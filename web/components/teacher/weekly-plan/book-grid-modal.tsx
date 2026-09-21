"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Loader2,
  Undo2,
  Wrench,
  X,
} from "lucide-react";

import {
  getTeacherStudentBookGrid,
  teacherKeys,
} from "@/lib/api/teacher";
import type {
  BookCell,
  BookGridResponse,
  BookSectionGrid,
} from "@/lib/types/student";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useReconcileBookCounters,
  useReleaseGridReserved,
  useRevertGridCompleted,
} from "@/lib/hooks/use-teacher-mutations";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  studentId: number;
  bookId: number | null;
}

/**
 * Sinema-koltuğu modal — Jinja `book_grid_content.html` parite.
 *
 * Her bölüm için test sayısı kadar küçük kare:
 *   - emerald → çözüldü (DONE)
 *   - amber   → rezerv (RESERVED, görev atanmış ama henüz yapılmadı)
 *   - slate   → boş (FREE)
 *
 * ÇÖZÜLDÜ ve REZERV karesi tıklanınca bölümün ALTINDA tek satırlık şerit açılır
 * (2026-09-21) — yeşilde "çözülmedi olarak geri al", sarıda "rezervden çıkar";
 * ikisinde de "o günün programı" (hafta ızgarasında görev VURGULANIR: ?task=).
 * Yeşil:
 * "çözülmedi olarak geri al" (öğrenci çözmediği testi işaretlemişse — seansta
 * kaynağa bakınca görülür) + o günün programına git. Koltuklar yer değiştirmez,
 * ek sütun/buton yok → ızgara sıkışmaz.
 *
 * Drift uyarısı: stored counter (section_progress) ile slot-bazlı sayım farklı
 * ise üstte amber uyarı görünür — Jinja'daki davranış aynen.
 */
export function BookGridModal({
  open,
  onOpenChange,
  studentId,
  bookId,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-3xl p-0 overflow-hidden"
        aria-describedby={undefined}
      >
        {open && bookId !== null ? (
          <Body
            studentId={studentId}
            bookId={bookId}
            onClose={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function Body({
  studentId,
  bookId,
  onClose,
}: {
  studentId: number;
  bookId: number;
  onClose: () => void;
}) {
  // Sayaç uyumsuzluğunu koç kendisi düzeltebilsin (2026-09-03): ölü rezerv
  // takılı kalınca o bölüme yeni test atanamıyordu, onarım yalnız SSH ile
  // yapılabiliyordu.
  const reconcile = useReconcileBookCounters(studentId);
  // Seçili yeşil koltuk — şerit o bölümün altında açılır (aynı anda tek seçim).
  const [sel, setSel] = React.useState<{
    sectionId: number;
    number: number;
  } | null>(null);
  const q = useQuery<BookGridResponse>({
    queryKey: teacherKeys.studentBookGrid(studentId, bookId),
    queryFn: () => getTeacherStudentBookGrid(studentId, bookId),
    staleTime: 30_000,
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 px-5 py-8 text-sm text-muted-foreground">
        <DialogTitle className="sr-only">Kitap detayı yükleniyor</DialogTitle>
        <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
      </div>
    );
  }
  if (q.error || !q.data) {
    return (
      <div className="px-5 py-8 text-sm text-rose-600">
        <DialogTitle className="sr-only">Kitap detayı</DialogTitle>
        Kitap detayı yüklenemedi.
      </div>
    );
  }

  const data = q.data;

  // Slot-bazlı toplamlar (drift kontrolü için)
  let slotDone = 0;
  let slotReserved = 0;
  for (const sec of data.sections) {
    for (const c of sec.cells) {
      if (c.state === "DONE") slotDone++;
      else if (c.state === "RESERVED") slotReserved++;
    }
  }
  const totalRemaining = Math.max(
    0,
    data.total_tests - slotDone - slotReserved,
  );
  const hasDrift =
    slotDone !== data.total_completed || slotReserved !== data.total_reserved;
  const isDeneme =
    data.book_type === "brans_denemesi" || data.book_type === "genel_deneme";
  const unitWord = isDeneme ? "deneme" : "test";

  return (
    <>
      <DialogHeader className="px-5 py-4 border-b border-border">
        <DialogTitle className="inline-flex items-center gap-2 text-base">
          <BookOpen className="size-4 text-muted-foreground" aria-hidden />
          {data.book_name}
        </DialogTitle>
        <p className="text-xs text-muted-foreground mt-0.5">
          {data.subject_name} ·{" "}
          <span className="font-medium text-foreground">
            {data.total_tests}
          </span>{" "}
          {unitWord}
        </p>
      </DialogHeader>

      <div className="px-5 py-2 border-b border-border bg-muted/30 flex items-center gap-4 text-xs">
        <span className="text-emerald-700 font-medium tabular-nums">
          ✓ {slotDone} çözüldü
        </span>
        <span className="text-amber-700 font-medium tabular-nums">
          ⏳ {slotReserved} rezerv
        </span>
        <span className="text-foreground font-medium tabular-nums">
          ⎯ {totalRemaining} boş
        </span>
        <span className="ml-auto text-muted-foreground tabular-nums">
          {data.total_tests > 0
            ? `%${Math.round((100 * slotDone) / data.total_tests)} tamamlandı`
            : ""}
        </span>
      </div>

      {hasDrift ? (
        <div className="px-5 py-2 border-b border-amber-200 bg-amber-50 text-[11px] text-amber-900 flex items-start gap-2 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
          <AlertTriangle
            className="size-3.5 text-amber-700 flex-shrink-0 mt-0.5"
            aria-hidden
          />
          <div className="flex-1">
            <b>Sayaç uyumsuzluğu:</b> kayıtlı sayaç (rezerv{" "}
            {data.total_reserved} · çözüldü {data.total_completed}) gerçek
            görev listesinden farklı (rezerv {slotReserved} · çözüldü{" "}
            {slotDone}). Aşağıdaki görünüm gerçek görevlerden üretilmiştir.
            <div className="mt-1.5">
              <button
                type="button"
                disabled={reconcile.isPending}
                onClick={() => reconcile.mutate({ bookId })}
                className="inline-flex items-center gap-1.5 rounded-md border border-amber-400 bg-amber-100 px-2 py-1 text-[11px] font-medium text-amber-900 hover:bg-amber-200 disabled:opacity-50 dark:bg-amber-500/20 dark:text-amber-100 dark:hover:bg-amber-500/30"
                title="Sayaçları gerçek görev listesinden yeniden hesapla — takılı kalan rezerv serbest kalır"
              >
                {reconcile.isPending ? (
                  <Loader2 className="size-3 animate-spin" aria-hidden />
                ) : (
                  <Wrench className="size-3" aria-hidden />
                )}
                Sayaçları düzelt
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="p-5 max-h-[70vh] overflow-y-auto space-y-5">
        {data.sections.length === 0 ? (
          <div className="text-center text-sm text-muted-foreground italic py-8">
            Bu kitabın bölümü tanımlanmamış.
          </div>
        ) : (
          data.sections.map((sec) => (
            <SectionGrid
              key={sec.section_id}
              section={sec}
              studentId={studentId}
              bookId={bookId}
              unitWord={unitWord}
              onClose={onClose}
              selectedNumber={
                sel?.sectionId === sec.section_id ? sel.number : null
              }
              onSelect={(n) =>
                setSel(
                  n === null ? null : { sectionId: sec.section_id, number: n },
                )
              }
            />
          ))
        )}
      </div>

      <footer className="px-5 py-2 border-t border-border bg-muted/30 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        <Legend tone="emerald" label="çözüldü" />
        <Legend tone="amber" label="rezervde (görev atanmış)" />
        <Legend tone="slate" label="henüz boş" />
        <span className="ml-auto italic">
          Her kutu bir {unitWord} · üzerine gel → tarih · yeşile/sarıya tıkla
          → geri al · rezervden çıkar · güne git
        </span>
      </footer>
    </>
  );
}

function SectionGrid({
  section,
  studentId,
  bookId,
  unitWord,
  onClose,
  selectedNumber,
  onSelect,
}: {
  section: BookSectionGrid;
  studentId: number;
  bookId: number;
  unitWord: string;
  onClose: () => void;
  selectedNumber: number | null;
  onSelect: (n: number | null) => void;
}) {
  // Slot-bazlı yeniden say (drift-proof, Jinja gibi)
  let comp = 0;
  let res = 0;
  for (const c of section.cells) {
    if (c.state === "DONE") comp++;
    else if (c.state === "RESERVED") res++;
  }
  const remaining = Math.max(0, section.test_count - comp - res);
  const secDrift = section.completed !== comp || section.reserved !== res;
  const selectedCell =
    selectedNumber === null
      ? null
      : (section.cells.find(
          (c) => c.number === selectedNumber && c.state !== "FREE",
        ) ?? null);
  // Aynı görevin bu bölümdeki AYNI durumdaki koltuk sayısı ("tümünü …")
  const sameTaskDone = selectedCell
    ? section.cells.filter(
        (c) =>
          c.state === selectedCell.state &&
          (c.task_id ?? null) === (selectedCell.task_id ?? null),
      ).length
    : 0;

  return (
    <section>
      <div className="flex items-baseline justify-between mb-2 gap-2 flex-wrap">
        <h3 className="text-sm font-semibold text-foreground">
          {section.label}
          {section.topic_name ? (
            <span className="text-muted-foreground italic font-normal">
              {" "}· {section.topic_name}
            </span>
          ) : null}
          {secDrift ? (
            <span
              className="ml-1.5 text-[10px] font-normal text-amber-700 bg-amber-50 border border-amber-200 rounded px-1 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200"
              title={`Kayıtlı: rezerv ${section.reserved} · çözüldü ${section.completed}. Gerçek görevlerden çıkan değer farklı.`}
            >
              sayaç uyumsuz
            </span>
          ) : null}
        </h3>
        <div className="text-xs text-muted-foreground whitespace-nowrap tabular-nums">
          <span className="text-emerald-700">{comp}</span> /{" "}
          <span className="text-amber-700">{res}</span> /{" "}
          <b className="text-foreground">{remaining}</b>
          <span className="text-muted-foreground/60"> · {section.test_count}</span>
        </div>
      </div>
      <div
        className="grid gap-1"
        style={{
          gridTemplateColumns: "repeat(auto-fill, minmax(22px, 1fr))",
        }}
      >
        {section.cells.map((cell) => (
          <Cell
            key={cell.number}
            cell={cell}
            unitWord={unitWord}
            selected={selectedNumber === cell.number}
            onSelect={() =>
              onSelect(selectedNumber === cell.number ? null : cell.number)
            }
          />
        ))}
      </div>
      {selectedCell ? (
        <RevertStrip
          cell={selectedCell}
          sameTaskDone={sameTaskDone}
          studentId={studentId}
          bookId={bookId}
          sectionId={section.section_id}
          unitWord={unitWord}
          onClose={onClose}
          onDismiss={() => onSelect(null)}
        />
      ) : null}
    </section>
  );
}

function Cell({
  cell,
  unitWord,
  selected,
  onSelect,
}: {
  cell: BookCell;
  unitWord: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const Unit = `${unitWord.charAt(0).toUpperCase()}${unitWord.slice(1)}`;
  if (cell.state === "DONE") {
    // Yeşil koltuk = buton: tıkla → bölüm altında şerit (geri al / güne git)
    return (
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className={cn(
          "aspect-square rounded-sm bg-emerald-500 hover:scale-125 hover:ring-2 hover:ring-emerald-700 transition-transform block",
          selected &&
            "ring-2 ring-offset-1 ring-offset-background ring-foreground scale-110",
        )}
        title={
          cell.task_date
            ? `${Unit} ${cell.number} · ${cell.task_date} tarihinde çözüldü işaretlendi — tıkla: geri al / güne git`
            : `${Unit} ${cell.number}: önceden çözülmüş (göreve bağlı değil) — tıkla: geri al`
        }
      />
    );
  }
  if (cell.state === "FREE") {
    return (
      <div
        className="aspect-square rounded-sm bg-muted border border-border/60 hover:scale-110 transition-transform"
        title={`${unitWord.charAt(0).toUpperCase()}${unitWord.slice(1)} ${cell.number}: henüz boş`}
      />
    );
  }
  // Sarı koltuk = buton: tıkla → bölüm altında şerit (rezervden çıkar / güne git)
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "aspect-square rounded-sm bg-amber-400 hover:scale-125 hover:ring-2 hover:ring-amber-600 transition-transform block",
        selected &&
          "ring-2 ring-offset-1 ring-offset-background ring-foreground scale-110",
      )}
      title={`${Unit} ${cell.number} · ${cell.task_date ?? "—"} tarihli görevde rezerve (henüz çözülmedi) — tıkla: rezervden çıkar / güne git`}
    />
  );
}

/** Seçili yeşil koltuk için bölüm altı şerit — koltuk düzenini bozmaz. */
function RevertStrip({
  cell,
  sameTaskDone,
  studentId,
  bookId,
  sectionId,
  unitWord,
  onClose,
  onDismiss,
}: {
  cell: BookCell;
  sameTaskDone: number;
  studentId: number;
  bookId: number;
  sectionId: number;
  unitWord: string;
  onClose: () => void;
  onDismiss: () => void;
}) {
  const revertMut = useRevertGridCompleted(studentId);
  const releaseMut = useReleaseGridReserved(studentId);
  const isReserved = cell.state === "RESERVED";
  const mut = isReserved ? releaseMut : revertMut;
  const taskId = cell.task_id ?? null;
  // "2026-09-01" → "01.09.2026"
  const dateTr = cell.task_date
    ? cell.task_date.split("-").reverse().join(".")
    : null;
  const run = (count: number) => {
    if (isReserved) {
      if (taskId === null) return;
      releaseMut.mutate(
        { bookId, sectionId, taskId, count },
        { onSuccess: onDismiss },
      );
    } else {
      revertMut.mutate(
        { bookId, sectionId, taskId, count },
        { onSuccess: onDismiss },
      );
    }
  };
  return (
    <div
      data-section="book-grid:revert-strip"
      className="mt-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-foreground">
          {isReserved ? (
            <>
              <b>{dateTr}</b> tarihli görevde bekliyor (rezerv)
              {sameTaskDone > 1
                ? ` — bu görevden ${sameTaskDone} ${unitWord}`
                : ""}
              .
            </>
          ) : cell.task_date ? (
            <>
              <b>{dateTr}</b> tarihli görevde çözüldü işaretlenmiş
              {sameTaskDone > 1
                ? ` (bu görevden ${sameTaskDone} ${unitWord})`
                : ""}
              .
            </>
          ) : (
            <>Göreve bağlı değil — önceden çözülmüş olarak işlenmiş.</>
          )}{" "}
          <span className="text-muted-foreground">
            {isReserved
              ? `Rezervden çıkarırsan görevin ${unitWord} sayısı düşer; görevde başka ${unitWord} kalmazsa görev programdan silinir.`
              : `Öğrenci aslında çözmediyse geri al: görev silinmez, geri alınan ${unitWord} yeniden atanabilir olur.`}
          </span>
        </p>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Kapat"
          className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X className="size-3.5" aria-hidden />
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={mut.isPending}
          onClick={() => run(1)}
          className="inline-flex items-center gap-1.5 rounded-md bg-rose-600 px-2.5 py-1 font-medium text-white hover:bg-rose-700 disabled:opacity-50"
        >
          {mut.isPending ? (
            <Loader2 className="size-3 animate-spin" aria-hidden />
          ) : (
            <Undo2 className="size-3" aria-hidden />
          )}
          {isReserved ? `1 ${unitWord} rezervden çıkar` : `1 ${unitWord} geri al`}
        </button>
        {sameTaskDone > 1 ? (
          <button
            type="button"
            disabled={mut.isPending}
            onClick={() => run(sameTaskDone)}
            className="inline-flex items-center gap-1.5 rounded-md border border-rose-300 px-2.5 py-1 font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-500/40 dark:text-rose-300 dark:hover:bg-rose-500/10"
          >
            {isReserved
              ? "Bu görevin tüm rezervini kaldır"
              : cell.task_date
                ? "Bu görevin tümünü geri al"
                : "Hepsini geri al"}{" "}
            ({sameTaskDone} {unitWord})
          </button>
        ) : null}
        {cell.task_date ? (
          <Link
            href={`/teacher/students/${studentId}/week?start=${encodeURIComponent(cell.task_date)}${taskId !== null ? `&task=${taskId}` : ""}`}
            onClick={onClose}
            className="ml-auto inline-flex items-center gap-1 text-muted-foreground hover:text-foreground hover:underline"
          >
            O günün programında göster
            <ArrowRight className="size-3" aria-hidden />
          </Link>
        ) : null}
      </div>
    </div>
  );
}

function Legend({
  tone,
  label,
}: {
  tone: "emerald" | "amber" | "slate";
  label: string;
}) {
  const cls = {
    emerald: "bg-emerald-500",
    amber: "bg-amber-400",
    slate: "bg-muted border border-border/60",
  }[tone];
  return (
    <span className="inline-flex items-center gap-1">
      <span className={cn("inline-block w-3 h-3 rounded-sm", cls)} />
      {label}
    </span>
  );
}
