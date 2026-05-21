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

import type { ParentTrendPoint } from "@/lib/types/parent";

/**
 * 30 günlük tamamlama trend chart — Recharts (Chart.js yerine).
 *
 * Jinja parite: student_detail.html `Chart` bar chart — aynı renkler
 * (slate planlanan + emerald tamamlanan), aynı eksen (0 base + auto-skip).
 * Fresh visual: shadcn theme renkleriyle (hsl(var(--border)) ızgara).
 */

interface Props {
  trend: ParentTrendPoint[];
  height?: number;
}

interface ChartDatum {
  label: string;
  date: string;
  planned: number;
  completed: number;
}

export function ParentTrendBarChart({ trend, height = 200 }: Props) {
  const data: ChartDatum[] = React.useMemo(
    () =>
      trend.map((t) => ({
        label: t.label,
        date: t.date,
        planned: t.planned,
        completed: t.completed,
      })),
    [trend],
  );

  return (
    <div style={{ width: "100%", height }} aria-label="30 gün tamamlama trendi">
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
            content={<TrendTooltip />}
            cursor={{ fill: "hsl(var(--muted) / 0.4)" }}
          />
          <Legend
            verticalAlign="bottom"
            iconType="square"
            wrapperStyle={{ fontSize: 11 }}
          />
          <Bar
            dataKey="planned"
            name="Planlanan"
            fill="#94a3b8"
            radius={[3, 3, 0, 0]}
            maxBarSize={18}
          />
          <Bar
            dataKey="completed"
            name="Tamamlanan"
            fill="#059669"
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

function TrendTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md min-w-[140px]">
      <div className="font-medium mb-1">{d.label}</div>
      <div className="flex justify-between gap-3">
        <span className="text-muted-foreground">Planlanan</span>
        <span className="tabular-nums">{d.planned}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span className="text-muted-foreground">Tamamlanan</span>
        <span className="tabular-nums font-semibold text-emerald-700">
          {d.completed}
        </span>
      </div>
    </div>
  );
}
