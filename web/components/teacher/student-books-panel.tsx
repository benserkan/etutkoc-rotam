"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  ArchiveRestore,
  ArrowRight,
  BookOpen,
  ChevronRight,
  Copy,
  ExternalLink,
  Library,
  Loader2,
  Lock,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";

import {
  getTeacherBooks,
  getTeacherStudent,
  getArchiveCandidates,
  getTeacherStudentBooks,
  teacherKeys,
} from "@/lib/api/teacher";
import { getTeacherSelfStudy, selfStudyKeys } from "@/lib/api/self-study";
import {
  useCoachSelfStudyCreate,
  useDeleteSelfStudyEntry,
  useReviewSelfStudy,
} from "@/lib/hooks/use-self-study-mutations";
import {
  SelfStudyEntryDialog,
  SelfStudyEntryRow,
} from "@/components/shared/self-study";
import type {
  SelfStudyListResponse,
  SelfStudyOptionBook,
} from "@/lib/types/self-study";
import { getLibraryBookSet, getLibraryBookSets, libraryKeys } from "@/lib/api/library";
import { setRecommendedForStudent } from "@/lib/utils/book-sets";
import {
  useAssignBook,
  useBulkAssignBooks,
  useSetSectionCompleted,
  useArchiveBooks,
  useUnassignBook,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  ArchiveCandidatesResponse,
  StudentBookListItem,
  StudentBookListResponse,
  StudentBookSectionProgressRow,
  TeacherBookListItem,
  TeacherBookListResponse,
  TeacherStudentDetailResponse,
} from "@/lib/types/teacher";
import type {
  BookSetDetailResponse,
  BookSetListItem,
  BookSetListResponse,
} from "@/lib/types/library";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

interface Props {
  studentId: number;
}

/* ============================================================ Ortak parçalar */

// Ders tonu — subject_id stable hash → her ders hep aynı renk.
const SUBJECT_DOTS = [
  "bg-indigo-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-violet-500",
  "bg-cyan-500",
  "bg-fuchsia-500",
  "bg-sky-500",
];
function subjectDot(subjectId: number) {
  return SUBJECT_DOTS[Math.abs(subjectId) % SUBJECT_DOTS.length];
}

// Kaynak rozeti — küçük öğede dolgulu (koyu zemin + beyaz metin) kuralı.
const SOURCE_BADGE: Record<string, { label: string; cls: string; hint: string }> = {
  catalog: {
    label: "Katalogdan",
    cls: "bg-cyan-700 text-white",
    hint: "Ortak Kitap Kataloğu'ndaki doğrulanmış yapıdan oluşturuldu (birebir test sayıları).",
  },
  template: {
    label: "Şablondan",
    cls: "bg-violet-600 text-white",
    hint: "Senin kitap şablonlarından birinden oluşturuldu.",
  },
  manual: {
    label: "Elle oluşturuldu",
    cls: "bg-slate-600 text-white",
    hint: "Üniteleri ve test sayıları elle girildi.",
  },
};

function SourceBadge({ kind }: { kind?: string | null }) {
  const b = kind ? SOURCE_BADGE[kind] : null;
  if (!b) return null;
  return (
    <span
      data-testid="book-source-badge"
      title={b.hint}
      className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold", b.cls)}
    >
      {b.label}
    </span>
  );
}

function TypeBadge({ label }: { label?: string | null }) {
  if (!label) return null;
  return (
    <span className="inline-flex rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-medium text-slate-800 dark:bg-slate-700 dark:text-slate-100">
      {label}
    </span>
  );
}

