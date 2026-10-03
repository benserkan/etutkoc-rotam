"use client";

import * as React from "react";
import {
  CircleEllipsis,
  Gift,
  GraduationCap,
  Mail,
  MessageCircle,
  Phone,
  Users,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Ticari Pano paylaşılan görsel yardımcıları.
 *
 * Emoji yok — backend `kind`/`color` alanları Lucide ikon + statik Tailwind
 * sınıfına map'lenir (purge güvenli literal string'ler).
 */

/** CRM aksiyon türü → Lucide ikon (action_center SuggestedAction.kind). */
export const ACTION_KIND_ICON: Record<string, LucideIcon> = {
  call: Phone,
  email: Mail,
  whatsapp: MessageCircle,
  meeting: Users,
  offer_sent: Gift,
  onboarding: GraduationCap,
  other: CircleEllipsis,
};

export function actionKindIcon(kind: string): LucideIcon {
  return ACTION_KIND_ICON[kind] ?? CircleEllipsis;
}

/** Sinyal severity → ton. */
export function severityTone(sev: string): string {
  switch (sev) {
    case "critical":
      return "rose";
    case "high":
      return "amber";
    case "positive":
      return "emerald";
    default:
      return "slate";
  }
}

export const SEVERITY_LABEL: Record<string, string> = {
  critical: "KRİTİK",
  high: "YÜKSEK",
  medium: "ORTA",
  low: "DÜŞÜK",
  positive: "POZİTİF",
};

/** Önerilen aksiyon buton tonları (statik — Tailwind purge güvenli). */
const SUGGEST_BTN: Record<string, string> = {
  rose: "border-rose-300 bg-rose-50 dark:bg-rose-500/15 dark:border-rose-500/30 text-rose-800 dark:text-rose-200 hover:bg-rose-100",
  amber: "border-amber-300 bg-amber-50 dark:bg-amber-500/15 dark:border-amber-500/30 text-amber-800 dark:text-amber-200 hover:bg-amber-100",
  emerald: "border-emerald-300 bg-emerald-50 dark:bg-emerald-500/15 dark:border-emerald-500/30 text-emerald-800 dark:text-emerald-200 hover:bg-emerald-100",
  indigo: "border-indigo-300 bg-indigo-50 dark:bg-indigo-500/15 dark:border-indigo-500/30 text-indigo-800 dark:text-indigo-200 hover:bg-indigo-100",
  slate: "border-slate-300 bg-slate-50 dark:bg-slate-500/15 dark:border-slate-500/30 text-slate-800 dark:text-slate-200 hover:bg-slate-100",
};
export function suggestBtnTone(color: string): string {
  return SUGGEST_BTN[color] ?? SUGGEST_BTN.indigo;
}

/** Sinyal/severity badge + kart kenarı tonları (statik). */
const SEV_BADGE: Record<string, string> = {
  rose: "bg-rose-100 dark:bg-rose-500/15 text-rose-800 dark:text-rose-200",
  amber: "bg-amber-100 dark:bg-amber-500/15 text-amber-800 dark:text-amber-200",
  emerald: "bg-emerald-100 dark:bg-emerald-500/15 text-emerald-800 dark:text-emerald-200",
  slate: "bg-slate-100 dark:bg-slate-500/15 text-slate-800 dark:text-slate-200",
};
const SEV_CARD: Record<string, string> = {
  rose: "border-rose-200",
  amber: "border-amber-200",
  emerald: "border-emerald-200",
  slate: "border-slate-200",
};
const SEV_HEAD: Record<string, string> = {
  rose: "bg-rose-50/50 dark:bg-rose-500/10 border-rose-100",
  amber: "bg-amber-50/50 dark:bg-amber-500/10 border-amber-100",
  emerald: "bg-emerald-50/50 dark:bg-emerald-500/10 border-emerald-100",
  slate: "bg-slate-50/50 dark:bg-slate-500/10 border-slate-100",
};
const SEV_SCORE: Record<string, string> = {
  rose: "bg-rose-100 dark:bg-rose-500/15 text-rose-800 dark:text-rose-200",
  amber: "bg-amber-100 dark:bg-amber-500/15 text-amber-800 dark:text-amber-200",
  emerald: "bg-emerald-100 dark:bg-emerald-500/15 text-emerald-800 dark:text-emerald-200",
  slate: "bg-slate-100 dark:bg-slate-500/15 text-slate-800 dark:text-slate-200",
};
export const sevBadge = (t: string) => SEV_BADGE[t] ?? SEV_BADGE.slate;
export const sevCard = (t: string) => SEV_CARD[t] ?? SEV_CARD.slate;
export const sevHead = (t: string) => SEV_HEAD[t] ?? SEV_HEAD.slate;
export const sevScore = (t: string) => SEV_SCORE[t] ?? SEV_SCORE.slate;

/** Kohort heatmap hücre tonları (revenue_cohort _rate_color ile aynı 6 ton). */
const COHORT_CELL: Record<string, string> = {
  emerald: "bg-emerald-100 dark:bg-emerald-500/15 text-emerald-800 dark:text-emerald-200",
  lime: "bg-lime-100 dark:bg-lime-500/15 text-lime-800 dark:text-lime-200",
  amber: "bg-amber-100 dark:bg-amber-500/15 text-amber-800 dark:text-amber-200",
  orange: "bg-orange-100 dark:bg-orange-500/15 text-orange-800 dark:text-orange-200",
  rose: "bg-rose-100 dark:bg-rose-500/15 text-rose-800 dark:text-rose-200",
  slate: "bg-slate-50 dark:bg-slate-500/15 text-slate-300",
};
export function cohortCell(color: string): string {
  return COHORT_CELL[color] ?? COHORT_CELL.slate;
}

/** Türk Lirası biçimi: 12.345 ₺ */
export function tl(n: number): string {
  return `${Math.round(n).toLocaleString("tr-TR")} ₺`;
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone = severityTone(severity);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold",
        sevBadge(tone),
      )}
    >
      {SEVERITY_LABEL[severity] ?? severity.toUpperCase()}
    </span>
  );
}
