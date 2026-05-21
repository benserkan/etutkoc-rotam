"use client";

import * as React from "react";

/**
 * Tema sağlayıcı — light/dark/system geçişi.
 *
 * Karar (kullanıcı onaylı, 2026-05-18): default = "light",
 * enableSystem = true. Eğitim/planlama araçları ağırlıklı gündüz
 * kullanıldığı için aydınlık mod birincil.
 *
 * Next.js 16 + React 19 Turbopack uyumsuzluğu yüzünden `next-themes`
 * yerine minimum kendi Context'imiz: FOUC önleme `app/layout.tsx`
 * <head> içindeki inline script ile çözülür (Server Component, problem yok).
 * Bu Context yalnız client tarafında tercih saklamak + Sonner gibi
 * tüketicilere `resolvedTheme` vermek için.
 */
export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "lgs-theme";

interface ThemeCtx {
  theme: Theme;
  setTheme: (t: Theme) => void;
  resolvedTheme: ResolvedTheme;
}

const Ctx = React.createContext<ThemeCtx | null>(null);

function readSavedTheme(): Theme {
  if (typeof window === "undefined") return "system";
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    // localStorage erişilemez (private mode vs.)
  }
  return "system";
}

function applyClass(t: ResolvedTheme) {
  const root = document.documentElement;
  root.classList.remove("light", "dark");
  root.classList.add(t);
  root.style.colorScheme = t;
}

function subscribeSystem(callback: () => void): () => void {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getSystemDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = React.useState<Theme>(() => readSavedTheme());
  // External browser store — React 19 set-state-in-effect kuralına uygun
  const systemDark = React.useSyncExternalStore(
    subscribeSystem,
    getSystemDark,
    () => false,                       // SSR snapshot — light kabul et
  );

  // Derived — state mutasyonu yok, effect lint kuralına uygun
  const resolvedTheme: ResolvedTheme =
    theme === "system" ? (systemDark ? "dark" : "light") : theme;

  // DOM class'ını uygula (FOUC önleme inline script ilk render'da yapıyor;
  // bu yalnız sonraki tema değişimleri için)
  React.useEffect(() => {
    applyClass(resolvedTheme);
  }, [resolvedTheme]);

  const setTheme = React.useCallback((t: Theme) => {
    setThemeState(t);
    try {
      window.localStorage.setItem(STORAGE_KEY, t);
    } catch {
      // ignore
    }
  }, []);

  const value = React.useMemo<ThemeCtx>(
    () => ({ theme, setTheme, resolvedTheme }),
    [theme, setTheme, resolvedTheme],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const v = React.useContext(Ctx);
  if (!v) {
    // Provider olmadan da çalışsın (test/storybook için)
    return {
      theme: "system",
      setTheme: () => {},
      resolvedTheme: "light",
    };
  }
  return v;
}
