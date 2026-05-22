"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { PricingCards } from "@/components/pricing/pricing-cards";
import { InstitutionContact } from "@/components/pricing/institution-contact";
import type { PricingCatalog } from "@/lib/types/pricing";

function tl(n: number): string {
  return `${n.toLocaleString("tr-TR")} ₺`;
}

export function PricingClient({ catalog, initialType = "" }: { catalog: PricingCatalog; initialType?: string }) {
  const solo = catalog.solo;
  const isKurum = initialType === "kurum";

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

        <div className="mt-10">
          <PricingCards initial={catalog} />
        </div>

        {/* Bağımsız koç — öğrenci sayına göre fiyat tablosu */}
        <div className="mt-16">
          <div className="mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="font-display text-lg font-bold">Bağımsız koç — öğrenci sayına göre</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Ücretsiz {solo.free.students} öğrenciye kadar. Ücretli planda öğrenci sayın arttıkça
              öğrenci başı maliyet düşer. {solo.trial_days} gün boyunca tüm özellikler ücretsiz.
            </p>
            <table className="mt-4 w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs text-muted-foreground">
                  <th className="pb-2 font-medium">Öğrenci</th>
                  <th className="pb-2 text-right font-medium">Aylık</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-slate-50">
                  <td className="py-2">1–{solo.free.students} (Ücretsiz)</td>
                  <td className="py-2 text-right font-semibold">0 ₺</td>
                </tr>
                {solo.bands.map((b, i) => {
                  const prev = i === 0 ? solo.free.students : solo.bands[i - 1].max_students;
                  return (
                    <tr key={b.max_students} className="border-b border-slate-50">
                      <td className="py-2">{prev + 1}–{b.max_students} öğrenci</td>
                      <td className="py-2 text-right font-semibold">{tl(b.monthly)}/ay</td>
                    </tr>
                  );
                })}
                <tr>
                  <td className="py-2">{solo.bands[solo.bands.length - 1].max_students}+ öğrenci</td>
                  <td className="py-2 text-right font-semibold">öğrenci başı +{tl(solo.over_cap_per_student)}/ay</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Kurumsal — fiyat yok, iletişim formu */}
        <div className="mt-12">
          <InstitutionContact catalog={catalog} autoFocus={isKurum} />
        </div>

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
