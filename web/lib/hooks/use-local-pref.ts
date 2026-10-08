"use client";

/**
 * Tarayıcıda saklanan küçük tercih (localStorage, JSON) — 2026-10-08.
 *
 * `use-section-prefs` deseni: `useSyncExternalStore` (sunucu snapshot'ı =
 * varsayılan → hydration uyuşmazlığı yok, effect'te setState yok). Okuma/yazma
 * try/catch: depolama yoksa varsayılan değerle çalışır.
 */

import { useCallback, useSyncExternalStore } from "react";

const listeners = new Set<() => void>();
const cache = new Map<string, { raw: string; value: unknown }>();

function emit(): void {
  for (const l of listeners) l();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function readRaw(key: string): string {
  try {
    return window.localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function readValue<T>(key: string, fallback: T): T {
  const raw = readRaw(key);
  const hit = cache.get(key);
  if (hit && hit.raw === raw) return hit.value as T;
  let value: T = fallback;
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as unknown;
      // Eksik alanlar varsayılandan tamamlanır (eski kayıtlar bozulmasın).
      value =
        fallback !== null && typeof fallback === "object" && !Array.isArray(fallback)
          ? ({ ...(fallback as object), ...(parsed as object) } as T)
          : (parsed as T);
    } catch {
      value = fallback;
    }
  }
  cache.set(key, { raw, value });
  return value;
}

export function useLocalPref<T>(key: string, fallback: T): [T, (next: T) => void] {
  const value = useSyncExternalStore(
    subscribe,
    () => readValue(key, fallback),
    () => fallback,
  );
  const set = useCallback(
    (next: T) => {
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // depolama yok — oturum içinde de değişmez; kabul edilebilir
      }
      emit();
    },
    [key],
  );
  return [value, set];
}
