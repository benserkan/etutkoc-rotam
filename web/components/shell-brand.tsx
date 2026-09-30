import Link from "next/link";

import { BrandLogo } from "@/components/brand-logo";
import { cn } from "@/lib/utils";
import type { BrandRef } from "@/lib/types/me";

/**
 * Panel markası (kurumsal kimlik).
 *
 * Kuruma bağlı kullanıcı (kurum yöneticisi, öğretmen, öğrenci, veli) sistemi
 * KURUMUN markasıyla görür: logo varsa kurum logosu, yoksa kurum adı; altında
 * küçük "ETÜTKOÇ Rotam altyapısı" notu (ETÜTKOÇ logosu gösterilmez). Kurumsuz
 * kullanıcıda ETÜTKOÇ Rotam markası.
 *
 * Logo herkese açık `/api/v2/brand/logo/{id}` ucundan (marka varlığı).
 */
export function ShellBrand({
  brand,
  href,
  size = 28,
  onDark = false,
  className,
  showPlatformNote = true,
}: {
  brand: BrandRef | null | undefined;
  href: string;
  size?: number;
  onDark?: boolean;
  className?: string;
  showPlatformNote?: boolean;
}) {
  if (!brand) {
    return (
      <BrandLogo
        href={href}
        size={size}
        className={className}
        wordmarkClassName={onDark ? "text-white" : undefined}
      />
    );
  }
  return (
    <Link
      href={href}
      aria-label={brand.name}
      title={brand.name}
      className={cn("inline-flex min-w-0 flex-col justify-center gap-0.5", className)}
      data-testid="shell-brand"
    >
      {brand.logo_url ? (
        // eslint-disable-next-line @next/next/no-img-element -- kurum logosu (dinamik, herkese açık uç)
        <img
          src={brand.logo_url}
          alt={brand.name}
          className={cn(
            "block h-8 w-auto max-w-[190px] object-contain",
            onDark && "rounded-md bg-white px-1.5 py-0.5",
          )}
        />
      ) : (
        <span
          className={cn(
            "font-display text-base font-bold leading-tight break-words",
            onDark ? "text-white" : "text-foreground",
          )}
        >
          {brand.name}
        </span>
      )}
      {showPlatformNote ? (
        <span
          className={cn(
            "text-[10px] leading-none",
            onDark ? "text-white/70" : "text-muted-foreground",
          )}
        >
          ETÜTKOÇ Rotam altyapısı
        </span>
      ) : null}
    </Link>
  );
}
