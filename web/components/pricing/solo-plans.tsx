"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";

import { FeatureLine, buildGlossaryMap } from "@/components/pricing/feature-info";
import { CycleSwitch, PlanOption, annualOf, tl, type Cycle } from "@/components/pricing/plan-ui";
import type { PricingCatalog } from "@/lib/types/pricing";

/**
 * /pricing — bireysel koç paketleri (2026-10-03, Paketim ile aynı dil).
 * Paketler seçilebilir kartlar; seçilenin içeriği ve tek eylem altta.
 * Fiyatlar katalogdan (akademik yıl = indirimli aylık × ay sayısı).
 */
export function SoloPlans({ catalog }: { catalog: PricingCatalog }) {
  const cards = catalog.cards.filter((c) => c.audience === "solo");
  const featured = cards.find((c) => c.highlight) ?? cards.find((c) => c.plan !== "solo_free") ?? cards[0];
  const [selected, setSelected] = React.useState(featured?.plan ?? "");
  const [cycle, setCycle] = React.useState<Cycle>("monthly");
  const glossary = buildGlossaryMap(catalog.feature_glossary);
  const discountPct = catalog.annual_discount_pct ?? 20;
  const sel = cards.find((c) => c.plan === selected) ?? featured;
  if (!sel) return null;

  const priceOf = (plan: string, monthly: number) => {
    if (monthly === 0) return { monthly: 0, total: 0, months: 1 };
    if (cycle === "monthly") return { monthly, total: monthly, months: 1 };
    return annualOf(catalog, plan, monthly);
  };
  const capOf = (plan: string) => {
    if (plan === "solo_free") return `${catalog.solo.free.students} öğrenciye kadar`;
    const t = catalog.solo.tiers.find((x) => x.code === plan);
    return t?.max_students == null ? "Sınırsız öğrenci" : `${t.max_students} öğrenciye kadar`;
  };
  const selPrice = priceOf(sel.plan, sel.monthly);
  const isFree = sel.monthly === 0;
  const features = catalog.plan_features[sel.plan] ?? sel.features;
  const href = sel.cta_href || `/signup/teacher?plan=${encodeURIComponent(sel.plan)}`;

  return (
    <section className="space-y-5" aria-label="Bireysel koç paketleri">
      <div className="flex flex-col items-center gap-2">
        <CycleSwitch cycle={cycle} onChange={setCycle} discountPct={discountPct} />
        <p className="text-sm text-muted-foreground">
          {cycle === "academic_year"
            ? `Akademik yıl: ${catalog.annual_paid_months} ay, tek ödeme, her ay %${discountPct} daha ucuz`
            : "Aylık öde, istediğin zaman iptal et"}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" role="radiogroup" aria-label="Paket seçimi">
        {cards.map((c) => {
          const p = priceOf(c.plan, c.monthly);
          return (
            <PlanOption
              key={c.key}
              name={c.name}
              capacity={capOf(c.plan)}
              price={c.monthly === 0 ? "Ücretsiz" : tl(p.monthly)}
              unit={c.monthly === 0 ? "" : "/ay"}
              priceNote={cycle === "academic_year" && c.monthly > 0 ? `${p.months} ay · toplam ${tl(p.total)}` : null}
              credits={c.credits_monthly || null}
              tag={c.badge || null}
              selected={c.plan === sel.plan}
              onSelect={() => setSelected(c.plan)}
            />
          );
        })}
      </div>

      <div className="rounded-3xl bg-muted/50 p-5 sm:p-7">
        <h3 className="font-display text-lg font-semibold text-foreground">{sel.name} paketinde neler var?</h3>
        {sel.tagline ? <p className="mt-1 text-sm text-muted-foreground">{sel.tagline}</p> : null}
        <ul className="mt-4 grid gap-2.5 sm:grid-cols-2">
          {features.map((f) => (
            <li key={f} className="flex items-start gap-2.5 text-sm">
              <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
              <FeatureLine text={f} glossary={glossary} tone="theme" />
            </li>
          ))}
        </ul>
        <div className="mt-6 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            {isFree ? (
              "Kart bilgisi istemez, süresiz ücretsiz."
            ) : (
              <>
                {cycle === "academic_year" ? `Akademik yıl (${selPrice.months} ay):` : "Aylık:"}{" "}
                <b className="text-lg text-foreground">{tl(selPrice.total)}</b>
                <span className="block text-xs">
                  Önce {catalog.solo.trial_days} gün ücretsiz dene, kart bilgisi istemez.
                </span>
              </>
            )}
          </p>
          <Link
            href={href}
            className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-cyan-700 px-6 text-base font-semibold text-white transition hover:bg-cyan-800 sm:w-auto"
          >
            {isFree ? "Ücretsiz başla" : `${sel.name} ile ${catalog.solo.trial_days} gün ücretsiz dene`}
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </div>
    </section>
  );
}
