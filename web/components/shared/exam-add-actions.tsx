"use client";

import * as React from "react";
import { FileUp, Plus } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
/**
 * Deneme ekleme yolları (2026-10-03 yeniden tasarım). PDF aktarımı ASIL yol —
 * konu analizi, unutulan konular, net fırsatı yalnız soru soru okunan
 * denemelerden beslenir; bu yüzden büyük, dolgulu ve sürükle-bırak hedefi.
 * Elle giriş ikincil (yalnız netler).
 */
export function ExamAddActions({
  onImport,
  onManual,
  pdfCount = 0,
  total = 0,
  note,
}: {
  onImport: (file: File | null) => void;
  /** Verilmezse (öğrenci yüzeyi) yalnız PDF kutusu tam genişlikte çizilir. */
  onManual?: () => void;
  pdfCount?: number;
  total?: number;
  /** PDF kutusuna eklenecek kısa not (örn. "koçun kontrol edip düzeltebilir"). */
  note?: string;
}) {
  const [over, setOver] = React.useState(false);
  const manualCount = total - pdfCount;
  return (
    <div
      className={cn(
        "grid gap-3",
        onManual && "md:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]",
      )}
    >
      <button
        type="button"
        onClick={() => onImport(null)}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files?.[0];
          if (!f) return;
          if (
            f.type !== "application/pdf" &&
            !f.name.toLowerCase().endsWith(".pdf")
          ) {
            toast.error("Yalnız PDF dosyası yüklenebilir");
            return;
          }
          onImport(f);
        }}
        className={cn(
          "group flex items-center gap-4 rounded-xl bg-violet-600 p-4 text-left text-white shadow-sm transition hover:bg-violet-700",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-2",
          over && "ring-4 ring-violet-300",
        )}
      >
        <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-white/15">
          <FileUp className="size-6" aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-base font-semibold">
            {over ? "Bırak — PDF okunmaya hazır" : "Deneme sonuç PDF'ini yükle"}
          </span>
          <span className="mt-0.5 block text-sm text-violet-100">
            Sorular tek tek okunur; konu analizi, unutulan konular ve net
            fırsatı kendiliğinden dolar.
            {note ? ` ${note}` : ""}
          </span>
          <span className="mt-2 flex flex-wrap gap-1.5 text-xs">
            <span className="rounded-full bg-white/15 px-2 py-0.5">
              Tıkla ya da sürükle-bırak
            </span>
            <span className="rounded-full bg-white/15 px-2 py-0.5">
              en çok 10 MB
            </span>
            <span className="rounded-full bg-white/15 px-2 py-0.5">
              okuma 3-5 dakika
            </span>
          </span>
        </span>
      </button>

      {onManual ? (
        <button
          type="button"
          onClick={onManual}
          className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition hover:bg-muted"
        >
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted text-foreground">
            <Plus className="size-5" aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-foreground">
              Elle deneme gir
            </span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              PDF yoksa toplam ya da ders netlerini yaz. Soru bilgisi olmadığı
              için konu analizine girmez.
            </span>
            {total > 0 ? (
              <span className="mt-1.5 block text-xs text-muted-foreground">
                Bu dönemde {pdfCount} PDF · {manualCount} elle girilmiş deneme
              </span>
            ) : null}
          </span>
        </button>
      ) : null}
    </div>
  );
}
