import Image from "next/image";

import { cn } from "@/lib/utils";

/**
 * Güvenli ödeme rozetleri — iyzico'nun RESMİ footer logo bandı (iyzico ile Öde +
 * Mastercard + Visa + Troy). iyzico sanal POS başvurusunun "Web sitesi kriterleri"
 * gereği anasayfada Visa + Mastercard + "iyzico ile Öde" logoları bulunmalı.
 *
 * Logolar iyzico resmi logo paketinden (docs.iyzico.com/ek-bilgiler/iyzico-logo-paketi)
 * alınan orijinal SVG bandıdır → public/iyzico/ altında. Caddy `/iyzico/*` rotası
 * bu dosyaları next:3000'e yönlendirir. next/image `unoptimized` ile public yolundan
 * servis edilir (BrandLogo deseni; SVG optimizasyonu/lint sorunu yok).
 *
 * `variant`:
 *  - "dark"  → koyu zemin (footer cyan-950) → beyaz bant
 *  - "light" → açık zemin (pricing vb.) → renkli bant
 */

// Resmi bant en-boy oranı: 429 × 32.
const BAND_W = 429;
const BAND_H = 32;

export function PaymentMethods({
  variant = "dark",
  className,
}: {
  variant?: "dark" | "light";
  className?: string;
}) {
  const dark = variant === "dark";
  const src = dark ? "/iyzico/logo-band-white.svg" : "/iyzico/logo-band-colored.svg";
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <Image
        src={src}
        alt="Güvenli ödeme — iyzico ile Öde · Mastercard · Visa · Troy"
        width={BAND_W}
        height={BAND_H}
        unoptimized
        className="h-7 w-auto max-w-full sm:h-8"
      />
      <p
        className={cn(
          "text-[11px] leading-relaxed",
          dark ? "text-cyan-200/50" : "text-slate-500",
        )}
      >
        Ödemeler iyzico altyapısı ile 256-bit SSL ve 3D Secure korumasıyla alınır.
      </p>
    </div>
  );
}
