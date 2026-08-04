import type { Metadata } from "next";

import { LandingClient } from "@/components/landing/landing-client";

/**
 * Hero v2 önizlemesi (2026-08-05) — "Rota iş başında" tasarımının canlı
 * değerlendirme sayfası. Anasayfa DEĞİŞMEDİ; beğenilirse LandingClient
 * varsayılanı v2'ye alınıp bu sayfa kaldırılır. Menülerde link YOK (yalnız
 * adresi bilen görür); arama motorlarına kapalı.
 */
export const metadata: Metadata = {
  title: "Hero önizleme — Rotam",
  robots: { index: false, follow: false },
};

export default function HeroPreviewPage() {
  return <LandingClient heroVariant="v2" />;
}
