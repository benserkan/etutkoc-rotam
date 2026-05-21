/**
 * Public landing fetcher + telemetri beacon.
 *
 * Kartlar A/B sıralı (feature_catalog) + variant_slug telemetriye taşınır.
 * Telemetri: navigator.sendBeacon (varsa) → fire-and-forget fetch fallback.
 * Anon session cookie (fc_sid) backend tarafından set edilir; aynı origin
 * (Caddy/dev rewrite) olduğu için cookie otomatik taşınır.
 */
import { api } from "@/lib/api";
import type { LandingResponse } from "@/lib/types/landing";

export const landingKeys = {
  cards: (limit: number) => ["landing", "cards", String(limit)] as const,
};

export function getLandingCards(limit = 5): Promise<LandingResponse> {
  return api<LandingResponse>(`/api/v2/landing?limit=${limit}`);
}

export function sendLandingTelemetry(
  slug: string,
  event: string,
  variant: string | null,
): void {
  if (!slug || !event) return;
  const body = JSON.stringify(
    variant ? { slug, event, variant } : { slug, event },
  );
  try {
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon("/api/v2/landing/telemetry", blob);
      return;
    }
  } catch {
    // sendBeacon başarısız → api fallback
  }
  // Fallback (sendBeacon yoksa): fire-and-forget, hata yutulur
  void api<void>("/api/v2/landing/telemetry", {
    method: "POST",
    body,
  }).catch(() => {});
}
