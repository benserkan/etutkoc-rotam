"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Calendar,
  CalendarPlus,
  CheckCircle2,
  ChevronDown,
  Clock,
  FileEdit,
  Loader2,
  Megaphone,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Printer,
  Rocket,
  Sparkles,
  Trash2,
  TriangleAlert,
} from "lucide-react";

import {
  useCarryover,
  useCreateProgram,
  useDeleteProgram,
  useUpdateProgram,
  useWrapLegacyTasks,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  WeeklyProgramItem,
  WeeklyProgramOverlapItem,
} from "@/lib/types/teacher";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DemoHint } from "@/components/demos/demo-hint";
import { cn } from "@/lib/utils";

import {
  getStudentAllSubjects,
  getStudentSidebar,
  getStudentWeekNotes,
  getTeacherStudentWeek,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  usePublishWeek,
} from "@/lib/hooks/use-weekly-plan-mutations";
import type {
  SidebarResponse,
  SubjectListResponse,
  TeacherStudentWeekResponse,
  TeacherWeekNote,
} from "@/lib/types/teacher";
import { Button } from "@/components/ui/button";

import { BookGridModal } from "./weekly-plan/book-grid-modal";
import { ParentAnnounceDialog } from "./weekly-plan/parent-announce-dialog";
import { WeekDayCard } from "./weekly-plan/week-day-card";
import { WeekNotesCard } from "./weekly-plan/week-notes-card";
import { ResourceSidebar } from "./weekly-plan/resource-sidebar";
import { CarryoverPanel } from "./weekly-plan/carryover-panel";
import { NextUnitsPanel } from "./weekly-plan/next-units-panel";
import { WeekGrid } from "./weekly-plan/week-grid";
import { WorkBlockPanel } from "./weekly-plan/work-block-panel";

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
  // Gün FİHRİSTİ (2026-09-03 koç geri bildirimi): 7 gün kartı alt alta
  // açıldığında içerik o kadar uzuyordu ki günler arası geçiş uzun kaydırma
  // gerektiriyordu. Artık solda gün listesi, sağda YALNIZ seçili günün kartı
  // render edilir — ızgaradan bir güne tıklamak da burayı değiştirir.
  const selectedDay =
    data.days.find((d) => d.date === openDate) ?? todayDay ?? data.days[0] ?? null;
  const sidebarQ = useQuery<SidebarResponse>({
    queryKey: teacherKeys.studentSidebar(studentId, focusedSubjectId),
    queryFn: () => getStudentSidebar(studentId, focusedSubjectId),
    staleTime: 30_000,
  });
  // Tüm dersler (kitapsız dahil) — deneme/branş görev adından ders eşleştirmek için.
  const allSubjectsQ = useQuery<SubjectListResponse>({
    queryKey: teacherKeys.studentAllSubjects(studentId),
    queryFn: () => getStudentAllSubjects(studentId),
    staleTime: 5 * 60_000,
  });
  const subjectsForGrouping = React.useMemo(
    () => (allSubjectsQ.data?.items ?? []).map((s) => ({ id: s.id, name: s.name })),
    [allSubjectsQ.data],
  );

  // Açık <details> ID'lerini swap'lerde koru
  const [openSubjects, setOpenSubjects] = React.useState<Set<number>>(
    new Set(),
  );
  const [openBooks, setOpenBooks] = React.useState<Set<number>>(new Set());

  // Sinema-koltuğu modal — kitap satırındaki grid ikonu açar
  const [gridBookId, setGridBookId] = React.useState<number | null>(null);

  const publishWeek = usePublishWeek(studentId);
  // Devret sürükle-bırak: panelden bir görevi gün kartına bırakınca o güne taşı.
  const carryDnd = useCarryover(studentId);
  const [dragOverDate, setDragOverDate] = React.useState<string | null>(null);
  const CARRY_MIME = "text/x-carryover-task";

  const draftTotal = data.week_draft_total ?? 0;

  // WP3 — Program-aware: aktif program + dialog state
  const [newProgramOpen, setNewProgramOpen] = React.useState(false);
  // Veliye duyur — gönderim öncesi önizleme modalı
  const [announceOpen, setAnnounceOpen] = React.useState(false);
  const [programsDropdownOpen, setProgramsDropdownOpen] = React.useState(false);
  // Sağ panel (Kaynak Durumu / Serbest Bloklar / Devret) katlanabilir: görev
  // eklerken gün kartı ~360px daha genişler — form alanları sıkışmasın
  // (koç geri bildirimi 2026-09-03: "en önemli kısım burası, ferah olmalı").
  // Tercih tarayıcıda saklanır.
  // NOT: tercih localStorage'da SAKLANMIYOR — effect içinde setState React
  // Compiler kuralına takılıyor (react-hooks/set-state-in-effect) ve lazy
  // initializer SSR/hydration uyuşmazlığı üretirdi. Oturum içi state yeterli:
  // koç panelini kapatıp o oturumda geniş kartla çalışır.
  const [sideOpen, setSideOpen] = React.useState(true);
  const toggleSide = React.useCallback(() => setSideOpen((v) => !v), []);
  // Program düzenle/sil — tarih hatasıyla oluşturulan programı düzeltmek veya
  // boş programı kaldırmak için (koç geri bildirimi 2026-09-03).
  const [editProgram, setEditProgram] = React.useState<WeeklyProgramItem | null>(null);
  const [deleteTarget, setDeleteTarget] = React.useState<WeeklyProgramItem | null>(null);
  const currentProgramId = data.current_program_id ?? null;
  const currentProgramName = data.current_program_name;
  const currentProgramDayCount = data.current_program_day_count;
  const allPrograms = data.programs ?? [];
  const currentProgram =
    allPrograms.find((p) => p.id === currentProgramId) ?? null;
  const unlinkedTaskCount = data.unlinked_task_count ?? 0;
  const unlinkedEarliest = data.unlinked_earliest;
  const unlinkedLatest = data.unlinked_latest;

  return (
    <div className="space-y-6">
      {/* WP3 — Eski görevler banner (mevcut öğrencilerin geçişi için tek tık) */}
      {unlinkedTaskCount > 0 ? (
        <UnlinkedTasksBanner
          studentId={studentId}
          taskCount={unlinkedTaskCount}
          earliest={unlinkedEarliest}
          latest={unlinkedLatest}
        />
      ) : null}

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
          {currentProgramId ? (
            <>
              <h1 className="text-2xl font-semibold tracking-tight font-display flex items-center gap-2">
                <span className="truncate">
                  {currentProgramName || "Program"}
                </span>
                <span className="text-[11px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded border border-cyan-200 bg-cyan-50 text-cyan-800">
                  {currentProgramDayCount ?? data.days?.length ?? 7} gün
                </span>
              </h1>
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <span>
                  {data.start_date} → {data.end_date}
                </span>
                {currentProgram ? (
                  <button
                    type="button"
                    onClick={() => setEditProgram(currentProgram)}
                    className="inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-[11px] hover:bg-muted"
                    title="Bu programın tarihlerini/etiketini düzelt"
                  >
                    <Pencil className="size-3" aria-hidden />
                    Tarihleri düzenle
                  </button>
                ) : null}
              </p>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-semibold tracking-tight font-display">
                Haftalık Program
              </h1>
              <p className="text-sm text-muted-foreground">
                {data.start_date} → {data.end_date}
                {allPrograms.length === 0 ? (
                  <span className="ml-2 text-amber-700 text-xs">
                    · Henüz program oluşturulmadı
                  </span>
                ) : null}
              </p>
            </>
          )}
          <DemoHint contextKey="program" role="teacher" className="mt-1.5" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* WP3 — Yeni Program Oluştur (en belirgin buton) */}
          <Button
            onClick={() => setNewProgramOpen(true)}
            className="bg-cyan-600 hover:bg-cyan-700 text-white"
            title="Bu öğrenci için yeni bir program oluştur (tarih aralığı seç)"
          >
            <CalendarPlus className="size-4" aria-hidden />
            Yeni Program
          </Button>
          {/* WP3 — Programlar dropdown (geçmiş erişim) */}
          {allPrograms.length > 0 ? (
            <ProgramsDropdown
              studentId={studentId}
              programs={allPrograms}
              currentProgramId={currentProgramId}
              open={programsDropdownOpen}
              onOpenChange={setProgramsDropdownOpen}
              onEdit={(p) => {
                setProgramsDropdownOpen(false);
                setEditProgram(p);
              }}
              onDelete={(p) => {
                setProgramsDropdownOpen(false);
                setDeleteTarget(p);
              }}
            />
          ) : null}
          <button
            type="button"
            onClick={toggleSide}
            className="hidden xl:inline-flex rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted items-center gap-1.5"
            title={
              sideOpen
                ? "Yan paneli gizle — gün kartı genişlesin"
                : "Yan paneli göster (Kaynak Durumu · Serbest Bloklar)"
            }
          >
            {sideOpen ? (
              <PanelRightClose className="size-4" aria-hidden />
            ) : (
              <PanelRightOpen className="size-4" aria-hidden />
            )}
            {sideOpen ? "Paneli gizle" : "Panel"}
          </button>
          <Link
            href={`/teacher/students/${studentId}/program/print${
              currentProgramId
                ? `?program_id=${currentProgramId}`
                : `?week=${data.start_date}`
            }`}
            target="_blank"
            rel="noopener"
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted inline-flex items-center gap-1.5"
            title="Bu programı yazdırılabilir formatta aç"
          >
            <Printer className="size-4" aria-hidden />
            Yazdır
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
                publishWeek.mutate({
                  body: {
                    week_start: data.start_date,
                    program_id: currentProgramId ?? undefined,
                  },
                });
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
            onClick={() => setAnnounceOpen(true)}
            title="Yayınlanmış programı bağlı velilere e-posta/WhatsApp ile duyur — önce önizleme"
            className="bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white"
          >
            <Megaphone className="size-4" aria-hidden />
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

      <WeekGrid
        studentId={studentId}
        days={data.days}
        subjects={subjectsForGrouping}
        openDate={openDate}
        onOpenDay={(date) => {
          setOpenDate(date);
          if (typeof window !== "undefined") {
            window.requestAnimationFrame(() => {
              document
                .getElementById("day-editor")
                ?.scrollIntoView({ behavior: "smooth", block: "start" });
            });
          }
        }}
      />

      <div
        className={cn(
          "grid grid-cols-1 gap-6",
          sideOpen && "xl:grid-cols-[1fr_360px]",
        )}
      >
        <div className="space-y-4 min-w-0">
          <WeekNotesCard
            studentId={studentId}
            weekStart={data.week_start_anchor}
            notes={notes}
          />

          <div id="day-editor" className="grid grid-cols-1 lg:grid-cols-[150px_1fr] gap-3 scroll-mt-4">
            {/* Gün fihristi — tıkla, sağdaki kart değişsin (uzun kaydırma yok) */}
            <nav
              className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible pb-1 lg:pb-0"
              aria-label="Günler"
            >
              {data.days.map((d) => {
                const active = selectedDay?.date === d.date;
                const total = d.tasks_count ?? d.tasks.length;
                const doneTasks = d.tasks.filter(
                  (t) =>
                    t.status === "completed" ||
                    (t.planned_count > 0 && t.completed_count >= t.planned_count),
                ).length;
                const pct = total > 0 ? Math.round((doneTasks / total) * 100) : 0;
                return (
                  <button
                    key={d.date}
                    type="button"
                    onClick={() => setOpenDate(d.date)}
                    onDragOver={(e) => {
                      if (d.is_past) return;
                      if (e.dataTransfer.types.includes(CARRY_MIME)) {
                        e.preventDefault();
                        e.dataTransfer.dropEffect = "copy";
                        if (dragOverDate !== d.date) setDragOverDate(d.date);
                      }
                    }}
                    onDragLeave={(e) => {
                      if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                        setDragOverDate((cur) => (cur === d.date ? null : cur));
                      }
                    }}
                    onDrop={(e) => {
                      const raw = e.dataTransfer.getData(CARRY_MIME);
                      setDragOverDate(null);
                      if (!raw || d.is_past) return;
                      e.preventDefault();
                      const tid = Number(raw);
                      if (!Number.isFinite(tid)) return;
                      setOpenDate(d.date);
                      carryDnd.mutate({
                        body: { target_date: d.date, period: null, task_ids: [tid] },
                      });
                    }}
                    className={cn(
                      "shrink-0 lg:w-full text-left rounded-lg border px-2.5 py-2 transition",
                      active
                        ? "border-cyan-400 bg-cyan-50 dark:bg-cyan-500/10 dark:border-cyan-500/40"
                        : "border-border hover:bg-muted",
                      dragOverDate === d.date &&
                        "ring-2 ring-amber-400 ring-offset-1 ring-offset-background",
                    )}
                    aria-current={active ? "true" : undefined}
                  >
                    <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
                      <span
                        className={cn(
                          "text-sm font-semibold",
                          active
                            ? "text-cyan-900 dark:text-cyan-200"
                            : "text-foreground",
                        )}
                      >
                        {d.dow_label}
                      </span>
                      {d.is_today ? (
                        <span className="text-[9px] uppercase tracking-wider px-1 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-200 dark:border-emerald-500/30">
                          bugün
                        </span>
                      ) : null}
                      {(d.draft_count ?? 0) > 0 ? (
                        <span className="text-[9px] uppercase tracking-wider px-1 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200 dark:bg-amber-500/15 dark:text-amber-200 dark:border-amber-500/30">
                          taslak
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground tabular-nums">
                      {total === 0 ? (
                        <span className="italic">boş</span>
                      ) : (
                        <>
                          {doneTasks}/{total} görev
                          {(d.test_planned ?? 0) > 0 ? (
                            <>
                              {" · "}
                              {d.test_completed ?? 0}/{d.test_planned} test
                            </>
                          ) : null}
                        </>
                      )}
                    </div>
                    {total > 0 ? (
                      <div className="mt-1 h-1 rounded-full bg-muted overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full",
                            pct >= 70
                              ? "bg-emerald-500"
                              : pct >= 40
                                ? "bg-amber-500"
                                : "bg-rose-500",
                          )}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </nav>

            {/* Seçili günün kartı — yalnız bu render edilir */}
            <div className="min-w-0">
              {selectedDay ? (
                <WeekDayCard
                  key={selectedDay.date}
                  studentId={studentId}
                  weekStartDate={data.start_date}
                  day={selectedDay}
                  weekDays={data.days}
                  subjects={subjectsForGrouping}
                  focusedSubjectId={focusedSubjectId}
                  onFocusSubject={setFocusedSubjectId}
                  isOpen
                  onSetOpen={() => {
                    /* fihristte gün kartı daima açık — kapatma yok */
                  }}
                  maturityValue={data.maturity_value ?? 0}
                  maturityLabel={data.maturity_label ?? ""}
                  weeksObserved={data.weeks_observed ?? 0}
                  daysObserved={data.days_observed ?? 0}
                  activePhase={data.active_phase ?? null}
                  trackRequired={data.track_required ?? false}
                  trackMissing={data.track_missing ?? false}
                  trackLabel={data.track_label ?? null}
                  onCarryoverDrop={
                    selectedDay.is_past
                      ? undefined
                      : (period, taskId) =>
                          carryDnd.mutate({
                            body: {
                              target_date: selectedDay.date,
                              period,
                              task_ids: [taskId],
                            },
                          })
                  }
                />
              ) : null}
            </div>
          </div>

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

        {sideOpen ? (
        <aside className="xl:sticky xl:top-4 xl:self-start xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto rounded-lg border border-border bg-card">
          <CarryoverPanel
            studentId={studentId}
            programId={currentProgramId}
            weekDays={data.days}
          />
          <NextUnitsPanel studentId={studentId} weekDays={data.days} />
          <WorkBlockPanel studentId={studentId} />
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
        ) : null}
      </div>

      <BookGridModal
        open={gridBookId !== null}
        onOpenChange={(o) => {
          if (!o) setGridBookId(null);
        }}
        studentId={studentId}
        bookId={gridBookId}
      />

      {/* Program düzenle / sil (tarih hatası düzeltme) */}
      {editProgram ? (
        <EditProgramDialog
          studentId={studentId}
          program={editProgram}
          onClose={() => setEditProgram(null)}
        />
      ) : null}
      {deleteTarget ? (
        <DeleteProgramDialog
          studentId={studentId}
          program={deleteTarget}
          isCurrent={deleteTarget.id === currentProgramId}
          onClose={() => setDeleteTarget(null)}
        />
      ) : null}

      {/* WP3 — Yeni program dialog */}
      <NewProgramDialog
        open={newProgramOpen}
        onClose={() => setNewProgramOpen(false)}
        studentId={studentId}
      />

      {/* Veliye duyur — gönderim öncesi önizleme */}
      <ParentAnnounceDialog
        studentId={studentId}
        weekStart={data.start_date}
        programId={currentProgramId ?? null}
        draftTotal={draftTotal}
        open={announceOpen}
        onOpenChange={setAnnounceOpen}
      />
    </div>
  );
}

// =============================================================================
// WP3 — Programs dropdown (geçmiş programları aç + tıkla → o haftaya git)
// =============================================================================

function ProgramsDropdown({
  studentId,
  programs,
  currentProgramId,
  open,
  onOpenChange,
  onEdit,
  onDelete,
}: {
  studentId: number;
  programs: WeeklyProgramItem[];
  currentProgramId: number | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onEdit: (p: WeeklyProgramItem) => void;
  onDelete: (p: WeeklyProgramItem) => void;
}) {
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onOpenChange(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open, onOpenChange]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted inline-flex items-center gap-1.5"
        title="Geçmiş programları gör"
      >
        <Calendar className="size-4" aria-hidden />
        Programlar
        <ChevronDown className="size-3.5" aria-hidden />
      </button>
      {open ? (
        <div className="absolute right-0 z-20 mt-1 w-80 max-h-96 overflow-y-auto rounded-md border border-border bg-popover p-1 shadow-md">
          {programs.map((p) => {
            const isCurrent = p.id === currentProgramId;
            return (
              <div
                key={p.id}
                className={cn(
                  "group flex items-stretch gap-1 rounded",
                  isCurrent && "bg-cyan-50 border border-cyan-200",
                )}
              >
                <Link
                  href={`/teacher/students/${studentId}/week?program_id=${p.id}`}
                  onClick={() => onOpenChange(false)}
                  className="flex-1 min-w-0 px-3 py-2 rounded text-sm hover:bg-muted"
                >
                  <div className="flex items-center gap-2 justify-between">
                    <span className="font-medium truncate">
                      {p.name || `${p.start_date} – ${p.end_date}`}
                    </span>
                    {p.is_active ? (
                      <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                        Bu hafta
                      </span>
                    ) : null}
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    {p.start_date} → {p.end_date} · {p.day_count} gün ·{" "}
                    {p.task_count > 0 ? (
                      <span>{p.task_count} görev</span>
                    ) : (
                      <span className="text-amber-700">boş</span>
                    )}
                  </div>
                </Link>
                <div className="flex items-center gap-0.5 pr-1">
                  <button
                    type="button"
                    onClick={() => onEdit(p)}
                    className="rounded p-1.5 text-slate-500 hover:bg-muted hover:text-slate-900"
                    title="Tarihleri / etiketi düzenle"
                    aria-label="Programı düzenle"
                  >
                    <Pencil className="size-3.5" aria-hidden />
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(p)}
                    className="rounded p-1.5 text-slate-500 hover:bg-rose-50 hover:text-rose-700"
                    title="Programı sil"
                    aria-label="Programı sil"
                  >
                    <Trash2 className="size-3.5" aria-hidden />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

// =============================================================================
// WP3 — Unlinked tasks banner (mevcut öğrenci için tek tık "Eski Dönem")
// =============================================================================

function UnlinkedTasksBanner({
  studentId,
  taskCount,
  earliest,
  latest,
}: {
  studentId: number;
  taskCount: number;
  earliest: string | null | undefined;
  latest: string | null | undefined;
}) {
  const wrap = useWrapLegacyTasks(studentId);
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  return (
    <>
      <div className="rounded-lg border-2 border-sky-200 bg-sky-50 px-4 py-3 flex items-start gap-3">
        <Sparkles className="size-5 text-sky-700 flex-shrink-0 mt-0.5" aria-hidden />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-sky-900">
            Bu öğrencinin {taskCount} görevi henüz bir programa bağlı değil
          </p>
          <p className="text-xs text-sky-800 mt-1">
            {earliest && latest ? (
              <>
                {earliest} – {latest} arası mevcut görevleri tek tık ile{" "}
                <b>&quot;Eski Dönem&quot;</b> programına bağlayabilirim. Veri kaybı yok.
              </>
            ) : (
              "Eski görevleri tek tık ile  dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200 dark:bg-cyan-500/10 dark:border-cyan-500/30 dark:text-cyan-200 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200'Eski Dönem' programına bağlayabilirim."
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setConfirmOpen(true)}
          disabled={wrap.isPending}
          className="rounded-md bg-sky-600 hover:bg-sky-700 text-white px-3 py-1.5 text-sm font-medium inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          {wrap.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <CheckCircle2 className="size-3.5" aria-hidden />
          )}
          Tek tıkla bağla
        </button>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Eski görevleri programa bağla</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm">
              {taskCount} görev <b>&quot;Eski Dönem&quot;</b> adlı yeni bir programa
              bağlanacak ({earliest} – {latest}). Veri kaybı yok, sadece
              gruplandırma.
            </p>
            <p className="text-[11px] text-muted-foreground italic">
              Bu işlemi yaptıktan sonra eski görevleri Programlar dropdown&apos;undan
              görebilir, yazdırabilir veya silebilirsin.
            </p>
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setConfirmOpen(false)}
              className="px-4 py-2 text-sm rounded-md border border-border hover:bg-muted"
            >
              Vazgeç
            </button>
            <button
              type="button"
              onClick={() => {
                wrap.mutate(
                  { name: "Eski Dönem" },
                  { onSuccess: () => setConfirmOpen(false) },
                );
              }}
              disabled={wrap.isPending}
              className="px-4 py-2 text-sm rounded-md bg-sky-600 hover:bg-sky-700 text-white inline-flex items-center gap-2"
            >
              {wrap.isPending ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <CheckCircle2 className="size-3.5" aria-hidden />
              )}
              Onaylıyorum
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// =============================================================================
// Program düzenle / sil — tarih hatasıyla oluşturulmuş programı düzeltmek veya
// yanlış aralıkta açılmış boş programı kaldırmak için (koç geri bildirimi).
// =============================================================================

function EditProgramDialog({
  studentId,
  program,
  onClose,
}: {
  studentId: number;
  program: WeeklyProgramItem;
  onClose: () => void;
}) {
  const router = useRouter();
  const [startDate, setStartDate] = React.useState(program.start_date);
  const [endDate, setEndDate] = React.useState(program.end_date);
  const [name, setName] = React.useState(program.name ?? "");
  const [overlaps, setOverlaps] = React.useState<WeeklyProgramOverlapItem[]>([]);
  const [allowOverlap, setAllowOverlap] = React.useState(false);
  const update = useUpdateProgram(studentId);

  const dayCount = React.useMemo(() => {
    const a = Date.parse(startDate);
    const b = Date.parse(endDate);
    if (Number.isNaN(a) || Number.isNaN(b)) return 0;
    return Math.floor((b - a) / 86400000) + 1;
  }, [startDate, endDate]);
  const validDays = dayCount >= 1 && dayCount <= 14;
  const changed =
    startDate !== program.start_date ||
    endDate !== program.end_date ||
    (name.trim() || null) !== (program.name ?? null);

  function handleSubmit() {
    if (!validDays) return;
    update.mutate(
      {
        programId: program.id,
        body: {
          start_date: startDate,
          end_date: endDate,
          name: name.trim() || null,
          allow_overlap: allowOverlap,
        },
      },
      {
        onSuccess: (res) => {
          onClose();
          // Tarih değiştiyse görüntülenen pencere kayar — programın kendi
          // aralığına götür ki koç düzelttiği haftayı görsün.
          router.push(
            `/teacher/students/${studentId}/week?program_id=${res.data.id}`,
          );
          router.refresh();
        },
        onError: (e) => {
          const detail = (e.detail ?? {}) as {
            code?: string;
            overlaps?: WeeklyProgramOverlapItem[];
          };
          if (detail.code === "overlap") setOverlaps(detail.overlaps ?? []);
        },
      },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pencil className="size-5 text-cyan-700" aria-hidden />
            Programı düzenle
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <p className="text-xs text-muted-foreground">
            Tarihleri değiştirdiğinde bu aralıktaki görevler yerinde kalır —
            görevler tarihe bağlıdır, programa değil. Yanlış aralıkta
            oluşturduğun programı buradan düzeltebilirsin.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="wp-edit-start">Başlangıç tarihi</Label>
              <Input
                id="wp-edit-start"
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  setOverlaps([]);
                  setAllowOverlap(false);
                }}
              />
            </div>
            <div>
              <Label htmlFor="wp-edit-end">Bitiş tarihi (dahil)</Label>
              <Input
                id="wp-edit-end"
                type="date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value);
                  setOverlaps([]);
                  setAllowOverlap(false);
                }}
              />
            </div>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <Clock className="size-4 text-muted-foreground" aria-hidden />
            <span>
              Süre:{" "}
              <b
                className={cn(
                  "tabular-nums",
                  validDays ? "text-cyan-700" : "text-rose-700",
                )}
              >
                {dayCount} gün
              </b>
              {!validDays ? (
                <span className="text-rose-700 ml-2 text-xs">
                  (1–14 gün arası olmalı)
                </span>
              ) : null}
            </span>
          </div>

          <div>
            <Label htmlFor="wp-edit-name">Etiket (opsiyonel)</Label>
            <Input
              id="wp-edit-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="örn. Bayram Sonrası Hafta"
              maxLength={120}
            />
          </div>

          {overlaps.length > 0 ? (
            <div className="rounded-lg border-2 border-amber-300 bg-amber-50 p-3 text-sm">
              <p className="font-semibold text-amber-900 mb-2">
                Yeni tarihler {overlaps.length} programla çakışıyor:
              </p>
              <ul className="space-y-1 text-amber-900">
                {overlaps.map((o) => (
                  <li
                    key={o.program_id}
                    className="text-xs flex items-center justify-between"
                  >
                    <span>
                      <b>{o.label}</b> ({o.start_date} → {o.end_date})
                    </span>
                    <span className="text-amber-800">
                      {o.overlap_days} gün, {o.task_count_in_overlap} görev
                    </span>
                  </li>
                ))}
              </ul>
              <label className="flex items-center gap-2 mt-3 text-xs text-amber-900">
                <input
                  type="checkbox"
                  checked={allowOverlap}
                  onChange={(e) => setAllowOverlap(e.target.checked)}
                />
                <span>Çakışmaya rağmen kaydet (eski programlar değişmez)</span>
              </label>
            </div>
          ) : null}
        </div>
        <DialogFooter>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-md border border-border hover:bg-muted"
          >
            Vazgeç
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={
              update.isPending ||
              !validDays ||
              !changed ||
              (overlaps.length > 0 && !allowOverlap)
            }
            className="px-4 py-2 text-sm rounded-md bg-cyan-600 hover:bg-cyan-700 text-white inline-flex items-center gap-2 disabled:opacity-50"
          >
            {update.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <Pencil className="size-3.5" aria-hidden />
            )}
            Kaydet
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteProgramDialog({
  studentId,
  program,
  isCurrent,
  onClose,
}: {
  studentId: number;
  program: WeeklyProgramItem;
  isCurrent: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [deleteTasks, setDeleteTasks] = React.useState(false);
  const del = useDeleteProgram(studentId);
  const isEmpty = program.task_count === 0;

  function handleDelete() {
    del.mutate(
      { programId: program.id, deleteTasks: isEmpty ? false : deleteTasks },
      {
        onSuccess: () => {
          onClose();
          if (isCurrent) {
            router.push(`/teacher/students/${studentId}/week`);
          }
          router.refresh();
        },
      },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Trash2 className="size-5 text-rose-600" aria-hidden />
            Programı sil
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2 text-sm">
          <div className="rounded-md border border-border bg-muted/40 p-3">
            <p className="font-medium text-slate-900">
              {program.name || `${program.start_date} – ${program.end_date}`}
            </p>
            <p className="text-xs text-slate-600 mt-0.5">
              {program.start_date} → {program.end_date} · {program.day_count} gün
            </p>
          </div>

          {isEmpty ? (
            <p className="text-slate-700">
              Bu program <b>boş</b> — içinde görev yok. Silmek güvenli.
            </p>
          ) : (
            <div className="rounded-lg border-2 border-amber-300 bg-amber-50 p-3 text-amber-900">
              <p className="flex items-start gap-2">
                <TriangleAlert className="size-4 mt-0.5 shrink-0" aria-hidden />
                <span>
                  Bu tarih aralığında <b>{program.task_count} görev</b> var.
                  Programı silmek görevleri silmez — görevler tarihe bağlıdır ve
                  varsayılan olarak <b>korunur</b>.
                </span>
              </p>
              <label className="flex items-start gap-2 mt-3 text-xs">
                <input
                  type="checkbox"
                  checked={deleteTasks}
                  onChange={(e) => setDeleteTasks(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  Bu aralıktaki {program.task_count} görevi de sil (kitap
                  rezervleri iade edilir). <b>Geri alınamaz.</b>
                </span>
              </label>
            </div>
          )}
        </div>
        <DialogFooter>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-md border border-border hover:bg-muted"
          >
            Vazgeç
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={del.isPending}
            className="px-4 py-2 text-sm rounded-md bg-rose-600 hover:bg-rose-700 text-white inline-flex items-center gap-2 disabled:opacity-50"
          >
            {del.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="size-3.5" aria-hidden />
            )}
            {!isEmpty && deleteTasks
              ? "Programı ve görevleri sil"
              : "Programı sil"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// WP3 — New program dialog (tarih aralığı seç + çakışma uyarısı)
// =============================================================================

function NewProgramDialog({
  open,
  onClose,
  studentId,
}: {
  open: boolean;
  onClose: () => void;
  studentId: number;
}) {
  if (!open) return null;
  return (
    <NewProgramDialogInner studentId={studentId} onClose={onClose} />
  );
}

function todayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

function addDaysIso(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y) return iso;
  const date = new Date(Date.UTC(y, m - 1, d));
  date.setUTCDate(date.getUTCDate() + days);
  const ny = date.getUTCFullYear();
  const nm = String(date.getUTCMonth() + 1).padStart(2, "0");
  const nd = String(date.getUTCDate()).padStart(2, "0");
  return `${ny}-${nm}-${nd}`;
}

function NewProgramDialogInner({
  studentId,
  onClose,
}: {
  studentId: number;
  onClose: () => void;
}) {
  const router = useRouter();
  const today = todayIso();
  const [startDate, setStartDate] = React.useState(today);
  const [endDate, setEndDate] = React.useState(addDaysIso(today, 6));
  const [name, setName] = React.useState("");
  const [overlaps, setOverlaps] = React.useState<WeeklyProgramOverlapItem[]>([]);
  const [allowOverlap, setAllowOverlap] = React.useState(false);
  const create = useCreateProgram(studentId);

  // Süre hesabı (UI ipucu)
  const dayCount = React.useMemo(() => {
    try {
      const a = new Date(startDate);
      const b = new Date(endDate);
      return Math.floor((b.getTime() - a.getTime()) / 86400000) + 1;
    } catch {
      return 0;
    }
  }, [startDate, endDate]);

  const validDays = dayCount >= 1 && dayCount <= 14;

  function handleSubmit() {
    setOverlaps([]);
    create.mutate(
      {
        start_date: startDate,
        end_date: endDate,
        name: name.trim() || null,
        allow_overlap: allowOverlap,
      },
      {
        onSuccess: (res) => {
          onClose();
          // Yeni programın HAFTASINA geç — yoksa sayfa bugünün haftasında kalır
          // ve eklenen görevler yanlış haftaya yazılır (06-29 programına 06-22'ye
          // görev düşmesi bug'ı). program_id ile o aralık görüntülenir.
          if (res?.data?.id) {
            router.push(
              `/teacher/students/${studentId}/week?program_id=${res.data.id}`,
            );
          }
        },
        onError: (err) => {
          const detail = err.detail as
            | { code?: string; overlaps?: WeeklyProgramOverlapItem[] }
            | undefined;
          if (detail?.code === "overlap" && detail.overlaps) {
            setOverlaps(detail.overlaps);
          }
        },
      },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarPlus className="size-5 text-cyan-700" aria-hidden />
            Yeni Program Oluştur
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          {/* Tarih seçici */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="wp-start">Başlangıç tarihi</Label>
              <Input
                id="wp-start"
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  setOverlaps([]);
                  setAllowOverlap(false);
                }}
              />
            </div>
            <div>
              <Label htmlFor="wp-end">Bitiş tarihi (dahil)</Label>
              <Input
                id="wp-end"
                type="date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value);
                  setOverlaps([]);
                  setAllowOverlap(false);
                }}
              />
            </div>
          </div>

          {/* Süre rozeti */}
          <div className="flex items-center gap-2 text-sm">
            <Clock className="size-4 text-muted-foreground" aria-hidden />
            <span>
              Süre:{" "}
              <b
                className={cn(
                  "tabular-nums",
                  validDays ? "text-cyan-700" : "text-rose-700",
                )}
              >
                {dayCount} gün
              </b>
              {!validDays ? (
                <span className="text-rose-700 ml-2 text-xs">
                  (1–14 gün arası olmalı)
                </span>
              ) : null}
            </span>
          </div>

          {/* Etiket (opsiyonel) */}
          <div>
            <Label htmlFor="wp-name">
              Etiket (opsiyonel){" "}
              <span className="text-[10px] text-muted-foreground normal-case">
                — Bayram Haftası, Yarıyıl Tatili vb.
              </span>
            </Label>
            <Input
              id="wp-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="örn. Bayram Sonrası Hafta"
              maxLength={120}
            />
          </div>

          {/* Çakışma uyarısı */}
          {overlaps.length > 0 ? (
            <div className="rounded-lg border-2 border-amber-300 bg-amber-50 p-3 text-sm">
              <p className="font-semibold text-amber-900 mb-2">
                Bu tarihler {overlaps.length} programla çakışıyor:
              </p>
              <ul className="space-y-1 text-amber-900">
                {overlaps.map((o) => (
                  <li
                    key={o.program_id}
                    className="text-xs flex items-center justify-between"
                  >
                    <span>
                      <b>{o.label}</b> ({o.start_date} → {o.end_date})
                    </span>
                    <span className="text-amber-800">
                      {o.overlap_days} gün, {o.task_count_in_overlap} görev
                    </span>
                  </li>
                ))}
              </ul>
              <label className="flex items-center gap-2 mt-3 text-xs text-amber-900">
                <input
                  type="checkbox"
                  checked={allowOverlap}
                  onChange={(e) => setAllowOverlap(e.target.checked)}
                />
                <span>Çakışmaya rağmen oluştur (eski programlar değişmez)</span>
              </label>
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-md border border-border hover:bg-muted"
          >
            Vazgeç
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={
              create.isPending ||
              !validDays ||
              (overlaps.length > 0 && !allowOverlap)
            }
            className="px-4 py-2 text-sm rounded-md bg-cyan-600 hover:bg-cyan-700 text-white inline-flex items-center gap-2 disabled:opacity-50"
          >
            {create.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <CalendarPlus className="size-3.5" aria-hidden />
            )}
            Oluştur
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
