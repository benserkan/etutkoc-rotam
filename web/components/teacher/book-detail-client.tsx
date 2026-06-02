"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Loader2, Sparkles, Trash2 } from "lucide-react";

import { getLibraryBook, libraryKeys } from "@/lib/api/library";
import {
  useAiSuggestSections,
  useAssignBookToStudents,
  useApplyTemplate,
  useBulkSectionsFromCatalog,
  useClearSections,
  useCreateSection,
  useDeleteBook,
  useDeleteSection,
  usePatchSection,
  useSaveAsTemplate,
} from "@/lib/hooks/use-library-mutations";
import type {
  BookTemplateListItem,
  LibraryBookDetailResponse,
  LibrarySectionItem,
  TopicRef,
} from "@/lib/types/library";
import { LIBRARY_BOOK_TYPE_LABELS_TR } from "@/lib/types/library";
import type { TeacherStudentListItem } from "@/lib/types/teacher";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type Tab = "sections" | "students" | "ai" | "templates";

const TABS: Array<{ key: Tab; label: string }> = [
  { key: "sections", label: "Bölümler" },
  { key: "students", label: "Öğrenciler" },
  { key: "ai", label: "AI önerisi" },
  { key: "templates", label: "Şablon" },
];

interface Props {
  initialBook: LibraryBookDetailResponse;
  topics: TopicRef[];
  templates: BookTemplateListItem[];
  students: TeacherStudentListItem[];
}

