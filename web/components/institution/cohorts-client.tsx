"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Info,
  Minus,
  Printer,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  getInstitutionCohorts,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  CohortStatsItem,
  CohortTab,
  CohortsResponse,
  WeekOverWeekInfo,
} from "@/lib/types/institution";
import { CohortBarChart } from "@/components/institution/cohort-bar-chart";

interface Props {
  initial: CohortsResponse;
  tab: CohortTab;
}

/**
 * Kohort Karşılaştırma — Jinja `cohorts.html` ile birebir.
 *
 * 4 sekme + WoW kartları + Recharts bar + tablo.
 */
export function CohortsClient({ initial, tab }: Props) {
  const q = useQuery<CohortsResponse>({
    queryKey: institutionKeys.cohorts(tab),
    queryFn: () => getInstitutionCohorts(tab),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const { institution, active_tab, tabs, cohorts, wow } = data;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href="/institution"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Panel
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
            Kohort Karşılaştırma
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {institution.name} — öğrencileri farklı kategorilerde gruplayıp
            performansını kıyasla.
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/institution/cohorts/print" target="_blank">
            <Printer className="size-4" aria-hidden />
            Yazdır / PDF
          </Link>
        </Button>
      </header>

      <PrivacyNote />

      <WoWGrid wow={wow} />

      <TabBar tabs={tabs} active={active_tab} />

      {cohorts.length === 0 ? (
        <EmptyState tab={active_tab} />
      ) : (
        <>
          <Card>
            <CardContent className="p-4">
              <h3 className="text-sm font-medium mb-3">
                Tamamlama oranı (% son 7 gün)
              </h3>
              <CohortBarChart cohorts={cohorts} />
            </CardContent>
          </Card>

          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-muted-foreground text-xs">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium">Kohort</th>
                    <th className="text-right px-4 py-2 font-medium">
                      Öğrenci
                    </th>
                    <th className="text-right px-4 py-2 font-medium">Plan</th>
                    <th className="text-right px-4 py-2 font-medium">
                      Tamamlanan
                    </th>
                    <th className="text-right px-4 py-2 font-medium">Oran</th>
                    <th className="text-right px-4 py-2 font-medium">Risk</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {cohorts.map((c) => (
                    <CohortRow key={c.cohort_key} cohort={c} />
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function PrivacyNote() {
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50 text-sky-900 px-3 py-2.5 text-xs flex items-start gap-2 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200">
      <Info className="size-4 shrink-0 mt-0.5" aria-hidden />
      <div>
        <strong>Gizlilik:</strong> Bu sayfa sadece{" "}
        <strong>kohort agregaları</strong> gösterir — bireysel öğrenci adı veya
        programı YOKTUR.{" "}
        <strong>Tamamlama oranı:</strong> Bu hafta planlanmış görevlerin yüzde
        kaçı yapıldı.{" "}
        <strong>Risk yüzdesi:</strong> Bu sınıfta &ldquo;Dikkat / Risk /
        Kritik&rdquo; seviyede uyarı alan öğrencilerin oranı (giriş yapmamak,
        eksik tamamlama, üst üste boş günler gibi göstergelere göre
        hesaplanır).
      </div>
    </div>
  );
}

function WoWGrid({ wow }: { wow: WeekOverWeekInfo }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <Card>
        <CardContent className="p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Bu hafta
          </div>
          <div
            className={cn(
              "text-3xl font-semibold mt-1 tabular-nums",
              wow.this_week_rate == null
                ? "text-muted-foreground"
                : rateColorClass(wow.this_week_rate),
            )}
          >
            {wow.this_week_rate == null ? "—" : `%${wow.this_week_rate}`}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            son 7 gün, kurum geneli tamamlama
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Geçen hafta
          </div>
          <div className="text-3xl font-semibold mt-1 tabular-nums">
            {wow.last_week_rate == null ? "—" : `%${wow.last_week_rate}`}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            önceki 7 gün, kıyas için
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Değişim
          </div>
          <DeltaValue wow={wow} />
          <div className="text-[11px] text-muted-foreground mt-1">
            {directionLabel(wow.direction)}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function DeltaValue({ wow }: { wow: WeekOverWeekInfo }) {
  if (wow.delta_pct == null) {
    return (
      <div className="text-3xl font-semibold mt-1 text-muted-foreground">—</div>
    );
  }
  if (wow.direction === "up") {
    return (
      <div className="text-3xl font-semibold mt-1 text-emerald-700 inline-flex items-center gap-1 tabular-nums">
        <ArrowUpRight className="size-6" aria-hidden />+{wow.delta_pct}
      </div>
    );
  }
  if (wow.direction === "down") {
    return (
      <div className="text-3xl font-semibold mt-1 text-rose-700 inline-flex items-center gap-1 tabular-nums">
        <ArrowDownRight className="size-6" aria-hidden />
        {wow.delta_pct}
      </div>
    );
  }
  return (
    <div className="text-3xl font-semibold mt-1 text-muted-foreground inline-flex items-center gap-1 tabular-nums">
      <Minus className="size-6" aria-hidden />0
    </div>
  );
}

function directionLabel(d: WeekOverWeekInfo["direction"]): string {
  switch (d) {
    case "up":
      return "iyileşme yönünde 👍";
    case "down":
      return "düşüş — dikkat 👀";
    case "flat":
      return "stabil";
    default:
      return "veri yetersiz";
  }
}

function TabBar({
  tabs,
  active,
}: {
  tabs: CohortsResponse["tabs"];
  active: CohortTab;
}) {
  return (
    <div className="border-b border-border">
      <nav className="flex gap-6 text-sm" aria-label="Kohort sekmeleri">
        {tabs.map((t) => (
          <Link
            key={t.key}
            href={`/institution/cohorts?tab=${t.key}`}
            className={cn(
              "pb-2 border-b-2 transition-colors -mb-px",
              t.key === active
                ? "border-foreground text-foreground font-medium"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
            aria-current={t.key === active ? "page" : undefined}
          >
            {t.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}

function CohortRow({ cohort }: { cohort: CohortStatsItem }) {
  return (
    <tr>
      <td className="px-4 py-2 font-medium">{cohort.cohort_label}</td>
      <td className="px-4 py-2 text-right tabular-nums">
        {cohort.student_count}
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {cohort.weekly_planned}
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {cohort.weekly_completed}
      </td>
      <td
        className={cn(
          "px-4 py-2 text-right tabular-nums font-semibold",
          rateColorByColor(cohort.rate_color),
        )}
      >
        {cohort.weekly_rate_pct == null ? "—" : `%${cohort.weekly_rate_pct}`}
      </td>
      <td className="px-4 py-2 text-right">
        {cohort.at_risk_pct != null && cohort.at_risk_pct > 0 ? (
          <>
            <span className="text-rose-700 font-medium tabular-nums">
              %{cohort.at_risk_pct}
            </span>{" "}
            <span className="text-xs text-muted-foreground">
              ({cohort.at_risk_count})
            </span>
          </>
        ) : (
          <span className="text-emerald-700">✓ 0</span>
        )}
      </td>
    </tr>
  );
}

function EmptyState({ tab }: { tab: CohortTab }) {
  let msg = "Aktif öğrenci yok ya da kategori bilgisi eksik.";
  if (tab === "track") {
    msg =
      "Alan bilgisi sadece 11+ ve mezun öğrencilerde aranır. Şu an kurumda bu seviyede aktif öğrenci yok.";
  } else if (tab === "exam_target") {
    msg =
      "Hedef sınav bilgisi öğrencinin sınıfından türetilir. Aktif öğrenci yoksa bu görünüm boş kalır.";
  }
  return (
    <Card>
      <CardContent className="p-12 text-center">
        <BarChart3
          className="size-12 mx-auto text-muted-foreground mb-3"
          aria-hidden
        />
        <h2 className="text-lg font-semibold mb-1">Bu kategoride veri yok</h2>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">{msg}</p>
      </CardContent>
    </Card>
  );
}

function rateColorClass(pct: number): string {
  if (pct >= 70) return "text-emerald-700";
  if (pct >= 40) return "text-amber-700";
  return "text-rose-700";
}

function rateColorByColor(color: string): string {
  switch (color) {
    case "green":
      return "text-emerald-700";
    case "amber":
      return "text-amber-700";
    case "red":
      return "text-rose-700";
    default:
      return "text-muted-foreground";
  }
}
