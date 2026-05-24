"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Check, Lock, ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";
import { getPricingCatalog, pricingKeys } from "@/lib/api/pricing";
import type { PricingCard, PricingCatalog } from "@/lib/types/pricing";

function fmt(n: number): string {
  return n.toLocaleString("tr-TR");
}

type CardsVariant = "landing" | "solo" | "institution";

function selectCards(catalog: PricingCatalog, variant: CardsVariant): PricingCard[] {
  const cards = catalog.cards;
  if (variant === "solo") return cards.filter((c) => c.audience === "solo");
  if (variant === "institution") return cards.filter((c) => c.audience === "institution");
  // landing: özet üçlü — Ücretsiz + öne çıkan Solo + Kurum
  const free = cards.find((c) => c.key === "free");
  const featured = cards.find((c) => c.audience === "solo" && c.highlight)
    ?? cards.find((c) => c.audience === "solo");
  const inst = cards.find((c) => c.audience === "institution");
  return [free, featured, inst].filter(Boolean) as PricingCard[];
}

/**
 * Paylaşılan üyelik kartları — TEK KAYNAK (/api/v2/pricing).
 * Hem anasayfa (variant="landing", özet üçlü) hem /pricing sekmeleri
 * (variant="solo" → 4 kart / "institution") bunu kullanır (tutarlılık).
 */
export function PricingCards({
  initial,
  variant = "landing",
}: {
  initial?: PricingCatalog;
  variant?: CardsVariant;
}) {
  const q = useQuery<PricingCatalog>({
    queryKey: pricingKeys.catalog(),
    queryFn: getPricingCatalog,
    initialData: initial,
    staleTime: 60_000,
  });
  const [yearly, setYearly] = React.useState(false);
  const catalog = q.data;

  if (!catalog) {
    return (
      <div className="grid items-start gap-6 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-96 animate-pulse rounded-2xl border border-slate-200 bg-white" />
        ))}
      </div>
    );
  }

  const months = catalog.annual_paid_months;
  const cards = selectCards(catalog, variant);
  const gridCols =
    cards.length >= 4 ? "md:grid-cols-2 lg:grid-cols-4"
      : cards.length === 1 ? "max-w-md mx-auto"
        : "md:grid-cols-3";

  return (
    <div className="space-y-7">
      {/* Aylık / Yıllık toggle */}
      <div className="flex flex-col items-center gap-2">
        <div className="inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50/60 p-1">
          <button
            type="button"
            onClick={() => setYearly(false)}
            className={cn("rounded-full px-5 py-2 text-sm font-bold transition", !yearly ? "bg-white text-cyan-800 shadow-sm" : "text-muted-foreground")}
          >
            Aylık
          </button>
          <button
            type="button"
            onClick={() => setYearly(true)}
            className={cn("inline-flex items-center gap-1.5 rounded-full px-5 py-2 text-sm font-bold transition", yearly ? "bg-white text-cyan-800 shadow-sm" : "text-muted-foreground")}
          >
            Akademik Yıl
            <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-700">2 ay bedava</span>
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          {yearly ? `${months} ay öde · 12 ay kullan` : "Aylık ödeme · istediğin zaman iptal"}
        </p>
      </div>

      <div className={cn("grid items-stretch gap-6", gridCols)}>
        {cards.map((card) => (
          <PlanCard key={card.key} card={card} yearly={yearly} months={months} />
        ))}
      </div>
    </div>
  );
}

function PlanCard({ card, yearly, months }: { card: PricingCard; yearly: boolean; months: number }) {
  const featured = card.tone === "featured" || card.highlight;
  const dark = card.tone === "dark";
  const onColor = featured || dark;   // koyu/renkli zemin → açık metin
  const isFree = card.monthly === 0;
  const monthly = yearly ? Math.round((card.monthly * months) / 12) : card.monthly;

  // Kurum kartı fiyat göstermez — "Kurumunuza özel teklif".
  // Solo paketleri kapaklı (sabit) fiyatlı → "X ₺/ay" (eski "'den" değil).
  let priceLabel = "Ücretsiz";
  let priceUnit = "";
  if (card.price_hidden) {
    priceLabel = card.price_caption || "Size özel teklif";
  } else if (!isFree) {
    priceLabel = `${fmt(monthly)} ₺`;
    priceUnit = "/ay";
  }
  const priceNote = yearly && !isFree && !card.price_hidden
    ? "yıllık peşin · 2 ay bedava"
    : card.price_note ?? "";

  const href = card.cta_href || `/signup/teacher?plan=${encodeURIComponent(card.plan)}`;

  return (
    <div
      className={cn(
        "relative flex h-full flex-col rounded-2xl border p-7 transition hover:-translate-y-1.5",
        featured && "border-transparent bg-gradient-to-br from-cyan-700 to-cyan-900 text-white shadow-xl shadow-cyan-700/25 md:-translate-y-3",
        dark && "border-transparent bg-gradient-to-br from-slate-800 to-slate-950 text-white shadow-xl shadow-slate-900/30",
        !onColor && "border-slate-200 bg-white shadow-sm hover:border-cyan-300",
      )}
    >
      {card.badge ? (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-amber-400 px-4 py-1 text-xs font-bold text-cyan-950 shadow-md">
          {card.badge}
        </span>
      ) : null}
      {card.corner ? (
        <span className="absolute -right-2 -top-2 inline-flex items-center gap-1 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 px-3 py-1.5 text-[11px] font-bold text-white shadow-lg ring-2 ring-white">
          <ShieldCheck className="size-3.5" aria-hidden /> {card.corner}
        </span>
      ) : null}

      <h3 className="text-center font-display text-xl font-bold">{card.name}</h3>
      <p className={cn("mt-1 text-center text-sm", onColor ? "text-white/70" : "text-muted-foreground")}>{card.tagline}</p>

      <div className="mt-5 text-center">
        <span className={cn("font-display font-extrabold", card.price_hidden ? "text-2xl" : "text-4xl")}>{priceLabel}</span>
        {priceUnit ? <span className={cn("text-sm font-medium", onColor ? "text-white/70" : "text-muted-foreground")}>{priceUnit}</span> : null}
        {priceNote ? <p className={cn("mt-1.5 text-xs", onColor ? "text-white/70" : "text-muted-foreground")}>{priceNote}</p> : null}
      </div>

      <div className={cn("my-6 h-px", onColor ? "bg-white/20" : "bg-slate-100")} />

      <ul className="flex-1 space-y-2.5 text-sm">
        {card.features.map((f) => (
          <li key={f} className="flex items-start gap-2.5">
            <Check className={cn("mt-0.5 size-4 shrink-0", onColor ? "text-amber-300" : "text-emerald-600")} aria-hidden />
            <span className={onColor ? "text-white/95" : "text-foreground/85"}>{f}</span>
          </li>
        ))}
        {card.excluded.map((f) => (
          <li key={f} className={cn("flex items-start gap-2.5", onColor ? "text-white/55" : "text-muted-foreground")}>
            <Lock className="mt-0.5 size-4 shrink-0 opacity-60" aria-hidden /> <span>{f}</span>
          </li>
        ))}
      </ul>

      <Link
        href={href}
        className={cn(
          "mt-7 inline-flex w-full items-center justify-center rounded-xl px-4 py-2.5 text-sm font-bold transition",
          onColor
            ? "bg-amber-400 text-cyan-950 hover:bg-amber-300"
            : "border border-cyan-600 text-cyan-700 hover:bg-cyan-50",
        )}
      >
        {card.cta}
      </Link>
    </div>
  );
}
