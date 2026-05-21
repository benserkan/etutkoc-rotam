"use client";

import * as React from "react";
import Link from "next/link";
import { Check, GraduationCap, Lock, Sparkles, Users } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import type { PricingCatalog } from "@/lib/types/pricing";

function tl(n: number): string {
  return `${n.toLocaleString("tr-TR")} ₺`;
}

type Audience = "solo" | "institution";

export function PricingClient({ catalog }: { catalog: PricingCatalog }) {
  const [audience, setAudience] = React.useState<Audience>("solo");
  const [annual, setAnnual] = React.useState(false);
  const months = catalog.annual_paid_months; // 10
  const freeMonths = 12 - months;

  // Yıllık görünümde aylık eşdeğeri (10 ay / 12) gösterelim ki kıyas net olsun.
  const perMonth = (monthly: number) =>
    annual ? Math.round((monthly * months) / 12) : monthly;

  const soloBandLabel = (i: number, max: number) => {
    const prevMax = i === 0 ? 0 : catalog.solo.bands[i - 1].max_students;
    return `${prevMax + 1}–${max} öğrenci`;
  };

  return (
    <main className="force-light min-h-screen bg-background">
      {/* Header */}
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
        {/* Hero */}
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Sana uygun planı seç</h1>
          <p className="mt-3 text-muted-foreground">
            Bir öğrencinin aylık koçluk ücretinin küçük bir kesriyle tüm öğrencilerini
            tek yerden yönet. Yapay zekâ destekli içgörü, veli güveni ve sınav odaklı takip.
          </p>
        </div>

        {/* Audience + annual toggle */}
        <div className="mt-8 flex flex-col items-center gap-4">
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
            <button
              onClick={() => setAudience("solo")}
              className={cn("inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition",
                audience === "solo" ? "bg-cyan-600 text-white" : "text-slate-600 hover:bg-slate-100")}
            >
              <GraduationCap className="size-4" aria-hidden /> Bağımsız Koç
            </button>
            <button
              onClick={() => setAudience("institution")}
              className={cn("inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition",
                audience === "institution" ? "bg-cyan-600 text-white" : "text-slate-600 hover:bg-slate-100")}
            >
              <Users className="size-4" aria-hidden /> Kurum
            </button>
          </div>
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
            <span className={cn(!annual && "font-semibold")}>Aylık</span>
            <button
              type="button"
              role="switch"
              aria-checked={annual}
              onClick={() => setAnnual((v) => !v)}
              className={cn("relative h-6 w-11 rounded-full transition", annual ? "bg-cyan-600" : "bg-slate-300")}
            >
              <span className={cn("absolute top-0.5 size-5 rounded-full bg-white transition", annual ? "left-[22px]" : "left-0.5")} />
            </button>
            <span className={cn(annual && "font-semibold")}>
              Yıllık <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-bold text-amber-700">{freeMonths} ay bedava</span>
            </span>
          </label>
        </div>

        {/* SOLO */}
        {audience === "solo" ? (
          <section className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <PlanCard
              title="Ücretsiz"
              priceLabel="0 ₺"
              sub={`${catalog.solo.free.students} öğrenciye kadar`}
              features={["Görev planlama + takip", "Temel analiz", "Veli daveti"]}
              excluded={["Yapay zekâ özellikleri", "Sınırsız öğrenci"]}
              cta={<Button asChild variant="outline" className="w-full"><Link href="/signup/teacher">Ücretsiz başla</Link></Button>}
            />
            {catalog.solo.bands.map((b, i) => (
              <PlanCard
                key={b.max_students}
                title={soloBandLabel(i, b.max_students)}
                priceLabel={tl(perMonth(b.monthly))}
                priceSuffix="/ay"
                annualNote={annual ? `Yıllık ${tl(b.monthly * months)} (peşin)` : undefined}
                highlight={i === 1}
                aiIncluded
                features={[
                  `${b.max_students} öğrenciye kadar`,
                  "Yapay zekâ içgörü + sesli dikte + foto",
                  "Veli güveni paneli",
                  "Deneme/akademik takip",
                ]}
                cta={<Button asChild className="w-full"><Link href="/signup/teacher">{catalog.solo.trial_days} gün ücretsiz dene</Link></Button>}
              />
            ))}
          </section>
        ) : null}

        {audience === "solo" ? (
          <p className="mx-auto mt-5 max-w-2xl text-center text-xs text-muted-foreground">
            30 öğrenciden fazlası için öğrenci başına +{tl(catalog.solo.over_cap_per_student)}/ay.
            Yeni kayıtlar {catalog.solo.trial_days} gün boyunca tüm Pro özellikleri ücretsiz dener.
          </p>
        ) : null}

        {/* INSTITUTION */}
        {audience === "institution" ? (
          <section className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <PlanCard
              title="Kurum Tanıma"
              priceLabel="0 ₺"
              sub={`${catalog.institution.free.teachers} öğretmen · ${catalog.institution.free.students} öğrenci`}
              features={["Görev planlama + temel analiz", "Manuel raporlama"]}
              excluded={["Yapay zekâ özellikleri", "Otomatik raporlar"]}
              cta={<Button asChild variant="outline" className="w-full"><Link href="/signup/teacher">Pilot başvurusu</Link></Button>}
            />
            {catalog.institution.tiers.map((t) => (
              <PlanCard
                key={t.code}
                title={t.label}
                priceLabel={t.code === "enterprise" ? "Özel" : tl(perMonth(t.per_coach_monthly))}
                priceSuffix={t.code === "enterprise" ? undefined : "/koç/ay"}
                annualNote={annual && t.code !== "enterprise" ? `Yıllık ${tl(t.per_coach_monthly * months)}/koç` : undefined}
                highlight={t.code === "dershane_pro"}
                aiIncluded
                features={[
                  t.max_coaches ? `${t.min_coaches}–${t.max_coaches} koç` : `${t.min_coaches}+ koç`,
                  `Koç başına ${catalog.institution.students_per_coach} öğrenci`,
                  "Yapay zekâ + havuz kredi",
                  t.white_label ? "White-label + atanmış yönetici" : "Risk paneli + kohort + raporlar",
                ]}
                cta={
                  t.code === "enterprise"
                    ? <Button asChild variant="outline" className="w-full"><Link href="/signup/teacher">İletişime geç</Link></Button>
                    : <Button asChild className="w-full"><Link href="/signup/teacher">{catalog.institution.trial_days} gün pilot</Link></Button>
                }
              />
            ))}
          </section>
        ) : null}

        {audience === "institution" ? (
          <p className="mx-auto mt-5 max-w-2xl text-center text-xs text-muted-foreground">
            Faturalama akademik yıl (10 ay peşin) uyumludur. Her koç {catalog.institution.students_per_coach} öğrenciye
            kadar; fazlası için ek koç lisansı.
          </p>
        ) : null}

        {/* AI note */}
        <div className="mx-auto mt-12 max-w-3xl rounded-xl border border-cyan-200 bg-cyan-50/60 p-5 text-sm text-slate-700">
          <p className="flex items-center gap-2 font-semibold text-cyan-900">
            <Sparkles className="size-4" aria-hidden /> Yapay zekâ özellikleri ücretli planlarda dahildir
          </p>
          <p className="mt-1.5">
            Sesli dikte, fotoğraftan seans doldurma ve koçluk içgörüsü ücretli planlarda
            aylık kredi ile gelir. Ücretsiz planlarda <Lock className="inline size-3.5" aria-hidden /> kapalıdır;
            dilediğin an yükseltebilirsin.
          </p>
        </div>

        <p className="mt-8 text-center text-sm text-muted-foreground">
          Tüm planlar KDV hariçtir. Sorular için{" "}
          <Link href="/signup/teacher" className="font-medium text-cyan-700 underline-offset-4 hover:underline">ücretsiz başla</Link>{" "}
          veya bizimle iletişime geç.
        </p>
      </div>
    </main>
  );
}

