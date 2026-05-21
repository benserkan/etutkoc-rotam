"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { MyAccountResponse, UserPublic } from "@/lib/types/me";

/**
 * Client-side oturum hook'u.
 *
 * Server Component'ler doğrudan `apiServer<MyAccountResponse>("/api/v2/me")`
 * kullanır; bu hook yalnız client component'lerden çağrılır (örn. SiteHeader,
 * /student/day içindeki interaktif bileşenler).
 *
 * QueryKey: `['session', 'me']` — login sonrası `qc.clear()` çağrısı + Paket 6'da
 * mutation invalidate'leri bu prefix'i tetikleyebilir.
 *
 * staleTime override 5 dk — login session'ı saniyede bir yenilenmesin.
 */
export function useSession() {
  return useQuery<MyAccountResponse>({
    queryKey: ["session", "me"],
    queryFn: () => api<MyAccountResponse>("/api/v2/me"),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

/** Yalnız user objesini almak isteyen bileşenler için kestirme. */
export function useSessionUser(): UserPublic | undefined {
  const q = useSession();
  return q.data?.user;
}
