"use client";

/**
 * Haftalık İskelet — HAYALET hücreler (F1b 2026-09-25 · F2-1 2026-09-26).
 *
 * İskelet satırı dolmamış gün+periyotta kesikli "öneri" satırı görünür. Görev
 * DEĞİLDİR, rezerv tutmaz. Satıra tıklanınca TAM ALTINDA çip şeridi açılır
 * (assign-count-chooser deseni — portal yok, satır altına akar). Çiplerin
 * sırası ölçülmüş iplik modelinden gelir; her çipte GEREKÇE ("dünün devamı ·
 * 3 test kaldı") + en çok 3 dolgulu rozet (denemede N yanlış …) → koç çipi
 * körü körüne değil bilgiyle seçer. Çip = görev (2 tık).
 *
 * F2-1: satır KAYNAĞINI gösterir (kitap ya da serbest metin adı) — aynı derste
 * üç satır varken hangisinin rutin olduğu okunur. Kitaba bağlı rutinin tek
 * çipi vardır (sıralı ya da karışık, çok bölümlü); kitapsız satır "etkinlik
 * olarak yaz" ile koçun elle verdiği görevin aynısını yazar.
 *
 * Koç kuralı: metin KIRPILMAZ (satır kaydırılır), küçük rozet DOLGULU.
 */

import * as React from "react";
import { CalendarCheck, Check, Loader2, PencilLine, Search, Sparkles, X } from "lucide-react";
import { toast } from "sonner";

import {
  addDays,
  type GhostCell,
  type GhostChip,
  ROUTINE_MODE_LABELS,
  SKELETON_PERIOD_LABELS,
  useAcceptGhost,
  useAcceptRoutine,
  useGhostAction,
} from "@/lib/api/weekly-skeleton";
import { cn } from "@/lib/utils";

import { TaskQuickAdd } from "./task-quick-add";
import { useTopicSpread } from "./topic-spread";

// Dolgulu rozet tonları — beyaz metinle ≥4.5 kontrast için 600/700 tonları.
const BADGE_FILL: Record<string, string> = {
  rose: "bg-rose-700 text-white",
  amber: "bg-amber-700 text-white",
  emerald: "bg-emerald-700 text-white",
  violet: "bg-violet-700 text-white",
  cyan: "bg-cyan-700 text-white",
  slate: "bg-slate-600 text-white",
};

const KIND_LABEL: Record<string, { label: string; cls: string }> = {
  thread: { label: "devam", cls: "bg-cyan-700 text-white" },
  next: { label: "sıradaki", cls: "bg-indigo-700 text-white" },
  new: { label: "yeni konu", cls: "bg-slate-600 text-white" },
  weak: { label: "tekrar", cls: "bg-rose-700 text-white" },
  routine: { label: "rutin", cls: "bg-emerald-700 text-white" },
};

function chipTitle(c: GhostChip): string {
  if (c.items && c.items.length > 1) return c.book_name;
  return c.topic_name && c.topic_name !== c.section_label
    ? `${c.section_label}`
    : c.section_label || c.topic_name || c.book_name;
}

/** Satırın kaynağı: kitap adı ya da serbest metin adı. */
function ghostSource(g: GhostCell): string | null {
  return g.book_name ?? g.label ?? null;
}

/** Kitapsız satır: çip yerine koçun elle verdiği etkinliğin aynısı yazılır. */
function isActivityGhost(g: GhostCell): boolean {
  return !!g.label && !g.book_id;
}

/** Rutin onayıyla yazılabilir mi (çipi ya da etkinlik adı var mı)? */
export function isWritableRoutine(g: GhostCell): boolean {
  return g.is_routine && (g.chips.length > 0 || isActivityGhost(g));
}

function previewText(g: GhostCell): string | null {
  const c = g.chips[0];
  if (c?.items && c.items.length > 0) {
    return c.items.map((it) => `${it.section_label} ${it.count}`).join(" · ");
  }
  if (c) return `${chipTitle(c)} · ${c.count} test`;
  return null;
}

