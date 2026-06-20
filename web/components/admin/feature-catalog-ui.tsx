"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Vitrin Kataloğu paylaşılan görsel yardımcıları.
 *
 * Tailwind v4 JIT, `bg-${tone}-50` gibi interpolasyonu purge eder; bu yüzden
 * tüm ton sınıfları STATİK string olarak burada tanımlı (literal görünür).
 */

const BADGE_TONES: Record<string, string> = {
  slate: "bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-200",
  emerald: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  rose: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
  indigo: "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
  blue: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-200",
  teal: "bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-500/10 dark:border-teal-500/30 dark:text-teal-200",
  stone: "bg-stone-100 text-stone-600 border-stone-200",
};

const SOLID_TONES: Record<string, string> = {
  slate: "bg-slate-100 text-slate-700",
  emerald: "bg-emerald-600 text-white",
  amber: "bg-amber-500 text-white",
  rose: "bg-rose-600 text-white",
  indigo: "bg-indigo-600 text-white",
};

/** Anomali kutusu (severity → bg + border + metin). */
const ANOMALY_TONES: Record<string, string> = {
  rose: "border-rose-200 bg-rose-50 dark:bg-rose-500/10 dark:border-rose-500/30",
  amber: "border-amber-200 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30",
  slate: "border-slate-200 bg-slate-50 dark:bg-slate-500/10 dark:border-slate-500/30",
  emerald: "border-emerald-200 bg-emerald-50 dark:bg-emerald-500/10 dark:border-emerald-500/30",
};
const ANOMALY_TITLE: Record<string, string> = {
  rose: "text-rose-800",
  amber: "text-amber-800",
  slate: "text-slate-800",
  emerald: "text-emerald-800",
};
const ANOMALY_HINT: Record<string, string> = {
  rose: "text-rose-700",
  amber: "text-amber-700",
  slate: "text-slate-600",
  emerald: "text-emerald-700",
};

export function badgeTone(tone: string): string {
  return BADGE_TONES[tone] ?? BADGE_TONES.slate;
}

export function anomalyBox(tone: string): string {
  return ANOMALY_TONES[tone] ?? ANOMALY_TONES.slate;
}
export function anomalyTitle(tone: string): string {
  return ANOMALY_TITLE[tone] ?? ANOMALY_TITLE.slate;
}
export function anomalyHint(tone: string): string {
  return ANOMALY_HINT[tone] ?? ANOMALY_HINT.slate;
}

/** Vitrin skoru → ton (Jinja: ≥70 emerald · ≥45 amber · <45 rose). */
export function scoreTone(p: number): string {
  if (p >= 70) return "emerald";
  if (p >= 45) return "amber";
  return "rose";
}

/** Çeşitlilik yüzdesi → ton (Jinja: ≥75 emerald · ≥50 amber · <50 rose). */
export function diversityTone(pct: number): string {
  if (pct >= 75) return "emerald";
  if (pct >= 50) return "amber";
  return "rose";
}

export function StatusBadge({
  label,
  tone,
  className,
}: {
  label: string;
  tone: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        badgeTone(tone),
        className,
      )}
    >
      {label}
    </span>
  );
}

export function SolidBadge({
  label,
  tone,
  className,
}: {
  label: string;
  tone: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold",
        SOLID_TONES[tone] ?? SOLID_TONES.slate,
        className,
      )}
    >
      {label}
    </span>
  );
}

/** Native form input — paylaşılan Tailwind class'ı. */
export const fieldClass =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent";
