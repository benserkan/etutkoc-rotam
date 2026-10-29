"use client";

import * as React from "react";

/**
 * Tema sağlayıcı — TEK TEMA.
 *
 * Karar (kullanıcı, 2026-10-29): açık/koyu mod ayrımı kaldırıldı; site her
 * cihazda aynı (açık) temayla açılır. Koyu mod iki kat bakım ve tekrarlayan
 * okunabilirlik hataları üretiyordu. `useTheme` tüketicileri (Sonner) için
 * API korunur ama her zaman "light" döner; `setTheme` etkisizdir.
 */
export type Theme = "light";
export type ResolvedTheme = "light";

interface ThemeCtx {
  theme: Theme;
  setTheme: (t: Theme) => void;
  resolvedTheme: ResolvedTheme;
}

const VALUE: ThemeCtx = { theme: "light", setTheme: () => {}, resolvedTheme: "light" };

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function useTheme(): ThemeCtx {
  return VALUE;
}
