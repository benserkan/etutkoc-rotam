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

import { cn } from "@/lib/utils";
import type {
  ActivityDauTrendPoint,
  ActivityStickinessPoint,
  ActivityWow,
} from "@/lib/types/admin";

/** Saat × gün ısı haritası — CSS grid (24 satır, 7 sütun). UTC. */
export function ActivityHeatmapGrid({
  matrix,
  dayLabels,
  maxValue,
}: {
  matrix: Record<string, Record<string, number>>;
  dayLabels: string[];
  maxValue: number;
}) {
  function cellClass(v: number): string {
    if (maxValue <= 0 || v === 0) return "bg-slate-50 text-slate-300";
    const intensity = (v * 100) / maxValue;
    if (intensity < 20) return "bg-indigo-100 text-indigo-700";
    if (intensity < 50) return "bg-indigo-300 text-indigo-900";
    if (intensity < 80) return "bg-indigo-500 text-white";
    return "bg-indigo-700 text-white font-semibold";
  }
  return (
    <div className="overflow-x-auto">
      <table className="text-[10px]">
        <thead>
          <tr>
            <th className="pr-2 text-left font-normal text-muted-foreground">Saat (UTC)</th>
            {dayLabels.map((d) => (
              <th key={d} className="px-1 text-center font-medium text-muted-foreground">{d}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 24 }, (_, h) => (
            <tr key={h}>
              <td className="pr-2 text-right font-mono text-muted-foreground">
                {String(h).padStart(2, "0")}
              </td>
              {Array.from({ length: 7 }, (_, d) => {
                const v = matrix[String(h)]?.[String(d)] ?? 0;
                return (
                  <td key={d} className="text-center">
                    <div
                      className={cn(
                        "flex h-5 w-8 items-center justify-center rounded",
                        cellClass(v),
                      )}
                      title={`${String(h).padStart(2, "0")}:00 UTC — ${v} giriş`}
                    >
                      {v > 0 ? v : ""}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Bu hafta vs geçen hafta — grouped bar (Recharts). */
export function WowBarChart({ wow, height = 180 }: { wow: ActivityWow; height?: number }) {
  const data = wow.day_labels.map((label, i) => ({
    label,
    this: wow.this_series[i] ?? 0,
    last: wow.last_series[i] ?? 0,
  }));
  return (
    <div style={{ width: "100%", height }} aria-label="Bu hafta vs geçen hafta">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={{ stroke: "hsl(var(--border))" }} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} width={26} />
          <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.4)" }} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="last" name="Geçen hafta" fill="#cbd5e1" radius={[3, 3, 0, 0]} maxBarSize={16} />
          <Bar dataKey="this" name="Bu hafta" fill="#6366f1" radius={[3, 3, 0, 0]} maxBarSize={16} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 14 günlük DAU trendi — bar (Recharts). */
export function DauTrendChart({
  series,
  height = 160,
}: {
  series: ActivityDauTrendPoint[];
  height?: number;
}) {
  const data = series.map((p) => ({ label: p.day.slice(5), dau: p.dau }));
  return (
    <div style={{ width: "100%", height }} aria-label="14 günlük günlük aktif kullanıcı">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={{ stroke: "hsl(var(--border))" }} tickLine={false} interval="preserveStartEnd" minTickGap={12} />
          <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} width={26} />
          <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.4)" }} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Bar dataKey="dau" name="Aktif" fill="#6366f1" radius={[3, 3, 0, 0]} maxBarSize={20} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 30 günlük yapışkanlık sparkline — CSS mini bar. */
export function StickinessSparkline({ series }: { series: ActivityStickinessPoint[] }) {
  const max = Math.max(...series.map((p) => p.ratio), 1);
  return (
    <div className="flex h-12 items-end gap-px">
      {series.map((p, i) => {
        const h = max > 0 ? Math.round((p.ratio * 100) / max) : 0;
        return (
          <div
            key={i}
            className="flex-1 rounded-sm bg-blue-400 hover:bg-blue-600"
            style={{ height: `${h}%`, minHeight: 1 }}
            title={`${p.day}: %${p.ratio} (${p.dau}/${p.mau})`}
          />
        );
      })}
    </div>
  );
}

/** Oturum süre bantları — yatay CSS bar. */
export function SessionBandsBar({
  bands,
}: {
  bands: { under_1: number; min_1_5: number; min_5_15: number; min_15_30: number; over_30: number };
}) {
  const meta: [keyof typeof bands, string, string][] = [
    ["under_1", "< 1 dk", "bg-rose-400"],
    ["min_1_5", "1-5 dk", "bg-amber-400"],
    ["min_5_15", "5-15 dk", "bg-cyan-400"],
    ["min_15_30", "15-30 dk", "bg-sky-400"],
    ["over_30", "> 30 dk", "bg-emerald-400"],
  ];
  const max = Math.max(...Object.values(bands), 1);
  return (
    <div className="space-y-1.5">
      {meta.map(([key, label, color]) => {
        const v = bands[key];
        const pct = max > 0 ? Math.round((v * 100) / max) : 0;
        return (
          <div key={key} className="flex items-center gap-2 text-xs">
            <div className="w-16 text-muted-foreground">{label}</div>
            <div className="relative h-5 flex-1 overflow-hidden rounded bg-slate-100">
              <div className={cn("absolute inset-y-0 left-0 rounded", color)} style={{ width: `${pct}%` }} />
            </div>
            <div className="w-10 text-right font-mono text-muted-foreground">{v}</div>
          </div>
        );
      })}
    </div>
  );
}
