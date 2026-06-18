"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Check,
  ChevronRight,
  Clock,
  FileEdit,
  GripVertical,
  Layers,
  Loader2,
  Pencil,
  Plus,
  Rocket,
  Trash2,
} from "lucide-react";

import {
  getStudentBookSections,
  getStudentBooksBySubject,
  getStudentSidebar,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  usePublishDay,
  useReorderTasks,
} from "@/lib/hooks/use-weekly-plan-mutations";
import {
  useDeleteTask,
  usePatchTask,
  usePatchTaskSingleItem,
} from "@/lib/hooks/use-teacher-mutations";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  BookOptionsResponse,
  SectionOptionsResponse,
  SidebarResponse,
  TaskPeriod,
  TaskType,
  TeacherActivePhase,
  TeacherStudentWeekDay,
  TeacherStudentWeekResponse,
  TeacherTask,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";
import {
  findSubjectByExactName,
  findSubjectInTitle,
  subjectGroupKey,
  subjectHue,
  type SubjectRef,
} from "@/lib/subject-match";

import { AddTaskForm } from "./add-task-form";
import { InlineSuggestions } from "./inline-suggestions";
import { TaskItemResultBadge } from "./task-item-result-badge";

const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

const TASK_TYPE_LABELS: Record<string, string> = {
  test: "Test",
  video: "Video",
  ozet: "Özet",
  tekrar: "Tekrar",
  other: "Diğer",
};

const TASK_TYPE_TONE: Record<string, string> = {
  test: "bg-foreground/5 text-foreground border-border",
  video: "bg-sky-50 text-sky-700 border-sky-200",
  ozet: "bg-emerald-50 text-emerald-700 border-emerald-200",
  tekrar: "bg-violet-50 text-violet-700 border-violet-200",
  other: "bg-muted text-muted-foreground border-border",
};

interface Props {
  studentId: number;
  weekStartDate: string;
  day: TeacherStudentWeekDay;
  subjects: SubjectRef[];
  focusedSubjectId: number | null;
  onFocusSubject: (id: number | null) => void;
  // Single-open accordion: parent kontrol eder; aynı anda yalnızca tek gün açık.
  isOpen: boolean;
  onSetOpen: (open: boolean) => void;
  maturityValue: number;
  maturityLabel: string;
  weeksObserved: number;
  daysObserved: number;
  activePhase: TeacherActivePhase | null;
  trackRequired: boolean;
  trackMissing: boolean;
  trackLabel: string | null;
}

export function WeekDayCard({
  studentId,
  day,
  subjects,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- parent kontratı için tutuluyor
  focusedSubjectId,
  onFocusSubject,
  isOpen,
  onSetOpen,
  maturityValue,
  maturityLabel,
  weeksObserved,
  daysObserved,
  activePhase,
  trackRequired,
  trackMissing,
  trackLabel,
}: Props) {
  const [addOpen, setAddOpen] = React.useState(false);

  const draftCount = day.draft_count ?? 0;
  const subjectSummary = day.subject_summary ?? [];
  const suggestions = day.suggestions ?? [];

  const dateParts = parseISO(day.date);

  return (
    <details
      id={`day-${day.date}`}
      open={isOpen}
      onToggle={(e) => {
        const next = (e.target as HTMLDetailsElement).open;
        if (next !== isOpen) onSetOpen(next);
      }}
      className={cn(
        "scroll-mt-4",
        "day-card rounded-xl border bg-card group transition-shadow",
        day.is_today
          ? "border-foreground/30 shadow-sm ring-1 ring-foreground/5"
          : "border-border open:shadow-sm",
      )}
      data-day={day.date}
    >
      <summary className="px-5 py-3.5 flex items-center justify-between cursor-pointer hover:bg-muted/40 list-none rounded-t-xl">
        <div className="flex items-baseline gap-3 min-w-0">
          <ChevronRight
            className="size-4 text-muted-foreground transition-transform group-open:rotate-90 flex-shrink-0"
            aria-hidden
          />
          {day.is_today ? (
            <span
              className="size-2 rounded-full bg-foreground flex-shrink-0 self-center"
              aria-hidden
            />
          ) : null}
          <div className="font-semibold text-foreground tracking-tight">
            {day.dow_label}
          </div>
          {dateParts ? (
            <div className="text-sm text-muted-foreground tabular-nums">
              {dateParts.d} {TR_MONTHS[dateParts.m - 1]}
            </div>
          ) : null}
          {day.is_today ? (
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
              bugün
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {day.tasks_count > 0 ? (
            <>
              <span className="text-foreground font-medium tabular-nums">
                {day.tasks_count} görev
              </span>
              {(day.test_planned ?? 0) > 0 ? (
                <span className="tabular-nums">
                  · {day.test_completed}/{day.test_planned} test
                </span>
              ) : null}
              {(day.deneme_count ?? 0) > 0 ? (
                <span className="tabular-nums">· {day.deneme_count} deneme</span>
              ) : null}
              {day.tasks_count > 0 ? (
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 tabular-nums font-medium",
                    day.pct >= 0.7 ? "text-emerald-600" : day.pct >= 0.4 ? "text-amber-600" : "text-rose-600",
                  )}
                  title={`Görev tamamlama %${Math.round(day.pct * 100)}`}
                >
                  <span className="hidden sm:inline-block h-1.5 w-10 rounded-full bg-muted overflow-hidden align-middle">
                    <span
                      className={cn(
                        "block h-full rounded-full",
                        day.pct >= 0.7 ? "bg-emerald-500" : day.pct >= 0.4 ? "bg-amber-500" : "bg-rose-500",
                      )}
                      style={{ width: `${Math.min(100, Math.round(day.pct * 100))}%` }}
                    />
                  </span>
                  %{Math.round(day.pct * 100)}
                </span>
              ) : null}
              {draftCount > 0 ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border border-amber-200 bg-amber-50 text-amber-800">
                  <Pencil className="size-3" aria-hidden />
                  {draftCount} taslak
                </span>
              ) : null}
            </>
          ) : (
            <span className="italic text-muted-foreground/70">boş</span>
          )}
        </div>
      </summary>

      {draftCount > 0 ? (
        <DayPublishBanner
          studentId={studentId}
          dayDate={day.date}
          draftCount={draftCount}
        />
      ) : null}

      {subjectSummary.length > 0 ? (
        <div className="px-5 py-2 border-t border-border border-l-[3px] border-l-slate-300 dark:border-l-slate-600 bg-muted/50 flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-semibold text-muted-foreground/80 mr-1">
            <Layers className="size-3" aria-hidden /> Ders dağılımı
          </span>
          <span className="text-muted-foreground/40">·</span>
          {subjectSummary.filter((e) => e.task_count > 0).map((ent) => (
            <SubjectChip key={ent.subject_id} ent={ent} />
          ))}
          {(() => {
            const empty = subjectSummary.filter((e) => e.task_count === 0).length;
            const withTasks = subjectSummary.length - empty;
            if (empty === 0) return null;
            return (
              <span className="text-[11px] text-muted-foreground/70 italic">
                {withTasks === 0 ? "Bu güne ders seçilmedi" : `+${empty} ders planlanmadı`}
              </span>
            );
          })()}
        </div>
      ) : null}

      <TaskList studentId={studentId} day={day} subjects={subjects} />

      <div className="px-5 py-3 border-t border-border border-l-[3px] border-l-sky-400/70 bg-sky-500/[0.04]">
        <div
          className={cn(
            "rounded-lg border border-dashed transition",
            addOpen
              ? "border-foreground/40 bg-card shadow-sm"
              : "border-border bg-card hover:border-foreground/30",
          )}
        >
          <button
            type="button"
            onClick={() => setAddOpen((v) => !v)}
            className="w-full text-left px-3 py-2.5 text-sm font-medium text-foreground hover:bg-muted/50 rounded-lg flex items-center gap-2 transition"
            aria-expanded={addOpen}
          >
            <span className="inline-flex items-center justify-center size-5 rounded-md bg-foreground text-background">
              <Plus className="size-3.5" aria-hidden />
            </span>
            <span>Yeni görev ekle</span>
            <span className="ml-auto text-[11px] text-muted-foreground font-normal">
              {addOpen ? "kapat" : "tıkla → form açılır"}
            </span>
          </button>
          {addOpen ? (
            <AddTaskForm
              studentId={studentId}
              dayDate={day.date}
              onFocusSubject={onFocusSubject}
              onAfterAdd={() => {
                // form açık kalır; ders/kitap/ünite sıfırlanır (form içinde)
              }}
            />
          ) : null}
        </div>
      </div>

      <InlineSuggestions
        studentId={studentId}
        dayDate={day.date}
        suggestions={suggestions}
        maturityValue={maturityValue}
        maturityLabel={maturityLabel}
        weeksObserved={weeksObserved}
        daysObserved={daysObserved}
        activePhase={activePhase}
        trackRequired={trackRequired}
        trackMissing={trackMissing}
        trackLabel={trackLabel}
      />
    </details>
  );
}

