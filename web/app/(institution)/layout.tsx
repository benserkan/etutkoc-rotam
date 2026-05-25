import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { MyAccountResponse } from "@/lib/types/me";
import { roleHome } from "@/lib/role-home";
import { InstitutionShell } from "@/components/institution/institution-shell";

/**
 * /(institution)/* — Kurum Yöneticisi paneli korumalı layout.
 *
 * Defense-in-depth:
 *   - Backend `_require_institution_admin` ile zaten 403 atar.
 *   - Bu layout boş sayfa yerine kullanıcıyı doğru hedefe yönlendirir.
 *
 * R-007: cache: "no-store" + dynamic = "force-dynamic" — App Router cache yok.
 */
export const dynamic = "force-dynamic";

export default async function InstitutionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let data: MyAccountResponse;
  try {
    data = await apiServer<MyAccountResponse>("/api/v2/me");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect("/login?returnUrl=" + encodeURIComponent("/institution"));
    }
    throw e;
  }

  const role = data.user.role;
  if (role !== "institution_admin") {
    redirect(roleHome(role));
  }

  return (
    <InstitutionShell user={data.user} institution={data.institution}>
      {children}
    </InstitutionShell>
  );
}
