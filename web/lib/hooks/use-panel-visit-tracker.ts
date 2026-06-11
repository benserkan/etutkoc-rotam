"use client";

/**
 * usePanelVisitTracker — panel shell'lerine takılan sessiz ziyaret izleyici.
 *
 * Davranış:
 *   - Rota değişimini izler; kullanıcı sayfada ≥3 sn kalırsa ziyaret sayılır
 *     (gelip-geçen/yanlış tıklamalar öğrenmeyi kirletmez).
 *   - Ziyaretler tarayıcıda biriktirilip 30 sn'de bir TOPLU gönderilir —
 *     her tıklamada sunucuya istek yok.
 *   - Sekme gizlenince / sayfa kapanırken kalan olaylar sendBeacon ile uçar.
 *   - Telemetri asla kullanıcıyı rahatsız etmez: gönderim hatası sessizce
 *     yutulur (olaylar düşer, tekrar denenmez).
 *
 * Ham path gönderilir; sunucu rota kataloğu ile normalize eder — katalog
 * dışı sayfalar (token'lı, /payment, /login) hiç sayılmaz.
 */

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

import { postPanelVisits } from "@/lib/api/quick-access";
import type { PanelVisitEventIn } from "@/lib/types/quick-access";

const MIN_DWELL_MS = 3_000;
const FLUSH_INTERVAL_MS = 30_000;
const MAX_BUFFER = 50;

interface CurrentPage {
  path: string;
  enteredAt: number;
  recorded: boolean;
}

export function usePanelVisitTracker(): void {
  const pathname = usePathname();
  const bufferRef = useRef<PanelVisitEventIn[]>([]);
  const currentRef = useRef<CurrentPage | null>(null);

  // Mevcut sayfayı (yeterince kalındıysa) buffer'a yazar — sayfa başına 1 kez.
  const closeCurrent = () => {
    const cur = currentRef.current;
    if (!cur || cur.recorded) return;
    const dwell = Date.now() - cur.enteredAt;
    if (dwell < MIN_DWELL_MS) return;
    if (bufferRef.current.length < MAX_BUFFER) {
      bufferRef.current.push({ path: cur.path, dwell_ms: dwell });
    }
    cur.recorded = true;
  };

  useEffect(() => {
    closeCurrent();
    currentRef.current = { path: pathname, enteredAt: Date.now(), recorded: false };
  }, [pathname]);

  useEffect(() => {
    const flush = () => {
      closeCurrent();
      const events = bufferRef.current.splice(0);
      if (events.length === 0) return;
      postPanelVisits(events).catch(() => {
        /* telemetri — sessiz */
      });
    };

    const flushBeacon = () => {
      closeCurrent();
      const events = bufferRef.current.splice(0);
      if (events.length === 0) return;
      try {
        const blob = new Blob([JSON.stringify({ events })], {
          type: "application/json",
        });
        navigator.sendBeacon("/api/v2/me/panel-visits", blob);
      } catch {
        /* sessiz */
      }
    };

    const interval = window.setInterval(flush, FLUSH_INTERVAL_MS);
    const onVisibility = () => {
      if (document.visibilityState === "hidden") flushBeacon();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", flushBeacon);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", flushBeacon);
    };
  }, []);
}
