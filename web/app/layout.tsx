import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { QueryProvider } from "@/components/query-provider";
import { Toaster } from "@/components/ui/sonner";
import { MetaPixel } from "@/components/meta-pixel";
import { SiteAssistant } from "@/components/assistant/site-assistant";
import { SITE_URL } from "@/lib/site";
import "./globals.css";

// Türkçe karakter için latin-ext zorunlu.
const inter = Inter({
  subsets: ["latin", "latin-ext"],
  variable: "--font-inter",
  display: "swap",
});

const display = Plus_Jakarta_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-jakarta",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: "Etütkoç Rotam",
  title: {
    default: "Etütkoç Rotam — Öğrenci Koçluğu Takip ve Deneme Analizi Sistemi",
    template: "%s | Etütkoç Rotam",
  },
  description:
    "Öğrenci koçları ve etüt merkezleri için takip programı: deneme karnesini konu konu analiz eder, haftalık programı kitaba bağlar, veliyi otomatik bilgilendirir. 14 gün ücretsiz.",
  openGraph: {
    type: "website",
    locale: "tr_TR",
    siteName: "Etütkoç Rotam",
    images: [{ url: "/og-rotam.png", width: 1200, height: 630, alt: "Etütkoç Rotam" }],
  },
  twitter: { card: "summary_large_image", images: ["/og-rotam.png"] },
};

/**
 * KIRMIZI ÇİZGİ — App Router caching agresif kalamaz (MIGRATION_RISKS R-007).
 *
 * Bu layout'un altındaki TÜM sayfalar dinamik render edilir; static cache
 * yok. İstisna yarı-statik sayfalar kendi `export const dynamic` veya
 * `export const revalidate` ile opt-in eder.
 */
export const dynamic = "force-dynamic";

/**
 * Tek tema (2026-10-29 kullanıcı kararı): site cihazın koyu/açık tercihine
 * bakmadan daima açık temada açılır; koyu mod kaldırıldı. Eski kayıtlı
 * "lgs-theme" tercihi yok sayılır. Script, hydrate öncesi <html>'e "light"
 * basar (eski oturumdan kalma "dark" sınıfı varsa siler).
 */
const THEME_INIT_SCRIPT = `
(function(){try{
  var r=document.documentElement;
  r.classList.remove('dark');
  r.classList.add('light');
  r.style.colorScheme='light';
}catch(e){}})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Plausible (self-host) — gizlilik-dostu, çerezsiz site analitiği. Script
  // ANA alan adından sunulur (Caddy /js/script.js → plausible) = first-party
  // → reklam engelleyiciler engellemez + KVKK (kişisel veri yok). Runtime env;
  // PLAUSIBLE_DOMAIN tanımlı değilse hiç basılmaz (kapalı kalır).
  const plausibleDomain = process.env.PLAUSIBLE_DOMAIN || "";
  const plausibleSrc = process.env.PLAUSIBLE_SRC || "/js/script.js";
  // Meta (Facebook/Instagram) pikseli — reklam yeniden hedefleme + dönüşüm
  // ölçümü. Plausible'dan FARKLI: kişisel veri işler → yalnız anonim
  // pazarlama sayfalarında çalışır (bkz. components/meta-pixel.tsx allowlist).
  // META_PIXEL_ID boşsa hiç yüklenmez.
  const metaPixelId = process.env.META_PIXEL_ID || "";

  return (
    <html lang="tr" className={`${inter.variable} ${display.variable}`} suppressHydrationWarning>
      <head>
        <link rel="icon" type="image/png" href="/favicon-96x96.png" sizes="96x96" />
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <link rel="shortcut icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
        <meta name="apple-mobile-web-app-title" content="ETÜTKOÇ" />
        <link rel="manifest" href="/site.webmanifest" />
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        {plausibleDomain ? (
          <script defer data-domain={plausibleDomain} src={plausibleSrc} />
        ) : null}
      </head>
      <body className="min-h-screen bg-background text-foreground font-sans antialiased">
        <ThemeProvider>
          <QueryProvider>
            {children}
            <Toaster />
            {/* Rota — sitenin her yerinde tek yapay zekâ asistanı (ziyaretçi dahil) */}
            <SiteAssistant />
            {metaPixelId ? <MetaPixel pixelId={metaPixelId} /> : null}
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
