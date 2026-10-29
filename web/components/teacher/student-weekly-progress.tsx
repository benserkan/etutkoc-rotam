"use client";

/**
 * Öğrenci detayı · Genel sekmesi — haftalık ilerleme (2026-10-20 onaylı taslak).
 *   1 Bu hafta (görev uyumu + çözülen test, aynı güne kadar kıyas) + gün gün
 *   2 Haftalar arası gidişat (son 8 program haftası) · 3 Önerilen önlemler
 *   4 13 başlık kartları (cetvel: gri nokta = geçmiş hafta) · 5 Deneme analizi (D4)
 * Veri: GET /teacher/students/{id}/weekly-progress (app/services/weekly_progress.py).
 */
import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Info, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAddAgendaItems } from "@/lib/hooks/use-exam-progress-mutations";
import {
  getWeeklyProgress,
  weeklyProgressKeys,
  type WPCard,
  type WPDay,
  type WeeklyProgressResponse,
} from "@/lib/api/weekly-progress";
import type { DenemeAnalysisSeries } from "@/lib/api/deneme";
import { cn } from "@/lib/utils";

const fmtPct = (v: number | null | undefined) => (v == null ? "—" : `%${Math.round(v)}`);

function isWarn(c: { status: string; trend?: boolean }) {
  return c.status === "below" || c.status === "critical" || !!c.trend;
}

const STATUS_LABEL: Record<string, string> = {
  insufficient: "Veri az",
  normal: "Her zamanki",
  // below/above yönden bağımsızdır: "Gece çalışma"da az değer iyi → above.
  below: "Normalden kötü",
  critical: "Geçmişin en kötüsü",
  above: "Normalden iyi",
  high: "Her zamankinden fazla",
  low: "Her zamankinden az",
};

export function StatusChip({ card }: { card: WPCard }) {
  // Kıyas yapılmayan bilgi kartı: "Her zamanki" gibi yanıltıcı bir rozet basma.
  if (card.status === "info" && card.key !== "balance") return null;
  let label = STATUS_LABEL[card.status] ?? card.status;
  let cls = "bg-slate-100 text-slate-700";
  if (card.key === "balance" && card.status === "below") label = "Kaçınılan ders";
  if (card.key === "balance" && card.status === "info") label = "Dengeli";
  if (card.key === "exam_net" && card.status === "above") label = "Yükseliyor";
  if (card.key === "exam_net" && card.status === "below") label = "Düştü";
  if (card.status === "critical") cls = "bg-rose-700 text-white";
  else if (card.status === "below") cls = "bg-orange-100 text-orange-800";
  else if (card.status === "above") cls = "bg-blue-100 text-blue-800";
  if (card.trend && (card.status === "normal" || card.status === "above" || card.status === "insufficient")) {
    label = `${card.trend_run} hafta üst üste kötüleşme`;
    cls = "border border-orange-400 bg-card text-orange-800";
  }
  return (
    <span className={cn("inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-[11px] font-bold", cls)}>
      {label}
    </span>
  );
}

// -----------------------------------------------------------------------------
// Cetvel: gri nokta = geçmiş hafta · gölge = haftaların yarısı · çizgi = bu hafta · halka = geçen hafta
// -----------------------------------------------------------------------------

function niceScale(vals: number[], unit: string): [number, number] {
  if (unit === "%") {
    const mn = Math.min(...vals);
    const lo = Math.max(0, Math.floor((mn - 5) / 10) * 10);
    return [lo, 100];
  }
  const mn = Math.min(...vals);
  const mx = Math.max(...vals);
  const pad = Math.max(1, Math.round((mx - mn) * 0.2));
  return [Math.max(0, mn - pad), mx + pad];
}

function fmtUnit(v: number, unit: string) {
  return unit === "%" ? `%${Math.round(v)}` : `${Math.round(v)}${unit ? ` ${unit}` : ""}`;
}

