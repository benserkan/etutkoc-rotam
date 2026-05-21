import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiServer } from "@/lib/api-server";
import { BrandLogo } from "@/components/brand-logo";
import { LoginForm } from "./login-form";

/**
 * Login sayfası (Dalga 7 P1).
 *
 * POST'lar /api/v2/auth/login'e gider; bcrypt doğrulaması + lockout + IP blok +
 * Turnstile CAPTCHA + audit + ActiveSession kaydı (G2a/G3 canlı panel) etkin.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Giriş",
};

interface TurnstileConfig {
  enabled: boolean;
  site_key: string | null;
}

export default async function LoginPage() {
  let turnstile: TurnstileConfig = { enabled: false, site_key: null };
  try {
    turnstile = await apiServer<TurnstileConfig>("/api/v2/auth/turnstile");
  } catch {
    // Turnstile config alınamazsa CAPTCHA'sız devam (backend zaten skip eder)
  }
  return (
    <main className="force-light min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center space-y-3 text-center">
          <BrandLogo href="/" size={40} wordmarkSize="text-2xl" />
          <p className="text-sm text-muted-foreground">
            Çalışma takip ve planlama sistemi
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Giriş yap</CardTitle>
            <CardDescription>Hesabınızla devam edin.</CardDescription>
          </CardHeader>
          <CardContent>
            <LoginForm
              turnstileEnabled={turnstile.enabled}
              turnstileSiteKey={turnstile.site_key}
            />
            <p className="mt-4 text-center text-sm">
              <Link href="/password/forgot" className="text-muted-foreground underline hover:text-foreground">
                Şifremi unuttum
              </Link>
            </p>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          KVKK aydınlatma metni:{" "}
          <Link href="/kvkk" className="underline hover:text-foreground">
            kvkk.etutkoc
          </Link>
        </p>
      </div>
    </main>
  );
}
