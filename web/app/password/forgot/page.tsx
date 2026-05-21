import Link from "next/link";

import { apiServer } from "@/lib/api-server";
import { BrandLogo } from "@/components/brand-logo";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ForgotPasswordForm } from "./forgot-form";

/**
 * /password/forgot — self-service şifre sıfırlama isteği (Dalga 7 P2).
 *
 * E-posta alır → POST /api/v2/auth/forgot-password. Enumeration koruması:
 * yanıt her zaman generic ("kayıtlıysa bağlantı gönderildi").
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Şifremi Unuttum" };

interface TurnstileConfig {
  enabled: boolean;
  site_key: string | null;
}

export default async function ForgotPasswordPage() {
  let turnstile: TurnstileConfig = { enabled: false, site_key: null };
  try {
    turnstile = await apiServer<TurnstileConfig>("/api/v2/auth/turnstile");
  } catch {
    // CAPTCHA config alınamazsa CAPTCHA'sız devam
  }
  return (
    <main className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex justify-center">
          <BrandLogo href="/" />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Şifremi unuttum</CardTitle>
            <CardDescription>
              Hesabınızın e-posta adresini girin. Kayıtlıysa, şifrenizi yenilemeniz
              için bir bağlantı göndereceğiz.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ForgotPasswordForm
              turnstileEnabled={turnstile.enabled}
              turnstileSiteKey={turnstile.site_key}
            />
          </CardContent>
        </Card>
        <p className="text-center text-sm text-muted-foreground">
          <Link href="/login" className="underline hover:text-foreground">
            Girişe dön
          </Link>
        </p>
      </div>
    </main>
  );
}
