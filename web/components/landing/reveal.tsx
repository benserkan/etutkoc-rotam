"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Giriş animasyonu — saf CSS (globals.css `.lp-reveal`).
 *
 * KRİTİK: İçerik dinlenme durumunda DAİMA görünür. Animasyon yalnızca bir
 * kez oynayan görsel katman; JS hydrate olmasa/yavaş olsa bile içerik gizli
 * kalmaz (eski IntersectionObserver + opacity-0 yaklaşımı, hydrate gecikince
 * hero'yu görünmez bırakıyordu — FOIC). Reduced-motion'da animasyon kapanır,
 * içerik yine görünür.
 */
export function Reveal({
  children,
  className,
  delayMs = 0,
  as: Tag = "div",
}: {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
  as?: React.ElementType;
}) {
  return (
    <Tag
      className={cn("lp-reveal", className)}
      style={delayMs ? { animationDelay: `${delayMs}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}

/** Görünürlüğe girince 0 → target sayan animasyonlu sayaç. */
export function CountUp({
  target,
  suffix = "",
  durationMs = 1600,
  className,
}: {
  target: number;
  suffix?: string;
  durationMs?: number;
  className?: string;
}) {
  const ref = React.useRef<HTMLSpanElement | null>(null);
  const [value, setValue] = React.useState(0);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    let started = false;
    const run = () => {
      const start = performance.now();
      const tick = (now: number) => {
        const p = Math.min((now - start) / durationMs, 1);
        // easeOutCubic
        const eased = 1 - Math.pow(1 - p, 3);
        setValue(Math.round(target * eased));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };
    if (!("IntersectionObserver" in window)) {
      run();
      return () => cancelAnimationFrame(raf);
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started) {
          started = true;
          run();
          io.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [target, durationMs]);

  return (
    <span ref={ref} className={className}>
      {value.toLocaleString("tr-TR")}
      {suffix}
    </span>
  );
}
