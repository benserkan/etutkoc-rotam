import { apiServer } from "@/lib/api-server";
import type { PricingCatalog } from "@/lib/types/pricing";
import { PricingClient } from "@/components/pricing/pricing-client";

/**
 * /pricing — public üyelik/fiyat sayfası. Tek kaynak: /api/v2/pricing.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Fiyatlar ve Paketler — Öğrenci Koçluğu Programı",
  description:
    "Etütkoç Rotam paketleri: 3 öğrenciye kadar ücretsiz, bağımsız koçlar için Patika, Rota ve Zirve; etüt merkezi, dershane ve özel okullara kuruma özel teklif. 14 gün ücretsiz deneme.",
  alternates: { canonical: "/pricing" },
};

interface TurnstileConfig {
  enabled: boolean;
  site_key: string | null;
}

export default async function PricingPage({
  searchParams,
}: {
  searchParams: Promise<{ type?: string }>;
}) {
  let turnstile: TurnstileConfig = { enabled: false, site_key: null };
  const [catalog, sp] = await Promise.all([
    apiServer<PricingCatalog>("/api/v2/pricing"),
    searchParams,
  ]);
  try {
    turnstile = await apiServer<TurnstileConfig>("/api/v2/auth/turnstile");
  } catch {
    // CAPTCHA config alınamazsa CAPTCHA'sız devam (form yine çalışır)
  }
  return (
    <PricingClient
      catalog={catalog}
      initialType={sp.type ?? ""}
      turnstileEnabled={turnstile.enabled}
      turnstileSiteKey={turnstile.site_key}
    />
  );
}
