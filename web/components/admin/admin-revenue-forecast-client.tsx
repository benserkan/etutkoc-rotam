"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CircleDollarSign,
  Sparkles,
  TrendingUp,
  User as UserIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminRevenueForecast } from "@/lib/api/admin";
import type {
  MrrProjection,
  RevenueForecastResponse,
} from "@/lib/types/admin";
import { fieldClass } from "@/components/admin/feature-catalog-ui";
import { tl } from "@/components/admin/revenue-ui";

interface Props {
  initial: RevenueForecastResponse;
}

const SAVE_RATES = [0.25, 0.5, 0.75, 1.0];

export function AdminRevenueForecastClient({ initial }: Props) {
  const [saveRate, setSaveRate] = React.useState(initial.save_rate);

  const q = useQuery<RevenueForecastResponse>({
    queryKey: adminKeys.revenueForecast(saveRate),
    queryFn: () => getAdminRevenueForecast(saveRate),
    initialData: saveRate === initial.save_rate ? initial : undefined,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;
  const projections = [data.proj_30, data.proj_60, data.proj_90];

  return (
    <div className="space-y-5">
      <header>
        <span className="text-sm text-muted-foreground">Ticari Pano</span>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <TrendingUp className="size-6 text-indigo-700" aria-hidden />
          Tahmin &amp; Senaryo
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          30/60/90 gün aylık gelir projeksiyonu, &quot;kaybedilebilecek
          gelir&quot; ve &quot;müdahale edersen ne kazanırsın&quot; senaryoları.
          Rakamlar geçmiş trendden uzatma; brüt aylık gelir (marj hariç).
        </p>
      </header>

      {/* Müdahale senaryosu seçimi */}
      <Card className="flex flex-wrap items-center gap-3 p-4 text-sm">
        <span className="font-medium">Müdahale senaryosu:</span>
        <span className="text-muted-foreground">Risk altındakilerin</span>
        <select
          value={saveRate}
          onChange={(e) => setSaveRate(Number(e.target.value))}
          className={cn(fieldClass, "w-auto")}
        >
          {SAVE_RATES.map((r) => (
            <option key={r} value={r}>
              %{Math.round(r * 100)}&apos;ini kurtarırsam
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-muted-foreground">
          Şu anki müdahale oranı: <strong>%{data.save_rate_pct}</strong>
        </span>
      </Card>

      {/* Üst KPI'lar */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi
          label="Bugünkü Aylık Gelir"
          value={tl(data.proj_90.current_mrr)}
          sub="aylık tekrarlayan (MRR)"
          tone="emerald"
        />
        <Kpi
          label="Risk Altında Aylık Gelir"
          value={tl(data.risk.total_at_risk_mrr)}
          sub={`${data.risk.critical_count} kritik + ${data.risk.risk_count} risk`}
          tone="rose"
        />
        <Kpi
          label="Deneme Dönüşüm"
          value={`%${Math.round(data.proj_90.trial_conversion_rate * 100)}`}
          sub="son 180 gün ortalaması"
          tone="amber"
        />
        <Kpi
          label="Aylık Ayrılma Oranı"
          value={`%${(data.proj_90.monthly_churn_rate * 100).toFixed(1)}`}
          sub="ödeyenlerin aylık kaybı (churn)"
          tone="slate"
        />
      </div>

      {/* Projeksiyon tablosu */}
      <section>
        <h2 className="mb-2 text-base font-semibold">
          Aylık Gelir Projeksiyonu — 30/60/90 Gün
        </h2>
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left">Süre</th>
                <th className="px-4 py-2 text-right">+ Deneme Dönüşümü</th>
                <th className="px-4 py-2 text-right">− Beklenen Ayrılma</th>
                <th className="px-4 py-2 text-right">− Risk Kaybı</th>
                <th className="px-4 py-2 text-right">Doğal Akış</th>
                <th className="px-4 py-2 text-right">Müdahale</th>
                <th className="px-4 py-2 text-right">Fark</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {projections.map((p: MrrProjection) => (
                <tr key={p.horizon_days} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium">{p.horizon_days} gün</td>
                  <td className="px-4 py-3 text-right font-mono text-emerald-700">
                    +{tl(p.expected_trial_conversions_mrr)}
                    <div className="text-[10px] text-muted-foreground">
                      {p.trial_ending_count} deneme bitiyor
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-rose-700">
                    −{tl(p.expected_churn_mrr)}
                    <div className="text-[10px] text-muted-foreground">trend</div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-rose-700">
                    −{tl(p.expected_at_risk_loss_mrr)}
                    <div className="text-[10px] text-muted-foreground">sağlık skoru</div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold">
                    {tl(p.projected_mrr_status_quo)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold text-indigo-700">
                    {tl(p.projected_mrr_with_intervention)}
                  </td>
                  <td
                    className={cn(
                      "px-4 py-3 text-right font-mono font-bold",
                      p.delta_mrr > 0 ? "text-emerald-700" : "text-muted-foreground",
                    )}
                  >
                    {p.delta_mrr > 0 ? "+" : ""}
                    {tl(p.delta_mrr)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </section>

      {/* Risk altındaki kurumlar */}
      <section>
        <h2 className="mb-2 text-base font-semibold">
          Risk Altındaki Ödeyen Kurumlar{" "}
          <span className="text-sm font-normal text-muted-foreground">
            ({data.risk.institutions.length} kurum, {tl(data.risk.total_at_risk_mrr)}/ay)
          </span>
        </h2>
        {data.risk.institutions.length === 0 ? (
          <Card className="p-10 text-center text-sm text-emerald-700">
            Şu an risk altında ödeyen kurum yok — temiz.
          </Card>
        ) : (
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">Kurum</th>
                  <th className="px-4 py-2 text-left">Plan</th>
                  <th className="px-4 py-2 text-center">Sağlık</th>
                  <th className="px-4 py-2 text-center">Seviye</th>
                  <th className="px-4 py-2 text-right">Aylık ₺</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.risk.institutions.slice(0, 30).map((inst) => {
                  const tone = inst.severity === "critical" ? "rose" : "amber";
                  return (
                    <tr key={`${inst.owner_type}-${inst.institution_id}`} className="hover:bg-muted/30">
                      <td className="px-4 py-2">
                        <Link href={inst.detail_url} className="font-medium hover:text-indigo-700">
                          {inst.name}
                        </Link>
                        {inst.owner_type === "user" ? (
                          <UserIcon className="ml-1 inline size-3 text-purple-600" aria-label="bağımsız öğretmen" />
                        ) : null}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{inst.plan}</td>
                      <td className="px-4 py-2 text-center font-mono">
                        {inst.health_score != null ? (
                          <span className={tone === "rose" ? "text-rose-700" : "text-amber-700"}>
                            {inst.health_score}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span
                          className={cn(
                            "rounded px-2 py-0.5 text-[10px] font-semibold uppercase",
                            tone === "rose" ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800",
                          )}
                        >
                          {inst.severity === "critical" ? "Kritik" : "Risk"}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right font-mono">{tl(inst.monthly_price_try)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {data.risk.institutions.length > 30 ? (
              <div className="border-t border-border bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
                … ve {data.risk.institutions.length - 30} kurum daha
              </div>
            ) : null}
          </Card>
        )}
      </section>

      {/* Senaryo karşılaştırma */}
      <section>
        <h2 className="mb-2 text-base font-semibold">Senaryo Karşılaştırma</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          Aynı 90 gün — iki yol. Soldaki: hiçbir şey yapma. Sağdaki: risk
          altındakilerin %{data.save_rate_pct}&apos;ini kurtar.
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Card className="bg-muted/30 p-5">
            <div className="mb-2 inline-flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
              <CircleDollarSign className="size-4" aria-hidden />
              Hiçbir Şey Yapma
            </div>
            <div className="space-y-2">
              {data.scenario.horizons.map((h) => (
                <div key={h.horizon_days} className="flex items-baseline justify-between border-b border-border pb-1">
                  <span className="text-xs text-muted-foreground">{h.horizon_days} gün sonra:</span>
                  <span className="font-mono text-base font-semibold">{tl(h.status_quo_mrr)}</span>
                </div>
              ))}
            </div>
          </Card>
          <Card className="border-2 border-indigo-300 bg-indigo-50/50 p-5">
            <div className="mb-2 inline-flex items-center gap-1.5 text-xs font-semibold uppercase text-indigo-700">
              <Sparkles className="size-4" aria-hidden />
              Müdahale Et (%{data.save_rate_pct} kurtarma)
            </div>
            <div className="space-y-2">
              {data.scenario.horizons.map((h) => (
                <div key={h.horizon_days} className="flex items-baseline justify-between border-b border-indigo-200 pb-1">
                  <span className="text-xs text-indigo-700">{h.horizon_days} gün sonra:</span>
                  <div className="text-right">
                    <span className="font-mono text-base font-semibold text-indigo-900">
                      {tl(h.intervention_mrr)}
                    </span>
                    <div className="text-[11px] text-emerald-700">+{tl(h.delta_mrr)} ek kazanç</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
        <Card className="mt-4 border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
          <span className="font-semibold">Eylem önerisi:</span> Aksiyon
          Merkezi&apos;nde risk altındaki kurumlara bugün ulaşırsan, 90 günde
          toplam{" "}
          <strong className="font-mono">
            {tl(data.scenario.horizons[data.scenario.horizons.length - 1]?.delta_mrr ?? 0)}
          </strong>{" "}
          ek aylık gelir koruyabilirsin.
          <Link
            href="/admin/revenue/action-center"
            className="ml-2 inline-flex items-center gap-0.5 underline"
          >
            Aksiyon Merkezi <ArrowRight className="size-3" aria-hidden />
          </Link>
        </Card>
      </section>
    </div>
  );
}

function Kpi({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub: string;
  tone: string;
}) {
  const cls: Record<string, string> = {
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900",
    rose: "bg-rose-50 border-rose-200 text-rose-900",
    amber: "bg-amber-50 border-amber-200 text-amber-900",
    slate: "bg-slate-50 border-slate-200 text-slate-900",
  };
  return (
    <div className={cn("rounded-lg border p-4", cls[tone] ?? cls.slate)}>
      <div className="text-[10px] uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 font-mono text-2xl font-semibold">{value}</div>
      <div className="text-[11px] opacity-70">{sub}</div>
    </div>
  );
}