function Ring({ pct, size = 92 }: { pct: number; size?: number }) {
  const r = (size - 10) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={9} className="fill-none stroke-slate-200 dark:stroke-slate-700" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        strokeWidth={9}
        strokeLinecap="round"
        strokeDasharray={`${(c * Math.min(100, pct)) / 100} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className="fill-none stroke-emerald-500"
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="fill-foreground text-[19px] font-bold">
        %{pct}
      </text>
    </svg>
  );
}

function ProgressBar({
  done,
  reserved,
  total,
  className,
}: {
  done: number;
  reserved: number;
  total: number;
  className?: string;
}) {
  const d = total > 0 ? Math.min(100, (100 * done) / total) : 0;
  const r = total > 0 ? Math.min(100 - d, (100 * reserved) / total) : 0;
  return (
    <div
      className={cn("flex h-2 w-full overflow-hidden rounded-full bg-muted", className)}
      role="progressbar"
      aria-valuenow={Math.round(d + r)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className="h-full bg-emerald-500 transition-[width]" style={{ width: `${d}%` }} />
      <div className="h-full bg-amber-500 transition-[width]" style={{ width: `${r}%` }} />
    </div>
  );
}

function Legend({ done, reserved, remaining, unit = "test" }: { done: number; reserved: number; remaining: number; unit?: string }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-muted-foreground">
      <span className="inline-flex items-center gap-1">
        <span className="size-2.5 rounded-sm bg-emerald-500" aria-hidden />
        Çözüldü <strong className="tabular-nums text-foreground">{done}</strong>
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="size-2.5 rounded-sm bg-amber-500" aria-hidden />
        Programda (rezerv) <strong className="tabular-nums text-foreground">{reserved}</strong>
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="size-2.5 rounded-sm bg-muted-foreground/30" aria-hidden />
        Atanabilir <strong className="tabular-nums text-foreground">{remaining}</strong> {unit}
      </span>
    </div>
  );
}

function isDenemeType(t: string) {
  return t === "brans_denemesi" || t === "genel_deneme";
}

interface SubjectGroup {
  subject_id: number;
  subject_name: string;
  items: StudentBookListItem[];
  total: number;
  done: number;
  reserved: number;
}

function groupBySubject(items: StudentBookListItem[]): SubjectGroup[] {
  const map = new Map<number, SubjectGroup>();
  for (const it of items) {
    let g = map.get(it.subject_id);
    if (!g) {
      g = { subject_id: it.subject_id, subject_name: it.subject_name, items: [], total: 0, done: 0, reserved: 0 };
      map.set(it.subject_id, g);
    }
    g.items.push(it);
    g.total += it.section_total_tests;
    g.done += it.section_completed_total;
    g.reserved += it.section_reserved_total;
  }
  return Array.from(map.values()).sort((a, b) => a.subject_name.localeCompare(b.subject_name, "tr"));
}

function trLower(s: string) {
  return s.toLocaleLowerCase("tr-TR");
}

/* ============================================================ Panel */

export function StudentBooksPanel({ studentId }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const subjectParam = searchParams.get("subject_id");
  const activeSubjectId = subjectParam ? Number(subjectParam) : null;

  // P4: varsayılan yalnız AKTİF kitaplar; arşivlenenler istenince yüklenir.
  const [showArchived, setShowArchived] = React.useState(false);
  const booksQ = useQuery<StudentBookListResponse>({
    queryKey: teacherKeys.studentBooks(studentId, showArchived),
    queryFn: () => getTeacherStudentBooks(studentId, showArchived),
    staleTime: 30_000,
  });
  const archivedCount = booksQ.data?.archived_count ?? 0;
  const [assignOpen, setAssignOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const data = booksQ.data;
  const allItems = React.useMemo(() => data?.items ?? [], [data]);
  const assignedIds = React.useMemo(() => new Set(allItems.map((b) => b.book_id)), [allItems]);
  const groups = React.useMemo(() => groupBySubject(allItems), [allItems]);

  const totals = React.useMemo(() => {
    const active = allItems.filter((b) => !b.is_archived && !isDenemeType(b.book_type));
    const total = active.reduce((s, b) => s + b.section_total_tests, 0);
    const done = active.reduce((s, b) => s + b.section_completed_total, 0);
    const reserved = active.reduce((s, b) => s + b.section_reserved_total, 0);
    const finished = active.filter((b) => b.section_total_tests > 0 && b.section_completed_total >= b.section_total_tests).length;
    const denemeBooks = allItems.filter((b) => !b.is_archived && isDenemeType(b.book_type)).length;
    return { total, done, reserved, remaining: Math.max(0, total - done - reserved), finished, denemeBooks, count: active.length };
  }, [allItems]);

  const q = trLower(query.trim());
  const visibleGroups = groups
    .filter((g) => activeSubjectId === null || g.subject_id === activeSubjectId)
    .map((g) => ({
      ...g,
      items: q
        ? g.items.filter((b) => trLower(`${b.book_name} ${b.publisher ?? ""}`).includes(q))
        : g.items,
    }))
    .filter((g) => g.items.length > 0);

  function setSubjectFilter(subjectId: number | null) {
    const sp = new URLSearchParams(searchParams.toString());
    if (subjectId === null) sp.delete("subject_id");
    else sp.set("subject_id", String(subjectId));
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}#books` : `${pathname}#books`, { scroll: false });
  }

  const pct = totals.total > 0 ? Math.round((100 * totals.done) / totals.total) : 0;
  const loading = booksQ.isLoading && !data;

  return (
    <div className="space-y-4" data-section="books-panel">
      {/* ---- Başlık + eylemler */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <h3 className="text-base font-semibold text-foreground">Kaynaklar</h3>
          <p className="text-[13px] text-muted-foreground">
            Öğrencinin kitapları, her kitapta ne kadar ilerlediği ve programa verilebilecek kalan test.
            {booksQ.isFetching && !booksQ.isLoading ? " · güncelleniyor…" : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {archivedCount > 0 || showArchived ? (
            <Button
              size="sm"
              variant={showArchived ? "secondary" : "outline"}
              onClick={() => setShowArchived((v) => !v)}
              title="Arşivlenen kitaplar gizlenir; kayıt ve görev geçmişi durur."
            >
              <Archive className="size-4" aria-hidden />
              {showArchived ? "Arşivi gizle" : `Arşivlenenler (${archivedCount})`}
            </Button>
          ) : null}
          <Button size="sm" onClick={() => setAssignOpen(true)} data-testid="open-assign">
            <Plus className="size-4" aria-hidden />
            Kitap ata
          </Button>
        </div>
      </div>

      <ArchiveSuggestionBand studentId={studentId} />

      {/* ---- Özet */}
      {loading ? (
        <div className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">Yükleniyor…</div>
      ) : allItems.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card p-8 text-center">
          <Library className="mx-auto size-8 text-muted-foreground" aria-hidden />
          <p className="mt-2 text-sm font-medium text-foreground">Bu öğrenciye henüz kitap atanmamış</p>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Kütüphanendeki kitaplardan seç ya da hazır bir kitap setini uygula.
          </p>
          <Button size="sm" className="mt-3" onClick={() => setAssignOpen(true)}>
            <Plus className="size-4" aria-hidden />
            Kitap ata
          </Button>
        </div>
      ) : (
        <>
          <div className="grid gap-3 xl:grid-cols-[1fr_minmax(280px,400px)]">
            <div className="rounded-xl border border-border bg-card p-4" data-testid="books-overview">
              <div className="flex flex-wrap items-center gap-4">
                <Ring pct={pct} />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <p className="text-sm font-semibold text-foreground">Soru bankası ilerlemesi</p>
                  <p className="text-[13px] text-muted-foreground">
                    <strong className="text-foreground">{totals.count}</strong> kitap ·{" "}
                    <strong className="text-foreground">{groups.length}</strong> ders ·{" "}
                    <strong className="text-foreground tabular-nums">{totals.total}</strong> test ·{" "}
                    <strong className="text-foreground">{totals.finished}</strong> kitap bitti
                    {totals.denemeBooks > 0 ? ` · ${totals.denemeBooks} deneme kitabı ayrı sayılır` : ""}
                  </p>
                  <ProgressBar done={totals.done} reserved={totals.reserved} total={totals.total} className="h-2.5" />
                  <Legend done={totals.done} reserved={totals.reserved} remaining={totals.remaining} />
                </div>
              </div>
            </div>
            <SelfStudyCard studentId={studentId} books={allItems} />
          </div>

          {/* ---- Ders listesi + kitaplar */}
          <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
            <nav className="space-y-2" aria-label="Dersler">
              <SubjectButton
                active={activeSubjectId === null}
                onClick={() => setSubjectFilter(null)}
                name="Tüm dersler"
                count={allItems.length}
                done={totals.done}
                reserved={totals.reserved}
                total={totals.total}
              />
              {groups.map((g) => (
                <SubjectButton
                  key={g.subject_id}
                  active={activeSubjectId === g.subject_id}
                  onClick={() => setSubjectFilter(g.subject_id)}
                  name={g.subject_name}
                  count={g.items.length}
                  done={g.done}
                  reserved={g.reserved}
                  total={g.total}
                  dot={subjectDot(g.subject_id)}
                />
              ))}
            </nav>

            <div className="min-w-0 space-y-4">
              {allItems.length > 4 ? (
                <label className="relative block">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Kitap adı veya yayınevi ara…"
                    aria-label="Öğrencinin kitaplarında ara"
                    className="h-9 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </label>
              ) : null}
              {visibleGroups.length === 0 ? (
                <div className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">
                  Bu filtrede kitap yok.
                </div>
              ) : (
                visibleGroups.map((g) => (
                  <section key={g.subject_id} className="space-y-2">
                    <header className="flex items-center gap-2">
                      <span className={cn("inline-block size-2.5 rounded-full", subjectDot(g.subject_id))} aria-hidden />
                      <h4 className="text-sm font-semibold text-foreground">{g.subject_name}</h4>
                      <span className="text-xs text-muted-foreground">· {g.items.length} kitap</span>
                    </header>
                    <div className="grid gap-3 2xl:grid-cols-2">
                      {g.items.map((b) => (
                        <BookCard key={b.student_book_id} book={b} studentId={studentId} />
                      ))}
                    </div>
                  </section>
                ))
              )}
            </div>
          </div>
        </>
      )}

      <Dialog open={assignOpen} onOpenChange={setAssignOpen}>
        <DialogContent className="flex max-h-[90vh] w-[calc(100vw-2rem)] max-w-5xl flex-col gap-3 overflow-hidden p-5">
          <DialogHeader>
            <DialogTitle>Kitap ata</DialogTitle>
          </DialogHeader>
          <AssignBookSurface
            studentId={studentId}
            alreadyAssignedIds={assignedIds}
            onDone={() => setAssignOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SubjectButton({
  active,
  onClick,
  name,
  count,
  done,
  reserved,
  total,
  dot,
}: {
  active: boolean;
  onClick: () => void;
  name: string;
  count: number;
  done: number;
  reserved: number;
  total: number;
  dot?: string;
}) {
  const pct = total > 0 ? Math.round((100 * done) / total) : 0;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      data-testid="books-subject"
      className={cn(
        "w-full rounded-xl border p-3 text-left transition",
        active
          ? "border-cyan-600 bg-cyan-50 ring-1 ring-cyan-600 dark:bg-cyan-500/10"
          : "border-border bg-card hover:border-cyan-400 hover:bg-muted/40",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={cn("inline-flex items-start gap-1.5 text-sm font-semibold", active ? "text-cyan-950 dark:text-cyan-100" : "text-foreground")}>
          {dot ? <span className={cn("mt-1.5 inline-block size-2 shrink-0 rounded-full", dot)} aria-hidden /> : null}
          <span>{name}</span>
        </span>
        <span className={cn("shrink-0 text-sm font-bold tabular-nums", active ? "text-cyan-900 dark:text-cyan-100" : "text-foreground")}>
          %{pct}
        </span>
      </div>
      <ProgressBar done={done} reserved={reserved} total={total} className="mt-2 h-1.5" />
      <p className={cn("mt-1.5 text-[12px]", active ? "text-cyan-900 dark:text-cyan-200" : "text-muted-foreground")}>
        {count} kitap · <span className="tabular-nums">{Math.max(0, total - done - reserved)}</span> test atanabilir
      </p>
    </button>
  );
}

/* ============================================================ Kitap kartı */

function BookCard({ book, studentId }: { book: StudentBookListItem; studentId: number }) {
  const mut = useUnassignBook(studentId);
  const archiveMut = useArchiveBooks(studentId);
  const isArchived = Boolean(book.is_archived);
  const isDeneme = isDenemeType(book.book_type);
  const unit = isDeneme ? "deneme" : "test";

  const total = book.section_total_tests;
  const done = book.section_completed_total;
  const reserved = book.section_reserved_total;
  const remaining = Math.max(0, total - done - reserved);
  const pct = total > 0 ? Math.round((100 * done) / total) : 0;
  const finished = total > 0 && done >= total;
  const next = book.sections.find((s) => s.test_count - s.completed_count - s.reserved_count > 0);
  const [open, setOpen] = React.useState(false);

  function onRemove() {
    if (!window.confirm(`"${book.book_name}" atamasını kaldırmak istiyor musunuz? Aktif rezerv varsa engellenir.`)) return;
    mut.mutate({ bookId: book.book_id });
  }

  return (
    <article
      data-testid="book-card"
      className={cn(
        "rounded-xl border border-border bg-card p-4",
        isArchived && "bg-slate-50 dark:bg-slate-500/5",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="break-words font-semibold leading-snug text-foreground">{book.book_name}</p>
          <div className="flex flex-wrap items-center gap-1.5">
            <TypeBadge label={book.book_type_label_tr} />
            <SourceBadge kind={book.source_kind} />
            {finished ? (
              <span className="inline-flex rounded-full bg-emerald-600 px-2 py-0.5 text-[11px] font-semibold text-white">Bitti</span>
            ) : null}
            {isArchived ? (
              <span className="inline-flex rounded-full bg-slate-500 px-2 py-0.5 text-[11px] font-semibold text-white">Arşivde</span>
            ) : null}
            {book.publisher ? <span className="text-[12px] text-muted-foreground">{book.publisher}</span> : null}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-xl font-bold tabular-nums text-foreground">%{pct}</p>
          <p className="text-[11px] text-muted-foreground">{done}/{total} {unit}</p>
        </div>
      </div>

      <ProgressBar done={done} reserved={reserved} total={total} className="mt-3" />
      <div className="mt-2">
        <Legend done={done} reserved={reserved} remaining={remaining} unit={unit} />
      </div>

      {total === 0 ? (
        <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-amber-100 px-3 py-2 text-[12px] text-amber-900 dark:bg-amber-500/15 dark:text-amber-100">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          Bu kitapta bölüm/test yok — programa görev verilemez. Kütüphanede bölümlerini ekle.
        </p>
      ) : next && !isArchived ? (
        <p className="mt-2 flex items-start gap-1.5 text-[12.5px] text-muted-foreground">
          <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
          <span>
            Sıradaki: <strong className="text-foreground">{next.label}</strong> ·{" "}
            {next.test_count - next.completed_count - next.reserved_count} {unit} atanabilir
          </span>
        </p>
      ) : null}

      {book.sections.length > 0 ? (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="inline-flex items-center gap-1 text-[12.5px] font-medium text-cyan-800 hover:underline dark:text-cyan-300"
          >
            <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} aria-hidden />
            {isDeneme ? "Denemeler" : "Üniteler"} ({book.sections.length})
          </button>
          {open ? (
            <ul className="mt-2 divide-y divide-border rounded-lg border border-border">
              {book.sections.map((s) => (
                <SectionRow
                  key={s.section_id}
                  section={s}
                  isDeneme={isDeneme}
                  studentId={studentId}
                  studentBookId={book.student_book_id}
                />
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center justify-end gap-1 border-t border-border pt-2">
        <Link
          href={`/teacher/library/books/${book.book_id}`}
          className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <BookOpen className="size-3.5" aria-hidden />
          Kitabı aç
        </Link>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          disabled={archiveMut.isPending}
          onClick={() => archiveMut.mutate({ bookIds: [book.book_id], archived: !isArchived })}
          title={isArchived ? "Kitabı yeniden kullanıma aç" : "Kitabı arşive al — kayıt ve görev geçmişi korunur, kütüphaneden gizlenir."}
        >
          {archiveMut.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : isArchived ? (
            <ArchiveRestore className="size-3.5" aria-hidden />
          ) : (
            <Archive className="size-3.5" aria-hidden />
          )}
          {isArchived ? "Arşivden çıkar" : "Arşivle"}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          disabled={mut.isPending}
          aria-label="Atamayı kaldır"
          className={cn("h-7 text-xs", book.has_reservations ? "opacity-70" : "")}
          title={book.has_reservations ? "Aktif rezerv var — silmek için önce görevleri tamamla/sil." : "Atamayı kaldır"}
        >
          {mut.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Trash2 className="size-3.5" aria-hidden />}
          Kaldır
        </Button>
      </div>
    </article>
  );
}

function SectionRow({
  section: s,
  isDeneme,
  studentId,
  studentBookId,
}: {
  section: StudentBookSectionProgressRow;
  isDeneme: boolean;
  studentId: number;
  studentBookId: number;
}) {
  const remaining = Math.max(0, s.test_count - s.completed_count - s.reserved_count);
  const dim = s.test_count === 0;
  const maxAllowed = Math.max(0, s.test_count - s.reserved_count);
  const unit = isDeneme ? "deneme" : "test";

  const [editing, setEditing] = React.useState(false);
  const [val, setVal] = React.useState(s.completed_count);
  const mut = useSetSectionCompleted(studentId);

  function save() {
    const clamped = Math.max(0, Math.min(val, maxAllowed));
    mut.mutate(
      { studentBookId, sectionId: s.section_id, completedCount: clamped },
      { onSuccess: () => setEditing(false) },
    );
  }

  return (
    <li className={cn("px-3 py-2 text-[12.5px]", dim && "opacity-60")} data-testid="book-section">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="break-words text-foreground">{s.label}</p>
          {!isDeneme && s.topic_name && s.topic_name !== s.label ? (
            <p className="break-words text-[11.5px] text-muted-foreground">Müfredat: {s.topic_name}</p>
          ) : null}
        </div>
        <div className="shrink-0 text-right tabular-nums">
          <span className="font-semibold text-foreground">{s.completed_count}</span>
          <span className="text-muted-foreground">/{s.test_count} çözüldü</span>
        </div>
      </div>
      <ProgressBar done={s.completed_count} reserved={s.reserved_count} total={s.test_count} className="mt-1.5 h-1.5" />
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-muted-foreground">
        {s.reserved_count > 0 ? <span>{s.reserved_count} programda</span> : null}
        <span>{remaining} {unit} atanabilir</span>
        {s.manual_count > 0 ? (
          <span title="Görev dışı — elle/bağımsız çalışma girişiyle işlendi">{s.manual_count} bağımsız çalışma</span>
        ) : null}
        {!dim && !editing ? (
          <button
            type="button"
            onClick={() => {
              setVal(s.completed_count);
              setEditing(true);
            }}
            className="ml-auto text-cyan-800 hover:underline dark:text-cyan-300"
          >
            {s.completed_count > 0 ? "Çözülen sayısını düzenle" : "Öğrenci bunu zaten çözmüştü"}
          </button>
        ) : null}
      </div>

      {editing ? (
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 rounded-md bg-muted/60 px-2 py-1.5">
          <span className="text-[11px] text-muted-foreground">Çözülmüş {unit}:</span>
          <input
            type="number"
            min={0}
            max={maxAllowed}
            value={val}
            onChange={(e) => setVal(Number(e.target.value) || 0)}
            className="h-7 w-16 rounded border border-input bg-background px-1.5 text-xs tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <button
            type="button"
            onClick={() => setVal(maxAllowed)}
            className="rounded border border-border px-1.5 py-0.5 text-[11px] hover:bg-background"
          >
            Tümü ({maxAllowed})
          </button>
          <button
            type="button"
            onClick={save}
            disabled={mut.isPending}
            className="rounded bg-emerald-600 px-2 py-0.5 text-[11px] font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
          >
            Kaydet
          </button>
          <button
            type="button"
            onClick={() => {
              setVal(s.completed_count);
              setEditing(false);
            }}
            className="rounded px-1.5 py-0.5 text-[11px] text-muted-foreground hover:bg-background"
          >
            İptal
          </button>
          {val < s.completed_count - s.manual_count ? (
            <p className="basis-full text-[11px] text-amber-800 dark:text-amber-200">
              Öğrenci çözmediği testi işaretlediyse gerçek sayıyı yaz: fark en yeni görevden geri alınır, o
              testler öğrencinin programında yeniden &quot;bekliyor&quot; olur (görevi silmen gerekmez).
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

/* ============================================================ Bağımsız çalışma */

function SelfStudyCard({ studentId, books }: { studentId: number; books: StudentBookListItem[] }) {
  const listQ = useQuery<SelfStudyListResponse>({
    queryKey: selfStudyKeys.teacherList("me", studentId),
    queryFn: () => getTeacherSelfStudy(studentId),
    staleTime: 30_000,
  });
  const create = useCoachSelfStudyCreate(studentId);
  const review = useReviewSelfStudy();
  const del = useDeleteSelfStudyEntry();
  const [dialogOpen, setDialogOpen] = React.useState(false);

  const items = listQ.data?.items ?? [];
  const pending = items.filter((i) => i.status === "pending");
  const settled = items.filter((i) => i.status !== "pending");

  const optionBooks: SelfStudyOptionBook[] = React.useMemo(
    () =>
      books.map((b) => ({
        student_book_id: b.student_book_id,
        book_id: b.book_id,
        book_name: b.book_name,
        subject_name: b.subject_name,
        book_type_label: b.book_type_label_tr,
        sections: b.sections.map((s) => ({
          section_id: s.section_id,
          label: s.label,
          test_count: s.test_count,
          completed_count: s.completed_count,
          reserved_count: s.reserved_count,
          remaining: Math.max(0, s.test_count - s.completed_count - s.reserved_count),
        })),
      })),
    [books],
  );

  const busy = review.isPending || del.isPending;

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1 space-y-0.5">
          <p className="text-sm font-semibold text-foreground">Bağımsız çalışma</p>
          <p className="text-[12.5px] text-muted-foreground">
            Program dışında çözülen testleri işle — kayıtlar izli tutulur, kitap ilerlemesi güncellenir.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={() => setDialogOpen(true)} disabled={books.length === 0}>
          <Plus className="size-4" aria-hidden />
          Giriş yap
        </Button>
      </div>

      {pending.length > 0 ? (
        <div className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
          <p className="text-xs font-medium text-amber-800 dark:text-amber-200">
            Öğrenci beyanı — onayını bekliyor ({pending.length})
          </p>
          <ul className="divide-y divide-border/60">
            {pending.map((it) => (
              <SelfStudyEntryRow
                key={it.id}
                item={it}
                isBusy={busy}
                onApprove={() => review.mutate({ entryId: it.id, body: { approve: true } })}
                onReject={() => {
                  if (window.confirm("Bu beyanı reddetmek istiyor musun? İlerlemeye işlenmez.")) {
                    review.mutate({ entryId: it.id, body: { approve: false } });
                  }
                }}
              />
            ))}
          </ul>
        </div>
      ) : null}

      {settled.length > 0 ? (
        <details className="group mt-2">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-xs text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden">
            <ChevronRight className="size-3 transition-transform group-open:rotate-90" aria-hidden />
            Geçmiş kayıtlar ({settled.length})
          </summary>
          <ul className="mt-1 divide-y divide-border">
            {settled.slice(0, 15).map((it) => (
              <SelfStudyEntryRow
                key={it.id}
                item={it}
                isBusy={busy}
                onDelete={() => {
                  if (
                    window.confirm(
                      it.status === "approved"
                        ? `Bu kaydı silmek ilerlemeden ${it.applied_count} testi geri alır. Devam?`
                        : "Bu kayıt silinsin mi?",
                    )
                  ) {
                    del.mutate({ entryId: it.id });
                  }
                }}
              />
            ))}
          </ul>
        </details>
      ) : null}

      <SelfStudyEntryDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        books={optionBooks}
        mode="coach"
        isPending={create.isPending}
        onSubmit={(body) => create.mutate(body, { onSuccess: () => setDialogOpen(false) })}
      />
    </div>
  );
}

/* ============================================================ Kitap atama */

type AssignTab = "manual" | "set";

function AssignBookSurface({
  studentId,
  alreadyAssignedIds,
  onDone,
}: {
  studentId: number;
  alreadyAssignedIds: Set<number>;
  onDone: () => void;
}) {
  const [tab, setTab] = React.useState<AssignTab>("manual");
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div role="tablist" aria-label="Atama kaynağı" className="flex items-center gap-1 border-b border-border">
        <TabButton active={tab === "manual"} onClick={() => setTab("manual")}>
          Kütüphanemden seç
        </TabButton>
        <TabButton active={tab === "set"} onClick={() => setTab("set")}>
          Set&apos;ten uygula
        </TabButton>
      </div>
      {tab === "manual" ? (
        <ManualAssignForm studentId={studentId} alreadyAssignedIds={alreadyAssignedIds} onDone={onDone} />
      ) : (
        <SetApplyForm studentId={studentId} alreadyAssignedIds={alreadyAssignedIds} onDone={onDone} />
      )}
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
        active ? "border-foreground font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

type SourceFilter = "all" | "catalog" | "template" | "manual";
const SOURCE_FILTERS: Array<{ key: SourceFilter; label: string }> = [
  { key: "all", label: "Tümü" },
  { key: "catalog", label: "Katalogdan" },
  { key: "template", label: "Şablondan" },
  { key: "manual", label: "Elle oluşturuldu" },
];

function ManualAssignForm({
  studentId,
  alreadyAssignedIds,
  onDone,
}: {
  studentId: number;
  alreadyAssignedIds: Set<number>;
  onDone: () => void;
}) {
  const teacherBooksQ = useQuery<TeacherBookListResponse>({
    queryKey: [...teacherKeys.books(), "for", studentId],
    queryFn: () => getTeacherBooks(studentId),
    staleTime: 60_000,
  });
  const single = useAssignBook(studentId);
  const bulk = useBulkAssignBooks(studentId);

  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [query, setQuery] = React.useState("");
  const [subject, setSubject] = React.useState<number | "all">("all");
  const [source, setSource] = React.useState<SourceFilter>("all");
  const [onlyFitting, setOnlyFitting] = React.useState(true);

  const allBooks = React.useMemo(() => teacherBooksQ.data?.items ?? [], [teacherBooksQ.data]);
  const candidates = React.useMemo(() => allBooks.filter((b) => !alreadyAssignedIds.has(b.id)), [allBooks, alreadyAssignedIds]);
  const assignedCount = allBooks.length - candidates.length;

  const subjects = React.useMemo(() => {
    const m = new Map<number, { id: number; name: string; n: number }>();
    for (const b of candidates) {
      const e = m.get(b.subject_id) ?? { id: b.subject_id, name: b.subject_name ?? "Diğer", n: 0 };
      e.n += 1;
      m.set(b.subject_id, e);
    }
    return Array.from(m.values()).sort((a, b) => a.name.localeCompare(b.name, "tr"));
  }, [candidates]);

  const q = trLower(query.trim());
  const base = candidates.filter(
    (b) =>
      (subject === "all" || b.subject_id === subject) &&
      (source === "all" || (b.source_kind ?? "manual") === source) &&
      (!q || trLower(`${b.name} ${b.publisher ?? ""} ${b.subject_name ?? ""}`).includes(q)),
  );
  const hiddenUnfit = onlyFitting ? base.filter((b) => b.fits_student === false).length : 0;
  const filtered = onlyFitting ? base.filter((b) => b.fits_student !== false) : base;

  const grouped = React.useMemo(() => {
    const m = new Map<string, TeacherBookListItem[]>();
    for (const b of filtered) {
      const k = b.subject_name ?? "Diğer";
      const arr = m.get(k) ?? [];
      arr.push(b);
      m.set(k, arr);
    }
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0], "tr"));
  }, [filtered]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) return;
    if (selected.size === 1) {
      const [only] = selected;
      single.mutate({ body: { book_id: only } }, { onSuccess: () => onDone() });
      return;
    }
    bulk.mutate({ body: { book_ids: Array.from(selected) } }, { onSuccess: () => onDone() });
  }

  const isPending = single.isPending || bulk.isPending;
  const selectedBooks = allBooks.filter((b) => selected.has(b.id));

  return (
    <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col gap-3" data-testid="assign-manual">
      {/* ---- Arama + filtreler */}
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <label className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Kitap adı, yayınevi veya ders ara…"
              aria-label="Kitap ara"
              data-testid="assign-search"
              className="h-10 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
          <select
            value={subject === "all" ? "" : String(subject)}
            onChange={(e) => setSubject(e.target.value ? Number(e.target.value) : "all")}
            aria-label="Ders"
            className="h-10 min-w-[180px] rounded-lg border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Tüm dersler ({candidates.length})</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.n})
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {SOURCE_FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setSource(f.key)}
              aria-pressed={source === f.key}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                source === f.key
                  ? "border-cyan-700 bg-cyan-700 font-semibold text-white"
                  : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {f.label}
            </button>
          ))}
          <label className="ml-auto inline-flex cursor-pointer items-center gap-1.5 text-xs text-foreground">
            <input type="checkbox" checked={onlyFitting} onChange={(e) => setOnlyFitting(e.target.checked)} />
            Yalnız öğrencinin sınıfına uygun
          </label>
        </div>
      </div>

      {/* ---- Liste */}
      <div className="min-h-[240px] flex-1 overflow-y-auto rounded-lg border border-border">
        {teacherBooksQ.isLoading ? (
          <p className="p-4 text-sm text-muted-foreground">Kitap listesi yükleniyor…</p>
        ) : candidates.length === 0 ? (
          <div className="p-6 text-center text-sm text-muted-foreground">
            Atayabileceğin başka kitap yok.{" "}
            <Link href="/teacher/library/new" className="font-medium text-cyan-800 underline dark:text-cyan-300">
              Kütüphaneye kitap ekle →
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Bu aramaya uyan kitap yok.</p>
        ) : (
          grouped.map(([subjectName, books]) => (
            <div key={subjectName}>
              <p className="sticky top-0 z-10 border-b border-border bg-muted px-3 py-1.5 text-xs font-semibold text-foreground">
                {subjectName} <span className="font-normal text-muted-foreground">· {books.length} kitap</span>
              </p>
              <ul className="divide-y divide-border">
                {books.map((b) => (
                  <AssignRow key={b.id} book={b} checked={selected.has(b.id)} onToggle={() => toggle(b.id)} />
                ))}
              </ul>
            </div>
          ))
        )}
      </div>

      {/* ---- Alt bilgi + seçim */}
      <div className="space-y-2 border-t border-border pt-3">
        <p className="text-[12px] text-muted-foreground">
          {filtered.length} kitap listeleniyor
          {hiddenUnfit > 0 ? ` · sınıfa uygun olmayan ${hiddenUnfit} kitap gizli` : ""}
          {assignedCount > 0 ? ` · ${assignedCount} kitap zaten atalı` : ""}
        </p>
        {selectedBooks.length > 0 ? (
          <div className="flex flex-wrap gap-1.5" data-testid="assign-selected">
            {selectedBooks.map((b) => (
              <span
                key={b.id}
                className="inline-flex items-center gap-1 rounded-full bg-cyan-700 py-0.5 pl-2.5 pr-1 text-[12px] font-medium text-white"
              >
                {b.name}
                <button
                  type="button"
                  onClick={() => toggle(b.id)}
                  aria-label={`${b.name} seçimini kaldır`}
                  className="rounded-full p-0.5 hover:bg-cyan-800"
                >
                  <X className="size-3" aria-hidden />
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <div className="flex flex-wrap items-center justify-end gap-2">
          {selected.size > 0 ? (
            <Button type="button" variant="ghost" size="sm" onClick={() => setSelected(new Set())} disabled={isPending}>
              Seçimi temizle
            </Button>
          ) : null}
          <Button type="button" variant="outline" onClick={onDone} disabled={isPending}>
            İptal
          </Button>
          <Button type="submit" disabled={isPending || selected.size === 0} data-testid="assign-submit">
            {isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            {selected.size > 0 ? `${selected.size} kitabı ata` : "Kitap seç"}
          </Button>
        </div>
      </div>
    </form>
  );
}

function AssignRow({ book: b, checked, onToggle }: { book: TeacherBookListItem; checked: boolean; onToggle: () => void }) {
  const empty = b.section_count === 0;
  const dup = (b.same_name_count ?? 1) > 1;
  return (
    <li data-testid="assign-row">
      <label
        className={cn(
          "flex cursor-pointer items-start gap-3 px-3 py-2.5 transition-colors",
          checked ? "bg-cyan-50 dark:bg-cyan-500/10" : "hover:bg-muted/50",
        )}
      >
        <input type="checkbox" checked={checked} onChange={onToggle} aria-label={b.name} className="mt-1 size-4 shrink-0" />
        <span className="min-w-0 flex-1 space-y-1">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className={cn("break-words text-sm font-semibold", checked ? "text-cyan-950 dark:text-cyan-50" : "text-foreground")}>
              {b.name}
            </span>
            <SourceBadge kind={b.source_kind} />
            <TypeBadge label={b.type_label} />
            {b.fits_student === false ? (
              <span className="inline-flex rounded-full bg-amber-500 px-2 py-0.5 text-[11px] font-semibold text-amber-950">
                Başka sınıf için
              </span>
            ) : null}
          </span>
          <span className={cn("block text-[12px]", checked ? "text-cyan-900 dark:text-cyan-100" : "text-muted-foreground")}>
            {[
              b.publisher,
              `${b.section_count} bölüm`,
              `${b.total_tests ?? 0} test`,
              b.grade_label,
              (b.assigned_student_count ?? 0) > 0 ? `${b.assigned_student_count} öğrencide` : "henüz kimsede yok",
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
          {empty ? (
            <span className="flex items-start gap-1 text-[12px] text-amber-800 dark:text-amber-200">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              Bölümü yok — atanırsa programa görev verilemez.
            </span>
          ) : null}
          {dup ? (
            <span className="flex items-start gap-1 text-[12px] text-muted-foreground">
              <Copy className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              Aynı adla {b.same_name_count} kitabın var{b.created_at ? ` · bu kayıt ${formatDate(b.created_at)}` : ""}
            </span>
          ) : null}
        </span>
      </label>
    </li>
  );
}

function formatDate(iso: string) {
  const [y, m, d] = iso.split("-");
  return d && m && y ? `${d}.${m}.${y}` : iso;
}

function SetApplyForm({
  studentId,
  alreadyAssignedIds,
  onDone,
}: {
  studentId: number;
  alreadyAssignedIds: Set<number>;
  onDone: () => void;
}) {
  const setsQ = useQuery<BookSetListResponse>({
    queryKey: libraryKeys.bookSets(),
    queryFn: () => getLibraryBookSets(),
    staleTime: 30_000,
  });
  const studentQ = useQuery<TeacherStudentDetailResponse>({
    queryKey: teacherKeys.student(studentId),
    queryFn: () => getTeacherStudent(studentId),
    staleTime: 60_000,
  });

  const [selectedSetId, setSelectedSetId] = React.useState<number | null>(null);
  const setDetailQ = useQuery<BookSetDetailResponse>({
    queryKey: libraryKeys.bookSet(selectedSetId ?? 0),
    queryFn: () => getLibraryBookSet(selectedSetId as number),
    enabled: selectedSetId !== null,
    staleTime: 30_000,
  });

  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [lastDetailKey, setLastDetailKey] = React.useState<string>("");
  const detail = setDetailQ.data;

  // Set değişince ya da yeni detay gelince: zaten atanmamış kitapları otomatik seç
  // (render-zamanı state karşılaştırması — effect'siz, ESLint güvenli).
  if (detail) {
    const detailKey = `${detail.id}:${detail.items.length}`;
    if (detailKey !== lastDetailKey) {
      const preselected = new Set<number>();
      for (const it of detail.items) {
        if (!alreadyAssignedIds.has(it.book_id)) preselected.add(it.book_id);
      }
      setSelected(preselected);
      setLastDetailKey(detailKey);
    }
  }

  const bulk = useBulkAssignBooks(studentId);

  function toggle(id: number, locked: boolean) {
    if (locked) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) return;
    bulk.mutate({ body: { book_ids: Array.from(selected) } }, { onSuccess: () => onDone() });
  }

  const sets = React.useMemo(() => setsQ.data?.items ?? [], [setsQ.data]);

  const studentGrade = studentQ.data?.student.grade_level ?? null;
  const studentIsGraduate = studentQ.data?.student.is_graduate ?? false;
  const { recommended, others } = React.useMemo(() => {
    const rec: BookSetListItem[] = [];
    const oth: BookSetListItem[] = [];
    for (const s of sets) {
      if (setRecommendedForStudent(s, studentGrade, studentIsGraduate)) rec.push(s);
      else oth.push(s);
    }
    return { recommended: rec, others: oth };
  }, [sets, studentGrade, studentIsGraduate]);

  const selectedSet = selectedSetId !== null ? sets.find((s) => s.id === selectedSetId) ?? null : null;
  const isMismatch = selectedSet !== null && !setRecommendedForStudent(selectedSet, studentGrade, studentIsGraduate);
  const studentLevelLabel = studentIsGraduate ? "Mezun" : studentGrade !== null ? `${studentGrade}. sınıf` : "Sınıf belirsiz";

  return (
    <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="set-picker" className="text-muted-foreground">
          Set:
        </label>
        <select
          id="set-picker"
          value={selectedSetId === null ? "" : String(selectedSetId)}
          onChange={(e) => setSelectedSetId(e.target.value ? Number(e.target.value) : null)}
          className="h-10 min-w-[200px] flex-1 rounded-lg border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">— Set seç —</option>
          {recommended.length > 0 ? (
            <optgroup label={`Önerilen (${studentLevelLabel})`}>
              {recommended.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.target_grade_label_tr} ({s.book_count} kitap)
                </option>
              ))}
            </optgroup>
          ) : null}
          {others.length > 0 ? (
            <optgroup label="Diğer sınıflar">
              {others.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.target_grade_label_tr} ({s.book_count} kitap)
                </option>
              ))}
            </optgroup>
          ) : null}
        </select>
        <Link
          href="/teacher/library/book-sets"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          Setleri yönet <ExternalLink className="size-3" aria-hidden />
        </Link>
      </div>

      {isMismatch && selectedSet ? (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden />
          <div>
            <p className="font-medium text-amber-800 dark:text-amber-200">Bu set öğrencinin sınıfı için önerilen değil.</p>
            <p className="mt-0.5 text-muted-foreground">
              Set hedefi: <strong>{selectedSet.target_grade_label_tr}</strong> · Öğrenci:{" "}
              <strong>{studentLevelLabel}</strong>. Yine de atayabilirsin — sadece bir hatırlatma.
            </p>
          </div>
        </div>
      ) : null}

      <div className="min-h-[200px] flex-1 overflow-y-auto rounded-lg border border-border">
        {sets.length === 0 && !setsQ.isLoading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Henüz kitap setiniz yok.{" "}
            <Link href="/teacher/library/book-sets" className="underline hover:no-underline">
              Set oluştur →
            </Link>
          </p>
        ) : selectedSetId === null ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Yukarıdan bir set seç; içindeki kitaplar listelenir.</p>
        ) : setDetailQ.isLoading || !detail ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Yükleniyor…</p>
        ) : detail.items.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Bu set boş.</p>
        ) : (
          <>
            {detail.notes ? <p className="border-b border-border px-3 py-2 text-xs italic text-muted-foreground">{detail.notes}</p> : null}
            <ul className="divide-y divide-border">
              {detail.items.map((it) => {
                const locked = alreadyAssignedIds.has(it.book_id);
                return (
                  <li key={it.book_id} className={cn("flex items-start gap-3 px-3 py-2 text-sm", locked && "opacity-60")}>
                    <input
                      type="checkbox"
                      checked={selected.has(it.book_id)}
                      onChange={() => toggle(it.book_id, locked)}
                      disabled={locked}
                      aria-label={it.book_name}
                      className="mt-1"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block break-words font-medium text-foreground">{it.book_name}</span>
                      <span className="block text-xs text-muted-foreground">{it.subject_name ?? "—"}</span>
                    </span>
                    {locked ? (
                      <span className="inline-flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                        <Lock className="size-3" aria-hidden />
                        zaten atalı
                      </span>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <p className="text-xs text-muted-foreground">Set kaydı değişmez — sadece bu öğrenciye atama yapılır.</p>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" onClick={onDone} disabled={bulk.isPending}>
            İptal
          </Button>
          <Button type="submit" disabled={bulk.isPending || selected.size === 0}>
            {bulk.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            {selected.size > 0 ? `${selected.size} kitabı ata` : "Kitap seç"}
          </Button>
        </div>
      </div>
    </form>
  );
}

/* ============================================================ Arşiv önerisi */

/**
 * P4 — "Geçen dönemden kalan kitaplar" bandı. Koç hangi kitabı arşivleyeceğini
 * tek tek seçer (yaz tekrarı için tutmak isteyebilir). Aday yoksa render olmaz.
 */
function ArchiveSuggestionBand({ studentId }: { studentId: number }) {
  const q = useQuery<ArchiveCandidatesResponse>({
    queryKey: teacherKeys.archiveCandidates(studentId),
    queryFn: () => getArchiveCandidates(studentId),
    staleTime: 60_000,
  });
  const archiveMut = useArchiveBooks(studentId);
  const [open, setOpen] = React.useState(false);
  const [picked, setPicked] = React.useState<number[]>([]);

  const candidates = q.data?.candidates ?? [];
  if (candidates.length === 0) return null;

  function toggle(id: number) {
    setPicked((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  return (
    <>
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-500/30 dark:bg-amber-500/10">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="font-medium text-amber-900 dark:text-amber-200">Geçen dönemden {candidates.length} kitap duruyor</p>
            <p className="text-xs text-amber-800 dark:text-amber-300">
              {q.data?.period_label ? `${q.data.period_label} ` : ""}dönemi başlamadan atanmıştı. Arşivlemek listeyi
              sadeleştirir; kayıt ve görev geçmişi silinmez, istediğinde geri alırsın.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="shrink-0 border-amber-300 bg-white text-amber-900 hover:bg-amber-100 hover:text-amber-900 dark:border-amber-500/40 dark:bg-transparent dark:text-amber-200"
            onClick={() => {
              setPicked(candidates.map((cd) => cd.book_id));
              setOpen(true);
            }}
          >
            <Archive className="size-4" aria-hidden />
            Gözden geçir
          </Button>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Geçen dönemin kitaplarını arşivle</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">
            Arşivlenen kitap kütüphaneden, görev kaynak seçicisinden ve müfredat kapsamasından gizlenir. Geçmiş
            görevler, çözülmüş test sayıları ve analizler olduğu gibi kalır. Yaz tekrarı için tutmak istediğin
            kitabın işaretini kaldır.
          </p>
          <div className="max-h-72 space-y-1.5 overflow-y-auto">
            {candidates.map((cd) => (
              <label key={cd.book_id} className="flex cursor-pointer items-start gap-2 rounded-md border p-2 text-sm hover:bg-muted/50">
                <input type="checkbox" className="mt-0.5" checked={picked.includes(cd.book_id)} onChange={() => toggle(cd.book_id)} />
                <span className="min-w-0 flex-1">
                  <span className="block break-words font-medium">{cd.book_name}</span>
                  <span className="block text-xs text-muted-foreground">
                    {cd.subject_name ?? "—"}
                    {cd.assigned_on ? ` · ${cd.assigned_on} tarihinde atandı` : ""}
                    {" · "}
                    {cd.completed_tests}/{cd.total_tests} test çözülmüş
                    {cd.reserved_tests > 0 ? ` · ${cd.reserved_tests} rezerv` : ""}
                  </span>
                </span>
              </label>
            ))}
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Vazgeç
            </Button>
            <Button
              size="sm"
              disabled={picked.length === 0 || archiveMut.isPending}
              onClick={() => archiveMut.mutate({ bookIds: picked, archived: true }, { onSuccess: () => setOpen(false) })}
            >
              {archiveMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Archive className="size-4" aria-hidden />}
              {picked.length} kitabı arşivle
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
