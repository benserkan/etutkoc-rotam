"use client";

/**
 * Sağ ŞERİT (rail) + geçici bölüm yuvası (peek host) — 2026-09-08.
 *
 * KOÇ: "sağ kısım epeyce yer kaplıyor; en sık kullanılanlar öne çıksın; program
 * hazırlama kısmına alan açılsın." Tasarım: sol gün fihristinin 44px şeridinin (bu şerit 52px — etiket sığsın)
 * simetriği — editör iki ince şerit arasında.
 *
 *   · Şerit her bölüm için simge + kısa etiket taşır (etiket = keşfedilebilirlik;
 *     sadece simge okunmaz). Sıra = son 7 gün kullanım (çok kullanılan üstte),
 *     sayfa yüklenişinde dondurulur.
 *   · Sabit bölüm (raptiye dolu): şeritte kehribar çubukla işaretli; tıklayınca
 *     paneldeki yerine kaydırır (katlıysa açar).
 *   · Sabit olmayan: tıklayınca PEEK — 320px'lik geçici panel şeridin solunda,
 *     editörün üstünde açılır (editör YER DEĞİŞTİRMEZ). Esc / dışarı tıklama /
 *     X kapatır; raptiye panele yerleştirir. Aynı anda tek peek.
 *   · Hiç sabit yoksa sağ taraf yalnız 52px şerittir → editör ~320px kazanır.
 *
 * Dar ekran (<xl): şerit yatay bir sıra olur, peek onun altında satır içi açılır.
 */

import * as React from "react";

import {
  closeSessionGroup,
  useSectionOrder,
  useSectionPref,
} from "@/lib/hooks/use-section-prefs";
import { cn } from "@/lib/utils";
import {
  SIDE_SECTION_IDS,
  SIDE_SECTIONS,
  type SideSectionDef,
} from "./side-sections";

const ACTIVE_TONE: Record<SideSectionDef["tone"], string> = {
  neutral: "bg-muted text-foreground",
  cyan: "bg-cyan-500/15 text-cyan-900 dark:text-cyan-100",
  violet: "bg-violet-500/15 text-violet-900 dark:text-violet-100",
  amber: "bg-amber-500/15 text-amber-900 dark:text-amber-100",
};

export function SideRail({
  badges,
  hidden,
  className,
}: {
  /** Simge üstü rozet (örn. Devret aday sayısı) */
  badges?: Record<string, number | undefined>;
  /** Şu an anlamsız bölümler (örn. adayı olmayan Devret) */
  hidden?: readonly string[];
  className?: string;
}) {
  const order = useSectionOrder(SIDE_SECTION_IDS);
  const defs = order
    .map((id) => SIDE_SECTIONS.find((d) => d.id === id))
    .filter((d): d is SideSectionDef => !!d && !hidden?.includes(d.id));
  return (
    <nav
      aria-label="Yan panel bölümleri"
      data-rail=""
      className={cn(
        "flex shrink-0 gap-0.5 rounded-lg border border-border bg-card p-1",
        "flex-row overflow-x-auto xl:w-[52px] xl:flex-col xl:overflow-visible",
        className,
      )}
    >
      {defs.map((d) => (
        <RailButton key={d.id} def={d} badge={badges?.[d.id]} />
      ))}
    </nav>
  );
}

function RailButton({ def, badge }: { def: SideSectionDef; badge?: number }) {
  const { pinned, open, toggle } = useSectionPref(
    def.id,
    def.defaultPinned,
    SIDE_SECTION_IDS,
  );
  const Icon = def.icon;

  function onClick() {
    if (pinned) {
      // Panele kaydır; oturumda katlanmışsa aç.
      if (!open) toggle();
      if (typeof window !== "undefined") {
        window.requestAnimationFrame(() => {
          document
            .querySelector(`[data-section="${def.id}"]`)
            ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
      }
      return;
    }
    toggle();
  }

  const title = pinned
    ? `${def.title} — sabit (panelde). ${def.hint}`
    : open
      ? `${def.title} — kapat`
      : `${def.title} — ${def.hint}`;

  return (
    <button
      type="button"
      onClick={onClick}
      data-rail={def.id}
      data-pinned={pinned ? "1" : "0"}
      data-open={open ? "1" : "0"}
      aria-pressed={open}
      title={title}
      className={cn(
        "relative flex shrink-0 flex-col items-center gap-0.5 rounded-md px-1.5 py-1.5 text-muted-foreground transition",
        "min-w-[56px] xl:min-w-0 xl:w-full",
        open ? ACTIVE_TONE[def.tone] : "hover:bg-muted hover:text-foreground",
      )}
    >
      {pinned ? (
        <span
          className="absolute inset-y-1.5 left-0 w-0.5 rounded-r bg-amber-500"
          aria-hidden
          data-pin-mark=""
        />
      ) : null}
      <Icon className="size-4" aria-hidden />
      <span className="max-w-full truncate text-[9px] font-medium leading-none">{def.short}</span>
      {badge ? (
        <span
          className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-amber-600 px-1 text-center text-[9px] font-bold leading-4 text-white"
          data-badge=""
        >
          {badge}
        </span>
      ) : null}
    </button>
  );
}

/**
 * Geçici bölümün yuvası: Esc ve dışarı tıklama kapatır. Açık bir diyalog
 * (Radix) varken dışarı tıklama YOK SAYILIR — diyalogla çalışan koçun altındaki
 * panel kaybolmasın (diyalog unmount olurdu).
 */
export function PeekHost({
  peekId,
  children,
  className,
}: {
  peekId: string | null;
  children: React.ReactNode;
  className?: string;
}) {
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!peekId) return;
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      if (document.querySelector('[role="dialog"][data-state="open"]')) return;
      closeSessionGroup(SIDE_SECTION_IDS);
    }
    function onDown(e: MouseEvent) {
      const t = e.target as Element | null;
      if (!t || !(t instanceof Element)) return;
      if (ref.current?.contains(t)) return;
      if (t.closest("[data-rail]")) return;
      if (document.querySelector('[role="dialog"][data-state="open"]')) return;
      if (t.closest("[data-sonner-toaster]")) return;
      closeSessionGroup(SIDE_SECTION_IDS);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [peekId]);

  if (!peekId) return null;
  return (
    <div
      ref={ref}
      data-peek={peekId}
      role="region"
      aria-label="Geçici bölüm"
      className={cn(
        "rounded-lg border border-border bg-card shadow-xl",
        className,
      )}
    >
      {children}
    </div>
  );
}
