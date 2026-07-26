"use client";

import { cn } from "@/lib/utils";
import { GUIDE_AVATAR_SRC } from "@/components/guide/coach-guide-data";

/**
 * Rota — rehber karakteri avatarı.
 * speaking=true iken: dışa yayılan halka + ekolayzer çubukları (CSS animasyonu,
 * globals.css `guide-*` keyframe'leri). Fotoğraf /static/guide altından gelir
 * (FastAPI static; dev'de next.config /static rewrite'ı, prod'da Caddy).
 */
export function GuideAvatar({
  size = 88,
  speaking = false,
  className,
}: {
  size?: number;
  speaking?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn("relative shrink-0 guide-breathe", className)}
      style={{ width: size, height: size }}
      aria-hidden
    >
      {speaking ? (
        <span className="guide-ring absolute inset-0 rounded-full border-2 border-cyan-400" />
      ) : null}
      <span
        className={cn(
          "absolute -inset-1 rounded-full bg-gradient-to-br from-cyan-500 via-cyan-400 to-amber-400",
          speaking ? "opacity-90" : "opacity-50",
        )}
      />
      {/* eslint-disable-next-line @next/next/no-img-element -- /static (FastAPI) varlığı; next/image optimizer prod'da bu origin'i çözemez */}
      <img
        src={GUIDE_AVATAR_SRC}
        alt="Rota — rehberin"
        width={size}
        height={size}
        className="relative h-full w-full rounded-full border-2 border-white object-cover shadow-lg"
        draggable={false}
      />
      {speaking ? (
        <span className="absolute -bottom-1 -right-1 flex h-7 w-7 items-end justify-center gap-[2.5px] rounded-full border border-cyan-200 bg-white p-1.5 shadow">
          <span className="guide-eq-bar h-full w-[3px] rounded-full bg-cyan-500" />
          <span className="guide-eq-bar h-full w-[3px] rounded-full bg-cyan-600 [animation-delay:0.15s]" />
          <span className="guide-eq-bar h-full w-[3px] rounded-full bg-amber-500 [animation-delay:0.3s]" />
        </span>
      ) : null}
    </div>
  );
}
