import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { MyAccountResponse, UserRole } from "@/lib/types/me";
import { roleHome } from "@/lib/role-home";
import { LandingClient } from "@/components/landing/landing-client";

/**
 * Kök sayfa (/) — public tanıtım vitrini.
 *
 * Jinja parite (app/main.py index()): giriş yapmış kullanıcı rolüne göre
 * panele yönlendirilir; anonim ziyaretçi feature_catalog kartlı landing görür.
 * Kartlar + A/B + telemetri client tarafında (`/api/v2/landing`) yüklenir.
 */
export const dynamic = "force-dynamic";

export default async function HomePage() {
  let role: UserRole | null = null;
  try {
    const me = await apiServer<MyAccountResponse>("/api/v2/me");
    role = me.user.role;
  } catch (e) {
    // 401/403 → anonim ziyaretçi (landing göster); diğer hatalar yukarı fırlar
    if (!(e instanceof ApiError)) throw e;
  }
  // redirect() NEXT_REDIRECT fırlatır → try/catch DIŞINDA çağrılmalı
  if (role) redirect(roleHome(role));

  return <LandingClient />;
}
