"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { BurnoutLevel, RiskLevel } from "@/lib/types/institution";

/**
 * Risk + Burnout seviyeleri için renkli pill badge — Jinja `at_risk_list.html`
 * ve `burnout.html` ile birebir aynı renk paleti.
 */

const RISK_CLASSES: Record<RiskLevel, string> = {
  critical: "bg-rose-100 text-rose-800 border-rose-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-amber-100 text-amber-800 border-amber-200",
  ok: "bg-emerald-100 text-emerald-800 border-emerald-200",
};

const BURNOUT_CLASSES: Record<BurnoutLevel, string> = {
  critical: "bg-rose-100 text-rose-800 border-rose-200",
  warn: "bg-amber-100 text-amber-800 border-amber-200",
  watch: "bg-sky-100 text-sky-800 border-sky-200",
  healthy: "bg-emerald-100 text-emerald-800 border-emerald-200",
};

const BURNOUT_LABELS: Record<BurnoutLevel, { label: string; emoji: string }> = {
  critical: { label: "Kritik", emoji: "🔴" },
  warn: { label: "Uyarı", emoji: "🟠" },
  watch: { label: "Dikkat", emoji: "🟡" },
  healthy: { label: "Sağlıklı", emoji: "🟢" },
};

export function RiskLevelBadge({
  level,
  label,
  emoji,
  className,
}: {
  level: RiskLevel;
  label: string;
  emoji: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium",
        RISK_CLASSES[level],
        className,
      )}
    >
      <span aria-hidden>{emoji}</span>
      <span>{label}</span>
    </span>
  );
}

export function BurnoutLevelBadge({
  level,
  className,
}: {
  level: BurnoutLevel;
  className?: string;
}) {
  const { label, emoji } = BURNOUT_LABELS[level];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium",
        BURNOUT_CLASSES[level],
        className,
      )}
    >
      <span aria-hidden>{emoji}</span>
      <span>{label}</span>
    </span>
  );
}

/** Skor (0-100) renk classı — Jinja `at_risk_list.html:117` koşulları. */
export function riskScoreColorClass(score: number): string {
  if (score >= 80) return "text-rose-700";
  if (score >= 60) return "text-orange-700";
  return "text-amber-700";
}

/** Burnout skor (0-100) renk classı — Jinja `burnout.html:35-39` koşulları. */
export function burnoutScoreColorClass(level: BurnoutLevel): string {
  switch (level) {
    case "critical":
      return "text-rose-700";
    case "warn":
      return "text-amber-700";
    case "watch":
      return "text-sky-700";
    case "healthy":
      return "text-emerald-700";
  }
}

/** Risk seviyesine göre satır arka planı — Jinja `at_risk_list.html:74-76`. */
export function riskRowBgClass(
  level: RiskLevel,
  isPaused: boolean,
): string {
  if (isPaused) return "bg-muted/40 opacity-60 grayscale-[40%]";
  if (level === "critical") return "bg-rose-50/40";
  if (level === "high") return "bg-orange-50/30";
  return "";
}

/** Pause badge — Jinja `at_risk_list.html:82-88` ile aynı (P4'teki pattern'le tutarlı). */
export function PauseBadge({
  reason,
  size = "sm",
}: {
  reason: string | null;
  size?: "xs" | "sm";
}) {
  const cls =
    size === "xs"
      ? "text-[10px] px-1.5 py-0.5"
      : "text-[10px] px-1.5 py-0.5";
  if (reason && reason.startsWith("auto")) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded border bg-amber-50 text-amber-800 border-amber-300",
          cls,
        )}
        title="Otomatik pasif — uyarılar susturulmuş"
      >
        🤖 pasif
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border bg-muted text-foreground/70 border-border",
        cls,
      )}
      title="Manuel pasif — uyarılar susturulmuş"
    >
      ⏸ pasif
    </span>
  );
}
