"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { NotifDailyTrend } from "@/lib/types/admin";

/**
 * 7 günlük bildirim teslimat trendi — stacked bar (Recharts).
 * Seriler: Gönderildi / Başarısız / Kuyrukta / Engellendi.
 */

interface Props {
  series: NotifDailyTrend[];
  height?: number;
}

interface Datum {
  iso: string;
  label: string;
  sent: number;
  failed: number;
  queued: number;
  suppressed: number;
}

function dayShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(5);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function NotifTrendBarChart({ series, height = 220 }: Props) {
  const data: Datum[] = React.useMemo(
    () =>
      series.map((p) => ({
        iso: p.day,
        label: dayShort(p.day),
        sent: p.sent,
        failed: p.failed,
        queued: p.queued,
        suppressed: p.suppressed,
      })),
    [series],
  );

  return (
    <div style={{ width: "100%", height }} aria-label="7 günlük bildirim trendi">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
            width={28}
          />
          <Tooltip content={<TrendTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="sent" name="Gönderildi" stackId="a" fill="#059669" maxBarSize={28} />
          <Bar dataKey="failed" name="Başarısız" stackId="a" fill="#e11d48" maxBarSize={28} />
          <Bar dataKey="queued" name="Kuyrukta" stackId="a" fill="#d97706" maxBarSize={28} />
          <Bar dataKey="suppressed" name="Engellendi" stackId="a" fill="#64748b" radius={[3, 3, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function TrendTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: Datum }[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const total = d.sent + d.failed + d.queued + d.suppressed;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-medium">{d.label}</div>
      <div className="space-y-0.5">
        <div className="flex justify-between gap-3"><span className="text-emerald-600">Gönderildi</span><span className="tabular-nums">{d.sent}</span></div>
        <div className="flex justify-between gap-3"><span className="text-rose-600">Başarısız</span><span className="tabular-nums">{d.failed}</span></div>
        <div className="flex justify-between gap-3"><span className="text-amber-600">Kuyrukta</span><span className="tabular-nums">{d.queued}</span></div>
        <div className="flex justify-between gap-3"><span className="text-slate-500">Engellendi</span><span className="tabular-nums">{d.suppressed}</span></div>
        <div className="mt-0.5 flex justify-between gap-3 border-t border-border pt-0.5 font-medium"><span>Toplam</span><span className="tabular-nums">{total}</span></div>
      </div>
    </div>
  );
}
