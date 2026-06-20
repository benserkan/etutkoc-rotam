"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, BarChart3 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { JargonTooltip } from "@/components/jargon-tooltip";
import { adminKeys, getAdminRevenueCohort } from "@/lib/api/admin";
import type { RevenueCohortResponse } from "@/lib/types/admin";
import { fieldClass } from "@/components/admin/feature-catalog-ui";
import { cohortCell, tl } from "@/components/admin/revenue-ui";

interface Props {
  initial: RevenueCohortResponse;
}

const MONTHS_BACK_OPTS = [6, 9, 12, 18, 24];
const HORIZON_OPTS = [3, 6, 9, 12, 18, 24];
const CHURN_DAY_OPTS = [30, 60, 90, 180, 365];

const LEGEND = [
  { tone: "emerald", label: "≥80%" },
  { tone: "lime", label: "60-79" },
  { tone: "amber", label: "40-59" },
  { tone: "orange", label: "20-39" },
  { tone: "rose", label: "<20%" },
];

export function AdminRevenueCohortClient({ initial }: Props) {
  const [monthsBack, setMonthsBack] = React.useState(initial.months_back);
  const [horizon, setHorizon] = React.useState(initial.horizon);
  const [churnDays, setChurnDays] = React.useState(initial.churn_days);

  const isInitial =
    monthsBack === initial.months_back &&
    horizon === initial.horizon &&
    churnDays === initial.churn_days;

  const q = useQuery<RevenueCohortResponse>({
    queryKey: adminKeys.revenueCohort(monthsBack, horizon, churnDays),
    queryFn: () => getAdminRevenueCohort(monthsBack, horizon, churnDays),
    initialData: isInitial ? initial : undefined,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;
  const { matrix, churn, ltv } = data;

  return (
    <div className="space-y-5">
      <header>
        <span className="text-sm text-muted-foreground">Ticari Pano</span>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <BarChart3 className="size-6 text-indigo-700" aria-hidden />
          Kohort &amp; Müşteri Yaşam Değeri
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Aylık kayıt grupları (kohort), N ay sonra kaçının ücretli planda kaldığı
          (tutunma), plan başına müşteri yaşam değeri tahmini.
        </p>
      </header>

      {/* Filtre */}
      <Card className="flex flex-wrap items-center gap-4 p-4 text-sm">
        <span className="font-medium">Filtre:</span>
        <label className="flex items-center gap-1.5">
          <span className="text-muted-foreground">Kohort sayısı:</span>
          <select value={monthsBack} onChange={(e) => setMonthsBack(Number(e.target.value))} className={cn(fieldClass, "w-auto")}>
            {MONTHS_BACK_OPTS.map((m) => (
              <option key={m} value={m}>{m} ay</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5">
          <span className="text-muted-foreground">İzleme süresi:</span>
          <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} className={cn(fieldClass, "w-auto")}>
            {HORIZON_OPTS.map((h) => (
              <option key={h} value={h}>{h} ay</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5">
          <span className="text-muted-foreground">Plan hareketi penceresi:</span>
          <select value={churnDays} onChange={(e) => setChurnDays(Number(e.target.value))} className={cn(fieldClass, "w-auto")}>
            {CHURN_DAY_OPTS.map((d) => (
              <option key={d} value={d}>{d} gün</option>
            ))}
          </select>
        </label>
      </Card>

      {/* Plan hareketleri */}
      <section>
        <h2 className="mb-2 text-base font-semibold">
          Son {churn.window_days} günde plan hareketleri
        </h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <ChurnKpi label="Yeni Kayıt" value={churn.signup_count} sub="yeni kurum" tone="emerald" />
          <ChurnKpi label="Deneme Bitti" value={churn.trial_expired_count} sub={`${churn.trial_converted_count} ücretliye geçti`} tone="blue" />
          <ChurnKpi
            label="Deneme Dönüşüm"
            value={churn.trial_conversion_pct != null ? `%${churn.trial_conversion_pct}` : "—"}
            sub="deneme → ücretli"
            tone="amber"
          />
          <ChurnKpi label="Yükseltme" value={`↑ ${churn.upgrade_count}`} sub="üst plana geçti" tone="indigo" />
          <ChurnKpi label="Alçaltma" value={`↓ ${churn.downgrade_count}`} sub={`${churn.cancel_count} ücretsize`} tone="rose" />
          <div
            className={cn(
              "rounded-lg border p-3",
              churn.net_movement >= 0
                ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200"
                : "border-rose-200 bg-rose-50 text-rose-900 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
            )}
          >
            <div className="text-[10px] uppercase tracking-wide opacity-80">Net Hareket</div>
            <div className="mt-1 inline-flex items-center gap-1 text-2xl font-semibold">
              {churn.net_movement >= 0 ? (
                <ArrowUpRight className="size-5" aria-hidden />
              ) : (
                <ArrowDownRight className="size-5" aria-hidden />
              )}
              {churn.net_movement > 0 ? "+" : ""}
              {churn.net_movement}
            </div>
            <div className="text-[11px] opacity-70">yükseltme − alçaltma</div>
          </div>
        </div>
      </section>

      {/* Cohort heatmap */}
      <section>
        <h2 className="mb-2 text-base font-semibold">
          Aylık Kayıt Kohortu — Tutunma Matrisi{" "}
          <span className="text-sm font-normal text-muted-foreground">
            ({matrix.total_signups} toplam kayıt, son {matrix.months_back} ay)
          </span>
        </h2>
        {matrix.cohorts.length === 0 ? (
          <Card className="p-10 text-center text-sm text-muted-foreground">
            Bu pencerede kayıt olan kurum yok.
          </Card>
        ) : (
          <>
            <Card className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead className="bg-muted/40">
                  <tr>
                    <th className="sticky left-0 z-10 border-r border-border bg-muted/40 px-3 py-2 text-left font-semibold">
                      Kayıt ayı
                    </th>
                    <th className="border-r border-border px-2 py-2 text-center font-semibold">Kurum</th>
                    {Array.from({ length: matrix.horizon_months }, (_, i) => i + 1).map((m) => (
                      <th key={m} className="min-w-[44px] px-2 py-2 text-center font-semibold text-muted-foreground">
                        {m}. ay
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {matrix.cohorts.map((c) => (
                    <tr key={c.cohort_key} className="hover:bg-muted/30">
                      <td className="sticky left-0 z-10 border-r border-border bg-card px-3 py-2 font-medium">
                        {c.cohort_label}
                      </td>
                      <td className="border-r border-border px-2 py-2 text-center font-mono text-muted-foreground">
                        {c.signup_count}
                      </td>
                      {c.retention.map((r) =>
                        r.future ? (
                          <td key={r.month} className="bg-muted/40 px-1.5 py-2 text-center text-[10px] text-muted-foreground/40">
                            ·
                          </td>
                        ) : (
                          <td
                            key={r.month}
                            className={cn("px-1.5 py-2 text-center font-mono font-semibold", cohortCell(r.color))}
                            title={`${r.count}/${c.signup_count} kurum hâlâ ücretli — %${r.pct}`}
                          >
                            <div>%{r.pct}</div>
                            <div className="text-[9px] font-normal opacity-70">{r.count}</div>
                          </td>
                        ),
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-muted-foreground">
              <span>Renk skalası:</span>
              {LEGEND.map((l) => (
                <span key={l.tone} className="inline-flex items-center gap-1">
                  <span className={cn("size-3 rounded", cohortCell(l.tone))} />
                  {l.label}
                </span>
              ))}
            </div>
          </>
        )}
      </section>

      {/* Müşteri Yaşam Değeri */}
      <section>
        <h2 className="mb-2 inline-flex items-center gap-1.5 text-base font-semibold">
          Plan Başına Müşteri Yaşam Değeri
          <JargonTooltip content="Müşteri Yaşam Değeri (yabancı kısaltması ile yaygın bilinir): bir kurumun ortalama kaç ay kalıp ne kadar ödediği. Aylık fiyat × ortalama yaş." />
        </h2>
        <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          <ChurnKpi label="Toplam Yaşam Değeri (tahmini)" value={tl(ltv.total_ltv_try)} sub="aktif ödeyenlerin kümülatifi" tone="emerald" mono />
          <ChurnKpi label="Ödeyen Kurum" value={String(ltv.paying_count)} sub="şu an ücretli planda" tone="indigo" />
          <ChurnKpi label="Kurum Başı Ort. Yaşam Değeri" value={tl(ltv.avg_ltv_per_paying)} sub="ödeyenlerin ortalaması" tone="sky" mono />
        </div>
        <Card className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="border-b border-border bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left">Plan</th>
                <th className="px-4 py-2 text-right">Aktif kurum</th>
                <th className="px-4 py-2 text-right">Aylık fiyat</th>
                <th className="px-4 py-2 text-right">Ort. yaş (ay)</th>
                <th className="px-4 py-2 text-right">Yaşam Değeri / kurum</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {ltv.plans.map((p) => (
                <tr key={p.plan} className={p.monthly_price_try === 0 ? "bg-muted/30" : ""}>
                  <td className="px-4 py-2">
                    <div className="font-medium">{p.label}</div>
                    <div className="font-mono text-[11px] text-muted-foreground">{p.plan}</div>
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-muted-foreground">{p.active_count}</td>
                  <td className={cn("px-4 py-2 text-right font-mono", p.monthly_price_try > 0 ? "" : "text-muted-foreground")}>
                    {p.monthly_price_try > 0 ? tl(p.monthly_price_try) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-muted-foreground">{p.avg_age_months}</td>
                  <td className={cn("px-4 py-2 text-right font-mono font-semibold", p.monthly_price_try > 0 ? "text-emerald-700" : "text-muted-foreground")}>
                    {p.monthly_price_try > 0 ? tl(p.estimated_ltv_try) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </section>
    </div>
  );
}

function ChurnKpi({
  label,
  value,
  sub,
  tone,
  mono,
}: {
  label: string;
  value: string | number;
  sub: string;
  tone: string;
  mono?: boolean;
}) {
  const cls: Record<string, string> = {
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
    blue: "bg-blue-50 border-blue-200 text-blue-900 dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-200",
    amber: "bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-900 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
    rose: "bg-rose-50 border-rose-200 text-rose-900 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
    sky: "bg-sky-50 border-sky-200 text-sky-900 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
  };
  return (
    <div className={cn("rounded-lg border p-3", cls[tone] ?? cls.indigo)}>
      <div className="text-[10px] uppercase tracking-wide opacity-80">{label}</div>
      <div className={cn("mt-1 text-2xl font-semibold", mono && "font-mono")}>{value}</div>
      <div className="text-[11px] opacity-70">{sub}</div>
    </div>
  );
}
