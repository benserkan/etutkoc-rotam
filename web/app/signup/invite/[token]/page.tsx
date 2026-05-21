import Link from "next/link";

import { ApiError } from "@/lib/api";
import { apiServer } from "@/lib/api-server";
import { BrandLogo } from "@/components/brand-logo";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SignupInviteForm } from "./signup-invite-form";

/**
 * /signup/invite/[token] — davetiyeli kayıt (Dalga 7 P3).
 *
 * Davet bilgisi server-side çekilir; geçersizse açıklayıcı ekran gösterilir.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Davetiyeli Kayıt" };

interface InvitationInfo {
  valid: boolean;
  status: string;
  email: string | null;
  full_name: string | null;
  role: string | null;
  institution_name: string | null;
}

const STATUS_MESSAGE: Record<string, string> = {
  not_found: "Davetiye bulunamadı. Bağlantıyı doğru kopyaladığınızdan emin olun.",
  expired: "Bu davetiyenin süresi dolmuş. Sizi davet eden kişiden yeni bir bağlantı isteyin.",
  consumed: "Bu davetiye zaten kullanılmış. Hesabınız varsa giriş yapın.",
  revoked: "Bu davetiye iptal edilmiş. Sizi davet eden kişiyle iletişime geçin.",
};

export default async function SignupInvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  let info: InvitationInfo | null = null;
  try {
    info = await apiServer<InvitationInfo>(`/api/v2/auth/signup/invite/${token}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    info = { valid: false, status: "not_found", email: null, full_name: null, role: null, institution_name: null };
  }

  const valid = info?.valid === true;

  return (
    <main className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-1.5">
          <BrandLogo href="/" />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{valid ? "Davetiyeyi tamamla" : "Davetiye geçersiz"}</CardTitle>
            <CardDescription>
              {valid
                ? info?.institution_name
                  ? `${info.institution_name} sizi davet etti. Bilgilerinizi tamamlayın.`
                  : "Davetiyeyi tamamlamak için bilgilerinizi girin."
                : STATUS_MESSAGE[info?.status ?? "not_found"] ?? STATUS_MESSAGE.not_found}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {valid && info ? (
              <SignupInviteForm
                token={token}
                defaultEmail={info.email ?? ""}
                defaultFullName={info.full_name ?? ""}
                role={info.role ?? "teacher"}
              />
            ) : (
              <Link
                href="/login"
                className="inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              >
                Girişe dön
              </Link>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
