"use client";

/**
 * Geçmiş dönem penceresi (haftalık havuz, 2026-10-13) — rehber / öğrenci / veli ORTAK.
 *
 * İki sekme:
 *  · Havuz kalemleri — "ne verildi, ne bitti": ders gruplu; kalem başına verilen / öğrenci kaydı /
 *    seansta işaretlenen / kalan + rozetler (öğrenci kalemi, öğretmen ödevi, denemeden, devir ×N,
 *    devredildi). Rehberde kaçınma izi ("kaba 3 kez girdi, 2 kez geri döndü") + kaldırılanlar grubu.
 *  · Gün gün — "hangi gün ne çalıştı": açılış → kapanış her gün; kaba alınan görevler, çözülen test,
 *    D/Y/B; görevsiz gün "kap boş". Gün sonu kapanışı ilerlemesiz kap görevini SİLDİĞİ (K34) için
 *    "aldı ama dokunmadı" burada görünmez; kısmi görev gün sonunda küçüldüğünden "3 test çözdü" okunur.
 *
 * Veri sunucuda yüzeye göre süzülür (audience): öğrenci kaçınma sayacı görmez (K41), veli ayrıca
 * onay bekleyen kalemi görmez (K52). Bileşen yalnız gösterir; yazma yok.
 */

import * as React from "react";
import { useQuery, type QueryKey } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  SOURCE_LABELS, UNIT_LABELS, type PoolPeriodDayTask, type PoolPeriodDetailItem, type PoolPeriodDetailResponse,
} from "@/lib/api/pool";

const DAY_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

