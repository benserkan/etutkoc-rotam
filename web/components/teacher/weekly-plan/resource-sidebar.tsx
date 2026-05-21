"use client";

import * as React from "react";
import { ChevronRight, Grid3x3, Loader2 } from "lucide-react";

import type {
  SidebarBook,
  SidebarResponse,
  SidebarSection,
  SidebarSubject,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

interface Props {
  data: SidebarResponse | undefined;
  isLoading: boolean;
  focusedSubjectId: number | null;
  onClearFocus: () => void;
  openSubjects: Set<number>;
  setOpenSubjects: React.Dispatch<React.SetStateAction<Set<number>>>;
  openBooks: Set<number>;
  setOpenBooks: React.Dispatch<React.SetStateAction<Set<number>>>;
  // Paket 3.5b — kitap satırı tıklanınca sinema-koltuğu modal açılır
  onOpenBookGrid?: (bookId: number) => void;
}

/**
 * "Kaynak Durumu" — 3 seviyeli reaktif sidebar (Jinja partial parite).
 *
 *   Ders (details) → Kitap (details) → Ünite (sade satır)
 *
 * Form'da bir ders seçildiğinde `focusedSubjectId` set edilir; backend
 * filtreli yanıt döndürür ve burada tek ders gösterilir. Açık olan dersler
 * ve kitaplar swap'lerde korunur.
 */
export function ResourceSidebar({
  data,
  isLoading,
  focusedSubjectId,
  onClearFocus,
  openSubjects,
  setOpenSubjects,
  openBooks,
  setOpenBooks,
  onOpenBookGrid,
}: Props) {
  // Filtre uygulandığında otomatik o ders açılsın
  React.useEffect(() => {
    if (focusedSubjectId !== null) {
      setOpenSubjects((prev) => {
        if (prev.has(focusedSubjectId)) return prev;
        const next = new Set(prev);
        next.add(focusedSubjectId);
        return next;
      });
    }
  }, [focusedSubjectId, setOpenSubjects]);

  function toggleSubject(id: number) {
    setOpenSubjects((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleBook(id: number) {
    setOpenBooks((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div>
      <div className="px-4 py-3 border-b border-border sticky top-0 bg-card z-10 flex items-center justify-between">
        <div>
          <p className="font-medium text-foreground">Kaynak Durumu</p>
          <p className="text-xs text-muted-foreground">
            Ders bazında kitap ilerlemesi
          </p>
        </div>
        {focusedSubjectId !== null ? (
          <button
            type="button"
            onClick={onClearFocus}
            className="text-[11px] text-indigo-600 hover:text-indigo-800 underline"
          >
            Tümü
          </button>
        ) : null}
      </div>

      {focusedSubjectId !== null && data && data.subjects.length > 0 ? (
        <div className="px-4 py-2 bg-indigo-50 border-b border-indigo-100 text-[11px] flex items-center justify-between gap-2">
          <span className="text-indigo-700 truncate">
            Filtre: <b>{data.subjects[0].name}</b>
          </span>
          <span className="text-muted-foreground">diğer dersler gizli</span>
        </div>
      ) : null}

      <div className="divide-y divide-border">
        {isLoading && !data ? (
          <div className="p-4 flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" aria-hidden /> Yükleniyor…
          </div>
        ) : !data || data.subjects.length === 0 ? (
          <div className="px-4 py-6 text-center text-xs text-muted-foreground">
            {focusedSubjectId !== null
              ? "Bu derse atanmış kitap yok."
              : "Atanmış kitap yok."}
          </div>
        ) : (
          data.subjects.map((s) => (
            <SubjectRow
              key={s.id}
              subject={s}
              isOpen={openSubjects.has(s.id)}
              onToggle={() => toggleSubject(s.id)}
              openBooks={openBooks}
              onToggleBook={toggleBook}
              onOpenBookGrid={onOpenBookGrid}
            />
          ))
        )}
      </div>

      <div className="px-4 py-2 text-[10px] text-muted-foreground border-t border-border flex gap-3 bg-card sticky bottom-0">
        <span className="text-emerald-600">✓ çöz.</span>
        <span className="text-amber-600">⏳ rez.</span>
        <span className="text-foreground">⎯ kalan</span>
      </div>
    </div>
  );
}

function SubjectRow({
  subject,
  isOpen,
  onToggle,
  openBooks,
  onToggleBook,
  onOpenBookGrid,
}: {
  subject: SidebarSubject;
  isOpen: boolean;
  onToggle: () => void;
  openBooks: Set<number>;
  onToggleBook: (id: number) => void;
  onOpenBookGrid?: (bookId: number) => void;
}) {
  const { total, completed, reserved, remaining, books_count } = subject.summary;
  const pctDone = total > 0 ? Math.round((100 * completed) / total) : 0;
  const pctRes = total > 0 ? Math.round((100 * reserved) / total) : 0;
  return (
    <div className="group resource-subject" data-subject-id={subject.id}>
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left px-4 py-2.5 hover:bg-muted/50 cursor-pointer"
        aria-expanded={isOpen}
      >
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-medium text-sm text-foreground truncate flex items-center gap-1.5">
            <ChevronRight
              className={cn(
                "size-3.5 text-muted-foreground transition-transform",
                isOpen ? "rotate-90" : "",
              )}
              aria-hidden
            />
            {subject.name}
          </span>
          <span className="text-[10px] text-muted-foreground whitespace-nowrap">
            {books_count} kitap
          </span>
        </div>
        <div className="mt-1.5 h-1.5 bg-muted rounded-full overflow-hidden flex ml-5">
          <div
            className="bg-emerald-500 h-full"
            style={{ width: `${pctDone}%` }}
          />
          <div
            className="bg-amber-400 h-full"
            style={{ width: `${pctRes}%` }}
          />
        </div>
        <div className="mt-1 text-[11px] text-muted-foreground flex gap-2 ml-5">
          <span className="text-emerald-600">✓{completed}</span>
          <span className="text-amber-600">⏳{reserved}</span>
          <span className="font-medium text-foreground">⎯{remaining}</span>
          <span className="text-muted-foreground/60 ml-auto">/ {total}</span>
        </div>
      </button>

      {isOpen ? (
        <div className="px-4 pb-3 pt-1 space-y-1.5 bg-muted/30">
          {subject.books.map((b) => (
            <BookRow
              key={b.id}
              book={b}
              isOpen={openBooks.has(b.id)}
              onToggle={() => onToggleBook(b.id)}
              onOpenGrid={
                onOpenBookGrid ? () => onOpenBookGrid(b.id) : undefined
              }
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function BookRow({
  book,
  isOpen,
  onToggle,
  onOpenGrid,
}: {
  book: SidebarBook;
  isOpen: boolean;
  onToggle: () => void;
  onOpenGrid?: () => void;
}) {
  const pctDone = book.total > 0 ? Math.round((100 * book.completed) / book.total) : 0;
  const pctRes = book.total > 0 ? Math.round((100 * book.reserved) / book.total) : 0;
  const isDeneme =
    book.type === "brans_denemesi" || book.type === "genel_deneme";
  const unitWord = isDeneme ? "deneme" : "test";

  return (
    <div className="rounded border border-border bg-card overflow-hidden">
      <div className="flex items-stretch">
        <button
          type="button"
          onClick={onToggle}
          className="flex-1 min-w-0 text-left px-2.5 py-2 hover:bg-muted/50"
          aria-expanded={isOpen}
        >
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-[13px] text-foreground leading-tight truncate flex items-center gap-1">
              <ChevronRight
                className={cn(
                  "size-3 text-muted-foreground transition-transform",
                  isOpen ? "rotate-90" : "",
                )}
                aria-hidden
              />
              {book.name}
            </span>
            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
              {book.total} {unitWord}
            </span>
          </div>
          <div className="mt-1 h-1.5 bg-muted rounded-full overflow-hidden flex ml-4">
            <div
              className="bg-emerald-500 h-full"
              style={{ width: `${pctDone}%` }}
            />
            <div
              className="bg-amber-400 h-full"
              style={{ width: `${pctRes}%` }}
            />
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground flex gap-1.5 ml-4">
            <span className="text-emerald-600">✓{book.completed}</span>
            <span className="text-amber-600">⏳{book.reserved}</span>
            <span className="font-medium text-foreground ml-auto">
              kalan {book.remaining}
            </span>
          </div>
        </button>
        {onOpenGrid ? (
          <button
            type="button"
            onClick={onOpenGrid}
            title="Test detayını sinema-koltuğu görünümüyle aç"
            aria-label="Sinema-koltuğu görünümü"
            className="flex items-center justify-center px-2 border-l border-border/60 text-muted-foreground hover:text-foreground hover:bg-muted transition"
          >
            <Grid3x3 className="size-3.5" aria-hidden />
          </button>
        ) : null}
      </div>

      {isOpen ? (
        <ul className="border-t border-border bg-muted/30 divide-y divide-border">
          {book.sections.length === 0 ? (
            <li className="px-3 py-2 text-[11px] italic text-muted-foreground">
              Bu kitapta tanımlı ünite yok.
            </li>
          ) : (
            book.sections.map((sec) => (
              <SectionRow key={sec.id} section={sec} />
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}

function SectionRow({ section }: { section: SidebarSection }) {
  return (
    <li className="px-3 py-1.5 text-[11px]">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-foreground truncate">
          {section.label}
          {section.topic_name ? (
            <span className="text-muted-foreground italic">
              {" "}
              ({section.topic_name})
            </span>
          ) : null}
        </span>
        <span className="text-muted-foreground whitespace-nowrap tabular-nums">
          <span className="text-emerald-600">✓{section.completed}</span>{" "}
          <span className="text-amber-600">⏳{section.reserved}</span>{" "}
          <b className="text-foreground">⎯{section.remaining}</b>
          <span className="text-muted-foreground/60"> / {section.total}</span>
        </span>
      </div>
    </li>
  );
}
