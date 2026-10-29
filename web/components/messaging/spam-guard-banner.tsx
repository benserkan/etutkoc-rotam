"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Flame, MessageSquare } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  getMessagingDispatchStats,
  messagingKeys,
} from "@/lib/api/messaging";
import type { DispatchStatsResponse } from "@/lib/types/messaging";

/**
 * P6 — Koç için spam guard banner.
 *
 * Eşikler:
 *  - <50 mesaj/gün → görünmez ("ok")
 *  - 50-99 → amber (yoğun)
 *  - 100+ → rose (çok yoğun)
 *
 * Banner asla ENGELLEMEZ — Faz 1 manuel akış, koç sorumlu. Yalnız
 * bilgilendirir: "veliler engelleyebilir / spam'a düşebilir".
 *
 * Hafta sayım her zaman alt satırda küçük metin olarak gösterilir
 * (özet/transparan, "ok" durumda da görünür eğer hafta_count > 0).
 */
export function SpamGuardBanner() {
  const q = useQuery<DispatchStatsResponse>({
    queryKey: messagingKeys.dispatchStats(),
    queryFn: getMessagingDispatchStats,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });

  if (q.isLoading || q.isError || !q.data) return null;

  const { warning_level, warning_message, today_count, week_count } = q.data;

  // "ok" + hafta_count==0 → tamamen sessiz
  if (warning_level === "ok" && week_count === 0) {
    return null;
  }

  // "ok" + hafta varsa: küçük gri özet (bilgi şeridi)
  if (warning_level === "ok") {
    return (
      <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground inline-flex items-center gap-2">
        <MessageSquare className="size-3.5" aria-hidden />
        Bu hafta <strong className="text-foreground">{week_count}</strong> mesaj
        tetiklediniz · bugün <strong>{today_count}</strong>
      </div>
    );
  }

  const tone =
    warning_level === "cok_yogun"
      ? "rose"
      : "amber";

  return (
    <div
      className={cn(
        "rounded-md border px-3 py-3 flex items-start gap-3",
        tone === "rose"
          ? "border-rose-300 bg-rose-50"
          : "border-amber-300 bg-amber-50",
      )}
      role="alert"
    >
      <div
        className={cn(
          "rounded-full p-1.5 shrink-0",
          tone === "rose" ? "bg-rose-200" : "bg-amber-200",
        )}
      >
        {tone === "rose" ? (
          <Flame className="size-4 text-rose-800" aria-hidden />
        ) : (
          <AlertTriangle className="size-4 text-amber-800" aria-hidden />
        )}
      </div>
      <div className="flex-1 min-w-0 text-sm">
        <div
          className={cn(
            "font-semibold",
            tone === "rose" ? "text-rose-900" : "text-amber-900",
          )}
        >
          {tone === "rose"
            ? `Bugün ${today_count} mesaj attınız — çok yoğun`
            : `Bugün ${today_count} mesaj attınız — yoğun`}
        </div>
        {warning_message ? (
          <p
            className={cn(
              "text-xs mt-0.5 leading-relaxed",
              tone === "rose" ? "text-rose-800/90" : "text-amber-800/90",
            )}
          >
            {warning_message}
          </p>
        ) : null}
        <div
          className={cn(
            "text-[11px] mt-1",
            tone === "rose" ? "text-rose-700" : "text-amber-700",
          )}
        >
          Bu hafta toplam: <strong>{week_count}</strong> mesaj
        </div>
      </div>
    </div>
  );
}