function DayPublishBanner({
  studentId,
  dayDate,
  draftCount,
}: {
  studentId: number;
  dayDate: string;
  draftCount: number;
}) {
  const publishDay = usePublishDay(studentId);
  const dateParts = parseISO(dayDate);
  function onClick() {
    if (
      !window.confirm(
        `${dateParts?.d ?? ""} ${
          dateParts ? TR_MONTHS[dateParts.m - 1] : ""
        } günü için ${draftCount} taslak görev yayınlansın? Bu işlem öğrencinin paneline indirilecek.`,
      )
    ) {
      return;
    }
    publishDay.mutate({ body: { task_date: dayDate } });
  }
  return (
    <div className="px-5 py-2.5 border-t border-border bg-amber-50/60 flex items-center justify-between gap-3">
      <p className="inline-flex items-center gap-2 text-xs text-amber-900">
        <FileEdit className="size-3.5 text-amber-700" aria-hidden />
        <span>
          <span className="font-semibold">{draftCount} taslak görev</span> —
          öğrenci henüz göremiyor.
        </span>
      </p>
      <button
        type="button"
        onClick={onClick}
        disabled={publishDay.isPending}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium shadow-sm transition disabled:opacity-50"
      >
        {publishDay.isPending ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <Rocket className="size-3.5" aria-hidden />
        )}
        Bu günü yayınla
      </button>
    </div>
  );
}

function SubjectChip({
  ent,
}: {
  ent: NonNullable<TeacherStudentWeekDay["subject_summary"]>[number];
}) {
  const hue = (ent.subject_id * 67) % 360;
  const hasTasks = ent.task_count > 0;
  return (
    <div
      className={cn(
        "flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-md border",
        hasTasks ? "" : "border-dashed bg-muted/40 text-muted-foreground",
      )}
      style={
        hasTasks
          ? {
              background: `hsl(${hue}, 45%, 97%)`,
              borderColor: `hsl(${hue}, 35%, 82%)`,
            }
          : undefined
      }
      title={
        hasTasks
          ? `${ent.subject_name} — ${ent.task_count} görev` +
            (ent.tests ? ` · ${ent.tests} test` : "") +
            (ent.denemeler ? ` · ${ent.denemeler} deneme` : "")
          : `${ent.subject_name} — bu güne görev seçilmedi`
      }
    >
      <span
        className="font-semibold whitespace-nowrap"
        style={
          hasTasks ? { color: `hsl(${hue}, 45%, 28%)` } : undefined
        }
      >
        {ent.subject_name}
      </span>
      {hasTasks ? (
        <>
          <span className="text-foreground/80 whitespace-nowrap tabular-nums">
            {ent.task_count}
          </span>
          {ent.tests > 0 ? (
            <>
              <span className="text-muted-foreground/40">·</span>
              <span className="text-emerald-700 whitespace-nowrap tabular-nums">
                {ent.tests} test
              </span>
            </>
          ) : null}
          {ent.denemeler > 0 ? (
            <>
              <span className="text-muted-foreground/40">·</span>
              <span className="text-indigo-700 whitespace-nowrap tabular-nums">
                {ent.denemeler} deneme
              </span>
            </>
          ) : null}
        </>
      ) : (
        <span className="italic">—</span>
      )}
    </div>
  );
}