export function PoolPeriodDialog({ open, onOpenChange, queryKey, queryFn, studentName }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  queryKey: QueryKey;
  queryFn: () => Promise<PoolPeriodDetailResponse>;
  studentName?: string;
}) {
  const q = useQuery({ queryKey, queryFn, enabled: open });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl" data-section="pool:period-dialog">
        {!q.data ? (
          <>
            <DialogHeader><DialogTitle>Dönem</DialogTitle><DialogDescription>{q.isError ? "Dönem yüklenemedi." : "Yükleniyor…"}</DialogDescription></DialogHeader>
            {!q.isError && <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" aria-hidden /> Dönem hazırlanıyor</div>}
          </>
        ) : (
          <PeriodBody key={q.data.period.id} data={q.data} studentName={studentName} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function PeriodBody({ data, studentName }: { data: PoolPeriodDetailResponse; studentName?: string }) {
  const [tab, setTab] = React.useState<"items" | "days">("items");
  const p = data.period;
  const coach = data.audience === "teacher";
  const title = `${fmtDate(p.opened_on)} → ${p.closed_on ? fmtDate(p.closed_on) : "açık"}`;
  return (
    <>
      <DialogHeader>
        <DialogTitle>{studentName ? `${studentName} · ` : ""}Dönem {title}</DialogTitle>
        <DialogDescription>
          {p.status_label} · %{p.pct} · {p.done_units}/{p.total_units} birim · {p.items_done}/{p.items_total} kalem bitti
          {p.carried_in > 0 ? ` · devirle geldi ${p.carried_in}` : ""}
          {p.carried_out > 0 ? ` · devredildi ${p.carried_out}` : ""}
          {coach && p.session_marked_units > 0 ? ` · seansta ${p.session_marked_units} birim işaretlendi` : ""}
          {p.has_session ? " · seans kaydı var" : ""}
        </DialogDescription>
      </DialogHeader>
      {p.subjects.length > 0 && (
        <div className="flex flex-wrap gap-1.5" data-section="pool:period-dialog:subjects">
          {p.subjects.map((s) => (
            <span key={s.subject} className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-foreground">
              {s.subject} {s.done}/{s.total} · %{s.pct}
            </span>
          ))}
        </div>
      )}
      {coach && p.note && <p className="text-xs text-muted-foreground">Not: {p.note}</p>}
      <div className="flex gap-1 rounded-md bg-muted p-1 text-sm" role="tablist">
        <TabButton active={tab === "items"} onClick={() => setTab("items")} testid="pool-period-tab-items">Havuz kalemleri</TabButton>
        <TabButton active={tab === "days"} onClick={() => setTab("days")} testid="pool-period-tab-days">Gün gün</TabButton>
      </div>
      {tab === "items" ? <ItemsTab data={data} /> : <DaysTab data={data} />}
    </>
  );
}

function TabButton({ active, onClick, children, testid }: { active: boolean; onClick: () => void; children: React.ReactNode; testid: string }) {
  return (
    <button type="button" role="tab" aria-selected={active} onClick={onClick} data-testid={testid}
            className={cn("flex-1 rounded px-3 py-1.5 font-medium transition",
              active ? "bg-cyan-700 text-white" : "text-muted-foreground hover:bg-background hover:text-foreground")}>
      {children}
    </button>
  );
}

// ---------------------------------------------------------------- Sekme 1: havuz kalemleri

function ItemsTab({ data }: { data: PoolPeriodDetailResponse }) {
  const coach = data.audience === "teacher";
  const groups = new Map<string, PoolPeriodDetailItem[]>();
  for (const it of data.items) {
    const g = groups.get(it.subject_name) ?? [];
    g.push(it);
    groups.set(it.subject_name, g);
  }
  return (
    <div className="space-y-3 text-sm" data-section="pool:period-dialog:items">
      {data.items.length === 0 && <p className="text-muted-foreground">Bu dönemde kalem yok.</p>}
      {[...groups.entries()].map(([name, list]) => (
        <div key={name}>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{name}</div>
          <ul className="divide-y rounded-md border">
            {list.map((it) => <ItemRow key={it.id} it={it} coach={coach} />)}
          </ul>
        </div>
      ))}
      {coach && data.removed_items.length > 0 && (
        <div data-section="pool:period-dialog:removed">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Kaldırılanlar ({data.removed_items.length})</div>
          <ul className="divide-y rounded-md border border-dashed opacity-70">
            {data.removed_items.map((it) => <ItemRow key={it.id} it={it} coach={coach} />)}
          </ul>
          <p className="mt-1 text-[11px] text-muted-foreground">Rehber kaldırdı; iz olarak durur, yüzdeye girmez.</p>
        </div>
      )}
    </div>
  );
}

function ItemRow({ it, coach }: { it: PoolPeriodDetailItem; coach: boolean }) {
  const unit = UNIT_LABELS[it.unit] ?? it.unit;
  const done = it.done >= it.quantity;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2" data-item={it.id}>
      <span className={cn("min-w-0 flex-1 break-words", done ? "text-muted-foreground line-through" : "text-foreground", it.teacher_homework && "italic")}>
        {it.title}
        {it.day_hint && <span className="ml-1 text-[11px] text-muted-foreground">({fmtDate(it.day_hint)})</span>}
      </span>
      <span className="text-xs text-muted-foreground" data-field="progress">
        {it.quantity} {unit} verildi · öğrenci {it.completed}
        {it.session_marked > 0 ? ` · seansta ${it.session_marked}` : ""}
        {it.remaining > 0 ? ` · kalan ${it.remaining}` : " · bitti"}
      </span>
      <span className="flex flex-wrap gap-1">
        {it.source === "ogrenci" && (
          <Badge tone={it.approval === "onaylandi" ? "emerald" : it.approval === "reddedildi" ? "rose" : "amber"}>
            öğrenci ekledi{it.approval === "bekliyor" ? " · onay bekliyor" : it.approval === "reddedildi" ? " · reddedildi" : ""}
          </Badge>
        )}
        {it.teacher_homework && <Badge tone="violet">öğretmen ödevi</Badge>}
        {it.exam_linked && <Badge tone="sky">denemeden</Badge>}
        {it.source === "devir" && <Badge tone="slate">devir ×{it.carry_count}</Badge>}
        {it.source !== "devir" && it.source !== "ogrenci" && it.source !== "rehber" && <Badge tone="slate">{SOURCE_LABELS[it.source] ?? it.source}</Badge>}
        {it.carried_out && <Badge tone="cyan">sonraki döneme devredildi</Badge>}
        {coach && it.cup_attempts > 0 && (
          <Badge tone={it.cup_returns >= 3 ? "amber" : "slate"}>
            kaba {it.cup_attempts} kez girdi{it.cup_returns > 0 ? `, ${it.cup_returns} kez geri döndü` : ""}
          </Badge>
        )}
        {coach && it.cup_attempts === 0 && !done && <Badge tone="slate">hiç kaba alınmadı</Badge>}
      </span>
    </li>
  );
}

const TONES: Record<string, string> = {
  emerald: "bg-emerald-700 text-white",
  rose: "bg-rose-700 text-white",
  amber: "bg-amber-400 text-amber-950",
  violet: "bg-violet-600 text-white",
  sky: "bg-sky-700 text-white",
  cyan: "bg-cyan-700 text-white",
  slate: "bg-slate-600 text-white",
};

function Badge({ tone, children }: { tone: keyof typeof TONES; children: React.ReactNode }) {
  return <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", TONES[tone])}>{children}</span>;
}

// ---------------------------------------------------------------- Sekme 2: gün gün

function DaysTab({ data }: { data: PoolPeriodDetailResponse }) {
  const empty = data.days.filter((d) => d.tasks.length === 0).length;
  return (
    <div className="space-y-2 text-sm" data-section="pool:period-dialog:days">
      <p className="text-xs text-muted-foreground">
        Öğrencinin her gün kaba alıp işlediği görevler. Kap boş kalan gün &quot;kap boş&quot; yazar
        {empty > 0 ? ` (${empty} gün)` : ""}. Kaba alınıp hiç dokunulmayan görev gün sonunda havuza döndüğü için burada görünmez.
      </p>
      <ul className="space-y-1.5">
        {data.days.map((d) => (
          <li key={d.date} className={cn("rounded-md border px-3 py-2", d.tasks.length === 0 && "border-dashed bg-muted/40")} data-day={d.date}>
            <div className="flex items-center gap-2">
              <span className="font-medium text-foreground">{DAY_SHORT[d.weekday]} {fmtDate(d.date)}</span>
              {d.tasks.length === 0
                ? <span className="text-xs text-muted-foreground">kap boş</span>
                : <span className="ml-auto text-xs text-muted-foreground">{d.done_units} birim</span>}
            </div>
            {d.tasks.length > 0 && (
              <ul className="mt-1 space-y-0.5">
                {d.tasks.map((t) => <DayTaskRow key={t.task_id} t={t} />)}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function DayTaskRow({ t }: { t: PoolPeriodDayTask }) {
  const done = t.status === "completed";
  const dyb = t.correct != null || t.wrong != null || t.blank != null;
  return (
    <li className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
      <span className={cn("size-1.5 rounded-full", done ? "bg-emerald-500" : "bg-amber-400")} aria-hidden />
      <span className={cn("min-w-0 flex-1 break-words", done ? "text-foreground" : "text-muted-foreground")}>{t.title}</span>
      {t.period && <span className="text-muted-foreground">{t.period}</span>}
      <span className="text-muted-foreground">
        {t.itemless ? (done ? "yapıldı" : "yapılmadı") : `${t.done} test çözdü`}
        {dyb ? ` · ${t.correct ?? 0}D ${t.wrong ?? 0}Y ${t.blank ?? 0}B` : ""}
      </span>
    </li>
  );
}
