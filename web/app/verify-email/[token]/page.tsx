import { BrandLogo } from "@/components/brand-logo";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { VerifyEmailClient } from "./verify-client";

/**
 * /verify-email/[token] — e-posta doğrulama (Dalga 7 P3).
 *
 * Sayfa açılınca token otomatik işlenir (POST /api/v2/auth/verify-email/{token}).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "E-posta Doğrulama" };

export default async function VerifyEmailPage({
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
            <CardTitle>E-posta doğrulama</CardTitle>
          </CardHeader>
          <CardContent>
            <VerifyEmailClient token={token} />
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