export function Ruler({ card }: { card: WPCard }) {
  if (card.value == null || card.low == null || card.high == null || card.baseline.length === 0) return null;
  const all = [...card.baseline, card.value, ...(card.prev != null ? [card.prev] : [])];
  const [s0, s1] = niceScale(all, card.unit);
  const p = (v: number) => Math.max(0, Math.min(100, (100 * (v - s0)) / (s1 - s0 || 1)));
  const lbl = (v: number) => Math.max(9, Math.min(91, p(v)));
  const warn = isWarn(card);
  return (
    <div className="relative h-[84px]" aria-label={`Bu hafta ${card.value_label}; genelde ${fmtUnit(card.low, card.unit)} ile ${fmtUnit(card.high, card.unit)} arası`}>
      <div
        className={cn(
          "absolute top-0 -translate-x-1/2 whitespace-nowrap text-xs font-extrabold",
          warn ? "text-orange-700" : "text-foreground",
        )}
        style={{ left: `${lbl(card.value)}%` }}
      >
        bu hafta {fmtUnit(card.value, card.unit)}
      </div>
      <div className="absolute inset-x-0 top-[33px] h-1.5 rounded-full bg-slate-200" />
      <div
        className="absolute top-[29px] h-3.5 rounded bg-cyan-600/20"
        style={{ left: `${p(card.low)}%`, width: `${Math.max(1.5, p(card.high) - p(card.low))}%` }}
      />
      {card.baseline.map((v, i) => (
        <div
          key={i}
          className="absolute top-[31px] size-2.5 -ml-[5px] rounded-full bg-slate-400 opacity-80"
          style={{ left: `${p(v)}%` }}
        />
      ))}
      {card.prev != null ? (
        <div
          className="absolute top-[30px] size-3 -ml-1.5 rounded-full border-2 border-slate-700 bg-card"
          style={{ left: `${p(card.prev)}%` }}
        />
      ) : null}
      <div
        className={cn(
          "absolute top-[22px] h-7 w-1 -ml-0.5 rounded",
          warn ? "bg-orange-700" : "bg-foreground",
        )}
        style={{ left: `${p(card.value)}%` }}
      />
      {card.prev != null ? (
        <div
          className="absolute top-[49px] -translate-x-1/2 whitespace-nowrap text-[11px] font-semibold text-muted-foreground"
          style={{ left: `${lbl(card.prev)}%` }}
        >
          geçen hafta {fmtUnit(card.prev, card.unit)}
        </div>
      ) : null}
      <div className="absolute inset-x-0 top-[68px] flex justify-between text-[11px] text-muted-foreground">
        <span>{fmtUnit(s0, card.unit)}</span>
        <span>{fmtUnit((s0 + s1) / 2, card.unit)}</span>
        <span>{fmtUnit(s1, card.unit)}</span>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------

function Zone({
  no,
  eyebrow,
  title,
  desc,
  tone,
  right,
  children,
  className,
}: {
  no: number;
  eyebrow: string;
  title: string;
  desc: React.ReactNode;
  tone: "cyan" | "indigo" | "amber" | "slate" | "violet";
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const eye = {
    cyan: "text-cyan-800",
    indigo: "text-indigo-700",
    amber: "text-amber-800",
    slate: "text-slate-700",
    violet: "text-violet-700",
  }[tone];
  return (
    // J dili (tek tema): bölüm başlığı kartın DIŞINDA, zemin beyaz; içerik
    // kendi çerçeveli kartlarında durur (renkli "tepsi" kutusu yok).
    <section className={cn("flex flex-col gap-4", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <div className={cn("text-xs font-extrabold tracking-[.08em]", eye)}>
            {no} · {eyebrow}
          </div>
          <h2 className="text-xl font-extrabold sm:text-[22px]">{title}</h2>
          <div className="text-sm leading-relaxed text-muted-foreground">{desc}</div>
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------- 1 BU HAFTA

function HeadlineCard({ card, title, sub }: { card: WPCard | undefined; title: string; sub: string }) {
  if (!card) return null;
  const warn = isWarn(card);
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border p-4",
        warn
          ? "border-orange-300 bg-orange-50"
          : "border-border bg-card",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className={cn("text-[13px] font-bold tracking-wide", warn ? "text-orange-900" : "text-foreground")}>
          {title}
        </div>
        <StatusChip card={card} />
      </div>
      <div className="flex items-baseline gap-3">
        <div className={cn("text-4xl font-extrabold leading-none", warn ? "text-orange-900" : "text-foreground")}>
          {card.value_label}
        </div>
        <div className="text-sm text-muted-foreground">{sub}</div>
      </div>
      <p className="text-[13px] leading-relaxed">{card.verdict}</p>
      <Ruler card={card} />
    </div>
  );
}

function DayCard({ d, usualStart, isPeriod }: { d: WPDay; usualStart: string; isPeriod: boolean }) {
  const [open, setOpen] = React.useState(false);
  const tone = {
    done: "border-sky-200 bg-sky-50",
    partial: "border-orange-300 bg-orange-50",
    missed: "border-rose-300 bg-rose-50",
    today: "border-2 border-cyan-700 bg-card",
    future: "border-dashed border-slate-300 bg-card",
    none: "border-dashed border-slate-300 bg-card",
  }[d.state];
  const pct = d.total ? Math.round((100 * d.done) / d.total) : 0;
  const bar = d.state === "partial" ? "bg-orange-600" : d.state === "missed" ? "bg-rose-600" : "bg-cyan-700";
  const note =
    d.state === "today"
      ? `Olağan başlama ${usualStart}`
      : d.state === "future"
        ? "görev planlı"
        : d.state === "none"
          ? isPeriod ? "kap boş" : "program yok"
          : d.missing.length
            ? `${d.missing.length} görev yapılmadı`
            : d.first_tick
              ? `Gününde · ${d.first_tick}`
              : "Tamamlandı";
  const popTitle =
    d.state === "today" ? "Bugünün görevleri (gün sürüyor)" : d.state === "future" ? "Planlı görevler" : `Yapılmayan ${d.missing.length} görev`;
  const hasPop = d.missing.length > 0;
  return (
    <div className="relative" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setOpen(false)}
        aria-expanded={hasPop ? open : undefined}
        className={cn("flex w-full min-w-0 flex-col gap-1.5 rounded-xl border p-2.5 text-left", tone)}
      >
        <div className="flex items-baseline justify-between gap-1.5">
          <span className="text-[13px] font-bold">{d.day}</span>
          <span className="text-[11px] text-muted-foreground">
            {d.label}
            {d.state === "today" ? " · bugün" : ""}
          </span>
        </div>
        <div className="text-xl font-extrabold leading-tight">
          {d.state === "future" ? d.total : `${d.done} / ${d.total}`}
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
          <div className={cn("h-full rounded-full", bar)} style={{ width: `${d.state === "future" ? 0 : pct}%` }} />
        </div>
        <div className="text-xs leading-snug">{note}</div>
      </button>
      {open && hasPop ? (
        <div className="absolute left-0 top-[calc(100%+6px)] z-20 w-64 rounded-lg bg-slate-900 p-3 text-white shadow-xl">
          <div className="mb-1.5 text-xs font-bold">{popTitle}</div>
          <ul className="space-y-1">
            {d.missing.slice(0, 8).map((m, i) => (
              <li key={i} className="flex justify-between gap-2 border-t border-white/10 pt-1 text-xs">
                <span className="break-words">{m.title}</span>
                {m.tests ? <span className="shrink-0 text-slate-300">{m.tests} test</span> : null}
              </li>
            ))}
            {d.missing.length > 8 ? (
              <li className="border-t border-white/10 pt-1 text-xs text-slate-300">+{d.missing.length - 8} görev daha</li>
            ) : null}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function ThisWeek({ data, studentId }: { data: WeeklyProgressResponse; studentId: number }) {
  const w = data.week!;
  const pr = data.projection;
  const g = data.headline.gorev_pct;
  const t = data.headline.test_done;
  const isPeriod = w.kind === "donem";
  const span =
    w.compare_days > 0
      ? `${data.days[0]?.day}–${data.days[Math.max(0, w.compare_days - 1)]?.day}`
      : "henüz geçen gün yok";
  return (
    <Zone
      no={1}
      eyebrow={isPeriod ? "BU DÖNEM" : "BU HAFTA"}
      tone="cyan"
      title={isPeriod ? "Bu dönem nasıl gidiyor?" : "Bu hafta nasıl gidiyor?"}
      desc={
        <>
          {w.ended ? (
            <>
              Son {isPeriod ? "havuz dönemi" : "program haftası"} ({w.label}) bitti; aktif{" "}
              {isPeriod ? "dönem" : "program"} yok. Aşağıdakiler {isPeriod ? "o dönemin" : "o haftanın"} tamamı.
            </>
          ) : (
            <>
              Kıyas, geçmiş {isPeriod ? "dönemlerin" : "haftaların"} <b>aynı gününe kadar</b> yapılır; bugün
              sürdüğü için sayılmaz.
            </>
          )}
          {w.kind === "takvim" && (
            <> Bu hafta için program kaydı açılmamış; görev günleri Pazartesi–Pazar haftası olarak sayıldı.</>
          )}
          {isPeriod && <> Havuz öğrencisinde her çalışma dönemi (iki seans arası) bir hafta yerine geçer.</>}
        </>
      }
      right={
        <Button asChild className="bg-cyan-700 text-white hover:bg-cyan-800">
          <Link href={isPeriod ? `/teacher/students/${studentId}/pool` : `/teacher/students/${studentId}/week?start=${w.start}`}>
            <CalendarDays className="size-4" aria-hidden /> {isPeriod ? "Havuzu aç" : `${w.label} programını aç`}
          </Link>
        </Button>
      }
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <HeadlineCard card={g} title="GÖREV UYUMU" sub={`${span}`} />
        <HeadlineCard card={t} title="ÇÖZÜLEN TEST" sub={`${span}`} />
        <div className="flex flex-col gap-2.5 rounded-xl border border-border bg-card p-4">
          <div className="text-[13px] font-bold tracking-wide">BÖYLE GİDERSE</div>
          {pr && pr.projected_pct != null && pr.band_low != null && pr.band_high != null ? (
            <p className="text-[15px] leading-relaxed">
              Bu tempoyla hafta sonunda görev uyumu <b>~{fmtPct(pr.projected_pct)}</b> olur. Öğrencinin
              tam haftası genelde {fmtPct(pr.band_low)}–{fmtPct(pr.band_high).slice(1)} —{" "}
              <b
                className={cn(
                  pr.position === "below" && "text-orange-700",
                  pr.position === "above" && "text-blue-700",
                )}
              >
                {pr.position === "below" ? "altında kalır" : pr.position === "above" ? "üstüne çıkar" : "her zamanki aralıkta kalır"}
              </b>
              .
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Tahmin için en az bir geçmiş gün ve 4 geçmiş program haftası gerekiyor.
            </p>
          )}
          {pr && pr.last4.length >= 3 && pr.slope_per_week != null ? (
            <p className="text-[13px] leading-relaxed text-muted-foreground">
              Son {pr.last4.length} haftanın eğilimi:{" "}
              <b
                className={cn(
                  pr.slope_per_week >= 1 && "text-blue-700",
                  pr.slope_per_week <= -1 && "text-orange-700",
                )}
              >
                {pr.slope_per_week >= 1 ? "yükseliyor" : pr.slope_per_week <= -1 ? "düşüyor" : "yatay"}
              </b>{" "}
              ({pr.last4.map((v) => fmtPct(v)).join(" → ")}, haftada {pr.slope_per_week > 0 ? "+" : ""}
              {pr.slope_per_week} puan).
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">Bu hafta verilen görev: {pr?.load ?? 0}.</p>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-1.5">
          <div className="text-[15px] font-extrabold">Gün gün</div>
          <div className="text-xs text-muted-foreground">Kartın üzerine gel ya da dokun: yapılmayan görevler açılır</div>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          {data.days.map((d) => (
            <DayCard key={d.date} d={d} usualStart={w.usual_start} isPeriod={isPeriod} />
          ))}
        </div>
      </div>
    </Zone>
  );
}

// ---------------------------------------------------------------- 2 GİDİŞAT

function Trend({ data }: { data: WeeklyProgressResponse }) {
  const ps = data.period_summary;
  const lo = ps?.band_low ?? null;
  const hi = ps?.band_high ?? null;
  const vals = data.chart.map((c) => c.value).filter((v): v is number => v != null);
  const floor = Math.max(0, Math.floor((Math.min(...vals, lo ?? 100) - 5) / 10) * 10);
  const pos = (v: number) => Math.max(0, Math.min(100, (100 * (v - floor)) / (100 - floor || 1)));
  return (
    <Zone
      no={2}
      eyebrow="GİDİŞAT"
      tone="indigo"
      title="Haftalar arası gidişat"
      desc="Son 8 program haftasında görev uyumu (tam haftalar; bu hafta bugüne kadar)."
      className="min-w-0 flex-[999_1_560px]"
    >
      <div className="flex flex-col gap-2 rounded-xl border border-indigo-200 bg-card px-4 pb-3 pt-5">
        <div className="mt-6 flex gap-2.5">
          <div className="flex h-44 w-9 flex-col justify-between text-right text-[11px] text-muted-foreground">
            <span>%100</span>
            <span>%{Math.round((100 + floor) / 2)}</span>
            <span>%{floor}</span>
          </div>
          <div className="relative h-44 min-w-0 flex-1 border-b border-l border-border">
            {lo != null && hi != null ? (
              <div
                className="absolute inset-x-0 bg-cyan-600/15"
                style={{ bottom: `${pos(lo)}%`, height: `${Math.max(1, pos(hi) - pos(lo))}%` }}
              />
            ) : null}
            <div className="absolute inset-0 flex">
              {data.chart.map((c, i) => {
                if (c.value == null) return <div key={i} className="flex-1" />;
                const p = pos(c.value);
                const below = lo != null && c.value < lo;
                const above = hi != null && c.value > hi;
                const color = c.current
                  ? "border-orange-700"
                  : below
                    ? "border-orange-600 bg-orange-600"
                    : above
                      ? "border-blue-700 bg-blue-700"
                      : "border-cyan-700 bg-cyan-700";
                const text = c.current || below
                  ? "text-orange-700"
                  : above
                    ? "text-blue-700"
                    : "text-cyan-800";
                return (
                  <div key={i} className="relative flex-1" title={`${c.range}: ${fmtPct(c.value)}`}>
                    <div className="absolute bottom-0 left-1/2 w-0.5 -ml-px bg-slate-200" style={{ height: `${p}%` }} />
                    <div
                      className={cn("absolute left-1/2 size-3.5 -mb-[7px] -ml-[7px] rounded-full border-[3px]", color, c.current && "bg-card")}
                      style={{ bottom: `${p}%` }}
                    />
                    <div className={cn("absolute inset-x-0 text-center text-xs font-bold", text)} style={{ bottom: `calc(${p}% + 12px)` }}>
                      {fmtPct(c.value)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        <div className="flex gap-2.5">
          <div className="w-9" />
          <div className="flex min-w-0 flex-1">
            {data.chart.map((c, i) => (
              <div key={i} className="min-w-0 flex-1 text-center text-[11px] leading-tight text-muted-foreground">
                {c.label}
                {c.current ? <span className="block">(bugüne kadar)</span> : null}
              </div>
            ))}
          </div>
        </div>
        {lo != null && hi != null ? (
          <div className="flex items-center gap-2 pl-11 text-xs text-muted-foreground">
            <span className="h-3 w-6 rounded bg-cyan-600/20" />
            gölgeli alan: öğrencinin haftalarının yarısı {fmtPct(lo)}–{fmtPct(hi).slice(1)} arasında
          </div>
        ) : null}
      </div>
      {ps ? (
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          {[
            ["BU DÖNEM", `${ps.weeks} hafta`],
            ["ORTANCA HAFTA", fmtPct(ps.median)],
            ["EN İYİ", ps.best ? `${fmtPct(ps.best.value)} · ${ps.best.label}` : "—"],
            ["EN DÜŞÜK", ps.worst ? `${fmtPct(ps.worst.value)} · ${ps.worst.label}` : "—"],
          ].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-indigo-200 bg-card px-3.5 py-3">
              <div className="text-[11px] font-semibold text-muted-foreground">{k}</div>
              <div className="text-[15px] font-bold">{v}</div>
            </div>
          ))}
        </div>
      ) : null}
      {ps && ps.decline_run >= 3 ? (
        <div className="rounded-xl border border-orange-300 bg-card px-3.5 py-3 text-[13px] leading-relaxed">
          <b className="text-orange-800">Eğilim bilgisi:</b> görev uyumu son {ps.decline_run} haftadır
          her hafta düşüyor. Aralık içinde kalan düşüşler alarm değil, buradan izlenir.
        </div>
      ) : null}
      <p className="text-xs leading-relaxed text-muted-foreground">
        Taban: bu sınıf dönemindeki program haftaları. İlk 2 alışma haftası ve 4 günden kısa haftalar tabana girmez;
        4 haftadan az tabanda kıyas yapılmaz.
      </p>
    </Zone>
  );
}

// ---------------------------------------------------------------- 3 ÖNLEMLER

function Actions({ data, studentId }: { data: WeeklyProgressResponse; studentId: number }) {
  const add = useAddAgendaItems(studentId);
  return (
    <Zone
      no={3}
      eyebrow="ÖNLEMLER"
      tone="amber"
      title="Önerilen önlemler"
      desc="Her öneri bir ölçüme dayanır; karar senin."
      className="min-w-0 flex-[1_1_340px]"
    >
      {data.actions.length === 0 ? (
        <p className="rounded-xl border border-amber-200 bg-card p-4 text-sm text-muted-foreground">
          Bu hafta öne çıkan bir sorun yok.
        </p>
      ) : (
        data.actions.map((a) => (
          <div key={a.key} className="flex flex-col gap-2.5 rounded-xl border border-amber-200 bg-card p-3.5">
            <div className="text-sm font-bold leading-snug">{a.title}</div>
            <div className="text-xs leading-relaxed text-muted-foreground">
              <b className="text-foreground">Neden:</b> {a.why}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm" className="bg-cyan-700 text-white hover:bg-cyan-800">
                <Link href={a.cta_href}>
                  {a.cta_label} <ArrowRight className="size-3.5" aria-hidden />
                </Link>
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={add.isPending}
                onClick={() => add.mutate([{ text: a.agenda, key: `wp:${a.key}`, source: "weekly" }])}
              >
                <Plus className="size-3.5" aria-hidden /> Seansa ekle
              </Button>
            </div>
          </div>
        ))
      )}
    </Zone>
  );
}

// ---------------------------------------------------------------- 4 KARTLAR

function MetricCard({ card }: { card: WPCard }) {
  const warn = isWarn(card);
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-2.5 rounded-xl border bg-card p-4",
        warn ? "border-orange-300" : "border-border",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-bold">{card.name}</span>
        <StatusChip card={card} />
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">{card.hint}</p>
      <div className="text-[28px] font-extrabold leading-none">{card.value_label}</div>
      <p className="text-[13px] leading-relaxed">{card.verdict}</p>
      <Ruler card={card} />
    </div>
  );
}

const GROUP_TONE: Record<string, { head: string; line: string }> = {
  gelisim: {
    head: "text-teal-800",
    line: "border-teal-600",
  },
  ilerleme: {
    head: "text-blue-800",
    line: "border-blue-600",
  },
  risk: {
    head: "text-orange-800",
    line: "border-orange-600",
  },
};

function Metrics({ data }: { data: WeeklyProgressResponse }) {
  return (
    <Zone
      no={4}
      eyebrow="13 BAŞLIK"
      tone="slate"
      title="Bu hafta, öğrencinin kendi normaline göre"
      desc="Her kart, öğrencinin geçmiş program haftalarının aynı noktasıyla kıyaslanır."
    >
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl bg-slate-50 px-3.5 py-2.5 text-xs">
        <b>Cetveller nasıl okunur?</b>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-slate-400" />
          her nokta geçmiş bir hafta
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-6 rounded bg-cyan-600/20" />
          &quot;genelde&quot;: haftaların yarısı bu aralıkta
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-4 w-1 rounded bg-foreground" />
          bu hafta
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded-full border-2 border-slate-700" />
          geçen hafta
        </span>
      </div>
      {data.groups.map((g) => {
        const cards = data.cards.filter((c) => c.group === g.key);
        if (cards.length === 0) return null;
        const t = GROUP_TONE[g.key];
        return (
          <div key={g.key} className="flex flex-col gap-3.5">
            <div className={cn("flex flex-wrap items-baseline gap-2.5 border-b-2 pb-2", t.line)}>
              <span className={cn("text-[17px] font-extrabold", t.head)}>{g.name}</span>
              <span className="text-[13px] text-muted-foreground">{g.desc}</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {cards.map((c) => (
                <MetricCard key={c.key} card={c} />
              ))}
            </div>
          </div>
        );
      })}
    </Zone>
  );
}

// ---------------------------------------------------------------- 5 DENEME

export function SeriesCard({ s }: { s: DenemeAnalysisSeries }) {
  const warn = s.decline_run >= 3 || s.last_position === "below";
  const pts = s.points.slice(-8);
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-3 rounded-xl border bg-card p-4",
        warn ? "border-orange-300" : "border-violet-200",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[15px] font-bold">{s.label}</div>
          <div className="text-xs text-muted-foreground">
            {s.count} deneme{pts[pts.length - 1]?.questions ? ` · ${pts[pts.length - 1].questions} soru` : ""}
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold",
            s.decline_run >= 3
              ? "border border-orange-400 bg-card text-orange-800"
              : s.normal_low == null
                ? "bg-slate-100 text-slate-700"
                : s.last_position === "below"
                  ? "bg-orange-100 text-orange-800"
                  : "bg-slate-100 text-slate-700",
          )}
        >
          {s.decline_run >= 3
            ? `${s.decline_run} deneme üst üste düşüş`
            : s.normal_low == null
              ? "Veri az"
              : s.last_position === "below"
                ? "Normalin altında"
                : s.last_position === "above"
                  ? "Normalin üstünde"
                  : "Normal aralıkta"}
        </span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-extrabold leading-none">
          {pts[pts.length - 1]?.net.toLocaleString("tr-TR")} net
        </span>
        <span className="text-[13px] text-muted-foreground">
          net {fmtPct(s.last_net_pct)}
          {s.normal_low != null && s.normal_high != null ? ` · genelde ${fmtPct(s.normal_low)}–${fmtPct(s.normal_high).slice(1)}` : ""}
        </span>
      </div>
      <div className="relative h-[70px] border-b border-border">
        {s.normal_low != null && s.normal_high != null ? (
          <div
            className="absolute inset-x-0 bg-cyan-600/15"
            style={{ bottom: `${s.normal_low}%`, height: `${Math.max(1, s.normal_high - s.normal_low)}%` }}
          />
        ) : null}
        <div className="absolute inset-0 flex items-end gap-1.5">
          {pts.map((p, i) => (
            <div
              key={p.exam_id}
              title={`${p.date} · ${p.net} net (%${p.net_pct ?? "—"})`}
              className={cn(
                "flex-1 rounded-t",
                i === pts.length - 1 ? (warn ? "bg-orange-600" : "bg-cyan-700") : "bg-slate-400",
              )}
              style={{ height: `${Math.max(3, p.net_pct ?? 0)}%` }}
            />
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
        <div>
          <span className="text-muted-foreground">Denemede doğruluk:</span> <b>{fmtPct(s.accuracy_pct)}</b>
        </div>
        <div>
          <span className="text-muted-foreground">Testlerde doğruluk:</span> <b>{fmtPct(s.test_accuracy_pct)}</b>
        </div>
        <div>
          <span className="text-muted-foreground">Boş oranı:</span> <b>{fmtPct(s.blank_rate_pct)}</b>
        </div>
        <div>
          <span className="text-muted-foreground">Soru başı:</span>{" "}
          <b>{s.min_per_question != null ? `${s.min_per_question.toLocaleString("tr-TR")} dk` : "—"}</b>
        </div>
      </div>
      {s.test_accuracy_pct != null && s.accuracy_pct != null && s.test_accuracy_pct - s.accuracy_pct >= 15 ? (
        <p className="text-xs leading-relaxed">
          Testlerde {fmtPct(s.test_accuracy_pct)}, denemede {fmtPct(s.accuracy_pct)} doğru: konu biliniyor, süre
          baskısında ya da karma soruda zorlanıyor olabilir.
        </p>
      ) : null}
      {s.projected_net_pct != null ? (
        <p className="text-xs text-muted-foreground">Böyle giderse 4 deneme sonra net ~{fmtPct(s.projected_net_pct)}.</p>
      ) : null}
    </div>
  );
}

function Deneme({ data, studentId }: { data: WeeklyProgressResponse; studentId: number }) {
  const dn = data.deneme;
  const branch = (dn?.series ?? []).filter((s) => s.kind === "brans");
  const genel = (dn?.series ?? []).filter((s) => s.kind === "genel");
  return (
    <Zone
      no={5}
      eyebrow="DENEMELER"
      tone="violet"
      title="Deneme analizi"
      desc="Programdaki deneme görevlerinden; net yüzdesi = net ÷ soru sayısı (farklı soru sayılı denemeler yan yana konur)."
      right={
        <div className="flex flex-wrap items-center gap-2">
          {dn && dn.summary.pending > 0 ? (
            <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-900">
              {dn.summary.pending} denemenin sonucu girilmedi
            </span>
          ) : null}
          <Link href={`/teacher/students/${studentId}#program-exams`} className="text-[13px] font-semibold text-cyan-800 hover:underline">
            Branş denemeleri analizi
          </Link>
        </div>
      }
    >
      {branch.length === 0 && genel.length === 0 ? (
        <p className="rounded-xl border border-violet-200 bg-card p-4 text-sm text-muted-foreground">
          Henüz sonucu girilmiş program denemesi yok. Deneme görevlerinde öğrenci doğru/yanlış girdikçe burada ders
          ders gidişat oluşur.
        </p>
      ) : (
        <div className="grid gap-3.5 md:grid-cols-2 xl:grid-cols-3">
          {[...branch, ...genel].map((s) => (
            <SeriesCard key={s.key} s={s} />
          ))}
        </div>
      )}
    </Zone>
  );
}

// ---------------------------------------------------------------- kök

export function StudentWeeklyProgress({ studentId }: { studentId: number }) {
  const q = useQuery({
    queryKey: weeklyProgressKeys.detail(studentId),
    queryFn: () => getWeeklyProgress(studentId),
    staleTime: 30_000,
  });
  if (q.isLoading) {
    return <div className="h-64 animate-pulse rounded-2xl bg-muted" aria-label="Yükleniyor" />;
  }
  if (q.isError || !q.data) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground">
        Haftalık ilerleme yüklenemedi.
      </div>
    );
  }
  const data = q.data;
  if (!data.has_program || !data.week) {
    return (
      <div className="flex items-start gap-3 rounded-2xl border border-cyan-300 bg-cyan-50 p-5 text-sm">
        <Info className="mt-0.5 size-5 shrink-0 text-cyan-800" aria-hidden />
        <div>
          <p className="font-semibold">Henüz program haftası yok.</p>
          <p className="mt-1 text-muted-foreground">
            İlk haftalık programı oluşturunca burada haftanın gidişatı ve öğrencinin kendi normaline göre kıyas görünür.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-10" data-section="student:weekly-progress">
      <ThisWeek data={data} studentId={studentId} />
      <div className="flex flex-wrap items-stretch gap-7">
        <Trend data={data} />
        <Actions data={data} studentId={studentId} />
      </div>
      <Metrics data={data} />
      <Deneme data={data} studentId={studentId} />
    </div>
  );
}
