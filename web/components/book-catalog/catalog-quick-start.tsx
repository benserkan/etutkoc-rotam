"use client";

/**
 * Sihirbaz Adım 1 — Ortak Kitap Kataloğu hızlı başlangıcı.
 *
 * Koç kitap adını yazar (veya kapağı taratır) → katalogda varsa kayıt kartı
 * çıkar → "Yapısını kullan" TEK TIKLA kitabı oluşturur: ünite + BİREBİR test
 * sayıları + müfredat eşleştirmesi katalogdan gelir (form doldurma yok).
 * Katalogda yoksa koç alttaki normal formla devam eder.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Camera, Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { bookCatalogKeys, coachSearchCatalog } from "@/lib/api/book-catalog";
import { useIdentifyCover } from "@/lib/hooks/use-book-catalog-mutations";
import { useCreateBook } from "@/lib/hooks/use-library-mutations";
import type { CatalogEntryBrief } from "@/lib/types/book-catalog";
import type { LibraryBookDetailResponse } from "@/lib/types/library";
import { LIBRARY_BOOK_TYPE_LABELS_TR } from "@/lib/types/library";

interface Props {
  onCreated: (book: LibraryBookDetailResponse) => void;
}

export function CatalogQuickStart({ onCreated }: Props) {
  const [search, setSearch] = React.useState("");
  const [debouncedQ, setDebouncedQ] = React.useState("");
  const [coverMatches, setCoverMatches] = React.useState<CatalogEntryBrief[] | null>(
    null,
  );
  const fileRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(search.trim()), 400);
    return () => clearTimeout(t);
  }, [search]);

  const searchQ = useQuery({
    queryKey: bookCatalogKeys.coachSearch(debouncedQ, null),
    queryFn: () => coachSearchCatalog(debouncedQ),
    enabled: debouncedQ.length >= 2,
    staleTime: 30_000,
  });

  const identify = useIdentifyCover();
  const createBook = useCreateBook();

  const onCover = (files: FileList | null) => {
    const f = files?.[0];
    if (!f) return;
    identify.mutate(f, {
      onSuccess: (res) => {
        if (res.book_title) setSearch(res.book_title);
        setCoverMatches(res.catalog_matches);
      },
    });
    if (fileRef.current) fileRef.current.value = "";
  };

  const applyEntry = (e: CatalogEntryBrief) => {
    if (e.subject_id == null) return;
    createBook.mutate(
      {
        body: {
          name: e.name,
          subject_id: e.subject_id,
          type: e.type,
          publisher: e.publisher,
          target_grade_min: e.target_grade_min,
          target_grade_max: e.target_grade_max,
          target_graduate: e.target_graduate,
          template_id: e.id,
        },
      },
      { onSuccess: (res) => onCreated(res.data) },
    );
  };

  // Kapak eşleşmeleri (varsa) + arama sonuçları birleşik, tekilleştirilmiş
  const items = React.useMemo(() => {
    const out: CatalogEntryBrief[] = [];
    const seen = new Set<number>();
    for (const e of coverMatches ?? []) {
      if (!seen.has(e.id)) {
        seen.add(e.id);
        out.push(e);
      }
    }
    for (const e of searchQ.data?.items ?? []) {
      if (!seen.has(e.id)) {
        seen.add(e.id);
        out.push(e);
      }
    }
    return out.slice(0, 5);
  }, [coverMatches, searchQ.data]);

  const busy = identify.isPending || createBook.isPending;
  const searched = debouncedQ.length >= 2 && !searchQ.isFetching;

  return (
    <Card className="border-cyan-200 dark:border-cyan-500/30">
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 size-4 shrink-0 text-cyan-600 dark:text-cyan-300" aria-hidden />
          <p className="text-sm text-muted-foreground">
            <strong className="text-foreground">Önce katalogda bakalım:</strong>{" "}
            kitap daha önce tanımlandıysa üniteler + <strong>birebir test
            sayıları</strong> + müfredat eşleştirmesi tek tıkla gelir — form
            doldurmana gerek kalmaz.
          </p>
        </div>

        <div className="flex gap-2">
          <Input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setCoverMatches(null);
            }}
            placeholder="Kitap adını yaz… (örn. 4K TYT Matematik)"
            className="flex-1"
          />
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
            title="Kitabın kapağını çek — sistem kitabı tanır"
          >
            {identify.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Camera className="size-4" aria-hidden />
            )}
            <span className="hidden sm:inline">Kapağı tarat</span>
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            className="hidden"
            onChange={(e) => onCover(e.target.files)}
          />
        </div>

        {searchQ.isFetching && debouncedQ.length >= 2 ? (
          <p className="text-xs text-muted-foreground">
            <Loader2 className="mr-1 inline size-3.5 animate-spin" aria-hidden />
            Katalogda aranıyor…
          </p>
        ) : null}

        {items.length > 0 ? (
          <ul className="space-y-1.5">
            {items.map((e) => (
              <li
                key={e.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 dark:bg-emerald-500/10 dark:border-emerald-500/30"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 text-sm font-medium text-emerald-900 dark:text-emerald-100">
                    <BookOpen className="size-4 shrink-0" aria-hidden />
                    <span className="truncate">{e.name}</span>
                  </div>
                  <div className="text-xs text-emerald-800/80 dark:text-emerald-200/80">
                    {e.publisher ? `${e.publisher} · ` : ""}
                    {LIBRARY_BOOK_TYPE_LABELS_TR[e.type]} · {e.section_count} bölüm ·{" "}
                    <strong>{e.total_tests} test</strong>
                    {e.mapped_count > 0
                      ? ` · ${e.mapped_count} ünite müfredata eşli`
                      : ""}
                  </div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  className={cn(
                    "bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white",
                  )}
                  disabled={busy || e.subject_id == null}
                  title={
                    e.subject_id == null
                      ? "Kayıtta ders bilgisi yok — alttaki formla oluştur"
                      : "Kitabı bu yapıyla oluştur"
                  }
                  onClick={() => applyEntry(e)}
                >
                  {createBook.isPending ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                  ) : null}
                  Yapısını kullan
                </Button>
              </li>
            ))}
          </ul>
        ) : searched || coverMatches !== null ? (
          <p className="text-xs text-muted-foreground">
            Katalogda bulunamadı — alttaki formla oluştur; 2. adımda{" "}
            <strong>içindekiler fotoğrafından okuma</strong> ile test sayılarını
            kitaptan birebir alabilirsin.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
