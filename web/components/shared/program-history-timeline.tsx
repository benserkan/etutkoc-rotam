"use client";

/**
 * Program geçmişi zaman çizelgesi (2026-10-22) — gün gün haftalar + havuz dönemleri + mod
 * geçişleri TEK listede, yeniden eskiye. Koç (öğrenci detayı "Program geçmişi" sekmesi) ve
 * öğrenci ("Program geçmişim") aynı bileşeni kullanır; haftanın açılınca ne göstereceğini
 * çağıran belirler (`renderWeekDetail`), dönem açılınca `onOpenPeriod` (mevcut dönem penceresi).
 */
import * as React from "react";
import { ArrowRightLeft, CalendarDays, ChevronDown, ChevronRight, Layers, Scissors } from "lucide-react";

import { cn } from "@/lib/utils";
import type { HistoryEntry, HistoryWeek, ProgramHistoryResponse } from "@/lib/api/program-history";

const MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
  "Ekim", "Kasım", "Aralık"];
const MONTHS_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
const DOW = ["Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"];

function parse(d: string) {
  const [y, m, day] = d.split("-").map(Number);
  return new Date(y, m - 1, day);
}

function shortDate(d: string) {
  const x = parse(d);
  return `${x.getDate()} ${MONTHS_SHORT[x.getMonth()]}`;
}

export function rangeLabel(a: string, b: string | null) {
  if (!b) return `${shortDate(a)} → sürüyor`;
  const x = parse(a);
  const y = parse(b);
  if (x.getMonth() === y.getMonth()) return `${x.getDate()}–${y.getDate()} ${MONTHS_SHORT[y.getMonth()]}`;
  return `${shortDate(a)} – ${shortDate(b)}`;
}

function dayCount(a: string, b: string) {
  return Math.round((parse(b).getTime() - parse(a).getTime()) / 86_400_000) + 1;
}

function pctTone(p: number) {
  if (p >= 70) return { text: "text-emerald-700", bar: "bg-emerald-500" };
  if (p >= 40) return { text: "text-amber-700", bar: "bg-amber-500" };
  return { text: "text-rose-700", bar: "bg-rose-500" };
}

function entryDate(e: HistoryEntry) {
  return e.week?.start ?? e.period?.opened_on ?? e.switch?.date ?? "";
}

export function weekKey(w: HistoryWeek) {
  return `${w.start}_${w.end}`;
}

type Filter = "all" | "gun_gun" | "havuz";

