"use client";

/**
 * Raptiyeli bölüm — sağ paneldeki her bölümün ortak iskeleti (v2, 2026-09-08).
 *
 * İki görünüm, tek bileşen:
 *   · DOCKED (raptiye DOLU): panelde sabit; başlıktan oturum içinde katlanır.
 *       ▾ Başlık · özet                         📌
 *   · PEEK (raptiye BOŞ, şeritten geçici açıldı): X ile kapanır, raptiyeyle
 *     panele yerleşir. "Sabitle" yazısı görünür — koç raptiyenin ne yaptığını
 *     okumadan anlasın (v1'de simge yanlış anlaşılmıştı).
 *
 * Sabit değil + açık değil → hiç render etmez (yeri şeritteki simgesidir).
 * İçerikteki tıklama `touch` ile kullanım sayılır → şeritte/panelde sıra.
 */

import * as React from "react";
import { ChevronDown, ChevronRight, Pin, X } from "lucide-react";

import { useSectionPref } from "@/lib/hooks/use-section-prefs";
import { cn } from "@/lib/utils";
import { SIDE_SECTION_IDS, type SideTone } from "./side-sections";

const TONE: Record<
  SideTone,
  { head: string; title: string; icon: string; peekBar: string }
> = {
  neutral: {
    head: "hover:bg-muted/50",
    title: "text-foreground",
    icon: "text-muted-foreground",
    peekBar: "bg-slate-400",
  },
  cyan: {
    head: "hover:bg-cyan-500/10",
    title: "text-cyan-900 dark:text-cyan-100",
    icon: "text-cyan-700 dark:text-cyan-300",
    peekBar: "bg-cyan-500",
  },
  violet: {
    head: "hover:bg-violet-500/10",
    title: "text-violet-900 dark:text-violet-100",
    icon: "text-violet-700 dark:text-violet-300",
    peekBar: "bg-violet-500",
  },
  amber: {
    head: "hover:bg-amber-500/10",
    title: "text-amber-900 dark:text-amber-100",
    icon: "text-amber-700 dark:text-amber-300",
    peekBar: "bg-amber-500",
  },
};

export function PinnableSection({
  id,
  title,
  icon,
  summary,
  defaultPinned = false,
  tone = "neutral",
  headerRight,
  children,
  className,
}: {
  /** localStorage anahtarı — sabit, bileşen yeri değişse de tercih kalır */
  id: string;
  title: React.ReactNode;
  icon?: React.ReactNode;
  /** Başlığın yanında görünen kısa özet */
  summary?: React.ReactNode;
  /** Hiç tercih yokken sabit mi */
  defaultPinned?: boolean;
  tone?: SideTone;
  /** Başlıkta raptiyenin solunda ek düğme (örn. "Yeni") — içerik açıkken görünür */
  headerRight?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const { open, pinned, toggle, togglePin, touch } = useSectionPref(
    id,
    defaultPinned,
    SIDE_SECTION_IDS,
  );
  if (!pinned && !open) return null;
  const mode = pinned ? "docked" : "peek";
  const T = TONE[tone];

  return (
    <section
      className={cn(
        mode === "docked" ? "border-b border-border" : "relative",
        className,
      )}
      data-section={id}
      data-mode={mode}
      data-open={open ? "1" : "0"}
      data-pinned={pinned ? "1" : "0"}
    >
      {mode === "peek" ? (
        <span className={cn("absolute inset-y-0 left-0 w-1 rounded-l-lg", T.peekBar)} aria-hidden />
      ) : null}
      <div className={cn("flex items-center gap-1 pr-1.5 transition", T.head)}>
        {mode === "docked" ? (
          <button
            type="button"
            onClick={toggle}
            aria-expanded={open}
            className="flex min-w-0 flex-1 items-center gap-2 px-3 py-2.5 text-left"
            title={open ? "Bölümü katla (bu oturumda)" : "Bölümü aç"}
          >
            {open ? (
              <ChevronDown className={cn("size-3.5 shrink-0", T.icon)} aria-hidden />
            ) : (
              <ChevronRight className={cn("size-3.5 shrink-0", T.icon)} aria-hidden />
            )}
            {icon ? <span className={cn("shrink-0", T.icon)}>{icon}</span> : null}
            <span className={cn("min-w-0 truncate text-sm font-medium", T.title)}>{title}</span>
            {summary ? (
              <span className="ml-auto shrink-0 text-[11px] text-muted-foreground tabular-nums">
                {summary}
              </span>
            ) : null}
          </button>
        ) : (
          // Peek başlığında ÖZET YOK: başlık + headerRight + "Sabitle" + X 320px'e
          // sığmıyordu ("Serbest Bloklar" → "S.."); özet katlı başlığın bilgisidir,
          // peek zaten içeriği gösterir. Koyu tema kontrolünde yakalandı.
          <div className="flex min-w-0 flex-1 items-center gap-2 px-3.5 py-2.5">
            {icon ? <span className={cn("shrink-0", T.icon)}>{icon}</span> : null}
            <span className={cn("min-w-0 truncate text-sm font-medium", T.title)}>{title}</span>
          </div>
        )}
        {open && headerRight ? <div className="shrink-0">{headerRight}</div> : null}
        <button
          type="button"
          onClick={togglePin}
          className={cn(
            "flex shrink-0 items-center gap-1 rounded px-1.5 py-1 text-[11px] transition",
            pinned
              ? "text-amber-600 hover:bg-amber-500/15 dark:text-amber-400"
              : "text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
          title={
            pinned
              ? "Sabit — her açılışta panelde açık. Kaldırırsan şeride iner."
              : "Sabitle — her açılışta panelde açık gelir."
          }
          aria-label={pinned ? "Sabitlemeyi kaldır" : "Sabitle"}
          aria-pressed={pinned}
        >
          <Pin className={cn("size-3.5", pinned && "fill-current")} aria-hidden />
          {mode === "peek" ? <span>Sabitle</span> : null}
        </button>
        {mode === "peek" ? (
          <button
            type="button"
            onClick={toggle}
            className="shrink-0 rounded p-1 text-muted-foreground transition hover:bg-muted hover:text-foreground"
            title="Kapat (Esc)"
            aria-label="Bölümü kapat"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        ) : null}
      </div>
      {open ? (
        // onClickCapture: içerideki her tıklama "kullanıldı" sayılır → sıralama.
        // Capture fazı → içerik kendi handler'ını çalıştırmaya devam eder.
        <div onClickCapture={touch}>{children}</div>
      ) : null}
    </section>
  );
}
