"use client";

import * as React from "react";
import Link from "next/link";
import { Sparkles, User, Building2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { PricingCards } from "@/components/pricing/pricing-cards";
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

      <div className="mx-auto max-w-6xl px-4 py-10 sm:py-14">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">Sana uygun planı seç</h1>
          <p className="mt-3 text-muted-foreground">
            Bir öğrencinin aylık koçluk ücretinin küçük bir kesriyle tüm öğrencilerini
            tek yerden yönet. Yapay zekâ destekli içgörü, veli güveni ve sınav odaklı takip.
          </p>
        </div>

        {/* Bireysel / Kurumsal sekmeleri */}
        <div className="mt-8 flex justify-center">
          <div className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white p-1 shadow-sm">
            <button
              type="button"
              onClick={() => setTab("solo")}
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-bold transition",
                tab === "solo" ? "bg-cyan-700 text-white shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <User className="size-4" aria-hidden /> Bireysel Koç
            </button>
            <button
              type="button"
              onClick={() => setTab("institution")}
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-bold transition",
                tab === "institution" ? "bg-slate-800 text-white shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Building2 className="size-4" aria-hidden /> Kurum
            </button>
          </div>
        </div>

        {tab === "solo" ? (
          <>
            {/* Paket seçim sihirbazı — ihtiyaçtan pakete (atlayan kartlardan seçer) */}
            <PlanWizard
              catalog={catalog}
              onSkip={() =>
                document.getElementById("paketler")?.scrollIntoView({ behavior: "smooth" })
              }
            />

            <div id="paketler" className="mt-8 scroll-mt-24">
              <PricingCards initial={catalog} variant="solo" />
            </div>

            {/* Güven şeridi */}
            <p className="mt-6 text-center text-xs text-muted-foreground">
              {catalog.solo.trial_days} gün ücretsiz deneme · kart bilgisi istemez · istediğin zaman iptal · verilerin hep senin
            </p>

            <div className="mx-auto mt-10 max-w-4xl space-y-5">
              <PlanMatrix catalog={catalog} />
              <CreditCostsTable rows={catalog.credit_costs ?? []} />
              <PlanFaq />
            </div>

            <TestimonialBand />

          </>
        ) : (
          <>
            <div className="mt-10">
              <PricingCards initial={catalog} variant="institution" />
            </div>

            {/* Kurum kademeleri */}
            <div className="mt-14">
              <div className="mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
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
            <div className="mt-12">
              <InstitutionContact
                catalog={catalog}
                autoFocus
                turnstileEnabled={turnstileEnabled}
                turnstileSiteKey={turnstileSiteKey}
              />
            </div>
          </>
        )}

        {/* AI note */}
        <div className="mx-auto mt-12 max-w-3xl rounded-xl border border-cyan-200 bg-cyan-50/60 p-5 text-sm text-slate-700 dark:bg-cyan-500/10 dark:border-cyan-500/30 dark:text-slate-200">
          <p className="flex items-center gap-2 font-semibold text-cyan-900">
            <Sparkles className="size-4" aria-hidden /> Yapay zekâ ücretli planlarda dahildir
          </p>
          <p className="mt-1.5">
            Sesli dikte, fotoğraftan seans doldurma ve koçluk içgörüsü ücretli planlarda
            aylık kredi ile gelir. Ücretsiz planlarda kapalıdır; dilediğin an yükseltebilirsin.
          </p>
        </div>

        <p className="mt-8 text-center text-sm text-muted-foreground">
          Tüm planlar KDV hariçtir. Yükseltme manuel aktivasyonla yapılır — planı seçip
          kayıt olduktan sonra hesabın hızlıca aktive edilir.
        </p>

        <div className="mt-10 flex justify-center border-t border-slate-200 pt-8">
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
    <div className="mx-auto mt-12 max-w-5xl">
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
