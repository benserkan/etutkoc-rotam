"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarCheck2, Gauge, Hourglass, TrendingDown, TrendingUp } from "lucide-react";

import { cn } from "@/lib/utils";
import { getStudentAnalytics, getStudentWeeklyProgress, studentProgressKeys } from "@/lib/api/student-progress";
import type { WPDay } from "@/lib/api/weekly-progress";

/**
 * Bugün sayfasında sınava hazırlık özeti (2026-10-21) — eski "Sınav projeksiyonu" kartının
 * yerine. Görev listesini aşağı itmeyecek kadar kısa: sınava kalan gün · bu hafta görev
 * uyumu · günlük tempo/gereken · bu gidişle fazla/eksik + haftanın günleri şeridi.
 * Ayrıntılar Gelişim sayfasında (/student/progress).
 */
const DAY_CLS: Record<WPDay["state"], string> = {
  done: "bg-emerald-600 text-white",
  partial: "bg-amber-400 text-amber-950",
  missed: "bg-rose-600 text-white",
  today: "bg-cyan-700 text-white ring-2 ring-cyan-300",
  future: "bg-muted text-muted-foreground",
  none: "border border-dashed border-border text-muted-foreground",
};

export function ProgressSummaryCard() {
  // Gelişim sayfasıyla AYNI önbellek + aynı sayılar (tempo/projeksiyon tek kaynak)
  const a = useQuery({
    queryKey: studentProgressKeys.analytics(),
    queryFn: getStudentAnalytics,
    staleTime: 60_000,
  });
  const w = useQuery({
    queryKey: studentProgressKeys.weekly(),
    queryFn: getStudentWeeklyProgress,
    staleTime: 60_000,
  });
  const wk = w.data?.has_program ? w.data : null;
  const gorev = wk?.headline.gorev_pct ?? null;
  const days = wk?.days ?? [];
  const p = a.data?.projection ?? null;
  const rate = a.data?.summary.rate_7d ?? null;
  const hasInv = p != null && p.total_tests > 0;
  const ok = hasInv ? p.gap >= 0 : null;

  return (
    <section
      className="overflow-hidden rounded-2xl border border-cyan-600/30 bg-gradient-to-br from-cyan-500/10 via-card to-indigo-500/10"
      data-section="student:progress-summary"
    >
      <div className="flex flex-wrap items-stretch gap-3 p-4">
        <div className="flex min-w-[8.5rem] flex-col justify-center rounded-xl bg-gradient-to-br from-cyan-800 to-indigo-900 px-4 py-3 text-white">
          <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-cyan-100">Sınava</span>
          {p?.days_left != null ? (
            <span className="font-display text-3xl font-extrabold leading-none tabular-nums">
              {p.days_left}
              <span className="ml-1 text-sm font-semibold text-cyan-100">gün</span>
            </span>
          ) : (
            <span className="text-sm font-semibold">tarih yok</span>
          )}
        </div>

        <div className="grid min-w-0 flex-1 grid-cols-1 gap-2 sm:grid-cols-3">
          <Tile
            icon={CalendarCheck2}
            label={wk?.week?.kind === "donem" ? "Bu dönem görev" : "Bu hafta görev"}
            value={gorev?.value != null ? `%${Math.round(gorev.value)}` : "—"}
            note={
              gorev && gorev.low != null && gorev.high != null
                ? `genelde %${Math.round(gorev.low)}–${Math.round(gorev.high)}`
                : "tamamlama oranı"
            }
            tone={
              gorev == null || gorev.status === "insufficient" || gorev.status === "info"
                ? "neutral"
                : gorev.status === "below" || gorev.status === "critical"
                  ? "warn"
                  : "good"
            }
          />
          <Tile
            icon={Gauge}
            label="Günlük tempo"
            value={rate != null ? `${rate.toLocaleString("tr-TR", { maximumFractionDigits: 1 })} test` : "—"}
            note={hasInv && p.required_rate > 0 ? `gereken ${p.required_rate.toLocaleString("tr-TR", { maximumFractionDigits: 1 })} test` : "son 7 günün ortalaması"}
            tone={rate == null || !hasInv ? "neutral" : rate >= p.required_rate ? "good" : "warn"}
          />
          <Tile
            icon={ok === false ? TrendingDown : ok ? TrendingUp : Hourglass}
            label="Bu gidişle"
            value={hasInv ? (p.remaining <= 0 ? "Bitti" : `${p.gap >= 0 ? "+" : "−"}${Math.abs(p.gap).toLocaleString("tr-TR")} test`) : "—"}
            note={hasInv ? (p.remaining <= 0 ? "kaynaklarını bitirdin" : p.gap >= 0 ? "kaynaklarını sınavdan önce bitirirsin" : "kaynaklarına göre eksik kalır") : "kaynak atanınca hesaplanır"}
            tone={ok == null ? "neutral" : ok ? "good" : "warn"}
          />
        </div>

        <Link
          href="/student/progress"
          className="inline-flex items-center gap-1.5 self-center rounded-lg bg-cyan-700 px-3.5 py-2.5 text-sm font-semibold text-white hover:bg-cyan-800"
          data-testid="progress-summary-link"
        >
          Gelişimim <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>

      {days.length > 0 ? (
        <div className="grid grid-cols-7 gap-1 border-t border-border px-4 py-2.5">
          {days.map((d) => (
            <div
              key={d.date}
              className={cn("rounded-md py-1 text-center", DAY_CLS[d.state])}
              title={d.missing.length > 0 ? `Yapılmayan: ${d.missing.map((m) => m.title).join(", ")}` : d.label}
            >
              <div className="text-[10px] font-bold uppercase leading-tight">{d.day}</div>
              <div className="text-[11px] font-semibold tabular-nums leading-tight">
                {d.total > 0 ? `${d.done}/${d.total}` : "—"}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function Tile({
  icon: Icon,
  label,
  value,
  note,
  tone,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  note: string;
  tone: "good" | "warn" | "neutral";
}) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-card/80 px-3 py-2">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground">
        <Icon className="size-3.5" aria-hidden />
        {label}
        <span
          className={cn(
            "ml-auto size-2 rounded-full",
            tone === "good" ? "bg-emerald-500" : tone === "warn" ? "bg-amber-500" : "bg-slate-300",
          )}
          aria-hidden
        />
      </div>
      <div className="text-xl font-extrabold tabular-nums text-foreground">{value}</div>
      <div className="text-[11px] text-muted-foreground">{note}</div>
    </div>
  );
}
