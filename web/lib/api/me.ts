/**
 * /api/v2/me + KVKK self-serve sarmalayıcıları.
 *
 * Paket 3.5d.2 — /me sayfası + şifre değiştirme.
 */
import { api } from "@/lib/api";
import type { MyAccountResponse } from "@/lib/types/me";

export const meKeys = {
  account: () => ["me", "account"] as const,
} as const;

export function getMyAccount(): Promise<MyAccountResponse> {
  return api<MyAccountResponse>("/api/v2/me");
}
