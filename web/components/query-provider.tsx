"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { makeQueryClient } from "@/lib/query-client";

/**
 * TanStack Query provider.
 *
 * - SSR güvenli: client ilk render'da bir kez oluşturulur (useState init'i).
 * - Default'lar `lib/query-client.ts` içinde — staleTime=0 (R-007 default).
 * - Devtools yalnız development'ta yüklenir.
 */
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = React.useState<QueryClient>(() => makeQueryClient());
  return (
    <QueryClientProvider client={client}>
      {children}
      {process.env.NODE_ENV !== "production" ? (
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
      ) : null}
    </QueryClientProvider>
  );
}
