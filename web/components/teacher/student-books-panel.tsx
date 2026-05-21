"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronRight,
  ExternalLink,
  Loader2,
  Lock,
  Plus,
  Trash2,
} from "lucide-react";

import {
  getTeacherBooks,
  getTeacherStudent,
  getTeacherStudentBooks,
  teacherKeys,
} from "@/lib/api/teacher";
import { getLibraryBookSet, getLibraryBookSets, libraryKeys } from "@/lib/api/library";
import { setRecommendedForStudent } from "@/lib/utils/book-sets";
import {
  useAssignBook,
  useBulkAssignBooks,
  useUnassignBook,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  StudentBookListItem,
  StudentBookListResponse,
  StudentBookSectionProgressRow,
  TeacherBookListResponse,
  TeacherStudentDetailResponse,
} from "@/lib/types/teacher";
import type {
  BookSetDetailResponse,
  BookSetListItem,
  BookSetListResponse,
} from "@/lib/types/library";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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

// Sabit pastel paleti — subject_id stable hash → ton; her ders aynı tonu alır
const SUBJECT_TONES: Array<{
  border: string;
  ring: string;
  dot: string;
  text: string;
}> = [
  { border: "border-l-indigo-500",  ring: "ring-indigo-500/10",  dot: "bg-indigo-500",  text: "text-indigo-600 dark:text-indigo-400" },
  { border: "border-l-emerald-500", ring: "ring-emerald-500/10", dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" },
  { border: "border-l-amber-500",   ring: "ring-amber-500/10",   dot: "bg-amber-500",   text: "text-amber-600 dark:text-amber-400" },
  { border: "border-l-rose-500",    ring: "ring-rose-500/10",    dot: "bg-rose-500",    text: "text-rose-600 dark:text-rose-400" },
  { border: "border-l-violet-500",  ring: "ring-violet-500/10",  dot: "bg-violet-500",  text: "text-violet-600 dark:text-violet-400" },
  { border: "border-l-cyan-500",    ring: "ring-cyan-500/10",    dot: "bg-cyan-500",    text: "text-cyan-600 dark:text-cyan-400" },
  { border: "border-l-fuchsia-500", ring: "ring-fuchsia-500/10", dot: "bg-fuchsia-500", text: "text-fuchsia-600 dark:text-fuchsia-400" },
  { border: "border-l-sky-500",     ring: "ring-sky-500/10",     dot: "bg-sky-500",     text: "text-sky-600 dark:text-sky-400" },
];

function subjectTone(subjectId: number) {
  return SUBJECT_TONES[Math.abs(subjectId) % SUBJECT_TONES.length];
}

interface SubjectGroup {
  subject_id: number;
  subject_name: string;
  items: StudentBookListItem[];
}

function groupBySubject(items: StudentBookListItem[]): SubjectGroup[] {
  const map = new Map<number, SubjectGroup>();
  for (const it of items) {
    const g = map.get(it.subject_id);
    if (g) g.items.push(it);
    else
      map.set(it.subject_id, {
        subject_id: it.subject_id,
        subject_name: it.subject_name,
        items: [it],
      });
  }
  return Array.from(map.values()).sort((a, b) =>
    a.subject_name.localeCompare(b.subject_name, "tr"),
  );
}

export function StudentBooksPanel({ studentId }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const subjectParam = searchParams.get("subject_id");
  const activeSubjectId = subjectParam ? Number(subjectParam) : null;

  const booksQ = useQuery<StudentBookListResponse>({
    queryKey: teacherKeys.studentBooks(studentId),
    queryFn: () => getTeacherStudentBooks(studentId),
    staleTime: 30_000,
  });
  const [assignOpen, setAssignOpen] = React.useState(false);
  const data = booksQ.data;
  const allItems = React.useMemo(() => data?.items ?? [], [data]);
  const assignedIds = React.useMemo(
    () => new Set(allItems.map((b) => b.book_id)),
    [allItems],
  );
  const groups = React.useMemo(() => groupBySubject(allItems), [allItems]);

  const visibleGroups =
    activeSubjectId !== null
      ? groups.filter((g) => g.subject_id === activeSubjectId)
      : groups;
  const visibleCount = visibleGroups.reduce((s, g) => s + g.items.length, 0);

  function setSubjectFilter(subjectId: number | null) {
    const sp = new URLSearchParams(searchParams.toString());
    if (subjectId === null) sp.delete("subject_id");
    else sp.set("subject_id", String(subjectId));
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}#books` : `${pathname}#books`, {
      scroll: false,
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-0.5">
          <h3 className="text-base font-medium">Kitap envanteri</h3>
          <p className="text-xs text-muted-foreground">
            {booksQ.isLoading && !data
              ? "Yükleniyor…"
              : `${allItems.length} kitap · ${groups.length} ders`}
            {activeSubjectId !== null && allItems.length !== visibleCount ? (
              <>
                {" · "}
                <span className="text-foreground">
                  Filtrede {visibleCount}
                </span>
              </>
            ) : null}
            {booksQ.isFetching && !booksQ.isLoading ? (
              <span className="ml-2 text-muted-foreground/70">
                · güncelleniyor…
              </span>
            ) : null}
          </p>
        </div>
        <Button size="sm" onClick={() => setAssignOpen(true)}>
          <Plus className="size-4" aria-hidden />
          Kitap ata
        </Button>
      </div>

      {groups.length > 1 ? (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <FilterChip
            active={activeSubjectId === null}
            onClick={() => setSubjectFilter(null)}
            label={`Tümü (${allItems.length})`}
          />
          {groups.map((g) => {
            const tone = subjectTone(g.subject_id);
            return (
              <FilterChip
                key={g.subject_id}
                active={activeSubjectId === g.subject_id}
                onClick={() => setSubjectFilter(g.subject_id)}
                label={`${g.subject_name} (${g.items.length})`}
                dotClassName={tone.dot}
              />
            );
          })}
        </div>
      ) : null}

      {booksQ.isLoading && !data ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Yükleniyor…
          </CardContent>
        </Card>
      ) : visibleGroups.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            {allItems.length === 0
              ? "Bu öğrenciye henüz kitap atanmamış."
              : "Bu filtrede kitap yok."}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {visibleGroups.map((g) => (
            <SubjectGroupSection key={g.subject_id} group={g} studentId={studentId} />
          ))}
        </div>
      )}

      <Dialog open={assignOpen} onOpenChange={setAssignOpen}>
        <DialogContent className="max-w-2xl">
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