function PlanCard({
  title,
  priceLabel,
  priceSuffix,
  sub,
  annualNote,
  features,
  excluded = [],
  highlight = false,
  aiIncluded = false,
  cta,
}: {
  title: string;
  priceLabel: string;
  priceSuffix?: string;
  sub?: string;
  annualNote?: string;
  features: string[];
  excluded?: string[];
  highlight?: boolean;
  aiIncluded?: boolean;
  cta: React.ReactNode;
}) {
  return (
    <div className={cn(
      "flex flex-col rounded-xl border bg-white p-5 shadow-sm",
      highlight ? "border-cyan-500 ring-2 ring-cyan-500/30" : "border-slate-200",
    )}>
      {highlight ? (
        <span className="mb-2 inline-flex w-fit rounded-full bg-cyan-600 px-2.5 py-0.5 text-[11px] font-bold text-white">En popüler</span>
      ) : null}
      <h3 className="text-base font-semibold">{title}</h3>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-2xl font-bold tracking-tight">{priceLabel}</span>
        {priceSuffix ? <span className="text-sm text-muted-foreground">{priceSuffix}</span> : null}
      </div>
      {sub ? <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p> : null}
      {annualNote ? <p className="mt-0.5 text-[11px] text-amber-700">{annualNote}</p> : null}
      {aiIncluded ? (
        <p className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-cyan-700">
          <Sparkles className="size-3.5" aria-hidden /> Yapay zekâ dahil
        </p>
      ) : null}

      <ul className="mt-4 flex-1 space-y-1.5 text-sm">
        {features.map((f) => (
          <li key={f} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden /> {f}</li>
        ))}
        {excluded.map((f) => (
          <li key={f} className="flex gap-2 text-muted-foreground"><Lock className="mt-0.5 size-4 shrink-0 text-slate-400" aria-hidden /> {f}</li>
        ))}
      </ul>

      <div className="mt-5">{cta}</div>
    </div>
  );
}
