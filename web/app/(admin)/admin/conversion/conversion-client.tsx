"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingDown, Users, UserPlus, CreditCard, Info, FlaskConical } from "lucide-react";

import { cn } from "@/lib/utils";
import { conversionKeys, getAdminConversion } from "@/lib/api/conversion";
import type { ConversionResponse } from "@/lib/types/conversion";

const RANGES = [
  { days: 7, label: "7 gün" },
  { days: 30, label: "30 gün" },
  { days: 90, label: "90 gün" },
];

export function ConversionClient({ initial }: { initial: ConversionResponse }) {
  const [days, setDays] = React.useState(30);
  const q = useQuery({
    queryKey: conversionKeys.funnel(days),
    queryFn: () => getAdminConversion(days),
    initialData: days === 30 ? initial : undefined,
  });
  const data = q.data ?? initial;
  const f = data.funnel;

  const steps = [
    { key: "visitors", label: "Ziyaretçi", value: f.visitors, hint: "Anasayfayı açan tekil kişi", tone: "bg-sky-500" },
    { key: "engaged", label: "Kartı gördü", value: f.engaged, hint: "En az bir kartı ekranda gören (scroll)", tone: "bg-cyan-500" },
    { key: "clicked", label: "Kartı tıkladı", value: f.clicked, hint: "Karta veya “Demo İzle”ye tıklayan", tone: "bg-teal-500" },
    { key: "signup", label: "Üye oldu", value: f.signups_landing, hint: "Anasayfadan gelip kayıt olan", tone: "bg-emerald-500" },
    { key: "paid", label: "Ücretli oldu", value: f.paid_landing, hint: "Ücretli pakete geçen", tone: "bg-amber-500" },
  ];
  const maxV = Math.max(1, f.visitors);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      {/* Başlık */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex size-9 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
              <TrendingDown className="size-5" aria-hidden />
            </span>
            <div>
              <h1 className="text-lg font-semibold">Dönüşüm Hunisi</h1>
              <p className="mt-0.5 max-w-2xl text-sm text-muted-foreground">
                Anasayfayı ziyaret eden kişiden ücretli üyeye kadar yolculuğun her adımında
                kaç kişi kaldığını gösterir. “Hangi tanıtım anlatımı (A/B) daha çok üye getiriyor?”
                sorusunu yanıtlar.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {RANGES.map((r) => (
              <button
                key={r.days}
                onClick={() => setDays(r.days)}
                className={cn(
                  "rounded-full border px-3 py-1 text-sm transition-colors",
                  days === r.days
                    ? "border-foreground bg-foreground text-background"
                    : "border-border text-muted-foreground hover:bg-muted",
                )}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {/* Üst KPI */}
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Kpi icon={Users} label="Ziyaretçi" value={f.visitors} tone="text-sky-700" />
          <Kpi icon={UserPlus} label="Üye (anasayfadan)" value={f.signups_landing} tone="text-emerald-700" />
          <Kpi icon={CreditCard} label="Ücretli" value={f.paid_landing} tone="text-amber-700" />
          <Kpi
            icon={TrendingDown}
            label="Genel dönüşüm"
            value={`%${f.rate_visitor_paid}`}
            tone="text-foreground"
            sub="ziyaretçi → ücretli"
          />
        </div>
      </div>

      {/* Huni */}
      <div className="mt-4 rounded-xl border border-border bg-card p-5">
        <h2 className="mb-4 text-sm font-semibold">Adım adım huni</h2>
        <div className="space-y-3">
          {steps.map((s, i) => {
            const pctOfVisitors = maxV > 0 ? Math.round((s.value / maxV) * 100) : 0;
            const prev = i > 0 ? steps[i - 1].value : null;
            const stepRate =
              prev && prev > 0 ? Math.round((s.value / prev) * 1000) / 10 : null;
            return (
              <div key={s.key}>
                {i > 0 ? (
                  <p className="mb-1 ml-1 text-xs text-muted-foreground">
                    <TrendingDown className="mr-1 inline size-3" aria-hidden />
                    bir önceki adımdan <strong className="text-foreground">%{stepRate ?? 0}</strong> geçti
                  </p>
                ) : null}
                <div className="flex items-center gap-3">
                  <div className="w-32 shrink-0">
                    <p className="text-sm font-medium">{s.label}</p>
                    <p className="text-[11px] text-muted-foreground">{s.hint}</p>
                  </div>
                  <div className="relative h-9 flex-1 overflow-hidden rounded-md bg-muted">
                    <div
                      className={cn("flex h-full items-center rounded-md px-3 transition-all", s.tone)}
                      style={{ width: `${Math.max(pctOfVisitors, 6)}%` }}
                    >
                      <span className="text-sm font-semibold text-white drop-shadow">{s.value}</span>
                    </div>
                  </div>
                  <div className="w-12 shrink-0 text-right text-xs text-muted-foreground">
                    %{pctOfVisitors}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <p className="mt-4 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          Not: Anasayfa izi olmayan <strong className="text-foreground">{f.signups_direct}</strong> doğrudan
          üyelik (davet/organik) bu hunide sayılmaz. Toplam üye:{" "}
          <strong className="text-foreground">{f.signups_total}</strong> · toplam ücretli:{" "}
          <strong className="text-foreground">{f.paid_total}</strong>.
        </p>
      </div>

      {/* A/B varyant kırılımı */}
      <div className="mt-4 rounded-xl border border-border bg-card p-5">
        <div className="mb-3 flex items-center gap-2">
          <FlaskConical className="size-4 text-violet-600" aria-hidden />
          <h2 className="text-sm font-semibold">A/B varyant dönüşümü</h2>
          {data.has_experiment && data.experiment_name ? (
            <span className="rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-xs text-violet-700">
              Aktif deney: {data.experiment_name}
            </span>
          ) : null}
        </div>
        {data.variants.length === 0 ? (
          <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            Bu dönemde A/B varyant verisi yok. Vitrin → Deneyler’den bir deney başlatınca, hangi
            anlatımın daha çok üye getirdiği burada görünür.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3">Varyant</th>
                  <th className="py-2 pr-3 text-right">Ziyaretçi</th>
                  <th className="py-2 pr-3 text-right">Üye</th>
                  <th className="py-2 pr-3 text-right">Dönüşüm</th>
                  <th className="py-2 pr-3 text-right">Ücretli</th>
                  <th className="py-2 text-right">Ücretli %</th>
                </tr>
              </thead>
              <tbody>
                {[...data.variants]
                  .sort((a, b) => b.conversion_pct - a.conversion_pct)
                  .map((v, idx) => (
                    <tr key={v.slug} className="border-b border-border/60">
                      <td className="py-2 pr-3 font-medium">
                        {v.slug}
                        {idx === 0 && v.signups > 0 ? (
                          <span className="ml-2 rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
                            en iyi
                          </span>
                        ) : null}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{v.sessions}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{v.signups}</td>
                      <td className="py-2 pr-3 text-right font-semibold tabular-nums">%{v.conversion_pct}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{v.paid}</td>
                      <td className="py-2 text-right tabular-nums">%{v.paid_pct}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Mini sözlük (jargon yasağı) */}
      <div className="mt-4 rounded-xl border border-border bg-muted/30 p-4">
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
          <Info className="size-4" aria-hidden /> Terimler
        </div>
        <dl className="grid gap-x-6 gap-y-1.5 text-xs text-muted-foreground sm:grid-cols-2">
          <Term t="Ziyaretçi" d="Anasayfayı açan tekil anonim kişi (90 günlük çerez ile sayılır; IP saklanmaz)." />
          <Term t="Kartı gördü" d="En az bir tanıtım kartı ekranına %50 girince otomatik sayılır (scroll ile; tıklama gerekmez)." />
          <Term t="Kartı tıkladı" d="Bir karta tıklayıp kayıt sayfasına giden veya “Demo İzle”ye tıklayan ziyaretçi (gerçek ilgi sinyali)." />
          <Term t="Üye oldu" d="Anasayfadan gelip ücretsiz denemeye kayıt olan kişi (çerez ile kayda bağlanır)." />
          <Term t="Ücretli" d="Üye olduktan sonra ücretli pakete geçen kişi." />
          <Term t="A/B varyant" d="Anasayfanın farklı kart düzeni/sıralaması. Ziyaretçi açılışta bir düzene atanır; tıklamadan, hangi düzeni göreni daha çok üye yaptığı ölçülür (Vitrin → Deneyler’de bir deney çalışıyorsa)." />
          <Term t="Dönüşüm %" d="Bir adımdan bir sonrakine geçenlerin oranı." />
          <Term t="Doğrudan üyelik" d="Anasayfa izi olmadan (davet/organik) gelen kayıt; bu hunide sayılmaz." />
        </dl>
      </div>
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone,
  sub,
}: {
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  label: string;
  value: number | string;
  tone: string;
  sub?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="size-3.5" aria-hidden /> {label}
      </div>
      <p className={cn("mt-0.5 text-2xl font-bold tabular-nums", tone)}>{value}</p>
      {sub ? <p className="text-[11px] text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

function Term({ t, d }: { t: string; d: string }) {
  return (
    <div>
      <dt className="inline font-medium text-foreground">{t}:</dt>{" "}
      <dd className="inline">{d}</dd>
    </div>
  );
}
