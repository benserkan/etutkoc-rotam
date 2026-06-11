import * as React from "react";
import { AppState } from "react-native";
import { useGlobalSearchParams, usePathname } from "expo-router";

import { mobilePathToCatalogPath, postPanelVisits } from "@/lib/quick-access";

/**
 * PanelVisitTracker — authed layout'a takılan sessiz ekran-ziyaret izleyici
 * (web'deki usePanelVisitTracker'ın mobil karşılığı, QA-3).
 *
 * Ekranda ≥3 sn kalış ziyaret sayılır; olaylar 30 sn'de bir toplu gönderilir;
 * uygulama arka plana inerken kalan olaylar uçurulur. Mobil ekran adları
 * burada DEĞİL — lib/quick-access.ts eşleme tablosunda katalog path'ine
 * çevrilir; eşleşmeyen ekran hiç sayılmaz. Hatalar sessizce yutulur
 * (telemetri kullanıcıyı asla rahatsız etmez).
 */

const MIN_DWELL_MS = 3_000;
const FLUSH_INTERVAL_MS = 30_000;
const MAX_BUFFER = 50;

interface CurrentScreen {
  catalogPath: string;
  enteredAt: number;
  recorded: boolean;
}

export function PanelVisitTracker() {
  const pathname = usePathname();
  const params = useGlobalSearchParams();
  const bufferRef = React.useRef<{ path: string; dwell_ms: number }[]>([]);
  const currentRef = React.useRef<CurrentScreen | null>(null);

  const closeCurrent = () => {
    const cur = currentRef.current;
    if (!cur || cur.recorded) return;
    const dwell = Date.now() - cur.enteredAt;
    if (dwell < MIN_DWELL_MS) return;
    if (bufferRef.current.length < MAX_BUFFER) {
      bufferRef.current.push({ path: cur.catalogPath, dwell_ms: dwell });
    }
    cur.recorded = true;
  };

  const catalogPath = mobilePathToCatalogPath(pathname, params);

  React.useEffect(() => {
    closeCurrent();
    currentRef.current = catalogPath
      ? { catalogPath, enteredAt: Date.now(), recorded: false }
      : null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalogPath]);

  React.useEffect(() => {
    const flush = () => {
      closeCurrent();
      const events = bufferRef.current.splice(0);
      if (events.length === 0) return;
      postPanelVisits(events).catch(() => {
        /* telemetri — sessiz */
      });
    };
    const interval = setInterval(flush, FLUSH_INTERVAL_MS);
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "background" || state === "inactive") flush();
    });
    return () => {
      clearInterval(interval);
      sub.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
