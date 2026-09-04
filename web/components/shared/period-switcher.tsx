"use client";

/**
 * Sınıf dönemi seçici (P3) — konu performansı, deneme listesi ve deneme konu
 * analizinde ortak.
 *
 * Varsayılan görünüm GÜNCEL dönemdir: geçen yılın verisi silinmez, sadece bu
 * yılın tablosunu bozmaz. Koç/öğrenci/veli buradan önceki döneme ya da tüm
 * geçmişe geçebilir.
 *
 * Tek dönemli (ya da dönem kaydı olmayan) öğrencide hiç render edilmez —
 * gereksiz kontrol göstermeyiz.
 */
import * as React from "react";
import { CalendarRange } from "lucide-react";

import type { PeriodFilterMeta } from "@/lib/types/period";
import { cn } from "@/lib/utils";

export function PeriodSwitcher({
  meta,
  value,
  onChange,
  className,
}: {
  meta?: PeriodFilterMeta | null;
  /** Seçili anahtar: undefined/"current" = güncel dönem · "all" · "<id>" */
  value?: string;
  onChange: (next: string | undefined) => void;
  className?: string;
}) {
  const options = meta?.options ?? [];
  if (options.length < 2) return null;

  const active = value ?? "current";
  const currentId = options.find((o) => o.is_current)?.id;

  function keyFor(id: number): string {
    // Güncel dönem "current" ile temsil edilir → varsayılan istek parametresiz
    // gider ve cache anahtarı sabit kalır.
    return currentId === id ? "current" : String(id);
  }

  return (
    <div className={cn("flex flex-wrap items-center gap-1.5 text-xs", className)}>
      <span className="flex items-center gap-1 text-muted-foreground">
        <CalendarRange className="size-3.5" aria-hidden />
        Dönem:
      </span>
      {options.map((o) => {
        const k = keyFor(o.id);
        const isActive = active === k || (o.is_current && active === "current");
        return (
          <button
            key={o.id}
            type="button"
            onClick={() => onChange(o.is_current ? undefined : k)}
            className={cn(
              "rounded-full border px-2.5 py-1 transition-colors",
              isActive
                ? "border-cyan-300 bg-cyan-50 font-medium text-cyan-900 dark:border-cyan-500/40 dark:bg-cyan-500/15 dark:text-cyan-200"
                : "border-border text-muted-foreground hover:bg-muted",
            )}
            title={
              o.is_current
                ? "Bu dönem (varsayılan)"
                : `${o.started_on} — ${o.ended_on ?? "…"}`
            }
          >
            {o.label}
            {o.is_current ? " · bu dönem" : ""}
          </button>
        );
      })}
      <button
        type="button"
        onClick={() => onChange("all")}
        className={cn(
          "rounded-full border px-2.5 py-1 transition-colors",
          active === "all"
            ? "border-slate-400 bg-slate-100 font-medium text-slate-900 dark:border-slate-500/50 dark:bg-slate-500/20 dark:text-slate-100"
            : "border-border text-muted-foreground hover:bg-muted",
        )}
        title="Tüm dönemler birlikte"
      >
        Tümü
      </button>
    </div>
  );
}

/** Seçili dönem güncel değilken gösterilen bilgi bandı. */
export function PeriodContextNote({
  meta,
  value,
}: {
  meta?: PeriodFilterMeta | null;
  value?: string;
}) {
  const active = value ?? "current";
  if (!meta || (meta.options?.length ?? 0) < 2) return null;
  if (active === "current") return null;

  const label =
    active === "all"
      ? "Tüm dönemler"
      : meta.options.find((o) => String(o.id) === active)?.label;

  return (
    <p className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
      {label ?? "Geçmiş dönem"} gösteriliyor — bu, öğrencinin{" "}
      <strong>güncel dönemi değil</strong>. Bu döneme dönmek için{" "}
      <em>bu dönem</em> seçeneğine dokun.
    </p>
  );
}
