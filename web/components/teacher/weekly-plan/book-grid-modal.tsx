"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BookOpen, Loader2 } from "lucide-react";

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
 * Çözüldü/Rezerv kareleri tıklanınca o görevin haftalık planı sayfasına gider
 * (start={task_date}). Modal kapanır.
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
      <DialogContent className="max-w-3xl p-0 overflow-hidden">
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
  const q = useQuery<BookGridResponse>({
    queryKey: teacherKeys.studentBookGrid(studentId, bookId),
    queryFn: () => getTeacherStudentBookGrid(studentId, bookId),
    staleTime: 30_000,
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 px-5 py-8 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
      </div>
    );
  }
  if (q.error || !q.data) {
    return (
      <div className="px-5 py-8 text-sm text-rose-600">
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
        <div className="px-5 py-2 border-b border-amber-200 bg-amber-50 text-[11px] text-amber-900 flex items-start gap-2">
          <AlertTriangle
            className="size-3.5 text-amber-700 flex-shrink-0 mt-0.5"
            aria-hidden
          />
          <div>
            <b>Sayaç uyumsuzluğu:</b> kayıtlı sayaç (rezerv{" "}
            {data.total_reserved} · çözüldü {data.total_completed}) gerçek
            görev listesinden farklı (rezerv {slotReserved} · çözüldü{" "}
            {slotDone}). Aşağıdaki görünüm gerçek görevlerden üretilmiştir.
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
              unitWord={unitWord}
              onClose={onClose}
            />
          ))
        )}
      </div>

      <footer className="px-5 py-2 border-t border-border bg-muted/30 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        <Legend tone="emerald" label="çözüldü" />
        <Legend tone="amber" label="rezervde (görev atanmış)" />
        <Legend tone="slate" label="henüz boş" />
        <span className="ml-auto italic">
          Her kutu bir {unitWord} · üzerine gel → tarih · tıkla → o günün
          programı
        </span>
      </footer>
    </>
  );
}

function SectionGrid({
  section,
  studentId,
  unitWord,
  onClose,
}: {
  section: BookSectionGrid;
  studentId: number;
  unitWord: string;
  onClose: () => void;
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
              className="ml-1.5 text-[10px] font-normal text-amber-700 bg-amber-50 border border-amber-200 rounded px-1"
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
            studentId={studentId}
            unitWord={unitWord}
            onClose={onClose}
          />
        ))}
      </div>
    </section>
  );
}

function Cell({
  cell,
  studentId,
  unitWord,
  onClose,
}: {
  cell: BookCell;
  studentId: number;
  unitWord: string;
  onClose: () => void;
}) {
  if (cell.state === "FREE") {
    return (
      <div
        className="aspect-square rounded-sm bg-muted border border-border/60 hover:scale-110 transition-transform"
        title={`${unitWord.charAt(0).toUpperCase()}${unitWord.slice(1)} ${cell.number}: henüz boş`}
      />
    );
  }
  // DONE veya RESERVED — tıklanabilir
  const tone =
    cell.state === "DONE"
      ? "bg-emerald-500 hover:ring-emerald-700"
      : "bg-amber-400 hover:ring-amber-600";
  const verb =
    cell.state === "DONE"
      ? "çözüldü"
      : "rezerve (henüz çözülmedi)";
  const dateLabel = cell.task_date ?? "—";
  const href = cell.task_date
    ? `/teacher/students/${studentId}/week?start=${encodeURIComponent(cell.task_date)}`
    : `/teacher/students/${studentId}/week`;
  return (
    <Link
      href={href}
      onClick={onClose}
      className={cn(
        "aspect-square rounded-sm hover:scale-125 hover:ring-2 transition-transform block",
        tone,
      )}
      title={`${unitWord.charAt(0).toUpperCase()}${unitWord.slice(1)} ${cell.number} · ${dateLabel} tarihinde ${verb} → o günün programına git`}
    />
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
