import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Next.js 16 proxy (eski adı: middleware) — cookie varlığını kontrol et +
 * protected path'leri /login'e yönlendir.
 *
 * NOT: JWT'yi DECODE ETMEZ. Cookie HttpOnly, JS'den okunmaz. Proxy sadece
 * **varlık** kontrolü yapar; gerçek yetki backend dependency'sinde
 * (`app/routes/api_v2/dependencies.py:get_current_user_v2`). Defense in depth.
 *
 * BFF cookie isimleri (production .env'de __Host- prefix kazandırılabilir):
 *   __Host-access / lgs_access     — short-lived
 *   __Host-refresh / lgs_refresh   — long-lived (path-scoped, burada görünmez)
 *
 * GEÇİŞ DÖNEMİ FALLBACK: Strangler Fig prensibi — Starlette SessionMiddleware
 * "session" cookie'si de kabul edilir; Jinja akışından gelen kullanıcı kapı
 * dışında kalmaz.
 */

const PUBLIC_PATHS_EXACT = new Set<string>([
  "/",            // splash / preview — anonim giriş kapısı
  "/pricing",     // public üyelik/fiyat sayfası
]);

const PUBLIC_PATHS_PREFIX = [
  "/login",
  "/signup",
  // Şifre sıfırlama akışı: token ile gelir, oturum yok — public olmalı.
  // /password/change AYRI (auth gerekir, must_change flow), bu listede YOK.
  "/password/forgot",
  "/password/reset",
  "/verify-email",          // /verify-email/<token> — token ile gelir, anonim
  "/parent/invitation",     // /parent/invitation/<token> — veli davet linki, anonim
  "/parent/unsubscribe",    // /parent/unsubscribe/<token> — bildirim mailindeki çıkış
  "/offers",
  "/pricing",
  "/kvkk",
  "/privacy",
  "/legal",
];

// BFF cookie + geçiş dönemi Jinja session cookie — herhangi biri yeterli.
// Production'da settings.auth_cookie_access_name = "__Host-access" olur.
const COOKIE_NAMES = ["__Host-access", "lgs_access", "session"];

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Static + API + healthz middleware'e gelmemeli zaten (matcher süzüyor),
  // güvenlik için yine de erken çıkış:
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/") ||
    pathname === "/favicon.ico" ||
    pathname === "/healthz"
  ) {
    return NextResponse.next();
  }

  // Statik public dosyalar (logo, görseller, fontlar) — auth'suz serve edilir.
  // Aksi halde anonim ziyaretçide /etutkoc-logo.svg gibi varlıklar /login'e
  // 307 redirect olur ve kırık görsel olarak görünür.
  if (/\.(?:svg|png|jpe?g|gif|webp|avif|ico|txt|xml|json|webmanifest|woff2?|ttf|otf|map)$/i.test(pathname)) {
    return NextResponse.next();
  }

  // Public path'ler proxy'yi atlar (login, davet linkleri, KVKK)
  if (PUBLIC_PATHS_EXACT.has(pathname)) {
    return NextResponse.next();
  }
  if (PUBLIC_PATHS_PREFIX.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }

  // Cookie varlığı kontrolü
  const hasAuth = COOKIE_NAMES.some((name) => req.cookies.has(name));
  if (!hasAuth) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("returnUrl", pathname + req.nextUrl.search);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Static + API + healthz hariç tüm sayfalar
    "/((?!_next/static|_next/image|favicon.ico|api|healthz).*)",
  ],
};
