/**
 * Server Component'lerde kullanılan fetch yardımcısı.
 *
 * Rewrites (next.config.ts) sadece TARAYICI → Next.js akışında çalışır;
 * Server Component'ler Node runtime'da, doğrudan FastAPI'ye gider.
 * Bu yüzden:
 *   - URL: INTERNAL_API_URL'den okunur (http://127.0.0.1:8081 dev, http://web:8000 prod)
 *   - Cookie: tarayıcının gönderdiği cookie header'ı el ile forward edilir
 *   - Cache: no-store (R-007 — bayatlama yasak)
 *
 * Hata: ApiError fırlatır (lib/api.ts ile birebir aynı şekil).
 */
import { cookies } from "next/headers";
import { ApiError, type ApiErrorDetail } from "@/lib/api";

const INTERNAL = process.env.INTERNAL_API_URL || "http://127.0.0.1:8081";

type ServerApiOptions = Omit<RequestInit, "cache" | "credentials">;

export async function apiServer<T>(path: string, opts: ServerApiOptions = {}): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const r = await fetch(`${INTERNAL}${path}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      cookie: cookieHeader,
      ...(opts.headers ?? {}),
    },
    ...opts,
  });

  if (!r.ok) {
    let detail: ApiErrorDetail = {
      error: "unknown",
      message: `Beklenmeyen yanıt: HTTP ${r.status}`,
    };
    try {
      const body = await r.json();
      if (body?.detail && typeof body.detail === "object") {
        detail = body.detail as ApiErrorDetail;
      } else if (typeof body?.detail === "string") {
        detail = { error: "error", message: body.detail };
      }
    } catch {
      // body JSON değil
    }
    throw new ApiError(r.status, detail);
  }

  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}
