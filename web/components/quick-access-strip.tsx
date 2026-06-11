"use client";

/**
 * QuickAccessStrip — davranıştan öğrenen hızlı erişim kartları şeridi.
 *
 * 5 rolün panel ana sayfasının üstünde yaşar (mevcut kartlara DOKUNMAZ).
 * Yaşam döngüsü: sistem sık ziyaret edilen sayfaları öğrenir → "önerilen"
 * kart gösterir → karta 3 tıklamada kart kalıcılaşır → kullanıcı dilediğinde
 * sabitler (📌) veya kaldırır (×, 90 gün önerilmez).
 *
 * Boş durum: yeterli veri yokken HİÇBİR ŞEY render edilmez (gürültü yok).
 * Kontrast: tonal zeminlerde explicit koyu renk (purge-safe) — tema token'ı
 * açık zeminde beyaza çözülmez.
 */

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pin, Sparkles, X, Zap } from "lucide-react";
import { toast } from "sonner";

import {
  getQuickCards,
  postQuickCardClick,
  postQuickCardDismiss,
  postQuickCardPin,
  quickAccessKeys,
} from "@/lib/api/quick-access";
import { applyInvalidate } from "@/lib/invalidate";
import type { QuickCard, QuickCardsResponse } from "@/lib/types/quick-access";
import { cn } from "@/lib/utils";

const MAX_VISIBLE = 6;

function stripQuery(href: string): string {
  return href.split("?")[0].split("#")[0].replace(/\/$/, "") || "/";
}

interface Props {
  /**
   * Panelde zaten statik kart/kısayol olarak duran hedefler — aynı sayfaya
   * ikinci kart açılmaz (mükerrer hedef tekilleştirme).
   */
  excludeHrefs?: string[];
  className?: string;
}

export function QuickAccessStrip({ excludeHrefs, className }: Props) {
  const qc = useQueryClient();
  const q = useQuery<QuickCardsResponse>({
    queryKey: quickAccessKeys.cards(),
    queryFn: () => getQuickCards(),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });

  const clickMut = useMutation({
    mutationFn: postQuickCardClick,
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
  });
  const pinMut = useMutation({
    mutationFn: ({ card, pinned }: { card: QuickCard; pinned: boolean }) =>
      postQuickCardPin(
        { route_key: card.route_key, entity_id: card.entity_id },
        pinned,
      ),
    onSuccess: (res, vars) => {
      applyInvalidate(qc, res.invalidate);
      toast.success(
        vars.pinned ? "Kart sabitlendi" : "Sabitleme kaldırıldı",
      );
    },
  });
  const dismissMut = useMutation({
    mutationFn: (card: QuickCard) =>
      postQuickCardDismiss({
        route_key: card.route_key,
        entity_id: card.entity_id,
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Kart kaldırıldı", {
        description: "Bu sayfa 90 gün boyunca tekrar önerilmeyecek.",
      });
    },
  });

  const excluded = React.useMemo(
    () => new Set((excludeHrefs ?? []).map(stripQuery)),
    [excludeHrefs],
  );
  const cards = (q.data?.cards ?? [])
    .filter((c) => !excluded.has(stripQuery(c.href)))
    .slice(0, MAX_VISIBLE);

  if (cards.length === 0) return null;

  return (
    <section
      aria-label="Hızlı erişim"
      className={cn(
        "rounded-xl border bg-card p-4 shadow-sm",
        "border-t-4 border-t-cyan-600",
        className,
      )}
    >
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <h2 className="text-sm font-semibold inline-flex items-center gap-1.5">
          <Zap className="size-4 text-cyan-600" aria-hidden />
          Hızlı Erişim
        </h2>
        <p className="text-xs text-muted-foreground">
          Kullanım alışkanlığından öğrenir — sık gittiğin sayfalar burada
          birikir. Sabitle (📌) ile kalıcı yap, × ile kaldır.
        </p>
      </div>
      <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-2">
        {cards.map((card) => (
          <QuickCardTile
            key={`${card.route_key}:${card.entity_id ?? 0}`}
            card={card}
            onClickThrough={() =>
              clickMut.mutate({
                route_key: card.route_key,
                entity_id: card.entity_id,
              })
            }
            onPin={(pinned) => pinMut.mutate({ card, pinned })}
            onDismiss={() => dismissMut.mutate(card)}
          />
        ))}
      </div>
    </section>
  );
}

function QuickCardTile({
  card,
  onClickThrough,
  onPin,
  onDismiss,
}: {
  card: QuickCard;
  onClickThrough: () => void;
  onPin: (pinned: boolean) => void;
  onDismiss: () => void;
}) {
  const pinned = card.state === "pinned";
  return (
    <div className="relative group">
      <Link
        href={card.href}
        onClick={onClickThrough}
        className={cn(
          "block rounded-lg border bg-background p-3 pr-12 transition",
          "hover:border-cyan-400 hover:shadow-sm",
          pinned && "border-cyan-300 ring-1 ring-inset ring-cyan-500/10",
        )}
      >
        <span className="block text-sm font-medium text-foreground truncate">
          {card.label}
        </span>
        {card.sublabel ? (
          <span className="block text-xs text-muted-foreground truncate mt-0.5">
            {card.sublabel}
          </span>
        ) : (
          <span className="block text-xs text-muted-foreground/60 truncate mt-0.5">
            Sayfa
          </span>
        )}
        {card.state === "suggested" && (
          <span className="mt-1.5 inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50 px-1.5 py-0.5 text-[10px] font-medium text-cyan-900">
            <Sparkles className="size-2.5" aria-hidden />
            önerilen
          </span>
        )}
      </Link>
      <div className="absolute right-1.5 top-1.5 flex flex-col gap-0.5">
        <button
          type="button"
          aria-label={pinned ? "Sabitlemeyi kaldır" : "Kartı sabitle"}
          title={pinned ? "Sabitlemeyi kaldır" : "Sabitle — skor düşse de kalır"}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onPin(!pinned);
          }}
          className={cn(
            "rounded p-1 transition",
            pinned
              ? "text-cyan-700 hover:bg-cyan-50"
              : "text-muted-foreground/50 hover:text-cyan-700 hover:bg-cyan-50",
          )}
        >
          <Pin className={cn("size-3.5", pinned && "fill-current")} aria-hidden />
        </button>
        <button
          type="button"
          aria-label="Kartı kaldır"
          title="Kaldır — 90 gün önerilmez"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDismiss();
          }}
          className="rounded p-1 text-muted-foreground/50 transition hover:text-rose-700 hover:bg-rose-50"
        >
          <X className="size-3.5" aria-hidden />
        </button>
      </div>
    </div>
  );
}
