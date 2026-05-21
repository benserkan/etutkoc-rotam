"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { UsageDailyPoint } from "@/lib/types/institution";

/**
 * 30 günlük kredi tüketim bar chart — Recharts.
 *
 * Jinja parite: `usage_dashboard.html:197-223` Chart.js bar — aynı x-tick
 * formatı (DD.MM), aynı y-axis (0 başlangıç), tek seri (kredi). Renk
 * şeması Next.js teması (indigo) — fresh approach.
 */

interface Props {
  series: UsageDailyPoint[];
  height?: number;
}

interface ChartDatum {
  iso: string;
  label: string;
  credits: number;
}

export function UsageDailyBarChart({ series, height = 200 }: Props) {
  const data: ChartDatum[] = React.useMemo(
    () =>
      series.map((p) => ({
        iso: p.day,
        label: formatDayShort(p.day),
        credits: p.credits,
      })),
    [series],
  );

  return (
    <div style={{ width: "100%", height }} aria-label="Günlük kredi tüketimi">
      <ResponsiveContainer>
        <BarChart
          data={data}
          margin={{ top: 8, right: 8, left: 0, bottom: 4 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsl(var(--border))"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickLine={false}
            interval="preserveStartEnd"
            minTickGap={16}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
            width={28}
          />
          <Tooltip
            content={<UsageTooltip />}
            cursor={{ fill: "hsl(var(--muted) / 0.4)" }}
          />
          <Bar
            dataKey="credits"
            fill="#4f46e5"
            radius={[3, 3, 0, 0]}
            maxBarSize={18}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface TooltipPayloadEntry {
  payload: ChartDatum;
}

function UsageTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="font-medium mb-0.5">{formatDayFull(d.iso)}</div>
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">Kredi:</span>
        <span className="font-semibold tabular-nums">{d.credits}</span>
      </div>
    </div>
  );
}

function formatDayShort(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}`;
}

function formatDayFull(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}
