"use client";

import * as React from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

import { cn } from "@/lib/utils";
import type { SurveyResultModel } from "@/lib/types/survey";

/**
 * Anket sonucu görünümü — koç paneli + öğrenci sayfası ORTAK.
 *
 * - dimensions/wheel: boyut sayısı ≥5 ise Recharts radar + her zaman bar listesi
 * - qualitative (SWOT): kadran kartları
 * - Sabit konumlandırma ibaresi (disclaimer) her raporda görünür.
 *
 * Kontrast: açık-zeminli ton kartlarında explicit koyu metin (purge-safe).
 */

// high_is_good=true → yüksek iyi (emerald) · false → yüksek riskli (rose)
function toneFor(level: string, highIsGood: boolean): "good" | "warn" | "bad" {
  if (level === "mid") return "warn";
  const strong = level === "high";
  if (highIsGood) return strong ? "good" : "bad";
  return strong ? "bad" : "good";
}

const BAR_TONE: Record<string, string> = {
  good: "bg-emerald-500",
  warn: "bg-amber-500",
  bad: "bg-rose-500",
};

const PILL_TONE: Record<string, string> = {
  good: "border-emerald-300 bg-emerald-50 text-emerald-900",
  warn: "border-amber-300 bg-amber-50 text-amber-900",
  bad: "border-rose-300 bg-rose-50 text-rose-900",
};

const QUADRANT_TONE: Record<string, { card: string; title: string }> = {
  guclu: { card: "border-emerald-300 bg-emerald-50", title: "text-emerald-900" },
  zayif: { card: "border-amber-300 bg-amber-50", title: "text-amber-900" },
  firsat: { card: "border-sky-300 bg-sky-50", title: "text-sky-900" },
  tehdit: { card: "border-rose-300 bg-rose-50", title: "text-rose-900" },
};

export function SurveyResultView({ result }: { result: SurveyResultModel }) {
  const dims = result.dimensions;
  const showRadar =
    (result.scoring_type === "dimensions" || result.scoring_type === "wheel") &&
    dims.length >= 5;

  const radarData = dims.map((d) => ({
    label: d.label,
    score: d.score_pct,
  }));

  const topSet = new Set(result.top_dimensions);

  return (
    <div className="space-y-4">
      {/* Radar — profil görünümü */}
      {showRadar ? (
        <div className="h-64 sm:h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} outerRadius="70%">
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: "currentColor" }}
              />
              <Radar
                dataKey="score"
                stroke="#117A86"
                fill="#117A86"
                fillOpacity={0.25}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      {/* Boyut listesi — bar + seviye + yorum */}
      {dims.length > 0 ? (
        <div className="space-y-2.5">
          {dims.map((d) => {
            const tone = toneFor(d.level, d.high_is_good);
            return (
              <div key={d.key} className="space-y-1">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-medium inline-flex items-center gap-1.5 min-w-0">
                    <span className="truncate">{d.label}</span>
                    {topSet.has(d.key) && result.scoring_type === "dimensions" ? (
                      <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded border border-cyan-300 bg-cyan-50 text-cyan-900">
                        öne çıkan
                      </span>
                    ) : null}
                  </span>
                  <span
                    className={cn(
                      "shrink-0 text-[11px] px-1.5 py-0.5 rounded border tabular-nums",
                      PILL_TONE[tone],
                    )}
                  >
                    %{Math.round(d.score_pct)} · {d.level_label}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={cn("h-full rounded-full", BAR_TONE[tone])}
                    style={{ width: `${Math.max(2, Math.min(100, d.score_pct))}%` }}
                  />
                </div>
                {d.description ? (
                  <p className="text-[11px] text-muted-foreground">{d.description}</p>
                ) : null}
                {d.comment ? (
                  <p
                    className={cn(
                      "text-xs rounded-md border px-2 py-1.5",
                      PILL_TONE[tone],
                    )}
                  >
                    {d.comment}
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {/* Nitel bloklar (SWOT kadranları) */}
      {result.qualitative.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {result.qualitative.map((b) => {
            const t = QUADRANT_TONE[b.key] ?? {
              card: "border-border bg-muted/30",
              title: "text-foreground",
            };
            return (
              <div key={b.key} className={cn("rounded-lg border p-3", t.card)}>
                <p className={cn("text-sm font-semibold", t.title)}>{b.label}</p>
                {b.description ? (
                  <p className="mt-0.5 text-[11px] text-slate-600">{b.description}</p>
                ) : null}
                <ul className="mt-2 space-y-2">
                  {b.entries.map((e, i) => (
                    <li key={i} className="text-xs">
                      <p className="text-slate-500">{e.question}</p>
                      <p className="mt-0.5 whitespace-pre-wrap text-slate-900">
                        {e.answer || <span className="italic text-slate-400">— boş bırakıldı</span>}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      ) : null}

      {/* Açık uç cevaplar (yaşam çarkı yansıtmaları vb.) */}
      {result.open_answers.length > 0 ? (
        <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Öğrencinin kendi cümleleri
          </p>
          {result.open_answers.map((e, i) => (
            <div key={i} className="text-xs">
              <p className="text-muted-foreground">{e.question}</p>
              <p className="mt-0.5 whitespace-pre-wrap">{e.answer}</p>
            </div>
          ))}
        </div>
      ) : null}

      {/* Yorum çerçevesi + atıf + sabit ibare */}
      {result.report_note ? (
        <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-3 text-xs text-cyan-900">
          <p className="font-semibold mb-0.5">Koçluk yorumu için çerçeve</p>
          <p className="leading-relaxed">{result.report_note}</p>
        </div>
      ) : null}
      <div className="text-[11px] text-muted-foreground space-y-1 border-t border-border pt-2">
        <p>{result.disclaimer}</p>
        {result.source_attribution ? <p>{result.source_attribution}</p> : null}
      </div>
    </div>
  );
}
