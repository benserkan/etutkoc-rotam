"use client";

/**
 * Dönem geçmişi — rehber havuz editörü (K60, 2026-10-13 yeniden tasarım).
 *
 * Her dönem bir kart: solda tarih bloğu (aralık + gün sayısı + durum), ortada ilerleme çubuğu (birim +
 * kalem) ve ders çipleri (Matematik 4/10 …), altında meta (devir girişi/çıkışı, seans kaydı, veli özeti),
 * sağda "Aç" + ⋯ menüsü (Dönemi aç · Veli özeti · Dönemi sil). Karta tıklamak da dönem penceresini açar.
 * Boş dönem (kalem yazılmamış) soluk kart + "Boş dönem" etiketi; veli özeti yok.
 *
 * Silme: onay penceresi önce etkiyi gösterir (kaç kalem gider, öğrencinin çalıştığı kap görevleri KORUNUR,
 * dokunulmamış kap görevleri silinir, devir bağı kopar). Açık dönem burada listelenmez (editör üst
 * çubuğundan yönetilir).
 */

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownLeft, ArrowUpRight, CalendarRange, ChevronRight, History, Loader2, Mail, MailCheck,
  MessagesSquare, MoreHorizontal, Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { PoolPeriodDialog } from "@/components/shared/pool-period-dialog";
import { PoolParentSummaryDialog } from "./pool-parent-summary-dialog";
import {
  getPoolHistory, getPoolPeriodDeleteImpact, getPoolPeriodDetail, poolHistoryKey, poolPeriodDeleteImpactKey,
  poolPeriodDetailKey, useDeletePoolPeriod,
  type PoolBundleResponse, type PoolHistoryRow,
} from "@/lib/api/pool";

const DAY_SHORT = ["Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"];

