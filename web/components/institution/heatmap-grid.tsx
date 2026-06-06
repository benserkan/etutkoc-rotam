"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { HeatmapCellData } from "@/lib/types/institution";

/**
 * Aktivite ısı haritası — günlere göre kareler, HAFTA gruplu + tarih eksenli.
 *
 * Okunabilirlik (kullanıcı geri bildirimi): tek sıra 11px kare + yalnız hover
 * tooltip "hangi gün" sorusunu çözmüyordu (mobilde hover yok). Çözüm: haftalar
 * arasına boşluk + her hafta başına tarih ekseni (DD.MM) + hafta-içi gün
 * kısaltması alt eksende. Renk: aktivite skoru (slate-100 → emerald-700).
 */
const LEVEL_COLORS: Record<number, string> = {
  0: "bg-slate-100",
  1: "bg-emerald-100",
  2: "bg-emerald-300",
  3: "bg-emerald-500",
  4: "bg-emerald-700",
};
const WD_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

function scoreToLevel(score: number): number {
  if (score <= 0) return 0;
  return Math.min(4, Math.ceil(score * 4));
}

function fmtDM(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function formatCellTitle(cell: HeatmapCellData): string {
  const d = new Date(cell.day);
  const wd = WD_SHORT[(d.getDay() + 6) % 7];
  return `${fmtDM(cell.day)} ${wd} — ${cell.login_count} giriş, ${cell.tasks_created} görev, ${cell.notes_created} not`;
}

/** Hücreleri haftalara böl (Pazartesi başlangıçlı). */
function intoWeeks(cells: HeatmapCellData[]): HeatmapCellData[][] {
  const weeks: HeatmapCellData[][] = [];
  let cur: HeatmapCellData[] = [];
  for (const c of cells) {
    const wd = (new Date(c.day).getDay() + 6) % 7; // 0=Pzt
    if (wd === 0 && cur.length > 0) {
      weeks.push(cur);
      cur = [];
    }
    cur.push(c);
  }
  if (cur.length > 0) weeks.push(cur);
  return weeks;
}

interface Props {
  cells: HeatmapCellData[];
  print?: boolean;
}

const CELL = 13;
const CELL_PRINT = 8;

/** Hafta başı tarih ekseni — heatmap strip'iyle aynı hizalama (header'da bir kez). */
export function HeatmapAxis({ cells, print = false }: Props) {
  const size = print ? CELL_PRINT : CELL;
  const weeks = intoWeeks(cells);
  return (
    <div className="flex gap-[6px]">
      {weeks.map((w, i) => (
        <div
          key={`ax-${i}`}
          className="text-[9px] leading-none text-muted-foreground"
          style={{ width: w.length * size + (w.length - 1) * 2 }}
        >
          {fmtDM(w[0].day)}
        </div>
      ))}
    </div>
  );
}

export function HeatmapGrid({ cells, print = false }: Props) {
  const size = print ? CELL_PRINT : CELL;
  const weeks = intoWeeks(cells);
  return (
    <div className="flex gap-[6px]" role="img" aria-label={`${cells.length} gün aktivite ısı haritası`}>
      {weeks.map((w, wi) => (
        <div key={`wk-${wi}`} className="flex gap-[2px]">
          {w.map((cell, idx) => {
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
      ))}
    </div>
  );
}

export function HeatmapLegend() {
  return (
    <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
      <span>Az aktif</span>
      <div className="size-[13px] rounded-[2px] bg-slate-100" />
      <div className="size-[13px] rounded-[2px] bg-emerald-100" />
      <div className="size-[13px] rounded-[2px] bg-emerald-300" />
      <div className="size-[13px] rounded-[2px] bg-emerald-500" />
      <div className="size-[13px] rounded-[2px] bg-emerald-700" />
      <span>Çok aktif</span>
      <span className="ml-2 hidden sm:inline">· Her kare = bir gün; haftalar boşlukla ayrılır, üstte hafta başı tarihi</span>
    </div>
  );
}
