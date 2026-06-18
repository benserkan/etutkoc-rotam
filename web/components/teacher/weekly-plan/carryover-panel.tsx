"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  History,
  Loader2,
  ChevronDown,
  Plus,
  Info,
  Boxes,
  X,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getCarryoverCandidates, teacherKeys } from "@/lib/api/teacher";
import { useCarryover } from "@/lib/hooks/use-teacher-mutations";
import type {
  CarryoverCandidate,
  CarryoverCandidatesResponse,
  TaskPeriod,
  TeacherStudentWeekDay,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

const PERIODS: { key: TaskPeriod; label: string }[] = [
  { key: "morning", label: "Sabah" },
  { key: "noon", label: "Öğle" },
  { key: "evening", label: "Akşam" },
];

function fmtDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return d && m ? `${d}.${m}` : iso;
}

/**
 * Devret — bir önceki haftadan YAPILMADAN KALAN görevler (tüm tipler: test/blok/
 * deneme/etkinlik). Varsayılan KAPALI; tek satır özet → tıkla aç.
 *
 * - mode="plan" (aktif/yeni hafta): EYLEMLİ. Her görev kartında "Ekle" → modal
 *   (hedef gün + varsa periyot seç) → yeni güne taşı. Taşınan görev DİNAMİK
 *   olarak listeden düşer (carried). Sayfayı açınca ölü rezerv otomatik serbest
 *   bırakılır (kapasite döner).
 * - mode="browse" (geçmiş program gezilirken): BİLGİ AMAÇLI (eylemsiz) — o
 *   haftada yapılmayan + sonraki haftaya taşınmamış görevler.
 *
 * Aday yoksa panel HİÇ görünmez.
 */
