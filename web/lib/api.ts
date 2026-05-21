/**
 * api.ts — Tüm /api/v2 çağrılarının tek geçit noktası.
 *
 * KIRMIZI ÇİZGİLER (MIGRATION_RISKS R-007):
 *   1. `cache: "no-store"` default — App Router cache bayatlama yasak.
 *   2. `credentials: "include"` — BFF cookie taşı (Dalga 0 sonu).
 *   3. 401 → bir kez refresh dene (BFF route üzerinden) → orijinal isteği tekrarla.
 *   4. Tüm hatalar `ApiError` ile — `detail.code` makine, `detail.message` insan.
 *
 * `app/routes/api_v2/dependencies.py:_auth_error` ile birebir uyumlu hata zarfı.
 */

const PUBLIC_BASE = process.env.NEXT_PUBLIC_PUBLIC_API_URL ?? "";

export interface ApiErrorDetail {
  error: string;
  code?: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail: ApiErrorDetail;

  constructor(status: number, detail: ApiErrorDetail) {
    super(detail?.message ?? `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }

  /** Yetki dışı hatalar — middleware'in yakalayacağı durumlar. */
  get isAuth(): boolean {
    return this.status === 401 || this.status === 403;
  }
}

type ApiOptions = RequestInit & {
  /** İç tekrar mekanizması için — manuel `true` set etmeyin. */
  _skipRefresh?: boolean;
  /** Yarı-statik yarı-statik veri için açık opt-in (örn. plan kataloğu). */
  revalidateSeconds?: number;
  /** JSON yerine `Response` döndür — file/stream tüketimi için. */
  raw?: boolean;
};

function buildUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${PUBLIC_BASE}${path}`;
}

async function parseError(r: Response): Promise<ApiError> {
  let detail: ApiErrorDetail = {
    error: "unknown",
    message: `Beklenmeyen yanıt: HTTP ${r.status}`,
  };
  try {
    const body = await r.json();
    // FastAPI HTTPException: {"detail": {...}}
    if (body?.detail && typeof body.detail === "object") {
      detail = body.detail as ApiErrorDetail;
    } else if (typeof body?.detail === "string") {
      detail = { error: "error", message: body.detail };
    }
  } catch {
    // body JSON değil — default detail kullanılır
  }
  return new ApiError(r.status, detail);
}

/**
 * Tipik kullanım:
 *   const me = await api<MyAccountResponse>("/api/v2/me");
 *   const res = await api<MutationResponse<X>>("/api/v2/foo", { method: "POST", body: JSON.stringify(...) });
 */
export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const { _skipRefresh, revalidateSeconds, raw, ...init } = opts;

  // Cache stratejisi: default no-store; revalidateSeconds verilirse Next.js cache aç.
  const cache: RequestCache | undefined = revalidateSeconds === undefined ? "no-store" : undefined;
  const next = revalidateSeconds !== undefined ? { revalidate: revalidateSeconds } : undefined;

  const r = await fetch(buildUrl(path), {
    cache,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
    next,
    ...init,
  });

  // 401 → cookie expired olabilir; refresh deneyip tekrar dene.
  if (r.status === 401 && !_skipRefresh) {
    const refreshed = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
    if (refreshed.ok) {
      return api<T>(path, { ...opts, _skipRefresh: true });
    }
    // Refresh de başarısız → orijinal 401'i fırlat (middleware /login'e yönlendirir)
  }

  if (!r.ok) {
    throw await parseError(r);
  }

  if (raw) {
    return r as unknown as T;
  }

  // 204 No Content
  if (r.status === 204) {
    return undefined as T;
  }

  return r.json() as Promise<T>;
}

/** Tip yardımcısı — backend MutationResponse zarfı (API_CONTRACTS_DRAFT §0.3). */
export interface MutationResponse<T> {
  data: T;
  invalidate: string[];
}
