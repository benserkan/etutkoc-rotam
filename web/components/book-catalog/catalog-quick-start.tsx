"use client";

/**
 * Sihirbaz Adım 1 — Ortak Kitap Kataloğu.
 *
 * Üç yol, tek kutu:
 *  1. Katalog tarayıcısı: yayındaki TÜM kitaplar ders başlıkları altında
 *     görünür; sınav grubu / ders / tür / yayınevi süzgeçleri + ad araması.
 *     Kitaba tıklayınca bölümleri ve test sayıları açılır; "Yapısını kullan"
 *     kitabı tek tıkla oluşturur (ünite + birebir test + müfredat eşleşmesi).
 *  2. "Kapak + içindekiler": kapak ve içindekiler fotoğrafları (≤8) ya da
 *     kitabın PDF'i (tam kitap da olur, ilk 12 sayfası okunur). Kapaktan
 *     kitap tanınır; katalogda varsa kaydı gösterilir, yoksa içindekiler
 *     okunur ve taslak sihirbaza verilir (2. adımda hazır gelir).
 *  3. Hiçbiri → alttaki form.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  FileUp,
  Library,
  Loader2,
  Search,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  bookCatalogKeys,
  coachBrowseCatalog,
  coachGetCatalogEntry,
} from "@/lib/api/book-catalog";
import { useScanBook } from "@/lib/hooks/use-book-catalog-mutations";
import { useCreateBook } from "@/lib/hooks/use-library-mutations";
import {
  CATALOG_EXAM_GROUP_LABELS_TR,
  type BookScanResult,
  type CatalogEntryBrief,
  type CatalogExamGroup,
} from "@/lib/types/book-catalog";
import type { LibraryBookDetailResponse, LibraryBookType } from "@/lib/types/library";
import { LIBRARY_BOOK_TYPE_LABELS_TR } from "@/lib/types/library";

interface Props {
  onCreated: (book: LibraryBookDetailResponse) => void;
  /** Katalogda olmayan kitabın içindekiler okuması — sihirbaz formu doldurur. */
  onScanned?: (result: BookScanResult) => void;
}

