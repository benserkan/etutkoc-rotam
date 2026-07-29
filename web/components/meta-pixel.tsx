"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

/**
 * Meta (Facebook/Instagram) pikseli — YALNIZ pazarlama sayfalarında.
 *
 * NEDEN ALLOWLIST (KVKK): piksel, Plausible'ın aksine kişisel veri işler
 * (tarayıcı parmak izi + ziyaret edilen URL Meta'ya gider). Panel içi
 * yollar (`/teacher/students/228` gibi) öğrenci/veli bağlamı taşır →
 * Meta'ya ASLA gitmemeli. Token'lı linkler (`/membership/<token>`,
 * `/offers/<token>`) de dışarıda: URL'de token var, sızdırılmaz.
 *
 * Bu yüzden piksel bir "izin listesi" ile çalışır: yalnız aşağıdaki
 * anonim pazarlama sayfalarında ateşlenir. Yeni bir public pazarlama
 * sayfası eklenirse listeye de eklenmelidir.
 *
 * Kapalı kalması için `META_PIXEL_ID` boş bırakılır (script hiç basılmaz).
 */

const MARKETING_EXACT = new Set(["/", "/pricing", "/iletisim", "/demos"]);
const MARKETING_PREFIX = ["/signup"];

export function isMarketingPath(pathname: string): boolean {
  if (MARKETING_EXACT.has(pathname)) return true;
  return MARKETING_PREFIX.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

type Fbq = (...args: unknown[]) => void;

function getFbq(): Fbq | null {
  if (typeof window === "undefined") return null;
  const fbq = (window as unknown as { fbq?: Fbq }).fbq;
  return typeof fbq === "function" ? fbq : null;
}

/**
 * Dönüşüm olayı gönder (Lead, CompleteRegistration, ViewContent...).
 * Piksel kapalıysa veya reklam engelleyici script'i düşürdüyse sessizce
 * hiçbir şey yapmaz — çağıran taraf try/catch yazmak zorunda değil.
 */
export function trackMetaEvent(name: string, params?: Record<string, unknown>): void {
  const fbq = getFbq();
  if (!fbq) return;
  try {
    fbq("track", name, params ?? {});
  } catch {
    /* ölçüm asla akışı bozmaz */
  }
}

function injectPixel(pixelId: string): void {
  if (getFbq()) return;
  const w = window as unknown as Record<string, unknown>;
  const n = function (...args: unknown[]) {
    const self = n as unknown as {
      callMethod?: (...a: unknown[]) => void;
      queue: unknown[];
    };
    if (self.callMethod) self.callMethod(...args);
    else self.queue.push(args);
  } as unknown as {
    (...args: unknown[]): void;
    push: unknown;
    loaded: boolean;
    version: string;
    queue: unknown[];
  };
  n.push = n;
  n.loaded = true;
  n.version = "2.0";
  n.queue = [];
  w.fbq = n;
  if (!w._fbq) w._fbq = n;

  const s = document.createElement("script");
  s.async = true;
  s.src = "https://connect.facebook.net/en_US/fbevents.js";
  document.head.appendChild(s);

  (n as unknown as Fbq)("init", pixelId);
}

export function MetaPixel({ pixelId }: { pixelId: string }) {
  const pathname = usePathname();
  const injected = useRef(false);

  useEffect(() => {
    if (!pixelId) return;
    if (!isMarketingPath(pathname)) return;

    if (!injected.current) {
      injectPixel(pixelId);
      injected.current = true;
    }
    const fbq = getFbq();
    if (fbq) fbq("track", "PageView");
  }, [pixelId, pathname]);

  return null;
}
