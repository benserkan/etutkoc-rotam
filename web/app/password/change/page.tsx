import { redirect } from "next/navigation";

import { ApiError } from "@/lib/api";
import { apiServer } from "@/lib/api-server";
import { BrandLogo } from "@/components/brand-logo";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PasswordChangeForm } from "./password-change-form";

/**
 * /password/change — zorunlu + isteğe bağlı şifre değiştirme (Dalga 7 P1).
 *
 * Jinja kaynağı: app/routes/password.py + auth/password_change.html.
 * Auth durumu server-side çözülür:
 *   - 200 (/auth/me)      → normal kullanıcı (mevcut şifre zorunlu)
 *   - 403 password_change_required → zorunlu akış (mevcut şifre gizli)
 *   - 401 / diğer         → /login'e yönlendir
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Şifre Değiştir" };

export default async function PasswordChangePage() {
  let isForced = false;
  try {
    await apiServer("/api/v2/auth/me");
  } catch (e) {
    if (
      e instanceof ApiError &&
      e.status === 403 &&
      e.detail?.code === "password_change_required"
    ) {
      isForced = true;
    } else {
      redirect("/login?returnUrl=/password/change");
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex justify-center">
          <BrandLogo href="/" />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{isForced ? "Şifrenizi belirleyin" : "Şifre değiştir"}</CardTitle>
            <CardDescription>
              {isForced
                ? "Hesabınız geçici bir şifreyle oluşturuldu. Devam etmeden önce kendi şifrenizi belirleyin."
                : "Güvenliğiniz için güçlü, başkalarınınkinden farklı bir şifre seçin."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PasswordChangeForm isForced={isForced} />
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
