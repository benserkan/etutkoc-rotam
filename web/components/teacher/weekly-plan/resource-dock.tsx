"use client";

/**
 * Kaynak Durumu — ALT PANEL (2026-10-08, koç denemesi).
 *
 * Koç ekran kullanımı: en çok Hafta Izgarası + Kaynak Durumu'nda çalışıyor,
 * ama Kaynak Durumu sağ panelde gün kartı hizasından başladığı için her
 * görevde ızgaraya bakmak için yukarı-aşağı kaydırıyordu. Izgarayı daraltmamak
 * (sütunlar zaten dar) için Kaynak Durumu sayfanın ALTINA yapışık panel olur:
 * sayfa ne kadar kaydırılırsa kaydırılsın görünür.
 *
 *   [ders listesi] | [seçili dersin kitapları yan yana → üniteler]
 *
 * Ünite satırı: "+" → seçili güne "Kaç test?" · ya da satırı ızgaradaki bir
 * günün üstüne SÜRÜKLE → orada "Kaç test?" açılır (week-grid).
 * Yükseklik üst kenardan ayarlanır, panel tek çubuğa katlanır; tercih
 * tarayıcıda saklanır. "Yana al" eski sağ panel düzenine döndürür.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, GripHorizontal, Grid3x3, Library, PanelRight, Plus } from "lucide-react";

import { AssignCountChooser } from "./assign-count-chooser";
import { SubjectTag, subjectColors } from "@/components/shared/subject-tag";
import { getTaskQuantity, teacherKeys } from "@/lib/api/teacher";
import { useCreateTask } from "@/lib/hooks/use-teacher-mutations";
import { useLocalPref } from "@/lib/hooks/use-local-pref";
import type { SidebarBook, SidebarResponse, SidebarSection } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

/** Izgaraya sürüklenen ünite (week-grid bu türü kabul eder). */
export const RESOURCE_SECTION_MIME = "text/x-resource-section";

export interface ResourceSectionDragPayload {
  bookId: number;
  bookName: string;
  bookType: string;
  sectionId: number;
  sectionLabel: string;
  remaining: number;
  subjectId: number;
}

export const DOCK_PREF_KEY = "rotam:week:resource-dock";
export interface DockPref {
  /** true → Kaynak Durumu alt panelde (sağ panelden kalkar) */
  enabled: boolean;
  collapsed: boolean;
  height: number;
  subjectId: number | null;
}
export const DOCK_PREF_DEFAULT: DockPref = {
  enabled: true,
  collapsed: false,
  height: 260,
  subjectId: null,
};

const MIN_H = 140;
const BAR_H = 40;

