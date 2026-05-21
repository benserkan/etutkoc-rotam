"use client";

import * as React from "react";
import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * JargonTooltip — admin/kurum metriklerinin yanına açıklayıcı tooltip.
 *
 * KIRMIZI ÇİZGİ ENFORCEMENT:
 *   "DAU/MRR/Churn/Tenant/Descending" gibi yabancı/teknik terimler
 *   açıklamasız geçemez ([[feedback_admin_panel_jargon]]).
 *
 *   Kullanım:
 *     <JargonTooltip term="Tutturma">
 *       Planlanan görevlerin gerçekten tamamlanma oranı (%)
 *     </JargonTooltip>
 *
 *   Veya inline (sadece term, ⓘ ikon):
 *     <span>Aktif kullanıcı <JargonTooltip term="DAU" content="..." /></span>
 */
interface JargonTooltipProps {
  /** Görünür terim — kullanıcının okuduğu kısa metin. */
  term?: string;
  /** Tooltip içeriği — Türkçe, jargon yok, somut. */
  content?: string;
  children?: React.ReactNode;
  className?: string;
}

export function JargonTooltip({ term, content, children, className }: JargonTooltipProps) {
  // children verilirse onu tooltip içeriği olarak kabul et
  const body = content ?? children;
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              "inline-flex items-center gap-1 cursor-help underline decoration-dotted decoration-muted-foreground/50 underline-offset-2",
              !term && "no-underline",
              className
            )}
          >
            {term ? <span>{term}</span> : null}
            <Info className="size-3.5 text-muted-foreground" aria-hidden="true" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top">{body}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
