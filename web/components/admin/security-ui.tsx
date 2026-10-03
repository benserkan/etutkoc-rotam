"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Güvenlik Kamarası (G2a) paylaşılan görsel yardımcıları.
 *
 * Tailwind v4 JIT `bg-${x}` interpolasyonunu purge eder; tüm ton sınıfları
 * STATİK literal string olarak tanımlı. Emoji yok — Lucide ikon kullanılır.
 */

// severity: critical / warn / info
const SEVERITY_BADGE: Record<string, string> = {
  critical: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  info: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
};
const SEVERITY_CARD: Record<string, string> = {
  critical: "border-l-rose-500 bg-rose-50/40 dark:bg-rose-500/10",
  warn: "border-l-amber-500 bg-amber-50/40 dark:bg-amber-500/10",
  info: "border-l-sky-500 bg-sky-50/40 dark:bg-sky-500/10",
};
const SEVERITY_ICON: Record<string, LucideIcon> = {
  critical: ShieldAlert,
  warn: AlertTriangle,
  info: Info,
};
const SEVERITY_ICON_COLOR: Record<string, string> = {
  critical: "text-rose-600 dark:text-rose-300",
  warn: "text-amber-600 dark:text-amber-300",
  info: "text-sky-600 dark:text-sky-300",
};
export const SEVERITY_LABEL: Record<string, string> = {
  critical: "Kritik",
  warn: "Uyarı",
  info: "Bilgi",
};

// level: ok / warn / critical / error / unknown / never / disabled / pending
const LEVEL_BADGE: Record<string, string> = {
  ok: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  critical: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
  error: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  never: "bg-slate-100 dark:bg-slate-500/15 dark:border-slate-500/30 text-slate-600 dark:text-slate-300 border-slate-200",
  disabled: "bg-slate-100 dark:bg-slate-500/15 dark:border-slate-500/30 text-slate-500 border-slate-200",
  unknown: "bg-slate-100 dark:bg-slate-500/15 dark:border-slate-500/30 text-slate-600 dark:text-slate-300 border-slate-200",
};
export const LEVEL_LABEL: Record<string, string> = {
  ok: "Sağlıklı",
  warn: "Uyarı",
  critical: "Kritik",
  error: "Hata",
  pending: "Beklemede",
  never: "Hiç çalışmadı",
  disabled: "Kapalı",
  unknown: "Bilinmiyor",
};

export function severityBadgeClass(sev: string): string {
  return SEVERITY_BADGE[sev] ?? SEVERITY_BADGE.info;
}
export function severityCardClass(sev: string): string {
  return SEVERITY_CARD[sev] ?? SEVERITY_CARD.info;
}
export function severityIcon(sev: string): LucideIcon {
  return SEVERITY_ICON[sev] ?? Info;
}
export function severityIconColor(sev: string): string {
  return SEVERITY_ICON_COLOR[sev] ?? SEVERITY_ICON_COLOR.info;
}
export function levelBadgeClass(level: string): string {
  return LEVEL_BADGE[level] ?? LEVEL_BADGE.unknown;
}

export function SeverityBadge({ sev }: { sev: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        severityBadgeClass(sev),
      )}
    >
      {SEVERITY_LABEL[sev] ?? sev}
    </span>
  );
}

export function LevelBadge({ level }: { level: string }) {
  const ok = level === "ok";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        levelBadgeClass(level),
      )}
    >
      {ok ? <CheckCircle2 className="size-3" aria-hidden /> : null}
      {LEVEL_LABEL[level] ?? level}
    </span>
  );
}

/** saniye → "az önce / N dk / N saat / N gün önce" (TR). */
export function humanizeAgo(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return "az önce";
  if (s < 3600) return `${Math.floor(s / 60)} dk önce`;
  if (s < 86400) return `${Math.floor(s / 3600)} saat önce`;
  return `${Math.floor(s / 86400)} gün önce`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("tr-TR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16);
  }
}

export function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `%${v.toFixed(1)}`;
}

/** Başarı yüzdesine göre metin rengi. */
export function successPctColor(v: number | null | undefined): string {
  if (v == null) return "text-muted-foreground";
  if (v >= 95) return "text-emerald-600 dark:text-emerald-300";
  if (v >= 80) return "text-amber-600 dark:text-amber-300";
  return "text-rose-600 dark:text-rose-300";
}