export function ProgramHistoryTimeline({
  data,
  renderWeekDetail,
  onOpenPeriod,
  emptyText = "Henüz geçmiş program yok.",
}: {
  data: ProgramHistoryResponse;
  /** Hafta açıldığında altında gösterilecek içerik (salt okunur). */
  renderWeekDetail: (w: HistoryWeek) => React.ReactNode;
  onOpenPeriod: (periodId: number) => void;
  emptyText?: string;
}) {
  const [filter, setFilter] = React.useState<Filter>("all");
  const [openWeek, setOpenWeek] = React.useState<string | null>(null);

  const entries = data.entries.filter((e) =>
    filter === "all" ? true : filter === "gun_gun" ? e.kind !== "period" : e.kind !== "week");
  // Aya göre grupla (giriş tarihine göre)
  const groups: { label: string; rows: HistoryEntry[] }[] = [];
  for (const e of entries) {
    const d = parse(entryDate(e));
    const label = `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.rows.push(e);
    else groups.push({ label, rows: [e] });
  }

  return (
    <div className="space-y-4" data-section="program-history">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-cyan-700 px-2.5 py-0.5 text-xs font-semibold text-white">
          Şu an: {data.program_mode_label}
        </span>
        <span className="text-xs text-muted-foreground">
          {data.weeks_count} gün gün hafta · {data.periods_count} havuz dönemi
        </span>
        <div className="ml-auto inline-flex rounded-md border bg-card p-0.5 text-xs" role="tablist" aria-label="Geçmiş süzgeci">
          {([["all", "Tümü"], ["gun_gun", "Gün gün haftalar"], ["havuz", "Havuz dönemleri"]] as const).map(([k, l]) => (
            <button key={k} type="button" role="tab" aria-selected={filter === k}
                    onClick={() => setFilter(k)}
                    className={cn("rounded px-2.5 py-1 font-medium",
                      filter === k ? "bg-cyan-700 text-white" : "text-muted-foreground hover:text-foreground")}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {groups.length === 0 ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        groups.map((g) => (
          <section key={g.label}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{g.label}</h3>
            <ol className="relative space-y-2 border-l border-border pl-4">
              {g.rows.map((e, i) => (
                <li key={`${e.kind}-${entryDate(e)}-${i}`} className="relative">
                  <span aria-hidden className={cn(
                    "absolute -left-[21px] top-3 size-2.5 rounded-full ring-2 ring-background",
                    e.kind === "period" ? "bg-cyan-600" : e.kind === "switch" ? "bg-violet-600" : "bg-slate-400",
                  )} />
                  {e.kind === "switch" && e.switch ? (
                    <SwitchRow s={e.switch} />
                  ) : e.kind === "period" && e.period ? (
                    <PeriodRow e={e} onOpen={() => onOpenPeriod(e.period!.id)} />
                  ) : e.week ? (
                    <WeekRow w={e.week} open={openWeek === weekKey(e.week)}
                             onToggle={() => setOpenWeek((v) => (v === weekKey(e.week!) ? null : weekKey(e.week!)))}>
                      {openWeek === weekKey(e.week) ? renderWeekDetail(e.week) : null}
                    </WeekRow>
                  ) : null}
                </li>
              ))}
            </ol>
          </section>
        ))
      )}
    </div>
  );
}

function SwitchRow({ s }: { s: NonNullable<HistoryEntry["switch"]> }) {
  const d = parse(s.date);
  return (
    <div className="rounded-lg border border-violet-300 bg-violet-50 px-3 py-2 text-sm text-violet-900"
         data-testid="history-switch">
      <div className="flex flex-wrap items-center gap-2 font-medium">
        <ArrowRightLeft className="size-4 shrink-0" aria-hidden />
        <span>{DOW[d.getDay()]} {shortDate(s.date)} · {s.from_label} → {s.to_label}</span>
      </div>
      {s.note && <p className="mt-0.5 text-xs text-violet-800">{s.note}</p>}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-xs text-muted-foreground">
      {label} <b className="font-semibold text-foreground">{value}</b>
    </span>
  );
}

function WeekRow({ w, open, onToggle, children }: {
  w: HistoryWeek; open: boolean; onToggle: () => void; children: React.ReactNode;
}) {
  const tone = pctTone(w.pct);
  const days = dayCount(w.start, w.end);
  return (
    <div className={cn("rounded-lg border bg-card", open && "ring-1 ring-cyan-600/40")} data-testid="history-week"
         data-start={w.start}>
      <button type="button" onClick={onToggle} aria-expanded={open}
              className="flex w-full flex-wrap items-center gap-x-4 gap-y-1.5 px-3 py-2.5 text-left hover:bg-muted/40">
        <span className="flex min-w-[11rem] items-center gap-2">
          {open ? <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            : <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />}
          <CalendarDays className="size-4 shrink-0 text-slate-500" aria-hidden />
          <span>
            <span className="block text-sm font-semibold text-foreground">{rangeLabel(w.start, w.end)}</span>
            <span className="block text-[11px] text-muted-foreground">
              {w.week_kind === "takvim" ? "Programsız görev günleri" : "Gün gün hafta"} · {days} gün
            </span>
          </span>
        </span>
        <span className="flex flex-wrap items-center gap-1.5">
          {w.current && <span className="rounded-full bg-slate-700 px-2 py-0.5 text-[10px] font-semibold text-white">Bu hafta</span>}
          {w.cut && (
            <span className="inline-flex items-center gap-1 rounded-full bg-violet-700 px-2 py-0.5 text-[10px] font-semibold text-white"
                  title="Program modu değiştiği için hafta erken bitti; haftalık eğilim hesabına katılmaz.">
              <Scissors className="size-3" aria-hidden /> Mod geçişiyle kısaldı
            </span>
          )}
        </span>
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Metric label="Görev" value={`${w.gorev_done}/${w.gorev_total}`} />
          {w.test_planned > 0 && <Metric label="Test" value={`${w.test_completed}/${w.test_planned}`} />}
          {w.deneme_units > 0 && <Metric label="Deneme" value={`${w.deneme_done}/${w.deneme_units}`} />}
        </span>
        <span className="ml-auto flex min-w-[7rem] items-center gap-2">
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
            <span className={cn("block h-full rounded-full", tone.bar)} style={{ width: `${Math.min(100, w.pct)}%` }} />
          </span>
          <span className={cn("text-sm font-bold tabular-nums", w.gorev_total ? tone.text : "text-muted-foreground")}>
            {w.gorev_total ? `%${w.pct}` : "—"}
          </span>
        </span>
      </button>
      {open && <div className="border-t px-3 py-3">{children}</div>}
    </div>
  );
}

function PeriodRow({ e, onOpen }: { e: HistoryEntry; onOpen: () => void }) {
  const p = e.period!;
  const tone = pctTone(p.pct);
  const empty = p.items_total === 0;
  return (
    <div className="rounded-lg border border-cyan-300 bg-card" data-testid="history-period">
      <button type="button" onClick={onOpen}
              className="flex w-full flex-wrap items-center gap-x-4 gap-y-1.5 px-3 py-2.5 text-left hover:bg-muted/40">
        <span className="flex min-w-[11rem] items-center gap-2">
          <Layers className="size-4 shrink-0 text-cyan-700" aria-hidden />
          <span>
            <span className="block text-sm font-semibold text-foreground">
              {rangeLabel(p.opened_on, p.closed_on ?? (e.period_current ? null : p.expected_next_on))}
            </span>
            <span className="block text-[11px] text-muted-foreground">
              Havuz dönemi{e.period_current && p.expected_next_on ? ` · beklenen seans ${shortDate(p.expected_next_on)}` : ""}
            </span>
          </span>
        </span>
        <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold text-white",
          e.period_current ? "bg-cyan-700" : "bg-slate-600")}>
          {e.period_current ? "Açık dönem" : p.status_label}
        </span>
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {empty ? <span className="text-xs text-muted-foreground">Havuz henüz boş</span> : (
            <>
              <Metric label="Kalem" value={`${p.items_done}/${p.items_total}`} />
              <Metric label="Birim" value={`${p.done_units}/${p.total_units}`} />
              {p.carried_out > 0 && <Metric label="Devredilen" value={String(p.carried_out)} />}
            </>
          )}
        </span>
        <span className="ml-auto flex min-w-[7rem] items-center gap-2">
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
            <span className={cn("block h-full rounded-full", tone.bar)} style={{ width: `${Math.min(100, p.pct)}%` }} />
          </span>
          <span className={cn("text-sm font-bold tabular-nums", empty ? "text-muted-foreground" : tone.text)}>
            {empty ? "—" : `%${p.pct}`}
          </span>
        </span>
      </button>
      {p.subjects.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-t px-3 py-2">
          {p.subjects.map((s) => (
            <span key={s.subject} className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] text-foreground">
              {s.subject} {s.done}/{s.total}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
