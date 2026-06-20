"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Brain,
  Lightbulb,
  ListChecks,
  Palette,
  Pin,
  Plus,
  Search,
  Telescope,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminFeatureCatalog } from "@/lib/api/admin";
import type {
  FeatureCardListItem,
  FeatureCatalogListResponse,
} from "@/lib/types/admin";
import {
  StatusBadge,
  diversityTone,
  fieldClass,
  scoreTone,
} from "@/components/admin/feature-catalog-ui";

interface Props {
  initial: FeatureCatalogListResponse;
}

export function AdminFeatureCatalogClient({ initial }: Props) {
  const [statusFilter, setStatusFilter] = React.useState<string>(
    initial.status_filter ?? "",
  );
  const [domainFilter, setDomainFilter] = React.useState<string>(
    initial.domain_filter ?? "",
  );
  const [tierFilter, setTierFilter] = React.useState<string>(
    initial.tier_filter ?? "",
  );
  const [q, setQ] = React.useState<string>(initial.q ?? "");
  const [qDebounced, setQDebounced] = React.useState<string>(initial.q ?? "");

  React.useEffect(() => {
    const t = setTimeout(() => setQDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  const query = useQuery<FeatureCatalogListResponse>({
    queryKey: adminKeys.featureCatalog(
      statusFilter || null,
      domainFilter || null,
      tierFilter || null,
      qDebounced || null,
    ),
    queryFn: () =>
      getAdminFeatureCatalog(
        statusFilter || null,
        domainFilter || null,
        tierFilter || null,
        qDebounced || null,
      ),
    initialData:
      !statusFilter && !domainFilter && !tierFilter && !qDebounced
        ? initial
        : undefined,
    staleTime: 15_000,
  });
  const data = query.data ?? initial;
  const divPct = Math.round(data.overall_diversity * 100);
  const divT = diversityTone(divPct);
  const hasFilter = !!(statusFilter || domainFilter || tierFilter || q);

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            href="/admin"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Panel
          </Link>
          <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <Lightbulb className="size-6 text-indigo-700" aria-hidden />
            Vitrin Kartları
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Anasayfada öne çıkan özellik kartlarının tek doğruluk kaynağı. Yeni
            özellik eklendikçe buraya kart açılır; sıralama otomatik hesaplanır.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/admin/feature-catalog/dashboard"
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted"
          >
            <Telescope className="size-4" aria-hidden />
            Yönetim Paneli
          </Link>
          <Link
            href="/admin/feature-catalog/experiments"
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted"
          >
            <ListChecks className="size-4" aria-hidden />
            A/B Deneyleri
          </Link>
          {data.discovery_pending > 0 ? (
            <Link
              href="/admin/feature-catalog/discovery-queue"
              className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100"
            >
              Onay Bekleyenler
              <span className="inline-flex h-5 min-w-[1.4em] items-center justify-center rounded-full bg-amber-600 px-1.5 text-[11px] font-bold text-white">
                {data.discovery_pending}
              </span>
            </Link>
          ) : null}
          <Link
            href="/admin/feature-catalog/new"
            className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            <Plus className="size-4" aria-hidden />
            Yeni Kart
          </Link>
        </div>
      </header>

      {/* Anasayfa sağlığı bandı */}
      <Card className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
          <HealthStat
            label="Anasayfada"
            value={`${data.landing_card_count}`}
            suffix="kart"
          />
          <div className="hidden h-10 w-px bg-border sm:block" />
          <HealthStat
            label="Çeşitlilik puanı"
            value={`%${divPct}`}
            tone={divT}
            help="Anasayfa kartları arasındaki ortalama tema farklılığı. %100 = hepsi farklı, %0 = hepsi aynı."
          />
          <div className="hidden h-10 w-px bg-border sm:block" />
          <HealthStat
            label="Öğrenme aktif"
            value={`${data.learning_count}`}
            suffix={`/ ${data.landing_card_count}`}
            help="Ziyaretçi davranışından beslenen öğrenen sıralama (LinUCB) için veri birikmiş kart sayısı."
          />
        </div>
      </Card>

      {/* Durum sayım kartları (filtre) */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {data.statuses.map((s) => {
          const active = statusFilter === s.value;
          return (
            <button
              key={s.value}
              type="button"
              onClick={() => setStatusFilter(active ? "" : s.value)}
              className={cn(
                "rounded-lg border bg-card p-3 text-left transition hover:border-foreground/30",
                active ? "border-indigo-400 ring-2 ring-indigo-200" : "border-border",
              )}
            >
              <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {s.label}
              </div>
              <div className="mt-0.5 text-2xl font-semibold">
                {data.counts[s.value] ?? 0}
              </div>
            </button>
          );
        })}
      </div>

      {/* Filtre çubuğu */}
      <Card className="flex flex-wrap items-center gap-2 p-3">
        <div className="relative min-w-[180px] flex-1">
          <Search className="absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Slug veya başlık ara…"
            className={cn(fieldClass, "pl-8")}
          />
        </div>
        <select
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          className={cn(fieldClass, "w-auto")}
        >
          <option value="">Tüm alanlar</option>
          {data.domains.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
          className={cn(fieldClass, "w-auto")}
        >
          <option value="">Tüm düzeyler</option>
          {data.tiers.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        {hasFilter ? (
          <button
            type="button"
            onClick={() => {
              setStatusFilter("");
              setDomainFilter("");
              setTierFilter("");
              setQ("");
            }}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            temizle ×
          </button>
        ) : null}
      </Card>

      {data.cards.length === 0 ? (
        <Card className="p-12 text-center text-sm text-muted-foreground">
          Filtreye uyan kart bulunamadı.{" "}
          <Link
            href="/admin/feature-catalog/new"
            className="text-indigo-600 hover:text-indigo-800"
          >
            Yeni kart oluştur →
          </Link>
        </Card>
      ) : (
        <>
          {/* Masaüstü tablo */}
          <Card className="hidden overflow-hidden lg:block">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-[11px] uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="w-1 px-0 py-2" />
                    <th className="px-3 py-2 text-left font-medium">Kart</th>
                    <th className="px-3 py-2 text-left font-medium">Alan · Düzey</th>
                    <th className="px-3 py-2 text-left font-medium">Durum</th>
                    <th className="px-3 py-2 text-center font-medium" title="1 düşük … 5 kritik">
                      Öncelik
                    </th>
                    <th className="px-3 py-2 text-center font-medium" title="Anasayfa sıralama skoru (0-100)">
                      Vitrin Skoru
                    </th>
                    <th className="px-3 py-2 text-left font-medium">Ziyaret</th>
                    <th className="px-3 py-2 text-right font-medium" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.cards.map((c) => (
                    <CardRow key={c.id} c={c} />
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Mobil kart-grid */}
          <div className="space-y-3 lg:hidden">
            {data.cards.map((c) => (
              <MobileCard key={c.id} c={c} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function HealthStat({
  label,
  value,
  suffix,
  tone,
  help,
}: {
  label: string;
  value: string;
  suffix?: string;
  tone?: string;
  help?: string;
}) {
  return (
    <div title={help}>
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 text-2xl font-semibold leading-none",
          tone === "emerald" && "text-emerald-700",
          tone === "amber" && "text-amber-700",
          tone === "rose" && "text-rose-700",
        )}
      >
        {value}
        {suffix ? (
          <span className="text-sm font-normal text-muted-foreground"> {suffix}</span>
        ) : null}
      </div>
    </div>
  );
}

function ScoreCell({ c }: { c: FeatureCardListItem }) {
  if (c.score == null) return <span className="text-xs text-muted-foreground">—</span>;
  const tone = scoreTone(c.score);
  return (
    <div className="flex flex-col items-center gap-1">
      <StatusBadge label={String(c.score)} tone={tone} className="font-semibold" />
      <div className="flex items-center gap-1 text-[10px]">
        {c.bandit_obs > 0 ? (
          <span
            className="inline-flex items-center gap-0.5 rounded border border-teal-200 bg-teal-50 px-1 text-teal-700 dark:bg-teal-500/10 dark:border-teal-500/30 dark:text-teal-200"
            title={`Akıllı sıralama (LinUCB) ${c.bandit_obs} gözlemden öğrendi.`}
          >
            <Brain className="size-3" aria-hidden />
            {c.bandit_obs}
          </span>
        ) : null}
        {c.is_landing && c.neighbor_sim != null && c.neighbor_sim > 0 ? (
          <span
            className="inline-flex items-center gap-0.5 rounded border border-stone-200 bg-stone-100 px-1 text-stone-600"
            title="Üst kartla tema farklılığı (yüksek = çeşitli)."
          >
            <Palette className="size-3" aria-hidden />%
            {Math.round((1 - c.neighbor_sim) * 100)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function VisitCell({ c }: { c: FeatureCardListItem }) {
  const totalClicks = c.demo_click + c.cta_click;
  if (!c.impression && !c.view && !totalClicks) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  return (
    <div
      className="space-y-0.5 text-xs"
      title={`Gösterim: ${c.impression} · Görüntüleme: ${c.view} · Demo: ${c.demo_click} · CTA: ${c.cta_click}`}
    >
      <div>
        <span className="font-semibold">{c.impression}</span>{" "}
        <span className="text-[10px] text-muted-foreground">gösterim</span>
      </div>
      {totalClicks > 0 ? (
        <div className="text-[11px] font-medium text-indigo-700">{totalClicks} tıklama</div>
      ) : null}
    </div>
  );
}

function CardRow({ c }: { c: FeatureCardListItem }) {
  return (
    <tr className="transition-colors hover:bg-muted/40">
      <td className="px-0 py-3 align-top">
        <div
          className="h-12 w-1 rounded-r"
          style={{ background: c.accent_color, opacity: c.is_landing ? 1 : 0.35 }}
          title={c.is_landing ? "Anasayfada görünüyor" : "Anasayfada görünmüyor"}
        />
      </td>
      <td className="max-w-md px-3 py-3 align-top">
        <div className="flex flex-wrap items-baseline gap-1.5">
          <Link
            href={`/admin/feature-catalog/${c.id}`}
            className="font-medium leading-snug hover:text-indigo-700"
          >
            {c.title}
          </Link>
          {c.manual_pin ? (
            <Pin className="size-3 text-amber-600" aria-label="Sabitlendi" />
          ) : null}
          {c.is_landing ? (
            <StatusBadge label="Anasayfada" tone="emerald" className="!text-[10px]" />
          ) : null}
        </div>
        <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">{c.slug}</div>
      </td>
      <td className="px-3 py-3 align-top">
        <div className="text-xs">{c.domain_label}</div>
        <div className="mt-0.5 text-[11px] text-muted-foreground">{c.tier_label}</div>
      </td>
      <td className="px-3 py-3 align-top">
        <StatusBadge label={c.status_label} tone={c.status_badge} />
        {c.manual_hide ? (
          <div className="mt-1 text-[10px] text-rose-600">gizli</div>
        ) : null}
      </td>
      <td className="px-3 py-3 text-center align-top">
        <span className="font-mono text-xs">
          {c.strategic_priority}
          <span className="text-muted-foreground">/5</span>
        </span>
      </td>
      <td className="px-3 py-3 text-center align-top">
        <ScoreCell c={c} />
      </td>
      <td className="px-3 py-3 align-top">
        <VisitCell c={c} />
      </td>
      <td className="px-3 py-3 text-right align-top">
        <Link
          href={`/admin/feature-catalog/${c.id}`}
          className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
        >
          Düzenle →
        </Link>
      </td>
    </tr>
  );
}

function MobileCard({ c }: { c: FeatureCardListItem }) {
  return (
    <Link href={`/admin/feature-catalog/${c.id}`} className="block">
      <Card className="p-3">
        <div className="flex items-start gap-2">
          <div
            className="mt-0.5 h-10 w-1 shrink-0 rounded-r"
            style={{ background: c.accent_color, opacity: c.is_landing ? 1 : 0.35 }}
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-1.5">
              <span className="font-medium">{c.title}</span>
              {c.manual_pin ? <Pin className="size-3 text-amber-600" aria-hidden /> : null}
            </div>
            <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">{c.slug}</div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge label={c.status_label} tone={c.status_badge} />
              {c.is_landing ? (
                <StatusBadge label="Anasayfada" tone="emerald" className="!text-[10px]" />
              ) : null}
              <span className="text-[11px] text-muted-foreground">
                {c.domain_label} · {c.tier_label}
              </span>
            </div>
            <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
              <span title="Öncelik">Öncelik {c.strategic_priority}/5</span>
              {c.score != null ? (
                <StatusBadge label={`Skor ${c.score}`} tone={scoreTone(c.score)} />
              ) : null}
              {c.impression > 0 ? <span>{c.impression} gösterim</span> : null}
            </div>
          </div>
        </div>
      </Card>
    </Link>
  );
}
