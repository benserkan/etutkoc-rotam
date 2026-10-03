"use client";

import * as React from "react";
import Link from "next/link";
import { Building2, Check, ChevronDown, User } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { PricingCards } from "@/components/pricing/pricing-cards";
import { SoloPlans } from "@/components/pricing/solo-plans";
import { InstitutionContact } from "@/components/pricing/institution-contact";
import { FloatingWhatsApp } from "@/components/contact/floating-whatsapp";
import { PaymentMethods } from "@/components/payment-methods";
import { CreditCostsTable, PlanFaq, PlanMatrix } from "@/components/pricing/plan-extras";
import { PlanWizard } from "@/components/pricing/plan-wizard";
import { useQuery } from "@tanstack/react-query";
import { getPublicTestimonials, testimonialKeys } from "@/lib/api/testimonials";
import type { TestimonialPublicResponse } from "@/lib/types/testimonial";
import type { PricingCatalog } from "@/lib/types/pricing";

function tl(n: number): string {
  return `${n.toLocaleString("tr-TR")} ₺`;
}

type Tab = "solo" | "institution";

export function PricingClient({
  catalog,
  initialType = "",
  turnstileEnabled = false,
  turnstileSiteKey = null,
}: {
  catalog: PricingCatalog;
  initialType?: string;
  turnstileEnabled?: boolean;
  turnstileSiteKey?: string | null;
}) {
  const [tab, setTab] = React.useState<Tab>(initialType === "kurum" ? "institution" : "solo");

  return (
    <main className="force-light min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <BrandLogo href="/" size={32} />
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm"><Link href="/login">Giriş</Link></Button>
            <Button asChild size="sm"><Link href="/signup/teacher">Ücretsiz başla</Link></Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl space-y-10 px-4 py-10 sm:py-14">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Sana uygun paketi seç
          </h1>
          <p className="mt-3 text-base leading-relaxed text-muted-foreground">
            Bir öğrencinin aylık koçluk ücretinin küçük bir kesriyle tüm öğrencilerini tek yerden
            yönet. {catalog.solo.trial_days} gün ücretsiz dene, kart bilgisi istemez.
          </p>
          <div className="mt-6 inline-flex rounded-full border border-border bg-muted/50 p-1" role="radiogroup" aria-label="Kimin için">
            {([
              ["solo", "Bireysel koç", User],
              ["institution", "Kurum", Building2],
            ] as const).map(([key, label, Icon]) => (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={tab === key}
                onClick={() => setTab(key)}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-semibold transition",
                  tab === key ? "bg-cyan-700 text-white" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="size-4" aria-hidden /> {label}
              </button>
            ))}
          </div>
        </div>

        {tab === "solo" ? (
          <>
            <SoloPlans catalog={catalog} />

            <ul className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
              {[
                `${catalog.solo.trial_days} gün ücretsiz deneme`,
                "Kart bilgisi istemez",
                "İstediğin zaman iptal",
                "Verilerin hep senin",
              ].map((t) => (
                <li key={t} className="flex items-center gap-1.5">
                  <Check className="size-4 text-emerald-600" aria-hidden /> {t}
                </li>
              ))}
            </ul>

            <div className="mx-auto max-w-4xl">
              <PlanWizard catalog={catalog} onSkip={() => window.scrollTo({ top: 0, behavior: "smooth" })} />
            </div>

            <details className="group mx-auto max-w-4xl rounded-3xl border border-border bg-card">
              <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4 text-sm font-semibold text-foreground">
                Tüm özellikleri ve kredi maliyetlerini yan yana gör
                <ChevronDown className="size-5 text-muted-foreground transition group-open:rotate-180" aria-hidden />
              </summary>
              <div className="space-y-5 px-5 pb-5">
                <PlanMatrix catalog={catalog} />
                <CreditCostsTable rows={catalog.credit_costs ?? []} />
              </div>
            </details>

            <div className="mx-auto max-w-4xl">
              <PlanFaq />
            </div>

            <TestimonialBand />

          </>
        ) : (
          <>
            <div>
              <PricingCards initial={catalog} variant="institution" />
            </div>

            {/* Kurum kademeleri */}
            <div>
              <div className="mx-auto max-w-2xl rounded-3xl border border-border bg-card p-6">
                <h2 className="font-display text-lg font-bold">Kurum kademeleri — koç sayısına göre</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Fiyat koç sayısına göre kademelidir (toplam aylık). Ücretsiz {catalog.institution.free.teachers} öğretmen
                  ve {catalog.institution.free.students} öğrenci ile dene. {catalog.institution.trial_days} gün pilot.
                </p>
                <table className="mt-4 w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-muted-foreground">
                      <th className="pb-2 font-medium">Kademe</th>
                      <th className="pb-2 font-medium">Koç</th>
                      <th className="pb-2 text-right font-medium">Aylık (toplam)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {catalog.institution.tiers.map((t) => (
                      <tr key={t.code} className="border-b border-slate-50">
                        <td className="py-2 font-medium">{t.label}</td>
                        <td className="py-2">
                          {t.max_coaches == null
                            ? `${t.min_coaches}+ koç`
                            : `${t.min_coaches}–${t.max_coaches} koç`}
                        </td>
                        <td className="py-2 text-right font-semibold">
                          {t.price_hidden || t.monthly_total == null ? "Özel teklif" : `${tl(t.monthly_total)}/ay`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-3 text-xs text-muted-foreground">
                  Her koç ortalama {catalog.institution.students_per_coach} öğrenciye kadar takip eder.
                  50+ koç ve özel okullar için white-label dahil özel sözleşme sunulur.
                </p>
              </div>
            </div>

            {/* Kurumsal — fiyat yok, iletişim formu */}
            <div>
              <InstitutionContact
                catalog={catalog}
                autoFocus
                turnstileEnabled={turnstileEnabled}
                turnstileSiteKey={turnstileSiteKey}
              />
            </div>
          </>
        )}

        <p className="text-center text-sm text-muted-foreground">
          Fiyatlara KDV dahil değildir. Ödeme kartla, 3D Secure ile alınır.
        </p>

        <div className="flex justify-center border-t border-border pt-8">
          <PaymentMethods variant="light" className="items-center text-center" />
        </div>
      </div>
      <FloatingWhatsApp phone={catalog.contact.whatsapp} />
    </main>
  );
}


/* ── Referans bandı — yayınlanmış yorumlar (sosyal kanıt; yoksa hiç render olmaz) ── */
function TestimonialBand() {
  const q = useQuery<TestimonialPublicResponse>({
    queryKey: testimonialKeys.public(null),
    queryFn: () => getPublicTestimonials(null, 6),
    staleTime: 5 * 60_000,
  });
  const items = (q.data?.items ?? []).slice(0, 3);
  if (items.length === 0) return null;
  return (
    <div className="mx-auto max-w-5xl">
      <h2 className="text-center font-display text-lg font-bold">Kullananlar ne diyor?</h2>
      <div className="mt-5 grid gap-4 md:grid-cols-3">
        {items.map((t) => (
          <figure key={t.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <blockquote className="text-sm leading-6 text-slate-700">
              &ldquo;{t.content.length > 220 ? t.content.slice(0, 220) + "…" : t.content}&rdquo;
            </blockquote>
            <figcaption className="mt-3 text-xs font-semibold text-slate-900">
              {t.author_name}
              {t.author_role_label || t.institution_name ? (
                <span className="font-normal text-muted-foreground">
                  {" "}· {t.institution_name ?? t.author_role_label}
                </span>
              ) : null}
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}