// ============================================================================
// Ders gruplama (Katman 1) — görevler ders bazlı gruplanır; aynı dersin
// görevleri yan yana durur (araya başka ders girmez). Etkinlik (kalemsiz)
// görevlerinde ders backend'den gelmez → başlık "{Ders} · {içerik}" parse edilir.
// ============================================================================

interface TaskSubject {
  key: string;
  id: number | null;
  name: string;
}

// Grup anahtarı ADA göre (subjectGroupKey) — aynı isimli ders (farklı müfredat
// id'si olsa bile) TEK grupta birleşir: "Fizik" testi + "Fizik" branş denemesi.
function taskSubject(task: TeacherTask, subjects?: SubjectRef[]): TaskSubject {
  const withSubj = task.items.find((it) => it.subject_id != null);
  if (withSubj?.subject_id != null) {
    const nm = withSubj.subject_name ?? "Ders";
    return { key: subjectGroupKey(nm), id: withSubj.subject_id, name: nm };
  }
  // Etkinlik (kalemsiz) VEYA blok görevi → başlık "{Ders} · {içerik}" parse et.
  if (task.items.length === 0 || task.work_block_id != null) {
    const sep = task.title.indexOf(" · ");
    if (sep > 0 && sep < task.title.length - 3) {
      const nm = task.title.substring(0, sep);
      // Bilinen bir derse çözülürse o dersin ADIYLA birleşir; değilse ham ad.
      const resolved = findSubjectByExactName(nm, subjects);
      const name = resolved ? resolved.name : nm;
      return { key: subjectGroupKey(name), id: resolved?.id ?? null, name };
    }
  }
  // Branş/genel deneme vb. (kitapsız kalem, " · " öneki yok) → başlıkta ders adı ara.
  const inTitle = findSubjectInTitle(task.title, subjects);
  if (inTitle) {
    return { key: subjectGroupKey(inTitle.name), id: inTitle.id, name: inTitle.name };
  }
  return { key: "other", id: null, name: "Diğer çalışmalar" };
}

// --------- Periyot (Sabah/Öğle/Akşam) — öğrenci günü periyotluysa editörde de ----
const PERIOD_RANK: Record<string, number> = {
  morning: 0,
  noon: 1,
  evening: 2,
};
const PERIOD_LABELS: Record<string, string> = {
  morning: "Sabah",
  noon: "Öğle",
  evening: "Akşam",
  none: "Zaman belirtilmemiş",
};
function periodRank(p: string | null | undefined): number {
  return p && p in PERIOD_RANK ? PERIOD_RANK[p] : 3;
}
function periodKey(p: string | null | undefined): string {
  return p && p in PERIOD_RANK ? p : "none";
}

// Görevleri (periyot →) ders grubuna göre sırala. Periyot kullanılıyorsa önce
// Sabah/Öğle/Akşam/belirsiz; her periyot içinde dersler ilk-görülme sırasında,
// "Diğer" en sonda. Periyot kullanılmıyorsa yalnız ders gruplaması (Katman 1).
function dayTaskOrder(
  tasks: TeacherTask[],
  subjects: SubjectRef[] | undefined,
  usePeriods: boolean,
): number[] {
  // bucket: periodRank -> { subjOrder, subj: Map<subjKey, ids[]> }
  const buckets = new Map<
    number,
    { subjOrder: string[]; subj: Map<string, number[]> }
  >();
  for (const t of tasks) {
    const pr = usePeriods ? periodRank(t.period) : 0;
    const sk = taskSubject(t, subjects).key;
    let b = buckets.get(pr);
    if (!b) {
      b = { subjOrder: [], subj: new Map() };
      buckets.set(pr, b);
    }
    if (!b.subj.has(sk)) {
      b.subj.set(sk, []);
      b.subjOrder.push(sk);
    }
    b.subj.get(sk)!.push(t.id);
  }
  const result: number[] = [];
  for (const pr of Array.from(buckets.keys()).sort((a, b) => a - b)) {
    const b = buckets.get(pr)!;
    const order = [...b.subjOrder].sort(
      (a, b2) => (a === "other" ? 1 : 0) - (b2 === "other" ? 1 : 0),
    );
    for (const sk of order) result.push(...(b.subj.get(sk) ?? []));
  }
  return result;
}

function SubjectGroupHeader({
  subj,
  count,
}: {
  subj: TaskSubject;
  count: number;
}) {
  const hue = subjectHue(subj.name);
  return (
    <div
      className="flex items-center gap-2 px-4 pt-3 pb-1.5 bg-muted/20 border-l-[3px]"
      style={{ borderLeftColor: `hsl(${hue}, 45%, 65%)` }}
    >
      <span
        className="size-2 rounded-full flex-shrink-0"
        style={{ backgroundColor: `hsl(${hue}, 55%, 52%)` }}
        aria-hidden
      />
      <span className="text-xs font-semibold text-foreground">{subj.name}</span>
      <span className="text-[11px] text-muted-foreground tabular-nums">
        · {count} görev
      </span>
    </div>
  );
}

