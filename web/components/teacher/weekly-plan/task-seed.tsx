"use client";

/**
 * Görev ekleme — hızlı kutu ↔ ayrıntılı form ↔ tip formları arasında TAŞINAN seçim
 * (2026-10-22). Koç hızlı kutuda konuyu seçip "Özet" ya da "Ayrıntılı form"a geçince
 * seçim kaybolmuyordu sanıyordu; kayboluyordu → form sıfırdan açılıyordu. Seçim artık
 * AddTaskForm'da tutulur ve gidilen her forma dolu aktarılır.
 *
 * Ayrıca kaynaksız konulu görevin birim seçicisi + sayfa devam önerisi burada (hızlı kutu
 * ve ayrıntılı form ortak kullanır).
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { getPageSuggestion, teacherKeys } from "@/lib/api/teacher";
import type {
  ItemUnit,
  PageSuggestionResponse,
  PickerSourceItem,
  PickerTopicItem,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

/** Hızlı kutudaki seçim + girdiler — formlar arasında taşınır. */
export type TaskSeed = {
  topic: PickerTopicItem;
  source: PickerSourceItem | null;
  count: string;
  unit: ItemUnit;
  note: string;
  pageFrom: string;
  pageTo: string;
};

export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Sayfa görevinde "kaldığı yer" — kitap notuna (yoksa konuya) göre son verilen aralık. */
export function usePageSuggestion(
  studentId: number,
  topicId: number | null,
  note: string,
  enabled: boolean,
  excludeTaskId: number | null = null,
) {
  const noteKey = useDebounced(note.trim(), 400);
  return useQuery<PageSuggestionResponse>({
    queryKey: teacherKeys.pageSuggestion(studentId, topicId, noteKey, excludeTaskId),
    queryFn: () => getPageSuggestion(studentId, topicId, noteKey, excludeTaskId),
    enabled: enabled && topicId !== null,
    staleTime: 30_000,
  });
}

export const UNIT_WORD: Record<ItemUnit, string> = { test: "test", soru: "soru", sayfa: "sayfa" };

/** Kompakt birim seçici (test · soru · sayfa). */
export function UnitSegment({
  value,
  onChange,
  className,
}: {
  value: ItemUnit;
  onChange: (u: ItemUnit) => void;
  className?: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Birim"
      className={cn("inline-flex rounded-md border border-input bg-background p-0.5", className)}
    >
      {(["test", "soru", "sayfa"] as const).map((u) => (
        <button
          key={u}
          type="button"
          role="radio"
          aria-checked={value === u}
          onClick={() => onChange(u)}
          className={cn(
            "rounded px-2 py-1 text-[12px] font-medium transition",
            value === u ? "bg-cyan-700 text-white" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {UNIT_WORD[u]}
        </button>
      ))}
    </div>
  );
}

function fmtShortDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

/** "Son verilen (Hız Fen): s. 45–50 · 22 Eki  [51. sayfadan devam et]" satırı. */
export function PageSuggestionLine({
  data,
  pageFrom,
  onPageFrom,
}: {
  data: PageSuggestionResponse | undefined;
  pageFrom: string;
  onPageFrom: (v: string) => void;
}) {
  const last = data?.last ?? null;
  const next = data?.next_from ?? null;
  if (!last) {
    return (
      <p className="text-[11.5px] text-muted-foreground">
        Bu kaynak için daha önce sayfa aralığı verilmemiş. Verdiğin aralıklar kaydedilir;
        sonraki görevde kaldığın sayfa önerilir.
      </p>
    );
  }
  return (
    <div
      className="flex flex-wrap items-center gap-2 text-[12px] leading-snug"
      data-section="task-form:page-suggestion"
    >
      <span className="text-foreground">
        Son verilen
        {last.note ? <> ({last.note})</> : null}:{" "}
        <b className="tabular-nums">
          s. {last.page_from}–{last.page_to}
        </b>
        {last.date ? <span className="text-muted-foreground"> · {fmtShortDate(last.date)}</span> : null}
      </span>
      {next !== null && pageFrom !== String(next) ? (
        <button
          type="button"
          onClick={() => onPageFrom(String(next))}
          className="rounded-md bg-cyan-700 px-2 py-1 text-[11.5px] font-semibold text-white hover:bg-cyan-800"
        >
          {next}. sayfadan devam et
        </button>
      ) : null}
    </div>
  );
}

/** Taşınan konu için etkinlik formlarında gösterilen bağ çipi (kaldırılabilir). */
export function LinkedTopicChip({ name, onRemove }: { name: string; onRemove: () => void }) {
  return (
    <p
      className="flex flex-wrap items-center gap-1.5 rounded-md border border-cyan-600/30 bg-cyan-500/5 px-2.5 py-1.5 text-[12px] text-foreground"
      data-section="task-form:linked-topic"
    >
      <span>
        Müfredat konusuna bağlı: <b>{name}</b>
      </span>
      <span className="text-muted-foreground">— tamamlanınca konu &quot;çalışıldı&quot; sayılır (test sayısına girmez).</span>
      <button
        type="button"
        onClick={onRemove}
        className="ml-auto text-[11.5px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
      >
        bağı kaldır
      </button>
    </p>
  );
}