function FilterChip({
  active,
  onClick,
  label,
  dotClassName,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  dotClassName?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 border transition-colors",
        active
          ? "border-foreground bg-foreground text-background"
          : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {dotClassName ? (
        <span
          className={cn("inline-block size-1.5 rounded-full", dotClassName)}
          aria-hidden
        />
      ) : null}
      {label}
    </button>
  );
}

function SubjectGroupSection({
  group,
  studentId,
}: {
  group: SubjectGroup;
  studentId: number;
}) {
  const tone = subjectTone(group.subject_id);
  return (
    <section className="space-y-3">
      <header className="flex items-center gap-2">
        <span className={cn("inline-block size-2 rounded-full", tone.dot)} aria-hidden />
        <h4 className={cn("text-sm font-medium uppercase tracking-wide", tone.text)}>
          {group.subject_name}
        </h4>
        <span className="text-xs text-muted-foreground">· {group.items.length} kitap</span>
      </header>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {group.items.map((b) => (
          <BookCard key={b.student_book_id} book={b} studentId={studentId} />
        ))}
      </div>
    </section>
  );
}

function BookCard({
  book,
  studentId,
}: {
  book: StudentBookListItem;
  studentId: number;
}) {
  const tone = subjectTone(book.subject_id);
  const mut = useUnassignBook(studentId);

  const total = book.section_total_tests;
  const done = book.section_completed_total;
  const reserved = book.section_reserved_total;
  const remaining = Math.max(0, total - done - reserved);
  const pctDone = total > 0 ? Math.round((100 * done) / total) : 0;
  const pctReserved = total > 0 ? Math.round((100 * reserved) / total) : 0;
  const isDeneme =
    book.book_type === "brans_denemesi" || book.book_type === "genel_deneme";
  const breakdownLabel = isDeneme ? "Deneme kırılımı" : "Ünite kırılımı";

  function onRemove() {
    if (
      !window.confirm(
        `"${book.book_name}" atamasını kaldırmak istiyor musunuz? Aktif rezerv varsa engellenir.`,
      )
    ) {
      return;
    }
    mut.mutate({ bookId: book.book_id });
  }

  return (
    <Card className={cn("border-l-4 ring-1 ring-inset", tone.border, tone.ring)}>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="font-medium truncate">{book.book_name}</p>
            <p className="text-xs text-muted-foreground truncate">
              {book.publisher ?? "—"} · {book.book_type_label_tr}
            </p>
          </div>
          <div className="text-right shrink-0">
            <p className="font-semibold tabular-nums">
              {remaining}
              <span className="text-muted-foreground"> / </span>
              {total}
            </p>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              kalan / toplam
            </p>
          </div>
        </div>

        <ProgressBar
          pctDone={pctDone}
          pctReserved={pctReserved}
        />

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <Chip dotColor="bg-emerald-500" label="Çözüldü" value={done} />
          <Chip dotColor="bg-amber-500" label="Rezerv" value={reserved} />
          <Chip dotColor="bg-muted-foreground/40" label="Kalan" value={remaining} />
          <span className="ml-auto text-muted-foreground tabular-nums">
            %{pctDone}
          </span>
        </div>

        {book.sections.length > 0 ? (
          <details className="group">
            <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground inline-flex items-center gap-1 list-none [&::-webkit-details-marker]:hidden">
              <ChevronRight
                className="size-3 transition-transform group-open:rotate-90"
                aria-hidden
              />
              {breakdownLabel} ({book.sections.length})
            </summary>
            <ul className="mt-2 divide-y divide-border border-t border-border">
              {book.sections.map((s) => (
                <SectionRow key={s.section_id} section={s} isDeneme={isDeneme} />
              ))}
            </ul>
          </details>
        ) : null}

        <div className="flex items-center justify-end pt-1 -mb-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={onRemove}
            disabled={mut.isPending}
            aria-label="Atamayı kaldır"
            className={cn(
              "h-7 text-xs",
              book.has_reservations ? "opacity-70" : "",
            )}
            title={
              book.has_reservations
                ? "Aktif rezerv var — silmek için önce görevleri tamamla/sil."
                : "Atamayı kaldır"
            }
          >
            {mut.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="size-3.5" aria-hidden />
            )}
            Kaldır
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ProgressBar({
  pctDone,
  pctReserved,
}: {
  pctDone: number;
  pctReserved: number;
}) {
  const doneWidth = Math.min(100, Math.max(0, pctDone));
  const reservedWidth = Math.min(100 - doneWidth, Math.max(0, pctReserved));
  return (
    <div
      className="h-2 w-full rounded-full bg-muted overflow-hidden flex"
      role="progressbar"
      aria-valuenow={doneWidth + reservedWidth}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full bg-emerald-500 transition-[width]"
        style={{ width: `${doneWidth}%` }}
      />
      <div
        className="h-full bg-amber-500 transition-[width]"
        style={{ width: `${reservedWidth}%` }}
      />
    </div>
  );
}

function Chip({
  dotColor,
  label,
  value,
}: {
  dotColor: string;
  label: string;
  value: number;
}) {
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground">
      <span className={cn("inline-block size-1.5 rounded-full", dotColor)} aria-hidden />
      <span>{label}</span>
      <span className="tabular-nums text-foreground">{value}</span>
    </span>
  );
}