function parse(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function fmtShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  return parse(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

function rangeLabel(p: PoolHistoryRow): string {
  if (!p.closed_on || p.closed_on === p.opened_on) return fmtShort(p.opened_on);
  const a = parse(p.opened_on);
  const b = parse(p.closed_on);
  if (a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear()) {
    return `${a.getDate()}–${b.toLocaleDateString("tr-TR", { day: "numeric", month: "short" })}`;
  }
  return `${fmtShort(p.opened_on)} – ${fmtShort(p.closed_on)}`;
}

function dayInfo(p: PoolHistoryRow): string {
  const a = parse(p.opened_on);
  const b = p.closed_on ? parse(p.closed_on) : a;
  const n = Math.round((b.getTime() - a.getTime()) / 86_400_000) + 1;
  return `${n} gün · ${DAY_SHORT[a.getDay()]}${n > 1 ? `–${DAY_SHORT[b.getDay()]}` : ""}`;
}

const STATUS_TONE: Record<string, string> = {
  kapandi: "bg-emerald-700 text-white",
  ara: "bg-amber-400 text-amber-950",
  gorusmesiz: "bg-slate-600 text-white",
  acik: "bg-cyan-700 text-white",
};

function pctTone(pct: number): { bar: string; text: string } {
  if (pct >= 70) return { bar: "bg-emerald-500", text: "text-emerald-700" };
  if (pct >= 40) return { bar: "bg-amber-500", text: "text-amber-700" };
  return { bar: "bg-rose-500", text: "text-rose-700" };
}

export function PeriodHistory({ data }: { data: PoolBundleResponse }) {
  const studentId = data.student.id;
  const past = data.periods.filter((p) => p.status !== "acik");
  const [summaryFor, setSummaryFor] = React.useState<number | null>(null);
  const [detailFor, setDetailFor] = React.useState<number | null>(null);
  const [deleteFor, setDeleteFor] = React.useState<PoolHistoryRow | null>(null);
  const [limit, setLimit] = React.useState(10);
  // açık dönem de geçmiş ucunda ilk sırada gelir → sayfa boyutuna +1 (ilk sayfa 10 kapanmış dönem)
  const fetchLimit = limit + (data.period ? 1 : 0);
  const hist = useQuery({
    queryKey: poolHistoryKey(studentId, 0, fetchLimit),
    queryFn: () => getPoolHistory(studentId, 0, fetchLimit),
    enabled: past.length > 0,
    placeholderData: (prev) => prev,
  });
  if (!past.length) return null;
  const latest = past[0];
  const pending = latest && latest.status === "kapandi" && !latest.parent_summary_sent_at && latest.total_units > 0 ? latest : null;
  const rows: PoolHistoryRow[] = (hist.data?.rows ?? []).filter((r) => r.status !== "acik");
  const total = Math.max(0, (hist.data?.total ?? data.periods_total) - (data.period ? 1 : 0));

  return (
    <section className="rounded-xl border bg-card p-4 text-sm" data-section="pool:history">
      <header className="flex flex-wrap items-start gap-3">
        <span className="grid size-9 place-items-center rounded-lg bg-cyan-700 text-white" aria-hidden>
          <History className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="flex flex-wrap items-center gap-2 text-base font-semibold text-foreground">
            Dönem geçmişi
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">{total} dönem</span>
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Geçmiş sınırsız saklanır. Bir döneme tıkla: kalem kalem (ne verildi, ne bitti) ve gün gün (hangi gün ne çalıştı).
            {" "}Gün gün programdan kalan haftalar dahil tüm geçmiş için{" "}
            <Link href={`/teacher/students/${studentId}#history`} className="font-medium text-cyan-700 underline">
              Program geçmişi
            </Link>.
          </p>
        </div>
      </header>

      {pending && (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900" data-section="pool:history:pending-summary">
          <Mail className="size-4 shrink-0" aria-hidden />
          <span className="min-w-0 flex-1">Dönem kapandı ({fmtShort(pending.opened_on)} → {fmtShort(pending.closed_on)}) — veli özeti hazır; otomatik gitmez, önizleyip gönder.</span>
          <Button type="button" size="sm" className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white" onClick={() => setSummaryFor(pending.id)} data-testid="pool-parent-summary-open">
            Veli özetini önizle
          </Button>
        </div>
      )}

      <ul className="mt-3 space-y-2">
        {rows.map((p) => (
          <PeriodCard key={p.id} p={p}
                      onOpen={() => setDetailFor(p.id)}
                      onSummary={() => setSummaryFor(p.id)}
                      onDelete={() => setDeleteFor(p)} />
        ))}
      </ul>

      {total > rows.length && (
        <Button type="button" variant="outline" size="sm" className="mt-3 w-full" onClick={() => setLimit((l) => l + 10)} data-testid="pool-history-more">
          Daha fazla ({rows.length}/{total})
        </Button>
      )}

      <PoolParentSummaryDialog studentId={studentId} periodId={summaryFor} open={summaryFor != null}
                               onOpenChange={(v) => { if (!v) setSummaryFor(null); }} />
      <PoolPeriodDialog open={detailFor != null} onOpenChange={(v) => { if (!v) setDetailFor(null); }}
                        studentName={data.student.full_name}
                        queryKey={poolPeriodDetailKey(studentId, detailFor ?? 0)}
                        queryFn={() => getPoolPeriodDetail(studentId, detailFor!)} />
      <DeletePeriodDialog studentId={studentId} period={deleteFor} onClose={() => setDeleteFor(null)} />
    </section>
  );
}

function PeriodCard({ p, onOpen, onSummary, onDelete }: {
  p: PoolHistoryRow; onOpen: () => void; onSummary: () => void; onDelete: () => void;
}) {
  const empty = p.total_units === 0 && p.items_total === 0;
  const tone = pctTone(p.pct);
  const summaryAllowed = p.status !== "ara" && !empty;
  return (
    <li data-period={p.id}
        className={cn("group relative rounded-lg border bg-background transition hover:border-cyan-600/60 hover:shadow-sm",
          empty && "border-dashed bg-muted/30")}>
      <div className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
        {/* tarih bloğu */}
        <button type="button" onClick={onOpen} className="flex min-w-[9.5rem] items-center gap-3 text-left" aria-label="Dönemi aç">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground" aria-hidden>
            <CalendarRange className="size-5" />
          </span>
          <span className="min-w-0">
            <span className="block font-semibold text-foreground">{rangeLabel(p)}</span>
            <span className="block text-xs text-muted-foreground">{dayInfo(p)}</span>
            <span className={cn("mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold", STATUS_TONE[p.status] ?? STATUS_TONE.gorusmesiz)}>
              {p.status_label}
            </span>
          </span>
        </button>

        {/* ilerleme + dersler */}
        <button type="button" onClick={onOpen} className="min-w-0 flex-1 text-left">
          {empty ? (
            <span className="block text-sm text-muted-foreground">Boş dönem — bu dönemde kalem yazılmamış.</span>
          ) : (
            <>
              <span className="flex items-baseline gap-2">
                <span className={cn("text-lg font-bold tabular-nums", tone.text)}>%{p.pct}</span>
                <span className="text-xs text-muted-foreground">{p.done_units}/{p.total_units} birim · {p.items_done}/{p.items_total} kalem bitti</span>
              </span>
              <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
                <span className={cn("block h-full rounded-full", tone.bar)} style={{ width: `${Math.min(100, p.pct)}%` }} />
              </span>
              {p.subjects.length > 0 && (
                <span className="mt-2 flex flex-wrap gap-1" data-section="pool:history:subjects">
                  {p.subjects.map((s) => (
                    <span key={s.subject} className="rounded-md border bg-card px-1.5 py-0.5 text-[11px] text-foreground">
                      {s.subject} <span className="tabular-nums text-muted-foreground">{s.done}/{s.total}</span>
                    </span>
                  ))}
                </span>
              )}
            </>
          )}
          <span className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
            {p.carried_in > 0 && <span className="inline-flex items-center gap-1"><ArrowDownLeft className="size-3" aria-hidden />devir girişi {p.carried_in}</span>}
            {p.carried_out > 0 && <span className="inline-flex items-center gap-1"><ArrowUpRight className="size-3" aria-hidden />devredildi {p.carried_out}</span>}
            {p.session_marked_units > 0 && <span>seansta {p.session_marked_units} birim işaretlendi</span>}
            {p.has_session && <span className="inline-flex items-center gap-1"><MessagesSquare className="size-3" aria-hidden />seans kaydı var</span>}
            {p.parent_summary_sent_at && <span className="inline-flex items-center gap-1 text-emerald-700"><MailCheck className="size-3" aria-hidden />veliye gönderildi</span>}
            {p.note && <span className="break-words">not: {p.note}</span>}
          </span>
        </button>

        {/* eylemler */}
        <div className="flex shrink-0 items-center gap-1.5 self-end sm:self-center">
          <Button type="button" size="sm" onClick={onOpen} data-testid={`pool-period-open-${p.id}`}
                  className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white">
            Aç <ChevronRight className="size-4" aria-hidden />
          </Button>
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <Button type="button" size="sm" variant="ghost" className="size-8 p-0" aria-label="Dönem işlemleri" data-testid={`pool-period-menu-${p.id}`}>
                <MoreHorizontal className="size-4" aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuItem onSelect={onOpen}>Dönemi aç</DropdownMenuItem>
              {summaryAllowed && (
                <DropdownMenuItem onSelect={onSummary} data-testid={`pool-parent-summary-${p.id}`}>
                  {p.parent_summary_sent_at ? "Gönderilen veli özeti" : "Veli özeti"}
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={onDelete} data-testid={`pool-period-delete-${p.id}`}
                                className="text-rose-700 focus:bg-rose-50 focus:text-rose-800">
                <Trash2 className="size-4" aria-hidden /> Dönemi sil
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </li>
  );
}

function DeletePeriodDialog({ studentId, period, onClose }: {
  studentId: number; period: PoolHistoryRow | null; onClose: () => void;
}) {
  const open = period != null;
  const q = useQuery({
    queryKey: poolPeriodDeleteImpactKey(studentId, period?.id ?? 0),
    queryFn: () => getPoolPeriodDeleteImpact(studentId, period!.id),
    enabled: open,
    staleTime: 0,
  });
  const del = useDeletePoolPeriod(studentId);
  const im = q.data;
  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="sm:max-w-lg" data-section="pool:period-delete">
        <DialogHeader>
          <DialogTitle>Dönemi sil</DialogTitle>
          <DialogDescription>
            {period ? `${rangeLabel(period)} · ${period.status_label}` : ""} — bu işlem geri alınamaz.
          </DialogDescription>
        </DialogHeader>
        {!im ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Etki hesaplanıyor
          </div>
        ) : !im.deletable ? (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">{im.blocked_reason}</p>
        ) : (
          <ul className="space-y-1.5 text-sm" data-section="pool:period-delete:impact">
            <ImpactLine tone="rose">
              {im.items > 0 ? `${im.items} havuz kalemi silinir` : "Dönemde havuz kalemi yok"}
              {im.removed_items > 0 ? ` (+ ${im.removed_items} kaldırılmış kalem izi)` : ""}.
            </ImpactLine>
            {im.tasks_kept > 0 && (
              <ImpactLine tone="emerald">
                Öğrencinin çalıştığı {im.tasks_kept} görev korunur — Bugün/hafta geçmişinde ve kitap sayacında kalır, yalnız havuz bağı kopar.
              </ImpactLine>
            )}
            {im.tasks_deleted > 0 && <ImpactLine tone="rose">Hiç dokunulmamış {im.tasks_deleted} kap görevi silinir.</ImpactLine>}
            {im.done_units > 0 && <ImpactLine tone="amber">Dönemin {im.done_units} birimlik ilerleme kaydı ve yüzdesi geçmişten kalkar.</ImpactLine>}
            {im.session_marked_units > 0 && (
              <ImpactLine tone="slate">Seansta işaretlenen {im.session_marked_units} birimin kitap sayacındaki izli kaydı kalır.</ImpactLine>
            )}
            {im.carried_out > 0 && (
              <ImpactLine tone="slate">Sonraki döneme devredilen {im.carried_out} kalem yerinde kalır; yalnız devir bağı kopar.</ImpactLine>
            )}
            {im.parent_summary_sent && <ImpactLine tone="slate">Bu dönemin veli özeti gönderilmişti; gönderilen e-posta geri alınamaz.</ImpactLine>}
          </ul>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Vazgeç</Button>
          <Button type="button" disabled={!im?.deletable || del.isPending} data-testid="pool-period-delete-confirm"
                  className="bg-rose-700 text-white hover:bg-rose-800 hover:text-white"
                  onClick={() => period && del.mutate({ period_id: period.id }, { onSuccess: onClose })}>
            {del.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Trash2 className="size-4" aria-hidden />}
            Dönemi sil
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const DOT: Record<string, string> = {
  rose: "bg-rose-500", emerald: "bg-emerald-500", amber: "bg-amber-500", slate: "bg-slate-400",
};

function ImpactLine({ tone, children }: { tone: keyof typeof DOT; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-foreground">
      <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", DOT[tone])} aria-hidden />
      <span className="min-w-0">{children}</span>
    </li>
  );
}
