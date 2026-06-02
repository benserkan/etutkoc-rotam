"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus, LayoutTemplate, Loader2, MoreHorizontal, Plus, Trash2 } from "lucide-react";

import {
  getTaskTemplates,
  getTeacherStudentBooks,
  getTeacherStudentDay,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  useApplyTaskTemplate,
  useCreateTask,
  useDeleteTask,
  usePatchTask,
  usePatchTaskItem,
  useTaskTemplateFromTask,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  StudentBookListResponse,
  TaskTemplateListResponse,
  TeacherStudentDayResponse,
  TeacherTask,
  TeacherTaskItem,
} from "@/lib/types/teacher";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { TaskForm } from "@/components/teacher/task-form";

interface Props {
  studentId: number;
  initial: TeacherStudentDayResponse;
  initialDate: string;
}

/**
 * Günlük plan etkileşim katmanı — görev ekle, sil, kalem güncelle.
 *
 * Optimistic update + rollback gün cache'i (`teacher:me:students:{id}:day:{date}`)
 * üzerinde. Capacity 422 → toast `RESERVE_OVER_CAPACITY`.
 *
 * "Görev ekle" modal'ı için öğrenciye atanmış kitaplar gerekli; ayrı `useQuery`
 * ile çekilir ve TaskForm'a geçilir.
 */
