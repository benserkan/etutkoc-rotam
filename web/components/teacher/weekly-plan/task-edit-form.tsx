"use client";

/**
 * "Görevi düzenle" — tek kalemli görev (2026-10-22 yeniden tasarım).
 *
 * Eski form yalnız KİTAPLI kalemi düzenleyebiliyordu: ders listesi yalnız kitabı olan
 * derslerdi, kaynaksız (müfredat konusuna bağlı) görev açılınca Ders/Kitap/Ünite boş
 * geliyor, birim (test/soru/sayfa) · kitap notu · sayfa aralığı hiç görünmüyordu.
 * Şimdi görev ekleme kutusuyla aynı dil: tüm dersler, "Kaynaksız" seçeneği, konu seçici,
 * birim + not + sayfa aralığı (kaldığı yer önerisi), miktar çipleri.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Loader2 } from "lucide-react";

import {
  getSubjectTopics,
  taskTopicKeys,
  type SubjectTopicsResponse,
} from "@/lib/api/task-topic-link";
import {
  getStudentAllSubjects,
  getStudentBookSections,
  getStudentBooksBySubject,
  getStudentSidebar,
  teacherKeys,
} from "@/lib/api/teacher";
import { usePatchTaskSingleItem } from "@/lib/hooks/use-teacher-mutations";
import type {
  BookOptionsResponse,
  ItemUnit,
  SectionOptionsResponse,
  SidebarResponse,
  SubjectListResponse,
  TaskPeriod,
  TaskType,
  TeacherTask,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

import { SourcelessOptions } from "./add-task-form";
import { usePageSuggestion } from "./task-seed";
import { TopicPickerPanel } from "./topic-picker-panel";

const FIELD =
  "w-full min-h-9 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

const PERIODS: { k: TaskPeriod | null; l: string }[] = [
  { k: null, l: "Yok" },
  { k: "morning", l: "Sabah" },
  { k: "noon", l: "Öğle" },
  { k: "evening", l: "Akşam" },
];

function FieldLabel({ htmlFor, children }: { htmlFor?: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-[12px] font-medium text-muted-foreground">
      {children}
    </label>
  );
}

function Section({
  title,
  children,
  testId,
}: {
  title: string;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-3" data-section={testId}>
      <h3 className="text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

/** Düzenlemenin desteklediği görev: tek kalem + (kitaplı ya da konulu kaynaksız). */
export function canRichEdit(task: TeacherTask): boolean {
  if (task.items.length !== 1) return false;
  const it = task.items[0];
  return it.book_id != null || it.topic_id != null;
}

