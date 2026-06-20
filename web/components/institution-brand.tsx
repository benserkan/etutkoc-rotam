import Image from "next/image";
import { Building2 } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Kurum co-branding rozeti — kurum logosu (varsa) + adı; logo yoksa Building2
 * ikonlu chip. Kurum yöneticisi + kuruma bağlı öğretmen panellerinde "hangi
 * kuruma aitim" bilgisini gösterir. Bağımsız koçta institution=null → hiç render
 * edilmez (yalnız platform markası kalır).
 *
 * Logo same-origin `<img>` (cookie auth ile serve ucu); next/Image unoptimized.
 */
export function InstitutionBrand({
  institution,
  className,
}: {
  institution: { id: number; name: string; has_logo?: boolean; logo_url?: string | null };
  className?: string;
}) {
  const hasLogo = !!institution.has_logo && !!institution.logo_url;
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-medium border max-w-full",
        hasLogo
          ? "bg-card text-foreground border-border"
          : "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
        className,
      )}
      title={institution.name}
    >
      {hasLogo ? (
        <Image
          src={institution.logo_url as string}
          alt={institution.name}
          width={16}
          height={16}
          unoptimized
          className="size-4 rounded object-contain shrink-0"
        />
      ) : (
        <Building2 className="size-3 shrink-0" aria-hidden />
      )}
      <span className="truncate">{institution.name}</span>
    </div>
  );
}
