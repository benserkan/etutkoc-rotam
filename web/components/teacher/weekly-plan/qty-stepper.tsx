"use client";

import * as React from "react";
import { Minus, Plus } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Görev adedi seçici — "+3 test" butonundaki 3'ün değişebilir hâli.
 *
 * KOÇ (2026-09-19): "bazen 3 yerine 2 test verme durumu oluyor". Kural:
 * 3 tık bozulmaz — varsayılan koçun bu dersteki ALIŞKANLIĞINDAN gelir (P3
 * `task-quantity`), koç dokunmazsa akış aynen "konu → satırdaki +N". Değiştirmek
 * isteyen −/+ ile ya da kutuya yazarak ayarlar; satır butonları anında "+N"
 * olur. Kompakt: 7px yüksekliğinde tek satır, panel düzenini bozmaz.
 */
export function QtyStepper({
  value,
  onChange,
  hint,
  min = 1,
  max = 30,
  unit = "test",
  className,
}: {
  value: number;
  onChange: (v: number) => void;
  /** "bu derste genelde 3" gibi gerekçe — koç varsayılanın nereden geldiğini görür */
  hint?: string | null;
  min?: number;
  max?: number;
  unit?: string;
  className?: string;
}) {
  const clamp = (n: number) => Math.min(max, Math.max(min, Math.round(n)));
  return (
    <div className={cn("flex items-center gap-1.5 text-[11px]", className)}>
      <span className="text-muted-foreground">Kaç {unit}:</span>
      <div className="inline-flex h-7 items-stretch overflow-hidden rounded-md border border-border bg-background">
        <button
          type="button"
          aria-label="Bir azalt"
          className="px-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
          disabled={value <= min}
          onClick={() => onChange(clamp(value - 1))}
        >
          <Minus className="h-3 w-3" aria-hidden />
        </button>
        <input
          type="number"
          inputMode="numeric"
          min={min}
          max={max}
          value={value}
          aria-label={`Kaç ${unit}`}
          onChange={(e) => {
            const n = Number(e.target.value);
            if (Number.isFinite(n) && n > 0) onChange(clamp(n));
          }}
          className="w-9 border-x border-border bg-transparent text-center text-[12px] font-semibold tabular-nums text-foreground outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        />
        <button
          type="button"
          aria-label="Bir artır"
          className="px-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
          disabled={value >= max}
          onClick={() => onChange(clamp(value + 1))}
        >
          <Plus className="h-3 w-3" aria-hidden />
        </button>
      </div>
      {hint ? (
        <span className="truncate text-[10px] text-muted-foreground" title={hint}>
          {hint}
        </span>
      ) : null}
    </div>
  );
}
