import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { QueryProvider } from "@/components/query-provider";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

// Türkçe karakter için latin-ext zorunlu.
const inter = Inter({
  subsets: ["latin", "latin-ext"],
  variable: "--font-inter",
  display: "swap",
});

const display = Plus_Jakarta_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "ETÜTKOÇ",
    template: "%s · ETÜTKOÇ",
  },
  description: "Çalışma takip ve planlama sistemi",
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
 * FOUC önleme — tema class'ını React hydrate olmadan önce <html>'e basar.
 * Server Component'te <script> sorun çıkarmaz (Next.js 16 React 19 uyumsuzluğu
 * yalnız Client Component içinde render edilen script'lerde tetikleniyor).
 *
 * try/catch içinde — localStorage erişilemezse (private mode) light'a düşer.
 */
const THEME_INIT_SCRIPT = `
(function(){try{
  var s=localStorage.getItem('lgs-theme');
  var sys=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches;
  var t=(s==='dark'||s==='light')?s:(s==='system'?(sys?'dark':'light'):(sys?'dark':'light'));
  var r=document.documentElement;
  r.classList.remove('light','dark');
  r.classList.add(t);
  r.style.colorScheme=t;
}catch(e){
  document.documentElement.classList.add('light');
}})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Plausible (self-host) — gizlilik-dostu, çerezsiz site analitiği. Script
  // ANA alan adından sunulur (Caddy /js/script.js → plausible) = first-party
  // → reklam engelleyiciler engellemez + KVKK (kişisel veri yok). Runtime env;
  // PLAUSIBLE_DOMAIN tanımlı değilse hiç basılmaz (kapalı kalır).
  const plausibleDomain = process.env.PLAUSIBLE_DOMAIN || "";
  const plausibleSrc = process.env.PLAUSIBLE_SRC || "/js/script.js";

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
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
