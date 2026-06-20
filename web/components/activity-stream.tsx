"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  CalendarDays,
  Filter,
  GraduationCap,
  ListPlus,
  Mail,
  ShoppingCart,
  Sparkles,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { DemoHint } from "@/components/demos/demo-hint";
import type { DemoRole } from "@/lib/demos";
import type {
  ActivityStreamItem,
  ActivityStreamResponse,
} from "@/lib/types/institution";

interface Props {
  title: string;
  description: string;
  // Tek bir queryFn alır — admin veya institution endpoint'i
  queryKey: (days: number, type: string | null) => readonly unknown[];
  queryFn: (days: number, type: string | null, limit?: number) => Promise<ActivityStreamResponse>;
  initial?: ActivityStreamResponse;
  demoRole?: DemoRole;
}

const TYPES: Array<{ key: string | null; label: string; tone?: string }> = [
  { key: null, label: "Tümü" },
  { key: "commercial", label: "Ticari", tone: "text-emerald-700" },
  { key: "signup", label: "Yeni kayıt", tone: "text-sky-700" },
  { key: "invitation", label: "Davetler", tone: "text-violet-700" },
  { key: "change", label: "Plan değişimi", tone: "text-amber-700" },
];

const DAYS_OPTIONS = [
  { v: 1, label: "Son 24 saat" },
  { v: 7, label: "Son 7 gün" },
  { v: 30, label: "Son 30 gün" },
  { v: 90, label: "Son 90 gün" },
];

function fmt(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}

function timeAgo(iso: string): string {
  const d = new Date(iso).getTime();
  const now = Date.now();
  const s = Math.floor((now - d) / 1000);
  if (s < 60) return "az önce";
  if (s < 3600) return `${Math.floor(s / 60)} dk önce`;
  if (s < 86400) return `${Math.floor(s / 3600)} sa önce`;
  return `${Math.floor(s / 86400)} gün önce`;
}

function categoryIcon(it: ActivityStreamItem): React.ReactNode {
  if (it.type === "plan_upgrade") return <ShoppingCart className="size-4" aria-hidden />;
  if (it.category === "signup") return <Sparkles className="size-4" aria-hidden />;
  if (it.category === "invitation") return <Mail className="size-4" aria-hidden />;
  if (it.category === "commercial") return <ShoppingCart className="size-4" aria-hidden />;
  return <Activity className="size-4" aria-hidden />;
}

function itemTone(it: ActivityStreamItem): { wrap: string; badge: string } {
  if (it.type === "plan_upgrade") {
    return { wrap: "border-emerald-300 bg-emerald-50/40", badge: "bg-emerald-600 text-white" };
  }
  if (it.is_commercial) {
    return { wrap: "border-emerald-200 bg-emerald-50/30 dark:bg-emerald-500/10 dark:border-emerald-500/30", badge: "bg-emerald-100 text-emerald-800" };
  }
  if (it.category === "signup") {
    return { wrap: "border-sky-200", badge: "bg-sky-100 text-sky-800" };
  }
  if (it.category === "invitation") {
    return { wrap: "border-violet-200", badge: "bg-violet-100 text-violet-800" };
  }
  return { wrap: "border-border", badge: "bg-muted text-muted-foreground" };
}

