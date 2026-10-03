"use client";

import * as React from "react";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";
import type { PricingCatalog } from "@/lib/types/pricing";

/**
 * Paket arayüzünün ORTAK parçaları (2026-10-03) — /pricing (vitrin) ve
 * /teacher/plan (Paketim) aynı renk, tipografi ve kart dilini kullansın.
 * Renk dili: camgöbeği = seçim/ana eylem · yeşil = dahil olan · kırmızı = olmaz.
 */

export type Cycle = "monthly" | "academic_year";

export function tl(n: number): string {
  return `${Math.round(n).toLocaleString("tr-TR")} ₺`;
}

export function capLabel(max: number | null): string {
  return max == null ? "Sınırsız öğrenci" : `${max} öğrenciye kadar`;
}

/** Akademik yıl fiyatları katalogdan (sunucu TEK KAYNAK: indirimli aylık + toplam). */
export function annualOf(catalog: PricingCatalog | undefined, code: string, monthly: number) {
  const t = catalog?.solo.tiers.find((x) => x.code === code);
  const pct = catalog?.annual_discount_pct ?? 20;
  const months = catalog?.annual_paid_months ?? 10;
  const am = t?.annual_monthly ?? Math.round((monthly * (100 - pct)) / 100);
  return { monthly: am, total: t?.annual_total ?? am * months, months, pct };
}

export function CycleSwitch({
  cycle,
  onChange,
  discountPct,
}: {
  cycle: Cycle;
  onChange: (c: Cycle) => void;
  discountPct: number;
}) {
  const opt = (c: Cycle, label: React.ReactNode) => (
    <button
      type="button"
      role="radio"
      aria-checked={cycle === c}
      onClick={() => onChange(c)}
      className={cn(
        "rounded-full px-4 py-2 text-sm font-semibold transition",
        cycle === c ? "bg-cyan-700 text-white" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
  return (
    <div className="inline-flex rounded-full border border-border bg-muted/50 p-1" role="radiogroup" aria-label="Ödeme dönemi">
      {opt("monthly", "Aylık")}
      {opt("academic_year", <>Akademik yıl · %{discountPct} indirim</>)}
    </div>
  );
}

export function PlanOption({
  name,
  capacity,
  price,
  unit = "/ay",
  priceNote,
  credits,
  tag,
  selected,
  disabled = false,
  disabledReason,
  onSelect,
}: {
  name: string;
  capacity: string;
  price: string;
  unit?: string;
  priceNote?: string | null;
  credits?: number | null;
  tag?: string | null;
  selected: boolean;
  disabled?: boolean;
  disabledReason?: string | null;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      disabled={disabled}
      onClick={onSelect}
      className={cn(
        "relative flex w-full items-start gap-3 rounded-2xl border-2 bg-card p-4 text-left transition sm:p-5",
        selected ? "border-cyan-600 shadow-md" : "border-border hover:border-cyan-600/50",
        disabled && "cursor-not-allowed opacity-60 hover:border-border",
      )}
    >
      <span
        className={cn(
          "mt-1 flex size-5 shrink-0 items-center justify-center rounded-full border-2",
          selected ? "border-cyan-600 bg-cyan-600" : "border-muted-foreground/40",
        )}
        aria-hidden
      >
        {selected ? <Check className="size-3 text-white" /> : null}
      </span>
      <span className="min-w-0 flex-1">
        {tag ? (
          <span className="mb-1.5 inline-block rounded-full bg-cyan-700 px-2 py-0.5 text-[11px] font-semibold text-white">
            {tag}
          </span>
        ) : null}
        <span className="block font-display text-lg font-bold text-foreground">{name}</span>
        <span className="block text-sm text-muted-foreground">{capacity}</span>
        <span className="mt-2 block">
          <span className="text-2xl font-bold text-foreground">{price}</span>
          {unit ? <span className="text-sm text-muted-foreground"> {unit}</span> : null}
        </span>
        {priceNote ? <span className="block text-xs text-muted-foreground">{priceNote}</span> : null}
        {credits ? (
          <span className="mt-1 block text-sm text-muted-foreground">
            Ayda {credits.toLocaleString("tr-TR")} yapay zekâ kredisi
          </span>
        ) : null}
        {disabled && disabledReason ? (
          <span className="mt-2 block text-xs font-medium text-rose-700 dark:text-rose-400">{disabledReason}</span>
        ) : null}
      </span>
    </button>
  );
}
