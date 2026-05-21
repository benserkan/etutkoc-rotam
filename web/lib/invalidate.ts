import type { QueryClient } from "@tanstack/react-query";
import type { MutationResponse } from "@/lib/api";

/**
 * MutationResponse.invalidate listesini TanStack Query queryKey'lerine yansıtır.
 *
 * Backend "me:kvkk" gönderirse ['me', 'kvkk'] prefix'iyle başlayan TÜM
 * query'ler geçersiz olur — etkilenen component'ler yeniden çeker.
 *
 * Bu R-006 (HTMX OOB swap kaybı) ve R-007 (cache bayatlama)'nın birincil
 * mekanizmasıdır.
 *
 * Tipik kullanım:
 *   const mut = useMutation({
 *     mutationFn: (id) => api("/api/v2/...", {...}),
 *     onSuccess: (res) => applyInvalidate(qc, res.invalidate),
 *   });
 */
export function applyInvalidate(qc: QueryClient, keys: string[] | undefined): void {
  if (!keys || keys.length === 0) return;
  for (const key of keys) {
    const parts = key.split(":").filter(Boolean);
    if (parts.length === 0) continue;
    // Backend numeric id'leri yazar (`teacher:13:...`, `student:42:...`); frontend
    // tüm "kendi" namespace'leri "me" altında cache'ler (`["teacher","me",...]`).
    // İlk iki segment owner prefix'i ise frontend formuna çevir.
    if (
      parts.length >= 2 &&
      (parts[0] === "teacher" ||
        parts[0] === "student" ||
        parts[0] === "institution") &&
      /^\d+$/.test(parts[1])
    ) {
      parts[1] = "me";
    }
    qc.invalidateQueries({ queryKey: parts });
  }
}

/**
 * Mutation tanımlarken default `onSuccess` üreten yardımcı.
 *
 * Kullanım:
 *   useMutation({
 *     mutationFn: ...,
 *     onSuccess: invalidateOnSuccess(qc),
 *   });
 */
export function invalidateOnSuccess<T>(qc: QueryClient) {
  return (res: MutationResponse<T>) => applyInvalidate(qc, res.invalidate);
}
