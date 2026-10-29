"use client";

/**
 * Öğrenci detayı → "Program geçmişi" sekmesi (2026-10-22). Gün gün haftalar SALT OKUNUR
 * açılır (hafta ızgarası + gün ayrıntısı; taşı/sil/düzenle yok), havuz dönemleri mevcut
 * dönem penceresinde. Öğrenci havuza geçince kapanan hafta editörünün geçmiş karşılığı.
 */
import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { History, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { getStudentAllSubjects, getTeacherStudentWeek, teacherKeys } from "@/lib/api/teacher";
import { getPoolPeriodDetail, poolPeriodDetailKey } from "@/lib/api/pool";
import { getTeacherProgramHistory, programHistoryKeys, type HistoryWeek } from "@/lib/api/program-history";
import type { TeacherStudentWeekDay, TeacherTask } from "@/lib/types/teacher";
import { PoolPeriodDialog } from "@/components/shared/pool-period-dialog";
import { ProgramHistoryTimeline } from "@/components/shared/program-history-timeline";
import { WeekGrid } from "@/components/teacher/weekly-plan/week-grid";

export function ProgramHistoryPanel({ studentId, studentName }: { studentId: number; studentName?: string }) {
  const q = useQuery({
    queryKey: programHistoryKeys.teacher(studentId),
    queryFn: () => getTeacherProgramHistory(studentId),
  });
  const [periodId, setPeriodId] = React.useState<number | null>(null);

  return (
    <div className="space-y-4" data-section="teacher:program-history">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
            <History className="size-4" aria-hidden /> Program geçmişi
          </h2>
          <p className="text-sm text-muted-foreground">
            Gün gün haftalar ve havuz dönemleri aynı çizelgede. Hafta açılınca salt okunur görünür;
            düzenleme yalnız güncel programda yapılır.
          </p>
        </div>
        {q.data && (
          <Link href={q.data.program_mode === "havuz" ? `/teacher/students/${studentId}/pool` : `/teacher/students/${studentId}/week`}
                className="rounded-md bg-cyan-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-cyan-800">
            {q.data.program_mode === "havuz" ? "Güncel havuza git" : "Güncel haftaya git"}
          </Link>
        )}
      </div>
      {q.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Yükleniyor…</p>
      ) : q.isError || !q.data ? (
        <p className="text-sm text-rose-700">Geçmiş yüklenemedi.</p>
      ) : (
        <ProgramHistoryTimeline
          data={q.data}
          onOpenPeriod={setPeriodId}
          renderWeekDetail={(w) => <ReadonlyWeek studentId={studentId} week={w} />}
        />
      )}
      <PoolPeriodDialog open={periodId != null} onOpenChange={(v) => { if (!v) setPeriodId(null); }}
                        studentName={studentName}
                        queryKey={poolPeriodDetailKey(studentId, periodId ?? 0)}
                        queryFn={() => getPoolPeriodDetail(studentId, periodId!)} />
    </div>
  );
}

function ReadonlyWeek({ studentId, week }: { studentId: number; week: HistoryWeek }) {
  const q = useQuery({
    queryKey: [...teacherKeys.studentWeek(studentId, week.start), "range", week.end] as const,
    queryFn: () => getTeacherStudentWeek(studentId, week.start, null, week.end),
  });
  const subj = useQuery({
    queryKey: teacherKeys.studentAllSubjects(studentId),
    queryFn: () => getStudentAllSubjects(studentId),
    staleTime: 60_000,
  });
  const [openDate, setOpenDate] = React.useState<string | null>(null);
  if (q.isLoading) return <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Hafta yükleniyor…</p>;
  if (!q.data) return <p className="text-sm text-rose-700">Hafta yüklenemedi.</p>;
  const days = q.data.days.filter((d) => d.date >= week.start && d.date <= week.end);
  const day = days.find((d) => d.date === openDate) ?? null;
  return (
    <div className="space-y-3" data-testid="history-week-detail">
      <WeekGrid studentId={studentId} days={days} subjects={(subj.data?.items ?? []).map((s) => ({ id: s.id, name: s.name }))} readOnly
                title="Hafta (salt okunur)" openDate={openDate} onOpenDay={setOpenDate} />
      {day ? <ReadonlyDay day={day} /> : (
        <p className="text-xs text-muted-foreground">Bir güne tıkla: görevler ve sonuçları altta açılır.</p>
      )}
    </div>
  );
}

const STATUS: Record<string, { label: string; cls: string }> = {
  completed: { label: "Tamamlandı", cls: "bg-emerald-700 text-white" },
  partial: { label: "Kısmen", cls: "bg-amber-600 text-white" },
  pending: { label: "Yapılmadı", cls: "bg-slate-600 text-white" },
};

function itemLine(t: TeacherTask) {
  return t.items.map((it) => {
    const unit = it.unit === "sayfa" ? "sayfa" : it.unit === "soru" ? "soru" : it.exam_kind ? "deneme" : "test";
    const where = [it.book_name, it.section_label ?? it.topic_name].filter(Boolean).join(" — ");
    const dyb = it.correct_count != null || it.wrong_count != null
      ? ` · ${it.correct_count ?? 0}D ${it.wrong_count ?? 0}Y ${it.blank_count ?? 0}B` : "";
    return { key: it.id, text: `${where}: ${it.completed_count}/${it.planned_count} ${unit}${dyb}` };
  });
}

function ReadonlyDay({ day }: { day: TeacherStudentWeekDay }) {
  return (
    <div className="rounded-lg border bg-card" data-testid="history-day">
      <div className="flex items-baseline justify-between border-b px-3 py-2">
        <span className="text-sm font-semibold text-foreground">{day.dow_label} · {day.date.split("-").reverse().join(".")}</span>
        <span className="text-xs text-muted-foreground">{day.tasks.length} görev</span>
      </div>
      {day.tasks.length === 0 ? (
        <p className="px-3 py-3 text-sm text-muted-foreground">Bu gün görev yok.</p>
      ) : (
        <ul className="divide-y">
          {day.tasks.map((t) => {
            const st = STATUS[t.status] ?? STATUS.pending;
            return (
              <li key={t.id} className="px-3 py-2">
                <div className="flex flex-wrap items-start gap-2">
                  <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold", st.cls)}>{st.label}</span>
                  <span className="text-sm text-foreground">{t.title}</span>
                  {t.is_draft && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-900">Taslak</span>}
                </div>
                {t.items.length > 0 && (
                  <ul className="mt-1 space-y-0.5 pl-1 text-xs text-muted-foreground">
                    {itemLine(t).map((l) => <li key={l.key}>{l.text}</li>)}
                  </ul>
                )}
                {t.solved_count ? <p className="mt-0.5 text-xs text-muted-foreground">Öğrenci {t.solved_count} soru çözdü</p> : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
