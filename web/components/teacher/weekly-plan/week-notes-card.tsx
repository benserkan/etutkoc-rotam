"use client";

import * as React from "react";
import { Eye, Loader2, NotebookPen, Plus, StickyNote, X } from "lucide-react";

import {
  useAddWeekNote,
  useDeleteWeekNote,
  useToggleWeekNote,
} from "@/lib/hooks/use-weekly-plan-mutations";
import type { TeacherWeekNote } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

interface Props {
  studentId: number;
  weekStart: string; // ISO YYYY-MM-DD
  notes: TeacherWeekNote[];
}

/**
 * Hafta notları kartı — öğrenci de görür, yazdırılan programda da çıkar.
 * Görsel: bg-card surface; sticky-note ikon başlık; emoji-yoğun amber paneli yerine
 * shadcn-flavored tonal palette + subtle accent.
 */
export function WeekNotesCard({ studentId, weekStart, notes }: Props) {
  const addMut = useAddWeekNote(studentId);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [draft, setDraft] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const body = draft.trim();
    if (!body) return;
    addMut.mutate(
      { body: { week_start: weekStart, body } },
      {
        onSuccess: () => {
          setDraft("");
          inputRef.current?.focus();
        },
      },
    );
  }

  const formattedWeek = formatTRDate(weekStart);
  const doneCount = notes.filter((n) => n.is_done).length;

  return (
    <section className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
      <header className="px-5 py-4 border-b border-border/60 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-muted text-foreground">
            <StickyNote className="size-4" aria-hidden />
          </span>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-foreground tracking-tight">
              Hafta notları
            </h3>
            <p className="text-xs text-muted-foreground">
              {formattedWeek} haftası ·{" "}
              {notes.length === 0
                ? "henüz not yok"
                : doneCount > 0
                  ? `${notes.length} madde · ${doneCount} tamam`
                  : `${notes.length} madde`}
            </p>
          </div>
        </div>
        <span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-muted-foreground">
          <Eye className="size-3.5" aria-hidden />
          öğrenci de görür
        </span>
      </header>

      {notes.length > 0 ? (
        <ul className="divide-y divide-border/60">
          {notes.map((n) => (
            <NoteRow key={n.id} studentId={studentId} note={n} />
          ))}
        </ul>
      ) : (
        <p className="px-5 py-4 text-xs text-muted-foreground italic">
          Hızlı bir not bırak — Salı dersine deneme getir, hedef kart sayısı, vb.
        </p>
      )}

      <form
        onSubmit={onSubmit}
        className="flex gap-2 px-5 py-3 border-t border-border/60 bg-muted/30"
      >
        <div className="flex-1 flex items-center gap-2 px-2.5 rounded-md border border-input bg-background focus-within:ring-2 focus-within:ring-ring focus-within:border-ring transition">
          <NotebookPen
            className="size-4 text-muted-foreground flex-shrink-0"
            aria-hidden
          />
          <input
            ref={inputRef}
            type="text"
            required
            maxLength={500}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Yeni not ekle…"
            className="flex-1 py-2 text-sm bg-transparent focus:outline-none placeholder:text-muted-foreground"
          />
        </div>
        <button
          type="submit"
          disabled={addMut.isPending || !draft.trim()}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-foreground text-background text-xs font-medium hover:bg-foreground/90 disabled:opacity-40 transition"
        >
          {addMut.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <Plus className="size-3.5" aria-hidden />
          )}
          Ekle
        </button>
      </form>
    </section>
  );
}

function NoteRow({
  studentId,
  note,
}: {
  studentId: number;
  note: TeacherWeekNote;
}) {
  const toggleMut = useToggleWeekNote(studentId);
  const deleteMut = useDeleteWeekNote(studentId);
  return (
    <li className="px-5 py-2.5 flex items-start gap-3 group hover:bg-muted/30 transition">
      <button
        type="button"
        onClick={() => toggleMut.mutate({ noteId: note.id })}
        disabled={toggleMut.isPending}
        title={note.is_done ? "Yapıldı işaretini kaldır" : "Yapıldı olarak işaretle"}
        className={cn(
          "mt-0.5 size-4 rounded border flex items-center justify-center text-[10px] leading-none transition",
          note.is_done
            ? "bg-foreground border-foreground text-background"
            : "border-input hover:border-foreground bg-background",
        )}
        aria-pressed={note.is_done}
      >
        {note.is_done ? "✓" : ""}
      </button>
      <span
        className={cn(
          "flex-1 text-sm leading-relaxed whitespace-pre-wrap",
          note.is_done
            ? "line-through text-muted-foreground"
            : "text-foreground",
        )}
      >
        {note.body}
      </span>
      <button
        type="button"
        onClick={() => {
          if (!window.confirm("Bu notu sil?")) return;
          deleteMut.mutate({ noteId: note.id });
        }}
        disabled={deleteMut.isPending}
        className="text-muted-foreground hover:text-destructive transition opacity-0 group-hover:opacity-100"
        title="Sil"
        aria-label="Notu sil"
      >
        {deleteMut.isPending ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <X className="size-3.5" aria-hidden />
        )}
      </button>
    </li>
  );
}

const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

function formatTRDate(iso: string): string {
  const [y, m, d] = iso.split("-").map((p) => Number(p));
  if (!y || !m || !d) return iso;
  return `${d} ${TR_MONTHS[m - 1]}`;
}