const TR_DOW = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
function dayLabel(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return `${TR_DOW[d.getDay()]} ${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function unitWordOf(book: SidebarBook): string {
  return book.type === "brans_denemesi" || book.type === "genel_deneme" ? "deneme" : "test";
}

export function ResourceDock({
  data,
  studentId,
  dayDate,
  onOpenBookGrid,
  focusedSubjectId,
  onClearFocus,
}: {
  data: SidebarResponse | undefined;
  studentId: number;
  /** Aktif gün — "+" bu güne yazar */
  dayDate: string;
  onOpenBookGrid?: (bookId: number) => void;
  focusedSubjectId: number | null;
  onClearFocus: () => void;
}) {
  const [pref, setPref] = useLocalPref<DockPref>(DOCK_PREF_KEY, DOCK_PREF_DEFAULT);
  const subjects = data?.subjects ?? [];
  const selected =
    subjects.find((s) => s.id === pref.subjectId) ?? subjects[0] ?? null;

  // ---- yükseklik: üst kenardan sürükle
  const [dragH, setDragH] = React.useState<number | null>(null);
  const startRef = React.useRef<{ y: number; h: number } | null>(null);
  function onResizeStart(e: React.PointerEvent) {
    e.preventDefault();
    startRef.current = { y: e.clientY, h: pref.height };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onResizeMove(e: React.PointerEvent) {
    if (!startRef.current) return;
    const max = Math.round(window.innerHeight * 0.7);
    const h = Math.min(max, Math.max(MIN_H, startRef.current.h + (startRef.current.y - e.clientY)));
    setDragH(h);
  }
  function onResizeEnd() {
    if (startRef.current && dragH !== null) setPref({ ...pref, height: dragH });
    startRef.current = null;
    setDragH(null);
  }
  const height = dragH ?? pref.height;

  return (
    <section
      aria-label="Kaynak Durumu (alt panel)"
      data-testid="resource-dock"
      data-collapsed={pref.collapsed ? "1" : "0"}
      className="sticky bottom-0 z-30 -mx-1 rounded-t-lg border border-b-0 border-border bg-card shadow-[0_-6px_18px_-8px_rgba(0,0,0,0.35)]"
    >
      {!pref.collapsed ? (
        <div
          role="separator"
          aria-orientation="horizontal"
          aria-label="Paneli büyüt/küçült"
          title="Sürükle: paneli büyüt / küçült"
          onPointerDown={onResizeStart}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeEnd}
          onPointerCancel={onResizeEnd}
          className="flex h-2.5 cursor-row-resize items-center justify-center text-muted-foreground/60 hover:text-foreground"
          data-testid="resource-dock-resize"
        >
          <GripHorizontal className="size-3.5" aria-hidden />
        </div>
      ) : null}

      {/* Başlık çubuğu */}
      <div
        className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3"
        style={{ minHeight: BAR_H }}
      >
        <span className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
          <Library className="size-4" aria-hidden /> Kaynak Durumu
        </span>
        {data ? (
          <span className="text-[11px] tabular-nums text-muted-foreground">
            <span className="text-emerald-600 dark:text-emerald-300">✓{data.grand_completed}</span>{" "}
            <span className="text-amber-600 dark:text-amber-300">⏳{data.grand_reserved}</span>{" "}
            <b className="text-foreground">⎯{data.grand_remaining}</b> kalan
          </span>
        ) : null}
        <span
          className="rounded bg-cyan-600 px-1.5 py-0.5 text-[11px] font-medium text-white"
          title="“+” düğmesi bu güne ekler. Başka güne eklemek için üniteyi ızgaradaki güne sürükle."
          data-testid="resource-dock-day"
        >
          “+” → {dayLabel(dayDate)}
        </span>
        <span className="hidden text-[11px] text-muted-foreground md:inline">
          ya da üniteyi ızgarada bir güne sürükle
        </span>
        {focusedSubjectId !== null ? (
          <button
            type="button"
            onClick={onClearFocus}
            className="text-[11px] text-indigo-600 underline hover:text-indigo-800 dark:text-indigo-300"
          >
            Tüm dersler
          </button>
        ) : null}
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => setPref({ ...pref, enabled: false })}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Kaynak Durumu'nu sağ panele geri taşı"
          data-testid="resource-dock-side"
        >
          <PanelRight className="size-3.5" aria-hidden /> Yana al
        </button>
        <button
          type="button"
          onClick={() => setPref({ ...pref, collapsed: !pref.collapsed })}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-expanded={!pref.collapsed}
          data-testid="resource-dock-toggle"
        >
          {pref.collapsed ? (
            <>
              <ChevronUp className="size-3.5" aria-hidden /> Aç
            </>
          ) : (
            <>
              <ChevronDown className="size-3.5" aria-hidden /> Katla
            </>
          )}
        </button>
      </div>

      {!pref.collapsed ? (
        <div className="flex min-h-0" style={{ height: height - BAR_H }}>
          {/* Ders listesi */}
          <ul
            className="w-48 shrink-0 overflow-y-auto border-r border-border py-1"
            aria-label="Dersler"
          >
            {subjects.length === 0 ? (
              <li className="px-3 py-2 text-xs text-muted-foreground">Atanmış kitap yok.</li>
            ) : (
              subjects.map((s) => {
                const active = selected?.id === s.id;
                const pct = s.summary.total > 0 ? (100 * s.summary.completed) / s.summary.total : 0;
                const res = s.summary.total > 0 ? (100 * s.summary.reserved) / s.summary.total : 0;
                return (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => setPref({ ...pref, subjectId: s.id })}
                      aria-pressed={active}
                      data-testid="resource-dock-subject"
                      className={cn(
                        "w-full border-l-4 px-2 py-1.5 text-left transition",
                        active ? "bg-muted" : "border-l-transparent hover:bg-muted/50",
                      )}
                      style={active ? { borderLeftColor: subjectColors(s.name).rail } : undefined}
                    >
                      <SubjectTag name={s.name} size="xs" />
                      <div className="mt-1 flex h-1 overflow-hidden rounded-full bg-muted-foreground/15">
                        <span className="bg-emerald-500" style={{ width: `${pct}%` }} />
                        <span className="bg-amber-400" style={{ width: `${res}%` }} />
                      </div>
                      <div className="mt-0.5 text-[10px] tabular-nums text-muted-foreground">
                        ⎯{s.summary.remaining} kalan · {s.summary.books_count} kitap
                      </div>
                    </button>
                  </li>
                );
              })
            )}
          </ul>

          {/* Seçili dersin kitapları yan yana */}
          {selected ? (
            <BooksStrip
              key={selected.id}
              studentId={studentId}
              subjectId={selected.id}
              books={selected.books}
              dayDate={dayDate}
              onOpenBookGrid={onOpenBookGrid}
            />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function BooksStrip({
  studentId,
  subjectId,
  books,
  dayDate,
  onOpenBookGrid,
}: {
  studentId: number;
  subjectId: number;
  books: SidebarBook[];
  dayDate: string;
  onOpenBookGrid?: (bookId: number) => void;
}) {
  const qtyQ = useQuery({
    queryKey: teacherKeys.taskQuantity(studentId, subjectId),
    queryFn: () => getTaskQuantity(studentId, subjectId),
    staleTime: 5 * 60_000,
  });
  const defaultCount = qtyQ.data?.quantity ?? 3;
  const qtyHint = qtyQ.data?.reason ?? null;
  const create = useCreateTask(studentId);
  function assign(book: SidebarBook, section: SidebarSection, count: number) {
    create.mutate({
      body: {
        date: dayDate,
        type: "test",
        title: `${book.name} — ${section.label}: ${count} ${unitWordOf(book)}`,
        scheduled_hour: null,
        period: null,
        items: [
          {
            book_id: book.id,
            section_id: section.id,
            planned_count: count,
            allow_over_capacity: count > section.remaining,
          },
        ],
      },
    });
  }

  return (
    <div className="flex min-w-0 flex-1 gap-2 overflow-x-auto p-2 pr-28" data-testid="resource-dock-books">
      {books.map((b) => {
        const pct = b.total > 0 ? (100 * b.completed) / b.total : 0;
        const res = b.total > 0 ? (100 * b.reserved) / b.total : 0;
        return (
          <div
            key={b.id}
            className="flex w-72 shrink-0 flex-col overflow-hidden rounded-md border border-border bg-background"
            data-testid="resource-dock-book"
          >
            <div className="flex items-start gap-2 border-b border-border px-2.5 py-1.5">
              <div className="min-w-0 flex-1">
                <p className="break-words text-[12.5px] font-medium leading-tight text-foreground">
                  {b.name}
                </p>
                <div className="mt-1 flex h-1 overflow-hidden rounded-full bg-muted">
                  <span className="bg-emerald-500" style={{ width: `${pct}%` }} />
                  <span className="bg-amber-400" style={{ width: `${res}%` }} />
                </div>
                <p className="mt-0.5 text-[10.5px] tabular-nums text-muted-foreground">
                  <span className="text-emerald-600 dark:text-emerald-300">✓{b.completed}</span>{" "}
                  <span className="text-amber-600 dark:text-amber-300">⏳{b.reserved}</span>{" "}
                  <b className="text-foreground">kalan {b.remaining}</b> / {b.total}
                </p>
              </div>
              {onOpenBookGrid ? (
                <button
                  type="button"
                  onClick={() => onOpenBookGrid(b.id)}
                  title="Test detayını sinema-koltuğu görünümüyle aç"
                  aria-label="Sinema-koltuğu görünümü"
                  className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <Grid3x3 className="size-3.5" aria-hidden />
                </button>
              ) : null}
            </div>
            <ul className="min-h-0 flex-1 divide-y divide-border overflow-y-auto">
              {b.sections.length === 0 ? (
                <li className="px-2.5 py-2 text-[11px] italic text-muted-foreground">
                  Bu kitapta tanımlı ünite yok.
                </li>
              ) : (
                b.sections.map((sec) => (
                  <DockSectionRow
                    key={sec.id}
                    book={b}
                    section={sec}
                    subjectId={subjectId}
                    defaultCount={defaultCount}
                    qtyHint={qtyHint}
                    pending={create.isPending}
                    onAssign={(n) => assign(b, sec, n)}
                  />
                ))
              )}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function DockSectionRow({
  book,
  section,
  subjectId,
  defaultCount,
  qtyHint,
  pending,
  onAssign,
}: {
  book: SidebarBook;
  section: SidebarSection;
  subjectId: number;
  defaultCount: number;
  qtyHint: string | null;
  pending: boolean;
  onAssign: (n: number) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const close = React.useCallback(() => setOpen(false), []);
  const unit = unitWordOf(book);
  const full = section.remaining <= 0;
  return (
    <li
      className="cursor-grab px-2.5 py-1.5 text-[11px] active:cursor-grabbing"
      draggable
      data-testid="resource-dock-section"
      onDragStart={(e) => {
        const payload: ResourceSectionDragPayload = {
          bookId: book.id,
          bookName: book.name,
          bookType: book.type,
          sectionId: section.id,
          sectionLabel: section.label,
          remaining: section.remaining,
          subjectId,
        };
        e.dataTransfer.setData(RESOURCE_SECTION_MIME, JSON.stringify(payload));
        e.dataTransfer.effectAllowed = "copy";
      }}
      title="Izgarada bir günün üstüne sürükle → o güne ekle"
    >
      <div className="flex items-start gap-2">
        {/* KIRPMA YOK — uzun ünite adı sarar */}
        <span className="min-w-0 flex-1 whitespace-normal break-words text-foreground">
          {section.label}
          {section.topic_name ? (
            <span className="italic text-muted-foreground"> ({section.topic_name})</span>
          ) : null}
        </span>
        <span className="whitespace-nowrap tabular-nums text-muted-foreground">
          <span className="text-emerald-600 dark:text-emerald-300">✓{section.completed}</span>{" "}
          <span className="text-amber-600 dark:text-amber-300">⏳{section.reserved}</span>{" "}
          <b className="text-foreground">⎯{section.remaining}</b>
        </span>
        <button
          type="button"
          disabled={pending}
          aria-expanded={open}
          aria-label={`${section.label}: ${unit} ver`}
          onClick={() => setOpen((v) => !v)}
          className={cn(
            "inline-flex size-6 shrink-0 items-center justify-center rounded border transition disabled:opacity-50",
            open
              ? "border-cyan-500 bg-cyan-600 text-white"
              : full
                ? "border-amber-300 text-amber-700 hover:bg-amber-50 dark:border-amber-500/40 dark:text-amber-300 dark:hover:bg-amber-500/10"
                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          <Plus className="size-3.5" aria-hidden />
        </button>
      </div>
      {open ? (
        <AssignCountChooser
          defaultCount={defaultCount}
          hint={qtyHint}
          remaining={section.remaining}
          unit={unit}
          pending={pending}
          onPick={(n) => {
            onAssign(n);
            setOpen(false);
          }}
          onClose={close}
        />
      ) : null}
    </li>
  );
}
