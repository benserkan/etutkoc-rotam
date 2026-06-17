"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { History, Loader2, ArrowRight } from "lucide-react";

import { getCarryoverCandidates, teacherKeys } from "@/lib/api/teacher";
import { useCarryover } from "@/lib/hooks/use-teacher-mutations";
import type { CarryoverCandidatesResponse } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

function todayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function fmtDate(iso: string): string {
  // "2026-06-12" → "12.06"
  const [, m, d] = iso.split("-");
  return d && m ? `${d}.${m}` : iso;
}

/**
 * Devret — geçen haftalardan yapılmadan kalan görevler.
 *
 * Öğrenci geçen hafta bir görevi yapmadıysa (hasta vb.), o testler rezervde
 * kilitli kalıyordu → yeni haftada aynı üniteyi atayamıyordun. Bu panel:
 * sayfayı açınca "ölü rezerv" otomatik serbest bırakılır (kapasite döner) +
 * eksik kalemler burada listelenir → seç + "bu haftaya taşı" ile tek tıkla
 * yeni güne yeni görev olarak eklenir. Eski görev kaydı (yapılmadı) durur.
 * Aday yoksa panel HİÇ görünmez.
 */
export function CarryoverPanel({ studentId }: { studentId: number }) {
  const q = useQuery<CarryoverCandidatesResponse>({
    queryKey: teacherKeys.carryoverCandidates(studentId),
    queryFn: () => getCarryoverCandidates(studentId),
    staleTime: 15_000,
  });
  const carry = useCarryover(studentId);

  const candidates = React.useMemo(() => q.data?.candidates ?? [], [q.data]);
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [target, setTarget] = React.useState(todayIso());

  // Aday listesi değişince geçersiz seçimleri ayıkla (render sırasında türet).
  const validIds = React.useMemo(
    () => new Set(candidates.map((c) => c.task_item_id)),
    [candidates],
  );
  const effectiveSelected = React.useMemo(
    () => new Set([...selected].filter((id) => validIds.has(id))),
    [selected, validIds],
  );

  if (q.isLoading || candidates.length === 0) return null;

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelected(new Set(candidates.map((c) => c.task_item_id)));
  }

  function onCarry() {
    const items = candidates
      .filter((c) => effectiveSelected.has(c.task_item_id))
      .map((c) => ({ book_id: c.book_id, section_id: c.section_id, count: c.remaining }));
    if (items.length === 0) return;
    carry.mutate(
      { body: { target_date: target, items } },
      { onSuccess: () => setSelected(new Set()) },
    );
  }

  const totalRemaining = candidates.reduce((s, c) => s + c.remaining, 0);

  return (
    <div className="border-b border-amber-200 bg-amber-50/60">
      <div className="px-4 py-3">
        <p className="flex items-center gap-1.5 font-medium text-amber-900">
          <History className="size-4" aria-hidden />
          Geçen haftadan eksikler ({candidates.length})
        </p>
        <p className="mt-0.5 text-xs text-amber-800">
          Yapılmadan kalan {totalRemaining} test serbest bırakıldı (kapasite döndü).
          Seç → bu haftaya taşı.
        </p>
      </div>

      <ul className="space-y-1 px-3 pb-2">
        {candidates.map((c) => (
          <li key={c.task_item_id}>
            <label
              className={cn(
                "flex cursor-pointer items-start gap-2 rounded-md border px-2 py-1.5 text-xs transition",
                effectiveSelected.has(c.task_item_id)
                  ? "border-amber-400 bg-amber-100/70"
                  : "border-amber-200 bg-white hover:bg-amber-50",
              )}
            >
              <input
                type="checkbox"
                checked={effectiveSelected.has(c.task_item_id)}
                onChange={() => toggle(c.task_item_id)}
                className="mt-0.5 rounded border-amber-300"
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium text-slate-900">
                  {c.book_name}
                </span>
                <span className="block truncate text-slate-600">
                  {c.section_label} ·{" "}
                  <span className="font-semibold text-amber-800">{c.remaining} test</span>
                  {c.completed > 0 ? (
                    <span className="text-slate-400"> ({c.completed} yapıldı)</span>
                  ) : null}
                  <span className="text-slate-400"> · {fmtDate(c.task_date)}</span>
                </span>
              </span>
            </label>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-2 px-4 pb-3 pt-1">
        <button
          type="button"
          onClick={selectAll}
          className="text-[11px] font-medium text-amber-800 hover:underline"
        >
          Tümünü seç
        </button>
        <span className="text-amber-300">·</span>
        <label className="flex items-center gap-1 text-[11px] text-amber-900">
          Tarih:
          <input
            type="date"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="rounded border border-amber-300 bg-white px-1.5 py-0.5 text-xs text-slate-900"
          />
        </label>
        <button
          type="button"
          onClick={onCarry}
          disabled={effectiveSelected.size === 0 || carry.isPending}
          className={cn(
            "ml-auto inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold transition",
            effectiveSelected.size === 0 || carry.isPending
              ? "cursor-not-allowed bg-amber-200 text-amber-500"
              : "bg-amber-600 text-white hover:bg-amber-700",
          )}
        >
          {carry.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <ArrowRight className="size-3.5" aria-hidden />
          )}
          Bu haftaya taşı ({effectiveSelected.size})
        </button>
      </div>
    </div>
  );
}