export function CarryoverPanel({
  studentId,
  programId,
  weekDays,
}: {
  studentId: number;
  programId: number | null;
  weekDays: TeacherStudentWeekDay[];
}) {
  const q = useQuery<CarryoverCandidatesResponse>({
    queryKey: teacherKeys.carryoverCandidates(studentId, programId),
    queryFn: () => getCarryoverCandidates(studentId, programId),
    staleTime: 15_000,
  });
  const carry = useCarryover(studentId);

  const candidates = React.useMemo(() => q.data?.candidates ?? [], [q.data]);
  const mode = q.data?.mode ?? "plan";
  const [expanded, setExpanded] = React.useState(false);
  const [addFor, setAddFor] = React.useState<CarryoverCandidate | null>(null);

  if (q.isLoading || candidates.length === 0) return null;

  const totalRemaining = candidates.reduce((s, c) => s + c.total_remaining, 0);
  const isBrowse = mode === "browse";

  return (
    <div
      className={cn(
        "border-b",
        isBrowse ? "border-slate-200 bg-slate-50/60" : "border-amber-200 bg-amber-50/60",
      )}
    >
      {/* Varsayılan kapalı — tek satır özet */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={cn(
          "flex w-full items-center gap-2 px-4 py-2.5 text-left transition",
          isBrowse ? "hover:bg-slate-100/60" : "hover:bg-amber-100/50",
        )}
        aria-expanded={expanded}
      >
        {isBrowse ? (
          <Info className="size-4 shrink-0 text-slate-500" aria-hidden />
        ) : (
          <History className="size-4 shrink-0 text-amber-700" aria-hidden />
        )}
        <span
          className={cn(
            "min-w-0 flex-1 text-sm font-medium",
            isBrowse ? "text-slate-700" : "text-amber-900",
          )}
        >
          {isBrowse ? "Bu haftada yapılmayanlar" : "Geçen haftadan eksikler"} ({candidates.length})
          {totalRemaining > 0 ? (
            <span className={cn("ml-1 font-normal", isBrowse ? "text-slate-500" : "text-amber-700")}>
              · {totalRemaining} test
            </span>
          ) : null}
        </span>
        <ChevronDown
          className={cn(
            "size-4 shrink-0 transition-transform",
            isBrowse ? "text-slate-400" : "text-amber-600",
            expanded && "rotate-180",
          )}
          aria-hidden
        />
      </button>

      {!expanded ? null : (
        <>
          <p
            className={cn(
              "px-4 pb-2 text-xs",
              isBrowse ? "text-slate-600" : "text-amber-800",
            )}
          >
            {isBrowse
              ? "Bu hafta tamamlanmamış + sonraki haftaya taşınmamış görevler (bilgi amaçlı)."
              : "Yapılmadan kalan görevler. Birine “Ekle” diyerek hedef güne taşıyın; taşınan görev listeden düşer."}
          </p>

          <ul className="space-y-1 px-3 pb-3">
            {candidates.map((c) => (
              <li
                key={c.task_id}
                className={cn(
                  "rounded-md border px-2.5 py-2 text-xs",
                  isBrowse ? "border-slate-200 bg-white" : "border-amber-200 bg-white",
                )}
              >
                <div className="flex items-start gap-2">
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1 font-medium text-slate-900">
                      {c.is_block ? (
                        <Boxes className="size-3 text-violet-500" aria-hidden />
                      ) : null}
                      <span className="truncate">{c.title}</span>
                    </span>
                    {c.section_items.map((si) => (
                      <span key={si.section_id} className="block truncate text-slate-600">
                        {si.book_name} · {si.section_label} ·{" "}
                        <span className="font-semibold text-amber-800">{si.remaining} test</span>
                      </span>
                    ))}
                    {c.itemless_items.map((il, i) => (
                      <span key={i} className="block truncate text-slate-600">
                        {il.label} · {il.count} test
                      </span>
                    ))}
                    <span className="text-slate-400">{fmtDate(c.task_date)}</span>
                  </span>
                  {!isBrowse ? (
                    <button
                      type="button"
                      onClick={() => setAddFor(c)}
                      className="inline-flex shrink-0 items-center gap-1 rounded-md bg-amber-600 px-2 py-1 text-[11px] font-semibold text-white transition hover:bg-amber-700"
                    >
                      <Plus className="size-3" aria-hidden />
                      Ekle
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* Hedef gün + periyot seçim modalı */}
      <AddToDayDialog
        candidate={addFor}
        weekDays={weekDays}
        pending={carry.isPending}
        onClose={() => setAddFor(null)}
        onConfirm={(targetDate, period) => {
          if (!addFor) return;
          carry.mutate(
            { body: { target_date: targetDate, period, task_ids: [addFor.task_id] } },
            { onSuccess: () => setAddFor(null) },
          );
        }}
      />
    </div>
  );
}

function AddToDayDialog({
  candidate,
  weekDays,
  pending,
  onClose,
  onConfirm,
}: {
  candidate: CarryoverCandidate | null;
  weekDays: TeacherStudentWeekDay[];
  pending: boolean;
  onClose: () => void;
  onConfirm: (targetDate: string, period: TaskPeriod | null) => void;
}) {
  const open = candidate !== null;
  // Hata 1: geçmiş güne tamamlanamayan görev eklenemez → yalnız bugün + ileri günler.
  const selectableDays = React.useMemo(
    () => weekDays.filter((d) => !d.is_past),
    [weekDays],
  );
  const usesPeriods = React.useMemo(
    () => weekDays.some((d) => d.tasks?.some((t) => t.period)),
    [weekDays],
  );
  const defaultDay = React.useMemo(() => {
    const today = selectableDays.find((d) => d.is_today);
    return today?.date ?? selectableDays[0]?.date ?? "";
  }, [selectableDays]);

  const [day, setDay] = React.useState(defaultDay);
  const [period, setPeriod] = React.useState<TaskPeriod | null>(null);

  // Modal her açıldığında varsayılanlara dön (prop değişince render'da sıfırla)
  const [lastKey, setLastKey] = React.useState<number | null>(null);
  if (candidate && candidate.task_id !== lastKey) {
    setLastKey(candidate.task_id);
    setDay(defaultDay);
    setPeriod((candidate.period as TaskPeriod | null) ?? null);
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-base">Hangi güne eklensin?</DialogTitle>
        </DialogHeader>
        {candidate ? (
          <p className="-mt-1 truncate text-xs text-muted-foreground">{candidate.title}</p>
        ) : null}

        <div className="space-y-3">
          <div>
            <p className="mb-1.5 text-xs font-medium text-foreground">Gün</p>
            {selectableDays.length === 0 ? (
              <p className="rounded-md bg-amber-50 px-2 py-1.5 text-[11px] text-amber-800">
                Bu haftada eklenebilecek (bugün veya ileri) gün yok. Yeni hafta
                oluşturup oraya taşıyın.
              </p>
            ) : null}
            <div className="grid grid-cols-2 gap-1.5">
              {selectableDays.map((d) => (
                <button
                  key={d.date}
                  type="button"
                  onClick={() => setDay(d.date)}
                  className={cn(
                    "rounded-md border px-2 py-1.5 text-left text-xs transition",
                    day === d.date
                      ? "border-amber-500 bg-amber-100 font-semibold text-amber-900"
                      : "border-border bg-card hover:bg-muted/50",
                  )}
                >
                  {d.dow_label} · {fmtDate(d.date)}
                  {d.is_today ? <span className="ml-1 text-amber-600">bugün</span> : null}
                </button>
              ))}
            </div>
          </div>

          {usesPeriods ? (
            <div>
              <p className="mb-1.5 text-xs font-medium text-foreground">Zaman dilimi</p>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => setPeriod(null)}
                  className={cn(
                    "rounded-md border px-2.5 py-1 text-xs transition",
                    period === null
                      ? "border-slate-500 bg-slate-100 font-semibold text-slate-900"
                      : "border-border bg-card hover:bg-muted/50",
                  )}
                >
                  Yok
                </button>
                {PERIODS.map((p) => (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() => setPeriod(p.key)}
                    className={cn(
                      "rounded-md border px-2.5 py-1 text-xs transition",
                      period === p.key
                        ? "border-amber-500 bg-amber-100 font-semibold text-amber-900"
                        : "border-border bg-card hover:bg-muted/50",
                    )}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="mt-2 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted/50"
          >
            <X className="size-4" aria-hidden />
            Vazgeç
          </button>
          <button
            type="button"
            onClick={() => day && onConfirm(day, period)}
            disabled={!day || pending}
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-semibold text-white transition",
              !day || pending ? "cursor-not-allowed bg-amber-300" : "bg-amber-600 hover:bg-amber-700",
            )}
          >
            {pending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Plus className="size-4" aria-hidden />
            )}
            Bu güne ekle
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
