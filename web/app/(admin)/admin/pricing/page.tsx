import { apiServer } from "@/lib/api-server";
import type { PricingAdminResponse } from "@/lib/types/admin";
import { AdminPricingClient } from "@/components/admin/admin-pricing-client";

/**
 * /admin/pricing — süper admin üyelik/fiyat düzenleme (tek kaynak override).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Ücretlendirme — Süper Admin" };

export default async function AdminPricingPage() {
  const data = await apiServer<PricingAdminResponse>("/api/v2/admin/settings/pricing");
  return <AdminPricingClient initial={data} />;
}
