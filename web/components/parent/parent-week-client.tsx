"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  ChevronsRight,
  Info,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getParentStudentWeek, parentKeys } from "@/lib/api/parent";
import type {
  ParentWeekDay,
  ParentWeekResponse,
  ParentWeekTask,
} from "@/lib/types/parent";

interface Props {
  initial: ParentWeekResponse;
  studentId: number;
  startParam: string | null;
}

const TR_WEEKDAYS = [
  "Pazartesi",
  "Salı",
  "Çarşamba",
  "Perşembe",
  "Cuma",
  "Cumartesi",
  "Pazar",
];

const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

const TASK_TYPE_LABELS: Record<string, string> = {
  test: "Test",
  video: "Video",
  ozet: "Özet",
  tekrar: "Tekrar",
  konu: "Konu",
  deneme: "Deneme",
};

/**
 * Haftalık program (read-only) — Jinja `student_week.html` feature parity.
 *
 * Gün accordion: planlanan/tamamlanan oran ratio ile gün şeridi renkli.
 * Task satırı subject_id hash → tonal background. book_items birden fazla
 * ise <ul> ile alt liste, tekse inline.
 */
export function ParentWeekClient({ initial, studentId, startParam }: Props) {
  const q = useQuery<ParentWeekResponse>({
    queryKey: parentKeys.studentWeek(studentId, startParam),
    queryFn: () => getParentStudentWeek(studentId, startParam),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href={`/parent/students/${studentId}`}
            className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            {data.student.full_name}
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
            7 Günlük Program
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            {formatRange(data.start, data.end)}
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link
              href={`/parent/students/${studentId}/week?start=${data.prev_start}`}
            >
              <ChevronLeft className="size-4" aria-hidden />
              7 gün
            </Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href={`/parent/students/${studentId}/week`}>Bu hafta</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link
              href={`/parent/students/${studentId}/week?start=${data.next_start}`}
            >
              7 gün
              <ChevronsRight className="size-4" aria-hidden />
            </Link>
          </Button>
        </div>
      </header>

      <div className="space-y-3">
        {data.days.map((day) => (
          <DayAccordion key={day.date} day={day} />
        ))}
      </div>

      <div className="rounded-md border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground flex items-start gap-2">
        <Info className="size-4 shrink-0 mt-0.5 text-[#117A86]" aria-hidden />
        <p className="leading-relaxed">
          Bu görünüm salt-okunurdur. Görevler öğretmen tarafından planlanır,
          öğrenci tarafından tamamlandı olarak işaretlenir.
        </p>
      </div>
    </div>
  );
}

function DayAccordion({ day }: { day: ParentWeekDay }) {
  const [open, setOpen] = React.useState(day.task_count > 0);
  const ratio = day.planned_total > 0
    ? day.completed_total / day.planned_total
    : 0;
  const dayTone =
    day.planned_total === 0
      ? "text-muted-foreground"
      : ratio >= 0.8
        ? "text-emerald-700"
        : ratio >= 0.4
          ? "text-amber-700"
          : "text-rose-700";

  const isoDate = new Date(day.date);
  const dd = isoDate.getDate();
  const monthLabel = TR_MONTHS[isoDate.getMonth()];

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-5 py-3 flex items-center justify-between hover:bg-muted/50 transition-colors text-left"
        aria-expanded={open}
      >
        <div className="flex items-baseline gap-3">
          <span className="font-semibold">{TR_WEEKDAYS[day.weekday]}</span>
          <span className="text-sm text-muted-foreground">
            {dd} {monthLabel}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {day.task_count > 0 ? (
            <>
              <span className="text-muted-foreground">
                {day.task_count} görev
              </span>
              {day.planned_total > 0 && (
                <>
                  <span className="text-muted-foreground/60">·</span>
                  <span className={cn("font-semibold tabular-nums", dayTone)}>
                    {day.completed_total}/{day.planned_total} test
                  </span>
                </>
              )}
            </>
          ) : (
            <span className="text-muted-foreground italic">boş</span>
          )}
          <ChevronDown
            className={cn(
              "size-4 transition-transform shrink-0",
              open ? "rotate-180" : undefined,
            )}
            aria-hidden
          />
        </div>
      </button>

      {open && (
        <>
          {day.tasks.length > 0 ? (
            <ul className="divide-y divide-border border-t border-border">
              {day.tasks.map((t) => (
                <TaskRow key={t.id} task={t} />
              ))}
            </ul>
          ) : (
            <p className="px-5 py-3 text-sm text-muted-foreground italic border-t border-border">
              Bu güne görev planlanmamış.
            </p>
          )}
        </>
      )}
    </Card>
  );
}

