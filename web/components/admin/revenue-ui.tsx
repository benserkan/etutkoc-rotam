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
  rose: "border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100",
  amber: "border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100",
  emerald: "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100",
  indigo: "border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100",
  slate: "border-slate-300 bg-slate-50 text-slate-800 hover:bg-slate-100",
};
export function suggestBtnTone(color: string): string {
  return SUGGEST_BTN[color] ?? SUGGEST_BTN.indigo;
}

/** Sinyal/severity badge + kart kenarı tonları (statik). */
const SEV_BADGE: Record<string, string> = {
  rose: "bg-rose-100 text-rose-800",
  amber: "bg-amber-100 text-amber-800",
  emerald: "bg-emerald-100 text-emerald-800",
  slate: "bg-slate-100 text-slate-800",
};
const SEV_CARD: Record<string, string> = {
  rose: "border-rose-200",
  amber: "border-amber-200",
  emerald: "border-emerald-200",
  slate: "border-slate-200",
};
const SEV_HEAD: Record<string, string> = {
  rose: "bg-rose-50/50 border-rose-100",
  amber: "bg-amber-50/50 border-amber-100",
  emerald: "bg-emerald-50/50 border-emerald-100",
  slate: "bg-slate-50/50 border-slate-100",
};
const SEV_SCORE: Record<string, string> = {
  rose: "bg-rose-100 text-rose-800",
  amber: "bg-amber-100 text-amber-800",
  emerald: "bg-emerald-100 text-emerald-800",
  slate: "bg-slate-100 text-slate-800",
};
export const sevBadge = (t: string) => SEV_BADGE[t] ?? SEV_BADGE.slate;
export const sevCard = (t: string) => SEV_CARD[t] ?? SEV_CARD.slate;
export const sevHead = (t: string) => SEV_HEAD[t] ?? SEV_HEAD.slate;
export const sevScore = (t: string) => SEV_SCORE[t] ?? SEV_SCORE.slate;

/** Kohort heatmap hücre tonları (revenue_cohort _rate_color ile aynı 6 ton). */
const COHORT_CELL: Record<string, string> = {
  emerald: "bg-emerald-100 text-emerald-800",
  lime: "bg-lime-100 text-lime-800",
  amber: "bg-amber-100 text-amber-800",
  orange: "bg-orange-100 text-orange-800",
  rose: "bg-rose-100 text-rose-800",
  slate: "bg-slate-50 text-slate-300",
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
