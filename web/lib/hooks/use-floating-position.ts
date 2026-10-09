"use client";

/**
 * Yüzen pencere taşıma — başlıktan tut, istediğin yere bırak (2026-10-08).
 *
 * Konum tarayıcıda saklanır (localStorage, `useSyncExternalStore` → hydration
 * uyuşmazlığı yok, effect'te setState yok). Konum yoksa pencere varsayılan
 * köşede (çağıranın CSS'i) durur. Ekran küçülürse pencere görünür alana
 * kırpılır — başlığı asla ekran dışında kalmaz.
 *
 * Kullanım:
 *   const fp = useFloatingPosition("rotam:float:video-basket");
 *   <div data-floating style={fp.style} className={fp.pos ? "fixed" : "fixed bottom-24 right-6"}>
 *     <div {...fp.handleProps}>başlık</div>
 */

import * as React from "react";

type Pos = { x: number; y: number } | null;

const listeners = new Set<() => void>();
const cache = new Map<string, { raw: string; pos: Pos }>();

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function read(key: string): Pos {
  let raw = "";
  try {
    raw = window.localStorage.getItem(key) ?? "";
  } catch {
    raw = "";
  }
  const hit = cache.get(key);
  if (hit && hit.raw === raw) return hit.pos;
  let pos: Pos = null;
  if (raw) {
    try {
      const p = JSON.parse(raw) as { x?: unknown; y?: unknown };
      if (typeof p.x === "number" && typeof p.y === "number") pos = { x: p.x, y: p.y };
    } catch {
      pos = null;
    }
  }
  cache.set(key, { raw, pos });
  return pos;
}

function write(key: string, pos: Pos): void {
  try {
    if (pos) window.localStorage.setItem(key, JSON.stringify(pos));
    else window.localStorage.removeItem(key);
  } catch {
    // depolama yok — konum yalnız bu sürüklemede geçerli
  }
  for (const l of listeners) l();
}

/** Başlık çubuğunun en az bu kadarı ekranda kalsın. */
const KEEP = 48;

function clamp(pos: { x: number; y: number }, w: number): { x: number; y: number } {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  return {
    x: Math.min(Math.max(pos.x, KEEP - w), vw - KEEP),
    y: Math.min(Math.max(pos.y, 0), vh - KEEP),
  };
}

export function useFloatingPosition(key: string, approxWidth = 380) {
  const stored = React.useSyncExternalStore(subscribe, () => read(key), () => null);
  const [drag, setDrag] = React.useState<{
    px: number; py: number; x: number; y: number; w: number; cur: { x: number; y: number };
  } | null>(null);

  const pos = drag ? drag.cur : stored;

  // Tutma yeri bir DÜĞME de olabilir (kapalı "Video Sepeti" düğmesi): 4px'ten
  // az oynarsa tıklama, fazlası taşıma sayılır; taşımadan sonraki click yutulur.
  const movedRef = React.useRef(false);

  const onPointerDown = (e: React.PointerEvent<HTMLElement>) => {
    if (e.button !== 0) return;
    // Başlıktaki İÇ düğmeler (kapat vb.) taşımayı başlatmasın — tutma yerinin
    // kendisi düğmeyse o sayılmaz.
    const inner = (e.target as HTMLElement).closest("button, a, input, select, textarea");
    if (inner && inner !== e.currentTarget) return;
    const win = e.currentTarget.closest("[data-floating]") as HTMLElement | null;
    if (!win) return;
    const r = win.getBoundingClientRect();
    movedRef.current = false;
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({ px: e.clientX, py: e.clientY, x: r.left, y: r.top, w: r.width, cur: { x: r.left, y: r.top } });
  };
  const onPointerMove = (e: React.PointerEvent<HTMLElement>) => {
    if (!drag) return;
    const dx = e.clientX - drag.px;
    const dy = e.clientY - drag.py;
    if (!movedRef.current && Math.abs(dx) + Math.abs(dy) < 4) return;
    movedRef.current = true;
    setDrag({ ...drag, cur: clamp({ x: drag.x + dx, y: drag.y + dy }, drag.w) });
  };
  const onPointerUp = () => {
    if (drag && movedRef.current) write(key, drag.cur);
    setDrag(null);
  };
  const onClickCapture = (e: React.MouseEvent<HTMLElement>) => {
    if (movedRef.current) {
      movedRef.current = false;
      e.preventDefault();
      e.stopPropagation();
    }
  };

  // Kayıtlı konum ekran dışına düşmüşse (pencere küçüldü) görünür alana çek.
  const style: React.CSSProperties | undefined = pos
    ? (() => {
        const p = typeof window === "undefined" ? pos : clamp(pos, approxWidth);
        return { left: p.x, top: p.y, right: "auto", bottom: "auto" };
      })()
    : undefined;

  return {
    pos,
    style,
    dragging: drag !== null,
    reset: () => write(key, null),
    handleProps: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel: onPointerUp,
      onClickCapture,
      style: { cursor: drag ? "grabbing" : "grab", touchAction: "none" } as React.CSSProperties,
      title: "Sürükle: pencereyi taşı",
    },
  };
}

/**
 * Tarayıcıda saklanan açık/kapalı bayrağı (örn. "Kaynak Durumu yüzen
 * pencerede mi"). Aynı store deseni: hydration uyuşmazlığı yok.
 */
function readFlag(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

export function useStoredFlag(key: string): [boolean, (v: boolean) => void] {
  const on = React.useSyncExternalStore(subscribe, () => readFlag(key), () => false);
  const set = React.useCallback(
    (v: boolean) => {
      try {
        if (v) window.localStorage.setItem(key, "1");
        else window.localStorage.removeItem(key);
      } catch {
        // depolama yok
      }
      for (const l of listeners) l();
    },
    [key],
  );
  return [on, set];
}
