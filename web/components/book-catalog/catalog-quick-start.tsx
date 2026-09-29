"use client";

/**
 * Kitap ekleme sihirbazının "başlangıç yolları" için yapı taşları.
 *
 *  - `CatalogBrowser`: yayındaki TÜM katalog kitapları ders başlıkları altında;
 *    sınav grubu / ders / tür / yayınevi süzgeçleri + ad araması. Kitaba
 *    tıklayınca bölümleri ve test sayıları açılır; "Kütüphaneme ekle" kitabı
 *    tek tıkla oluşturur (ünite + birebir test + müfredat eşleşmesi).
 *  - `BookScanUpload`: kapak + içindekiler fotoğrafları (≤8) ya da kitabın PDF'i.
 *    Kapaktan kitap tanınır; katalogda varsa kaydı gösterilir, yoksa içindekiler
 *    okunur ve taslak sihirbaza verilir.
 *  - `useCatalogApply`: katalog kaydından kitap oluşturma.
 *
 * Hangi yolun gösterileceğini sihirbaz ("Ne yapmak istiyorsun?") belirler.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  Camera,
  ChevronDown,
  ChevronRight,
  FileUp,
  Loader2,
  Search,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

/** Katalog özeti (başlangıç kartındaki "N kitap hazır" sayısı için). */
export function useCatalogBrowse() {
  return useQuery({
    queryKey: bookCatalogKeys.coachBrowse(),
    queryFn: coachBrowseCatalog,
    staleTime: 5 * 60_000,
  });
}

