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
  CalendarRange,
  Moon,
  Pencil,
  Plus,
  Rocket,
  Sun,
  Sunrise,
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
  useSpreadTask,
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
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
  video: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
  ozet: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  tekrar: "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-500/10 dark:border-violet-500/30 dark:text-violet-200",
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
  // Devret sürükle-bırak: bir zaman dilimi (periyot) başlığına bırakılınca o
  // periyoda taşı (week-board day-level drop period=null fallback'tir).
  onCarryoverDrop?: (period: TaskPeriod | null, taskId: number) => void;
  // "Haftaya yay" dialoğu için haftanın günleri (rutin görev — 2026-08-12)
  weekDays?: TeacherStudentWeekDay[];
}

export function WeekDayCard({
  studentId,
  day,
  subjects,
  weekDays,
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
  onCarryoverDrop,
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

      <TaskList
        studentId={studentId}
        day={day}
        subjects={subjects}
        weekDays={weekDays}
        onCarryoverDrop={onCarryoverDrop}
        onFocusSubject={onFocusSubject}
      />

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
// görevlerinde ders backend dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200'den gelmez → başlık "{Ders} · {içerik}" parse edilir.
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
  // Etkinlik (kalemsiz) VEYA blok (bloğu silinmiş dahil) → "{Ders} · {içerik}" parse.
  if (task.items.length === 0 || task.work_block_id != null || task.block_detached) {
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

/**
 * Periyot BÖLGESİ görsel kimliği (2026-09-07 yeniden tasarım).
 *
 * ÖLÇÜLDÜ: eski hâlde periyot başlığı ↔ kart zemini ΔE 2,8 (insan gözü için
 * "aynı renk"), ders başlığı ↔ periyot başlığı ΔE 0,0. Üç hiyerarşi katmanı
 * aynı gri şeritti; koç "sabah-öğle-akşam ayrılmıyor" dedi — haklıydı.
 *
 * İLKE: her katmana FARKLI görsel kanal. Periyot = BÖLGE (zemin + çerçeve +
 * koyu başlık şeridi + günün saatine uygun ikon), ders = RENK (satır rayı +
 * soluk satır zemini), görev = SATIR. Renk iki katmana birden verilmez.
 *
 * Tonlar günün saatine göre ANLAMLI (kullanıcı kararı): sabah sıcak/açık,
 * öğle nötr/parlak, akşam serin/koyu. Düşük doygunluk → ders renkleriyle
 * yarışmaz ama bölgeyi hissettirir. Hedef bölge ↔ kart ΔE ≥ 10.
 * Tonlu zemin → koyu tema için dark: varyantı ZORUNLU (kontrast kuralı).
 */
const PERIOD_ZONE: Record<
  string,
  { Icon: typeof Sun; zone: string; head: string; headText: string; hint: string }
> = {
  morning: {
    Icon: Sunrise,
    zone: "bg-orange-100 border-orange-300 dark:bg-orange-500/[0.10] dark:border-orange-500/30",
    head: "bg-orange-900 dark:bg-orange-950",
    headText: "text-orange-50",
    hint: "Sabaha ekle",
  },
  noon: {
    Icon: Sun,
    zone: "bg-yellow-100 border-yellow-300 dark:bg-yellow-500/[0.10] dark:border-yellow-500/30",
    head: "bg-yellow-700 dark:bg-yellow-900",
    headText: "text-yellow-50",
    hint: "Öğleye ekle",
  },
  evening: {
    Icon: Moon,
    zone: "bg-indigo-100 border-indigo-300 dark:bg-indigo-500/[0.12] dark:border-indigo-500/30",
    head: "bg-indigo-950 dark:bg-indigo-950",
    headText: "text-indigo-50",
    hint: "Akşama ekle",
  },
  none: {
    Icon: Clock,
    zone: "bg-muted/40 border-border",
    head: "bg-slate-700 dark:bg-slate-800",
    headText: "text-slate-50",
    hint: "Zamansız ekle",
  },
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

function PeriodHeader({
  pkey,
  count,
  onCarryoverDrop,
}: {
  pkey: string;
  count: number;
  onCarryoverDrop?: (period: TaskPeriod | null, taskId: number) => void;
}) {
  const [over, setOver] = React.useState(false);
  const CARRY_MIME = "text/x-carryover-task";
  const periodValue: TaskPeriod | null =
    pkey === "morning" || pkey === "noon" || pkey === "evening"
      ? (pkey as TaskPeriod)
      : null;
  const droppable = !!onCarryoverDrop;
  const PZ = PERIOD_ZONE[pkey] ?? PERIOD_ZONE.none;
  return (
    <div
      onDragOver={
        droppable
          ? (e) => {
              if (e.dataTransfer.types.includes(CARRY_MIME)) {
                e.preventDefault();
                e.stopPropagation();
                e.dataTransfer.dropEffect = "copy";
                if (!over) setOver(true);
              }
            }
          : undefined
      }
      onDragLeave={droppable ? () => setOver(false) : undefined}
      onDrop={
        droppable
          ? (e) => {
              const raw = e.dataTransfer.getData(CARRY_MIME);
              setOver(false);
              if (!raw) return;
              e.preventDefault();
              e.stopPropagation(); // gün-level drop tetiklenmesin (çift taşıma yok)
              const tid = Number(raw);
              if (Number.isFinite(tid)) onCarryoverDrop?.(periodValue, tid);
            }
          : undefined
      }
      className={cn(
        // Koyu başlık şeridi: bölgenin en üst katmanı, kart zemininden
        // belirgin ayrışır (eski gri şerit ΔE 2,8'di). Yuvarlak üst köşe
        // bölge çerçevesiyle birleşir.
        "flex items-center gap-2 px-3 py-1.5 rounded-t-md transition",
        PZ.head,
        over && "ring-2 ring-inset ring-amber-300",
      )}
    >
      <PZ.Icon className={cn("size-3.5 flex-shrink-0", PZ.headText)} aria-hidden />
      <span className={cn("text-[11.5px] uppercase tracking-wider font-bold", PZ.headText)}>
        {PERIOD_LABELS[pkey] ?? PERIOD_LABELS.none}
      </span>
      {over ? (
        <span className="text-[10px] font-semibold text-amber-200">→ buraya bırak</span>
      ) : null}
      <span className={cn("ml-auto text-[10.5px] tabular-nums opacity-80", PZ.headText)}>
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
  onCarryoverDrop,
  weekDays,
  onFocusSubject,
}: {
  studentId: number;
  day: TeacherStudentWeekDay;
  subjects: SubjectRef[];
  onCarryoverDrop?: (period: TaskPeriod | null, taskId: number) => void;
  weekDays?: TeacherStudentWeekDay[];
  onFocusSubject?: (subjectId: number | null) => void;
}) {
  // Periyoda DOĞRUDAN ekleme (2026-09-07): her bölgenin altında "+ Sabaha
  // ekle". Açılan form o periyot ön-seçili gelir → koç çip seçmez (3 tık).
  const [openAddPk, setOpenAddPk] = React.useState<string | null>(null);
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

  // Fare/pointer'ın SON konumu — bırakma anında hangi bölgede olduğunu
  // bulmak için. dnd-kit'in activatorEvent+delta hesabı aktivasyon eşiğine
  // göre kayabiliyor; gerçek konum tek doğruluk kaynağı.
  const lastPointer = React.useRef<{ x: number; y: number } | null>(null);
  React.useEffect(() => {
    function onMove(ev: PointerEvent) {
      lastPointer.current = { x: ev.clientX, y: ev.clientY };
    }
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => document.removeEventListener("pointermove", onMove);
  }, []);

  // Bırakma noktasının HANGİ BÖLGEDE olduğunu koordinatla bul (2026-09-07).
  // dnd-kit `over` = en yakın SATIR merkezi; sıralama animasyonu sırasında
  // satırlar kayınca fare Öğle bölgesinde olsa da `over` Akşam satırına
  // düşebiliyor → görev yanlış periyoda gidiyordu (tarayıcı testinde yakalandı:
  // bırakılan bölge Öğle, kaydedilen periyot evening). Bölge tasarımında doğru
  // davranış: fare hangi bölgenin içinde bırakıldıysa o periyot kazanır.
  const zoneAtPointer = React.useCallback((x: number, y: number): string | null => {
    // Sürüklenen satır (transform ile fare altında) kendi kaynak bölgesinin
    // DOM çocuğu → elementFromPoint onu yakalarsa yanlış bölge çıkar. Bunun
    // için geometriye bak: fare hangi bölgenin dikdörtgeni içinde?
    const secs = Array.from(
      document.querySelectorAll<HTMLElement>("section[data-period]"),
    );
    for (const sec of secs) {
      const r = sec.getBoundingClientRect();
      if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) {
        return sec.dataset.period ?? null;
      }
    }
    return null;
  }, []);

  function onDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const activeTask = tasksById.get(Number(active.id));
    const overTask = tasksById.get(Number(over.id));
    if (!activeTask || !overTask) return;

    // Hedef periyot: önce fare koordinatındaki bölge, yoksa üstüne düşülen satır.
    let targetPk = periodKey(overTask.period);
    if (usePeriods && lastPointer.current) {
      const z = zoneAtPointer(lastPointer.current.x, lastPointer.current.y);
      if (z) targetPk = z;
    }

    // (1) Farklı periyot bölümüne bırakıldı → görevin periyodunu hedef bölüme TAŞI
    // (mıknatıs: o periyodun ders grubuna girer; sayfa yenilense de kalıcı).
    if (usePeriods && periodKey(activeTask.period) !== targetPk) {
      const targetPeriod: TaskPeriod | null =
        targetPk === "none" ? null : (targetPk as TaskPeriod); // null = Zaman belirtilmemiş
      const prevPeriod = activeTask.period ?? null;
      // OPTİMİSTİK: week cache'inde period'u hemen güncelle → editör + Hafta
      // Izgarası ANINDA yeni periyoda taşır (refetch beklenmez). Hata → geri al.
      const setPeriodInCache = (p: TaskPeriod | null) =>
        qc.setQueriesData<TeacherStudentWeekResponse>(
          { queryKey: ["teacher", "me", "students", String(studentId), "week"] },
          // DİKKAT: prefix, hafta notları gibi ALT sorguları da yakalar
          // ([...studentWeek, "notes"] — verisi dizi). days olmayan cache'e
          // dokunma; yoksa updater throw eder ve PATCH hiç atılmaz
          // (2026-08-12 saha bug'ı: taşıma görünür ama kaydedilmezdi).
          (prev) =>
            prev && Array.isArray(prev.days)
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
        { taskId: activeTask.id, body: { period: targetPeriod ?? "" } },
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
        {usePeriods ? (
          // PERİYOT BÖLGELERİ (2026-09-07): her periyot ayrı çerçeveli blok —
          // zemin tonu günün saatine göre, koyu başlık şeridi, bölgeler arası
          // boşluk. Ders başlıkları KALDIRILDI: eski hâlde periyot içinde
          // derse göre gruplama periyot başına ders başına 1 görev üretiyor,
          // 9 görev için 9 ders başlığı çiziliyordu (kartın %30'u başlıktı).
          // Ders bilgisi artık satırın kendisinde: kalın ders adı + renkli
          // ray + soluk satır zemini. Sıra yine derse göre (mıknatıs korunur).
          <div className="space-y-3 px-3 pt-3 pb-1">
            {(["morning", "noon", "evening", "none"] as const).map((pk) => {
              const ids = orderedIds.filter((id) => {
                const t = tasksById.get(id);
                return t ? periodKey(t.period) === pk : false;
              });
              if (ids.length === 0) return null;
              const PZ = PERIOD_ZONE[pk];
              return (
                <section
                  key={pk}
                  // @container: satır içindeki kitap adı KABIN genişliğine göre
                  // gizlenir (viewport'a göre değil — dar sağ panelde yanlış karar)
                  className={cn("@container rounded-md border overflow-hidden", PZ.zone)}
                  aria-label={PERIOD_LABELS[pk]}
                  data-period={pk}
                >
                  <PeriodHeader
                    pkey={pk}
                    count={periodCounts.get(pk) ?? ids.length}
                    onCarryoverDrop={onCarryoverDrop}
                  />
                  <div className="divide-y divide-black/[0.06] dark:divide-white/[0.06]">
                    {ids.map((id) => {
                      const task = tasksById.get(id);
                      if (!task) return null;
                      return (
                        <SortableTaskRow
                          key={id}
                          studentId={studentId}
                          dayDate={day.date}
                          task={task}
                          subjects={subjects}
                          weekDays={weekDays}
                        />
                      );
                    })}
                  </div>
                  {openAddPk === pk ? (
                    <div className="border-t border-black/[0.06] dark:border-white/[0.06] bg-card">
                      <AddTaskForm
                        studentId={studentId}
                        dayDate={day.date}
                        onFocusSubject={onFocusSubject ?? (() => {})}
                        onAfterAdd={() => {}}
                        initialPeriod={pk === "none" ? null : (pk as TaskPeriod)}
                      />
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setOpenAddPk(pk)}
                      className="flex w-full items-center gap-1.5 px-3 py-1.5 text-[11.5px] text-slate-600 hover:text-slate-900 hover:bg-slate-500/10 dark:text-slate-300 dark:hover:text-slate-100 transition"
                    >
                      <Plus className="size-3" aria-hidden />
                      {PZ.hint}
                    </button>
                  )}
                </section>
              );
            })}
          </div>
        ) : (
          // Periyotsuz gün: tek liste, ders sırasıyla (Katman 1). Ders
          // başlığı burada da yok — ders satırın kendisinde okunur.
          <div className="@container divide-y divide-border/60 border-t border-border">
            {orderedIds.map((id) => {
              const task = tasksById.get(id);
              if (!task) return null;
              return (
                <SortableTaskRow
                  key={id}
                  studentId={studentId}
                  dayDate={day.date}
                  task={task}
                  subjects={subjects}
                  weekDays={weekDays}
                />
              );
            })}
          </div>
        )}
      </SortableContext>
    </DndContext>
  );
}

function SortableTaskRow({
  studentId,
  dayDate,
  task,
  subjects,
  weekDays,
}: {
  studentId: number;
  dayDate: string;
  task: TeacherTask;
  subjects: SubjectRef[];
  weekDays?: TeacherStudentWeekDay[];
}) {
  const deleteMut = useDeleteTask(studentId, dayDate);
  const [editOpen, setEditOpen] = React.useState(false);
  const [spreadOpen, setSpreadOpen] = React.useState(false);
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
  if (!primarySubjectName && (task.items.length === 0 || task.work_block_id != null || task.block_detached)) {
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

  // DERS RENGİ SATIR ZEMİNİNDE (2026-09-07): eski hâlde renk yalnız 10px'lik
  // rozetteydi, satır zeminleri dersten bağımsız AYNIYDI (ölçüm: Matematik ↔
  // Fizik satırı ΔE 0,0). Göz zemini tarar, rozeti OKUR — okumak çabadır.
  // Şimdi ders hue'su ray (%45 doygun) + soluk zemin (%8 alfa) olarak satırda;
  // farklı ders satırları okumadan ayrışır. Blok/deneme kendi tonunu korur.
  // Satır zemini bölge tonunun ÜSTÜNE değil YERİNE çizilir: beyaz taban +
  // ders tonu (%14). Bölge rengi çerçeve + şerit + satırlar arası boşlukta
  // kalır; satırlar kendi zemininde ayrışır (iki ton üst üste = çamur).
  const rowTint = primarySubjectName
    ? `hsl(${hue}, 65%, 91%)`
    : isBlock
      ? "hsl(258, 60%, 95%)"
      : isDeneme
        ? "hsl(239, 60%, 95%)"
        : "hsl(0, 0%, 99%)";
  // Koyu temada açık pastel zemin beyaza yakın parlar → aynı hue'nun koyu tonu.
  const rowTintDark = primarySubjectName
    ? `hsla(${hue}, 45%, 60%, 0.16)`
    : isBlock
      ? "rgba(139, 92, 246, 0.16)"
      : isDeneme
        ? "rgba(99, 102, 241, 0.16)"
        : "rgba(255,255,255,0.03)";
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    "--row-light": rowTint,
    "--row-dark": rowTintDark,
    borderLeftColor:
      primarySubjectName
        ? `hsl(${hue}, 55%, 55%)`
        : isBlock
          ? "#8b5cf6" // violet — serbest blok
          : isDeneme
            ? "#6366f1" // indigo — deneme
            : ACTIVITY_ACCENT[task.type] ?? "transparent",
    opacity: isDragging ? 0.5 : 1,
  } as React.CSSProperties;

  const typeTone =
    TASK_TYPE_TONE[task.type] ?? "bg-muted text-muted-foreground border-border";

  // KOMPAKT BAŞLIK: "Kitap — Bölüm: N test" biçimindeki başlıkta kitap adı
  // çoğu zaman ders adını tekrar eder ("Matematik Soru Bankası"). Ders adı
  // satır başında kalın yazılacağı için başlığı böl: bölüm ana metin, kitap
  // ikincil (soluk). Biçim tutmuyorsa başlık olduğu gibi kalır.
  let primaryText = displayTitle;
  let secondaryText: string | null = null;
  const dash = displayTitle.indexOf(" — ");
  if (dash > 0 && task.items.length === 1 && task.items[0].book_id !== null) {
    secondaryText = displayTitle.slice(0, dash);       // kitap
    primaryText = displayTitle.slice(dash + 3);         // "Bölüm: N test"
    // Kitap adı ders adını tekrar ediyorsa ("Matematik Soru Bankası") ön eki
    // at → "Soru Bankası". Ölçümde ders adı 3 ders için 30 kez yazılıyordu;
    // kaynağı bu tekrardı. Ders adı satırda zaten kalın, bir kez yeter.
    if (primarySubjectName) {
      const plain = primarySubjectName.replace(/^(TYT|AYT|LGS)\s+/i, "");
      for (const pref of [primarySubjectName, plain]) {
        if (pref && secondaryText.toLocaleLowerCase("tr").startsWith(pref.toLocaleLowerCase("tr") + " ")) {
          secondaryText = secondaryText.slice(pref.length + 1);
          break;
        }
      }
    }
  }
  // TEST rozeti gösterilmez: görevlerin %78'i test, her satırda yazmak bilgi
  // değil gürültü. Diğer tipler (video/deneme/blok/diğer) rozetini taşır.
  const showTypeBadge = isBlock || isDeneme || task.type !== "test";

  return (
    <div
      ref={setNodeRef}
      id={`task-${task.id}`}
      className={cn(
        "px-3 py-1.5 flex items-center gap-2.5 border-l-[3px] task-row transition-colors",
        "bg-[var(--row-light)] dark:bg-[var(--row-dark)]",
        "hover:brightness-[0.97] dark:hover:brightness-110",
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
        <div className="flex items-baseline gap-x-2 gap-y-0.5 flex-wrap">
          {primarySubjectName ? (
            <span
              className="text-[13px] font-semibold whitespace-nowrap text-[var(--subj-light)] dark:text-[var(--subj-dark)]"
              style={
                {
                  "--subj-light": `hsl(${hue}, 45%, 32%)`,
                  "--subj-dark": `hsl(${hue}, 60%, 78%)`,
                } as React.CSSProperties
              }
              title={primarySubjectName}
            >
              {primarySubjectName}
            </span>
          ) : null}
          {showTypeBadge ? (
            <span
              className={cn(
                "text-[10px] uppercase tracking-wider font-semibold px-1.5 py-px rounded border self-center",
                isBlock
                  ? "bg-violet-100 text-violet-700 border-violet-300 dark:bg-violet-950/40 dark:text-violet-200 dark:border-violet-800"
                  : isDeneme
                    ? "bg-indigo-100 text-indigo-700 border-indigo-300 dark:bg-indigo-950/40 dark:text-indigo-200 dark:border-indigo-800"
                    : typeTone,
              )}
            >
              {isBlock ? "Blok" : isDeneme ? "Deneme" : (TASK_TYPE_LABELS[task.type] ?? task.type)}
            </span>
          ) : null}
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
          <span className="text-[13px] text-foreground">
            {primaryText}
          </span>
          {task.completed_count > 0 ? (
            <span className="text-xs text-emerald-700 tabular-nums">
              · {task.completed_count}/{task.planned_count}
            </span>
          ) : null}
          {/* Tek kalemli görevde D/Y rozeti — task badge dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200'lerinin yanına inline */}
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
        {secondaryText ? (
          <span
            className="hidden @xl:inline text-[11px] text-muted-foreground truncate max-w-[11rem]"
            title={secondaryText}
          >
            {secondaryText}
          </span>
        ) : null}
        {weekDays && weekDays.length > 1 ? (
          <button
            type="button"
            onClick={() => setSpreadOpen(true)}
            className="inline-flex items-center gap-1 px-1.5 py-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition"
            title="Haftaya yay — bu görevi seçtiğin günlere çoğalt"
            aria-label="Haftaya yay"
          >
            <CalendarRange className="size-3.5" aria-hidden />
          </button>
        ) : null}
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
      {spreadOpen && weekDays ? (
        <SpreadTaskDialog
          open={spreadOpen}
          onOpenChange={setSpreadOpen}
          task={task}
          sourceDate={dayDate}
          weekDays={weekDays}
        />
      ) : null}
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
  const [period, setPeriod] = React.useState<TaskPeriod | null>(
    (task.period as TaskPeriod | null) ?? null,
  );
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
          period,
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
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
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

      <div>
        <span className="text-sm font-medium">Zaman dilimi (gün içi bölüm)</span>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {([
            { k: null, l: "Yok" },
            { k: "morning", l: "Sabah" },
            { k: "noon", l: "Öğle" },
            { k: "evening", l: "Akşam" },
          ] as { k: TaskPeriod | null; l: string }[]).map((p) => (
            <button
              key={p.l}
              type="button"
              onClick={() => setPeriod(p.k)}
              className={cn(
                "rounded-md border px-2.5 py-1 text-xs transition",
                period === p.k
                  ? "border-amber-500 bg-amber-100 font-semibold text-amber-900"
                  : "border-input bg-background hover:bg-muted/50",
              )}
            >
              {p.l}
            </button>
          ))}
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
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200">
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
  const [taskDate, setTaskDate] = React.useState(task.date);
  const [period, setPeriod] = React.useState<TaskPeriod | null>(
    (task.period as TaskPeriod | null) ?? null,
  );
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
    const curPeriod = (task.period as TaskPeriod | null) ?? null;
    patchMut.mutate(
      {
        taskId: task.id,
        body: {
          title:
            trimmedTitle && trimmedTitle !== task.title ? trimmedTitle : undefined,
          date: taskDate && taskDate !== task.date ? taskDate : undefined,
          period: period !== curPeriod ? (period ?? "") : undefined,
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
      <div className="space-y-1">
        <label
          htmlFor={`edit-date-${task.id}`}
          className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium"
        >
          Gün (başka güne taşı)
        </label>
        <input
          id={`edit-date-${task.id}`}
          type="date"
          value={taskDate}
          onChange={(e) => setTaskDate(e.target.value)}
          required
          className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
      <div className="space-y-1">
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">
          Zaman dilimi (gün içi bölüm)
        </span>
        <div className="flex flex-wrap gap-1.5">
          {([
            { k: null, l: "Yok" },
            { k: "morning", l: "Sabah" },
            { k: "noon", l: "Öğle" },
            { k: "evening", l: "Akşam" },
          ] as { k: TaskPeriod | null; l: string }[]).map((p) => (
            <button
              key={p.l}
              type="button"
              onClick={() => setPeriod(p.k)}
              className={cn(
                "rounded-md border px-2.5 py-1 text-xs transition",
                period === p.k
                  ? "border-amber-500 bg-amber-100 font-semibold text-amber-900"
                  : "border-input bg-background hover:bg-muted/50",
              )}
            >
              {p.l}
            </button>
          ))}
        </div>
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


// ---------------------------------------------------------------------------
// "Haftaya yay" — rutin görev dağıtımı (2026-08-12, Hatice önerisi)
// ---------------------------------------------------------------------------

const SPREAD_SKIP_LABELS: Record<string, string> = {
  past_date: "geçmiş gün",
  duplicate: "aynı görev zaten vardı",
  source_exhausted: "kaynakta test kalmadı",
  reserve_failed: "rezerv edilemedi",
  invalid_date: "geçersiz tarih",
};

const DOW_SHORT: Record<string, string> = {
  Pazartesi: "Pzt", Salı: "Sal", Çarşamba: "Çar", Perşembe: "Per",
  Cuma: "Cum", Cumartesi: "Cmt", Pazar: "Paz",
};

function SpreadTaskDialog({
  open,
  onOpenChange,
  task,
  sourceDate,
  weekDays,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  task: TeacherTask;
  sourceDate: string;
  weekDays: TeacherStudentWeekDay[];
}) {
  const spreadMut = useSpreadTask();
  const hasBookItems = task.items.some((it) => it.book_id != null);
  // Varsayılan: kaynak gün + geçmiş günler HARİÇ tüm program günleri seçili.
  const [selected, setSelected] = React.useState<Set<string>>(
    () =>
      new Set(
        weekDays
          .filter((d) => d.date !== sourceDate && !d.is_past)
          .map((d) => d.date),
      ),
  );
  const [continueSections, setContinueSections] = React.useState(true);

  const toggle = (date: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });

  const apply = () => {
    spreadMut.mutate(
      {
        taskId: task.id,
        body: {
          dates: [...selected],
          continue_sections: continueSections,
        },
      },
      {
        onSuccess: (res) => {
          const r = res.data;
          if (r.created.length > 0) {
            toast.success(`${r.created.length} güne yayıldı`, {
              description:
                r.partial.length > 0
                  ? `${r.partial.length} güne kaynaktan kalan kadar konuldu.`
                  : "Kopyalar taslak olarak eklendi — yayınlayınca öğrenci görür.",
            });
          }
          const dupCount = r.skipped.filter((x) => x.reason === "duplicate").length;
          if (dupCount > 0) {
            toast.info(`${dupCount} gün atlandı — aynı görev zaten vardı.`);
          }
          if (r.warning) {
            toast.warning("Kaynak yetmedi", { description: r.warning });
          } else if (r.created.length === 0 && dupCount === 0) {
            const first = r.skipped[0];
            toast.warning("Hiçbir güne eklenemedi", {
              description: first
                ? SPREAD_SKIP_LABELS[first.reason] ?? first.reason
                : undefined,
            });
          }
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarRange className="size-4" aria-hidden />
            Haftaya yay
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{task.title}</span>{" "}
            görevi seçtiğin günlere kopyalanır (taslak olarak — yayınlayınca
            öğrenci görür).
          </p>
          <div className="flex flex-wrap gap-1.5">
            {weekDays.map((d) => {
              const isSource = d.date === sourceDate;
              const disabled = isSource || d.is_past;
              const on = selected.has(d.date);
              return (
                <button
                  key={d.date}
                  type="button"
                  disabled={disabled}
                  onClick={() => toggle(d.date)}
                  className={cn(
                    "px-2.5 py-1.5 rounded-lg border text-xs font-medium transition",
                    disabled
                      ? "border-border text-muted-foreground/50 cursor-not-allowed"
                      : on
                        ? "border-cyan-500 bg-cyan-50 text-cyan-900 dark:bg-cyan-500/15 dark:text-cyan-200"
                        : "border-border text-muted-foreground hover:border-foreground/40",
                  )}
                  title={
                    isSource ? "Kaynak gün" : d.is_past ? "Geçmiş gün" : undefined
                  }
                >
                  {DOW_SHORT[d.dow_label] ?? d.dow_label}
                  {isSource ? " (bu)" : ""}
                </button>
              );
            })}
          </div>
          {hasBookItems ? (
            <label className="flex items-start gap-2 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={continueSections}
                onChange={(e) => setContinueSections(e.target.checked)}
                className="mt-0.5"
              />
              <span>
                Bölüm biterse kitabın <b>sıradaki bölümünden</b> devam et
                <span className="block text-xs text-muted-foreground">
                  Kapalıysa yalnız bu görevdeki bölümün kalanı dağıtılır.
                </span>
              </span>
            </label>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Vazgeç
            </Button>
            <Button
              onClick={apply}
              disabled={selected.size === 0 || spreadMut.isPending}
            >
              {spreadMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              {selected.size} güne yay
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