function TaskRow({ task }: { task: ParentWeekTask }) {
  const firstSubjId = task.book_items[0]?.subject_id;
  const hue = firstSubjId != null ? (firstSubjId * 67) % 360 : null;
  const isCompleted = task.status === "completed";
  const isPartial = task.status === "partial";
  const typeLabel = task.type
    ? TASK_TYPE_LABELS[task.type] ?? task.type
    : null;
  const single = task.book_items.length === 1 ? task.book_items[0] : null;

  return (
    <li
      className="px-5 py-2.5 border-l-4"
      style={
        hue != null
          ? {
              // Düşük-opaklık tint — kart zemininin üzerine biner; metin tema
              // token'ı (text-foreground) hem açık hem koyu temada okunur.
              // (Opak hsl 98% sabit-açık zemindi → koyu temada beyaz metin kaybı.)
              background: `hsla(${hue}, 65%, 50%, 0.08)`,
              borderLeftColor: `hsl(${hue}, 60%, 55%)`,
            }
          : { borderLeftColor: "transparent" }
      }
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {task.book_items[0]?.subject_name && hue != null && (
              <span
                className="text-[10px] uppercase tracking-wide font-semibold px-1.5 py-0.5 rounded"
                style={{
                  background: `hsl(${hue}, 70%, 90%)`,
                  color: `hsl(${hue}, 60%, 25%)`,
                }}
              >
                {task.book_items[0].subject_name}
              </span>
            )}
            {typeLabel && (
              <span className="text-[10px] uppercase tracking-wide bg-muted text-foreground/80 px-1.5 py-0.5 rounded">
                {typeLabel}
              </span>
            )}
            <span className="text-sm font-medium">{task.title}</span>
            {isCompleted && (
              <span className="text-xs text-emerald-600">✓ tamamlandı</span>
            )}
            {isPartial && (
              <span className="text-xs text-amber-600">kısmen</span>
            )}
          </div>

          {single ? (
            <div className="text-xs text-muted-foreground mt-0.5">
              {single.book_name} · {single.section_label}
              {single.topic_name && ` (${single.topic_name})`}
              <span className="ml-2 font-medium text-foreground tabular-nums">
                {single.completed_count}/{single.planned_count}
              </span>
            </div>
          ) : task.book_items.length > 1 ? (
            <ul className="mt-1 text-xs text-muted-foreground space-y-0.5">
              {task.book_items.map((it, idx) => (
                <li key={idx}>
                  <ChevronRight
                    className="inline size-3 align-middle mr-0.5"
                    aria-hidden
                  />
                  {it.book_name} — {it.section_label}
                  {it.topic_name && (
                    <span className="text-muted-foreground/70">
                      {" "}
                      ({it.topic_name})
                    </span>
                  )}
                  :{" "}
                  <strong className="tabular-nums text-foreground">
                    {it.completed_count}/{it.planned_count}
                  </strong>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function formatRange(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const sd = start.getDate();
  const sm = TR_MONTHS[start.getMonth()];
  const ed = end.getDate();
  const em = TR_MONTHS[end.getMonth()];
  const ey = end.getFullYear();
  return `${sd} ${sm} – ${ed} ${em} ${ey}`;
}
