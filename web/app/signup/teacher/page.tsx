import Link from "next/link";
import { Building2, Check, Lock, Sparkles } from "lucide-react";

import { apiServer } from "@/lib/api-server";
import { BrandLogo } from "@/components/brand-logo";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { PricingCatalog, PricingCard } from "@/lib/types/pricing";
import { SignupTeacherForm } from "./signup-teacher-form";

/**
 * /signup/teacher — bağımsız öğretmen self-signup (Dalga 7 P3 + M6 pakete duyarlı).
 *
 * ?plan=solo_pro ile gelindiğinde seçilen paketin detayları gösterilir; anasayfa
 * kartıyla TUTARLI (aynı /api/v2/pricing kaynağı). 14 gün çerçevesi DÜRÜST:
 * denemede sınırsız öğrenci + tüm takip açık, yapay zekâ Solo'ya geçince devreye
 * girer (AI ücretli — trial/free kapalı, maliyet koruması).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Öğretmen Kaydı" };

interface TurnstileConfig {
  enabled: boolean;
  site_key: string | null;
}

function PlanValuePanel({
  card,
  planLabel,
  capText,
  trialDays,
  freeStudents,
}: {
  card: PricingCard | null;
  planLabel: string;
  capText: string;          // seçilen paketin öğrenci kapasitesi (örn. "10 öğrenciye kadar")
  trialDays: number;
  freeStudents: number;
}) {
  const planName = card?.name ?? planLabel;
  const tagline = card?.tagline ?? "Büyüyen, yapay zekâ kullanan koç için";

  // Denemede HEMEN açık olanlar — yapay zekâ DAHİL (50 kredi tavanıyla).
  // Öğrenci sayısı buraya YAZILMAZ: deneme tüm özellikleri açar; öğrenci
  // kapasitesi paket bilgisidir (aşağıdaki "Seçtiğin paket" rozeti).
  const trialOpen: { title: string; sub: string }[] = [
    { title: "Yapay zekâ hazırlığı — 50 kredi", sub: "Sesli dikte, fotoğraftan not, koçluk içgörüsü denemede açık" },
    { title: "Haftalık plan + günlük görev yönetimi", sub: "Programı kur, takip et" },
    { title: "Veliye otomatik ilerleme bildirimi", sub: "Veli sürekli 'ne yapıyor?' diye sormaz" },
    { title: "Deneme ve net gelişim takibi", sub: "Sınav sonuçları + akademik grafik" },
    { title: "Risk paneli + aralıklı tekrar", sub: "Kopan öğrenciyi erken yakala" },
  ];

  return (
    <div>
      <h2 className="font-display text-2xl font-extrabold tracking-tight sm:text-3xl">
        {planName} planını {trialDays} gün <span className="text-cyan-700">ücretsiz dene</span>
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">{tagline}</p>

      {/* Seçtiğin paket — öğrenci kapasitesi paket bilgisi olarak net gösterilir */}
      <div className="mt-4 inline-flex items-center gap-2 rounded-xl border border-cyan-200 bg-cyan-50/70 px-3 py-2 text-sm">
        <span className="font-semibold text-cyan-800">Seçtiğin paket:</span>
        <span className="font-medium text-foreground">{planName} · {capText}</span>
      </div>

      <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-cyan-700">
        Denemende hemen açık
      </p>
      <ul className="mt-3 space-y-3.5">
        {trialOpen.map((b) => (
          <li key={b.title} className="flex items-start gap-3">
            <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-cyan-100 text-cyan-700">
              <Check className="size-3.5" aria-hidden />
            </span>
            <div>
              <p className="font-semibold leading-tight">{b.title}</p>
              <p className="text-sm text-muted-foreground">{b.sub}</p>
            </div>
          </li>
        ))}
      </ul>

      {/* 14 gün sonra — dürüst çerçeve: ücretsiz plana düşüş + AI kapanması */}
      <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-sm text-amber-900">
        <p className="flex items-center gap-1.5 font-semibold text-amber-800">
          <Sparkles className="size-4 text-amber-500" aria-hidden /> {trialDays} gün sonra ne olur?
        </p>
        <p className="mt-1.5 flex items-start gap-2">
          <Lock className="mt-0.5 size-3.5 shrink-0 opacity-70" aria-hidden />
          <span>
            Yükseltmezsen hesabın <strong>Solo Ücretsiz</strong>&apos;e ({freeStudents} öğrenci)
            kibarca düşer ve yapay zekâ kapanır; verilerin korunur. <strong>{planName}</strong>
            {" "}paketine geçince öğrenci kapasiten ve yapay zekâ kesintisiz devam eder.
          </span>
        </p>
      </div>
    </div>
  );
}

