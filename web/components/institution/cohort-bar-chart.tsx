"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { CohortStatsItem } from "@/lib/types/institution";

/**
 * Kohort tamamlama oranı bar chart — Recharts.
 *
 * Jinja parite: `cohorts.html:159-208` Chart.js bar — aynı renkler
 * (#059669/#d97706/#dc2626/#94a3b8), aynı eksen (%0-100), aynı tooltip
 * (öğrenci sayısı after-body).
 */

const RATE_COLORS: Record<string, string> = {
  green: "#059669",
  amber: "#d97706",
  red: "#dc2626",
  slate: "#94a3b8",
};

interface ChartDatum {
  label: string;
  rate: number;
  color: string;
  studentCount: number;
  planned: number;
  completed: number;
  atRiskPct: number | null;
}

interface Props {
  cohorts: CohortStatsItem[];
  height?: number;
}

export function CohortBarChart({ cohorts, height = 280 }: Props) {
  const data: ChartDatum[] = React.useMemo(
    () =>
      cohorts.map((c) => ({
        label: c.cohort_label,
        rate: c.weekly_rate_pct ?? 0,
        color: RATE_COLORS[c.rate_color] ?? RATE_COLORS.slate,
        studentCount: c.student_count,
        planned: c.weekly_planned,
        completed: c.weekly_completed,
        atRiskPct: c.at_risk_pct,
      })),
    [cohorts],
  );

  if (data.length === 0) return null;

  return (
    <div style={{ width: "100%", height }} aria-label="Kohort bar grafiği">
      <ResponsiveContainer>
        <BarChart
          data={data}
          margin={{ top: 12, right: 16, left: 0, bottom: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickLine={false}
            interval={0}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(v) => `%${v}`}
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip content={<CohortTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
          <Bar dataKey="rate" radius={[6, 6, 0, 0]} maxBarSize={56}>
            {data.map((d, idx) => (
              <Cell key={`cell-${idx}`} fill={d.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface TooltipPayloadEntry {
  payload: ChartDatum;
}

function CohortTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md min-w-[180px]">
      <div className="font-medium text-foreground mb-1">{d.label}</div>
      <div className="flex justify-between gap-3">
        <span className="text-muted-foreground">Tamamlama</span>
        <span className="font-semibold tabular-nums">%{d.rate}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span className="text-muted-foreground">Öğrenci</span>
        <span className="tabular-nums">{d.studentCount}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span className="text-muted-foreground">Plan / Tamam</span>
        <span className="tabular-nums">
          {d.completed} / {d.planned}
        </span>
      </div>
      {d.atRiskPct != null && d.atRiskPct > 0 && (
        <div className="flex justify-between gap-3 mt-1 pt-1 border-t border-border">
          <span className="text-muted-foreground">Risk altında</span>
          <span className="text-rose-700 font-medium tabular-nums">
            %{d.atRiskPct}
          </span>
        </div>
      )}
    </div>
  );
}
