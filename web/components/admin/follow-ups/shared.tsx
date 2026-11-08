"use client";

import { cn } from "@/lib/utils";
import type { FollowUpVerdict, MetricPoint } from "@/lib/types/follow-ups";

/** Yerel takvim günü (YYYY-MM-DD) — UTC kayması olmasın. */
export function isoToday(plusDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + plusDays);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function fmtValue(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined) return "—";
  const s = Number.isInteger(v) ? String(v) : v.toFixed(1).replace(".", ",");
  return unit === "%" ? `%${s}` : s;
}

export function fmtDelta(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined) return "—";
  const s = (Math.abs(v) % 1 === 0 ? Math.abs(v).toFixed(0) : Math.abs(v).toFixed(1)).replace(".", ",");
  const sign = v > 0 ? "+" : v < 0 ? "−" : "±";
  return `${sign}${s}${unit === "%" ? " puan" : ""}`;
}

/** İyiye giden değişim yeşil, kötüye giden kırmızı (yön ölçüye göre). */
export function deltaTone(v: number | null | undefined, higherIsBetter: boolean): string {
  if (v === null || v === undefined || v === 0) return "text-slate-600";
  const good = higherIsBetter ? v > 0 : v < 0;
  return good ? "text-emerald-700" : "text-rose-700";
}

export const VERDICT_META: Record<FollowUpVerdict, { label: string; cls: string }> = {
  declined: { label: "Düşüş var", cls: "bg-rose-600 text-white" },
  improved: { label: "İyileşme var", cls: "bg-emerald-600 text-white" },
  stable: { label: "Belirgin değişim yok", cls: "bg-slate-600 text-white" },
  few_samples: { label: "Az örnek", cls: "bg-slate-200 text-slate-700" },
  single_point: { label: "Tek ölçüm", cls: "bg-slate-200 text-slate-700" },
  no_data: { label: "Veri birikiyor", cls: "bg-slate-200 text-slate-700" },
};

export function VerdictBadge({ verdict }: { verdict: FollowUpVerdict }) {
  const m = VERDICT_META[verdict];
  return (
    <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-semibold", m.cls)}>
      {m.label}
    </span>
  );
}

/** Basit eğilim çizgisi (SVG) — boşluklar (null) atlanır. */
export function Sparkline({
  points,
  width = 120,
  height = 32,
  className,
}: {
  points: MetricPoint[];
  width?: number;
  height?: number;
  className?: string;
}) {
  const vals = points.filter((p) => p.value !== null && p.value !== undefined) as {
    on: string;
    value: number;
  }[];
  if (vals.length < 2) {
    return (
      <span className="text-xs text-muted-foreground">
        {vals.length === 1 ? "tek ölçüm" : "veri yok"}
      </span>
    );
  }
  const min = Math.min(...vals.map((p) => p.value));
  const max = Math.max(...vals.map((p) => p.value));
  const span = max - min || 1;
  const step = width / (vals.length - 1);
  const xy = vals.map((p, i) => [i * step, height - 3 - ((p.value - min) / span) * (height - 6)]);
  const d = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const last = xy[xy.length - 1];
  return (
    <svg width={width} height={height} className={cn("overflow-visible text-cyan-700", className)} aria-hidden>
      <path d={d} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r={2.5} fill="currentColor" />
    </svg>
  );
}
