import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { MyAccountResponse } from "@/lib/types/me";
import { roleHome } from "@/lib/role-home";
import { SiteHeader } from "@/components/site-header";
import { PhoneVerifyBanner } from "@/components/me/phone-verify-banner";
import { ImpersonationBanner } from "@/components/impersonation-banner";

/**
 * /student/* için korumalı layout.
 *
 * R-007 sözleşmesi: tüm child sayfalar her istekte taze render edilir.
 * Cache: no-store + dynamic = "force-dynamic" — App Router cache yok.
 *
 * Server-side oturum kontrolü:
 *   - 401/403 → /login?returnUrl=<orig>
 *   - role != "student" → /me/account (öğrenci olmayan kullanıcı kendi paneline)
 *
 * Yalnız oturumu olan ve rolü STUDENT olan kullanıcı geçer. Backend
 * `_require_student` kapısı zaten her endpoint'te 403 atar — bu layout
 * defense-in-depth: kullanıcıyı boş sayfa yerine doğru hedefe yönlendirir.
 */
export const dynamic = "force-dynamic";

export default async function StudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let data: MyAccountResponse;
  try {
    data = await apiServer<MyAccountResponse>("/api/v2/me");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect("/login?returnUrl=" + encodeURIComponent("/student/day"));
    }
    throw e;
  }

  if (data.user.role !== "student") {
    redirect(roleHome(data.user.role));
  }

  return (
    <div className="min-h-screen bg-background">
      <SiteHeader user={data.user} />
      <ImpersonationBanner />
      <PhoneVerifyBanner phoneVerified={data.user.phone_verified ?? true} />
      <main className="mx-auto max-w-6xl px-4 py-6 sm:py-8">{children}</main>
    </div>
  );
}
