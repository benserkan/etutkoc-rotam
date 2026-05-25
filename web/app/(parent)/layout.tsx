import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { MyAccountResponse } from "@/lib/types/me";
import { roleHome } from "@/lib/role-home";
import { ParentShell } from "@/components/parent/parent-shell";

/**
 * /(parent)/* — Veli paneli korumalı layout.
 *
 * Defense-in-depth: backend `_require_parent` zaten 403 atar; bu layout
 * boş sayfa yerine kullanıcıyı doğru hedefe yönlendirir.
 *
 * R-007: cache: "no-store" + dynamic = "force-dynamic" — App Router cache yok.
 */
export const dynamic = "force-dynamic";

export default async function ParentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let data: MyAccountResponse;
  try {
    data = await apiServer<MyAccountResponse>("/api/v2/me");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect("/login?returnUrl=" + encodeURIComponent("/parent"));
    }
    throw e;
  }

  const role = data.user.role;
  if (role !== "parent") {
    redirect(roleHome(role));
  }

  return <ParentShell user={data.user}>{children}</ParentShell>;
}