export function TaskRichEditForm({
  studentId,
  task,
  onDone,
}: {
  studentId: number;
  task: TeacherTask;
  onDone: () => void;
}) {
  const editMut = usePatchTaskSingleItem(studentId);
  const item = task.items[0];
  const wasSourceless = item.book_id == null;
  const done = item.completed_count;

  const [taskDate, setTaskDate] = React.useState(task.date);
  const [hour, setHour] = React.useState<string>(
    task.scheduled_hour ? String(Number(task.scheduled_hour.slice(0, 2))) : "",
  );
  const [taskType, setTaskType] = React.useState<TaskType>(task.type);
  const [period, setPeriod] = React.useState<TaskPeriod | null>(
    (task.period as TaskPeriod | null) ?? null,
  );
  const [subjectId, setSubjectId] = React.useState<number | "">(item.subject_id ?? "");
  const [bookId, setBookId] = React.useState<number | "none" | "">(
    wasSourceless ? "none" : item.book_id,
  );
  const [sectionId, setSectionId] = React.useState<number | "">(
    wasSourceless ? "" : item.section_id,
  );
  const [topicId, setTopicId] = React.useState<number | "">(
    wasSourceless ? (item.topic_id ?? item.curriculum_topic_id ?? "") : "",
  );
  const [topicName, setTopicName] = React.useState<string | null>(
    wasSourceless ? item.topic_name : null,
  );
  const [topicOpen, setTopicOpen] = React.useState(false);
  const [unit, setUnit] = React.useState<ItemUnit>(wasSourceless ? (item.unit ?? "test") : "test");
  const [note, setNote] = React.useState(
    wasSourceless && item.book_name && item.book_name !== item.topic_name ? item.book_name : "",
  );
  const [pageFrom, setPageFrom] = React.useState(item.page_from ? String(item.page_from) : "");
  const [pageTo, setPageTo] = React.useState(item.page_to ? String(item.page_to) : "");
  const [count, setCount] = React.useState<string>(String(item.planned_count));
  const [notes, setNotes] = React.useState(task.notes ?? "");
  const [moveCompleted, setMoveCompleted] = React.useState(true);

  // Tüm dersler (kitabı olanlar önde, işaretli) — kaynaksız görev her derste verilebilir.
  const allQ = useQuery<SubjectListResponse>({
    queryKey: teacherKeys.studentAllSubjects(studentId),
    queryFn: () => getStudentAllSubjects(studentId),
    staleTime: 5 * 60_000,
  });
  const sidebarQ = useQuery<SidebarResponse>({
    queryKey: teacherKeys.studentSidebar(studentId, null),
    queryFn: () => getStudentSidebar(studentId, null),
    staleTime: 60_000,
  });
  const bookedIds = new Set((sidebarQ.data?.subjects ?? []).map((s) => s.id));
  const subjectList = (() => {
    const seen = new Map<number, string>();
    for (const s of sidebarQ.data?.subjects ?? []) seen.set(s.id, s.name);
    for (const s of allQ.data?.items ?? []) if (!seen.has(s.id)) seen.set(s.id, s.name);
    if (item.subject_id != null && !seen.has(item.subject_id)) {
      seen.set(item.subject_id, item.subject_name ?? "Ders");
    }
    return [...seen.entries()].map(([id, name]) => ({ id, name }));
  })();

  const booksQ = useQuery<BookOptionsResponse>({
    queryKey: teacherKeys.studentBooksBySubject(studentId, subjectId === "" ? null : subjectId),
    queryFn: () => getStudentBooksBySubject(studentId, subjectId === "" ? null : subjectId),
    enabled: subjectId !== "",
    staleTime: 60_000,
  });
  const books = booksQ.data?.items ?? [];
  const sourceless = bookId === "none";
  const realBookId = typeof bookId === "number" ? bookId : null;

  const sectionsQ = useQuery<SectionOptionsResponse>({
    queryKey: teacherKeys.studentBookSections(studentId, realBookId ?? 0),
    queryFn: () => getStudentBookSections(studentId, realBookId ?? 0),
    enabled: realBookId !== null,
    staleTime: 60_000,
  });
  const topicsQ = useQuery<SubjectTopicsResponse>({
    queryKey: taskTopicKeys.subjectTopics(studentId, subjectId === "" ? 0 : subjectId),
    queryFn: () => getSubjectTopics(studentId, subjectId === "" ? 0 : subjectId),
    enabled: sourceless && subjectId !== "",
    staleTime: 5 * 60_000,
  });
  const pageSugQ = usePageSuggestion(
    studentId,
    topicId === "" ? null : topicId,
    note,
    sourceless && unit === "sayfa",
    task.id,
  );

  // Kaynak değişimi + çözülenler
  const sourceChanged = sourceless
    ? !wasSourceless
    : wasSourceless || realBookId !== item.book_id || sectionId !== item.section_id;
  // Kaynaksız↔kitaplı geçişte çözülen varsa sunucu reddeder (çözülenin yeri belirsiz)
  const crossBlocked = done > 0 && sourceless !== wasSourceless;
  const canMove = done > 0 && sourceChanged && !crossBlocked && !sourceless;
  const sourceBlocked = crossBlocked || (canMove && !moveCompleted);

  const pageMode = sourceless && unit === "sayfa";
  const pf = Number(pageFrom);
  const pt = Number(pageTo);
  const rangeValid = pageMode && pageFrom !== "" && pageTo !== "" && pf >= 1 && pt >= pf;
  const qty = pageMode ? (rangeValid ? pt - pf + 1 : 0) : Number(count);
  const countBelow = Number.isFinite(qty) && qty > 0 && qty < done && !(canMove && moveCompleted);
  const ready =
    subjectId !== "" &&
    (sourceless ? topicId !== "" : realBookId !== null && sectionId !== "") &&
    Number.isFinite(qty) &&
    qty >= 1 &&
    (!pageMode || rangeValid);
  const unitWord = sourceless ? unit : sectionsQ.data?.is_deneme ? "deneme" : "test";
  const currentSection = (sectionsQ.data?.items ?? []).find((s) => s.id === sectionId);

  function onSubjectChange(v: string) {
    setSubjectId(v === "" ? "" : Number(v));
    setBookId("");
    setSectionId("");
    setTopicId("");
    setTopicName(null);
    setTopicOpen(false);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || countBelow || sourceBlocked) return;
    const hourNum = hour === "" ? null : Number(hour);
    const common = {
      date: taskDate,
      scheduled_hour: hourNum,
      type: taskType,
      period,
      notes: notes.trim() || null,
      planned_count: qty,
    };
    const body = sourceless
      ? {
          ...common,
          book_id: null,
          section_id: null,
          topic_id: topicId as number,
          label: note.trim() || null,
          unit,
          page_from: pageMode ? pf : null,
          page_to: pageMode ? pt : null,
        }
      : {
          ...common,
          book_id: realBookId,
          section_id: sectionId as number,
          move_completed: canMove && moveCompleted,
          allow_over_capacity: true,
        };
    editMut.mutate({ taskId: task.id, body }, { onSuccess: () => onDone() });
  }

  const id = (k: string) => `te-${k}-${task.id}`;

  return (
    <form onSubmit={submit} className="@container space-y-3" aria-label="Görev düzenleme">
      {done > 0 ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
          Bu görevde <b>{done}</b> {unitWord === "sayfa" ? "sayfa yapılmış" : `${unitWord} çözülmüş`}.
          Sayı bunun altına inemez.
        </p>
      ) : null}

      <Section title="Ne zaman?" testId="task-edit:when">
        <div className="grid grid-cols-1 gap-3 @md:grid-cols-3">
          <div>
            <FieldLabel htmlFor={id("date")}>Tarih</FieldLabel>
            <input
              id={id("date")}
              type="date"
              value={taskDate}
              onChange={(e) => setTaskDate(e.target.value)}
              required
              className={FIELD}
            />
          </div>
          <div>
            <FieldLabel htmlFor={id("hour")}>Saat</FieldLabel>
            <select id={id("hour")} value={hour} onChange={(e) => setHour(e.target.value)} className={FIELD}>
              <option value="">Saatsiz</option>
              {Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={String(h)}>
                  {String(h).padStart(2, "0")}:00
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel htmlFor={id("type")}>Tip</FieldLabel>
            <select
              id={id("type")}
              value={taskType}
              onChange={(e) => setTaskType(e.target.value as TaskType)}
              className={FIELD}
            >
              <option value="test">Test</option>
              <option value="video">Video</option>
              <option value="ozet">Özet</option>
              <option value="tekrar">Tekrar</option>
              <option value="other">Diğer</option>
            </select>
          </div>
        </div>
        <div>
          <FieldLabel>Gün içi bölüm</FieldLabel>
          <div className="inline-flex flex-wrap rounded-md border border-input bg-background p-0.5" role="radiogroup" aria-label="Periyot">
            {PERIODS.map((p) => (
              <button
                key={p.l}
                type="button"
                role="radio"
                aria-checked={period === p.k}
                onClick={() => setPeriod(p.k)}
                className={cn(
                  "rounded px-3 py-1 text-[12.5px] font-medium transition",
                  period === p.k ? "bg-cyan-700 text-white" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {p.l}
              </button>
            ))}
          </div>
        </div>
      </Section>

      <Section title="Ne çalışacak?" testId="task-edit:source">
        <div className="grid grid-cols-1 gap-3 @md:grid-cols-2">
          <div>
            <FieldLabel htmlFor={id("subject")}>Ders</FieldLabel>
            <select
              id={id("subject")}
              value={subjectId === "" ? "" : String(subjectId)}
              onChange={(e) => onSubjectChange(e.target.value)}
              className={FIELD}
            >
              <option value="">— ders seç —</option>
              {subjectList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {bookedIds.has(s.id) ? " · kitabı var" : ""}
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel htmlFor={id("book")}>Kaynak</FieldLabel>
            <select
              id={id("book")}
              value={bookId === "" ? "" : String(bookId)}
              onChange={(e) => {
                const v = e.target.value;
                setBookId(v === "" ? "" : v === "none" ? "none" : Number(v));
                setSectionId("");
                if (v === "none") setTopicOpen(topicId === "");
              }}
              disabled={subjectId === ""}
              className={FIELD}
            >
              <option value="">{subjectId === "" ? "— önce ders —" : "— kaynak seç —"}</option>
              {books.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
              {subjectId !== "" ? <option value="none">Kaynaksız (müfredat konusu)</option> : null}
            </select>
          </div>
        </div>

        {sourceless ? (
          <div>
            <FieldLabel>Müfredat konusu</FieldLabel>
            <button
              type="button"
              onClick={() => setTopicOpen((o) => !o)}
              aria-expanded={topicOpen}
              aria-label="Müfredat konusu seç"
              className={cn(
                "flex min-h-9 w-full items-center justify-between gap-2 rounded-md border bg-background px-3 py-1.5 text-left text-sm",
                topicOpen ? "border-cyan-600 ring-1 ring-cyan-600" : "border-input",
              )}
            >
              <span className={cn("min-w-0 break-words", !topicName && "text-muted-foreground")}>
                {topicName ?? "— konu ara / seç —"}
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            </button>
            {topicOpen ? (
              <div className="mt-2">
                <TopicPickerPanel
                  topics={topicsQ.data?.topics ?? []}
                  loading={topicsQ.isLoading}
                  selectedId={topicId === "" ? null : topicId}
                  onSelect={(t) => {
                    setTopicId(t.topic_id);
                    setTopicName(t.name);
                    setTopicOpen(false);
                  }}
                  onClose={() => setTopicOpen(false)}
                />
              </div>
            ) : null}
          </div>
        ) : realBookId !== null ? (
          <div>
            <FieldLabel htmlFor={id("section")}>Ünite / deneme</FieldLabel>
            <select
              id={id("section")}
              value={sectionId === "" ? "" : String(sectionId)}
              onChange={(e) => setSectionId(e.target.value === "" ? "" : Number(e.target.value))}
              className={FIELD}
            >
              <option value="">— ünite seç —</option>
              {(sectionsQ.data?.items ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                  {s.topic_name ? ` (${s.topic_name})` : ""} · kalan {s.remaining}
                </option>
              ))}
            </select>
            {currentSection && !sourceChanged ? (
              <p className="mt-1 text-[11.5px] text-muted-foreground">
                Bu ünitede boş kapasite: <b className="tabular-nums text-foreground">{currentSection.remaining}</b> test
                (bu görevin ayırdığı hariç).
              </p>
            ) : null}
          </div>
        ) : null}

        {sourceless && topicId !== "" ? (
          <SourcelessOptions
            unit={unit}
            onUnit={(u) => {
              setUnit(u);
              if (u !== "sayfa") {
                setPageFrom("");
                setPageTo("");
              }
            }}
            note={note}
            onNote={setNote}
            pageFrom={pageFrom}
            pageTo={pageTo}
            onPageFrom={setPageFrom}
            onPageTo={setPageTo}
            rangeInvalid={pageMode && pageFrom !== "" && pageTo !== "" && !rangeValid}
            suggestion={pageSugQ.data}
          />
        ) : null}

        {!pageMode ? (
          <div>
            <FieldLabel htmlFor={id("count")}>Miktar ({unitWord})</FieldLabel>
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Miktar">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-pressed={count === String(n)}
                  onClick={() => setCount(String(n))}
                  className={cn(
                    "h-9 w-9 rounded-md border text-sm font-semibold tabular-nums transition",
                    count === String(n)
                      ? "border-cyan-700 bg-cyan-700 text-white"
                      : "border-input bg-background text-foreground hover:bg-muted",
                  )}
                >
                  {n}
                </button>
              ))}
              <input
                id={id("count")}
                type="number"
                min={1}
                value={count}
                onChange={(e) => setCount(e.target.value)}
                aria-label={unitWord === "soru" ? "Soru sayısı" : unitWord === "deneme" ? "Deneme sayısı" : "Test sayısı"}
                className="h-9 w-24 rounded-md border border-input bg-background px-2.5 text-right text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        ) : (
          <p className="text-[12px] text-muted-foreground" aria-label="Sayfa adedi">
            Adet: <b className="tabular-nums text-foreground">{rangeValid ? `${qty} sayfa` : "aralıktan hesaplanır"}</b>
          </p>
        )}

        {crossBlocked ? (
          <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-800">
            Çözülen kısım olduğu için kitaplı ↔ kaynaksız geçiş yapılamaz. Yeni görev oluşturup
            bunu silebilirsin.
          </p>
        ) : null}
        {canMove ? (
          <label className="flex items-start gap-2 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-[12px] text-cyan-900">
            <input
              type="checkbox"
              checked={moveCompleted}
              onChange={(e) => setMoveCompleted(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              Çözülen <b>{done}</b> testi yeni üniteye taşı (eski ünitenin “çözüldü” sayısı düşer,
              yenisininki artar).{!moveCompleted ? " İşaretlemezsen kaynak değiştirilemez." : ""}
            </span>
          </label>
        ) : null}
        {countBelow ? (
          <p className="text-[12px] text-rose-700">
            Yeni miktar ({qty}) yapılan miktardan ({done}) küçük olamaz.
          </p>
        ) : null}
      </Section>

      <div>
        <FieldLabel htmlFor={id("notes")}>Öğrenciye not (isteğe bağlı)</FieldLabel>
        <textarea
          id={id("notes")}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          maxLength={500}
          className={FIELD}
        />
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
        <button
          type="button"
          onClick={onDone}
          disabled={editMut.isPending}
          className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition hover:bg-muted"
        >
          İptal
        </button>
        <button
          type="submit"
          disabled={editMut.isPending || !ready || countBelow || sourceBlocked}
          className="inline-flex items-center gap-1.5 rounded-md bg-cyan-700 px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-cyan-800 disabled:opacity-50"
        >
          {editMut.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
          Kaydet
        </button>
      </div>
    </form>
  );
}
