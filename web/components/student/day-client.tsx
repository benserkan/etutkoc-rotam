"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Clock, Moon, Sun, Sunrise } from "lucide-react";

import { getStudentDay, studentKeys } from "@/lib/api/student";
import type { StudentDayResponse, StudentTask, TaskPeriod } from "@/lib/types/student";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";

import { DayHeader } from "./day-header";
import { ResourceSidebar } from "./resource-sidebar";
import { TaskCard } from "./task-card";
import { ProjectionCard } from "./projection-card";
import { CommModal, type CommMode } from "./comm-modal";

interface Props {
  initial: StudentDayResponse;
}

/**
 * /student/day kalbi — Server Component'in initialData'sını TanStack Query
 * cache'ine seed ederek hydrate eder; sonrasında tüm interaktif state buradan
 * yönetilir.
 *
 * Sözleşme:
 *   - useQuery key: studentKeys.day(date) — invalidate ile uyumlu (R-006).
 *   - Mutation hook'ları setQueryData ile optimistic; refetch invalidate sonrası
 *     gerçek backend snapshot'ı yazar.
 *   - URL ?date= query'si Server Component'in initialData'sını besler; bu
 *     bileşen yine de useQuery ile aynı date'i talep eder (anlık state).
 */
export function DayClient({ initial }: Props) {
  const dateIso = initial.date;

  const q = useQuery<StudentDayResponse>({
    queryKey: studentKeys.day(dateIso),
    queryFn: () => getStudentDay(dateIso),
    initialData: initial,
    staleTime: 60_000,
  });

  // Comm modal state — task-card menülerinden açılır
  const [comm, setComm] = React.useState<
    | { mode: Exclude<CommMode, "add">; task: StudentTask }
    | { mode: "add" }
    | null
  >(null);

  function openComm(mode: Exclude<CommMode, "add">, task: StudentTask) {
    setComm({ mode, task });
  }

  if (q.isError) {
    return (
      <ErrorState
        description={q.error instanceof Error ? q.error.message : undefined}
        onRetry={() => q.refetch()}
      />
    );
  }
  if (!q.data) {
    return <LoadingState fullPage />;
  }
  const day = q.data;

  const showProjection =
    day.projection && (day.is_today || day.is_future) && !day.is_past;

  return (
    <div className="space-y-4">
      <DayHeader day={day} onRequestAdd={() => setComm({ mode: "add" })} />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6 items-start">
        {/* Sol kolon: görev listesi + projeksiyon */}
        <div className="space-y-3 min-w-0">
          {showProjection && day.projection ? (
            <ProjectionCard projection={day.projection} />
          ) : null}

          {day.tasks.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-card px-4 py-10 text-center text-sm text-muted-foreground">
              <p className="font-medium">Bu güne henüz görev yok.</p>
              {day.is_past ? (
                <p className="mt-1 text-xs">Geçmiş bir gün — koçunla iletişime geç.</p>
              ) : (
                <p className="mt-1 text-xs">
                  Yukarıdaki <span className="font-medium">Yeni görev iste</span> butonu ile öneride bulunabilirsin.
                </p>
              )}
            </div>
          ) : (
            <PeriodGroupedTasks tasks={day.tasks} dateIso={dateIso} openComm={openComm} />
          )}
        </div>

        {/* Sağ kolon: kaynak sidebar — lg ve üstü sticky */}
        <ResourceSidebar data={day.sidebar} />
      </div>

      {/* Comm modal — tek instance, mode prop'a göre içerik */}
      {comm ? (
        comm.mode === "add" ? (
          <CommModal
            open
            onOpenChange={(o) => !o && setComm(null)}
            mode="add"
            sidebar={day.sidebar}
            dateIso={dateIso}
            targetDate={dateIso}
          />
        ) : (
          <CommModal
            open
            onOpenChange={(o) => !o && setComm(null)}
            mode={comm.mode}
            task={comm.task}
            sidebar={day.sidebar}
            dateIso={dateIso}
          />
        )
      ) : null}
    </div>
  );
}

// =============================================================================
// PeriodGroupedTasks — M6: koç period atadıysa görevleri 3 (veya 4) bölüme ayır.
// Hiçbir görevde period yoksa tek liste (geriye uyum, sade görünüm).
// =============================================================================

interface PeriodGroupedTasksProps {
  tasks: StudentTask[];
  dateIso: string;
  openComm: (mode: Exclude<CommMode, "add">, task: StudentTask) => void;
}

const PERIOD_META: Array<{
  key: TaskPeriod | null;
  label: string;
  Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  toneText: string;
  toneBorder: string;
}> = [
  { key: "morning", label: "Sabah", Icon: Sunrise, toneText: "text-amber-700", toneBorder: "border-amber-200" },
  { key: "noon", label: "Öğle", Icon: Sun, toneText: "text-orange-700", toneBorder: "border-orange-200" },
  { key: "evening", label: "Akşam", Icon: Moon, toneText: "text-indigo-700", toneBorder: "border-indigo-200" },
  { key: null, label: "Saatsiz", Icon: Clock, toneText: "text-muted-foreground", toneBorder: "border-border" },
];

function PeriodGroupedTasks({ tasks, dateIso, openComm }: PeriodGroupedTasksProps) {
  // Koç hiç period atamadıysa tek liste — sade UX (geriye uyum).
  const anyPeriod = tasks.some((t) => t.period != null);
  if (!anyPeriod) {
    return (
      <>
        {tasks.map((t) => (
          <TaskCard key={t.id} task={t} dateIso={dateIso} onOpenComm={openComm} />
        ))}
      </>
    );
  }
  return (
    <div className="space-y-4">
      {PERIOD_META.map(({ key, label, Icon, toneText, toneBorder }) => {
        const group = tasks.filter((t) => t.period === key);
        if (group.length === 0) return null;
        return (
          <section key={key ?? "none"}>
            <header className={`flex items-center gap-2 mb-2 pb-1 border-b ${toneBorder}`}>
              <Icon className={`size-4 ${toneText}`} aria-hidden />
              <h3 className={`text-xs uppercase tracking-wider font-semibold ${toneText}`}>
                {label}
              </h3>
              <span className="text-[11px] text-muted-foreground tabular-nums">
                · {group.length} görev
              </span>
            </header>
            <div className="space-y-2">
              {group.map((t) => (
                <TaskCard key={t.id} task={t} dateIso={dateIso} onOpenComm={openComm} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
