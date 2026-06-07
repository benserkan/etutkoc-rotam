import { apiServer } from "@/lib/api-server";
import type { PricingCatalog } from "@/lib/types/pricing";
import { IletisimClient } from "@/components/contact/iletisim-client";

/**
 * /iletisim — public iletişim sayfası. Çok kanallı (WhatsApp / telefon / e-posta)
 * + profesyonel form (Cloudflare Turnstile doğrulamalı → /api/v2/contact).
 * İletişim kanalları tek kaynak: /api/v2/pricing (süper admin panelden ayarlanır).
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "İletişim — ETÜTKOÇ Rotam",
  description:
    "ETÜTKOÇ Rotam ile iletişime geçin: kurumsal teklif, teknik destek ve genel sorular için WhatsApp, telefon, e-posta veya form.",
};

interface TurnstileConfig {
  enabled: boolean;
  site_key: string | null;
}

export default async function IletisimPage({
  searchParams,
}: {
  searchParams: Promise<{ konu?: string }>;
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
    <IletisimClient
      catalog={catalog}
      initialTopic={sp.konu ?? ""}
      turnstileEnabled={turnstile.enabled}
      turnstileSiteKey={turnstile.site_key}
    />
  );
}
