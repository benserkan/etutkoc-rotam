"use client";

import * as React from "react";
import Link from "next/link";
import { Sparkles, User, Building2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { PricingCards } from "@/components/pricing/pricing-cards";
import { InstitutionContact } from "@/components/pricing/institution-contact";
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
  const solo = catalog.solo;
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
            <div className="mt-10">
              <PricingCards initial={catalog} variant="solo" />
            </div>

            {/* Bağımsız koç — paket sınırları özeti */}
            <div className="mt-14">
              <div className="mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="font-display text-lg font-bold">Bağımsız koç paketleri — bir bakışta</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Ücretsiz {solo.free.students} öğrenciye kadar, süresiz. Öğrenci sayın büyüdükçe
                  paketini yükselt. {solo.trial_days} gün boyunca tüm özellikler ücretsiz denenir.
                </p>
                <table className="mt-4 w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-muted-foreground">
                      <th className="pb-2 font-medium">Paket</th>
                      <th className="pb-2 font-medium">Öğrenci</th>
                      <th className="pb-2 text-right font-medium">Aylık</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-slate-50">
                      <td className="py-2 font-medium">Ücretsiz</td>
                      <td className="py-2">{solo.free.students} öğrenciye kadar</td>
                      <td className="py-2 text-right font-semibold">0 ₺</td>
                    </tr>
                    {solo.tiers.map((t) => (
                      <tr key={t.code} className="border-b border-slate-50">
                        <td className="py-2 font-medium">{t.label}</td>
                        <td className="py-2">
                          {t.max_students == null ? "Sınırsız öğrenci" : `${t.max_students} öğrenciye kadar`}
                        </td>
                        <td className="py-2 text-right font-semibold">{tl(t.monthly)}/ay</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
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
        <div className="mx-auto mt-12 max-w-3xl rounded-xl border border-cyan-200 bg-cyan-50/60 p-5 text-sm text-slate-700">
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
      </div>
    </main>
  );
}