function SectionRow({
  section: s,
  isDeneme,
}: {
  section: StudentBookSectionProgressRow;
  isDeneme: boolean;
}) {
  const remaining = Math.max(0, s.test_count - s.completed_count - s.reserved_count);
  const dim = s.test_count === 0;
  return (
    <li
      className={cn(
        "py-1.5 flex items-start justify-between gap-3 text-xs",
        dim && "opacity-60",
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate">{s.label}</p>
        {!isDeneme && s.topic_name ? (
          <p className="text-muted-foreground truncate">{s.topic_name}</p>
        ) : null}
      </div>
      <div className="shrink-0 tabular-nums text-right space-x-1">
        <span>
          {remaining}
          <span className="text-muted-foreground">/{s.test_count}</span>
          <span className="text-muted-foreground"> kalan</span>
        </span>
        {s.reserved_count > 0 ? (
          <span className="text-amber-600 dark:text-amber-400">
            ({s.reserved_count} rezerv)
          </span>
        ) : null}
        {s.completed_count > 0 ? (
          <span className="text-emerald-600 dark:text-emerald-400">
            ({s.completed_count} çöz.)
          </span>
        ) : null}
      </div>
    </li>
  );
}

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
    <div className="space-y-3">
      <div
        role="tablist"
        aria-label="Atama kaynağı"
        className="flex items-center gap-1 border-b border-border"
      >
        <TabButton active={tab === "manual"} onClick={() => setTab("manual")}>
          Tek tek seç
        </TabButton>
        <TabButton active={tab === "set"} onClick={() => setTab("set")}>
          Set&apos;ten uygula
        </TabButton>
      </div>
      {tab === "manual" ? (
        <ManualAssignForm
          studentId={studentId}
          alreadyAssignedIds={alreadyAssignedIds}
          onDone={onDone}
        />
      ) : (
        <SetApplyForm
          studentId={studentId}
          alreadyAssignedIds={alreadyAssignedIds}
          onDone={onDone}
        />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "px-3 py-2 -mb-px text-sm border-b-2 transition-colors",
        active
          ? "border-foreground font-medium"
          : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

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
    queryKey: teacherKeys.books(),
    queryFn: () => getTeacherBooks(),
    staleTime: 60_000,
  });
  const single = useAssignBook(studentId);
  const bulk = useBulkAssignBooks(studentId);

  const [selected, setSelected] = React.useState<Set<number>>(new Set());

  const allBooks = teacherBooksQ.data?.items ?? [];
  const candidates = allBooks.filter((b) => !alreadyAssignedIds.has(b.id));

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
      single.mutate(
        { body: { book_id: only } },
        { onSuccess: () => onDone() },
      );
      return;
    }
    bulk.mutate(
      { body: { book_ids: Array.from(selected) } },
      { onSuccess: () => onDone() },
    );
  }

  const isPending = single.isPending || bulk.isPending;

  return (
    <form onSubmit={submit} className="space-y-3">
      {teacherBooksQ.isLoading ? (
        <p className="text-sm text-muted-foreground">Kitap listesi yükleniyor…</p>
      ) : candidates.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Atayabileceğin başka kitap yok. Önce kitap oluştur.
        </p>
      ) : (
        <ul className="max-h-[50vh] overflow-y-auto divide-y divide-border border border-border rounded-md">
          {candidates.map((b) => (
            <li key={b.id} className="px-3 py-2 flex items-center gap-3 text-sm">
              <input
                type="checkbox"
                checked={selected.has(b.id)}
                onChange={() => toggle(b.id)}
                aria-label={b.name}
              />
              <span className="flex-1 min-w-0">
                <span className="font-medium truncate block">{b.name}</span>
                <span className="text-xs text-muted-foreground truncate block">
                  {b.subject_name ?? "—"} · {b.section_count} bölüm
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button type="button" variant="ghost" onClick={onDone} disabled={isPending}>
          İptal
        </Button>
        <Button type="submit" disabled={isPending || selected.size === 0}>
          {isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          {selected.size > 0 ? `${selected.size} kitap ata` : "Ata"}
        </Button>
      </div>
    </form>
  );
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

  // Set değişince ya da yeni detay gelince: zaten atanmamış kitapları otomatik seç.
  // (React.useEffect yerine render-zamanı state karşılaştırması — book-set-detail-client
  // ile aynı kalıp; ref kullanımı yerine ESLint güvenli.)
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
    bulk.mutate(
      { body: { book_ids: Array.from(selected) } },
      { onSuccess: () => onDone() },
    );
  }

  const sets = React.useMemo(
    () => setsQ.data?.items ?? [],
    [setsQ.data],
  );

  // Setleri öğrencinin sınıfına göre Önerilen / Diğer şeklinde böl
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

  // Seçili setin uyum durumu — uyarı banner için
  const selectedSet = selectedSetId !== null
    ? sets.find((s) => s.id === selectedSetId) ?? null
    : null;
  const isMismatch =
    selectedSet !== null &&
    !setRecommendedForStudent(selectedSet, studentGrade, studentIsGraduate);

  const studentLevelLabel = studentIsGraduate
    ? "Mezun"
    : studentGrade !== null
      ? `${studentGrade}. sınıf`
      : "Sınıf belirsiz";

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="set-picker" className="text-muted-foreground">
          Set:
        </label>
        <select
          id="set-picker"
          value={selectedSetId === null ? "" : String(selectedSetId)}
          onChange={(e) =>
            setSelectedSetId(e.target.value ? Number(e.target.value) : null)
          }
          className={cn(
            "h-9 flex-1 min-w-[200px] rounded-md border border-input bg-background px-2 text-sm",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
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
          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          Setleri yönet <ExternalLink className="size-3" aria-hidden />
        </Link>
      </div>

      {isMismatch && selectedSet ? (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs flex items-start gap-2">
          <AlertTriangle
            className="size-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5"
            aria-hidden
          />
          <div>
            <p className="font-medium text-amber-700 dark:text-amber-300">
              Bu set öğrencinin sınıfı için önerilen değil.
            </p>
            <p className="text-muted-foreground mt-0.5">
              Set hedefi: <strong>{selectedSet.target_grade_label_tr}</strong>{" "}
              · Öğrenci: <strong>{studentLevelLabel}</strong>. Yine de
              atayabilirsin — sadece bir hatırlatma.
            </p>
          </div>
        </div>
      ) : null}

      {sets.length === 0 && !setsQ.isLoading ? (
        <p className="text-sm text-muted-foreground py-6 text-center">
          Henüz kitap setiniz yok.{" "}
          <Link
            href="/teacher/library/book-sets"
            className="underline hover:no-underline"
          >
            Set oluştur →
          </Link>
        </p>
      ) : selectedSetId === null ? (
        <p className="text-sm text-muted-foreground py-6 text-center">
          Yukarıdan bir set seç; içindeki kitaplar listelenir.
        </p>
      ) : setDetailQ.isLoading || !detail ? (
        <p className="text-sm text-muted-foreground py-6 text-center">
          Yükleniyor…
        </p>
      ) : detail.items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-6 text-center">
          Bu set boş.
        </p>
      ) : (
        <>
          {detail.notes ? (
            <p className="text-xs text-muted-foreground italic">{detail.notes}</p>
          ) : null}
          <ul className="max-h-[45vh] overflow-y-auto divide-y divide-border border border-border rounded-md">
            {detail.items.map((it) => {
              const locked = alreadyAssignedIds.has(it.book_id);
              return (
                <li
                  key={it.book_id}
                  className={cn(
                    "px-3 py-2 flex items-center gap-3 text-sm",
                    locked && "opacity-60",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(it.book_id)}
                    onChange={() => toggle(it.book_id, locked)}
                    disabled={locked}
                    aria-label={it.book_name}
                  />
                  <span className="flex-1 min-w-0">
                    <span className="font-medium truncate block">
                      {it.book_name}
                    </span>
                    <span className="text-xs text-muted-foreground truncate block">
                      {it.subject_name ?? "—"}
                    </span>
                  </span>
                  {locked ? (
                    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground shrink-0">
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

      <div className="flex items-center justify-between gap-2 pt-2 border-t border-border">
        <p className="text-xs text-muted-foreground">
          Set kaydı değişmez — sadece bu öğrenciye atama yapılır.
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={onDone}
            disabled={bulk.isPending}
          >
            İptal
          </Button>
          <Button type="submit" disabled={bulk.isPending || selected.size === 0}>
            {bulk.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            {selected.size > 0 ? `${selected.size} kitap ata` : "Ata"}
          </Button>
        </div>
      </div>
    </form>
  );
}