function PeriodHeader({ pkey, count }: { pkey: string; count: number }) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-foreground/[0.07] border-y border-border">
      <Clock className="size-3.5 text-foreground/70 flex-shrink-0" aria-hidden />
      <span className="text-[12px] uppercase tracking-wider font-bold text-foreground">
        {PERIOD_LABELS[pkey] ?? PERIOD_LABELS.none}
      </span>
      <span className="ml-auto text-[10px] text-muted-foreground tabular-nums bg-background/70 rounded-full px-2 py-0.5">
        {count} görev
      </span>
    </div>
  );
}

// ============================================================================
// Task list with drag-drop
// ============================================================================

function TaskList({
  studentId,
  day,
  subjects,
}: {
  studentId: number;
  day: TeacherStudentWeekDay;
  subjects: SubjectRef[];
}) {
  const reorderMut = useReorderTasks(studentId);
  const patchTask = usePatchTask(studentId, day.date);
  const qc = useQueryClient();
  // Gün periyot kullanıyor mu? En az bir görevde period dolu ise Sabah/Öğle/
  // Akşam bölümleri gösterilir (öğrenci günü mantığıyla aynı).
  const usePeriods = day.tasks.some((t) => t.period != null);

  const [orderedIds, setOrderedIds] = React.useState<number[]>(() =>
    dayTaskOrder(day.tasks, subjects, usePeriods),
  );

  // Görev seti / periyot-modu / görev PERİYODU / DERS LİSTESİ değişince türetilmiş
  // (periyot → ders MIKNATIS) sıraya yeniden kur. KRİTİK: subjects async yüklenir;
  // anahtara subjects imzası dahil → ders listesi gelince (branş deneme isimden
  // çözülünce) sıra yeniden hesaplanır (yoksa deneme "Diğer" konumunda kalıp
  // başlık Fizik'e çözülür = ayrık görünür). period değişince de anında düzenlenir.
  const orderKey =
    (usePeriods ? "p:" : "s:") +
    "subj:" +
    subjects.map((s) => s.id).join(",") +
    "|" +
    day.tasks
      .map((t) => `${t.id}:${t.period ?? ""}`)
      .sort()
      .join(",");
  const [lastKey, setLastKey] = React.useState(orderKey);
  if (lastKey !== orderKey) {
    setLastKey(orderKey);
    setOrderedIds(dayTaskOrder(day.tasks, subjects, usePeriods));
  }

  const tasksById = React.useMemo(() => {
    const m = new Map<number, TeacherTask>();
    for (const t of day.tasks) m.set(t.id, t);
    return m;
  }, [day.tasks]);

  // Ders grup başına sayı — periyot kullanılıyorsa periyot+ders bazlı anahtar.
  const groupCounts = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const t of day.tasks) {
      const pk = usePeriods ? periodKey(t.period) : "_";
      const k = `${pk}|${taskSubject(t, subjects).key}`;
      m.set(k, (m.get(k) ?? 0) + 1);
    }
    return m;
  }, [day.tasks, subjects, usePeriods]);

  // Periyot başına toplam görev (periyot başlığında gösterilir).
  const periodCounts = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const t of day.tasks) {
      const pk = periodKey(t.period);
      m.set(pk, (m.get(pk) ?? 0) + 1);
    }
    return m;
  }, [day.tasks]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );

  function onDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const activeTask = tasksById.get(Number(active.id));
    const overTask = tasksById.get(Number(over.id));
    if (!activeTask || !overTask) return;

    // (1) Farklı periyot bölümüne bırakıldı → görevin periyodunu hedef bölüme TAŞI
    // (mıknatıs: o periyodun ders grubuna girer; sayfa yenilense de kalıcı).
    if (
      usePeriods &&
      periodKey(activeTask.period) !== periodKey(overTask.period)
    ) {
      const targetPeriod = overTask.period ?? null; // null = Zaman belirtilmemiş
      const prevPeriod = activeTask.period ?? null;
      // OPTİMİSTİK: week cache'inde period'u hemen güncelle → editör + Hafta
      // Izgarası ANINDA yeni periyoda taşır (refetch beklenmez). Hata → geri al.
      const setPeriodInCache = (p: TaskPeriod | null) =>
        qc.setQueriesData<TeacherStudentWeekResponse>(
          { queryKey: ["teacher", "me", "students", String(studentId), "week"] },
          (prev) =>
            prev
              ? {
                  ...prev,
                  days: prev.days.map((d) => ({
                    ...d,
                    tasks: d.tasks.map((t) =>
                      t.id === activeTask.id ? { ...t, period: p } : t,
                    ),
                  })),
                }
              : prev,
        );
      setPeriodInCache(targetPeriod);
      patchTask.mutate(
        { taskId: activeTask.id, body: { period: overTask.period ?? "" } },
        { onError: () => setPeriodInCache(prevPeriod) },
      );
      return;
    }

    // (2) Farklı ders grubuna bırakma → mıknatıs gereği YOK SAY (dersler iç içe
    // geçmez). Yalnız AYNI ders grubu içinde yeniden sıralama kaydedilir.
    if (
      taskSubject(activeTask, subjects).key !==
      taskSubject(overTask, subjects).key
    ) {
      return;
    }
    setOrderedIds((prev) => {
      const oldIdx = prev.indexOf(Number(active.id));
      const newIdx = prev.indexOf(Number(over.id));
      if (oldIdx < 0 || newIdx < 0) return prev;
      const next = arrayMove(prev, oldIdx, newIdx);
      reorderMut.mutate({ body: { task_date: day.date, task_ids: next } });
      return next;
    });
  }

  if (day.tasks.length === 0) {
    return (
      <div className="border-t border-border px-5 py-3 text-sm text-muted-foreground italic">
        görev yok
      </div>
    );
  }

  return (
    <DndContext
      // Stable id zorunlu: dnd-kit module-level useUniqueId counter'ı SSR↔client
      // arasında farklı değer üretir → "DndDescribedBy-N" hydration mismatch.
      id={`dnd-day-${day.date}`}
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={onDragEnd}
    >
      <SortableContext items={orderedIds} strategy={verticalListSortingStrategy}>
        <div className="divide-y divide-border/60 border-t border-border">
          {orderedIds.map((id, idx) => {
            const task = tasksById.get(id);
            if (!task) return null;
            const subj = taskSubject(task, subjects);
            const pk = usePeriods ? periodKey(task.period) : "_";
            const prevTask =
              idx > 0 ? tasksById.get(orderedIds[idx - 1]) : undefined;
            const prevPk = prevTask
              ? usePeriods
                ? periodKey(prevTask.period)
                : "_"
              : null;
            const prevSubjKey = prevTask
              ? taskSubject(prevTask, subjects).key
              : null;
            const showPeriod = usePeriods && pk !== prevPk;
            const showSubject = showPeriod || subj.key !== prevSubjKey;
            return (
              <React.Fragment key={id}>
                {showPeriod ? (
                  <PeriodHeader pkey={pk} count={periodCounts.get(pk) ?? 1} />
                ) : null}
                {showSubject ? (
                  <SubjectGroupHeader
                    subj={subj}
                    count={groupCounts.get(`${pk}|${subj.key}`) ?? 1}
                  />
                ) : null}
                <SortableTaskRow
                  studentId={studentId}
                  dayDate={day.date}
                  task={task}
                  subjects={subjects}
                />
              </React.Fragment>
            );
          })}
        </div>
      </SortableContext>
    </DndContext>
  );
}

