import Link from "next/link";
import { Check, Sparkles } from "lucide-react";

import { apiServer } from "@/lib/api-server";
import { BrandLogo } from "@/components/brand-logo";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SignupTeacherForm } from "./signup-teacher-form";

/**
 * /signup/teacher — bağımsız öğretmen self-signup (Dalga 7 P3).
 *
 * 14 günlük deneme + BFF auto-login + soft e-posta doğrulama (banner ile).
 * Form yanında "14 günde neler açık?" değer paneli (Jinja parite).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Öğretmen Kaydı" };

interface TurnstileConfig {
  enabled: boolean;
  site_key: string | null;
}

const TRIAL_BENEFITS: { title: string; sub: string }[] = [
  { title: "Sınırsız öğrenci", sub: "Deneme boyunca öğrenci kapasiten yok" },
  { title: "Yapay zeka plan şablonu", sub: "Yapay zeka ile haftalık plan önerisi" },
  { title: "Veli WhatsApp bildirimi", sub: "Otomatik haftalık özet + düşüş alarmı" },
  { title: "Hedef ağacı + Risk paneli", sub: "5 göstergede risk skoru, hiyerarşik hedefler" },
  { title: "CSV toplu içe aktarım", sub: "Mevcut öğrenci listeni dakikalar içinde aktar" },
];

function TrialBenefits() {
  return (
    <div>
      <h2 className="font-display text-2xl font-extrabold tracking-tight sm:text-3xl">
        14 günde neler <span className="text-cyan-700">açık?</span>
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Pro özelliklerin tamamı, kredi kartı talep etmeden.
      </p>
      <ul className="mt-6 space-y-4">
        {TRIAL_BENEFITS.map((b) => (
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
      <div className="mt-7 rounded-2xl border border-cyan-200 bg-cyan-50/60 p-4 text-sm text-cyan-900">
        <span className="font-semibold text-cyan-800">14 gün sonra:</span>{" "}
        Hesabın Solo Ücretsiz&apos;e (3 öğrenci limit) kibarca düşer; verilerin
        korunur. İstediğin an Solo Pro&apos;ya yükseltebilirsin.
      </div>
    </div>
  );
}

export default async function SignupTeacherPage() {
  let turnstile: TurnstileConfig = { enabled: false, site_key: null };
  try {
    turnstile = await apiServer<TurnstileConfig>("/api/v2/auth/turnstile");
  } catch {
    // CAPTCHA config alınamazsa CAPTCHA'sız devam
  }
  return (
    <main className="force-light min-h-screen bg-background px-4 py-12">
      <div className="mx-auto w-full max-w-5xl">
        <div className="mb-8 flex justify-center">
          <BrandLogo href="/" size={36} wordmarkSize="text-xl" />
        </div>

        <div className="grid items-center gap-10 lg:grid-cols-2">
          {/* Değer paneli — mobilde formun altında */}
          <div className="order-2 lg:order-1">
            <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold text-cyan-800">
              <Sparkles className="size-3.5 text-amber-500" aria-hidden /> 14 gün ücretsiz · kart gerekmez
            </div>
            <TrialBenefits />
          </div>

          {/* Form */}
          <div className="order-1 mx-auto w-full max-w-sm lg:order-2">
            <Card className="lp-card border-slate-200">
              <CardHeader>
                <CardTitle>Hesap oluştur</CardTitle>
                <CardDescription>
                  14 gün ücretsiz deneyin. Kayıt sonrası e-postanıza bir doğrulama
                  bağlantısı göndereceğiz.
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
