"use client";

/**
 * Tıkla-gör özellik balonu (2026-08-04, kullanıcı onaylı mekanizma).
 *
 * Sorun: "Yanlışına ipucu" gibi kısa etiketler ilk kez okuyana yetmiyor;
 * açıklamayı satıra yazmak sayfayı şişiriyor. Çözüm: sözlükte karşılığı olan
 * kısa başlık NOKTALI ALTÇİZGİ ile işaretlenir; dokununca kompakt bir pencere
 * açılır — 1-2 cümle sade açıklama + (varsa) özelliğin GERÇEK ekran karesi
 * ("anlatma, göster"). Sözlük tek kaynak: /api/v2/pricing feature_glossary.
 */
import * as React from "react";
import Image from "next/image";

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
  const onColor = tone === "onColor";
  const i = text.indexOf(" — ");
  const title = i < 0 ? text : text.slice(0, i);
  const detail = i < 0 ? null : text.slice(i + 3);
  const entry = glossary?.get(title);

  const titleEl = entry ? (
    <button
      type="button"
      onClick={() => setOpen(true)}
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
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="max-w-sm overflow-hidden p-0">
            {entry.image ? (
              // Gerçek ürün ekranı — yalnız balon açılınca yüklenir
              <div className="relative aspect-[16/10] w-full border-b border-border bg-slate-100">
                <Image
                  src={entry.image}
                  alt={entry.term}
                  fill
                  sizes="384px"
                  className="object-cover object-top"
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
            </div>
          </DialogContent>
        </Dialog>
      ) : null}
    </span>
  );
}
