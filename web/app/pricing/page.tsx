import { apiServer } from "@/lib/api-server";
import type { PricingCatalog } from "@/lib/types/pricing";
import { PricingClient } from "@/components/pricing/pricing-client";

/**
 * /pricing — public üyelik/fiyat sayfası. Tek kaynak: /api/v2/pricing.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Üyelik ve Fiyatlar — ETÜTKOÇ",
  description: "Bağımsız koç ve kurumlar için üyelik planları ve fiyatları.",
};

export default async function PricingPage() {
  const catalog = await apiServer<PricingCatalog>("/api/v2/pricing");
  return <PricingClient catalog={catalog} />;
}