function SortableTaskRow({
  studentId,
  dayDate,
  task,
  subjects,
}: {
  studentId: number;
  dayDate: string;
  task: TeacherTask;
  subjects: SubjectRef[];
}) {
  const deleteMut = useDeleteTask(studentId, dayDate);
  const [editOpen, setEditOpen] = React.useState(false);
  const hourBound = task.scheduled_hour !== null;
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id, disabled: hourBound });

  // Kitapsız etkinlik görevlerinde (Video/Özet/Tekrar/Diğer · items=[]) ders
  // backend'den gelmez; add-task-form başlığı `{Ders} · {içerik}` formatında
  // üretir → burada parse edip rozet olarak gösteririz (Test ile görsel
  // simetri). Title "·" içermiyorsa fallback: ders yok.
  let primarySubjectName: string | null = task.items[0]?.subject_name ?? null;
  let displayTitle = task.title;
  if (!primarySubjectName && (task.items.length === 0 || task.work_block_id != null)) {
    const sepIdx = task.title.indexOf(" · ");
    if (sepIdx > 0 && sepIdx < task.title.length - 3) {
      primarySubjectName = task.title.substring(0, sepIdx);
      displayTitle = task.title.substring(sepIdx + 3);
    }
  }
  // Branş deneme (kitapsız, " · " öneki yok) — görev adından dersi çöz (alias
  // dahil): "AYT Fizik Branş" → Fizik. Bulunursa ders rozeti DENEME'nin başında
  // gösterilir (genel denemede ders bulunmaz → yalnız DENEME). Test ile simetri.
  if (!primarySubjectName) {
    const resolved = taskSubject(task, subjects);
    if (resolved.key !== "other") {
      primarySubjectName = resolved.name;
    }
  }
  // Renk hue: ders ADINA göre (grup başlığıyla AYNI renk; aynı ad daima aynı
  // ton). Ders yoksa nötr (220).
  const hue = primarySubjectName ? subjectHue(primarySubjectName) : 220;
  // Serbest iş bloğu görevi (work_block_id set) — "deneme"den ayır.
  const isBlock = task.work_block_id != null;
  // Kitapsız (deneme) kalem = book_id None → tam deneme; blok + bloğu-silinmiş
  // (block_detached) görev HARİÇ → onlar 'Diğer' olarak gösterilir, DENEME değil.
  const isDeneme =
    !isBlock && !task.block_detached && task.items.some((it) => it.book_id === null);
  // Dersi olmayan etkinlik satırları (video/özet/tekrar/diğer) için tip-renkli şerit.
  const ACTIVITY_ACCENT: Record<string, string> = {
    video: "#38bdf8", ozet: "#34d399", tekrar: "#a78bfa", other: "#94a3b8",
  };

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    borderLeftColor:
      primarySubjectName
        ? `hsl(${hue}, 45%, 65%)`
        : isBlock
          ? "#8b5cf6" // violet — serbest blok
          : isDeneme
            ? "#6366f1" // indigo — deneme
            : ACTIVITY_ACCENT[task.type] ?? "transparent",
    opacity: isDragging ? 0.5 : 1,
  };

  const typeTone =
    TASK_TYPE_TONE[task.type] ?? "bg-muted text-muted-foreground border-border";

  return (
    <div
      ref={setNodeRef}
      id={`task-${task.id}`}
      className={cn(
        "px-4 py-2.5 flex items-start gap-3 border-l-[3px] task-row transition-colors",
        isBlock
          ? "bg-violet-500/[0.05] hover:bg-violet-500/[0.09]"
          : isDeneme
            ? "bg-indigo-500/[0.05] hover:bg-indigo-500/[0.09]"
            : "hover:bg-muted/30",
      )}
      style={style}
    >
      <button
        type="button"
        className={cn(
          "select-none text-muted-foreground hover:text-foreground flex-shrink-0 mt-1 leading-none transition",
          hourBound ? "opacity-30 cursor-not-allowed" : "cursor-grab",
        )}
        title={
          hourBound
            ? "Saat atanmış: kronolojik sırada"
            : "Sürükle-bırak ile sırala"
        }
        {...attributes}
        {...listeners}
        aria-label="Sırala"
      >
        <GripVertical className="size-4" aria-hidden />
      </button>
      {task.scheduled_hour !== null ? (
        <span
          className="inline-flex items-center justify-center text-[10px] font-bold font-mono px-1.5 py-0.5 rounded-md flex-shrink-0 mt-0.5 min-w-[42px] bg-foreground/10 text-foreground tabular-nums"
        >
          {String(task.scheduled_hour).padStart(2, "0")}:00
        </span>
      ) : null}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {primarySubjectName ? (
            <span
              className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded whitespace-nowrap"
              style={{
                background: `hsl(${hue}, 60%, 92%)`,
                color: `hsl(${hue}, 50%, 28%)`,
              }}
              title={primarySubjectName}
            >
              {primarySubjectName}
            </span>
          ) : null}
          <span
            className={cn(
              "text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded border",
              isBlock
                ? "bg-violet-100 text-violet-700 border-violet-300 dark:bg-violet-950/40 dark:text-violet-200 dark:border-violet-800"
                : isDeneme
                  ? "bg-indigo-100 text-indigo-700 border-indigo-300"
                  : typeTone,
            )}
          >
            {isBlock ? "Blok" : isDeneme ? "Deneme" : (TASK_TYPE_LABELS[task.type] ?? task.type)}
          </span>
          {isBlock && task.planned_count > 0 ? (
            <span className="text-[11px] text-violet-700 dark:text-violet-300 font-medium tabular-nums">
              {task.planned_count} {task.work_block_unit ?? "test"}
            </span>
          ) : isDeneme && task.planned_count > 0 ? (
            <span className="text-[11px] text-indigo-700 font-medium tabular-nums">
              {task.planned_count} soru
            </span>
          ) : null}
          {task.is_draft ? (
            <span
              className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded border border-amber-200 bg-amber-50 text-amber-800"
              title="Henüz yayınlanmadı — öğrenci paneline inmez"
            >
              <Pencil className="size-2.5" aria-hidden />
              taslak
            </span>
          ) : null}
          <span className="text-sm font-medium text-foreground">
            {displayTitle}
          </span>
          {task.completed_count > 0 ? (
            <span className="text-xs text-emerald-700 tabular-nums">
              · {task.completed_count}/{task.planned_count}
            </span>
          ) : null}
          {/* Tek kalemli görevde D/Y rozeti — task badge'lerinin yanına inline */}
          {task.items.length === 1 ? (
            <TaskItemResultBadge
              studentId={studentId}
              dateIso={dayDate}
              task={task}
              item={task.items[0]}
            />
          ) : null}
          {task.status === "completed" ? (
            <span className="inline-flex items-center gap-0.5 text-xs text-emerald-700">
              <Check className="size-3" aria-hidden />
              tamam
            </span>
          ) : task.status === "partial" ? (
            <span className="text-xs text-amber-700">kısmen</span>
          ) : null}
        </div>
        {task.items.length > 1 ? (
          <div className="mt-1 text-xs text-muted-foreground space-y-0.5">
            {task.items.map((it) => (
              <div key={it.id} className="flex items-baseline flex-wrap">
                <span className="text-muted-foreground/60">▸</span>{" "}
                <span>
                  {it.book_name} — {it.section_label}
                  {it.topic_name ? (
                    <span className="text-muted-foreground/70">
                      {" "}({it.topic_name})
                    </span>
                  ) : null}
                  : <span className="font-medium tabular-nums">{it.planned_count}</span>
                  {it.completed_count > 0 ? (
                    <span className="text-emerald-700 tabular-nums">
                      {" "}({it.completed_count} çöz.)
                    </span>
                  ) : null}
                </span>
                <TaskItemResultBadge
                  studentId={studentId}
                  dateIso={dayDate}
                  task={task}
                  item={it}
                />
              </div>
            ))}
          </div>
        ) : null}
        {task.notes ? (
          <div className="mt-1 text-xs text-muted-foreground italic truncate max-w-xl border-l-2 border-border pl-2">
            {task.notes}
          </div>
        ) : null}
      </div>
      <div className="flex items-center gap-2 text-xs whitespace-nowrap flex-shrink-0">
        <button
          type="button"
          onClick={() => setEditOpen(true)}
          className="inline-flex items-center gap-1 px-1.5 py-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition"
          title="Düzenle"
          aria-label="Düzenle"
        >
          <Pencil className="size-3.5" aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => {
            if (
              !window.confirm(
                "Görev silinsin mi? Rezerv edilen testler iade edilecek.",
              )
            ) {
              return;
            }
            deleteMut.mutate({ taskId: task.id });
          }}
          disabled={deleteMut.isPending}
          className="inline-flex items-center gap-1 px-1.5 py-1 rounded text-muted-foreground hover:text-destructive hover:bg-muted transition"
          title="Sil"
        >
          {deleteMut.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <Trash2 className="size-3.5" aria-hidden />
          )}
        </button>
      </div>

      <TaskQuickEditDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        studentId={studentId}
        dayDate={dayDate}
        task={task}
      />
    </div>
  );
}

