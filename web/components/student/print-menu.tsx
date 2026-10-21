"use client";

import * as React from "react";
import { CalendarDays, CalendarRange, Printer, Trophy } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface Props {
  /** Hangi haftanın yazdırılacağı — "YYYY-MM-DD" formatında hafta başlangıç günü. */
  startDate: string;
  /** "Günü yazdır" için gün — verilmezse startDate. */
  dayDate?: string;
  /** Custom etiket — default "Yazdır". */
  label?: string;
}

/**
 * Yazdırma menüsü (2026-10-21): Günü / Haftayı / Deneme sonuçlarını yazdır.
 * Hepsi Next.js `(print)` sayfaları — yeni sekmede açılır, oradan yazdırılır ya da PDF kaydedilir.
 * (Eski "Veli raporu yazdır" kaldırıldı: veli raporu velinin kendi panelinde.)
 */
export function PrintMenu({ startDate, dayDate, label = "Yazdır" }: Props) {
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
            href={`/student/day/print?date=${encodeURIComponent(dayDate ?? startDate)}`}
            icon={<CalendarDays className="size-3.5" />}
            title="Günü yazdır"
            description="Günün görevleri, A4 dikey — doğru/yanlış yazma alanlı"
            onClick={() => setOpen(false)}
          />
          <PrintLink
            href={`/student/week/print${q}`}
            icon={<CalendarRange className="size-3.5" />}
            title="Haftayı yazdır"
            description="7 günlük çalışma planı, A4 yatay"
            onClick={() => setOpen(false)}
          />
          <PrintLink
            href="/student/exams/print"
            icon={<Trophy className="size-3.5" />}
            title="Deneme sonuçlarını yazdır"
            description="Tüm denemelerin netleri, ders ders, A4 dikey"
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
