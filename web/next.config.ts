import type { NextConfig } from "next";

/**
 * Next.js config — geliştirme rewrites + production ayarları.
 *
 * Geliştirme akışı:
 *   Tarayıcı → localhost:3000 → Next.js rewrite → localhost:8081 (FastAPI)
 *
 * Bu sayede CORS gerekmiyor (browser her şeyi same-origin görüyor) ve
 * cookie'ler tek origin'de (localhost:3000) tutuluyor.
 *
 * Production'da rewrites çalışmaz; Caddy reverse proxy `/api/*` ve `/webhooks/*`
 * path'lerini doğrudan FastAPI container'ına yönlendirir.
 *
 * BFF route'ları (`/api/auth/*` — TR: kimlik) Next.js'in KENDİ
 * route'larıdır; rewrite EDİLMEZ.
 */
const nextConfig: NextConfig = {
  output: "standalone",  // Docker multi-stage build için

  async rewrites() {
    const apiTarget = process.env.INTERNAL_API_URL || "http://127.0.0.1:8081";
    return [
      // BFF Next.js route'larını rewrite ETME — bunlar Next.js'te kalır
      // /api/auth/refresh — özel BFF route'u (route.ts dosyası)

      // FastAPI'ye giden API katmanları
      { source: "/api/v1/:path*", destination: `${apiTarget}/api/v1/:path*` },
      { source: "/api/v2/:path*", destination: `${apiTarget}/api/v2/:path*` },

      // Webhooks (Meta WhatsApp callback) ve health probe FastAPI'de
      { source: "/webhooks/:path*", destination: `${apiTarget}/webhooks/:path*` },
      { source: "/healthz", destination: `${apiTarget}/healthz` },

      // Hibrit kalıcı: KVKK, legal, email/print sayfaları FastAPI Jinja
      { source: "/kvkk", destination: `${apiTarget}/kvkk` },
      { source: "/privacy", destination: `${apiTarget}/privacy` },
      { source: "/legal/:path*", destination: `${apiTarget}/legal/:path*` },
      // Landing "Demo İzle" linki — /demos Jinja'da kalır (dev'de de çalışsın)
      { source: "/demos", destination: `${apiTarget}/demos` },

      // Henüz v2'ye taşınmamış print sayfaları (Jinja'da kalan)
      // /student/week/print → Next.js'in kendisi (Paket 7 sonrası)
      // /student/weekly-report/print → Jinja (yarın v2'ye taşınacak)
      // /institution/.../print → Jinja
      { source: "/student/weekly-report/print", destination: `${apiTarget}/student/weekly-report/print` },
      { source: "/institution/cohorts/print", destination: `${apiTarget}/institution/cohorts/print` },
      { source: "/institution/at-risk/print", destination: `${apiTarget}/institution/at-risk/print` },
      { source: "/institution/activity-heatmap/print", destination: `${apiTarget}/institution/activity-heatmap/print` },

      // Jinja /login akışı geçici olarak FastAPI'de yaşıyor.
      // Next.js /login DALGA 0'da yazıldı; çakışmayı önlemek için bu
      // satırı KALDIRIYORUZ — Next.js kendi /login'ini render eder.
      // Eski Jinja /login'e hâlâ ihtiyaç olursa /jinja-login üzerinden erişilir.
    ];
  },
};

export default nextConfig;
