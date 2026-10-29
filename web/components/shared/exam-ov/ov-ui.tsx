"use client";

/**
 * Deneme analizi yeni tasarım (2026-10-20) — paylaşılan görsel parçalar.
 * Koç / öğrenci / veli deneme sayfalarının sekmeleri bu parçalarla kurulur.
 */
import * as React from "react";

import { cn } from "@/lib/utils";
import type { OvHeatRow, OvSubjectRow, OvTrend } from "@/lib/api/exam-overview";

export function fmtNum(v: number | null | undefined, opts: { plus?: boolean; digits?: number } = {}): string {
  if (v == null || Number.isNaN(v)) return "—";
  const d = opts.digits ?? 2;
  const s = Number(v.toFixed(d)).toLocaleString("tr-TR", { maximumFractionDigits: d });
  if (opts.plus && v > 0) return `+${s}`;
  return s.replace("-", "−");
}

export function pct(v: number | null | undefined): string {
  return v == null ? "—" : `%${Math.round(v * 100)}`;
}

/** Bölüm kartı: üst etiket + başlık + açıklama + sağ alan. */
export function OvSection({
  eyebrow,
  tone = "cyan",
  title,
  desc,
  right,
  children,
  className,
  dataSection,
}: {
  eyebrow: string;
  tone?: "cyan" | "rose" | "emerald" | "orange" | "violet";
  title: React.ReactNode;
  desc?: React.ReactNode;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  dataSection?: string;
}) {
  const eyebrowTone = {
    cyan: "text-cyan-800",
    rose: "text-rose-700",
    emerald: "text-emerald-800",
    orange: "text-orange-800",
    violet: "text-violet-800",
  }[tone];
  return (
    <section
      data-section={dataSection}
      className={cn("flex min-w-0 flex-col gap-4 rounded-2xl border border-border bg-card p-5 sm:p-6", className)}
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <div className={cn("text-xs font-bold tracking-wider", eyebrowTone)}>{eyebrow}</div>
          <h3 className="mt-1 text-lg font-extrabold leading-snug sm:text-xl">{title}</h3>
          {desc ? <div className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{desc}</div> : null}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

/** Oran (0..1) → dolgulu hücre sınıfı. Açık dolgu + koyu yazı her iki temada okunur. */
export function ratioClass(r: number | null | undefined): string {
  if (r == null) return "bg-muted text-muted-foreground";
  if (r >= 0.85) return "bg-teal-700 text-white";
  if (r >= 0.7) return "bg-teal-200 text-teal-950";
  if (r >= 0.5) return "bg-amber-200 text-amber-950";
  if (r >= 0.3) return "bg-orange-300 text-orange-950";
  return "bg-rose-300 text-rose-950";
}

export function RatioLegend({ className }: { className?: string }) {
  const items: [number, string][] = [
    [0.9, "%85+"],
    [0.75, "%70–85"],
    [0.6, "%50–70"],
    [0.4, "%30–50"],
    [0.1, "%30 altı"],
  ];
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5 text-[11px] font-semibold", className)}>
      {items.map(([r, l]) => (
        <span key={l} className={cn("rounded-md px-2 py-0.5", ratioClass(r))}>
          {l}
        </span>
      ))}
    </div>
  );
}

/** Net gidişatı: noktalar + normal bant + hedef çizgisi + kesikli tahmin. */
export function TrendChart({ trend, height = 240, className }: { trend: OvTrend; height?: number; className?: string }) {
  const pts = trend.points;
  const W = 900;
  const H = height;
  const padL = 44;
  const padR = trend.projection != null ? 70 : 24;
  const padT = 26;
  const padB = 34;
  const vals = [
    ...pts.map((p) => p.net),
    ...(trend.band_low != null ? [trend.band_low, trend.band_high ?? trend.band_low] : []),
    ...(trend.projection != null ? [trend.projection] : []),
    ...(trend.target != null ? [trend.target] : []),
  ];
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (hi - lo < 10) {
    const mid = (hi + lo) / 2;
    lo = mid - 5;
    hi = mid + 5;
  }
  const pad = (hi - lo) * 0.12;
  lo = Math.max(0, Math.floor((lo - pad) / 5) * 5);
  hi = Math.ceil((hi + pad) / 5) * 5;
  const n = pts.length + (trend.projection != null ? 1 : 0);
  const stepX = n > 1 ? (W - padL - padR) / (n - 1) : 0;
  const x = (i: number) => (n > 1 ? padL + i * stepX : (W - padL - padR) / 2 + padL);
  const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);
  const ticks = [0, 1, 2, 3].map((i) => lo + ((hi - lo) * i) / 3);
  const line = pts.map((p, i) => `${x(i)},${y(p.net)}`).join(" ");
  const lastI = pts.length - 1;
  const aria = `Net gidişatı: ${pts.map((p) => `${p.label} ${fmtNum(p.net)}`).join(", ")}${
    trend.projection != null ? `; sonraki deneme tahmini ${fmtNum(trend.projection, { digits: 0 })}` : ""
  }`;
  return (
    // Dar ekranda grafik okunmaz hale küçülmesin: en az 600px, kartın içinde yatay kayar.
    <div className="-mx-1 overflow-x-auto px-1">
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={aria} className={cn("block min-w-[600px]", className)}>
      {trend.band_low != null && trend.band_high != null ? (
        <>
          <rect
            x={padL}
            y={y(trend.band_high)}
            width={W - padL - padR}
            height={Math.max(2, y(trend.band_low) - y(trend.band_high))}
            className="fill-teal-500/15"
          />
          <text x={padL + 8} y={y(trend.band_high) + 15} className="fill-teal-800 text-[11px] font-semibold">
            normal aralık {fmtNum(trend.band_low)}–{fmtNum(trend.band_high)}
          </text>
        </>
      ) : null}
      {ticks.map((t) => (
        <g key={t}>
          <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} className="stroke-border" strokeWidth={1} />
          <text x={padL - 8} y={y(t) + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">
            {Math.round(t)}
          </text>
        </g>
      ))}
      {trend.target != null ? (
        <>
          <line x1={padL} x2={W - padR} y1={y(trend.target)} y2={y(trend.target)} className="stroke-violet-600" strokeDasharray="8 6" strokeWidth={2} />
          <text x={padL + 4} y={y(trend.target) - 6} className="fill-violet-700 text-[11px] font-semibold">
            hedef {fmtNum(trend.target)}
          </text>
        </>
      ) : null}
      <polyline points={line} fill="none" className="stroke-cyan-700" strokeWidth={3} strokeLinejoin="round" />
      {trend.projection != null && pts.length ? (
        <>
          <line
            x1={x(lastI)}
            y1={y(pts[lastI].net)}
            x2={x(lastI + 1)}
            y2={y(trend.projection)}
            className="stroke-cyan-700"
            strokeWidth={2}
            strokeDasharray="6 6"
          />
          <circle cx={x(lastI + 1)} cy={y(trend.projection)} r={6} className="fill-card stroke-cyan-700" strokeWidth={2} strokeDasharray="3 3" />
          <text x={x(lastI + 1)} y={y(trend.projection) - 12} textAnchor="middle" className="fill-cyan-800 text-[11px] font-semibold">
            ~{fmtNum(trend.projection, { digits: 0 })}
          </text>
          <text x={x(lastI + 1)} y={H - 10} textAnchor="middle" className="fill-muted-foreground text-[11px]">
            tahmin
          </text>
        </>
      ) : null}
      {pts.map((p, i) => {
        const isLast = i === lastI;
        const below = trend.band_low != null && p.net < trend.band_low;
        return (
          <g key={p.id}>
            <title>{`${p.title} · ${p.label}: ${fmtNum(p.net)} net (${p.correct}D ${p.wrong}Y ${p.blank}B)`}</title>
            <circle
              cx={x(i)}
              cy={y(p.net)}
              r={isLast ? 8 : 6}
              className={cn(
                isLast ? "fill-cyan-700" : "fill-card",
                below ? "stroke-orange-600" : "stroke-cyan-700",
              )}
              strokeWidth={3}
            />
            <text
              x={x(i)}
              y={y(p.net) - 13}
              textAnchor="middle"
              className={cn(
                "text-[12px] font-bold",
                below ? "fill-orange-700" : isLast ? "fill-cyan-800" : "fill-foreground",
              )}
            >
              {fmtNum(p.net)}
            </text>
            <text x={x(i)} y={H - 10} textAnchor="middle" className="fill-muted-foreground text-[11px]">
              {p.label}
            </text>
          </g>
        );
      })}
    </svg>
    </div>
  );
}

