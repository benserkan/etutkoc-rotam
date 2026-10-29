import Link from "next/link";
import { CalendarCheck2, LineChart, ShieldCheck, Users } from "lucide-react";

import { apiServer } from "@/lib/api-server";
import { BrandLogo } from "@/components/brand-logo";
import { TurnstilePreconnect } from "@/components/turnstile-widget";
import { LoginForm } from "./login-form";

/**
 * Login sayfası.
 *
 * POST'lar /api/v2/auth/login'e gider; bcrypt doğrulaması + lockout + IP blok +
 * Turnstile CAPTCHA + audit + ActiveSession kaydı etkin. Düzen: masaüstünde solda
 * marka paneli, sağda form; mobilde yalnız form (marka üstte kompakt).
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Giriş",
};

interface TurnstileConfig {
  enabled: boolean;
  site_key: string | null;
}

const POINTS = [
  { icon: CalendarCheck2, title: "Haftalık program", text: "Kitaba bağlı görevler, kalan test kendiliğinden düşer." },
  { icon: LineChart, title: "Deneme analizi", text: "Karne yüklenir, konu konu nerede net kaçtığı görünür." },
  { icon: Users, title: "Koç, öğrenci, veli", text: "Herkes aynı programı kendi ekranından izler." },
];

export default async function LoginPage() {
  let turnstile: TurnstileConfig = { enabled: false, site_key: null };
  try {
    turnstile = await apiServer<TurnstileConfig>("/api/v2/auth/turnstile");
  } catch {
    // Turnstile config alınamazsa CAPTCHA'sız devam (backend zaten skip eder)
  }
  const captcha = turnstile.enabled && !!turnstile.site_key;

  return (
    <main className="force-light min-h-dvh bg-slate-100 text-slate-900">
      {captcha ? <TurnstilePreconnect /> : null}
      <div className="mx-auto grid min-h-dvh max-w-6xl lg:grid-cols-[1.05fr_1fr]">
        {/* Marka paneli — yalnız geniş ekranda */}
        <section className="relative hidden overflow-hidden bg-gradient-to-br from-cyan-900 via-cyan-800 to-slate-900 p-12 text-white lg:my-6 lg:flex lg:flex-col lg:justify-between lg:rounded-3xl">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-amber-400/20 blur-3xl"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -bottom-32 -left-16 size-96 rounded-full bg-cyan-400/20 blur-3xl"
          />
          <BrandLogo href="/" size={34} wordmarkSize="text-2xl" wordmarkClassName="text-white" />

          <div className="relative space-y-8">
            <div className="space-y-3">
              <h1 className="font-display text-4xl font-bold leading-tight tracking-tight">
                Öğrencinin yolculuğu
                <br />
                tek panelde.
              </h1>
              <p className="max-w-md text-base text-cyan-100">
                Program, deneme ve veli iletişimi aynı yerde. Kaldığın yerden devam et.
              </p>
            </div>
            <ul className="space-y-4">
              {POINTS.map(({ icon: Icon, title, text }) => (
                <li key={title} className="flex gap-3">
                  <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/15">
                    <Icon className="size-4.5 text-amber-300" aria-hidden />
                  </span>
                  <span>
                    <span className="block font-semibold">{title}</span>
                    <span className="block text-sm text-cyan-100">{text}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <p className="relative flex items-center gap-2 text-xs text-cyan-200">
            <ShieldCheck className="size-4" aria-hidden />
            Bağlantı şifreli · veriler KVKK kapsamında işlenir
          </p>
        </section>

        {/* Form */}
        <section className="flex items-center justify-center px-4 py-10 sm:px-8">
          <div className="w-full max-w-md">
            <div className="mb-8 flex justify-center lg:hidden">
              <BrandLogo href="/" size={36} wordmarkSize="text-2xl" />
            </div>

            <div className="rounded-3xl bg-white p-7 shadow-xl shadow-slate-900/5 ring-1 ring-slate-200 sm:p-9">
              <div className="mb-7 space-y-1.5">
                <h2 className="font-display text-2xl font-bold tracking-tight text-slate-900">
                  Tekrar hoş geldin
                </h2>
                <p className="text-sm text-slate-500">
                  Hesabının e-posta adresi ve şifresiyle giriş yap.
                </p>
              </div>

              <LoginForm
                turnstileEnabled={turnstile.enabled}
                turnstileSiteKey={turnstile.site_key}
              />
            </div>

            <p className="mt-6 text-center text-sm text-slate-600">
              Hesabın yok mu?{" "}
              <Link href="/signup/teacher" className="font-semibold text-cyan-800 hover:underline">
                14 gün ücretsiz dene
              </Link>
            </p>
            <p className="mt-3 text-center text-xs text-slate-500">
              <Link href="/kvkk" className="underline-offset-2 hover:underline">
                KVKK aydınlatma metni
              </Link>
              {" · "}
              <Link href="/kullanim-sartlari" className="underline-offset-2 hover:underline">
                Kullanım şartları
              </Link>
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