/** Katalog kaydından kitap oluşturur (ünite + test + müfredat eşleşmesi). */
export function useCatalogApply(onCreated: (book: LibraryBookDetailResponse) => void) {
  const createBook = useCreateBook();
  const apply = (e: CatalogEntryBrief) => {
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
  return { apply, isPending: createBook.isPending };
}

// =============================================================================
// Katalog tarayıcısı
// =============================================================================

export function CatalogBrowser({
  onApply,
  busy,
}: {
  onApply: (e: CatalogEntryBrief) => void;
  busy: boolean;
}) {
  const [search, setSearch] = React.useState("");
  const [group, setGroup] = React.useState<CatalogExamGroup | "">("");
  const [subjectF, setSubjectF] = React.useState("");
  const [typeF, setTypeF] = React.useState<LibraryBookType | "">("");
  const [publisherF, setPublisherF] = React.useState("");

  const browseQ = useCatalogBrowse();
  const all = React.useMemo(() => browseQ.data?.items ?? [], [browseQ.data]);

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
  const selectCls = "h-10 rounded-lg border border-input bg-background px-2 text-sm";

  return (
    <div className="space-y-3" data-testid="catalog-browser">
      {/* Sınav grubu: tek dokunuşluk segment */}
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Sınav grubu">
        {([["", "Tümü", all.length]] as [string, string, number][])
          .concat(
            (Object.keys(CATALOG_EXAM_GROUP_LABELS_TR) as CatalogExamGroup[])
              .filter((g) => groupCounts[g])
              .map((g) => [g, CATALOG_EXAM_GROUP_LABELS_TR[g], groupCounts[g] ?? 0]),
          )
          .map(([g, label, n]) => {
            const on = group === g;
            return (
              <button
                key={g || "all"}
                type="button"
                aria-pressed={on}
                onClick={() => {
                  setGroup(g as CatalogExamGroup | "");
                  setSubjectF("");
                  setPublisherF("");
                }}
                className={
                  on
                    ? "rounded-full bg-cyan-700 px-3 py-1.5 text-sm font-medium text-white"
                    : "rounded-full border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted"
                }
              >
                {label} <span className={on ? "text-cyan-100" : "text-muted-foreground"}>{n}</span>
              </button>
            );
          })}
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Kitap adı ya da yayınevi yaz… (örn. 345 TYT Matematik)"
          className="h-11 pl-9 text-base"
          aria-label="Katalogda ara"
          autoFocus
        />
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <select aria-label="Ders" value={subjectF} onChange={(e) => setSubjectF(e.target.value)} className={selectCls}>
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
          className={selectCls}
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
          className={selectCls}
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
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1 inline size-4 animate-spin" aria-hidden />
          Katalog yükleniyor…
        </p>
      ) : grouped.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-sm text-muted-foreground">
          Bu aramaya uyan kitap katalogda yok.
        </p>
      ) : (
        <div className="max-h-[32rem] space-y-4 overflow-y-auto pr-1" data-testid="catalog-browse-list">
          {grouped.map(([subj, items]) => (
            <section key={subj} className="space-y-1.5">
              <h4 className="sticky top-0 z-10 bg-card py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {subj} · {items.length}
              </h4>
              <ul className="space-y-1.5">
                {items.map((e) => (
                  <CatalogRow key={e.id} entry={e} busy={busy} onApply={onApply} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Kapak + içindekiler yükleme
// =============================================================================

export function BookScanUpload({
  onApply,
  onScanned,
  busy,
}: {
  onApply: (e: CatalogEntryBrief) => void;
  /** İçindekiler okundu (katalogda yok ya da koç "bu değil" dedi). */
  onScanned: (result: BookScanResult) => void;
  busy: boolean;
}) {
  const [scan, setScan] = React.useState<BookScanResult | null>(null);
  const [files, setFiles] = React.useState<File[] | null>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);
  const scanMut = useScanBook();

  const run = (fs: File[], forceRead: boolean) => {
    scanMut.mutate(
      { files: fs, forceRead },
      {
        onSuccess: (res) => {
          setScan(res);
          if (res.structure) onScanned(res);
        },
      },
    );
  };

  const onFiles = (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const fs = Array.from(list);
    setFiles(fs);
    setScan(null);
    run(fs, false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const disabled = busy || scanMut.isPending;

  return (
    <div className="space-y-3" data-testid="scan-upload">
      {scanMut.isPending ? (
        <div className="flex items-center gap-3 rounded-xl border border-violet-200 bg-violet-50 px-4 py-5 text-sm text-violet-900 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-100">
          <Loader2 className="size-5 shrink-0 animate-spin" aria-hidden />
          <span>
            Kapak tanınıyor; katalogda yoksa içindekiler iki kez okunuyor…
            <br />
            <span className="text-xs">30-60 saniye sürebilir, sayfadan ayrılma.</span>
          </span>
        </div>
      ) : (
        <button
          type="button"
          disabled={disabled}
          onClick={() => fileRef.current?.click()}
          className="flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed border-violet-300 bg-violet-50/50 px-4 py-8 text-center transition hover:border-violet-500 hover:bg-violet-50 disabled:opacity-60 dark:border-violet-500/40 dark:bg-violet-500/5 dark:hover:bg-violet-500/10"
          data-testid="scan-button"
        >
          <span className="inline-flex size-12 items-center justify-center rounded-full bg-violet-600 text-white">
            <FileUp className="size-6" aria-hidden />
          </span>
          <span className="text-base font-semibold text-violet-950 dark:text-violet-100">
            {scan ? "Başka dosya seç" : "Fotoğraf ya da PDF seç"}
          </span>
          <span className="max-w-md text-sm text-violet-900 dark:text-violet-200">
            Kapağın ve içindekiler sayfalarının fotoğrafları (en çok 8) ya da kitabın PDF’i.
            Tam kitap PDF’i de olur — yalnız ilk 12 sayfası okunur.
          </span>
          <span className="inline-flex items-center gap-1 text-xs text-violet-800 dark:text-violet-300">
            <Camera className="size-3.5" aria-hidden /> Telefonda doğrudan kamera açılır · kredi harcamaz
          </span>
        </button>
      )}
      <input
        ref={fileRef}
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp,application/pdf"
        className="hidden"
        onChange={(e) => onFiles(e.target.files)}
        data-testid="scan-input"
      />
      {scan ? (
        <ScanOutcome
          scan={scan}
          busy={disabled}
          onApply={onApply}
          onForceRead={files && !scan.structure ? () => run(files, true) : null}
        />
      ) : null}
    </div>
  );
}

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
    <div className="space-y-2" data-testid="scan-outcome">
      {ident ? (
        <p className="text-sm">
          Tanınan kitap: <strong className="break-words">{ident}</strong>
        </p>
      ) : null}
      {scan.notes.map((n, i) => (
        <p key={i} className="text-xs text-muted-foreground">
          • {n}
        </p>
      ))}
      {scan.structure ? (
        <p className="rounded-lg bg-emerald-600 px-3 py-2 text-sm text-white" data-testid="scan-read-ok">
          {scan.catalog_matches.length > 0 ? "İçindekilerden" : "Katalogda yok — içindekilerden"}{" "}
          <strong>{scan.structure.sections.length} bölüm</strong> okundu. Aşağıda ders ve sınıfı
          seçip oluştur; bölümler bir sonraki adımda kontrol için hazır gelecek.
        </p>
      ) : scan.catalog_matches.length > 0 ? (
        <>
          <p className="text-sm font-semibold">Bu kitap katalogda var — yapısı hazır:</p>
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
      className="rounded-xl border border-border bg-card transition hover:border-cyan-400"
      data-testid="catalog-row"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="min-w-0 flex-1 text-left"
          aria-expanded={open}
        >
          <div className="flex items-start gap-1.5 text-sm font-medium">
            {open ? (
              <ChevronDown className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
            ) : (
              <ChevronRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
            )}
            <BookOpen className="mt-0.5 size-4 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
            <span className="break-words">{e.name}</span>
          </div>
          <div className="pl-[2.375rem] text-xs text-muted-foreground">
            {e.publisher ? `${e.publisher} · ` : ""}
            {LIBRARY_BOOK_TYPE_LABELS_TR[e.type]}
            {grade ? ` · ${grade}` : ""} · {e.section_count} bölüm ·{" "}
            <strong className="text-foreground">{e.total_tests} test</strong>
            {e.usage_count > 0 ? ` · ${e.usage_count} koç kullanıyor` : ""}
          </div>
        </button>
        <Button
          type="button"
          size="sm"
          className="bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white"
          disabled={busy || e.subject_id == null}
          title={
            e.subject_id == null
              ? "Kayıtta ders bilgisi yok — elle oluştur"
              : "Kitabı bu yapıyla kütüphanene ekle"
          }
          onClick={() => onApply(e)}
        >
          Kütüphaneme ekle
        </Button>
      </div>
      {open ? (
        <div className="border-t border-border px-3 py-2">
          {detailQ.isLoading ? (
            <p className="text-xs text-muted-foreground">
              <Loader2 className="mr-1 inline size-3.5 animate-spin" aria-hidden />
              Bölümler yükleniyor…
            </p>
          ) : detailQ.data ? (
            <ol className="space-y-0.5 text-xs" data-testid="catalog-sections">
              {detailQ.data.sections.map((s, i) => (
                <li key={`${s.order}-${i}`} className="flex items-start justify-between gap-3">
                  <span className="min-w-0 break-words">
                    {i + 1}. {s.label}
                    {s.topic_name && s.topic_name !== s.label ? (
                      <span className="text-muted-foreground"> → {s.topic_name}</span>
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
