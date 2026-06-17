"use client";

import * as React from "react";
import Link from "next/link";
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
  Microscope,
  Printer,
  Rocket,
  Sparkles,
} from "lucide-react";

import {
  useCreateProgram,
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

  const draftTotal = data.week_draft_total ?? 0;

  // WP3 — Program-aware: aktif program + dialog state
  const [newProgramOpen, setNewProgramOpen] = React.useState(false);
  // Veliye duyur — gönderim öncesi önizleme modalı
  const [announceOpen, setAnnounceOpen] = React.useState(false);
  const [programsDropdownOpen, setProgramsDropdownOpen] = React.useState(false);
  const currentProgramId = data.current_program_id ?? null;
  const currentProgramName = data.current_program_name;
  const currentProgramDayCount = data.current_program_day_count;
  const allPrograms = data.programs ?? [];
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
              <p className="text-sm text-muted-foreground">
                {data.start_date} → {data.end_date}
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
            />
          ) : null}
          <Link
            href={`/teacher/students/${studentId}/diagnostics`}
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted inline-flex items-center gap-1.5"
            title="Öneri motorunun sayısal iç durumunu gör"
          >
            <Microscope className="size-4" aria-hidden />
            Tanı
          </Link>
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
        days={data.days}
        subjects={subjectsForGrouping}
        openDate={openDate}
        onOpenDay={(date) => {
          setOpenDate(date);
          if (typeof window !== "undefined") {
            window.requestAnimationFrame(() => {
              document
                .getElementById(`day-${date}`)
                ?.scrollIntoView({ behavior: "smooth", block: "start" });
            });
          }
        }}
      />

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
              subjects={subjectsForGrouping}
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
          <CarryoverPanel studentId={studentId} />
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
      </div>

      <BookGridModal
        open={gridBookId !== null}
        onOpenChange={(o) => {
          if (!o) setGridBookId(null);
        }}
        studentId={studentId}
        bookId={gridBookId}
      />

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
}: {
  studentId: number;
  programs: WeeklyProgramItem[];
  currentProgramId: number | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
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
              <Link
                key={p.id}
                href={`/teacher/students/${studentId}/week?program_id=${p.id}`}
                onClick={() => onOpenChange(false)}
                className={cn(
                  "block px-3 py-2 rounded text-sm hover:bg-muted",
                  isCurrent && "bg-cyan-50 border border-cyan-200",
                )}
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
                  {p.start_date} → {p.end_date} · {p.day_count} gün
                </div>
              </Link>
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
              "Eski görevleri tek tık ile 'Eski Dönem' programına bağlayabilirim."
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
        onSuccess: () => onClose(),
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
