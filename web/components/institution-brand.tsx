import { Building2 } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Kurum co-branding — kurum logosu (varsa) + adı; logo yoksa Building2 ikonlu
 * çip. Kurum yöneticisi + kuruma bağlı öğretmen panellerinde "hangi kuruma
 * aitim" bilgisini gösterir. Bağımsız koçta institution=null → hiç render
 * edilmez (yalnız platform markası kalır).
 *
 * Logo KENDİ ORANINDA gösterilir (2026-09-28): önceki 16×16 kare yatay
 * logoları okunmaz hale getiriyordu. Kurum adı kırpılmaz, sarar.
 * `compact` → üst çubuk: yalnız logo (ad title/alt'ta); logo yoksa çip.
 *
 * Logo same-origin `<img>` (cookie auth ile serve ucu).
 */
export function InstitutionBrand({
  institution,
  className,
  compact = false,
}: {
  institution: { id: number; name: string; has_logo?: boolean; logo_url?: string | null };
  className?: string;
  compact?: boolean;
}) {
  const hasLogo = !!institution.has_logo && !!institution.logo_url;

  if (hasLogo) {
    return (
      <div className={cn("min-w-0", className)} title={institution.name} data-testid="institution-brand">
        {/* eslint-disable-next-line @next/next/no-img-element -- cookie-auth'lu same-origin logo ucu */}
        <img
          src={institution.logo_url as string}
          alt={institution.name}
          className={cn(
            "block w-auto max-w-full rounded-md object-contain",
            compact ? "h-7" : "h-9",
          )}
        />
        {compact ? null : (
          <span className="mt-1 block text-[11px] leading-snug text-muted-foreground break-words">
            {institution.name}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "inline-flex max-w-full items-start gap-1.5 rounded-lg border px-2 py-1 text-[11px] font-medium leading-snug",
        "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
        className,
      )}
      title={institution.name}
      data-testid="institution-brand"
    >
      <Building2 className="mt-px size-3 shrink-0" aria-hidden />
      <span className="break-words">{institution.name}</span>
    </div>
  );
}
