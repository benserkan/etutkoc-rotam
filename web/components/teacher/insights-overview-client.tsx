"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";

import { getInsightsOverview, insightsKeys } from "@/lib/api/insights";
import type { FleetInsightsResponse } from "@/lib/types/insights";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Props {
  initial: FleetInsightsResponse;
}

export function InsightsOverviewClient({ initial }: Props) {
  const q = useQuery<FleetInsightsResponse>({
    queryKey: insightsKeys.overview(),
    queryFn: () => getInsightsOverview(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;

  const fleetRate =
    data.fleet_acceptance_rate !== null
      ? Math.round(data.fleet_acceptance_rate * 100)
      : null;
  const avgMaturity = Math.round(data.avg_maturity * 100);

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground inline-flex items-center gap-2">
          <Sparkles className="size-3.5" aria-hidden />
          AI öneri motoru
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          Filo içgörüleri
        </h1>
        <p className="text-sm text-muted-foreground">
          Öneri motorunun ne öğrendiğini, kaç önerinin kabul edildiğini ve
          öğrenci başına olgunluğunu burada görürsün.
        </p>
      </header>

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi
          label="Toplam kabul"
          value={data.fleet_total_accepted}
          sub={
            fleetRate !== null
              ? `%${fleetRate} kabul oranı`
              : "Yetersiz veri"
          }
        />
        <Kpi
          label="Toplam red"
          value={data.fleet_total_rejected}
          sub={`${data.weekly_trend.length} haftalık iz`}
        />
        <Kpi
          label="Ortalama olgunluk"
          value={`%${avgMaturity}`}
          sub={`${data.students_with_data}/${data.students.length} öğrenci verili`}
        />
        <Kpi
          label="Son aktivite"
          value={
            data.last_activity_at
              ? data.last_activity_at.slice(0, 10)
              : "—"
          }
          sub={data.health_activity.label}
        />
      </section>

      <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <HealthCard title="Genel durum" badge={data.health_overall} />
        <HealthCard title="Etkileşim sıklığı" badge={data.health_activity} />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Haftalık trend</CardTitle>
          </CardHeader>
          <CardContent>
            <TrendBars buckets={data.weekly_trend} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Öğrenci olgunluğu</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {data.students.length === 0 ? (
              <p className="text-sm text-muted-foreground px-4 pb-4">
                Henüz öğrenci atanmamış.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {data.students.map((s) => (
                  <li key={s.student_id} className="px-4 py-2.5 text-sm">
                    <div className="flex items-center gap-3">
                      <Link
                        href={`/teacher/students/${s.student_id}#insights`}
                        className="flex-1 min-w-0 hover:underline"
                      >
                        <span className="font-medium truncate block">
                          {s.full_name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {s.weeks_observed} hafta gözlem · {s.maturity_text}
                          {" · "}
                          {s.acceptance_rate !== null
                            ? `kabul %${Math.round(
                                s.acceptance_rate * 100,
                              )}`
                            : "yetersiz veri"}
                        </span>
                      </Link>
                      <MaturityBar value={s.maturity_value} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <PatternsCard
          title="En çok kabul edilen"
          patterns={data.top_accepted}
          variant="accept"
        />
        <PatternsCard
          title="En çok reddedilen"
          patterns={data.top_rejected}
          variant="reject"
        />
      </section>
    </div>
  );
}

function Kpi({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4 space-y-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        {sub ? <p className="text-xs text-muted-foreground">{sub}</p> : null}
      </CardContent>
    </Card>
  );
}

function HealthCard({
  title,
  badge,
}: {
  title: string;
  badge: { key: string; label: string; color: string };
}) {
  return (
    <Card>
      <CardContent className="p-4 flex items-center gap-3">
        <span
          aria-hidden
          className="inline-block w-3 h-3 rounded-full"
          style={{ backgroundColor: badge.color }}
        />
        <div className="leading-tight">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            {title}
          </p>
          <p className="text-sm font-medium">{badge.label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function MaturityBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div
      className="w-20 h-2 rounded-full bg-muted overflow-hidden"
      title={`olgunluk %${pct}`}
    >
      <div
        className="h-full bg-foreground/70"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function TrendBars({
  buckets,
}: {
  buckets: FleetInsightsResponse["weekly_trend"];
}) {
  const max = Math.max(
    1,
    ...buckets.map((b) => Math.max(b.accepted, b.rejected)),
  );
  return (
    <div className="space-y-2">
      {buckets.map((b) => (
        <div key={b.start} className="text-xs">
          <div className="flex items-center justify-between mb-1">
            <span className="text-muted-foreground">{b.start.slice(5)}</span>
            <span className="tabular-nums text-muted-foreground">
              {b.accepted} kabul · {b.rejected} red
            </span>
          </div>
          <div className="flex gap-1 h-3">
            <div
              className="bg-emerald-500/70 rounded-sm"
              style={{ width: `${(b.accepted / max) * 100}%` }}
              aria-label={`${b.accepted} kabul`}
            />
            <div
              className="bg-rose-500/70 rounded-sm"
              style={{ width: `${(b.rejected / max) * 100}%` }}
              aria-label={`${b.rejected} red`}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function PatternsCard({
  title,
  patterns,
  variant,
}: {
  title: string;
  patterns: FleetInsightsResponse["top_accepted"];
  variant: "accept" | "reject";
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {patterns.length === 0 ? (
          <p className="text-sm text-muted-foreground px-4 pb-4">Veri yok.</p>
        ) : (
          <ul className="divide-y divide-border text-sm">
            {patterns.map((p) => (
              <li
                key={`${p.book_id}-${p.section_id}`}
                className="px-4 py-2.5 flex items-center gap-3"
              >
                <span className="flex-1 min-w-0">
                  <span className="font-medium truncate block">
                    {p.book_name} — {p.section_label}
                  </span>
                  <span className="text-xs text-muted-foreground truncate block">
                    {p.subject_name} · {p.students} öğrenci
                  </span>
                </span>
                <span
                  className={cn(
                    "tabular-nums text-sm font-semibold",
                    variant === "accept"
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-rose-600 dark:text-rose-400",
                  )}
                >
                  {p.count}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
