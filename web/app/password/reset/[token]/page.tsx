import Link from "next/link";

import { BrandLogo } from "@/components/brand-logo";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ResetPasswordForm } from "./reset-form";

/**
 * /password/reset/[token] — token'lı yeni şifre belirleme (Dalga 7 P2).
 *
 * Token geçerliliği POST sırasında backend'de doğrulanır (get_usable_token);
 * geçersiz/süresi dolmuş token formda invalid_token hatası gösterir.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Şifre Sıfırla" };

export default async function ResetPasswordPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return (
    <main className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex justify-center">
          <BrandLogo href="/" />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Yeni şifre belirleyin</CardTitle>
            <CardDescription>
              Güçlü, başkalarınınkinden farklı bir şifre seçin. Bağlantı tek
              kullanımlıktır ve kısa süre geçerlidir.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ResetPasswordForm token={token} />
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
