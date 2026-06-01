"use client";

import { Target, TrendingDown, TrendingUp } from "lucide-react";

import { cn } from "@/lib/utils";
import type { DowKey, ProjectionPanel } from "@/lib/types/student";
import { JargonTooltip } from "@/components/jargon-tooltip";

interface Props {
  projection: ProjectionPanel;
}

/**
 * Sınav projeksiyon paneli — DOW (haftagünleri) bazlı forward walk + gap.
 *
 * Gösterim sırası:
 *   - Üst rozet: sınava kalan gün + tampon hariç gerçekleşebilir gün
 *   - "Bu gidişle X test çözebilirsin / Hedefe Y test eksiksin"
 *   - Methodoloji + güven düzeyi (low/medium/high) küçük etiket
 *   - 7 hücreli DOW grid: measured=true ise renkli oran, false ise gri
 *
 * Yalnız gelecekteki veya bugünkü günler için anlamlı — geçmiş günlerde
 * gizlenir (parent kontrol eder).
 */
export function ProjectionCard({ projection: p }: Props) {
  const isPositive = p.gap >= 0;
  const gapAbs = Math.abs(p.gap);

  return (
    <section className="rounded-lg border border-border bg-card p-4 space-y-3">
      <header className="flex items-start gap-2">
        <Target className="size-4 text-muted-foreground mt-0.5" aria-hidden="true" />
        <div className="flex-1">
          <h2 className="text-sm font-semibold">Sınav projeksiyonu</h2>
          <p className="text-xs text-muted-foreground">
            {p.days_left !== null
              ? `Sınava ${p.days_left} gün · etkin ${p.effective_days} gün (tampon ${p.buffer_days})`
              : "Sınav tarihi henüz tanımlı değil"}
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
            p.confidence_level === "high"
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
              : p.confidence_level === "medium"
                ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
          )}
        >
          {p.confidence_level === "high"
            ? "Yüksek güven"
            : p.confidence_level === "medium"
              ? "Orta güven"
              : "Düşük güven"}
        </span>
      </header>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-muted-foreground">Bu gidişle çözülecek</p>
          <p className="font-display text-2xl font-bold tabular-nums">
            {p.projected_completable.toLocaleString("tr-TR")}
            <span className="ml-1 text-sm font-medium text-muted-foreground">test</span>
          </p>
          <p className="text-[11px] text-muted-foreground">
            Günde ortalama {p.rate_per_day.toFixed(1)} test
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">
            {isPositive ? "Hedefe fazlalık" : "Hedefe eksik"}
          </p>
          <div className="flex items-center gap-1.5">
            {isPositive ? (
              <TrendingUp className="size-5 text-emerald-600" aria-hidden="true" />
            ) : (
              <TrendingDown className="size-5 text-destructive" aria-hidden="true" />
            )}
            <span
              className={cn(
                "font-display text-2xl font-bold tabular-nums",
                isPositive ? "text-emerald-600" : "text-destructive",
              )}
            >
              {gapAbs.toLocaleString("tr-TR")}
            </span>
            <span className="text-sm font-medium text-muted-foreground">test</span>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Yetişmek için günde {p.required_rate.toFixed(1)} test gerekli
          </p>
        </div>
      </div>

      <div className="space-y-1.5">
        <p className="text-[11px] text-muted-foreground inline-flex items-center gap-1">
          <JargonTooltip
            term="Haftagünleri tutturma"
            content="Geçmiş haftalarda her gün için planlanmış görevin ne kadarını yaptın — gelecekteki tahmin bu örüntüden besleniyor."
          />
        </p>
        <DowGrid rates={p.dow_hit_rates} measured={p.dow_hit_measured} />
      </div>
    </section>
  );
}

const DOW_LABELS: Record<DowKey, string> = {
  monday: "Pzt",
  tuesday: "Sal",
  wednesday: "Çar",
  thursday: "Per",
  friday: "Cum",
  saturday: "Cmt",
  sunday: "Paz",
};

const DOW_ORDER: DowKey[] = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

function DowGrid({
  rates,
  measured,
}: {
  rates: Record<DowKey, number | null>;
  measured: Record<DowKey, boolean>;
}) {
  return (
    <ul className="grid grid-cols-7 gap-1">
      {DOW_ORDER.map((k) => {
        const m = measured[k];
        const r = rates[k];
        const pct = r !== null && r !== undefined ? Math.round(r * 100) : null;
        return (
          <li key={k} className="flex flex-col items-center gap-0.5">
            <span className="text-[10px] uppercase text-muted-foreground">
              {DOW_LABELS[k]}
            </span>
            <div
              className={cn(
                "w-full h-7 rounded-md grid place-items-center text-[10px] font-medium tabular-nums",
                m && pct !== null
                  ? pct >= 80
                    ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                    : pct >= 50
                      ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                      : "bg-destructive/15 text-destructive"
                  : "bg-muted text-muted-foreground",
              )}
              aria-label={
                m && pct !== null
                  ? `${DOW_LABELS[k]}: %${pct} tutturma`
                  : `${DOW_LABELS[k]}: veri yok`
              }
            >
              {m && pct !== null ? `%${pct}` : "—"}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
