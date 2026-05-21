"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { getTeacherUsage, settingsKeys } from "@/lib/api/settings";
import type { TeacherUsageResponse } from "@/lib/types/settings";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Props {
  initial: TeacherUsageResponse;
}

export function UsageClient({ initial }: Props) {
  const q = useQuery<TeacherUsageResponse>({
    queryKey: settingsKeys.usage(),
    queryFn: () => getTeacherUsage(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;

  if (!data.is_independent) {
    return (
      <div className="space-y-6">
        <Header />
        <Card>
          <CardContent className="p-6 text-sm space-y-2">
            <p>
              Bu öğretmen bir kuruma bağlı. Kredi havuzu kurum hesabında
              yönetilir; ayrıntılar için kurum yöneticinizle iletişime geçin.
            </p>
            <p className="text-muted-foreground">
              Kurum ID: {data.institution_id}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const acc = data.account!;
  return (
    <div className="space-y-6">
      <Header subtitle={`${acc.period} dönemi`} />

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi
          label="Plan"
          value={acc.plan_code}
          sub={`${acc.allocated_credits + acc.bonus_credits} kredi/ay`}
        />
        <Kpi
          label="Kullanılan"
          value={acc.used_credits}
          sub={`%${acc.usage_pct}`}
        />
        <Kpi
          label="Kalan"
          value={acc.remaining_credits}
          sub={
            acc.is_currently_blocked
              ? "Şu an blokda"
              : acc.bonus_credits > 0
                ? `+${acc.bonus_credits} bonus`
                : "Aktif"
          }
        />
        <Kpi
          label="Soğuma"
          value={
            acc.blocked_until
              ? acc.blocked_until.slice(0, 16).replace("T", " ")
              : "—"
          }
          sub={acc.hard_block_enabled ? "Sert blok aktif" : ""}
        />
      </section>

      <ProgressBar
        used={acc.used_credits}
        total={acc.allocated_credits + acc.bonus_credits}
      />

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Tür kırılımı</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {data.breakdown.length === 0 ? (
              <p className="text-sm text-muted-foreground px-4 pb-4">
                Bu ay henüz kullanım yok.
              </p>
            ) : (
              <ul className="divide-y divide-border text-sm">
                {data.breakdown.map((b) => (
                  <li
                    key={b.kind}
                    className="px-4 py-2 flex items-center justify-between"
                  >
                    <span>
                      {b.label}{" "}
                      <span className="text-xs text-muted-foreground">
                        ({b.cost_per_call} kredi/çağrı)
                      </span>
                    </span>
                    <span className="tabular-nums font-medium">{b.credits}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Son 30 gün</CardTitle>
          </CardHeader>
          <CardContent>
            <DailyBars series={data.daily_series} />
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Son etkinlikler</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {data.recent_events.length === 0 ? (
            <p className="text-sm text-muted-foreground px-4 pb-4">
              Henüz kayıt yok.
            </p>
          ) : (
            <ul className="divide-y divide-border text-sm">
              {data.recent_events.map((e) => (
                <li
                  key={e.id}
                  className="px-4 py-2 flex items-center justify-between"
                >
                  <div className="min-w-0">
                    <p className="font-medium truncate">{e.label}</p>
                    <p className="text-xs text-muted-foreground tabular-nums">
                      {e.occurred_at.slice(0, 16).replace("T", " ")}
                    </p>
                  </div>
                  <span className="tabular-nums text-xs text-muted-foreground">
                    {e.credits} kredi
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Plan tablosu</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ul className="divide-y divide-border text-sm">
            {data.plan_allocations.map((p) => (
              <li
                key={p.plan_code}
                className={cn(
                  "px-4 py-2 flex items-center justify-between",
                  p.plan_code === acc.plan_code ? "bg-muted/40 font-medium" : "",
                )}
              >
                <span>{p.plan_code}</span>
                <span className="tabular-nums">{p.monthly_credits} kredi</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function Header({ subtitle }: { subtitle?: string }) {
  return (
    <header className="space-y-1">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        Kullanım
      </p>
      <h1 className="text-2xl font-semibold tracking-tight font-display">
        Aylık kredi paneli
      </h1>
      {subtitle ? (
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      ) : null}
    </header>
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

function ProgressBar({ used, total }: { used: number; total: number }) {
  const denom = total > 0 ? total : 1;
  const pct = Math.min(100, Math.round((used / denom) * 100));
  const warn = pct >= 80;
  return (
    <div className="space-y-1">
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={cn(
            "h-full",
            warn ? "bg-amber-500" : "bg-foreground/70",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground tabular-nums">
        {used} / {total} kredi kullanıldı
      </p>
    </div>
  );
}

function DailyBars({
  series,
}: {
  series: TeacherUsageResponse["daily_series"];
}) {
  const max = Math.max(1, ...series.map((s) => s.credits));
  return (
    <div className="grid grid-cols-15 gap-1 items-end h-24">
      {series.slice(-30).map((s) => {
        const h = Math.max(4, Math.round((s.credits / max) * 96));
        return (
          <div
            key={s.date}
            className="bg-foreground/60 rounded-sm"
            style={{ height: `${h}px` }}
            title={`${s.date}: ${s.credits} kredi`}
            aria-label={`${s.date} ${s.credits} kredi`}
          />
        );
      })}
    </div>
  );
}