// =============================================================================
// G2b — band_color / role color statik tonları (Tailwind purge-safe)
// Servis "emerald|amber|rose|slate|yellow|indigo|sky|purple|..." döndürür.
// =============================================================================

const TONE_DOT: Record<string, string> = {
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
  slate: "bg-slate-400",
  yellow: "bg-yellow-500",
  indigo: "bg-indigo-500",
  sky: "bg-sky-500",
  purple: "bg-purple-500",
  blue: "bg-blue-500",
  cyan: "bg-cyan-500",
  violet: "bg-violet-500",
  fuchsia: "bg-fuchsia-500",
  orange: "bg-orange-500",
};

const TONE_BADGE: Record<string, string> = {
  emerald: "bg-emerald-100 dark:bg-emerald-500/15 dark:border-emerald-500/30 text-emerald-800 dark:text-emerald-200 border-emerald-200",
  amber: "bg-amber-100 dark:bg-amber-500/15 dark:border-amber-500/30 text-amber-800 dark:text-amber-200 border-amber-200",
  rose: "bg-rose-100 dark:bg-rose-500/15 dark:border-rose-500/30 text-rose-800 dark:text-rose-200 border-rose-200",
  slate: "bg-slate-100 dark:bg-slate-500/15 dark:border-slate-500/30 text-slate-700 dark:text-slate-300 border-slate-200",
  yellow: "bg-yellow-100 dark:bg-yellow-500/15 dark:border-yellow-500/30 text-yellow-800 dark:text-yellow-200 border-yellow-200",
  indigo: "bg-indigo-100 dark:bg-indigo-500/15 dark:border-indigo-500/30 text-indigo-800 dark:text-indigo-200 border-indigo-200",
  sky: "bg-sky-100 dark:bg-sky-500/15 dark:border-sky-500/30 text-sky-800 dark:text-sky-200 border-sky-200",
  purple: "bg-purple-100 dark:bg-purple-500/15 dark:border-purple-500/30 text-purple-800 dark:text-purple-200 border-purple-200",
  blue: "bg-blue-100 dark:bg-blue-500/15 dark:border-blue-500/30 text-blue-800 dark:text-blue-200 border-blue-200",
  cyan: "bg-cyan-100 dark:bg-cyan-500/15 dark:border-cyan-500/30 text-cyan-800 dark:text-cyan-200 border-cyan-200",
  violet: "bg-violet-100 dark:bg-violet-500/15 dark:border-violet-500/30 text-violet-800 dark:text-violet-200 border-violet-200",
  fuchsia: "bg-fuchsia-100 dark:bg-fuchsia-500/15 dark:border-fuchsia-500/30 text-fuchsia-800 dark:text-fuchsia-200 border-fuchsia-200",
  orange: "bg-orange-100 dark:bg-orange-500/15 dark:border-orange-500/30 text-orange-800 dark:text-orange-200 border-orange-200",
};

const TONE_TEXT: Record<string, string> = {
  emerald: "text-emerald-700 dark:text-emerald-300",
  amber: "text-amber-700 dark:text-amber-300",
  rose: "text-rose-700 dark:text-rose-300",
  slate: "text-slate-600 dark:text-slate-300",
  yellow: "text-yellow-700 dark:text-yellow-300",
  indigo: "text-indigo-700 dark:text-indigo-300",
  sky: "text-sky-700 dark:text-sky-300",
  purple: "text-purple-700 dark:text-purple-300",
  blue: "text-blue-700 dark:text-blue-300",
  cyan: "text-cyan-700 dark:text-cyan-300",
  violet: "text-violet-700 dark:text-violet-300",
  fuchsia: "text-fuchsia-700 dark:text-fuchsia-300",
  orange: "text-orange-700 dark:text-orange-300",
};

export function toneDot(color: string): string {
  return TONE_DOT[color] ?? TONE_DOT.slate;
}
export function toneBadge(color: string): string {
  return TONE_BADGE[color] ?? TONE_BADGE.slate;
}
export function toneText(color: string): string {
  return TONE_TEXT[color] ?? TONE_TEXT.slate;
}
