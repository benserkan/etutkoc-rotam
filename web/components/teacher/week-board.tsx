"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  FileEdit,
  Loader2,
  Megaphone,
  Microscope,
  Rocket,
} from "lucide-react";

import {
  getStudentSidebar,
  getStudentWeekNotes,
  getTeacherStudentWeek,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  useNotifyParents,
  usePublishWeek,
} from "@/lib/hooks/use-weekly-plan-mutations";
import type {
  SidebarResponse,
  TeacherStudentWeekResponse,
  TeacherWeekNote,
} from "@/lib/types/teacher";
import { Button } from "@/components/ui/button";

import { BookGridModal } from "./weekly-plan/book-grid-modal";
import { WeekDayCard } from "./weekly-plan/week-day-card";
import { WeekNotesCard } from "./weekly-plan/week-notes-card";
import { ResourceSidebar } from "./weekly-plan/resource-sidebar";

/**
 * Öğretmen — haftalık plan ekranı (Paket 3.5a).
 *
 * Jinja `student_week.html` ile parite:
 *  - 2 sütun (xl+): sol açılır günler + sağ sticky Kaynak Durumu
 *  - Üst: navigation + 🔬 Tanı + 🚀 Tüm haftayı yayınla + 📣 Veliye duyur
 *  - Hafta notları (öğrenci de görür, yazdırılan programda çıkar)
 *  - Gün kartı: açılır, ders bazlı rozet özeti, drag-drop görev listesi,
 *    inline +Yeni görev ekle, inline AI öneri paneli
 *  - Sidebar: 3 seviyeli (subject → book → section) reaktif
 */

interface Props {
  studentId: number;
  initial: TeacherStudentWeekResponse;
  initialStart: string;
}

