/**
 * Türkçe locale formatter'ları — tek nokta tutarlılık.
 *
 * [[feedback_simple_language]] — sade Türkçe + jargon önce yasak.
 * Tarih + sayı + para formatları bu modülden geçer.
 */

const TR = "tr-TR";

export const fmtDate = new Intl.DateTimeFormat(TR, {
  year: "numeric",
  month: "long",
  day: "numeric",
});

export const fmtDateShort = new Intl.DateTimeFormat(TR, {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export const fmtTime = new Intl.DateTimeFormat(TR, {
  hour: "2-digit",
  minute: "2-digit",
});

export const fmtDateTime = new Intl.DateTimeFormat(TR, {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export const fmtRelative = new Intl.RelativeTimeFormat(TR, {
  numeric: "auto",
});

export const fmtNumber = new Intl.NumberFormat(TR);

export const fmtPercent = new Intl.NumberFormat(TR, {
  style: "percent",
  maximumFractionDigits: 0,
});

export const fmtCurrency = new Intl.NumberFormat(TR, {
  style: "currency",
  currency: "TRY",
  maximumFractionDigits: 0,
});

/**
 * "2026-05-18T14:30:00Z" → "18 Mayıs 2026"
 */
export function formatDate(iso: string | Date | null | undefined): string {
  if (!iso) return "—";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (isNaN(d.getTime())) return "—";
  return fmtDate.format(d);
}

/**
 * Sadece-gün ISO string ("2026-05-18") → kısa Türkçe ("18.05.2026")
 */
export function formatDateShort(iso: string | Date | null | undefined): string {
  if (!iso) return "—";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (isNaN(d.getTime())) return "—";
  return fmtDateShort.format(d);
}

export function formatDateTime(iso: string | Date | null | undefined): string {
  if (!iso) return "—";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (isNaN(d.getTime())) return "—";
  return fmtDateTime.format(d);
}

/** "Bugün" / "Dün" / "3 gün önce" — şimdiki tarihe göre relatif. */
export function formatRelative(iso: string | Date | null | undefined): string {
  if (!iso) return "—";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (isNaN(d.getTime())) return "—";
  const diffMs = d.getTime() - Date.now();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (Math.abs(diffDays) >= 1) return fmtRelative.format(diffDays, "day");
  const diffHours = Math.round(diffMs / (1000 * 60 * 60));
  if (Math.abs(diffHours) >= 1) return fmtRelative.format(diffHours, "hour");
  const diffMin = Math.round(diffMs / (1000 * 60));
  return fmtRelative.format(diffMin, "minute");
}