export function BookDetailClient({
  initialBook,
  topics,
  templates,
  students,
}: Props) {
  const router = useRouter();
  const [active, setActive] = React.useState<Tab>("sections");

  const bookQ = useQuery<LibraryBookDetailResponse>({
    queryKey: libraryKeys.book(initialBook.id),
    queryFn: () => getLibraryBook(initialBook.id),
    initialData: initialBook,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const book = bookQ.data ?? initialBook;

  const deleteBookMut = useDeleteBook(book.id);
  function onDeleteBook() {
    if (
      !window.confirm(
        `"${book.name}" kitabını silmek istiyor musunuz? Atanmış öğrencilerin ilerlemesi VARSA silinemez.`,
      )
    ) {
      return;
    }
    deleteBookMut.mutate(undefined, {
      onSuccess: () => router.push("/teacher/library"),
    });
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            <Link href="/teacher/library" className="hover:underline">
              Kitaplar
            </Link>
            {" · "}
            {book.subject_name ?? "—"} ·{" "}
            {LIBRARY_BOOK_TYPE_LABELS_TR[book.type]}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight font-display truncate">
            {book.name}
          </h1>
          <p className="text-sm text-muted-foreground">
            {book.sections.length} bölüm · {book.total_tests} test ·{" "}
            {book.assigned_students.length} öğrenciye atanmış
            {book.publisher ? ` · ${book.publisher}` : ""}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onDeleteBook}
          disabled={deleteBookMut.isPending}
        >
          {deleteBookMut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <Trash2 className="size-4" aria-hidden />
          )}
          Kitabı sil
        </Button>
      </header>

      {/* Atanmamış öğrenci uyarısı — kitap hiçbir öğrenciye atanmadıysa program
          yaparken GÖRÜNMEZ. Tüm sekmelerde belirgin durur (AI sekmesinde de
          "önce ata" hatırlatması). Atama yapılınca kaybolur. */}
      {book.assigned_students.length === 0 ? (
        <div className="flex items-start gap-3 rounded-lg border-l-4 border-l-amber-500 border border-amber-300 bg-amber-50 dark:bg-amber-950/30 px-4 py-3">
          <AlertTriangle className="size-5 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">
              Bu kitap henüz hiçbir öğrenciye atanmadı
            </p>
            <p className="text-xs text-amber-800 dark:text-amber-300/90 mt-0.5">
              Atamadan kitap, program yaparken öğrencinin listesinde
              <strong> görünmez</strong>. Öğrenci seçip <strong>Kaydet</strong> butonuna basın.
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => setActive("students")}
            className="shrink-0 bg-amber-600 text-white hover:bg-amber-700"
          >
            Öğrenci ata
          </Button>
        </div>
      ) : null}

      <div
        role="tablist"
        aria-label="Kitap sekmeleri"
        className="flex items-center gap-1 border-b border-border"
      >
        {TABS.map((t) => {
          const isActive = active === t.key;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActive(t.key)}
              className={cn(
                "px-3 py-2 -mb-px text-sm border-b-2 transition-colors",
                isActive
                  ? "border-foreground font-medium"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {active === "sections" ? (
        <SectionsTab book={book} topics={topics} />
      ) : null}
      {active === "students" ? (
        <AssignmentsTab book={book} students={students} />
      ) : null}
      {active === "ai" ? <AiSuggestTab book={book} /> : null}
      {active === "templates" ? (
        <TemplatesTab book={book} templates={templates} />
      ) : null}
    </div>
  );
}

// =============================================================================
// Sections tab
// =============================================================================

function SectionsTab({
  book,
  topics,
}: {
  book: LibraryBookDetailResponse;
  topics: TopicRef[];
}) {
  const [addOpen, setAddOpen] = React.useState(false);
  const [bulkOpen, setBulkOpen] = React.useState(false);
  const clearMut = useClearSections(book.id);

  function onClearAll() {
    if (
      !window.confirm(
        "Tüm bölümleri silmek istiyor musunuz? Rezerv/tamam test varsa engellenir.",
      )
    ) {
      return;
    }
    clearMut.mutate();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => setAddOpen(true)}>
          + Bölüm ekle
        </Button>
        {topics.length > 0 ? (
          <Button size="sm" variant="outline" onClick={() => setBulkOpen(true)}>
            Katalog konularından ekle
          </Button>
        ) : null}
        {book.sections.length > 0 ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={onClearAll}
            disabled={clearMut.isPending}
          >
            {clearMut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            Tümünü sil
          </Button>
        ) : null}
      </div>

      {book.sections.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Henüz bölüm yok. Manuel ekleyebilir, katalog konularından çekebilir
            veya AI önerisi alabilirsiniz.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {book.sections.map((s) => (
                <SectionRow key={s.id} section={s} bookId={book.id} />
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Yeni bölüm</DialogTitle>
          </DialogHeader>
          <AddSectionForm
            bookId={book.id}
            topics={topics}
            onDone={() => setAddOpen(false)}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Katalog konularından toplu ekle</DialogTitle>
          </DialogHeader>
          <BulkCatalogForm
            bookId={book.id}
            topics={topics}
            existingTopicIds={new Set(
              book.sections
                .map((s) => s.topic_id)
                .filter((t): t is number => t !== null),
            )}
            defaultTestCount={book.avg_questions_per_test ?? 5}
            onDone={() => setBulkOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SectionRow({
  section,
  bookId,
}: {
  section: LibrarySectionItem;
  bookId: number;
}) {
  const [editing, setEditing] = React.useState(false);
  const [label, setLabel] = React.useState(section.label);
  const [testCount, setTestCount] = React.useState(section.test_count);
  const patchMut = usePatchSection(bookId);
  const deleteMut = useDeleteSection(bookId);

  // Section prop değişince form değerini de güncelle
  if (!editing && (label !== section.label || testCount !== section.test_count)) {
    setLabel(section.label);
    setTestCount(section.test_count);
  }

  function save() {
    patchMut.mutate(
      {
        sectionId: section.id,
        body: {
          label: label.trim() !== section.label ? label.trim() : undefined,
          test_count: testCount !== section.test_count ? testCount : undefined,
        },
      },
      { onSettled: () => setEditing(false) },
    );
  }

  function onDelete() {
    if (
      !window.confirm(
        `"${section.label}" bölümünü silmek istiyor musunuz? Rezerv/tamam test varsa engellenir.`,
      )
    ) {
      return;
    }
    deleteMut.mutate({ sectionId: section.id });
  }

  return (
    <li className="p-3 flex items-center gap-3 text-sm">
      {editing ? (
        <>
          <Input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="flex-1"
          />
          <Input
            type="number"
            min={1}
            value={testCount}
            onChange={(e) =>
              setTestCount(Math.max(1, Number(e.target.value) || 1))
            }
            className="w-20"
          />
          <Button size="sm" onClick={save} disabled={patchMut.isPending}>
            Kaydet
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setLabel(section.label);
              setTestCount(section.test_count);
              setEditing(false);
            }}
            disabled={patchMut.isPending}
          >
            İptal
          </Button>
        </>
      ) : (
        <>
          <span className="flex-1 min-w-0">
            <span className="font-medium truncate block">{section.label}</span>
            {section.topic_name ? (
              <span className="text-xs text-muted-foreground">
                Konu: {section.topic_name}
              </span>
            ) : null}
          </span>
          <span className="tabular-nums text-muted-foreground text-xs">
            {section.test_count} test · rezerv {section.reserved_total} · tamam{" "}
            {section.completed_total}
          </span>
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
            Düzenle
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={onDelete}
            disabled={deleteMut.isPending || section.has_progress}
            title={
              section.has_progress
                ? "Bölümde rezerv/tamam var — silinemez"
                : undefined
            }
            className={section.has_progress ? "opacity-50" : ""}
          >
            {deleteMut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="size-4" aria-hidden />
            )}
          </Button>
        </>
      )}
    </li>
  );
}

function AddSectionForm({
  bookId,
  topics,
  onDone,
}: {
  bookId: number;
  topics: TopicRef[];
  onDone: () => void;
}) {
  const mut = useCreateSection(bookId);
  const [label, setLabel] = React.useState("");
  const [testCount, setTestCount] = React.useState(10);
  const [topicId, setTopicId] = React.useState<number | "">("");
  const [error, setError] = React.useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!label.trim()) {
      setError("Bölüm adı zorunlu.");
      return;
    }
    if (testCount < 1) {
      setError("Test sayısı en az 1 olmalı.");
      return;
    }
    mut.mutate(
      {
        body: {
          label: label.trim(),
          test_count: testCount,
          topic_id: topicId ? Number(topicId) : null,
        },
      },
      { onSuccess: () => onDone() },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor="as-label">Bölüm adı</Label>
        <Input
          id="as-label"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          autoFocus
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="as-count">Test sayısı</Label>
          <Input
            id="as-count"
            type="number"
            min={1}
            value={testCount}
            onChange={(e) => setTestCount(Math.max(1, Number(e.target.value) || 1))}
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="as-topic">Konu (opsiyonel)</Label>
          <select
            id="as-topic"
            value={topicId === "" ? "" : String(topicId)}
            onChange={(e) =>
              setTopicId(e.target.value ? Number(e.target.value) : "")
            }
            className={cn(
              "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
            )}
          >
            <option value="">— Yok —</option>
            {topics.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button type="button" variant="ghost" onClick={onDone} disabled={mut.isPending}>
          İptal
        </Button>
        <Button type="submit" disabled={mut.isPending}>
          {mut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          Ekle
        </Button>
      </div>
    </form>
  );
}

function BulkCatalogForm({
  bookId,
  topics,
  existingTopicIds,
  defaultTestCount,
  onDone,
}: {
  bookId: number;
  topics: TopicRef[];
  existingTopicIds: Set<number>;
  defaultTestCount: number;
  onDone: () => void;
}) {
  const mut = useBulkSectionsFromCatalog(bookId);
  const [selected, setSelected] = React.useState<Map<number, number>>(new Map());

  function toggle(topicId: number) {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(topicId)) next.delete(topicId);
      else next.set(topicId, defaultTestCount);
      return next;
    });
  }

  function setCount(topicId: number, count: number) {
    setSelected((prev) => {
      const next = new Map(prev);
      next.set(topicId, Math.max(1, count));
      return next;
    });
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) return;
    const items = Array.from(selected.entries()).map(([topic_id, test_count]) => ({
      topic_id,
      test_count,
    }));
    mut.mutate({ body: { items } }, { onSuccess: () => onDone() });
  }

  const available = topics.filter((t) => !existingTopicIds.has(t.id));

  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Bu kitaba henüz eklenmemiş konular gösterilir. Test sayısı default {defaultTestCount}.
      </p>
      {available.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Tüm konular zaten ekli.
        </p>
      ) : (
        <ul className="max-h-[50vh] overflow-y-auto divide-y divide-border border border-border rounded-md">
          {available.map((t) => {
            const checked = selected.has(t.id);
            const count = selected.get(t.id) ?? defaultTestCount;
            return (
              <li
                key={t.id}
                className="px-3 py-2 flex items-center gap-3 text-sm"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(t.id)}
                  aria-label={t.name}
                />
                <span className="flex-1 truncate">{t.name}</span>
                <Input
                  type="number"
                  min={1}
                  value={count}
                  disabled={!checked}
                  onChange={(e) => setCount(t.id, Number(e.target.value) || 1)}
                  className="w-20 h-8 text-xs"
                />
              </li>
            );
          })}
        </ul>
      )}
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button type="button" variant="ghost" onClick={onDone} disabled={mut.isPending}>
          İptal
        </Button>
        <Button
          type="submit"
          disabled={mut.isPending || selected.size === 0}
        >
          {mut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          {selected.size} konuyu ekle
        </Button>
      </div>
    </form>
  );
}

// =============================================================================
// Assignments tab
// =============================================================================

function AssignmentsTab({
  book,
  students,
}: {
  book: LibraryBookDetailResponse;
  students: TeacherStudentListItem[];
}) {
  const assignedSet = new Set(book.assigned_students.map((s) => s.student_id));
  const lockedSet = new Set(
    book.assigned_students.filter((s) => s.has_progress).map((s) => s.student_id),
  );
  const [selected, setSelected] = React.useState<Set<number>>(assignedSet);
  const mut = useAssignBookToStudents(book.id);

  // book değişince selected'ı yeniden senkronla
  const [lastSyncedAssigned, setLastSyncedAssigned] = React.useState<string>(
    JSON.stringify([...assignedSet].sort()),
  );
  const currentKey = JSON.stringify([...assignedSet].sort());
  if (currentKey !== lastSyncedAssigned) {
    setLastSyncedAssigned(currentKey);
    setSelected(assignedSet);
  }

  function toggle(sid: number) {
    if (lockedSet.has(sid)) return; // rezerv var, dokunma
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid);
      else next.add(sid);
      return next;
    });
  }

  function save() {
    mut.mutate({ body: { student_ids: Array.from(selected) } });
  }

  const hasChange =
    selected.size !== assignedSet.size ||
    [...selected].some((s) => !assignedSet.has(s));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Kutuyu işaretle/kaldır. Rezerv/tamam test olan öğrenciler kilitli
          (silinemez).
        </p>
        <div className="flex items-center gap-2 shrink-0">
          {hasChange ? (
            <span className="text-xs font-medium text-amber-700 dark:text-amber-300 whitespace-nowrap">
              Kaydedilmedi — başka sekmeye geçmeden kaydedin
            </span>
          ) : null}
          <Button
            onClick={save}
            disabled={!hasChange || mut.isPending}
            className={cn(hasChange ? "bg-amber-600 text-white hover:bg-amber-700" : "")}
          >
            {mut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            Kaydet
          </Button>
        </div>
      </div>
      <Card>
        <CardContent className="p-0">
          {students.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">Öğrenci yok.</p>
          ) : (
            <ul className="divide-y divide-border max-h-[60vh] overflow-y-auto">
              {students.map((s) => {
                const checked = selected.has(s.id);
                const locked = lockedSet.has(s.id);
                return (
                  <li
                    key={s.id}
                    className="px-4 py-2 flex items-center gap-3 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={locked}
                      onChange={() => toggle(s.id)}
                      aria-label={s.full_name}
                    />
                    <span className="flex-1 min-w-0">
                      <span className="font-medium truncate block">
                        {s.full_name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {s.email}
                        {locked ? " · kilitli (rezerv var)" : ""}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// =============================================================================
// AI suggest tab
// =============================================================================

function AiSuggestTab({ book }: { book: LibraryBookDetailResponse }) {
  const mut = useAiSuggestSections(book.id);
  const [gradeHint, setGradeHint] = React.useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate({
      body: { grade_hint: gradeHint.trim() || null },
    });
  }

  if (book.sections.length > 0) {
    return (
      <Card>
        <CardContent className="p-6 space-y-2 text-sm">
          <p className="font-medium">Bu kitapta zaten {book.sections.length} bölüm var.</p>
          <p className="text-muted-foreground">
            AI önerisi alabilmek için önce mevcut bölümleri silmelisiniz.
            (&quot;Bölümler&quot; sekmesinden &quot;Tümünü sil&quot;.)
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-6 space-y-4">
        <div className="space-y-2">
          <p className="font-medium flex items-center gap-2">
            <Sparkles className="size-4" aria-hidden /> AI ünite önerisi
          </p>
          <p className="text-sm text-muted-foreground">
            Anthropic Claude bu kitabın muhtemel bölümlerini önerir; sonuçlar
            kitaba eklenir ve aynı zamanda doğrulanmamış bir şablon olarak
            kaydedilir. AI çağrısı 30 saniyeye kadar sürebilir.
          </p>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="ai-grade">Sınıf ipucu (opsiyonel)</Label>
            <Input
              id="ai-grade"
              value={gradeHint}
              onChange={(e) => setGradeHint(e.target.value)}
              placeholder="örn. 8. sınıf"
            />
            <p className="text-xs text-muted-foreground">
              Boş bırakırsanız kitabın hedef sınıfından türetilir.
            </p>
          </div>
          <Button type="submit" disabled={mut.isPending}>
            {mut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Sparkles className="size-4" aria-hidden />
            )}
            {mut.isPending ? "AI yanıt veriyor (≤30s)…" : "AI önerisi al"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Templates tab
// =============================================================================

function TemplatesTab({
  book,
  templates,
}: {
  book: LibraryBookDetailResponse;
  templates: BookTemplateListItem[];
}) {
  const [templateName, setTemplateName] = React.useState("");
  const [applyId, setApplyId] = React.useState<number | "">("");
  const [overwrite, setOverwrite] = React.useState(false);
  const saveMut = useSaveAsTemplate(book.id);
  const applyMut = useApplyTemplate(book.id);

  function save(e: React.FormEvent) {
    e.preventDefault();
    saveMut.mutate(
      { body: { template_name: templateName.trim() || null } },
      { onSuccess: () => setTemplateName("") },
    );
  }

  function apply(e: React.FormEvent) {
    e.preventDefault();
    if (!applyId) return;
    if (
      overwrite &&
      !window.confirm(
        "Mevcut bölümler silinecek (rezerv/tamam test yoksa). Devam?",
      )
    ) {
      return;
    }
    applyMut.mutate(
      { body: { template_id: Number(applyId), overwrite } },
      {
        onSuccess: () => {
          setApplyId("");
          setOverwrite(false);
        },
      },
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Şablon olarak kaydet</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={save} className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="sav-name">Şablon adı (opsiyonel)</Label>
              <Input
                id="sav-name"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder={book.name}
              />
            </div>
            <Button
              type="submit"
              disabled={saveMut.isPending || book.sections.length === 0}
            >
              {saveMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              Kaydet
            </Button>
            {book.sections.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Kaydetmek için en az bir bölüm olmalı.
              </p>
            ) : null}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Şablonu uygula</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={apply} className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="ap-template">Şablon</Label>
              <select
                id="ap-template"
                value={applyId === "" ? "" : String(applyId)}
                onChange={(e) =>
                  setApplyId(e.target.value ? Number(e.target.value) : "")
                }
                className={cn(
                  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                )}
                required
              >
                <option value="">— Seç —</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.section_count} bölüm)
                    {t.is_ai_generated && !t.is_verified ? " · AI taslak" : ""}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={overwrite}
                onChange={(e) => setOverwrite(e.target.checked)}
              />
              Üzerine yaz (mevcut bölümleri sil — rezerv yoksa)
            </label>
            <Button
              type="submit"
              disabled={applyMut.isPending || !applyId}
            >
              {applyMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              Uygula
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
