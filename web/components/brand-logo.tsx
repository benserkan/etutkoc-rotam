import Link from "next/link";
import Image from "next/image";

import { cn } from "@/lib/utils";

/**
 * Paylaşılan marka kilidi — amblem (etutkoc-mark.svg, şeffaf) + "etütkoç·rotam"
 * wordmark.
 *
 * Neden amblem + ayrı yazı: tam dikey kilit (amblem + "etütkoç" yazısı) küçük
 * header boyutunda okunmuyordu. Amblem net bir ikon olarak gösterilir, marka
 * adı yanında crisp metin olarak okunur. Amblem küçük beyaz çip içinde →
 * koyu/renkli zeminde (admin, veli, footer) de okunaklı.
 *
 * Server + client bileşenlerinde kullanılabilir (hook yok).
 */
export function BrandLogo({
  href = "/",
  size = 30,
  className,
  showWordmark = true,
  wordmarkClassName,
  wordmarkSize = "text-lg",
}: {
  href?: string;
  size?: number;
  className?: string;
  showWordmark?: boolean;
  wordmarkClassName?: string;
  wordmarkSize?: string;
}) {
  return (
    <Link
      href={href}
      aria-label="ETÜTKOÇ Rotam"
      className={cn("group inline-flex items-center gap-2.5", className)}
    >
      <span className="inline-flex items-center justify-center rounded-xl bg-white p-1.5 shadow-sm ring-1 ring-black/5 transition group-hover:-translate-y-0.5">
        <Image
          src="/etutkoc-mark.svg"
          alt="ETÜTKOÇ"
          width={size}
          height={size}
          unoptimized
          priority
          className="object-contain"
          style={{ width: size, height: size }}
        />
      </span>
      {showWordmark ? (
        <span
          className={cn(
            "font-display font-bold tracking-tight leading-none",
            wordmarkSize,
            wordmarkClassName,
          )}
        >
          etütkoç<span className="text-amber-500">·</span>rotam
        </span>
      ) : null}
    </Link>
  );
}
