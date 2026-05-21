/**
 * BFF refresh route — tarayıcının lib/api.ts'sinden çağrılır.
 *
 * Sorumluluk:
 *   1. Tarayıcının cookie'lerini (refresh dahil) FastAPI'ye taşı
 *   2. FastAPI'nin yeni Set-Cookie'lerini tarayıcıya pas geç
 *   3. Refresh başarısızsa 401 dön → lib/api.ts /login'e yönlendirir
 *
 * Production'da Caddy `/api/v2/*` zaten FastAPI'ye gönderiyor; bu route da
 * aynı işi yapardı ama BFF deseni dokümante etmek + ileride extra logic
 * (örn. otomatik logout + redirect) eklemek için var.
 */

const INTERNAL = process.env.INTERNAL_API_URL || "http://127.0.0.1:8081";

export async function POST(req: Request) {
  const cookie = req.headers.get("cookie") ?? "";

  const upstream = await fetch(`${INTERNAL}/api/v2/auth/refresh`, {
    method: "POST",
    headers: {
      cookie,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  // FastAPI'nin Set-Cookie header'larını bire bir pas geç
  const headers = new Headers();
  // Node 22+ getSetCookie() destekli — varsa onu kullan, yoksa raw header
  const setCookies =
    typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : upstream.headers.get("set-cookie")
        ? [upstream.headers.get("set-cookie") as string]
        : [];
  for (const c of setCookies) headers.append("set-cookie", c);

  const contentType = upstream.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers,
  });
}
