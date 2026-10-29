"use client";

/**
 * Cloudflare Turnstile — paylaşılan, sağlam yükleyici.
 *
 * Eski desenin (her formda kopyalanmış Script onLoad + render) sorunları:
 *  - Sayfaya istemci tarafında yeniden gelince script zaten yüklü olduğundan
 *    onLoad tetiklenmiyor → widget hiç çizilmiyor, buton "yükleniyor"da kalıyordu.
 *  - Token süresi (~300 sn) dolunca kullanıcıya bir şey söylenmiyordu; gönderimde
 *    "doğrulama başarısız" çıkıyordu.
 *  - Ağ yavaşsa / engellenmişse sonsuz bekleme; tek çıkış sayfayı yenilemekti.
 *
 * Bu bileşen: script'i bir kez yükler (window düzeyinde tek promise), her mount'ta
 * widget'ı yeniden çizer, token'ı state olarak yukarı verir, süre dolunca otomatik
 * yeniler, 20 sn'de yanıt gelmezse "yeniden dene" sunar (sayfa yenilemeden).
 */
import * as React from "react";
import { Loader2, RefreshCw, ShieldCheck } from "lucide-react";

interface TurnstileApi {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  reset: (id?: string) => void;
  remove: (id?: string) => void;
  getResponse: (id?: string) => string | undefined;
}
declare global {
  interface Window {
    turnstile?: TurnstileApi;
    __rotamTurnstileLoad?: Promise<TurnstileApi>;
  }
}

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const SLOW_MS = 20_000;

function loadTurnstile(): Promise<TurnstileApi> {
  if (typeof window === "undefined") return Promise.reject(new Error("ssr"));
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (window.__rotamTurnstileLoad) return window.__rotamTurnstileLoad;
  window.__rotamTurnstileLoad = new Promise<TurnstileApi>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error("no_api")));
    s.onerror = () => {
      window.__rotamTurnstileLoad = undefined; // sonraki deneme yeniden yüklesin
      s.remove();
      reject(new Error("load_failed"));
    };
    document.head.appendChild(s);
  });
  return window.__rotamTurnstileLoad;
}

export type TurnstileStatus = "loading" | "verifying" | "ready" | "expired" | "error";

interface Props {
  siteKey: string;
  /** Sunucu tarafında doğrulanan eylem adı (login, signup, forgot, contact). */
  action: string;
  onToken: (token: string | null) => void;
  onStatus?: (s: TurnstileStatus) => void;
  theme?: "light" | "dark";
  className?: string;
  /**
   * Artırıldığında widget yeniden çizilir (yeni token). Token tek kullanımlık
   * olduğundan form her gönderim denemesinden sonra bunu artırır; aynı anda
   * kendi token state'ini null'a çeker.
   */
  resetKey?: number;
}

export function TurnstileWidget({
  siteKey,
  action,
  onToken,
  onStatus,
  theme = "light",
  className,
  resetKey = 0,
}: Props) {
  const boxRef = React.useRef<HTMLDivElement | null>(null);
  const widgetIdRef = React.useRef<string | null>(null);
  const [status, setStatusState] = React.useState<TurnstileStatus>("loading");
  const [slow, setSlow] = React.useState(false);
  const [attempt, setAttempt] = React.useState(0);

  // Callback'ler Cloudflare'in içinden çağrılır; en güncel prop'u ref'ten oku.
  const cbRef = React.useRef({ onToken, onStatus });
  React.useEffect(() => {
    cbRef.current = { onToken, onStatus };
  });

  const setStatus = React.useCallback((s: TurnstileStatus) => {
    setStatusState(s);
    cbRef.current.onStatus?.(s);
  }, []);


  React.useEffect(() => {
    let cancelled = false;
    const slowTimer = window.setTimeout(() => {
      if (!cancelled) setSlow(true);
    }, SLOW_MS);

    loadTurnstile()
      .then((ts) => {
        if (cancelled || !boxRef.current) return;
        setStatus("verifying");
        widgetIdRef.current = ts.render(boxRef.current, {
          sitekey: siteKey,
          action,
          theme,
          language: "tr",
          size: "flexible",
          appearance: "always",
          "refresh-expired": "auto",
          "refresh-timeout": "auto",
          retry: "auto",
          callback: (token: string) => {
            window.clearTimeout(slowTimer);
            setSlow(false);
            cbRef.current.onToken(token);
            setStatus("ready");
          },
          "expired-callback": () => {
            cbRef.current.onToken(null);
            setStatus("expired"); // refresh-expired:auto yeniden çözer
          },
          "timeout-callback": () => {
            cbRef.current.onToken(null);
            setStatus("expired");
          },
          "error-callback": () => {
            cbRef.current.onToken(null);
            setStatus("error");
            return true; // hatayı biz gösteriyoruz; konsola düşmesin
          },
          "unsupported-callback": () => setStatus("error"),
        });
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
      window.clearTimeout(slowTimer);
      if (window.turnstile && widgetIdRef.current) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          /* zaten kaldırılmış */
        }
      }
      widgetIdRef.current = null;
    };
  }, [siteKey, action, theme, attempt, resetKey, setStatus]);

  const retry = () => {
    setSlow(false);
    cbRef.current.onToken(null);
    setStatus("loading");
    setAttempt((n) => n + 1);
  };

  const showRetry = status === "error" || slow;
  const dark = theme === "dark";
  const tone = {
    muted: dark ? "text-slate-300" : "text-slate-500 dark:text-slate-300",
    ok: dark ? "text-emerald-300" : "text-emerald-700 dark:text-emerald-300",
    warn: dark ? "text-amber-300" : "text-amber-700 dark:text-amber-300",
    bad: dark ? "text-rose-300" : "text-rose-700 dark:text-rose-300",
  };

  return (
    <div className={className}>
      <div ref={boxRef} className="min-h-[65px] w-full" />
      <div aria-live="polite" className="mt-1.5 min-h-5 text-xs">
        {status === "loading" || (status === "verifying" && !slow) ? (
          <p className={`flex items-center gap-1.5 ${tone.muted}`}>
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            Güvenlik kontrolü yapılıyor…
          </p>
        ) : null}
        {status === "ready" ? (
          <p className={`flex items-center gap-1.5 ${tone.ok}`}>
            <ShieldCheck className="size-3.5" aria-hidden />
            Bağlantın doğrulandı.
          </p>
        ) : null}
        {status === "expired" ? (
          <p className={`flex items-center gap-1.5 ${tone.warn}`}>
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            Doğrulamanın süresi doldu, yenileniyor…
          </p>
        ) : null}
        {showRetry ? (
          <p className={`flex flex-wrap items-center gap-1.5 ${tone.bad}`}>
            {status === "error"
              ? "Güvenlik kontrolü yüklenemedi."
              : "Güvenlik kontrolü beklenenden uzun sürüyor."}
            <button
              type="button"
              onClick={retry}
              className="inline-flex items-center gap-1 font-medium underline underline-offset-2"
            >
              <RefreshCw className="size-3" aria-hidden />
              Yeniden dene
            </button>
          </p>
        ) : null}
      </div>
    </div>
  );
}

/** <head>'e erken bağlantı ipucu — script ve challenge isteği daha hızlı başlar. */
export function TurnstilePreconnect() {
  return (
    <>
      <link rel="preconnect" href="https://challenges.cloudflare.com" />
      <link rel="dns-prefetch" href="https://challenges.cloudflare.com" />
    </>
  );
}