export function WeekBoard({ studentId, initial, initialStart }: Props) {
  const startDate = initial.start_date;
  const weekQ = useQuery<TeacherStudentWeekResponse>({
    queryKey: teacherKeys.studentWeek(studentId, startDate),
    queryFn: () => getTeacherStudentWeek(studentId, startDate),
    initialData: initialStart === startDate ? initial : undefined,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = weekQ.data ?? initial;

  // Hafta notları ayrı query (mutation invalidate hedefi)
  const notesQ = useQuery<TeacherWeekNote[]>({
    queryKey: [
      ...teacherKeys.studentWeek(studentId, startDate),
      "notes",
      data.week_start_anchor,
    ] as const,
    queryFn: () =>
      getStudentWeekNotes(studentId, data.week_start_anchor),
    initialData: data.notes,
    staleTime: 30_000,
  });
  const notes = notesQ.data ?? data.notes;

  // Sidebar focus state — form ders select buraya yazar
  const [focusedSubjectId, setFocusedSubjectId] = React.useState<number | null>(
    null,
  );

  // Single-open accordion: aynı anda yalnızca bir gün açık (Jinja'da bu yoktu;
  // kullanıcı talebi 2026-05-19). Default: bugüne denk gelen gün.
  const todayDay = data.days.find((d) => d.is_today);
  const [openDate, setOpenDate] = React.useState<string | null>(
    todayDay ? todayDay.date : data.days[0]?.date ?? null,
  );
  const sidebarQ = useQuery<SidebarResponse>({
    queryKey: teacherKeys.studentSidebar(studentId, focusedSubjectId),
    queryFn: () => getStudentSidebar(studentId, focusedSubjectId),
    staleTime: 30_000,
  });

  // Açık <details> ID'lerini swap'lerde koru
  const [openSubjects, setOpenSubjects] = React.useState<Set<number>>(
    new Set(),
  );
  const [openBooks, setOpenBooks] = React.useState<Set<number>>(new Set());

  // Sinema-koltuğu modal — kitap satırındaki grid ikonu açar
  const [gridBookId, setGridBookId] = React.useState<number | null>(null);

  const publishWeek = usePublishWeek(studentId);
  const notifyParents = useNotifyParents(studentId);

  const draftTotal = data.week_draft_total ?? 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            <Link
              href={`/teacher/students/${studentId}`}
              className="hover:underline"
            >
              ← Öğrenci detayı
            </Link>
          </p>
          <h1 className="text-2xl font-semibold tracking-tight font-display">
            7 Günlük Program
          </h1>
          <p className="text-sm text-muted-foreground">
            {data.start_date} → {data.end_date}
            {data.week_anchor ? (
              <>
                {" · "}
                <span className="text-muted-foreground/80">
                  an: <b>{data.week_anchor}</b>
                  {data.anchor_is_manual ? (
                    <span className="text-indigo-600"> ●</span>
                  ) : null}
                </span>
              </>
            ) : null}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <nav className="flex items-center gap-1 text-sm">
            <Link
              href={`/teacher/students/${studentId}/week?start=${data.prev_start}`}
              className="rounded-md border border-border px-3 py-1.5 hover:bg-muted"
            >
              ← 7 gün
            </Link>
            <Link
              href={`/teacher/students/${studentId}/week`}
              className="rounded-md border border-border px-3 py-1.5 hover:bg-muted"
            >
              Bugünden
            </Link>
            <Link
              href={`/teacher/students/${studentId}/week?start=${data.next_start}`}
              className="rounded-md border border-border px-3 py-1.5 hover:bg-muted"
            >
              7 gün →
            </Link>
          </nav>
          <Link
            href={`/teacher/students/${studentId}/diagnostics`}
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted inline-flex items-center gap-1.5"
            title="Öneri motorunun sayısal iç durumunu gör"
          >
            <Microscope className="size-4" aria-hidden />
            Tanı
          </Link>
          {draftTotal > 0 ? (
            <Button
              onClick={() => {
                if (
                  !window.confirm(
                    `${draftTotal} taslak görev yayına alınsın? Bu işlem öğrencinin paneline indirilecek (veli bildirimi YOK — ayrıca "Veliye duyur" basmalısın).`,
                  )
                ) {
                  return;
                }
                publishWeek.mutate({ body: { week_start: data.start_date } });
              }}
              disabled={publishWeek.isPending}
              className="bg-amber-600 hover:bg-amber-700 text-white"
              title="Tüm haftanın taslak görevlerini öğrenciye aç"
            >
              {publishWeek.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Rocket className="size-4" aria-hidden />
              )}
              Tüm haftayı yayınla ({draftTotal})
            </Button>
          ) : null}
          <Button
            variant="outline"
            onClick={() => {
              if (
                !window.confirm(
                  `Bu hafta ${data.start_date} – ${data.end_date} programını bağlı velilere bildirim olarak göndermek istediğinizden emin misiniz?${
                    draftTotal > 0
                      ? `\n\nNOT: ${draftTotal} taslak görev YAYINLANMAMIŞ; bildirimde sayılmaz.`
                      : ""
                  }`,
                )
              ) {
                return;
              }
              notifyParents.mutate({ body: { week_start: data.start_date } });
            }}
            disabled={notifyParents.isPending}
            title="Yayınlanmış programı bağlı velilere e-posta/WhatsApp ile duyur"
            className="border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
          >
            {notifyParents.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Megaphone className="size-4" aria-hidden />
            )}
            Veliye duyur
          </Button>
        </div>
      </header>

      {draftTotal > 0 ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50/60 px-4 py-3 text-sm text-amber-900 flex items-start gap-3">
          <FileEdit
            className="size-4 text-amber-700 mt-0.5 flex-shrink-0"
            aria-hidden
          />
          <span>
            <span className="font-semibold">{draftTotal} görev taslak halinde</span>{" "}
            — öğretmen panelinde görünür, öğrenci paneline indirilmedi. Hazır
            olunca yukarıdaki <span className="font-medium">Tüm haftayı yayınla</span>{" "}
            butonuna bas; veya gün bazında yayınlayabilirsin.
          </span>
        </div>
      ) : null}

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6">
        <div className="space-y-4 min-w-0">
          <WeekNotesCard
            studentId={studentId}
            weekStart={data.week_start_anchor}
            notes={notes}
          />

          {data.days.map((d) => (
            <WeekDayCard
              key={d.date}
              studentId={studentId}
              weekStartDate={data.start_date}
              day={d}
              focusedSubjectId={focusedSubjectId}
              onFocusSubject={setFocusedSubjectId}
              isOpen={openDate === d.date}
              onSetOpen={(nowOpen) => {
                if (nowOpen) setOpenDate(d.date);
                else if (openDate === d.date) setOpenDate(null);
              }}
              maturityValue={data.maturity_value ?? 0}
              maturityLabel={data.maturity_label ?? ""}
              weeksObserved={data.weeks_observed ?? 0}
              daysObserved={data.days_observed ?? 0}
              activePhase={data.active_phase ?? null}
              trackRequired={data.track_required ?? false}
              trackMissing={data.track_missing ?? false}
              trackLabel={data.track_label ?? null}
            />
          ))}

          <div className="flex gap-3 text-xs text-muted-foreground mt-2">
            <span className="italic">
              Aynı anda yalnızca bir gün açık olur — başka bir güne tıkla, mevcut
              gün kapanır.
            </span>
            <span className="text-muted-foreground/40">·</span>
            <button
              type="button"
              onClick={() => setOpenDate(null)}
              className="hover:text-foreground hover:underline"
            >
              Tümünü kapat
            </button>
          </div>
        </div>

        <aside className="xl:sticky xl:top-4 xl:self-start xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto rounded-lg border border-border bg-card">
          <ResourceSidebar
            data={sidebarQ.data}
            isLoading={sidebarQ.isLoading}
            focusedSubjectId={focusedSubjectId}
            onClearFocus={() => setFocusedSubjectId(null)}
            openSubjects={openSubjects}
            setOpenSubjects={setOpenSubjects}
            openBooks={openBooks}
            setOpenBooks={setOpenBooks}
            onOpenBookGrid={setGridBookId}
          />
        </aside>
      </div>

      <BookGridModal
        open={gridBookId !== null}
        onOpenChange={(o) => {
          if (!o) setGridBookId(null);
        }}
        studentId={studentId}
        bookId={gridBookId}
      />
    </div>
  );
}
