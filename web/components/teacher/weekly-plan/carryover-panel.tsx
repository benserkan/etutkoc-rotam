"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  History,
  Loader2,
  Plus,
  Info,
  Boxes,
  X,
  GripVertical,
  ExternalLink,
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
import { PinnableSection } from "./pinnable-section";

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
  const [addFor, setAddFor] = React.useState<CarryoverCandidate | null>(null);
  const [detailFor, setDetailFor] = React.useState<CarryoverCandidate | null>(null);

  if (q.isLoading || candidates.length === 0) return null;

  const totalRemaining = candidates.reduce((s, c) => s + c.total_remaining, 0);
  const isBrowse = mode === "browse";

  return (
    <PinnableSection
      id="week:carryover"
      tone={isBrowse ? "neutral" : "amber"}
      icon={
        isBrowse ? (
          <Info className="size-4" aria-hidden />
        ) : (
          <History className="size-4" aria-hidden />
        )
      }
      title={isBrowse ? "Bu haftada yapılmayanlar" : "Geçen haftadan eksikler"}
      summary={`${candidates.length} görev${totalRemaining > 0 ? ` · ${totalRemaining} test` : ""}`}
      className={
        isBrowse
          ? "bg-slate-50/60 dark:bg-slate-500/10"
          : "bg-amber-50/60 dark:bg-amber-500/10"
      }
    >
      <div>
          <p
            className={cn(
              "px-4 pb-2 text-xs",
              isBrowse ? "text-slate-600" : "text-amber-800",
            )}
          >
            {isBrowse
              ? "Bu hafta tamamlanmamış + sonraki haftaya taşınmamış görevler (bilgi amaçlı)."
              : "Yapılmadan kalan görevler. Bir güne SÜRÜKLEYİP bırakın ya da “Ekle” ile taşıyın; taşınan görev listeden düşer."}
          </p>

          <ul className="space-y-1 px-3 pb-3">
            {candidates.map((c) => (
              <li
                key={c.task_id}
                draggable={!isBrowse}
                onDragStart={
                  isBrowse
                    ? undefined
                    : (e) => {
                        e.dataTransfer.setData("text/x-carryover-task", String(c.task_id));
                        e.dataTransfer.effectAllowed = "copy";
                      }
                }
                className={cn(
                  "rounded-md border px-2.5 py-2 text-xs",
                  isBrowse
                    ? "border-slate-200 bg-white"
                    : "cursor-grab border-amber-200 bg-white active:cursor-grabbing",
                )}
              >
                <div className="flex items-start gap-2">
                  {!isBrowse ? (
                    <GripVertical
                      className="mt-0.5 size-3.5 shrink-0 text-amber-400"
                      aria-hidden
                    />
                  ) : null}
                  {/* Metin KIRPILMAZ (sarar); karta tıklayınca ayrıntı penceresi */}
                  <button
                    type="button"
                    onClick={() => setDetailFor(c)}
                    title={cardTooltip(c)}
                    className="min-w-0 flex-1 rounded text-left outline-none hover:opacity-80 focus-visible:ring-2 focus-visible:ring-amber-400"
                  >
                    <span className="flex items-start gap-1 font-medium text-slate-900">
                      {c.is_block ? (
                        <Boxes className="mt-0.5 size-3 shrink-0 text-violet-500" aria-hidden />
                      ) : null}
                      <span className="break-words">{c.title}</span>
                    </span>
                    {c.section_items.map((si) => (
                      <span key={si.section_id} className="block break-words text-slate-600">
                        {si.book_name} · {si.section_label} ·{" "}
                        <span className="font-semibold text-amber-800">{si.remaining} test</span>
                      </span>
                    ))}
                    {c.itemless_items
                      .filter((il) => il.label !== c.title)
                      .map((il, i) => (
                        <span key={i} className="block break-words text-slate-600">
                          {il.label} · {il.count} soru
                        </span>
                      ))}
                    <span className="text-slate-500">
                      {fmtDate(c.task_date)} ·{" "}
                      <span className="underline decoration-dotted">ayrıntı</span>
                    </span>
                  </button>
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
      </div>

      <CarryoverDetailDialog
        candidate={detailFor}
        canAdd={!isBrowse}
        onClose={() => setDetailFor(null)}
        onAdd={(c) => {
          setDetailFor(null);
          setAddFor(c);
        }}
      />

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
    </PinnableSection>
  );
}

const TYPE_LABELS: Record<string, string> = {
  test: "Test",
  video: "Video dersi",
  summary: "Özet",
  review: "Tekrar",
  other: "Etkinlik / deneme",
};

const PERIOD_LABELS: Record<string, string> = {
  morning: "Sabah",
  noon: "Öğle",
  evening: "Akşam",
};

function fmtLongDate(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long" });
}

/** Üzerine gelince görünen tam metin (tarayıcı ipucu). */
function cardTooltip(c: CarryoverCandidate): string {
  const lines = [c.title];
  for (const si of c.section_items) {
    lines.push(`${si.book_name} · ${si.section_label} · ${si.remaining} test`);
  }
  for (const il of c.itemless_items) {
    if (il.label !== c.title) lines.push(`${il.label} · ${il.count} soru`);
  }
  if (c.notes) lines.push(`Not: ${c.notes}`);
  return lines.join("\n");
}

/** Devret kartının ayrıntısı — tam başlık, yapılmayan kalemler, not, bağlantı. */
function CarryoverDetailDialog({
  candidate,
  canAdd,
  onClose,
  onAdd,
}: {
  candidate: CarryoverCandidate | null;
  canAdd: boolean;
  onClose: () => void;
  onAdd: (c: CarryoverCandidate) => void;
}) {
  const c = candidate;
  const itemCls =
    "rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200";
  return (
    <Dialog open={c !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="break-words pr-6 text-base leading-snug">
            {c?.title ?? "Görev"}
          </DialogTitle>
        </DialogHeader>
        {c ? (
          <div className="space-y-3 text-sm">
            <dl className="grid grid-cols-[96px_1fr] gap-x-3 gap-y-1 text-xs">
              <dt className="text-muted-foreground">Tür</dt>
              <dd className="text-foreground">
                {c.is_block ? "Serbest blok" : (TYPE_LABELS[c.type] ?? c.type)}
              </dd>
              <dt className="text-muted-foreground">Planlanan gün</dt>
              <dd className="text-foreground">{fmtLongDate(c.task_date)}</dd>
              {c.period ? (
                <>
                  <dt className="text-muted-foreground">Periyot</dt>
                  <dd className="text-foreground">{PERIOD_LABELS[c.period] ?? c.period}</dd>
                </>
              ) : null}
            </dl>

            {c.section_items.length > 0 || c.itemless_items.length > 0 ? (
              <div>
                <p className="mb-1 text-xs font-semibold text-foreground">Yapılmayan kısım</p>
                <ul className="space-y-1">
                  {c.section_items.map((si) => (
                    <li key={si.section_id} className={itemCls}>
                      <span className="block break-words font-medium">{si.book_name}</span>
                      <span className="block break-words">
                        {si.section_label} ·{" "}
                        <span className="font-semibold">{si.remaining} test</span>
                      </span>
                    </li>
                  ))}
                  {c.itemless_items.map((il, i) => (
                    <li key={i} className={itemCls}>
                      <span className="break-words">{il.label}</span> ·{" "}
                      <span className="font-semibold">{il.count} soru</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Etkinlik görevi — soru sayısı yok, yapıldı/yapılmadı olarak izlenir.
              </p>
            )}

            {c.notes ? (
              <div>
                <p className="mb-1 text-xs font-semibold text-foreground">Not</p>
                <p className="whitespace-pre-wrap break-words rounded-md bg-muted/60 px-2.5 py-1.5 text-xs text-foreground">
                  {c.notes}
                </p>
              </div>
            ) : null}

            {c.link_url ? (
              <a
                href={c.link_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-medium text-cyan-700 underline hover:text-cyan-800 dark:text-cyan-300"
              >
                <ExternalLink className="size-3.5 shrink-0" aria-hidden />
                Bağlantıyı aç
              </a>
            ) : null}

            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted/50"
              >
                Kapat
              </button>
              {canAdd ? (
                <button
                  type="button"
                  onClick={() => onAdd(c)}
                  className="inline-flex items-center gap-1 rounded-md bg-amber-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-amber-700"
                >
                  <Plus className="size-3.5" aria-hidden />
                  Bir güne ekle
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
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
          <p className="-mt-1 break-words text-xs text-muted-foreground">{candidate.title}</p>
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
