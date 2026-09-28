"use client";

import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { Info } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Tablo sütun başlığı / KPI etiketi açıklaması (2026-09-28).
 *
 * Başlığın üzerine gelince (hover) ya da klavyeyle odaklanınca açıklama kutusu
 * açılır; dokunmatik ekranda hover olmadığı için DOKUNUNCA da açılır/kapanır.
 * Etiket noktalı altçizgi + (i) ikonu taşır → "burada açıklama var" görünür.
 *
 *   <th><ColumnHint label="Plan" hint="Son 7 günde planlanan test sayısı" /></th>
 */
export function ColumnHint({
  label,
  hint,
  className,
  side = "top",
}: {
  label: React.ReactNode;
  hint: React.ReactNode;
  className?: string;
  side?: "top" | "bottom" | "left" | "right";
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <TooltipPrimitive.Provider delayDuration={120}>
      <TooltipPrimitive.Root open={open} onOpenChange={setOpen}>
        <TooltipPrimitive.Trigger asChild>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              setOpen((v) => !v);
            }}
            data-column-hint
            className={cn(
              "inline-flex items-center gap-1 rounded-sm text-inherit font-inherit",
              "cursor-help underline decoration-dotted decoration-current/40 underline-offset-[3px]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              className,
            )}
          >
            <span>{label}</span>
            <Info className="size-3 shrink-0 opacity-60" aria-hidden />
          </button>
        </TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={6}
            collisionPadding={12}
            className={cn(
              "z-50 max-w-xs rounded-md border border-border bg-popover px-3 py-2 text-left text-xs font-normal normal-case tracking-normal leading-relaxed text-popover-foreground shadow-md",
              "animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
            )}
          >
            {hint}
            <TooltipPrimitive.Arrow className="fill-popover" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