function TaskQuickEditDialog({
  open,
  onOpenChange,
  studentId,
  dayDate,
  task,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  studentId: number;
  dayDate: string;
  task: TeacherTask;
}) {
  const isSingleItem = task.items.length === 1;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={isSingleItem ? "max-w-2xl" : "max-w-md"}>
        <DialogHeader>
          <DialogTitle>Görevi düzenle</DialogTitle>
          <p className="text-xs text-muted-foreground mt-1">
            {isSingleItem
              ? "Kaynak (kitap/ünite/adet) değiştirebilir, saat/tip/not güncelleyebilirsin. Başlık otomatik üretilir."
              : "Çok kalemli görevde yalnızca üst-bilgi (saat/taslak/not) düzenlenir. Kalem değiştirmek için görevi silip yeniden oluştur."}
          </p>
        </DialogHeader>
        {/* Dialog her açılışta form'u sıfır mount eder; initial state task'tan alınır. */}
        {open ? (
          isSingleItem ? (
            <TaskRichEditForm
              studentId={studentId}
              task={task}
              onDone={() => onOpenChange(false)}
            />
          ) : (
            <TaskQuickEditForm
              studentId={studentId}
              dayDate={dayDate}
              task={task}
              onDone={() => onOpenChange(false)}
            />
          )
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function TaskRichEditForm({
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

  const [taskDate, setTaskDate] = React.useState(task.date);
  const [hour, setHour] = React.useState<string>(
    task.scheduled_hour ? task.scheduled_hour.slice(0, 2) : "",
  );
  const [taskType, setTaskType] = React.useState<TaskType>(task.type);
  const [subjectId, setSubjectId] = React.useState<number | "">(
    item.subject_id ?? "",
  );
  const [bookId, setBookId] = React.useState<number | "">(item.book_id);
  const [sectionId, setSectionId] = React.useState<number | "">(item.section_id);
  const [count, setCount] = React.useState<string>(String(item.planned_count));
  const [notes, setNotes] = React.useState(task.notes ?? "");

  // Ders listesi — tüm sidebar (subject focus filtresiz)
  const sidebarQ = useQuery<SidebarResponse>({
    queryKey: teacherKeys.studentSidebar(studentId, null),
    queryFn: () => getStudentSidebar(studentId, null),
    staleTime: 60_000,
  });
  const subjects = (sidebarQ.data?.subjects ?? []).map((s) => ({
    id: s.id,
    name: s.name,
  }));

  // Subject → books cascade
  const booksQ = useQuery<BookOptionsResponse>({
    queryKey: teacherKeys.studentBooksBySubject(
      studentId,
      subjectId === "" ? null : subjectId,
    ),
    queryFn: () =>
      getStudentBooksBySubject(
        studentId,
        subjectId === "" ? null : subjectId,
      ),
    enabled: subjectId !== "",
    staleTime: 60_000,
  });

  // Book → sections cascade
  const sectionsQ = useQuery<SectionOptionsResponse>({
    queryKey: teacherKeys.studentBookSections(
      studentId,
      bookId === "" ? 0 : bookId,
    ),
    queryFn: () => getStudentBookSections(studentId, bookId === "" ? 0 : bookId),
    enabled: bookId !== "",
    staleTime: 60_000,
  });

  // Kaynak değişti mi (Jinja parite — completed > 0 ise blokla)
  const sourceChanged =
    bookId !== item.book_id || sectionId !== item.section_id;
  const sourceBlocked = sourceChanged && item.completed_count > 0;
  const countBelowCompleted =
    count !== "" && Number(count) < item.completed_count;

  function onSubjectChange(v: string) {
    const num = v === "" ? "" : Number(v);
    setSubjectId(num as number | "");
    setBookId("");
    setSectionId("");
  }

  function onBookChange(v: string) {
    const num = v === "" ? "" : Number(v);
    setBookId(num as number | "");
    setSectionId("");
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (bookId === "" || sectionId === "" || count === "") return;
    const countNum = Number(count);
    if (!Number.isFinite(countNum) || countNum < 1) return;
    const hourNum = hour.trim() === "" ? null : Number(hour);
    if (hourNum !== null && (!Number.isFinite(hourNum) || hourNum < 0 || hourNum > 23)) {
      return;
    }
    editMut.mutate(
      {
        taskId: task.id,
        body: {
          date: taskDate,
          scheduled_hour: hourNum,
          type: taskType,
          book_id: bookId,
          section_id: sectionId,
          planned_count: countNum,
          notes: notes.trim() || null,
        },
      },
      { onSuccess: () => onDone() },
    );
  }

  // Seçili section'da kalan kapasite (Jinja parite UX hint)
  const currentSection = (sectionsQ.data?.items ?? []).find(
    (s) => s.id === sectionId,
  );

  return (
    <form onSubmit={submit} className="space-y-4">
      {item.completed_count > 0 ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Bu görevde <b>{item.completed_count}</b> test çözülmüş — kaynak (kitap/ünite)
          değişikliği bloke; sayıyı en az <b>{item.completed_count}</b> tutmalısın.
        </div>
      ) : null}

      <div className="grid grid-cols-3 gap-3">
        <div>
          <Label htmlFor={`re-date-${task.id}`}>Tarih</Label>
          <input
            id={`re-date-${task.id}`}
            type="date"
            value={taskDate}
            onChange={(e) => setTaskDate(e.target.value)}
            required
            className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <Label htmlFor={`re-hour-${task.id}`}>Saat (0-23, boş = saatsiz)</Label>
          <input
            id={`re-hour-${task.id}`}
            type="number"
            min={0}
            max={23}
            value={hour}
            onChange={(e) => setHour(e.target.value)}
            placeholder="—"
            className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm font-mono text-center tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <Label htmlFor={`re-type-${task.id}`}>Tip</Label>
          <select
            id={`re-type-${task.id}`}
            value={taskType}
            onChange={(e) => setTaskType(e.target.value as TaskType)}
            className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="test">Test</option>
            <option value="video">Video</option>
            <option value="ozet">Özet</option>
            <option value="tekrar">Tekrar</option>
            <option value="other">Diğer</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-3">
          <Label htmlFor={`re-subject-${task.id}`}>Ders</Label>
          <select
            id={`re-subject-${task.id}`}
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={(e) => onSubjectChange(e.target.value)}
            disabled={sourceBlocked}
            className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          >
            <option value="">— ders seç —</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <div className="col-span-4">
          <Label htmlFor={`re-book-${task.id}`}>Kitap</Label>
          <select
            id={`re-book-${task.id}`}
            value={bookId === "" ? "" : String(bookId)}
            onChange={(e) => onBookChange(e.target.value)}
            disabled={subjectId === "" || sourceBlocked}
            className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          >
            <option value="">— önce ders —</option>
            {(booksQ.data?.items ?? []).map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div className="col-span-3">
          <Label htmlFor={`re-section-${task.id}`}>Ünite / Deneme</Label>
          <select
            id={`re-section-${task.id}`}
            value={sectionId === "" ? "" : String(sectionId)}
            onChange={(e) =>
              setSectionId(e.target.value === "" ? "" : Number(e.target.value))
            }
            disabled={bookId === "" || sourceBlocked}
            className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          >
            <option value="">— önce kitap —</option>
            {(sectionsQ.data?.items ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
                {s.topic_name ? ` (${s.topic_name})` : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="col-span-2">
          <Label htmlFor={`re-count-${task.id}`}>Test Sayısı</Label>
          <input
            id={`re-count-${task.id}`}
            type="number"
            min={Math.max(1, item.completed_count)}
            value={count}
            onChange={(e) => setCount(e.target.value)}
            required
            className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm text-right tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      {currentSection ? (
        <div className="text-[11px] text-muted-foreground">
          Bu ünitede kalan kapasite:{" "}
          <span className="font-semibold text-foreground tabular-nums">
            {currentSection.remaining}
          </span>{" "}
          test. Tamamlanan: <span className="tabular-nums">{item.completed_count}</span>/
          <span className="tabular-nums">{item.planned_count}</span>.
        </div>
      ) : null}

      {countBelowCompleted ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
          Yeni sayı ({count}) tamamlanmış miktardan ({item.completed_count}) küçük olamaz.
        </div>
      ) : null}

      <div className="space-y-1">
        <Label htmlFor={`re-notes-${task.id}`}>Not (opsiyonel)</Label>
        <textarea
          id={`re-notes-${task.id}`}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          maxLength={500}
          className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
        <button
          type="button"
          onClick={onDone}
          disabled={editMut.isPending}
          className="px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-muted transition"
        >
          İptal
        </button>
        <button
          type="submit"
          disabled={
            editMut.isPending ||
            bookId === "" ||
            sectionId === "" ||
            !count ||
            countBelowCompleted
          }
          className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-foreground text-background text-sm font-medium hover:bg-foreground/90 disabled:opacity-50 transition"
        >
          {editMut.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : null}
          Kaydet
        </button>
      </div>
    </form>
  );
}

function Label({
  htmlFor,
  children,
}: {
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1"
    >
      {children}
    </label>
  );
}

function TaskQuickEditForm({
  studentId,
  dayDate,
  task,
  onDone,
}: {
  studentId: number;
  dayDate: string;
  task: TeacherTask;
  onDone: () => void;
}) {
  const patchMut = usePatchTask(studentId, dayDate);
  const [title, setTitle] = React.useState(task.title);
  const [hour, setHour] = React.useState<string>(
    task.scheduled_hour ? task.scheduled_hour.slice(0, 2) : "",
  );
  const [isDraft, setIsDraft] = React.useState(task.is_draft);
  const [notes, setNotes] = React.useState(task.notes ?? "");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    let hourNum: number | null | undefined;
    if (hour.trim() === "") {
      hourNum = task.scheduled_hour !== null ? null : undefined;
    } else {
      const h = Number(hour);
      if (!Number.isFinite(h) || h < 0 || h > 23) return;
      const current = task.scheduled_hour
        ? Number(task.scheduled_hour.slice(0, 2))
        : null;
      hourNum = h !== current ? h : undefined;
    }
    const trimmedTitle = title.trim();
    const trimmedNotes = notes.trim();
    patchMut.mutate(
      {
        taskId: task.id,
        body: {
          title:
            trimmedTitle && trimmedTitle !== task.title ? trimmedTitle : undefined,
          scheduled_hour: hourNum,
          is_draft: isDraft !== task.is_draft ? isDraft : undefined,
          notes:
            trimmedNotes !== (task.notes ?? "")
              ? trimmedNotes || null
              : undefined,
        },
      },
      { onSuccess: () => onDone() },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="space-y-1">
        <label
          htmlFor={`edit-title-${task.id}`}
          className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium"
        >
          Başlık
        </label>
        <input
          id={`edit-title-${task.id}`}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          maxLength={200}
          className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label
            htmlFor={`edit-hour-${task.id}`}
            className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium"
          >
            Saat (0-23, boş = saat yok)
          </label>
          <input
            id={`edit-hour-${task.id}`}
            type="number"
            min={0}
            max={23}
            value={hour}
            onChange={(e) => setHour(e.target.value)}
            placeholder="—"
            className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm font-mono tabular-nums text-center focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="flex items-end pb-1.5">
          <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={isDraft}
              onChange={(e) => setIsDraft(e.target.checked)}
              className="size-4 rounded border-input"
            />
            <span>Taslak (öğrenci görmesin)</span>
          </label>
        </div>
      </div>
      <div className="space-y-1">
        <label
          htmlFor={`edit-notes-${task.id}`}
          className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium"
        >
          Not (opsiyonel)
        </label>
        <textarea
          id={`edit-notes-${task.id}`}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          maxLength={500}
          className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
      <div className="flex items-center justify-end gap-2 pt-2">
        <button
          type="button"
          onClick={onDone}
          disabled={patchMut.isPending}
          className="px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-muted transition"
        >
          İptal
        </button>
        <button
          type="submit"
          disabled={patchMut.isPending}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-foreground text-background text-sm font-medium hover:bg-foreground/90 disabled:opacity-50 transition"
        >
          {patchMut.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : null}
          Kaydet
        </button>
      </div>
    </form>
  );
}

function parseISO(iso: string): { y: number; m: number; d: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  return { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) };
}