export default async function SignupTeacherPage({
  searchParams,
}: {
  searchParams: Promise<{ plan?: string }>;
}) {
  const sp = await searchParams;
  const planParam = sp.plan ?? "solo_pro";

  let turnstile: TurnstileConfig = { enabled: false, site_key: null };
  let catalog: PricingCatalog | null = null;
  try {
    [turnstile, catalog] = await Promise.all([
      apiServer<TurnstileConfig>("/api/v2/auth/turnstile"),
      apiServer<PricingCatalog>("/api/v2/pricing"),
    ]);
  } catch {
    // Config alınamazsa CAPTCHA'sız + varsayılan panelle devam
  }

  const cards = catalog?.cards ?? [];
  const requested = cards.find((c) => c.plan === planParam) ?? null;
  const isInstitutionPlan = requested?.audience === "institution";
  // Gelinen solo paketi gösterilir; yoksa öne çıkan Solo kartı (free/kurum seçilse bile).
  const soloCard =
    (requested && requested.audience === "solo" ? requested : null) ??
    cards.find((c) => c.audience === "solo" && c.highlight) ??
    cards.find((c) => c.audience === "solo") ??
    null;
  const trialDays = catalog?.solo.trial_days ?? 14;
  const freeStudents = catalog?.solo.free.students ?? 3;

  // Seçilen Solo paketinin öğrenci tavanı — "denemede hemen açık" satırı bununla
  // tutarlı olmalı (örn. Solo Başlangıç → 10 öğrenci; "sınırsız" değil).
  const soloTiers = catalog?.solo.tiers ?? [];
  const selectedTier =
    soloTiers.find((t) => t.code === (soloCard?.plan ?? planParam)) ??
    soloTiers.find((t) => t.code === planParam) ??
    null;
  const planLabel = soloCard?.name ?? selectedTier?.label ?? "Solo";
  const capText =
    selectedTier && selectedTier.max_students != null
      ? `${selectedTier.max_students} öğrenciye kadar`
      : "Sınırsız öğrenci";

  return (
    <main className="force-light min-h-screen bg-background px-4 py-12">
      <div className="mx-auto w-full max-w-5xl">
        <div className="mb-8 flex justify-center">
          <BrandLogo href="/" size={36} wordmarkSize="text-xl" />
        </div>

        {isInstitutionPlan ? (
          <div className="mx-auto mb-8 max-w-3xl rounded-2xl border border-slate-300 bg-slate-50 p-4 text-sm text-slate-700">
            <p className="flex items-center gap-2 font-semibold text-slate-800">
              <Building2 className="size-4" aria-hidden /> Kurumsal bir plan seçtiniz
            </p>
            <p className="mt-1">
              Kurumlar için fiyat ve kurulum size özel belirlenir.{" "}
              <Link href="/pricing?type=kurum" className="font-medium text-cyan-700 underline-offset-4 hover:underline">
                Kurumsal teklif formuna gidin
              </Link>
              . Yine de bağımsız koç olarak {trialDays} gün ücretsiz deneyebilirsiniz.
            </p>
          </div>
        ) : null}

        <div className="grid items-center gap-10 lg:grid-cols-2">
          {/* Değer paneli — mobilde formun altında */}
          <div className="order-2 lg:order-1">
            <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold text-cyan-800">
              <Sparkles className="size-3.5 text-amber-500" aria-hidden /> {trialDays} gün ücretsiz · kart gerekmez
            </div>
            <PlanValuePanel
              card={soloCard}
              planLabel={planLabel}
              capText={capText}
              trialDays={trialDays}
              freeStudents={freeStudents}
            />
          </div>

          {/* Form */}
          <div className="order-1 mx-auto w-full max-w-sm lg:order-2">
            <Card className="lp-card border-slate-200">
              <CardHeader>
                <CardTitle>Hesap oluştur</CardTitle>
                <CardDescription>
                  {trialDays} gün ücretsiz deneyin. Kayıt sonrası e-postanıza bir
                  doğrulama bağlantısı göndereceğiz.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SignupTeacherForm
                  turnstileEnabled={turnstile.enabled}
                  turnstileSiteKey={turnstile.site_key}
                />
              </CardContent>
            </Card>
            <p className="mt-4 text-center text-sm text-muted-foreground">
              Zaten hesabınız var mı?{" "}
              <Link href="/login" className="font-medium text-cyan-700 underline-offset-4 hover:underline">
                Giriş yapın
              </Link>
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
