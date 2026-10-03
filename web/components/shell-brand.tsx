"use client";

import * as React from "react";
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
  variant = "bar",
}: {
  brand: BrandRef | null | undefined;
  href: string;
  size?: number;
  onDark?: boolean;
  className?: string;
  showPlatformNote?: boolean;
  /**
   * sidebar = sol menü başı (geniş alan → büyük logo) · bar = üst çubuk
   * (dar yükseklik). Kare logolar küçük yükseklikte okunmaz; bu yüzden
   * yükseklik varyanta göre ayrı.
   */
  variant?: "sidebar" | "bar";
}) {
  const sidebar = variant === "sidebar";
  if (brand && sidebar) {
    return <SidebarBrandCard brand={brand} href={href} className={className} />;
  }
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
            "block w-auto object-contain",
            sidebar ? "h-16 max-w-[210px]" : "h-10 max-w-[180px]",
            onDark && "rounded-md bg-white px-1.5 py-0.5",
          )}
        />
      ) : (
        <span
          className={cn(
            "font-display font-bold leading-tight break-words",
            sidebar ? "text-lg" : "text-base",
            onDark ? "text-white" : "text-foreground",
          )}
        >
          {brand.name}
        </span>
      )}
      {showPlatformNote ? (
        <span
          className={cn(
            "text-[10px] leading-none whitespace-nowrap",
            onDark ? "text-white/70" : "text-muted-foreground",
          )}
        >
          ETÜTKOÇ Rotam altyapısı
        </span>
      ) : null}
    </Link>
  );
}

/** Kurum adının baş harfleri (logo yoksa monogram karosu). */
function initials(name: string): string {
  const parts = name
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter(Boolean);
  return parts
    .slice(0, 2)
    .map((w) => w.charAt(0).toLocaleUpperCase("tr-TR"))
    .join("");
}

/**
 * Sol menü başındaki kurum kartı.
 *
 * Kare/yuvarlak logo → beyaz karo + yanında kurum adı (tema fark etmeksizin
 * logo kendi zemininde durur, koyu temada "beyaz kutu" gibi yüzmez).
 * Yatay (geniş) logo → tam genişlik beyaz şerit; logo zaten adı içerir.
 * Logo yok → kurum rengiyle monogram karo + ad. Altyapı notu tek satır.
 */
function SidebarBrandCard({
  brand,
  href,
  className,
}: {
  brand: BrandRef;
  href: string;
  className?: string;
}) {
  const [wide, setWide] = React.useState(false);
  const logo = brand.logo_url;
  const measure = React.useCallback((img: HTMLImageElement) => {
    if (img.naturalHeight > 0 && img.naturalWidth / img.naturalHeight >= 1.8) setWide(true);
  }, []);

  const platformNote = (
    <span className="block whitespace-nowrap text-[10.5px] leading-tight text-muted-foreground">
      Altyapı: ETÜTKOÇ Rotam
    </span>
  );

  if (logo && wide) {
    return (
      <Link
        href={href}
        aria-label={brand.name}
        title={brand.name}
        data-testid="shell-brand"
        className={cn("block w-full min-w-0 space-y-1.5", className)}
      >
        <span className="flex h-16 w-full items-center justify-center rounded-xl bg-card px-3 shadow-sm ring-1 ring-black/5">
          {/* eslint-disable-next-line @next/next/no-img-element -- kurum logosu (dinamik, herkese açık uç) */}
          <img src={logo} alt={brand.name} className="block max-h-12 max-w-full object-contain" />
        </span>
        {platformNote}
      </Link>
    );
  }

  return (
    <Link
      href={href}
      aria-label={brand.name}
      title={brand.name}
      data-testid="shell-brand"
      className={cn(
        "group flex w-full min-w-0 items-center gap-3 rounded-xl p-1.5 -m-1.5 transition-colors hover:bg-muted/60",
        className,
      )}
    >
      {logo ? (
        <span className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-card p-1 shadow-sm ring-1 ring-black/5">
          {/* eslint-disable-next-line @next/next/no-img-element -- kurum logosu (dinamik, herkese açık uç) */}
          <img
            src={logo}
            alt=""
            className="block max-h-full max-w-full object-contain"
            ref={(el) => {
              // Hidrasyondan önce yüklenen görselde onLoad tetiklenmez → ref'te de ölç.
              if (el?.complete) measure(el);
            }}
            onLoad={(e) => measure(e.currentTarget)}
          />
        </span>
      ) : (
        <span
          aria-hidden
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-cyan-700 font-display text-lg font-bold text-white shadow-sm"
        >
          {initials(brand.name)}
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block font-display text-[15px] font-bold leading-snug text-foreground break-words">
          {brand.name}
        </span>
        <span className="mt-1 block">{platformNote}</span>
      </span>
    </Link>
  );
}