const TR_MAP: Record<string, string> = {
  ı: "i", İ: "i", I: "i", ş: "s", Ş: "s", ğ: "g", Ğ: "g",
  ü: "u", Ü: "u", ö: "o", Ö: "o", ç: "c", Ç: "c",
};
function norm(s: string | null | undefined): string {
  return (s ?? "")
    .replace(/[ıİIşŞğĞüÜöÖçÇ]/g, (c) => TR_MAP[c] ?? c)
    .toLowerCase()
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function matchesQuery(e: CatalogEntryBrief, q: string): boolean {
  const tokens = norm(q).split(" ").filter(Boolean);
  if (tokens.length === 0) return true;
  const hay = norm(`${e.name} ${e.publisher ?? ""} ${e.subject_name ?? ""}`);
  const compact = hay.replace(/ /g, "");
  return tokens.every((t) => hay.includes(t) || compact.includes(t));
}

function gradeText(e: CatalogEntryBrief): string | null {
  const lo = e.target_grade_min;
  const hi = e.target_grade_max;
  const parts: string[] = [];
  if (lo != null && hi != null) parts.push(lo === hi ? `${lo}. sınıf` : `${lo}-${hi}. sınıf`);
  else if (lo != null) parts.push(`${lo}. sınıf ve üstü`);
  else if (hi != null) parts.push(`${hi}. sınıfa kadar`);
  if (e.target_graduate) parts.push("mezun");
  return parts.length ? parts.join(" + ") : null;
}

export function CatalogQuickStart({ onCreated, onScanned }: Props) {
  const [search, setSearch] = React.useState("");
  const [group, setGroup] = React.useState<CatalogExamGroup | "">("");
  const [subjectF, setSubjectF] = React.useState("");
  const [typeF, setTypeF] = React.useState<LibraryBookType | "">("");
  const [publisherF, setPublisherF] = React.useState("");
  const [browseOpen, setBrowseOpen] = React.useState(true);
  const [scan, setScan] = React.useState<BookScanResult | null>(null);
  const [scanFiles, setScanFiles] = React.useState<File[] | null>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const browseQ = useQuery({
    queryKey: bookCatalogKeys.coachBrowse(),
    queryFn: coachBrowseCatalog,
    staleTime: 5 * 60_000,
  });
  const all = React.useMemo(() => browseQ.data?.items ?? [], [browseQ.data]);

  const scanMut = useScanBook();
  const createBook = useCreateBook();

  const runScan = (files: File[], forceRead: boolean) => {
    scanMut.mutate(
      { files, forceRead },
      {
        onSuccess: (res) => {
          setScan(res);
          if (res.structure && onScanned) onScanned(res);
        },
      },
    );
  };

  const onFiles = (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const files = Array.from(list);
    setScanFiles(files);
    setScan(null);
    runScan(files, false);
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

  // Süzgeç seçenekleri: bir üst süzgece göre daralır
  const inGroup = React.useMemo(
    () => (group ? all.filter((e) => e.exam_group === group) : all),
    [all, group],
  );
  const subjectOptions = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const e of inGroup) {
      const k = e.subject_name ?? "Ders belirtilmemiş";
      m.set(k, (m.get(k) ?? 0) + 1);
    }
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0], "tr"));
  }, [inGroup]);
  const publisherOptions = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const e of inGroup) {
      if (!e.publisher) continue;
      m.set(e.publisher, (m.get(e.publisher) ?? 0) + 1);
    }
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0], "tr"));
  }, [inGroup]);
  const groupCounts = React.useMemo(() => {
    const c: Partial<Record<CatalogExamGroup, number>> = {};
    for (const e of all) {
      if (e.exam_group) c[e.exam_group] = (c[e.exam_group] ?? 0) + 1;
    }
    return c;
  }, [all]);

  const filtered = React.useMemo(
    () =>
      inGroup.filter(
        (e) =>
          (!subjectF || (e.subject_name ?? "Ders belirtilmemiş") === subjectF) &&
          (!typeF || e.type === typeF) &&
          (!publisherF || e.publisher === publisherF) &&
          matchesQuery(e, search),
      ),
    [inGroup, subjectF, typeF, publisherF, search],
  );
  const grouped = React.useMemo(() => {
    const m = new Map<string, CatalogEntryBrief[]>();
    for (const e of filtered) {
      const k = e.subject_name ?? "Ders belirtilmemiş";
      const arr = m.get(k) ?? [];
      arr.push(e);
      m.set(k, arr);
    }
    return Array.from(m.entries());
  }, [filtered]);

  const anyFilter = !!(group || subjectF || typeF || publisherF || search.trim());
  const busy = scanMut.isPending || createBook.isPending;

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

        {/* Kapak + içindekiler tek yükleme */}
        <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 dark:border-violet-500/30 dark:bg-violet-500/10">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0 flex-1 text-sm text-violet-900 dark:text-violet-100">
              <strong>Kitap elinde mi?</strong> Kapağın ve içindekiler sayfalarının
              fotoğraflarını (en çok 8) ya da kitabın PDF’ini seç.
            </div>
            <Button
              type="button"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
              className="bg-violet-600 text-white hover:bg-violet-700 hover:text-white"
              data-testid="scan-button"
            >
              {scanMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <FileUp className="size-4" aria-hidden />
              )}
              Kapak + içindekiler yükle
            </Button>
          </div>
          <p className="mt-1.5 text-xs text-violet-800 dark:text-violet-200">
            Sistem kapaktan kitabı tanır: katalogda varsa yapısı tek tıkla gelir;
            yoksa içindekiler iki kez okunur ve test sayıları kitaptan alınır.
            Tam kitap PDF’i de olur — yalnız ilk 12 sayfası (kapak + içindekiler)
            okunur. Kredi harcamaz.
          </p>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,application/pdf"
            className="hidden"
            onChange={(e) => onFiles(e.target.files)}
            data-testid="scan-input"
          />
          {scanMut.isPending ? (
            <p className="mt-2 text-xs text-violet-900 dark:text-violet-100">
              <Loader2 className="mr-1 inline size-3.5 animate-spin" aria-hidden />
              Kapak tanınıyor, gerekirse içindekiler okunuyor… (30-60 sn sürebilir)
            </p>
          ) : null}
          {scan ? (
            <ScanOutcome
              scan={scan}
              busy={busy}
              onApply={applyEntry}
              onForceRead={
                scanFiles && !scan.structure ? () => runScan(scanFiles, true) : null
              }
            />
          ) : null}
        </div>

        {/* Katalog tarayıcısı */}
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => setBrowseOpen((v) => !v)}
            className="flex w-full items-center gap-2 text-left text-sm font-semibold"
            aria-expanded={browseOpen}
            data-testid="catalog-browse-toggle"
          >
            {browseOpen ? (
              <ChevronDown className="size-4 shrink-0" aria-hidden />
            ) : (
              <ChevronRight className="size-4 shrink-0" aria-hidden />
            )}
            <Library className="size-4 shrink-0 text-cyan-600 dark:text-cyan-300" aria-hidden />
            {browseQ.data
              ? `Katalogda ${browseQ.data.total} kitap var (toplam ${browseQ.data.total_tests.toLocaleString("tr-TR")} test)`
              : "Katalog yükleniyor…"}
          </button>

          {browseOpen ? (
            <>
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                  aria-hidden
                />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Kitap adı ya da yayınevi… (örn. 345 TYT Matematik)"
                  className="pl-8"
                  aria-label="Katalogda ara"
                />
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <select
                  aria-label="Sınav grubu"
                  value={group}
                  onChange={(e) => {
                    setGroup(e.target.value as CatalogExamGroup | "");
                    setSubjectF("");
                    setPublisherF("");
                  }}
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                >
                  <option value="">Tüm sınavlar</option>
                  {(Object.keys(CATALOG_EXAM_GROUP_LABELS_TR) as CatalogExamGroup[])
                    .filter((g) => groupCounts[g])
                    .map((g) => (
                      <option key={g} value={g}>
                        {CATALOG_EXAM_GROUP_LABELS_TR[g]} ({groupCounts[g]})
                      </option>
                    ))}
                </select>
                <select
                  aria-label="Ders"
                  value={subjectF}
                  onChange={(e) => setSubjectF(e.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                >
                  <option value="">Tüm dersler</option>
                  {subjectOptions.map(([n, c]) => (
                    <option key={n} value={n}>
                      {n} ({c})
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Tür"
                  value={typeF}
                  onChange={(e) => setTypeF(e.target.value as LibraryBookType | "")}
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                >
                  <option value="">Tüm türler</option>
                  {(Object.keys(LIBRARY_BOOK_TYPE_LABELS_TR) as LibraryBookType[]).map((t) => (
                    <option key={t} value={t}>
                      {LIBRARY_BOOK_TYPE_LABELS_TR[t]}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Yayınevi"
                  value={publisherF}
                  onChange={(e) => setPublisherF(e.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                >
                  <option value="">Tüm yayınevleri</option>
                  {publisherOptions.map(([n, c]) => (
                    <option key={n} value={n}>
                      {n} ({c})
                    </option>
                  ))}
                </select>
              </div>
              {anyFilter ? (
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>{filtered.length} kitap gösteriliyor</span>
                  <button
                    type="button"
                    className="underline underline-offset-2"
                    onClick={() => {
                      setGroup("");
                      setSubjectF("");
                      setTypeF("");
                      setPublisherF("");
                      setSearch("");
                    }}
                  >
                    Süzgeçleri temizle
                  </button>
                </div>
              ) : null}

              {browseQ.isLoading ? (
                <p className="text-xs text-muted-foreground">
                  <Loader2 className="mr-1 inline size-3.5 animate-spin" aria-hidden />
                  Katalog yükleniyor…
                </p>
              ) : grouped.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Katalogda bulunamadı — yukarıdan <strong>kapak + içindekiler</strong>{" "}
                  yükle ya da alttaki formla oluştur.
                </p>
              ) : (
                <div
                  className="max-h-[28rem] space-y-3 overflow-y-auto pr-1"
                  data-testid="catalog-browse-list"
                >
                  {grouped.map(([subj, items]) => (
                    <section key={subj} className="space-y-1.5">
                      <h4 className="sticky top-0 z-10 bg-card py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {subj} · {items.length}
                      </h4>
                      <ul className="space-y-1.5">
                        {items.map((e) => (
                          <CatalogRow key={e.id} entry={e} busy={busy} onApply={applyEntry} />
                        ))}
                      </ul>
                    </section>
                  ))}
                </div>
              )}
            </>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Tarama sonucu
// =============================================================================

function ScanOutcome({
  scan,
  busy,
  onApply,
  onForceRead,
}: {
  scan: BookScanResult;
  busy: boolean;
  onApply: (e: CatalogEntryBrief) => void;
  onForceRead: (() => void) | null;
}) {
  const ident = [scan.book_title, scan.publisher].filter(Boolean).join(" · ");
  return (
    <div className="mt-3 space-y-2" data-testid="scan-outcome">
      {ident ? (
        <p className="text-sm text-violet-900 dark:text-violet-100">
          Tanınan kitap: <strong className="break-words">{ident}</strong>
        </p>
      ) : null}
      {scan.notes.map((n, i) => (
        <p key={i} className="text-xs text-violet-800 dark:text-violet-200">
          • {n}
        </p>
      ))}
      {scan.structure ? (
        <p className="rounded-md bg-emerald-600 px-3 py-2 text-sm text-white" data-testid="scan-read-ok">
          {scan.catalog_matches.length > 0 ? "İçindekilerden" : "Katalogda yok — içindekilerden"}{" "}
          <strong>{scan.structure.sections.length} bölüm</strong> okundu. Aşağıdaki
          formda ders ve sınıfı seçip oluştur; bölümler 2. adımda kontrol için
          hazır gelecek.
        </p>
      ) : scan.catalog_matches.length > 0 ? (
        <>
          <p className="text-xs font-semibold text-violet-900 dark:text-violet-100">
            Katalogda eşleşen kayıt:
          </p>
          <ul className="space-y-1.5">
            {scan.catalog_matches.map((e) => (
              <CatalogRow key={e.id} entry={e} busy={busy} onApply={onApply} defaultOpen />
            ))}
          </ul>
          {onForceRead ? (
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={onForceRead}>
              Bu kitap değil — içindekileri oku
            </Button>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

// =============================================================================
// Katalog satırı (tıkla → bölümler)
// =============================================================================

function CatalogRow({
  entry: e,
  busy,
  onApply,
  defaultOpen = false,
}: {
  entry: CatalogEntryBrief;
  busy: boolean;
  onApply: (e: CatalogEntryBrief) => void;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  const detailQ = useQuery({
    queryKey: bookCatalogKeys.coachDetail(e.id),
    queryFn: () => coachGetCatalogEntry(e.id),
    enabled: open,
    staleTime: 5 * 60_000,
  });
  const grade = gradeText(e);

  return (
    <li
      className="rounded-lg border border-emerald-200 bg-emerald-50 dark:border-emerald-500/30 dark:bg-emerald-500/10"
      data-testid="catalog-row"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="min-w-0 flex-1 text-left"
          aria-expanded={open}
        >
          <div className="flex items-start gap-1.5 text-sm font-medium text-emerald-900 dark:text-emerald-100">
            {open ? (
              <ChevronDown className="mt-0.5 size-4 shrink-0" aria-hidden />
            ) : (
              <ChevronRight className="mt-0.5 size-4 shrink-0" aria-hidden />
            )}
            <BookOpen className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span className="break-words">{e.name}</span>
          </div>
          <div className="pl-[2.375rem] text-xs text-emerald-800 dark:text-emerald-200">
            {e.publisher ? `${e.publisher} · ` : ""}
            {LIBRARY_BOOK_TYPE_LABELS_TR[e.type]}
            {grade ? ` · ${grade}` : ""} · {e.section_count} bölüm ·{" "}
            <strong>{e.total_tests} test</strong>
            {e.mapped_count > 0 ? ` · ${e.mapped_count} bölüm müfredata eşli` : ""}
            {e.usage_count > 0 ? ` · ${e.usage_count} koç kullanıyor` : ""}
          </div>
        </button>
        <Button
          type="button"
          size="sm"
          className={cn("bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white")}
          disabled={busy || e.subject_id == null}
          title={
            e.subject_id == null
              ? "Kayıtta ders bilgisi yok — alttaki formla oluştur"
              : "Kitabı bu yapıyla oluştur"
          }
          onClick={() => onApply(e)}
        >
          Yapısını kullan
        </Button>
      </div>
      {open ? (
        <div className="border-t border-emerald-200 px-3 py-2 dark:border-emerald-500/30">
          {detailQ.isLoading ? (
            <p className="text-xs text-emerald-800 dark:text-emerald-200">
              <Loader2 className="mr-1 inline size-3.5 animate-spin" aria-hidden />
              Bölümler yükleniyor…
            </p>
          ) : detailQ.data ? (
            <ol className="space-y-0.5 text-xs text-emerald-900 dark:text-emerald-100" data-testid="catalog-sections">
              {detailQ.data.sections.map((s, i) => (
                <li key={`${s.order}-${i}`} className="flex items-start justify-between gap-3">
                  <span className="min-w-0 break-words">
                    {i + 1}. {s.label}
                    {s.topic_name && s.topic_name !== s.label ? (
                      <span className="text-emerald-700 dark:text-emerald-300"> → {s.topic_name}</span>
                    ) : null}
                  </span>
                  <span className="shrink-0 font-semibold tabular-nums">{s.test_count} test</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-xs text-rose-700 dark:text-rose-300">Bölümler yüklenemedi.</p>
          )}
        </div>
      ) : null}
    </li>
  );
}
