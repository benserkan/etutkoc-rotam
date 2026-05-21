"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Bell, Circle, Radio } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminSecurityLiveFeed } from "@/lib/api/admin";
import type { LiveFeedItem, LiveFeedResponse } from "@/lib/types/admin";
import { fmtDateTime } from "@/components/admin/security-ui";

interface Props {
  initial: LiveFeedResponse;
}

const WINDOWS = [
  { value: 300, label: "Son 5 dk" },
  { value: 600, label: "Son 10 dk" },
  { value: 1800, label: "Son 30 dk" },
  { value: 3600, label: "Son 1 saat" },
];

const INTERVALS = [
  { value: 2000, label: "2 sn" },
  { value: 5000, label: "5 sn" },
  { value: 15000, label: "15 sn" },
  { value: 0, label: "Durdur" },
];

function severityMeta(sev: string): { dot: string; badge: string; Icon: typeof Circle } {
  if (sev === "critical") return { dot: "bg-rose-100 text-rose-700", badge: "bg-rose-50 text-rose-700", Icon: AlertTriangle };
  if (sev === "warn") return { dot: "bg-amber-100 text-amber-700", badge: "bg-amber-50 text-amber-700", Icon: AlertTriangle };
  return { dot: "bg-slate-100 text-slate-600", badge: "bg-slate-50 text-slate-600", Icon: Circle };
}

export function SecurityLiveClient({ initial }: Props) {
  const [sinceSeconds, setSinceSeconds] = React.useState(initial.since_seconds || 600);
  const [intervalMs, setIntervalMs] = React.useState(5000);

  const q = useQuery<LiveFeedResponse>({
    queryKey: adminKeys.securityLiveFeed(sinceSeconds),
    queryFn: () => getAdminSecurityLiveFeed(sinceSeconds),
    initialData: sinceSeconds === initial.since_seconds ? initial : undefined,
    refetchInterval: intervalMs > 0 ? intervalMs : false,
    staleTime: 0,
  });
  const items = q.data?.items ?? [];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/admin/security-monitor" className="text-sm text-muted-foreground hover:text-foreground">
            ← Güvenlik Kamarası
          </Link>
          <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <Radio className="size-6 text-rose-600" aria-hidden />
            Canlı Olay Akışı
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Sistemde şu an ne oluyor — denetim olayları (kim ne yaptı) ve alarmların karışık şeridi.
            Sistem kamerası gibi izle.
          </p>
        </div>
        <Link href="/admin/security-monitor/alarms" className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted">
          <Bell className="mr-1 inline size-4" aria-hidden /> Alarm Ayarları
        </Link>
      </header>

      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <span className={cn("inline-block size-2 rounded-full bg-rose-500", intervalMs > 0 && "animate-pulse")} />
          {intervalMs > 0 ? "canlı" : "duraklatıldı"}
        </span>
        <label className="inline-flex items-center gap-1">
          Aralık:
          <select value={sinceSeconds} onChange={(e) => setSinceSeconds(Number(e.target.value))} className="rounded border border-input bg-background px-2 py-1 text-xs">
            {WINDOWS.map((w) => <option key={w.value} value={w.value}>{w.label}</option>)}
          </select>
        </label>
        <label className="inline-flex items-center gap-1">
          Yenileme:
          <select value={intervalMs} onChange={(e) => setIntervalMs(Number(e.target.value))} className="rounded border border-input bg-background px-2 py-1 text-xs">
            {INTERVALS.map((i) => <option key={i.value} value={i.value}>{i.label}</option>)}
          </select>
        </label>
        {q.isFetching ? <span className="text-[11px]">güncelleniyor…</span> : null}
      </div>

      <Card className="min-h-[400px] overflow-hidden">
        {items.length === 0 ? (
          <p className="px-4 py-16 text-center text-sm text-muted-foreground">Bu pencerede olay yok. Etrafta sessizlik.</p>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((it, i) => (
              <LiveRow key={i} item={it} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function LiveRow({ item }: { item: LiveFeedItem }) {
  const m = severityMeta(item.severity);
  const Icon = item.type === "alarm" ? Bell : m.Icon;
  return (
    <li className="flex items-start gap-3 px-4 py-2 hover:bg-muted/40">
      <span className={cn("mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full", m.dot)}>
        <Icon className="size-3.5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm">{item.title}</span>
          <span className={cn("rounded px-1.5 py-0.5 text-[10px]", m.badge)}>{item.type}</span>
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {item.actor_id ? <>aktör #{item.actor_id} · </> : null}
          {item.ip ? <code className="font-mono">{item.ip}</code> : null}
          {item.details ? <> {item.actor_id || item.ip ? "· " : ""}{item.details}</> : null}
        </div>
      </div>
      <span className="shrink-0 whitespace-nowrap text-xs text-muted-foreground">{fmtDateTime(item.ts)}</span>
    </li>
  );
}
