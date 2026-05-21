"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus, SearchX, Trash2, Users } from "lucide-react";

import { getLibraryBookSet, libraryKeys } from "@/lib/api/library";
import {
  useAddBooksToSet,
  useDeleteBookSet,
  usePatchBookSet,
  useRemoveBookFromSet,
} from "@/lib/hooks/use-library-mutations";
import type {
  BookSetAssignedStudent,
  BookSetDetailResponse,
  BookSetGradeBucket,
  LibraryBookListItem,
  LibraryBookType,
  SubjectRef,
} from "@/lib/types/library";
import {
  CURRICULUM_MODEL_LABELS_TR,
  LIBRARY_BOOK_TYPE_LABELS_TR,
} from "@/lib/types/library";
import type { CurriculumModel } from "@/lib/types/library";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import {
  TargetGradePicker,
  targetGradeBody,
  targetGradeFromFields,
  type TargetGradeValue,
} from "@/components/target-grade-picker";

interface Props {
  initial: BookSetDetailResponse;
  allBooks: LibraryBookListItem[];
  allSubjects: SubjectRef[];
}

export function BookSetDetailClient({ initial, allBooks, allSubjects }: Props) {
  const router = useRouter();
  const q = useQuery<BookSetDetailResponse>({
    queryKey: libraryKeys.bookSet(initial.id),
    queryFn: () => getLibraryBookSet(initial.id),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const bs = q.data ?? initial;
  const memberIds = new Set(bs.items.map((it) => it.book_id));
  const candidates = allBooks.filter((b) => !memberIds.has(b.id));

  const patchMut = usePatchBookSet(bs.id);
  const deleteSetMut = useDeleteBookSet(bs.id);
  const addBooksMut = useAddBooksToSet(bs.id);
  const removeBookMut = useRemoveBookFromSet(bs.id);

  const [editing, setEditing] = React.useState(false);
  const [name, setName] = React.useState(bs.name);
  const [notes, setNotes] = React.useState(bs.notes ?? "");
  const [grade, setGrade] = React.useState<TargetGradeValue>(() =>
    targetGradeFromFields(
      bs.target_grade_min,
      bs.target_grade_max,
      bs.target_graduate,
    ),
  );
  const [addOpen, setAddOpen] = React.useState(false);
  const [selectedToAdd, setSelectedToAdd] = React.useState<Set<number>>(
    new Set(),
  );

  // bs değişince form değerlerini güncelle (rendering sırasında)
  const [lastBsKey, setLastBsKey] = React.useState(
    `${bs.name}::${bs.notes ?? ""}::${bs.target_grade_min}::${bs.target_grade_max}::${bs.target_graduate}`,
  );
  const currentKey = `${bs.name}::${bs.notes ?? ""}::${bs.target_grade_min}::${bs.target_grade_max}::${bs.target_graduate}`;
  if (!editing && currentKey !== lastBsKey) {
    setLastBsKey(currentKey);
    setName(bs.name);
    setNotes(bs.notes ?? "");
    setGrade(
      targetGradeFromFields(
        bs.target_grade_min,
        bs.target_grade_max,
        bs.target_graduate,
      ),
    );
  }

  function savePatch() {
    const gradeBody = targetGradeBody(grade);
    patchMut.mutate(
      {
        body: {
          name: name.trim() !== bs.name ? name.trim() : undefined,
          notes:
            (notes.trim() || null) !== (bs.notes ?? null)
              ? notes.trim() || null
              : undefined,
          target_grade_min: gradeBody.target_grade_min,
          target_grade_max: gradeBody.target_grade_max,
          target_graduate: gradeBody.target_graduate,
        },
      },
      { onSettled: () => setEditing(false) },
    );
  }

  function deleteSet() {
    if (!window.confirm(`"${bs.name}" setini silmek istiyor musunuz?`)) return;
    deleteSetMut.mutate(undefined, {
      onSuccess: () => router.push("/teacher/library/book-sets"),
    });
  }

  function addBooks() {
    if (selectedToAdd.size === 0) return;
    addBooksMut.mutate(
      { body: { book_ids: Array.from(selectedToAdd) } },
      {
        onSuccess: () => {
          setSelectedToAdd(new Set());
          setAddOpen(false);
        },
      },
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            <Link href="/teacher/library/book-sets" className="hover:underline">
              Kitap setleri
            </Link>
          </p>
          {editing ? (
            <div className="space-y-3 mt-1 max-w-2xl">
              <div className="space-y-1">
                <Label htmlFor="edit-name">Set adı</Label>
                <Input
                  id="edit-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="edit-notes">Açıklama</Label>
                <Input
                  id="edit-notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Açıklama"
                />
              </div>
              <TargetGradePicker
                value={grade}
                onChange={setGrade}
                idPrefix="edit-tg"
              />
              <div className="flex gap-2 pt-2 border-t border-border">
                <Button
                  size="sm"
                  onClick={savePatch}
                  disabled={patchMut.isPending}
                >
                  Kaydet
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setName(bs.name);
                    setNotes(bs.notes ?? "");
                    setGrade(
                      targetGradeFromFields(
                        bs.target_grade_min,
                        bs.target_grade_max,
                        bs.target_graduate,
                      ),
                    );
                    setEditing(false);
                  }}
                >
                  İptal
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-baseline gap-2 flex-wrap">
                <h1 className="text-2xl font-semibold tracking-tight font-display truncate">
                  {bs.name}
                </h1>
                <span className="shrink-0 text-[11px] font-medium px-2 py-0.5 rounded bg-muted text-muted-foreground whitespace-nowrap">
                  {bs.target_grade_label_tr}
                </span>
              </div>
              {bs.notes ? (
                <p className="text-sm text-muted-foreground">{bs.notes}</p>
              ) : null}
              <p className="text-sm text-muted-foreground">
                {bs.items.length} kitap
              </p>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!editing ? (
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              Düzenle
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            onClick={deleteSet}
            disabled={deleteSetMut.isPending}
          >
            {deleteSetMut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="size-4" aria-hidden />
            )}
            Sil
          </Button>
        </div>
      </header>

      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">Setteki kitaplar</h2>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="size-4" aria-hidden />
              Kitap ekle
            </Button>
          </div>
          {bs.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Sette henüz kitap yok.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {bs.items.map((it) => (
                <li
                  key={it.book_id}
                  className="py-2 flex items-center gap-3 text-sm"
                >
                  <Link
                    href={`/teacher/library/books/${it.book_id}`}
                    className="flex-1 min-w-0 hover:underline"
                  >
                    <span className="font-medium truncate block">
                      {it.book_name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {it.subject_name ?? "—"} ·{" "}
                      {LIBRARY_BOOK_TYPE_LABELS_TR[it.book_type]}
                    </span>
                  </Link>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      removeBookMut.mutate({ bookId: it.book_id })
                    }
                    disabled={removeBookMut.isPending}
                    aria-label="Setten çıkar"
                  >
                    {removeBookMut.isPending ? (
                      <Loader2 className="size-4 animate-spin" aria-hidden />
                    ) : (
                      <Trash2 className="size-4" aria-hidden />
                    )}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <AssignedStudentsSection
        students={bs.assigned_students}
        gradeDistribution={bs.grade_distribution}
        setBookCount={bs.items.length}
      />

      <AddBooksDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        candidates={candidates}
        subjects={allSubjects}
        selected={selectedToAdd}
        setSelected={setSelectedToAdd}
        isPending={addBooksMut.isPending}
        onSubmit={addBooks}
      />
    </div>
  );
}

// =============================================================================
// Kitap ekle dialog'u — arama + tip + ders/müfredat gruplama (3.5d.6)
// =============================================================================

function AddBooksDialog({
  open,
  onOpenChange,
  candidates,
  subjects,
  selected,
  setSelected,
  isPending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  candidates: LibraryBookListItem[];
  subjects: SubjectRef[];
  selected: Set<number>;
  setSelected: React.Dispatch<React.SetStateAction<Set<number>>>;
  isPending: boolean;
  onSubmit: () => void;
}) {
  const [query, setQuery] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState<LibraryBookType | "">("");

  function handleOpenChange(o: boolean) {
    if (!o) {
      setQuery("");
      setTypeFilter("");
    }
    onOpenChange(o);
  }

  const subjectMeta = React.useMemo(() => {
    const m = new Map<number, SubjectRef>();
    for (const s of subjects) m.set(s.id, s);
    return m;
  }, [subjects]);

  // Arama + tip filtre uygulanmış kitaplar
  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return candidates.filter((b) => {
      if (typeFilter && b.type !== typeFilter) return false;
      if (!q) return true;
      const hay = `${b.name} ${b.publisher ?? ""} ${b.subject_name ?? ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [candidates, query, typeFilter]);

  // Grupla: önce müfredat (curriculum_model), sonra ders adı.
  // candidates'in subject_id'sini → SubjectRef üzerinden curriculum_model'e map'liyoruz.
  interface Group {
    curriculum: CurriculumModel | "other";
    curriculumLabel: string;
    subjectId: number;
    subjectName: string;
    books: LibraryBookListItem[];
  }
  const groups = React.useMemo<Group[]>(() => {
    const bySubject = new Map<number, LibraryBookListItem[]>();
    for (const b of filtered) {
      const arr = bySubject.get(b.subject_id);
      if (arr) arr.push(b);
      else bySubject.set(b.subject_id, [b]);
    }
    const result: Group[] = [];
    for (const [sid, books] of bySubject.entries()) {
      const meta = subjectMeta.get(sid);
      const cm = (meta?.curriculum_model as CurriculumModel | null) ?? null;
      result.push({
        curriculum: cm ?? "other",
        curriculumLabel:
          cm !== null
            ? CURRICULUM_MODEL_LABELS_TR[cm]
            : "Diğer / Sınıflandırılmamış",
        subjectId: sid,
        subjectName: meta?.name ?? books[0]?.subject_name ?? "—",
        books,
      });
    }
    // Sırala: müfredat sırası → ders adı
    const cmOrder: Record<string, number> = {
      lgs: 0,
      maarif_lise: 1,
      klasik_lise: 2,
      other: 3,
    };
    result.sort((a, b) => {
      const ca = cmOrder[a.curriculum] ?? 99;
      const cb = cmOrder[b.curriculum] ?? 99;
      if (ca !== cb) return ca - cb;
      return a.subjectName.localeCompare(b.subjectName, "tr");
    });
    return result;
  }, [filtered, subjectMeta]);

  // Curriculum'lara göre üst-grupla (header)
  interface CurriculumBlock {
    curriculum: string;
    curriculumLabel: string;
    groups: Group[];
  }
  const curriculumBlocks = React.useMemo<CurriculumBlock[]>(() => {
    const blocks = new Map<string, CurriculumBlock>();
    for (const g of groups) {
      const key = g.curriculum;
      const b = blocks.get(key);
      if (b) b.groups.push(g);
      else
        blocks.set(key, {
          curriculum: key,
          curriculumLabel: g.curriculumLabel,
          groups: [g],
        });
    }
    return Array.from(blocks.values());
  }, [groups]);

  const typeCounts = React.useMemo(() => {
    const c: Record<string, number> = {};
    for (const b of candidates) c[b.type] = (c[b.type] ?? 0) + 1;
    return c;
  }, [candidates]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Sete kitap ekle</DialogTitle>
        </DialogHeader>

        {candidates.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center">
            Tüm kitaplar zaten sette. Önce yeni kitap oluşturun.
          </p>
        ) : (
          <div className="space-y-3">
            <Input
              type="search"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Kitap, yayınevi veya ders ara…"
              aria-label="Kitap ara"
            />

            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium mr-1">
                Tip
              </span>
              <DialogChip
                active={typeFilter === ""}
                onClick={() => setTypeFilter("")}
                label="Tümü"
                count={candidates.length}
              />
              {(
                ["soru_bankasi", "fasikul", "konu_anlatimli", "brans_denemesi", "genel_deneme"] as LibraryBookType[]
              ).map((t) => {
                const count = typeCounts[t] ?? 0;
                if (count === 0 && typeFilter !== t) return null;
                return (
                  <DialogChip
                    key={t}
                    active={typeFilter === t}
                    onClick={() => setTypeFilter(t)}
                    label={LIBRARY_BOOK_TYPE_LABELS_TR[t]}
                    count={count}
                  />
                );
              })}
            </div>

            <div className="max-h-[55vh] overflow-y-auto rounded-md border border-border divide-y divide-border">
              {filtered.length === 0 ? (
                <div className="p-8 text-center text-sm text-muted-foreground space-y-2">
                  <SearchX
                    className="size-6 mx-auto text-muted-foreground/60"
                    aria-hidden
                  />
                  <p>Eşleşen kitap yok.</p>
                  {(query || typeFilter) ? (
                    <button
                      type="button"
                      onClick={() => {
                        setQuery("");
                        setTypeFilter("");
                      }}
                      className="text-xs text-muted-foreground hover:text-foreground underline"
                    >
                      Filtreleri temizle
                    </button>
                  ) : null}
                </div>
              ) : (
                curriculumBlocks.map((cb) => (
                  <div key={cb.curriculum} className="bg-muted/20">
                    <p className="px-3 py-1.5 text-[10px] uppercase tracking-wider font-medium text-muted-foreground bg-muted/40">
                      {cb.curriculumLabel}
                    </p>
                    {cb.groups.map((g) => (
                      <div key={g.subjectId} className="bg-background">
                        <p className="px-3 py-1.5 text-xs font-medium border-t border-border flex items-center justify-between">
                          <span>{g.subjectName}</span>
                          <span className="text-muted-foreground tabular-nums">
                            {g.books.length}
                          </span>
                        </p>
                        <ul className="divide-y divide-border">
                          {g.books.map((b) => (
                            <li
                              key={b.id}
                              className="px-3 py-2 flex items-center gap-3 text-sm hover:bg-muted/40"
                            >
                              <input
                                type="checkbox"
                                checked={selected.has(b.id)}
                                onChange={() => toggle(b.id)}
                                aria-label={b.name}
                                id={`add-book-${b.id}`}
                              />
                              <label
                                htmlFor={`add-book-${b.id}`}
                                className="flex-1 min-w-0 cursor-pointer"
                              >
                                <span className="font-medium truncate block">
                                  {b.name}
                                </span>
                                <span className="text-xs text-muted-foreground truncate block">
                                  {b.publisher ?? "—"} ·{" "}
                                  {LIBRARY_BOOK_TYPE_LABELS_TR[b.type]}
                                </span>
                              </label>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                ))
              )}
            </div>

            <div className="flex items-center justify-between gap-2 pt-2 border-t border-border">
              <p className="text-xs text-muted-foreground">
                {selected.size > 0
                  ? `${selected.size} kitap seçili`
                  : "Eklemek için bir veya daha fazla kitap seç"}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => handleOpenChange(false)}
                  disabled={isPending}
                >
                  İptal
                </Button>
                <Button
                  type="button"
                  onClick={onSubmit}
                  disabled={isPending || selected.size === 0}
                >
                  {isPending ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                  ) : null}
                  {selected.size > 0
                    ? `${selected.size} kitap ekle`
                    : "Ekle"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DialogChip({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 border text-xs transition-colors",
        active
          ? "border-foreground bg-foreground text-background"
          : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <span>{label}</span>
      {count !== undefined ? (
        <span className={cn("tabular-nums", active ? "opacity-70" : "opacity-60")}>
          {count}
        </span>
      ) : null}
    </button>
  );
}

type GradeFilter = "all" | string;

function AssignedStudentsSection({
  students,
  gradeDistribution,
  setBookCount,
}: {
  students: BookSetAssignedStudent[];
  gradeDistribution: BookSetGradeBucket[];
  setBookCount: number;
}) {
  const [filter, setFilter] = React.useState<GradeFilter>("all");

  const filtered = React.useMemo(() => {
    if (filter === "all") return students;
    if (filter === "graduate") return students.filter((s) => s.is_graduate);
    const grade = Number(filter);
    return students.filter((s) => !s.is_graduate && s.grade_level === grade);
  }, [students, filter]);

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-0.5">
            <h2 className="text-base font-medium inline-flex items-center gap-2">
              <Users className="size-4 text-muted-foreground" aria-hidden />
              Atanmış öğrenciler
            </h2>
            <p className="text-xs text-muted-foreground">
              Setin kitaplarından en az birini almış öğrenciler. Sağdaki sayı,
              öğrencinin bu setten kaç kitabı aldığını gösterir
              (set boyutu: {setBookCount}).
            </p>
          </div>
          {students.length > 0 ? (
            <div className="flex items-center gap-2 text-xs">
              <label htmlFor="grade-filter" className="text-muted-foreground">
                Sınıf:
              </label>
              <select
                id="grade-filter"
                value={filter}
                onChange={(e) => setFilter(e.target.value as GradeFilter)}
                className={cn(
                  "h-8 rounded-md border border-input bg-background px-2 text-xs",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                <option value="all">Tümü ({students.length})</option>
                {gradeDistribution.map((g) => {
                  const value = g.is_graduate
                    ? "graduate"
                    : g.grade_level === null
                      ? "all"
                      : String(g.grade_level);
                  if (value === "all") return null;
                  return (
                    <option key={`${value}`} value={value}>
                      {g.label_tr} ({g.student_count})
                    </option>
                  );
                })}
              </select>
            </div>
          ) : null}
        </div>

        {students.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Bu setin kitaplarından hiçbiri henüz öğrenciye atanmadı.
          </p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Seçili sınıfta öğrenci yok.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {filtered.map((s) => (
              <li
                key={s.student_id}
                className={cn(
                  "py-2 flex items-center gap-3 text-sm",
                  !s.is_active && "opacity-60",
                )}
              >
                <Link
                  href={`/teacher/students/${s.student_id}#books`}
                  className="flex-1 min-w-0 hover:underline"
                >
                  <span className="font-medium truncate block">
                    {s.full_name}
                    {!s.is_active ? (
                      <span className="ml-2 text-[10px] uppercase tracking-wide rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
                        pasif
                      </span>
                    ) : null}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {s.grade_label_tr}
                  </span>
                </Link>
                <span
                  className="text-xs tabular-nums text-muted-foreground shrink-0"
                  title="Bu öğrencinin setten aldığı kitap sayısı"
                >
                  {s.assigned_book_count} / {setBookCount}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
