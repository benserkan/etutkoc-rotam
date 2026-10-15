"use client";

import * as React from "react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Düğme üstüne gelince "bu ne yapar?" açıklaması (Radix tooltip; klavye odağında da açılır).
 * Kullanım: <Hint text="Dönemi kapatır…"><Button>…</Button></Hint> — çocuk tek öğe olmalı.
 */
export function Hint({ text, side = "top", children }: {
  text: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  children: React.ReactElement;
}) {
  return (
    <TooltipProvider delayDuration={250}>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent side={side} className="max-w-xs leading-snug">{text}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
