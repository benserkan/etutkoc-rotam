"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { HeatmapCellData } from "@/lib/types/institution";

/**
 * GitHub contribution stili tek satır heatmap — günlere göre kareler.
 *
 * Jinja parite: `activity_heatmap.html:6-19` ile aynı renk paleti
 * (slate-100 / emerald-100/300/500/700) ve 11px hücreler.
 *
 * Skor → seviye:
 *   - 0           → boş (slate-100)
 *   - 0 < s ≤ 0.25 → lvl-1 (emerald-100)
 *   - 0.25 < s ≤ 0.5 → lvl-2 (emerald-300)
 *   - 0.5 < s ≤ 0.75 → lvl-3 (emerald-500)
 *   - 0.75 < s ≤ 1.0 → lvl-4 (emerald-700)
 *
 * Hücre hover'da büyür + browser tooltip (title attr) "{tarih} — N giriş…" gösterir.
 */
const LEVEL_COLORS: Record<number, string> = {
  0: "bg-slate-100",
  1: "bg-emerald-100",
  2: "bg-emerald-300",
  3: "bg-emerald-500",
  4: "bg-emerald-700",
};

function scoreToLevel(score: number): number {
  if (score <= 0) return 0;
  // Jinja: (score * 4) | round(0, 'ceil')
  const lvl = Math.min(4, Math.ceil(score * 4));
  return lvl;
}

function formatCellTitle(cell: HeatmapCellData): string {
  const d = new Date(cell.day);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy} — ${cell.login_count} giriş, ${cell.tasks_created} task, ${cell.notes_created} not`;
}

interface Props {
  cells: HeatmapCellData[];
  /** Yazdırma görünümünde hover/animasyon kapanır + 8px küçük hücre. */
  print?: boolean;
}

export function HeatmapGrid({ cells, print = false }: Props) {
  const size = print ? 8 : 11;
  return (
    <div
      className="grid gap-[2px]"
      style={{ gridTemplateColumns: `repeat(${cells.length}, ${size}px)` }}
      role="img"
      aria-label={`${cells.length} gün aktivite ısı haritası`}
    >
      {cells.map((cell, idx) => {
        const lvl = scoreToLevel(cell.activity_score);
        return (
          <div
            key={`${cell.day}-${idx}`}
            title={formatCellTitle(cell)}
            className={cn(
              "rounded-[2px]",
              LEVEL_COLORS[lvl],
              !print && "transition-transform hover:scale-150 hover:cursor-pointer",
            )}
            style={{ width: size, height: size }}
          />
        );
      })}
    </div>
  );
}

export function HeatmapLegend() {
  return (
    <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
      <span>Az aktif</span>
      <div className="size-[11px] rounded-[2px] bg-slate-100" />
      <div className="size-[11px] rounded-[2px] bg-emerald-100" />
      <div className="size-[11px] rounded-[2px] bg-emerald-300" />
      <div className="size-[11px] rounded-[2px] bg-emerald-500" />
      <div className="size-[11px] rounded-[2px] bg-emerald-700" />
      <span>Çok aktif</span>
    </div>
  );
}