export function ActivityStreamPage({
  title, description, queryKey, queryFn, initial, demoRole,
}: Props) {
  const [days, setDays] = React.useState(30);
  const [type, setType] = React.useState<string | null>(null);

  const q: UseQueryResult<ActivityStreamResponse> = useQuery({
    queryKey: queryKey(days, type),
    queryFn: () => queryFn(days, type),
    initialData: days === initial?.days && type === null ? initial : undefined,
    staleTime: 20_000,
  });
  const data = q.data;
  const items = data?.items ?? [];
  const counts = data?.counts ?? {};

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold">
          <Activity className="size-6 text-indigo-700" aria-hidden />
          {title}
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>
        {demoRole ? <DemoHint contextKey="activity-stream" role={demoRole} className="mt-2" /> : null}
      </header>

      {/* KPI kartları */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard
          icon={<ShoppingCart className="size-4 text-emerald-700" aria-hidden />}
          label="Paket satın alma"
          value={counts.purchases ?? 0}
          highlight
        />
        <KpiCard
          icon={<ListPlus className="size-4 text-emerald-700" aria-hidden />}
          label="Ticari (toplam)"
          value={counts.commercial ?? 0}
          highlight
        />
        <KpiCard
          icon={<Sparkles className="size-4 text-sky-700" aria-hidden />}
          label="Yeni kayıt"
          value={counts.signup ?? 0}
        />
        <KpiCard
          icon={<Mail className="size-4 text-violet-700" aria-hidden />}
          label="Davetler"
          value={counts.invitation ?? 0}
        />
        <KpiCard
          icon={<Activity className="size-4 text-foreground" aria-hidden />}
          label="Toplam olay"
          value={counts.total ?? 0}
        />
      </section>

      {/* Filtre çubuğu */}
      <Card className="px-4 py-3 flex flex-wrap items-center gap-3">
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
          <CalendarDays className="size-3.5" aria-hidden /> Tarih:
        </span>
        <div className="flex flex-wrap gap-1">
          {DAYS_OPTIONS.map((d) => (
            <button
              key={d.v}
              type="button"
              onClick={() => setDays(d.v)}
              className={cn(
                "rounded-full border px-2.5 py-1 text-xs transition",
                days === d.v
                  ? "border-foreground bg-foreground/5 font-medium"
                  : "border-border text-muted-foreground hover:bg-muted/40",
              )}
            >
              {d.label}
            </button>
          ))}
        </div>
        <span className="ml-3 inline-flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
          <Filter className="size-3.5" aria-hidden /> Tip:
        </span>
        <div className="flex flex-wrap gap-1">
          {TYPES.map((t) => (
            <button
              key={t.key ?? "all"}
              type="button"
              onClick={() => setType(t.key)}
              className={cn(
                "rounded-full border px-2.5 py-1 text-xs transition",
                type === t.key
                  ? "border-foreground bg-foreground/5 font-medium"
                  : "border-border text-muted-foreground hover:bg-muted/40",
                t.tone,
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {q.isLoading ? "yükleniyor…" : `${items.length} kayıt`}
        </span>
      </Card>

      {/* Feed */}
      <Card className="overflow-hidden">
        {items.length === 0 && !q.isLoading ? (
          <p className="p-8 text-center text-sm text-muted-foreground">
            Bu dönemde / bu filtreyle eşleşen aktivite yok.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((it) => {
              const tone = itemTone(it);
              const Wrapper: React.ElementType = it.detail_url ? Link : "div";
              const wrapperProps = it.detail_url ? { href: it.detail_url } : {};
              return (
                <li key={it.id}>
                  <Wrapper
                    {...wrapperProps}
                    className={cn(
                      "block px-4 py-3 transition hover:bg-muted/40 border-l-4",
                      tone.wrap,
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <span
                        className={cn(
                          "shrink-0 inline-flex items-center justify-center rounded-md size-7",
                          tone.badge,
                        )}
                      >
                        {categoryIcon(it)}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-baseline gap-x-2">
                          <span className={cn(
                            "text-sm font-medium",
                            it.type === "plan_upgrade" && "text-emerald-800",
                          )}>
                            {it.title}
                          </span>
                          {it.detail_url && (
                            <ArrowUpRight className="size-3 text-muted-foreground" aria-hidden />
                          )}
                          <span className="ml-auto text-[11px] text-muted-foreground tabular-nums">
                            {timeAgo(it.occurred_at)} · {fmt(it.occurred_at)}
                          </span>
                        </div>
                        {it.subtitle && (
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            {it.subtitle}
                          </p>
                        )}
                        {(it.institution_name || it.actor_email) && (
                          <p className="mt-1 text-[11px] text-muted-foreground flex flex-wrap gap-x-2">
                            {it.institution_name && (
                              <span className="inline-flex items-center gap-1">
                                <GraduationCap className="size-3" aria-hidden />
                                {it.institution_name}
                              </span>
                            )}
                            {it.actor_email && it.actor_email !== it.subtitle && (
                              <span className="inline-flex items-center gap-1">
                                <Users className="size-3" aria-hidden />
                                {it.actor_email}
                              </span>
                            )}
                          </p>
                        )}
                      </div>
                    </div>
                  </Wrapper>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}

function KpiCard({
  icon, label, value, highlight = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <Card className={cn(
      "p-3",
      highlight && "border-emerald-300 bg-emerald-50/30",
    )}>
      <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
        {icon} {label}
      </div>
      <div className={cn(
        "mt-1 text-3xl font-bold tabular-nums",
        highlight && "text-emerald-700",
      )}>
        {value}
      </div>
    </Card>
  );
}
