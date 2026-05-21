"use client";

import * as React from "react";
import { FileText, Printer, Users } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface Props {
  /** Hangi haftanın yazdırılacağı — "YYYY-MM-DD" formatında hafta başlangıç günü. */
  startDate: string;
  /** Custom etiket — default "Yazdır". */
  label?: string;
}

/**
 * Yazdırma menüsü — Jinja'da yaşayan A4 print sayfalarına çıkış noktası.
 *
 * Sözleşme:
 *   - Print sayfaları FastAPI Jinja'da kalır (hibrit kalıcı karar,
 *     `project_nextjs_migration.md` ve Caddyfile `@prints` matcher'ı).
 *   - Bu component yalnız `<a target="_blank">` ile o sayfalara açılır.
 *   - Dev'de Next.js `next.config.ts` rewrite'ı `/student/.../print` path'lerini
 *     FastAPI'ye geçirir; prod'da Caddy aynı işi yapar — URL değişmez.
 */
export function PrintMenu({ startDate, label = "Yazdır" }: Props) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const q = `?start=${encodeURIComponent(startDate)}`;

  return (
    <div className="relative" ref={ref}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Printer className="size-4" aria-hidden />
        {label}
      </Button>
      {open ? (
        <div
          role="menu"
          className={cn(
            "absolute right-0 z-30 mt-1 w-64 rounded-md border border-border bg-popover p-1 shadow-md",
          )}
        >
          <PrintLink
            href={`/student/week/print${q}`}
            icon={<FileText className="size-3.5" />}
            title="Haftalık planı yazdır"
            description="7 günlük çalışma planı, A4 yatay"
            onClick={() => setOpen(false)}
          />
          <PrintLink
            href={`/student/weekly-report/print${q}`}
            icon={<Users className="size-3.5" />}
            title="Veli raporu yazdır"
            description="Veli paylaşımı için haftalık performans (klasik biçim)"
            onClick={() => setOpen(false)}
          />
        </div>
      ) : null}
    </div>
  );
}

function PrintLink({
  href,
  icon,
  title,
  description,
  onClick,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener"
      role="menuitem"
      onClick={onClick}
      className="flex items-start gap-2 rounded-sm px-2 py-2 text-sm hover:bg-muted transition-colors"
    >
      <span className="text-muted-foreground mt-0.5 shrink-0" aria-hidden>
        {icon}
      </span>
      <span className="flex-1 min-w-0">
        <span className="block font-medium leading-tight">{title}</span>
        <span className="block text-xs text-muted-foreground mt-0.5">
          {description}
        </span>
      </span>
    </a>
  );
}