/** Ders × deneme: hücre = ders neti, renk = dersin soru sayısına oranı. */
export function SubjectMatrix({
  rows,
  labels,
  showReading = true,
}: {
  rows: OvSubjectRow[];
  labels: string[];
  showReading?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl" data-testid="subject-matrix">
      <table className="w-full min-w-[720px] border-separate border-spacing-[3px] text-sm">
        <thead>
          <tr className="text-xs text-muted-foreground">
            <th scope="col" className="px-2 py-1.5 text-left font-semibold">
              Ders (soru)
            </th>
            {labels.map((l, i) => (
              <th key={`${l}-${i}`} scope="col" className="px-1 font-semibold">
                {l}
              </th>
            ))}
            <th scope="col" className="px-2 font-semibold">
              İlk → son
            </th>
            {showReading ? (
              <th scope="col" className="px-2 text-left font-semibold">
                Okuma
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name}>
              <th scope="row" className="whitespace-nowrap px-2 text-left text-[13px] font-semibold">
                {r.name} <span className="font-normal text-muted-foreground">({r.questions})</span>
              </th>
              {r.cells.map((c, i) => (
                <td
                  key={i}
                  title={c ? `${c.correct}D ${c.wrong}Y ${c.blank}B · ${c.questions} soru` : "Bu denemede yok"}
                  className={cn("h-9 min-w-[56px] rounded-md text-center text-[13px] font-bold tabular-nums", ratioClass(c?.ratio))}
                >
                  {c ? fmtNum(c.net) : "—"}
                </td>
              ))}
              <td
                className={cn(
                  "px-2 text-center font-bold tabular-nums",
                  r.change == null
                    ? "text-muted-foreground"
                    : r.change > 0
                      ? "text-emerald-700"
                      : r.change < 0
                        ? "text-rose-700"
                        : "text-muted-foreground",
                )}
              >
                {r.change == null ? "—" : fmtNum(r.change, { plus: true })}
              </td>
              {showReading ? (
                <td className="min-w-[220px] px-2 text-[13px] leading-snug text-foreground">{r.reading}</td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Konu × deneme ısı haritası. */
export function TopicHeatTable({ rows, labels }: { rows: OvHeatRow[]; labels: string[] }) {
  return (
    <div className="overflow-x-auto rounded-xl" data-testid="topic-heat">
      <table className="w-full min-w-[680px] border-separate border-spacing-[3px] text-sm">
        <thead>
          <tr className="text-xs text-muted-foreground">
            <th scope="col" className="px-2 py-1.5 text-left font-semibold">
              Konu
            </th>
            {labels.map((l, i) => (
              <th key={`${l}-${i}`} scope="col" className="px-1 font-semibold">
                {l}
              </th>
            ))}
            <th scope="col" className="px-2 font-semibold">
              Toplam
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.topic_id}>
              <th scope="row" className="min-w-[200px] px-2 text-left text-[13px] font-semibold leading-snug">
                {r.topic_name} <span className="font-normal text-muted-foreground">· {r.subject_name}</span>
              </th>
              {r.cells.map((c, i) => (
                <td
                  key={i}
                  title={c ? `${c.correct} doğru / ${c.total} soru` : "Bu denemede sorulmadı"}
                  className={cn("h-9 min-w-[52px] rounded-md text-center text-[13px] font-bold tabular-nums", ratioClass(c ? c.accuracy : null))}
                >
                  {c ? `${c.correct}/${c.total}` : "—"}
                </td>
              ))}
              <td className="px-2 text-center text-[13px] font-semibold tabular-nums">{pct(r.accuracy)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Yığılmış yatay çubuk (yanlış / boş). */
export function SplitBar({
  parts,
  className,
}: {
  parts: { value: number; className: string; label?: string }[];
  className?: string;
}) {
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  return (
    <div className={cn("flex h-2.5 w-full overflow-hidden rounded-full bg-muted", className)}>
      {parts.map((p, i) =>
        p.value > 0 ? (
          <div key={i} className={p.className} style={{ width: `${(100 * p.value) / total}%` }} title={p.label} />
        ) : null,
      )}
    </div>
  );
}