export function DayBoard({ studentId, initial, initialDate }: Props) {
  const dateIso = initial.date;
  const day = useQuery<TeacherStudentDayResponse>({
    queryKey: teacherKeys.studentDay(studentId, dateIso),
    queryFn: () => getTeacherStudentDay(studentId, dateIso),
    initialData: initialDate === dateIso ? initial : undefined,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = day.data ?? initial;
  const pct = Math.round((data.today_pct ?? 0) * 100);

  const [createOpen, setCreateOpen] = React.useState(false);
  const studentBooksQ = useQuery<StudentBookListResponse>({
    queryKey: teacherKeys.studentBooks(studentId),
    queryFn: () => getTeacherStudentBooks(studentId),
    enabled: createOpen,
    staleTime: 60_000,
  });

  const createMut = useCreateTask(studentId);
  const [tplOpen, setTplOpen] = React.useState(false);
  const applyTplMut = useApplyTaskTemplate(studentId);
  const templatesQ = useQuery<TaskTemplateListResponse>({
    queryKey: teacherKeys.taskTemplates(),
    queryFn: getTaskTemplates,
    enabled: tplOpen,
    staleTime: 60_000,
  });

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            <Link href="/teacher/students" className="hover:underline">
              Öğrenciler
            </Link>
            {" · "}
            <Link
              href={`/teacher/students/${studentId}`}
              className="hover:underline"
            >
              #{studentId}
            </Link>
          </p>
          <h1 className="text-2xl font-semibold tracking-tight font-display">
            Günlük plan · {data.date}
          </h1>
          <p className="text-sm text-muted-foreground">
            {data.gorev ? (
              <>
                <strong className="text-foreground tabular-nums">
                  {data.gorev.gorev_done}/{data.gorev.gorev_total}
                </strong>{" "}
                görev · %{data.gorev.gorev_pct}
                {" · "}
                {data.gorev.test_completed}/{data.gorev.test_planned} test
                {data.gorev.deneme_count > 0
                  ? ` · ${data.gorev.deneme_done}/${data.gorev.deneme_count} deneme`
                  : ""}
              </>
            ) : (
              <>
                {data.today_completed}/{data.today_planned} tamam · %{pct}
              </>
            )}
            {data.is_today
              ? " · Bugün"
              : data.is_future
                ? " · Gelecek"
                : " · Geçmiş"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <nav className="flex items-center gap-2 text-sm">
            <Link
              href={`/teacher/students/${studentId}/day?date=${data.prev_date}`}
              className="rounded-md border border-border px-3 py-1.5 hover:bg-muted"
            >
              ← {data.prev_date}
            </Link>
            <Link
              href={`/teacher/students/${studentId}/day?date=${data.next_date}`}
              className="rounded-md border border-border px-3 py-1.5 hover:bg-muted"
            >
              {data.next_date} →
            </Link>
          </nav>
          <Button variant="outline" onClick={() => setTplOpen(true)}>
            <LayoutTemplate className="size-4" aria-hidden />
            Şablondan
          </Button>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" aria-hidden />
            Görev ekle
          </Button>
        </div>
      </header>

      {data.tasks.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Bu güne henüz görev yok.
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-2.5">
          {data.tasks.map((t) => (
            <li key={t.id}>
              <TaskCardEditable
                task={t}
                studentId={studentId}
                dateIso={dateIso}
              />
            </li>
          ))}
        </ul>
      )}

      <Dialog
        open={createOpen}
        onOpenChange={(o) => {
          if (!createMut.isPending) setCreateOpen(o);
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Yeni görev · {dateIso}</DialogTitle>
          </DialogHeader>
          <TaskForm
            studentId={studentId}
            studentBooks={studentBooksQ.data}
            defaultDate={dateIso}
            isPending={createMut.isPending}
            onCancel={() => setCreateOpen(false)}
            onSubmit={(body) => {
              createMut.mutate(
                { body },
                {
                  onSuccess: () => setCreateOpen(false),
                },
              );
            }}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={tplOpen} onOpenChange={(o) => { if (!applyTplMut.isPending) setTplOpen(o); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Şablondan görev ekle · {dateIso}</DialogTitle>
          </DialogHeader>
          {templatesQ.isLoading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              <Loader2 className="mx-auto size-5 animate-spin" aria-hidden />
            </p>
          ) : (templatesQ.data?.items.length ?? 0) === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Henüz görev şablonun yok.{" "}
              <Link href="/teacher/library/task-templates" className="underline">
                Şablon oluştur →
              </Link>
            </p>
          ) : (
            <ul className="max-h-[420px] space-y-2 overflow-y-auto">
              {templatesQ.data!.items.map((t) => (
                <li
                  key={t.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border p-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-semibold truncate">{t.name}</p>
                    <p className="text-xs text-muted-foreground truncate">
                      {t.item_count} kalem · {t.total_planned} test ·{" "}
                      {t.items.map((i) => `${i.book_name} (${i.planned_count})`).join(", ")}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    disabled={applyTplMut.isPending}
                    onClick={() =>
                      applyTplMut.mutate(
                        { body: { template_id: t.id, date: dateIso } },
                        { onSuccess: () => setTplOpen(false) },
                      )
                    }
                  >
                    {applyTplMut.isPending ? (
                      <Loader2 className="size-4 animate-spin" aria-hidden />
                    ) : (
                      <Plus className="size-4" aria-hidden />
                    )}
                    Uygula
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Görev durumu (deneme/etkinlik dahil): done = COMPLETED veya hacim tamamlandı;
// partial = ilerleme var ama bitmedi; todo = hiç yapılmadı; cancelled = iptal.
type GorevState = "done" | "partial" | "todo" | "cancelled";
function gorevState(task: TeacherTask): GorevState {
  if (task.status === "cancelled") return "cancelled";
  const done =
    task.status === "completed" ||
    (task.planned_count > 0 && task.completed_count >= task.planned_count);
  if (done) return "done";
  return task.completed_count > 0 ? "partial" : "todo";
}

// Tamamlanmamış (todo) + kısmi (partial) DİKKAT ÇEKİCİ (renkli sol şerit + tonlu
// zemin); tamamlanan SAKİN (de-emphasize). Purge-safe explicit renkler.
const STATE_CARD: Record<GorevState, string> = {
  todo: "border-l-4 border-l-rose-500 bg-rose-50/60 dark:bg-rose-950/25",
  partial: "border-l-4 border-l-amber-500 bg-amber-50/60 dark:bg-amber-950/25",
  done: "border-l-4 border-l-emerald-500/40 opacity-75",
  cancelled: "border-l-4 border-l-slate-300 opacity-55",
};
const STATE_BADGE: Record<GorevState, { text: string; cls: string }> = {
  todo: { text: "Yapılmadı", cls: "bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-200" },
  partial: { text: "Kısmen", cls: "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-200" },
  done: { text: "Tamamlandı", cls: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200" },
  cancelled: { text: "İptal", cls: "bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300" },
};

function TaskCardEditable({
  task,
  studentId,
  dateIso,
}: {
  task: TeacherTask;
  studentId: number;
  dateIso: string;
}) {
  const pct = Math.round((task.pct ?? 0) * 100);
  const gstate = gorevState(task);
  const badge = STATE_BADGE[gstate];
  const [editTitleOpen, setEditTitleOpen] = React.useState(false);

  const deleteMut = useDeleteTask(studentId, dateIso);
  const patchMut = usePatchTask(studentId, dateIso);
  const saveTplMut = useTaskTemplateFromTask();

  function onDelete() {
    if (!window.confirm(`"${task.title}" görevini silmek istiyor musunuz?`)) {
      return;
    }
    deleteMut.mutate({ taskId: task.id });
  }

  function onSaveTemplate() {
    const name = window.prompt(
      "Görev şablonu adı (sık kullandığın bu görevi kaydet):",
      task.title || "Görev şablonu",
    );
    if (name && name.trim()) {
      saveTplMut.mutate({ taskId: task.id, name: name.trim() });
    }
  }

  return (
    <Card className={cn(STATE_CARD[gstate])}>
      <CardContent className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                  badge.cls,
                )}
              >
                {badge.text}
              </span>
              <p
                className={cn(
                  "font-medium truncate",
                  gstate === "done" || gstate === "cancelled" ? "text-muted-foreground" : "",
                  gstate === "cancelled" ? "line-through" : "",
                )}
              >
                {task.title || "—"}
              </p>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {task.scheduled_hour ?? "Saat belirsiz"} · {task.type} ·{" "}
              {task.completed_count}/{task.planned_count} (%{pct})
              {task.is_draft ? " · taslak" : ""}
              {task.has_pending_request ? " · talep var" : ""}
            </p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={onSaveTemplate}
              disabled={saveTplMut.isPending}
              title="Şablon olarak kaydet"
              aria-label="Şablon olarak kaydet"
            >
              {saveTplMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <BookmarkPlus className="size-4" aria-hidden />
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setEditTitleOpen(true)}
              aria-label="Düzenle"
            >
              <MoreHorizontal className="size-4" aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onDelete}
              disabled={deleteMut.isPending}
              aria-label="Sil"
            >
              {deleteMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Trash2 className="size-4" aria-hidden />
              )}
            </Button>
          </div>
        </div>
        {task.items.length > 0 ? (
          <ul className="divide-y divide-border border-t border-border -mx-4">
            {task.items.map((it) => (
              <ItemEditableRow
                key={it.id}
                item={it}
                taskId={task.id}
                studentId={studentId}
                dateIso={dateIso}
              />
            ))}
          </ul>
        ) : null}
      </CardContent>

      <Dialog open={editTitleOpen} onOpenChange={setEditTitleOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Görevi düzenle</DialogTitle>
          </DialogHeader>
          <EditTitleForm
            task={task}
            isPending={patchMut.isPending}
            onCancel={() => setEditTitleOpen(false)}
            onSubmit={(body) => {
              patchMut.mutate(
                { taskId: task.id, body },
                { onSuccess: () => setEditTitleOpen(false) },
              );
            }}
          />
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function EditTitleForm({
  task,
  isPending,
  onSubmit,
  onCancel,
}: {
  task: TeacherTask;
  isPending: boolean;
  onSubmit: (body: { title?: string; scheduled_hour?: number | null; is_draft?: boolean; notes?: string | null }) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = React.useState(task.title);
  const [hour, setHour] = React.useState<string>(
    task.scheduled_hour ? task.scheduled_hour.slice(0, 2) : "",
  );
  const [isDraft, setIsDraft] = React.useState(task.is_draft);
  const [notes, setNotes] = React.useState(task.notes ?? "");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    let hourNum: number | null | undefined = undefined;
    if (hour.trim() === "") {
      hourNum = null;
    } else {
      const h = Number(hour);
      if (!Number.isFinite(h) || h < 0 || h > 23) {
        return;
      }
      hourNum = h;
    }
    onSubmit({
      title: title.trim() !== task.title ? title.trim() : undefined,
      scheduled_hour: hourNum,
      is_draft: isDraft !== task.is_draft ? isDraft : undefined,
      notes: notes.trim() !== (task.notes ?? "") ? (notes.trim() || null) : undefined,
    });
  }
  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="space-y-1">
        <label htmlFor="ed-title" className="text-sm font-medium">
          Başlık
        </label>
        <Input
          id="ed-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
      </div>
      <div className="space-y-1">
        <label htmlFor="ed-hour" className="text-sm font-medium">
          Saat (0-23, boş bırak = saat yok)
        </label>
        <Input
          id="ed-hour"
          type="number"
          min={0}
          max={23}
          value={hour}
          onChange={(e) => setHour(e.target.value)}
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={isDraft}
          onChange={(e) => setIsDraft(e.target.checked)}
        />
        Taslak
      </label>
      <div className="space-y-1">
        <label htmlFor="ed-notes" className="text-sm font-medium">
          Not
        </label>
        <textarea
          id="ed-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={isPending}>
          İptal
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          Kaydet
        </Button>
      </div>
    </form>
  );
}

function ItemEditableRow({
  item,
  taskId,
  studentId,
  dateIso,
}: {
  item: TeacherTaskItem;
  taskId: number;
  studentId: number;
  dateIso: string;
}) {
  const patchItem = usePatchTaskItem(studentId, dateIso);
  const qc = useQueryClient();

  const [editing, setEditing] = React.useState(false);
  const [value, setValue] = React.useState(item.planned_count);

  // item.planned_count değişince form değerini de güncelle (server'dan
  // gelen invalidate sonrası).
  if (!editing && value !== item.planned_count) {
    setValue(item.planned_count);
  }

  function save() {
    if (value === item.planned_count) {
      setEditing(false);
      return;
    }
    if (value < item.completed_count) {
      // Backend bunu 422'yle reddedecek; ön-engelle
      return;
    }
    patchItem.mutate(
      { taskId, itemId: item.id, body: { planned_count: value } },
      {
        onSettled: () => {
          setEditing(false);
          // Cache zaten invalidate ile tazelenir; ekstra adım yok.
          void qc;
        },
      },
    );
  }

  return (
    <li className="px-4 py-2 text-xs flex items-center gap-3">
      <span className="flex-1 min-w-0 truncate">
        {item.book_name}
        {item.section_label ? ` · ${item.section_label}` : ""}
        {item.topic_name ? ` · ${item.topic_name}` : ""}
      </span>
      {editing ? (
        <>
          <Input
            type="number"
            min={Math.max(1, item.completed_count)}
            value={value}
            onChange={(e) => setValue(Math.max(1, Number(e.target.value) || 1))}
            className="h-7 w-16 text-xs"
          />
          <Button
            type="button"
            size="sm"
            onClick={save}
            disabled={patchItem.isPending}
          >
            Kaydet
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setValue(item.planned_count);
              setEditing(false);
            }}
            disabled={patchItem.isPending}
          >
            İptal
          </Button>
        </>
      ) : (
        <>
          <span className="tabular-nums text-muted-foreground">
            {item.completed_count}/{item.planned_count}
          </span>
          <span className="text-muted-foreground tabular-nums">
            ünite kalan {item.section_remaining}
          </span>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setEditing(true)}
            disabled={item.completed_count >= item.planned_count && item.completed_count > 0}
          >
            Düzenle
          </Button>
        </>
      )}
    </li>
  );
}
