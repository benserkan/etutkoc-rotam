import { QueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/lib/api";

/**
 * TanStack Query default'ları.
 *
 * KIRMIZI ÇİZGİLER:
 *   - staleTime=60_000 (1 dk) — kullanıcı tercihi, sekme değişimlerinde
 *     gereksiz istek patlaması olmasın. Mutation'lar invalidate ile
 *     anında refresh tetikler (R-006/R-007).
 *   - refetchOnWindowFocus=false — sekme odakları arasında istek
 *     patlamasını önle (kullanıcı: Paket 5 onayı).
 *   - 401/403 retry YOK — refresh denemesi `lib/api.ts:api()` içinde
 *     tek seferlik. 5xx ve network hataları bir kez retry.
 */
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        gcTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
        retry: (count, err) => {
          const apiErr = err as ApiError | undefined;
          if (apiErr?.status === 401 || apiErr?.status === 403) return false;
          if (apiErr?.status && apiErr.status >= 400 && apiErr.status < 500) return false;
          return count < 1;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}
