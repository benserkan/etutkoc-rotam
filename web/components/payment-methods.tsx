import { ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Güvenli ödeme rozetleri — iyzico altyapısı + kabul edilen kart şemaları
 * (Visa / Mastercard). iyzico sanal POS başvurusunun "Web sitesi kriterleri"
 * gereği anasayfada Visa + Mastercard + "iyzico ile Öde" logoları bulunmalı.
 *
 * Logolar harici dosya yerine satır-içi SVG olarak çizilir → public/ altına yeni
 * statik dosya + Caddy rotası gerekmez (CLAUDE.md statik-varlık notu). Her logo
 * beyaz yuvarlak çip içinde → koyu footer zemininde de net okunur.
 */

function CardChip({
  children,
  label,
  className,
}: {
  children: React.ReactNode;
  label: string;
  className?: string;
}) {
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex h-9 w-[58px] items-center justify-center rounded-md bg-white px-2 shadow-sm ring-1 ring-black/5",
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Visa — resmi mavi (#1434CB) wordmark. */
function VisaLogo() {
  return (
    <CardChip label="Visa">
      <svg viewBox="0 0 48 16" className="h-4 w-full" aria-hidden>
        <text
          x="24"
          y="13.5"
          textAnchor="middle"
          fontFamily="Arial, Helvetica, sans-serif"
          fontWeight="700"
          fontStyle="italic"
          fontSize="15"
          letterSpacing="0.5"
          fill="#1434CB"
        >
          VISA
        </text>
      </svg>
    </CardChip>
  );
}

/** Mastercard — iç içe iki daire (kırmızı + turuncu) + wordmark. */
function MastercardLogo() {
  return (
    <CardChip label="Mastercard">
      <svg viewBox="0 0 40 30" className="h-6 w-full" aria-hidden>
        <circle cx="15" cy="11" r="9" fill="#EB001B" />
        <circle cx="25" cy="11" r="9" fill="#F79E1B" />
        <path
          d="M20 4.2a9 9 0 0 1 0 13.6 9 9 0 0 1 0-13.6Z"
          fill="#FF5F00"
        />
        <text
          x="20"
          y="28"
          textAnchor="middle"
          fontFamily="Arial, Helvetica, sans-serif"
          fontWeight="700"
          fontSize="6"
          letterSpacing="0.2"
          fill="#1A1A1A"
        >
          mastercard
        </text>
      </svg>
    </CardChip>
  );
}

/** iyzico — "iyzico" wordmark (resmi lacivert tonu + turkuaz vurgu). */
function IyzicoLogo() {
  return (
    <CardChip label="iyzico ile Öde" className="w-[72px]">
      <svg viewBox="0 0 82 22" className="h-4 w-full" aria-hidden>
        <text
          x="0"
          y="17"
          fontFamily="Arial, Helvetica, sans-serif"
          fontWeight="800"
          fontSize="18"
          letterSpacing="-0.5"
          fill="#1E064A"
        >
          iyzic
        </text>
        <text
          x="58"
          y="17"
          fontFamily="Arial, Helvetica, sans-serif"
          fontWeight="800"
          fontSize="18"
          letterSpacing="-0.5"
          fill="#00BDC4"
        >
          o
        </text>
      </svg>
    </CardChip>
  );
}

/**
 * Anasayfa footer'ında gösterilen güvenli ödeme şeridi.
 * `variant`:
 *  - "dark"  → koyu footer (cyan-950) için açık metin
 *  - "light" → açık zeminli sayfalar (pricing vb.) için koyu metin
 */
export function PaymentMethods({
  variant = "dark",
  className,
}: {
  variant?: "dark" | "light";
  className?: string;
}) {
  const dark = variant === "dark";
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-3",
        className,
      )}
    >
      <span
        className={cn(
          "inline-flex items-center gap-1.5 text-xs font-semibold",
          dark ? "text-cyan-100/70" : "text-slate-600",
        )}
      >
        <ShieldCheck
          className={cn("size-4", dark ? "text-amber-300" : "text-cyan-700")}
          aria-hidden
        />
        Güvenli Ödeme
      </span>
      <div className="flex items-center gap-2">
        <IyzicoLogo />
        <VisaLogo />
        <MastercardLogo />
      </div>
      <span
        className={cn(
          "text-[11px] leading-relaxed",
          dark ? "text-cyan-200/50" : "text-slate-500",
        )}
      >
        Ödemeler iyzico altyapısı ile 256-bit SSL ve 3D Secure korumasıyla alınır.
      </span>
    </div>
  );
}
