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
  critical: "bg-rose-50 text-rose-700 border-rose-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200",
  info: "bg-sky-50 text-sky-700 border-sky-200",
};
const SEVERITY_CARD: Record<string, string> = {
  critical: "border-l-rose-500 bg-rose-50/40",
  warn: "border-l-amber-500 bg-amber-50/40",
  info: "border-l-sky-500 bg-sky-50/40",
};
const SEVERITY_ICON: Record<string, LucideIcon> = {
  critical: ShieldAlert,
  warn: AlertTriangle,
  info: Info,
};
const SEVERITY_ICON_COLOR: Record<string, string> = {
  critical: "text-rose-600",
  warn: "text-amber-600",
  info: "text-sky-600",
};
export const SEVERITY_LABEL: Record<string, string> = {
  critical: "Kritik",
  warn: "Uyarı",
  info: "Bilgi",
};

// level: ok / warn / critical / error / unknown / never / disabled / pending
const LEVEL_BADGE: Record<string, string> = {
  ok: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200",
  critical: "bg-rose-50 text-rose-700 border-rose-200",
  error: "bg-rose-50 text-rose-700 border-rose-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  never: "bg-slate-100 text-slate-600 border-slate-200",
  disabled: "bg-slate-100 text-slate-500 border-slate-200",
  unknown: "bg-slate-100 text-slate-600 border-slate-200",
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
  if (v >= 95) return "text-emerald-600";
  if (v >= 80) return "text-amber-600";
  return "text-rose-600";
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
  emerald: "bg-emerald-100 text-emerald-800 border-emerald-200",
  amber: "bg-amber-100 text-amber-800 border-amber-200",
  rose: "bg-rose-100 text-rose-800 border-rose-200",
  slate: "bg-slate-100 text-slate-700 border-slate-200",
  yellow: "bg-yellow-100 text-yellow-800 border-yellow-200",
  indigo: "bg-indigo-100 text-indigo-800 border-indigo-200",
  sky: "bg-sky-100 text-sky-800 border-sky-200",
  purple: "bg-purple-100 text-purple-800 border-purple-200",
  blue: "bg-blue-100 text-blue-800 border-blue-200",
  cyan: "bg-cyan-100 text-cyan-800 border-cyan-200",
  violet: "bg-violet-100 text-violet-800 border-violet-200",
  fuchsia: "bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200",
  orange: "bg-orange-100 text-orange-800 border-orange-200",
};

const TONE_TEXT: Record<string, string> = {
  emerald: "text-emerald-700",
  amber: "text-amber-700",
  rose: "text-rose-700",
  slate: "text-slate-600",
  yellow: "text-yellow-700",
  indigo: "text-indigo-700",
  sky: "text-sky-700",
  purple: "text-purple-700",
  blue: "text-blue-700",
  cyan: "text-cyan-700",
  violet: "text-violet-700",
  fuchsia: "text-fuchsia-700",
  orange: "text-orange-700",
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
