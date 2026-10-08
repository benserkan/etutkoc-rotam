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

  const onPointerDown = (e: React.PointerEvent<HTMLElement>) => {
    // Başlıktaki düğmeler (kapat vb.) taşımayı başlatmasın
    if ((e.target as HTMLElement).closest("button, a, input, select, textarea")) return;
    const win = e.currentTarget.closest("[data-floating]") as HTMLElement | null;
    if (!win) return;
    const r = win.getBoundingClientRect();
    e.currentTarget.setPointerCapture(e.pointerId);
    e.preventDefault();
    setDrag({ px: e.clientX, py: e.clientY, x: r.left, y: r.top, w: r.width, cur: { x: r.left, y: r.top } });
  };
  const onPointerMove = (e: React.PointerEvent<HTMLElement>) => {
    if (!drag) return;
    setDrag({
      ...drag,
      cur: clamp({ x: drag.x + (e.clientX - drag.px), y: drag.y + (e.clientY - drag.py) }, drag.w),
    });
  };
  const onPointerUp = () => {
    if (drag && (drag.cur.x !== drag.x || drag.cur.y !== drag.y)) write(key, drag.cur);
    setDrag(null);
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
      style: { cursor: drag ? "grabbing" : "grab", touchAction: "none" } as React.CSSProperties,
      title: "Sürükle: pencereyi taşı",
    },
  };
}
