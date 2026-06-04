import { storageDelete, storageGet, storageSet } from "./storage";

/**
 * API istemcisi — ETÜTKOÇ FastAPI backend (/api/v2), JWT Bearer ile.
 *
 * Web ile AYNI backend + veritabanı; yalnız auth kanalı farklı (web cookie,
 * mobil Bearer). Token'lar secure-store'da. 401'de bir kez refresh denenir.
 */
export const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE?.replace(/\/$/, "") || "https://rotam.etutkoc.com";

const ACCESS_KEY = "etk_access_token";
const REFRESH_KEY = "etk_refresh_token";

export async function setTokens(access: string, refresh?: string | null): Promise<void> {
  await storageSet(ACCESS_KEY, access);
  if (refresh) await storageSet(REFRESH_KEY, refresh);
}
export async function clearTokens(): Promise<void> {
  await storageDelete(ACCESS_KEY);
  await storageDelete(REFRESH_KEY);
}
export async function getAccessToken(): Promise<string | null> {
  return storageGet(ACCESS_KEY);
}
export async function getRefreshToken(): Promise<string | null> {
  return storageGet(REFRESH_KEY);
}

export class ApiError extends Error {
  status: number;
  code: string;
  data: unknown;
  constructor(status: number, code: string, message: string, data?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean; // Bearer ekle (default true)
}

async function rawRequest(path: string, opts: RequestOptions, token: string | null): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (opts.auth !== false && token) headers["authorization"] = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
}

let refreshInflight: Promise<string | null> | null = null;

async function refreshAccess(): Promise<string | null> {
  if (refreshInflight) return refreshInflight;
  refreshInflight = (async () => {
    const refresh = await getRefreshToken();
    if (!refresh) return null;
    try {
      const res = await fetch(`${API_BASE}/api/v2/auth/token/refresh`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) {
        await clearTokens();
        return null;
      }
      const data = (await res.json()) as { access_token?: string };
      if (data.access_token) {
        await storageSet(ACCESS_KEY, data.access_token);
        return data.access_token;
      }
      return null;
    } catch {
      return null;
    } finally {
      refreshInflight = null;
    }
  })();
  return refreshInflight;
}

export async function apiRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const access = await getAccessToken();
  let res = await rawRequest(path, opts, access);

  // 401 + refresh token varsa bir kez yenile, tekrar dene (login gibi auth:false hariç)
  if (res.status === 401 && opts.auth !== false && (await getRefreshToken())) {
    const newAccess = await refreshAccess();
    if (newAccess) res = await rawRequest(path, opts, newAccess);
  }

  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const detail = (data as { detail?: unknown })?.detail ?? data;
    const code =
      (detail as { code?: string })?.code ?? `http_${res.status}`;
    const message =
      (detail as { message?: string })?.message ??
      (typeof detail === "string" ? detail : "Bir hata oluştu.");
    throw new ApiError(res.status, code, message, data);
  }
  return data as T;
}
