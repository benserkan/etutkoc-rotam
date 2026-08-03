"use client";

/**
 * Tıkla-gör özellik balonu (2026-08-04, kullanıcı onaylı mekanizma).
 *
 * Sorun: "Yanlışına ipucu" gibi kısa etiketler ilk kez okuyana yetmiyor;
 * açıklamayı satıra yazmak sayfayı şişiriyor. Çözüm: sözlükte karşılığı olan
 * kısa başlık NOKTALI ALTÇİZGİ ile işaretlenir; dokununca kompakt pencere —
 * 1-2 cümle sade açıklama + (varsa) özelliğin ekran kanıtı.
 *
 * DERS (tekrarlayan hata, 2026-08-04): tam ekran görüntüsü (1440×900) küçük
 * boyutta HİÇ okunmuyor. Bu yüzden balon, önceden KIRPILMIŞ odak görselini
 * gösterir (okunur punto); meraklıya "Ekranın tamamını gör" ile tam kare
 * geniş pencerede açılır. Sözlük tek kaynak: /api/v2/pricing feature_glossary.
 */
import * as React from "react";
import Image from "next/image";
import { Maximize2 } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { FeatureGlossaryEntry } from "@/lib/types/pricing";

export type GlossaryMap = Map<string, FeatureGlossaryEntry>;

export function buildGlossaryMap(entries: FeatureGlossaryEntry[] | undefined): GlossaryMap {
  return new Map((entries ?? []).map((e) => [e.term, e]));
}

/**
 * "Kısa Başlık — detay" maddesi: başlık belirgin, detay soluk/küçük.
 * Başlığın sözlükte karşılığı varsa tıklanabilir (noktalı altçizgi) olur.
 * tone: "light" (beyaz kart) · "onColor" (koyu/renkli zemin).
 */
export function FeatureLine({
  text,
  glossary,
  tone = "light",
}: {
  text: string;
  glossary?: GlossaryMap;
  tone?: "light" | "onColor";
}) {
  const [open, setOpen] = React.useState(false);
  const [full, setFull] = React.useState(false); // tam kare büyütme
  const onColor = tone === "onColor";
  const i = text.indexOf(" — ");
  const title = i < 0 ? text : text.slice(0, i);
  const detail = i < 0 ? null : text.slice(i + 3);
  const entry = glossary?.get(title);

  const titleEl = entry ? (
    <button
      type="button"
      onClick={() => { setFull(false); setOpen(true); }}
      className={cn(
        "cursor-help font-medium underline decoration-dotted underline-offset-2 transition",
        onColor
          ? "decoration-amber-300/70 hover:text-amber-200"
          : "decoration-cyan-500/60 hover:text-cyan-700",
      )}
      aria-label={`${title} — nedir?`}
    >
      {title}
    </button>
  ) : (
    <span className="font-medium">{title}</span>
  );

  return (
    <span className={onColor ? "text-white/95" : "text-foreground/90"}>
      {titleEl}
      {detail ? (
        <span className={cn("ml-1 text-xs", onColor ? "text-white/60" : "text-muted-foreground")}>
          {detail}
        </span>
      ) : null}
      {entry ? (
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) setFull(false); }}>
          <DialogContent
            className={cn("overflow-hidden p-0", full ? "max-w-4xl" : "max-w-md")}
          >
            {full && entry.image_full ? (
              // Tam kare — geniş pencerede, okunur
              <div className="relative aspect-[16/10] w-full bg-slate-100">
                <Image
                  src={entry.image_full}
                  alt={entry.term}
                  fill
                  sizes="896px"
                  className="object-contain"
                  unoptimized
                />
              </div>
            ) : entry.image ? (
              // KIRPILMIŞ odak görseli — küçük boyutta da okunur (tam kare değil!)
              <div
                className="relative w-full border-b border-border bg-slate-50"
                style={{
                  aspectRatio:
                    entry.image_w && entry.image_h
                      ? `${entry.image_w} / ${entry.image_h}`
                      : "16 / 10",
                }}
              >
                <Image
                  src={entry.image}
                  alt={entry.term}
                  fill
                  sizes="448px"
                  className="object-contain"
                  unoptimized
                />
              </div>
            ) : null}
            <div className="px-5 pb-5 pt-4">
              <DialogHeader>
                <DialogTitle className="text-base">{entry.term}</DialogTitle>
              </DialogHeader>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {entry.explanation}
              </p>
              {entry.image_full ? (
                <button
                  type="button"
                  onClick={() => setFull((f) => !f)}
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-cyan-700 hover:text-cyan-800"
                >
                  <Maximize2 className="size-3.5" aria-hidden />
                  {full ? "Odak görünümüne dön" : "Ekranın tamamını gör"}
                </button>
              ) : null}
            </div>
          </DialogContent>
        </Dialog>
      ) : null}
    </span>
  );
}
