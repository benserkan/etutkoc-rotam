"use client";

/**
 * Sihirbaz Adım 2 — "Fotoğraftan oku" paneli.
 *
 * Koç kitabın İÇİNDEKİLER sayfalarını fotoğraflar (1-6 foto veya 1 PDF) →
 * Gemini İKİ KEZ okur → düzeltilebilir önizleme (şüpheli satır amber, eksik
 * sayı kırmızı) → "Uygula" bölümleri kitaba yazar. Kredi DÜŞMEZ; günlük tavan
 * vardır. Kapak fotoğrafı İŞE YARAMAZ — test sayıları içindekilerde yazar.
 */
import * as React from "react";
import { Camera, Check, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  SectionsDraftEditor,
  sectionsValid,
  type DraftSection,
} from "@/components/book-catalog/sections-draft-editor";
import {
  useReadStructure,
} from "@/lib/hooks/use-book-catalog-mutations";
import { useBulkCreateSections } from "@/lib/hooks/use-library-mutations";
import type { LibraryBookDetailResponse } from "@/lib/types/library";

export function PhotoReadPanel({ book }: { book: LibraryBookDetailResponse }) {
  const [draft, setDraft] = React.useState<DraftSection[] | null>(null);
  const [warnings, setWarnings] = React.useState<string[]>([]);
  const [readsLeft, setReadsLeft] = React.useState<number | null>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const read = useReadStructure("coach");
  const apply = useBulkCreateSections(book.id);

  const onFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    read.mutate(Array.from(files), {
      onSuccess: (res) => {
        setDraft(
          res.sections.map((s) => ({
            label: s.label,
            test_count: s.test_count,
            suspect: s.suspect,
          })),
        );
        setWarnings(res.warnings);
        setReadsLeft(res.reads_left_today);
      },
    });
    if (fileRef.current) fileRef.current.value = "";
  };

  const onApply = () => {
    if (!draft || !sectionsValid(draft)) return;
    apply.mutate({
      items: draft.map((s) => ({
        label: s.label.trim(),
        test_count: s.test_count ?? 0,
      })),
    });
    // Başarıda kitap query'si bayatlar → sihirbaz "N ünite eklendi" kartına döner.
  };

  const busy = read.isPending || apply.isPending;

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        {draft === null ? (
          <>
            <p className="text-sm text-muted-foreground">
              Kitabın <strong className="text-foreground">İçindekiler</strong>{" "}
              sayfasını çek (genelde 1-2 sayfa — testlerin listelendiği kısım).
              Sistem iki bağımsız okuma yapıp karşılaştırır; test sayıları{" "}
              <strong className="text-foreground">kitaptan birebir</strong> gelir,
              tahmin edilmez. Kredi harcamaz.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={() => fileRef.current?.click()} disabled={busy}>
                {read.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden /> İki kez
                    okunuyor…
                  </>
                ) : (
                  <>
                    <Camera className="size-4" aria-hidden /> Fotoğraf çek / dosya seç
                  </>
                )}
              </Button>
              <span className="text-xs text-muted-foreground">
                1-6 fotoğraf (JPEG/PNG) veya 1 PDF
              </span>
            </div>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp,application/pdf"
              capture="environment"
              className="hidden"
              onChange={(e) => onFiles(e.target.files)}
            />
          </>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm">
                <Check className="inline size-4 text-emerald-600" aria-hidden />{" "}
                <strong>{draft.length} bölüm okundu</strong> — kontrol et, gerekirse
                düzelt, sonra uygula.
              </p>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => {
                  setDraft(null);
                  setWarnings([]);
                }}
              >
                Yeniden çek
              </Button>
            </div>
            {warnings.length > 0 ? (
              <ul className="space-y-0.5 text-xs text-amber-800 dark:text-amber-200">
                {warnings.map((w, i) => (
                  <li key={i}>• {w}</li>
                ))}
              </ul>
            ) : null}
            <SectionsDraftEditor
              sections={draft}
              onChange={setDraft}
              disabled={apply.isPending}
            />
            <div className="flex items-center justify-end gap-2">
              <Button
                type="button"
                onClick={onApply}
                disabled={busy || !sectionsValid(draft)}
              >
                {apply.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Check className="size-4" aria-hidden />
                )}
                {draft.length} bölümü kitaba ekle
              </Button>
            </div>
          </>
        )}
        {readsLeft != null && readsLeft <= 5 ? (
          <p className="text-xs text-muted-foreground">
            Bugün {readsLeft} okuma hakkın kaldı.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
