"use client";

/**
 * Raptiyeli bölüm — sağ paneldeki her bölümün ortak iskeleti (2026-09-08).
 *
 *   ▾ Başlık  · kısa özet                         📌
 *   … içerik (açıkken) …
 *
 * Başlığa tıkla → aç/kapa (+ kullanım sayar). Raptiye → sabitle (hep açık).
 * Katlı satır boş değil: `summary` ile koç açmadan durumu görür
 * ("Sıradaki üniteler (14)", "Serbest Bloklar · 2 aktif").
 *
 * İçerik alanına tıklama `touch` ile kullanım sayılır → yoğun kullanılan bölüm
 * açık kalır, kullanılmayan bir hafta sonra kendiliğinden katlanır.
 */

import * as React from "react";
import { ChevronDown, ChevronRight, Pin, PinOff } from "lucide-react";

import { useSectionPref } from "@/lib/hooks/use-section-prefs";
import { cn } from "@/lib/utils";

export function PinnableSection({
  id,
  title,
  icon,
  summary,
  defaultOpen = false,
  tone = "neutral",
  headerRight,
  children,
  className,
}: {
  /** localStorage anahtarı — sabit, bileşen yeri değişse de tercih kalır */
  id: string;
  title: React.ReactNode;
  icon?: React.ReactNode;
  /** Katlıyken başlığın yanında görünen kısa özet */
  summary?: React.ReactNode;
  /** Hiç tercih yokken varsayılan */
  defaultOpen?: boolean;
  tone?: "neutral" | "cyan" | "violet";
  /** Başlıkta raptiyenin solunda ek düğme (örn. "Yeni") — açıkken görünür */
  headerRight?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const { open, pinned, toggle, togglePin, touch } = useSectionPref(id, defaultOpen);

  const TONE = {
    neutral: {
      head: "hover:bg-muted/50",
      title: "text-foreground",
      icon: "text-muted-foreground",
    },
    cyan: {
      head: "hover:bg-cyan-500/10",
      title: "text-cyan-900 dark:text-cyan-100",
      icon: "text-cyan-700 dark:text-cyan-300",
    },
    violet: {
      head: "hover:bg-violet-500/10",
      title: "text-violet-900 dark:text-violet-100",
      icon: "text-violet-700 dark:text-violet-300",
    },
  }[tone];

  return (
    <section
      className={cn("border-b border-border", className)}
      data-section={id}
      data-open={open ? "1" : "0"}
      data-pinned={pinned ? "1" : "0"}
    >
      <div className={cn("flex items-center gap-1 pr-2 transition", TONE.head)}>
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-center gap-2 px-4 py-2.5 text-left"
        >
          {open ? (
            <ChevronDown className={cn("size-3.5 shrink-0", TONE.icon)} aria-hidden />
          ) : (
            <ChevronRight className={cn("size-3.5 shrink-0", TONE.icon)} aria-hidden />
          )}
          {icon ? <span className={cn("shrink-0", TONE.icon)}>{icon}</span> : null}
          <span className={cn("min-w-0 truncate text-sm font-medium", TONE.title)}>
            {title}
          </span>
          {summary ? (
            <span className="ml-auto shrink-0 text-[11px] text-muted-foreground tabular-nums">
              {summary}
            </span>
          ) : null}
        </button>
        {open && headerRight ? <div className="shrink-0">{headerRight}</div> : null}
        <button
          type="button"
          onClick={togglePin}
          className={cn(
            "shrink-0 rounded p-1.5 transition",
            pinned
              ? "text-amber-600 hover:bg-amber-500/15 dark:text-amber-400"
              : "text-muted-foreground/60 hover:bg-muted hover:text-foreground",
          )}
          title={pinned ? "Sabitlemeyi kaldır — kullanımına göre açılır/katlanır" : "Sabitle — her açılışta açık gelir"}
          aria-label={pinned ? "Sabitlemeyi kaldır" : "Sabitle"}
          aria-pressed={pinned}
        >
          {pinned ? (
            <Pin className="size-3.5 fill-current" aria-hidden />
          ) : (
            <PinOff className="size-3.5" aria-hidden />
          )}
        </button>
      </div>
      {open ? (
        // onClickCapture: içerideki her tıklama "kullanıldı" sayılır — bölüm
        // gerçekten kullanılıyorsa açık kalır. Capture fazı → içerik kendi
        // handler'ını çalıştırmaya devam eder.
        <div onClickCapture={touch}>{children}</div>
      ) : null}
    </section>
  );
}
