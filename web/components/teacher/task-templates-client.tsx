"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus, Trash2, LayoutTemplate } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getTaskTemplates, teacherKeys } from "@/lib/api/teacher";
import { getLibraryBook } from "@/lib/api/library";
import {
  useCreateTaskTemplate,
  useDeleteTaskTemplate,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  TaskTemplateListResponse,
  TaskTemplateItemBody,
} from "@/lib/types/teacher";
import type { LibraryBookListItem, LibraryBookDetailResponse } from "@/lib/types/library";

const FIELD =
  "h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

const TYPE_OPTS: { value: string; label: string }[] = [
  { value: "test", label: "Test" },
  { value: "video", label: "Video" },
  { value: "ozet", label: "Özet" },
  { value: "tekrar", label: "Tekrar" },
  { value: "other", label: "Diğer" },
];

interface Props {
  initialTemplates: TaskTemplateListResponse;
  books: LibraryBookListItem[];
}

export function TaskTemplatesClient({ initialTemplates, books }: Props) {
  const q = useQuery<TaskTemplateListResponse>({
    queryKey: teacherKeys.taskTemplates(),
    queryFn: getTaskTemplates,
    initialData: initialTemplates,
  });
  const del = useDeleteTaskTemplate();
  const templates = q.data?.items ?? [];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-display text-2xl font-bold inline-flex items-center gap-2">
          <LayoutTemplate className="size-5 text-indigo-500" aria-hidden />
          Görev şablonları
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Sık kullandığın görev kalıpları (kitap + bölüm + test sayısı). Haftalık/günlük
          plana eklerken <strong>&quot;Şablondan&quot;</strong> ile tek tıkla aynı görevi
          uygula. (Kitabın bölüm yapısını kopyalayan <em>Kitap şablonları</em>&apos;ndan
          farklıdır.)
        </p>
      </div>

      <CreateForm books={books} />

      <div className="grid gap-3 sm:grid-cols-2">
        {templates.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Henüz görev şablonu yok. Üstteki formdan oluştur ya da plandaki bir görevin
            menüsünden &quot;Şablon olarak kaydet&quot; de.
          </p>
        ) : (
          templates.map((t) => (
            <Card key={t.id} className="overflow-hidden">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold truncate">{t.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {t.item_count} kalem · toplam {t.total_planned} test
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm(`"${t.name}" şablonunu sil?`)) del.mutate({ id: t.id });
                    }}
                    disabled={del.isPending}
                    className="shrink-0 rounded-md border border-border p-1.5 text-muted-foreground hover:bg-rose-50 hover:text-rose-600"
                    aria-label="Sil"
                  >
                    <Trash2 className="size-4" aria-hidden />
                  </button>
                </div>
                <ul className="mt-2 space-y-1">
                  {t.items.map((it) => (
                    <li key={it.section_id} className="text-xs text-muted-foreground">
                      • {it.book_name} — {it.section_label}:{" "}
                      <span className="font-medium text-foreground">{it.planned_count}</span> test
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}

function CreateForm({ books }: { books: LibraryBookListItem[] }) {
  const create = useCreateTaskTemplate();
  const [name, setName] = React.useState("");
  const [type, setType] = React.useState("test");
  const [bookId, setBookId] = React.useState<number | "">("");
  const [sectionId, setSectionId] = React.useState<number | "">("");
  const [count, setCount] = React.useState(10);
  const [items, setItems] = React.useState<
    (TaskTemplateItemBody & { _label: string })[]
  >([]);

  const bookDetail = useQuery<LibraryBookDetailResponse>({
    queryKey: ["teacher", "me", "library", "book", String(bookId)],
    queryFn: () => getLibraryBook(Number(bookId)),
    enabled: bookId !== "",
  });
  const sections = bookDetail.data?.sections ?? [];

  function addItem() {
    if (bookId === "" || sectionId === "" || count < 1) return;
    const book = books.find((b) => b.id === bookId);
    const sec = sections.find((s) => s.id === sectionId);
    if (!book || !sec) return;
    setItems((prev) => [
      ...prev,
      {
        book_id: Number(bookId),
        section_id: Number(sectionId),
        planned_count: count,
        _label: `${book.name} — ${sec.label}: ${count} test`,
      },
    ]);
    setSectionId("");
    setCount(10);
  }

  function submit() {
    if (!name.trim() || items.length === 0) return;
    create.mutate(
      {
        body: {
          name: name.trim(),
          type,
          items: items.map(({ book_id, section_id, planned_count }) => ({
            book_id,
            section_id,
            planned_count,
          })),
        },
      },
      {
        onSuccess: () => {
          setName("");
          setType("test");
          setItems([]);
          setBookId("");
          setSectionId("");
          setCount(10);
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Yeni görev şablonu</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium">Ad</label>
            <input
              className={FIELD}
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={160}
              placeholder="Örn. Günlük 20 matematik"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium">Tip</label>
            <select className={FIELD} value={type} onChange={(e) => setType(e.target.value)}>
              {TYPE_OPTS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Kalem ekleme */}
        <div className="rounded-lg border border-dashed border-border p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Kalem ekle
          </p>
          <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto_auto]">
            <select
              className={FIELD}
              value={bookId}
              onChange={(e) => {
                setBookId(e.target.value ? Number(e.target.value) : "");
                setSectionId("");
              }}
            >
              <option value="">Kitap seç…</option>
              {books.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <select
              className={FIELD}
              value={sectionId}
              onChange={(e) => setSectionId(e.target.value ? Number(e.target.value) : "")}
              disabled={bookId === "" || bookDetail.isLoading}
            >
              <option value="">
                {bookDetail.isLoading ? "Yükleniyor…" : "Bölüm seç…"}
              </option>
              {sections.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              className={cn(FIELD, "w-24")}
              value={count}
              onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))}
            />
            <Button
              type="button"
              variant="outline"
              onClick={addItem}
              disabled={bookId === "" || sectionId === ""}
            >
              <Plus className="size-4" aria-hidden />
              Ekle
            </Button>
          </div>
          {items.length > 0 ? (
            <ul className="mt-2 space-y-1">
              {items.map((it, i) => (
                <li key={`${it.section_id}-${i}`} className="flex items-center justify-between gap-2 text-xs">
                  <span>• {it._label}</span>
                  <button
                    type="button"
                    onClick={() => setItems((prev) => prev.filter((_, j) => j !== i))}
                    className="text-muted-foreground hover:text-rose-600"
                    aria-label="Kalemi çıkar"
                  >
                    <Trash2 className="size-3.5" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="flex justify-end">
          <Button onClick={submit} disabled={create.isPending || !name.trim() || items.length === 0}>
            {create.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Plus className="size-4" aria-hidden />
            )}
            Şablon oluştur
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
