"use client";

import * as React from "react";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * "Kaç test?" seçim şeridi — satırın HEMEN ALTINDA açılır, çipe tıklamak görevi yazar.
 *
 * KOÇ (2026-09-19): satırlarda zaten ✓/⏳/⎯ sayıları var; ayrı bir "+3" ve
 * yukarıda ayrı bir adet seçici işlevsel değildi ("yukarı çık, 2 yap, aşağı in,
 * ata"). Yeni akış: satırdaki "+" → tam orada çipler (1-5 + başka) → tek tık.
 * Varsayılan (koçun bu dersteki alışkanlığı, P3) vurgulu gelir; Esc/×/dışarı
 * tıklama kapatır. Portal yok — satırın altına akar, düzeni bozmaz.
 */
export function AssignCountChooser({
  defaultCount,
  hint,
  remaining,
  unit = "test",
  pending = false,
  onPick,
  onClose,
  className,
}: {
  defaultCount: number;
  /** "bu derste genelde 3" — vurgulu çipin gerekçesi */
  hint?: string | null;
  /** kapasite (kalan); aşılırsa çipte uyarı tonu */
  remaining?: number | null;
  unit?: string;
  pending?: boolean;
  onPick: (count: number) => void;
  onClose: () => void;
  className?: string;
}) {
  const ref = React.useRef<HTMLDivElement>(null);
  const [custom, setCustom] = React.useState("");

  // Esc / dışarı tıklama kapatır (mousedown — menü öğeleri de mousedown kullanır)
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [onClose]);

  const chips = Array.from(new Set([1, 2, 3, 4, 5, defaultCount])).sort((a, b) => a - b);
  const over = (n: number) => remaining !== null && remaining !== undefined && n > remaining;

  function pickCustom() {
    const n = Math.round(Number(custom));
    if (Number.isFinite(n) && n >= 1 && n <= 60) onPick(n);
  }

  return (
    <div
      ref={ref}
      role="group"
      aria-label={`Kaç ${unit}`}
      data-testid="assign-count-chooser"
      className={cn(
        "mt-1 flex flex-wrap items-center gap-1 rounded-md border border-cyan-300 bg-cyan-50/70 px-2 py-1.5 text-[11px] dark:border-cyan-500/40 dark:bg-cyan-500/10",
        className,
      )}
    >
      <span className="mr-0.5 text-cyan-900 dark:text-cyan-100">Kaç {unit}?</span>
      {chips.map((n) => {
        const isDefault = n === defaultCount;
        return (
          <button
            key={n}
            type="button"
            disabled={pending}
            aria-pressed={isDefault}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => onPick(n)}
            title={
              over(n)
                ? `${n} ${unit} — kalan ${remaining}, kapasite aşılır (uyarı verilir)`
                : `${n} ${unit} ver`
            }
            className={cn(
              "h-7 min-w-7 rounded-md border px-1.5 text-[12px] font-semibold tabular-nums transition disabled:opacity-50",
              isDefault
                ? "border-cyan-600 bg-cyan-600 text-white hover:bg-cyan-700"
                : over(n)
                  ? "border-amber-300 bg-background text-amber-700 hover:bg-amber-50 dark:border-amber-500/40 dark:text-amber-300 dark:hover:bg-amber-500/10"
                  : "border-border bg-background text-foreground hover:bg-muted",
            )}
          >
            {n}
          </button>
        );
      })}
      <span className="inline-flex h-7 items-stretch overflow-hidden rounded-md border border-border bg-background">
        <input
          type="number"
          inputMode="numeric"
          min={1}
          max={60}
          value={custom}
          placeholder="başka"
          aria-label="Başka sayı"
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              pickCustom();
            }
          }}
          className="w-12 bg-transparent px-1.5 text-center text-[12px] tabular-nums text-foreground outline-none placeholder:text-muted-foreground [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        />
        <button
          type="button"
          disabled={pending || !custom}
          onClick={pickCustom}
          className="border-l border-border px-1.5 text-[11px] font-medium text-foreground hover:bg-muted disabled:opacity-40"
        >
          Ver
        </button>
      </span>
      {hint ? (
        <span className="ml-auto truncate text-[10px] text-cyan-900/80 dark:text-cyan-100/80" title={hint}>
          {hint}
        </span>
      ) : null}
      <button
        type="button"
        aria-label="Kapat"
        onClick={onClose}
        className="ml-0.5 rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <X className="size-3" aria-hidden />
      </button>
    </div>
  );
}
