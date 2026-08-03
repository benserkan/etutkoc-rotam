import { apiServer } from "@/lib/api-server";
import type { PricingAdminResponse } from "@/lib/types/admin";
import { AdminPricingClient } from "@/components/admin/admin-pricing-client";
import { AdminPricingContentClient } from "@/components/admin/admin-pricing-content-client";

/**
 * /admin/pricing — süper admin üyelik/fiyat düzenleme (tek kaynak override).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Ücretlendirme — Süper Admin" };

export default async function AdminPricingPage() {
  const data = await apiServer<PricingAdminResponse>("/api/v2/admin/settings/pricing");
  return (
    <div className="space-y-6">
      <AdminPricingClient initial={data} />
      <div className="mx-auto max-w-3xl px-4 pb-6 sm:px-6">
        <AdminPricingContentClient />
      </div>
    </div>
  );
}
