"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bot, Brain, Lightbulb, ListChecks, Plus, Telescope } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminFeatureCatalogDashboard } from "@/lib/api/admin";
import type { FeatureCatalogDashboardResponse } from "@/lib/types/admin";
import {
  anomalyBox,
  anomalyHint,
  anomalyTitle,
  diversityTone,
} from "@/components/admin/feature-catalog-ui";

interface Props {
  initial: FeatureCatalogDashboardResponse;
}

export function AdminFeatureCatalogDashboardClient({ initial }: Props) {
  const q = useQuery<FeatureCatalogDashboardResponse>({
    queryKey: adminKeys.featureCatalogDashboard(),
    queryFn: () => getAdminFeatureCatalogDashboard(),
    initialData: initial,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;
  const s = data.summary;
  const lh = data.landing_health;
  const w = data.last_7d;
  const divT = diversityTone(lh.diversity_pct);

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link href="/admin" className="text-sm text-muted-foreground hover:text-foreground">
            ← Panel
          </Link>
          <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <Telescope className="size-6 text-indigo-700" aria-hidden />
            Vitrin Yönetim Paneli
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Anasayfa kart kataloğunun tek noktadan görünümü; tüm sıralama, öğrenme
            ve deney mekanizmalarının özeti + dikkat gereken durumlar.
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Son güncelleme: {new Date(data.generated_at).toLocaleString("tr-TR")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/admin/feature-catalog"
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted"
          >
            <Lightbulb className="size-4" aria-hidden />
            Kart Listesi
          </Link>
          <Link
            href="/admin/feature-catalog/experiments"
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted"
          >
            <ListChecks className="size-4" aria-hidden />
            A/B Deneyleri
          </Link>
          <Link
            href="/admin/feature-catalog/new"
            className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            <Plus className="size-4" aria-hidden />
            Yeni Kart
          </Link>
        </div>
      </header>

      {/* Üst sayım kartları */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <SummaryCard label="Toplam kart" value={s.total} href="/admin/feature-catalog" />
        <SummaryCard label="Yayında" value={s.published} tone="emerald" href="/admin/feature-catalog?status_filter=published" />
        <SummaryCard label="Anasayfada" value={s.landing} />
        <SummaryCard label="Taslak" value={s.draft} tone="amber" href="/admin/feature-catalog?status_filter=draft" />
        <SummaryCard
          label="Onay bekliyor"
          value={s.queue_pending}
          tone={s.queue_pending > 0 ? "amber" : "slate"}
          href="/admin/feature-catalog/discovery-queue"
        />
        <SummaryCard
          label="Aktif deney"
          value={s.active_experiment}
          tone={s.active_experiment > 0 ? "emerald" : "slate"}
          href="/admin/feature-catalog/experiments"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Sol */}
        <div className="space-y-5 lg:col-span-2">
          <Card className="p-5">
            <h2 className="text-sm font-semibold">Anasayfa Sağlığı</h2>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              Şu anda anasayfada görünen kartların yapısı.
            </p>
            <div className="mt-3 grid grid-cols-3 gap-4">
              <Stat label="Kart sayısı" value={`${lh.landing_count}`} />
              <Stat label="Çeşitlilik" value={`%${lh.diversity_pct}`} tone={divT} />
              <Stat
                label="Öğrenme aktif"
                value={`${lh.learning_count}`}
                suffix={`/ ${lh.landing_count}`}
              />
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="text-sm font-semibold">Son {w.window_days} Gün</h2>
            <p className="mb-4 text-[11px] text-muted-foreground">
              Anasayfa trafiği, yeni keşfedilen adaylar ve öğrenme güncellemeleri.
            </p>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <MetricBox value={w.impressions} label="Gösterim" />
              <MetricBox value={w.views} label="Görüntüleme" />
              <MetricBox value={w.total_clicks} label="Tıklama" tone="indigo" />
              <MetricBox value={`%${w.ctr_pct}`} label="CTR" tone="emerald" />
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Bot className="size-4" aria-hidden />
                <span>
                  <strong className="text-foreground">{w.new_discoveries}</strong> yeni aday keşfedildi
                </span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Brain className="size-4" aria-hidden />
                <span>
                  <strong className="text-foreground">{w.bandit_updates}</strong> öğrenme güncellemesi
                </span>
              </div>
            </div>
          </Card>

          {data.experiment ? (
            <Card className="border-emerald-200 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
                    Aktif A/B Deneyi
                    <span className="rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-emerald-700">
                      Çalışıyor
                    </span>
                  </h2>
                  <div className="mt-1 font-medium">{data.experiment.name}</div>
                  <div className="font-mono text-[11px] text-muted-foreground">
                    {data.experiment.slug} · {data.experiment.started_days_ago} gün önce başladı
                  </div>
                </div>
                <Link
                  href={`/admin/feature-catalog/experiments/${data.experiment.id}`}
                  className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
                >
                  Detay →
                </Link>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {data.experiment.variants.map((v) => (
                  <div key={v.slug} className="rounded border border-border bg-muted/40 p-3">
                    <div className="mb-1 flex items-center gap-1.5">
                      <span className="text-xs font-medium">{v.label}</span>
                      {v.is_control ? (
                        <span className="rounded bg-muted px-1 text-[10px] text-muted-foreground">
                          kontrol
                        </span>
                      ) : null}
                    </div>
                    <div className="text-xl font-semibold">
                      %{(v.ctr * 100).toFixed(2)}
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      {v.total_clicks} / {v.impression} tıklama
                    </div>
                    {v.vs_control_significant ? (
                      <div className="mt-1 text-[10px] font-medium text-emerald-700">
                        ✓ anlamlı fark
                      </div>
                    ) : v.lift_pct != null ? (
                      <div
                        className={cn(
                          "mt-1 text-[10px]",
                          v.lift_pct > 0 ? "text-emerald-600" : v.lift_pct < 0 ? "text-rose-600" : "text-muted-foreground",
                        )}
                      >
                        {v.lift_pct >= 0 ? "+" : ""}
                        {Math.round(v.lift_pct)}% kontrolden
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </Card>
          ) : (
            <Card className="p-5 text-center text-sm text-muted-foreground">
              Şu anda çalışan A/B deney yok.{" "}
              <Link href="/admin/feature-catalog/experiments/new" className="text-indigo-600 hover:text-indigo-800">
                Yeni deney oluştur →
              </Link>
            </Card>
          )}
        </div>

        {/* Sağ */}
        <div className="space-y-5">
          <Card className="p-5">
            <h2 className="text-sm font-semibold">Dikkat Gerekli</h2>
            <p className="mb-3 text-[11px] text-muted-foreground">
              Otomatik tespit edilen durumlar.
            </p>
            {data.anomalies.length === 0 ? (
              <div className="py-2 text-sm text-emerald-700">
                ✓ Sistem sağlıklı, bilinen sorun yok.
              </div>
            ) : (
              <div className="space-y-2">
                {data.anomalies.map((a, i) => (
                  <div key={i} className={cn("rounded-lg border p-3", anomalyBox(a.severity))}>
                    <div className={cn("text-sm font-medium", anomalyTitle(a.severity))}>
                      {a.title}
                    </div>
                    <div className={cn("mt-1 text-[11px]", anomalyHint(a.severity))}>{a.hint}</div>
                    <Link
                      href={a.action_url}
                      className={cn(
                        "mt-1.5 inline-block text-xs underline underline-offset-2 hover:no-underline",
                        anomalyHint(a.severity),
                      )}
                    >
                      {a.action_label} →
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-5">
            <h2 className="mb-3 text-sm font-semibold">Son Hareketler</h2>
            {data.recent_audit.length === 0 ? (
              <div className="py-2 text-sm text-muted-foreground">Henüz kayıt yok.</div>
            ) : (
              <ol className="space-y-2.5">
                {data.recent_audit.map((r, i) => (
                  <li key={i} className="text-xs">
                    <div className="flex items-baseline gap-2">
                      <span className="whitespace-nowrap text-muted-foreground">{r.ago_label}</span>
                      <span>{r.action_label}</span>
                    </div>
                    {r.target_slug ? (
                      <div className="mt-0.5 pl-1 font-mono text-[10px] text-muted-foreground">
                        {r.target_slug}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  tone,
  href,
}: {
  label: string;
  value: number;
  tone?: string;
  href?: string;
}) {
  const inner = (
    <>
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "mt-0.5 text-2xl font-semibold",
          tone === "emerald" && "text-emerald-700",
          tone === "amber" && (value > 0 ? "text-amber-700" : "text-muted-foreground"),
          tone === "slate" && "text-muted-foreground",
        )}
      >
        {value}
      </div>
    </>
  );
  if (href) {
    return (
      <Link href={href} className="rounded-lg border border-border bg-card p-3 transition hover:border-foreground/30">
        {inner}
      </Link>
    );
  }
  return <div className="rounded-lg border border-border bg-card p-3">{inner}</div>;
}

function Stat({
  label,
  value,
  suffix,
  tone,
}: {
  label: string;
  value: string;
  suffix?: string;
  tone?: string;
}) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div
        className={cn(
          "mt-0.5 text-3xl font-semibold",
          tone === "emerald" && "text-emerald-700",
          tone === "amber" && "text-amber-700",
          tone === "rose" && "text-rose-700",
        )}
      >
        {value}
        {suffix ? <span className="text-base font-normal text-muted-foreground"> {suffix}</span> : null}
      </div>
    </div>
  );
}

function MetricBox({
  value,
  label,
  tone,
}: {
  value: number | string;
  label: string;
  tone?: string;
}) {
  return (
    <div
      className={cn(
        "rounded p-2 text-center",
        tone === "indigo" ? "bg-indigo-50" : tone === "emerald" ? "bg-emerald-50" : "bg-muted/50",
      )}
    >
      <div
        className={cn(
          "text-2xl font-semibold",
          tone === "indigo" && "text-indigo-700",
          tone === "emerald" && "text-emerald-700",
        )}
      >
        {value}
      </div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
    </div>
  );
}