/** Tek hayalet satırı + (açıksa) altındaki çip şeridi. */
export function GhostRow({
  studentId,
  ghost,
}: {
  studentId: number;
  ghost: GhostCell;
}) {
  const [open, setOpen] = React.useState(false);
  const [other, setOther] = React.useState(false);
  const [countOverride, setCountOverride] = React.useState<number | null>(null);
  const accept = useAcceptGhost(studentId);
  const action = useGhostAction(studentId);
  const spread = useTopicSpread();

  /** Kabulden sonra: çapa satırında yayma önizlemesi HEMEN açılır (koç kararı);
   *  diğer satırlarda bildirimde "Konuyu yay" düğmesi. */
  function afterAccept(p: { topicId: number | null; sectionId: number | null; count: number; title: string }) {
    const params = {
      topicId: p.topicId,
      sectionId: p.topicId ? null : p.sectionId,
      start: addDays(ghost.date, 1),
      perDay: p.count,
      title: p.title,
    };
    if (ghost.is_anchor) {
      spread.open(params);
    } else {
      toast.message("Kalan testleri sonraki günlere yaymak ister misin?", {
        action: { label: "Konuyu yay", onClick: () => spread.open(params) },
      });
    }
  }
  const boxRef = React.useRef<HTMLDivElement | null>(null);

  // Dışarı tıklama / Esc kapatır (mousedown — context-menu dersi).
  React.useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const routineChip = ghost.chips[0]?.kind === "routine";

  function pick(c: GhostChip) {
    if (c.items && c.items.length > 0) {
      accept.mutate({
        slot_id: ghost.slot_id,
        date: ghost.date,
        items: c.items.map((it) => ({ section_id: it.section_id, count: it.count })),
        chip_rank: c.rank,
        chip_kind: c.kind,
        chip_count: ghost.chips.length,
      });
      return;
    }
    const n = countOverride ?? c.count;
    accept.mutate(
      {
        slot_id: ghost.slot_id,
        date: ghost.date,
        section_id: c.section_id,
        count: n,
        chip_rank: c.rank,
        chip_kind: c.kind,
        chip_count: ghost.chips.length,
      },
      {
        onSuccess: () =>
          afterAccept({
            topicId: c.topic_id,
            sectionId: c.section_id,
            count: n,
            title: c.topic_name ?? c.section_label,
          }),
      },
    );
  }

  function writeActivity() {
    accept.mutate({ slot_id: ghost.slot_id, date: ghost.date, as_activity: true, chip_rank: 1 });
  }

  function dismiss() {
    action.mutate(
      { slot_id: ghost.slot_id, date: ghost.date, action: "dismissed" },
      {
        onSuccess: () =>
          toast.success(`${ghost.subject_name} önerisi bu gün için kaldırıldı`, {
            action: {
              label: "Geri al",
              onClick: () =>
                action.mutate({
                  slot_id: ghost.slot_id,
                  date: ghost.date,
                  action: "restore",
                }),
            },
          }),
      },
    );
  }

  const busy = accept.isPending;
  const source = ghostSource(ghost);
  const preview = previewText(ghost);

  return (
    <div ref={boxRef} data-ghost-slot={ghost.slot_id} data-ghost-date={ghost.date}>
      <div
        className={cn(
          "flex items-center gap-2 rounded-md border border-dashed px-2.5 py-1.5 transition",
          open
            ? "border-cyan-600 bg-cyan-500/[0.06] dark:border-cyan-400"
            : "border-slate-400/70 bg-transparent hover:border-cyan-600 hover:bg-cyan-500/[0.04] dark:border-slate-500",
        )}
      >
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-0.5 text-left"
          data-testid="ghost-row"
        >
          <Sparkles className="size-3.5 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
          <span className="text-[13px] font-semibold text-foreground">{ghost.subject_name}</span>
          {source ? (
            <span className="text-[12.5px] font-medium text-foreground" data-testid="ghost-source">
              · {source}
            </span>
          ) : null}
          <span className="rounded bg-slate-600 px-1.5 py-px text-[10px] font-semibold text-white">
            öneri
          </span>
          {ghost.is_anchor ? (
            <span className="rounded bg-indigo-700 px-1.5 py-px text-[10px] font-semibold text-white">
              dershane/okul dersi
            </span>
          ) : null}
          {ghost.is_routine ? (
            <span className="rounded bg-emerald-700 px-1.5 py-px text-[10px] font-semibold text-white">
              rutin
              {ghost.routine_mode ? ` · ${ROUTINE_MODE_LABELS[ghost.routine_mode]}` : ""}
            </span>
          ) : null}
          {preview ? (
            <span className="text-[12px] text-muted-foreground">{preview}</span>
          ) : isActivityGhost(ghost) ? (
            <span className="text-[12px] text-muted-foreground">etkinlik olarak yazılır</span>
          ) : (
            <span className="text-[12px] italic text-muted-foreground">
              uygun kaynak yok — başka konu seç
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={dismiss}
          disabled={action.isPending}
          className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label={`${ghost.subject_name} önerisini bu gün için kaldır`}
          title="Bu gün için kaldır"
        >
          <X className="size-3.5" aria-hidden />
        </button>
      </div>

      {open ? (
        <div
          className="mt-1 space-y-2 rounded-md border border-cyan-600/40 bg-card p-2.5 shadow-sm"
          data-testid="ghost-strip"
        >
          {ghost.is_anchor ? (
            <p className="text-[12.5px] font-medium text-foreground" data-testid="anchor-question">
              Bugün {ghost.subject_name} dersinde hangi konu işlendi? Seçtiğin konu bugüne
              yazılır, kalan testleri sonraki günlere yaymak için önizleme açılır.
            </p>
          ) : null}
          {!routineChip && ghost.chips.length > 0 ? (
            <div className="flex flex-wrap items-center gap-1.5 text-[11.5px]">
              <span className="text-muted-foreground">Adet:</span>
              <button
                type="button"
                onClick={() => setCountOverride(null)}
                className={cn(
                  "rounded border px-2 py-0.5",
                  countOverride == null
                    ? "border-cyan-700 bg-cyan-700 text-white"
                    : "border-border text-foreground hover:bg-muted",
                )}
              >
                önerilen
              </button>
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setCountOverride(n)}
                  className={cn(
                    "min-w-7 rounded border px-2 py-0.5 tabular-nums",
                    countOverride === n
                      ? "border-cyan-700 bg-cyan-700 text-white"
                      : "border-border text-foreground hover:bg-muted",
                  )}
                >
                  {n}
                </button>
              ))}
              {busy ? <Loader2 className="ml-auto size-3.5 animate-spin" aria-hidden /> : null}
            </div>
          ) : null}

          {isActivityGhost(ghost) ? (
            <button
              type="button"
              disabled={busy}
              onClick={writeActivity}
              data-testid="ghost-activity"
              className="flex w-full items-start gap-2 rounded-md border border-border bg-background px-2.5 py-2 text-left hover:border-cyan-600 hover:bg-cyan-500/[0.05] disabled:opacity-60"
            >
              <PencilLine className="mt-0.5 size-3.5 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
              <span className="min-w-0">
                <span className="block text-[13px] font-semibold text-foreground">
                  Etkinlik olarak yaz: {ghost.label}
                </span>
                <span className="block text-[12px] text-muted-foreground">
                  Kitaba bağlı değil — test sayısına ve kitap ilerlemesine girmez.
                </span>
              </span>
            </button>
          ) : null}

          {ghost.chips.length > 0 ? (
            <ul className="space-y-1.5">
              {ghost.chips.map((c) => {
                const k = KIND_LABEL[c.kind] ?? KIND_LABEL.new;
                const n = c.items ? c.count : (countOverride ?? c.count);
                const over = !c.items && n > c.remaining;
                return (
                  <li key={`${c.rank}-${c.section_id}`}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => pick(c)}
                      data-testid="ghost-chip"
                      className="w-full rounded-md border border-border bg-background px-2.5 py-2 text-left hover:border-cyan-600 hover:bg-cyan-500/[0.05] disabled:opacity-60"
                    >
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className={cn("rounded px-1.5 py-px text-[10px] font-semibold", k.cls)}>
                          {k.label}
                        </span>
                        <span className="text-[13px] font-semibold text-foreground">
                          {chipTitle(c)}
                        </span>
                        {c.items && c.items.length > 1 ? null : (
                          <span className="text-[12px] text-muted-foreground">{c.book_name}</span>
                        )}
                        <span
                          className={cn(
                            "ml-auto rounded px-1.5 py-px text-[11px] font-semibold tabular-nums",
                            over ? "bg-amber-700 text-white" : "bg-foreground text-background",
                          )}
                          title={over ? `Bölümde ${c.remaining} test kaldı — kapasite aşılır` : undefined}
                        >
                          {n} test
                        </span>
                      </div>
                      {c.items && c.items.length > 1 ? (
                        <ul className="mt-1 flex flex-wrap gap-1" data-testid="ghost-chip-items">
                          {c.items.map((it) => (
                            <li
                              key={it.section_id}
                              className="rounded border border-border px-1.5 py-px text-[11.5px] text-foreground"
                            >
                              {it.section_label} · {it.count}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      <div className="mt-0.5 text-[12px] text-muted-foreground">{c.reason}</div>
                      {c.badges.length > 0 ? (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {c.badges.slice(0, 3).map((b, i) => (
                            <span
                              key={`${b.code}-${i}`}
                              className={cn(
                                "rounded px-1.5 py-px text-[10.5px] font-semibold",
                                BADGE_FILL[b.tone] ?? BADGE_FILL.slate,
                              )}
                            >
                              {b.label}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}

          {other ? (
            <div className="@container rounded-md border border-border p-2">
              <TaskQuickAdd
                studentId={studentId}
                dayDate={ghost.date}
                period={ghost.period}
                initialQuery={ghost.subject_name}
                autoOpen
                onAfterAdd={() => setOpen(false)}
                onSourcePick={({ section_id, count }) =>
                  accept.mutate(
                    {
                      slot_id: ghost.slot_id,
                      date: ghost.date,
                      section_id,
                      count,
                      chip_rank: null,
                    },
                    {
                      onSuccess: () =>
                        afterAccept({
                          topicId: null,
                          sectionId: section_id,
                          count,
                          title: ghost.subject_name,
                        }),
                    },
                  )
                }
              />
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setOther(true)}
              className="inline-flex items-center gap-1 text-[12px] text-cyan-800 hover:underline dark:text-cyan-300"
            >
              <Search className="size-3" aria-hidden /> Başka konu seç
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}

/** Gün kartı içinde: günün hayaletleri (periyotlu ise periyot etiketiyle). */
export function DayGhostRows({
  studentId,
  date,
  ghosts,
  weekEnd,
}: {
  studentId: number;
  date: string;
  ghosts: GhostCell[];
  /** Görüntülenen haftanın son günü — "bu haftanın rutinleri" için */
  weekEnd?: string;
}) {
  const routine = useAcceptRoutine(studentId);
  if (ghosts.length === 0) return null;
  const routineCount = ghosts.filter(isWritableRoutine).length;
  const usePeriods = ghosts.some((g) => g.period != null);
  const order = ["morning", "noon", "evening", "none"];
  const sorted = [...ghosts].sort(
    (a, b) =>
      order.indexOf(a.period ?? "none") - order.indexOf(b.period ?? "none") ||
      a.position - b.position,
  );
  const canWeek = !!weekEnd && weekEnd > date;

  return (
    <div
      className="border-t border-border border-l-[3px] border-l-cyan-600/60 px-4 py-3 space-y-2"
      data-section="day:skeleton-ghosts"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          İskeletten öneriler
        </span>
        <span className="text-[11px] text-muted-foreground">
          görev değil — tıkla, konuyu seç
        </span>
        {routineCount > 0 ? (
          <span className="ml-auto flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              disabled={routine.isPending}
              onClick={() => routine.mutate({ date })}
              className="inline-flex items-center gap-1 rounded-md bg-emerald-700 px-2 py-1 text-[11.5px] font-semibold text-white hover:bg-emerald-800 disabled:opacity-60"
            >
              <Check className="size-3.5" aria-hidden />
              Rutinleri onayla ({routineCount})
            </button>
            {canWeek ? (
              <button
                type="button"
                disabled={routine.isPending}
                onClick={() => routine.mutate({ date, end: weekEnd })}
                title="Bugünden haftanın sonuna kadar her günün rutinleri sırayla yazılır — her gün bir öncekinin kaldığı yerden devam eder"
                className="inline-flex items-center gap-1 rounded-md border border-emerald-700 px-2 py-1 text-[11.5px] font-semibold text-emerald-800 hover:bg-emerald-500/10 disabled:opacity-60 dark:border-emerald-400 dark:text-emerald-300"
              >
                <CalendarCheck className="size-3.5" aria-hidden />
                Haftanın rutinleri
              </button>
            ) : null}
          </span>
        ) : null}
      </div>
      <div className="space-y-1.5">
        {sorted.map((g, i) => {
          const prev = sorted[i - 1];
          const showPeriod =
            usePeriods && (i === 0 || (prev?.period ?? null) !== (g.period ?? null));
          return (
            <React.Fragment key={`${g.slot_id}-${g.date}`}>
              {showPeriod ? (
                <div className="pt-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  {g.period ? SKELETON_PERIOD_LABELS[g.period] : "Zaman belirtilmemiş"}
                </div>
              ) : null}
              <GhostRow studentId={studentId} ghost={g} />
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

/** Hafta Izgarası hücresi içinde: kesikli "öneri" satırları (salt görünüm). */
export function GridGhostCells({ ghosts }: { ghosts: GhostCell[] }) {
  if (ghosts.length === 0) return null;
  return (
    <div className="space-y-0.5" data-testid="grid-ghosts">
      {ghosts.map((g) => {
        const source = ghostSource(g);
        return (
          <div
            key={`${g.slot_id}-${g.date}`}
            className="rounded border border-dashed border-slate-400/70 px-1 py-0.5 text-[10px] leading-tight text-muted-foreground dark:border-slate-500"
            title={
              g.chips[0]
                ? `Öneri: ${g.subject_name}${source ? ` · ${source}` : ""} — ${chipTitle(g.chips[0])} (${g.chips[0].reason})`
                : `Öneri: ${g.subject_name}${source ? ` · ${source}` : ""}`
            }
          >
            <span className="font-semibold text-foreground/80">{g.subject_name}</span>
            {g.is_routine ? <span className="italic"> · rutin</span> : <span className="italic"> · öneri</span>}
          </div>
        );
      })}
    </div>
  );
}
