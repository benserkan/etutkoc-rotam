"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CalendarClock,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Clock,
  Link2,
  Pencil,
  Plus,
  Repeat,
  Video,
  X,
  type LucideIcon,
} from "lucide-react";

import {
  appointmentKeys,
  getGoogleConnectUrl,
  getTeacherAppointments,
} from "@/lib/api/appointments";
import {
  useApproveAppointment,
  useCreateAppointment,
  useDisconnectGoogle,
  useRecordSession,
  useRejectAppointment,
  useReplaceAvailability,
  useSetAppointmentStatus,
  useUpdateAppointment,
  useUpdateSeries,
} from "@/lib/hooks/use-appointment-mutations";
import type {
  AppointmentItem,
  AvailabilityWindowItem,
  SeriesItem,
  TeacherAppointmentsResponse,
} from "@/lib/types/appointment";
import type { TeacherStudentListItem } from "@/lib/types/teacher";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/**
 * Koç görüşme takvimi — 2026-09-29 yeniden tasarım: özet şeridi + sıradaki
 * görüşme + haftalık ızgara + yan sütun (istekler, haftalık planlar,
 * uygunluk, Google). Tarayıcı istemleri (prompt/confirm) yerine diyaloglar.
 */

const WEEKDAYS = [
  "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
];
const MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

const STATUS_RAIL: Record<string, string> = {
  scheduled: "border-l-cyan-600",
  pending: "border-l-amber-500",
  cancelled: "border-l-slate-400 opacity-70",
  rejected: "border-l-slate-400 opacity-70",
  done: "border-l-emerald-600",
  no_show: "border-l-rose-600",
};

const STATUS_CHIP: Record<string, string> = {
  scheduled: "bg-cyan-700 text-white",
  pending: "bg-amber-500 text-slate-950",
  cancelled: "bg-slate-500 text-white",
  rejected: "bg-slate-500 text-white",
  done: "bg-emerald-600 text-white",
  no_show: "bg-rose-600 text-white",
};

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function mondayOf(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtShort(iso: string): string {
  const [, m, dd] = iso.split("-");
  return `${dd}.${m}`;
}

function fmtLong(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

function weekdayIdx(iso: string): number {
  return (new Date(`${iso}T12:00:00`).getDay() + 6) % 7;
}

function relDay(iso: string): string {
  const t = todayISO();
  if (iso === t) return "Bugün";
  if (iso === addDays(t, 1)) return "Yarın";
  return `${fmtLong(iso)} ${WEEKDAYS[weekdayIdx(iso)]}`;
}

interface Props {
  initial: TeacherAppointmentsResponse;
  students: TeacherStudentListItem[];
}

type ReasonAsk = {
  title: string;
  description: string;
  confirmLabel: string;
  danger?: boolean;
  withReason: boolean;
  onConfirm: (reason: string) => void;
} | null;

export function AppointmentsClient({ initial, students }: Props) {
  const thisMonday = mondayOf(todayISO());
  const [weekStart, setWeekStart] = React.useState(thisMonday);

  // Özet (bu hafta + gelecek hafta) — takvim nereye gidilirse gitsin sabit
  const home = useQuery<TeacherAppointmentsResponse>({
    queryKey: appointmentKeys.teacher("me", thisMonday),
    queryFn: () => getTeacherAppointments(thisMonday, addDays(thisMonday, 13)),
    initialData: initial,
    staleTime: 15_000,
  });
  const view = useQuery<TeacherAppointmentsResponse>({
    queryKey: appointmentKeys.teacher("me", weekStart),
    queryFn: () => getTeacherAppointments(weekStart, addDays(weekStart, 13)),
    enabled: weekStart !== thisMonday,
    staleTime: 15_000,
  });
  const homeData = home.data ?? initial;
  const viewData = weekStart === thisMonday ? homeData : (view.data ?? null);

  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const g = params.get("google");
    if (!g) return;
    if (g === "connected") toast.success("Google hesabın bağlandı — Meet linkleri artık otomatik oluşturulur");
    else if (g === "denied") toast.error("Google bağlantısı iptal edildi");
    else toast.error("Google bağlantısı tamamlanamadı — tekrar dene");
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  const [createOpen, setCreateOpen] = React.useState(false);
  const [availOpen, setAvailOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<AppointmentItem | null>(null);
  const [recording, setRecording] = React.useState<AppointmentItem | null>(null);
  const [seriesTime, setSeriesTime] = React.useState<SeriesItem | null>(null);
  const [ask, setAsk] = React.useState<ReasonAsk>(null);

  const today = todayISO();
  const upcoming = homeData.items
    .filter((a) => a.status === "scheduled" && !a.is_past)
    .sort((a, b) => (a.date + a.start_time).localeCompare(b.date + b.start_time));
  const next = upcoming[0] ?? null;
  const thisWeekEnd = addDays(thisMonday, 6);
  const weekPlanned = homeData.items.filter(
    (a) => a.status === "scheduled" && a.date >= thisMonday && a.date <= thisWeekEnd,
  ).length;
  const toRecord = homeData.items.filter(
    (a) => !a.session_id && ((a.status === "scheduled" && a.is_past) || a.status === "done" || a.status === "no_show"),
  );

  const days = React.useMemo(() => {
    const out: { date: string; items: AppointmentItem[] }[] = [];
    for (let i = 0; i < 7; i++) {
      const d = addDays(weekStart, i);
      out.push({
        date: d,
        items: (viewData?.items ?? [])
          .filter((a) => a.date === d)
          .sort((a, b) => a.start_time.localeCompare(b.start_time)),
      });
    }
    return out;
  }, [weekStart, viewData]);
  const viewCount = days.reduce((n, d) => n + d.items.filter((a) => a.status === "scheduled").length, 0);

  const cardActions = {
    onEdit: setEditing,
    onRecord: setRecording,
    onAsk: setAsk,
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <Video className="size-6 text-cyan-700 dark:text-cyan-400" aria-hidden />
            Görüşmeler
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Online koçluk görüşmelerini planla; öğrenci ve veli otomatik bilgilendirilir,
            görüşmeden önce hatırlatma gider.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setAvailOpen(true)}>
            <Clock className="mr-1.5 size-4" aria-hidden />
            Uygunluk saatleri
          </Button>
          <Button
            className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white"
            onClick={() => setCreateOpen(true)}
            data-testid="appt-new"
          >
            <Plus className="mr-1.5 size-4" aria-hidden />
            Yeni görüşme
          </Button>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard icon={CalendarDays} chip="bg-cyan-700 text-white" label="Bu hafta planlı"
          value={weekPlanned} unit="görüşme" />
        <StatCard icon={CalendarClock} chip={homeData.pending.length > 0 ? "bg-amber-500 text-slate-950" : "bg-slate-600 text-white"}
          label="Onay bekleyen istek" value={homeData.pending.length} unit="istek" />
        <StatCard icon={ClipboardCheck} chip={toRecord.length > 0 ? "bg-rose-600 text-white" : "bg-slate-600 text-white"}
          label="Kaydı bekleyen seans" value={toRecord.length} unit="görüşme (bu hafta)" />
      </section>

      <NextCard next={next} onRecord={setRecording} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_340px]">
        <section className="rounded-xl border border-border bg-card shadow-sm" data-section="appointments:calendar">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
            <div>
              <p className="text-sm font-semibold">
                {fmtLong(weekStart)} – {fmtLong(addDays(weekStart, 6))}
              </p>
              <p className="text-xs text-muted-foreground">
                {viewData ? `${viewCount} planlı görüşme` : "Yükleniyor…"}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <Button variant="outline" size="sm" onClick={() => setWeekStart((w) => addDays(w, -7))} aria-label="Önceki hafta">
                <ChevronLeft className="size-4" aria-hidden />
              </Button>
              <Button variant="outline" size="sm" onClick={() => setWeekStart(thisMonday)} disabled={weekStart === thisMonday}>
                Bu hafta
              </Button>
              <Button variant="outline" size="sm" onClick={() => setWeekStart((w) => addDays(w, 7))} aria-label="Sonraki hafta">
                <ChevronRight className="size-4" aria-hidden />
              </Button>
            </div>
          </div>
          <div className="divide-y divide-border">
            {days.map(({ date, items }) => (
              <DayColumn key={date} date={date} items={items} isToday={date === today} {...cardActions} />
            ))}
          </div>
        </section>

        <aside className="space-y-4">
          <PendingPanel pending={homeData.pending} onAsk={setAsk} />
          <SeriesPanel series={homeData.series} onTime={setSeriesTime} onAsk={setAsk} />
          <AvailabilitySummary windows={homeData.availability} onEdit={() => setAvailOpen(true)} />
          <GoogleCard google={homeData.google} onAsk={setAsk} />
        </aside>
      </div>

      <CreateDialog open={createOpen} onClose={() => setCreateOpen(false)} students={students} />
      <AvailabilityDialog open={availOpen} onClose={() => setAvailOpen(false)} initial={homeData.availability} />
      {editing && <EditDialog appt={editing} onClose={() => setEditing(null)} />}
      {recording && <RecordSessionDialog appt={recording} onClose={() => setRecording(null)} />}
      {seriesTime && <SeriesTimeDialog series={seriesTime} onClose={() => setSeriesTime(null)} />}
      {ask && <AskDialog ask={ask} onClose={() => setAsk(null)} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Özet kartları
// ---------------------------------------------------------------------------

function StatCard({ icon: Icon, chip, label, value, unit }: {
  icon: LucideIcon; chip: string; label: string; value: number; unit: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-sm">
      <span className={cn("grid size-10 shrink-0 place-items-center rounded-lg", chip)}>
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold tabular-nums leading-tight">
          {value} <span className="text-sm font-medium text-muted-foreground">{unit}</span>
        </p>
      </div>
    </div>
  );
}

function NextCard({ next, onRecord }: { next: AppointmentItem | null; onRecord: (a: AppointmentItem) => void }) {
  if (!next) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card px-5 py-4 text-sm text-muted-foreground">
        Önümüzdeki iki haftada planlı görüşme yok. “Yeni görüşme” ile plan yapabilirsin.
      </div>
    );
  }
  return (
    <div
      className="flex flex-wrap items-center gap-4 rounded-xl bg-gradient-to-r from-cyan-800 to-cyan-600 px-5 py-4 text-white shadow-sm"
      data-testid="appt-next"
    >
      <div className="grid size-14 shrink-0 place-items-center rounded-xl bg-white/15 text-center">
        <span className="text-lg font-bold leading-none">{next.start_time}</span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wider text-cyan-100">Sıradaki görüşme</p>
        <p className="break-words text-lg font-semibold">{next.student_name}</p>
        <p className="text-sm text-cyan-50">
          {relDay(next.date)} · {next.start_time} · {next.duration_min} dakika
          {next.series_id ? " · her hafta" : ""}
        </p>
        {next.note ? <p className="mt-0.5 text-sm text-cyan-50">Not: {next.note}</p> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {next.meeting_link ? (
          <a
            href={next.meeting_link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-cyan-900 hover:bg-cyan-50"
          >
            <Video className="size-4" aria-hidden />
            Görüşmeye katıl
          </a>
        ) : (
          <span className="rounded-lg bg-white/15 px-3 py-2 text-xs text-white">
            Görüşme linki eklenmemiş
          </span>
        )}
        <Link
          href={`/teacher/students/${next.student_id}`}
          className="inline-flex items-center rounded-lg border border-white/40 px-3 py-2 text-sm font-medium text-white hover:bg-white/10"
        >
          Öğrenci profili
        </Link>
        {next.is_past ? (
          <button type="button" onClick={() => onRecord(next)}
            className="rounded-lg border border-white/40 px-3 py-2 text-sm font-medium text-white hover:bg-white/10">
            Seansı kaydet
          </button>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Takvim
// ---------------------------------------------------------------------------

type CardActions = {
  onEdit: (a: AppointmentItem) => void;
  onRecord: (a: AppointmentItem) => void;
  onAsk: (a: ReasonAsk) => void;
};

function DayColumn({ date, items, isToday, ...actions }: {
  date: string; items: AppointmentItem[]; isToday: boolean;
} & CardActions) {
  const past = date < todayISO();
  return (
    <div
      className={cn(
        "flex flex-col gap-2 px-4 py-3 sm:flex-row sm:gap-4",
        isToday && "bg-cyan-50/70 dark:bg-cyan-500/10",
        past && !isToday && "bg-muted/30",
      )}
      data-testid="appt-day"
    >
      <div className="shrink-0 sm:w-32">
        <p className={cn("text-xs font-semibold uppercase tracking-wide",
          isToday ? "text-cyan-800 dark:text-cyan-300" : "text-muted-foreground")}>
          {WEEKDAYS[weekdayIdx(date)]}{isToday ? " · Bugün" : ""}
        </p>
        <p className={cn("text-sm font-semibold", isToday && "text-cyan-800 dark:text-cyan-300")}>
          {fmtLong(date)}
        </p>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground/70 sm:self-center">Görüşme yok</p>
      ) : (
        <div className="grid min-w-0 flex-1 grid-cols-1 gap-2 md:grid-cols-2 2xl:grid-cols-3">
          {items.map((a) => <AppointmentCard key={a.id} appt={a} {...actions} />)}
        </div>
      )}
    </div>
  );
}

function AppointmentCard({ appt, onEdit, onRecord, onAsk }: { appt: AppointmentItem } & CardActions) {
  const setStatus = useSetAppointmentStatus();
  const active = appt.status === "scheduled" || appt.status === "pending";
  const needsRecord = !appt.session_id && ((appt.status === "scheduled" && appt.is_past) || appt.status === "done" || appt.status === "no_show");
  return (
    <div className={cn("rounded-lg border border-border border-l-4 bg-card p-2.5 shadow-sm", STATUS_RAIL[appt.status])}
      data-testid="appt-card">
      <div className="flex flex-wrap items-center justify-between gap-1">
        <span className="text-base font-bold tabular-nums">{appt.start_time}</span>
        <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", STATUS_CHIP[appt.status])}>
          {appt.status_label}
        </span>
      </div>
      <Link href={`/teacher/students/${appt.student_id}`} className="mt-0.5 block break-words text-sm font-medium hover:underline">
        {appt.student_name}
      </Link>
      <p className="text-xs text-muted-foreground">
        {appt.duration_min} dk
        {appt.series_id ? (
          <span className="ml-1 inline-flex items-center gap-0.5"><Repeat className="size-3" aria-hidden /> her hafta</span>
        ) : null}
      </p>
      {appt.note ? <p className="mt-1 break-words text-xs text-muted-foreground">{appt.note}</p> : null}
      {appt.cancel_reason ? <p className="mt-1 break-words text-xs text-muted-foreground">Sebep: {appt.cancel_reason}</p> : null}
      <div className="mt-2 flex flex-wrap gap-1">
        {appt.meeting_link && active && !appt.is_past ? (
          <a href={appt.meeting_link} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-md bg-cyan-700 px-2 py-1 text-xs font-semibold text-white hover:bg-cyan-800">
            <Video className="size-3" aria-hidden /> Katıl
          </a>
        ) : null}
        {appt.session_id ? (
          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2 py-1 text-xs font-semibold text-white">
            <Check className="size-3" aria-hidden /> Seans kaydedildi
          </span>
        ) : needsRecord ? (
          <button type="button" onClick={() => onRecord(appt)}
            className="rounded-md bg-rose-600 px-2 py-1 text-xs font-semibold text-white hover:bg-rose-700">
            Seansı kaydet
          </button>
        ) : null}
        {appt.status === "scheduled" && !appt.is_past ? (
          <>
            <button type="button" onClick={() => onEdit(appt)} aria-label="Düzenle"
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium hover:bg-muted">
              <Pencil className="size-3" aria-hidden /> Düzenle
            </button>
            <button type="button" disabled={setStatus.isPending}
              onClick={() => onAsk({
                title: "Görüşmeyi iptal et",
                description: `${appt.student_name} · ${relDay(appt.date)} ${appt.start_time}. Öğrenci ve veliye iptal bildirimi gider.`,
                confirmLabel: "Görüşmeyi iptal et",
                danger: true,
                withReason: true,
                onConfirm: (reason) => setStatus.mutate({ apptId: appt.id, status: "cancelled", reason: reason || undefined }),
              })}
              className="rounded-md border border-border px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10">
              İptal
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Yan sütun
// ---------------------------------------------------------------------------

function Panel({ icon: Icon, title, children, action }: {
  icon: LucideIcon; title: string; children: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
          <Icon className="size-4 text-cyan-700 dark:text-cyan-400" aria-hidden />
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function PendingPanel({ pending, onAsk }: { pending: AppointmentItem[]; onAsk: (a: ReasonAsk) => void }) {
  const approve = useApproveAppointment();
  const reject = useRejectAppointment();
  return (
    <Panel icon={CalendarClock} title={`Görüşme istekleri (${pending.length})`}>
      {pending.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Bekleyen istek yok. Öğrenciler uygunluk saatlerinden görüşme isteyebilir.
        </p>
      ) : (
        <ul className="space-y-2" data-testid="appt-pending">
          {pending.map((p) => (
            <li key={p.id} className="rounded-lg border border-amber-300 border-l-4 border-l-amber-500 p-2.5 dark:border-amber-500/40">
              <p className="break-words text-sm font-semibold">{p.student_name}</p>
              <p className="text-xs text-muted-foreground">
                {relDay(p.date)} · {p.start_time} · {p.duration_min} dk
              </p>
              {p.request_note ? (
                <p className="mt-1 break-words rounded-md bg-muted/60 px-2 py-1 text-xs">“{p.request_note}”</p>
              ) : null}
              <div className="mt-2 flex gap-1.5">
                <Button size="sm" className="h-7 bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white"
                  disabled={approve.isPending} onClick={() => approve.mutate({ apptId: p.id })}>
                  <Check className="mr-1 size-3.5" aria-hidden /> Onayla
                </Button>
                <Button size="sm" variant="outline" className="h-7" disabled={reject.isPending}
                  onClick={() => onAsk({
                    title: "Görüşme isteğini reddet",
                    description: `${p.student_name} · ${relDay(p.date)} ${p.start_time}. Sebep öğrenciye iletilir.`,
                    confirmLabel: "Reddet",
                    danger: true,
                    withReason: true,
                    onConfirm: (reason) => reject.mutate({ apptId: p.id, reason: reason || undefined }),
                  })}>
                  <X className="mr-1 size-3.5" aria-hidden /> Reddet
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function SeriesPanel({ series, onTime, onAsk }: {
  series: SeriesItem[]; onTime: (s: SeriesItem) => void; onAsk: (a: ReasonAsk) => void;
}) {
  const update = useUpdateSeries();
  return (
    <Panel icon={Repeat} title="Haftalık görüşme planları">
      {series.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Sabit gün/saatli görüşme yok. Yeni görüşmede “Her hafta tekrarla”yı seçersen
          sistem randevuyu her hafta kendiliğinden oluşturur.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {series.map((s) => (
            <li key={s.id} className="py-2">
              <p className="break-words text-sm font-medium">{s.student_name}</p>
              <p className="text-xs text-muted-foreground">
                Her {s.weekday_label} {s.start_time} · {s.duration_min} dk
                {s.link_source === "google" ? " · Meet otomatik" : s.meeting_link ? " · link var" : ""}
              </p>
              <div className="mt-1.5 flex gap-1.5">
                <button type="button" onClick={() => onTime(s)} disabled={update.isPending}
                  className="rounded-md border border-border px-2 py-1 text-xs font-medium hover:bg-muted">
                  Saati değiştir
                </button>
                <button type="button" disabled={update.isPending}
                  onClick={() => onAsk({
                    title: "Haftalık planı kapat",
                    description: `${s.student_name} ile her ${s.weekday_label} ${s.start_time} görüşmesi kapatılır; gelecekteki planlı görüşmeler iptal edilir.`,
                    confirmLabel: "Planı kapat",
                    danger: true,
                    withReason: false,
                    onConfirm: () => update.mutate({ seriesId: s.id, active: false }),
                  })}
                  className="rounded-md border border-border px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10">
                  Kapat
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function AvailabilitySummary({ windows, onEdit }: { windows: AvailabilityWindowItem[]; onEdit: () => void }) {
  const sorted = [...windows].sort((a, b) => a.weekday - b.weekday || a.start_time.localeCompare(b.start_time));
  return (
    <Panel icon={Clock} title="Uygunluk saatlerin"
      action={<button type="button" onClick={onEdit} className="text-xs font-medium text-cyan-700 hover:underline dark:text-cyan-400">Düzenle</button>}>
      {sorted.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Tanımlı değil — öğrenciler görüşme isteyemez, görüşmeleri yalnız sen planlarsın.
        </p>
      ) : (
        <ul className="space-y-1 text-xs">
          {sorted.map((w, i) => (
            <li key={i} className="flex justify-between gap-2">
              <span className="font-medium">{WEEKDAYS[w.weekday]}</span>
              <span className="text-muted-foreground">{w.start_time}–{w.end_time} · {w.slot_minutes} dk</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function GoogleCard({ google, onAsk }: {
  google: TeacherAppointmentsResponse["google"]; onAsk: (a: ReasonAsk) => void;
}) {
  const disconnect = useDisconnectGoogle();
  const [loading, setLoading] = React.useState(false);
  if (!google.configured) return null;

  async function connect() {
    setLoading(true);
    try {
      const { url } = await getGoogleConnectUrl();
      window.location.href = url;
    } catch {
      toast.error("Bağlantı adresi alınamadı — tekrar dene");
      setLoading(false);
    }
  }

  return (
    <Panel icon={Link2} title="Google Meet bağlantısı">
      {google.connected ? (
        <>
          <p className="break-words text-xs text-muted-foreground">
            {google.email ?? "Bağlı"} — yeni randevulara Meet linki otomatik eklenir.
          </p>
          {google.last_error ? (
            <p className="mt-1 break-words text-xs text-rose-700 dark:text-rose-400">Son hata: {google.last_error}</p>
          ) : null}
          <Button variant="outline" size="sm" className="mt-2" disabled={disconnect.isPending}
            onClick={() => onAsk({
              title: "Google bağlantısını kaldır",
              description: "Mevcut linkler silinmez; yeni randevularda otomatik Meet linki üretilmez.",
              confirmLabel: "Bağlantıyı kaldır",
              danger: true,
              withReason: false,
              onConfirm: () => disconnect.mutate(),
            })}>
            Bağlantıyı kaldır
          </Button>
        </>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            Google hesabını bağlarsan görüşme linkleri senin hesabından otomatik oluşturulur
            (ücretsiz Gmail yeterli). Bağlamazsan linki elle yapıştırabilirsin.
          </p>
          <Button size="sm" className="mt-2 bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white"
            onClick={connect} disabled={loading}>
            {loading ? "Yönlendiriliyor…" : "Google ile bağlan"}
          </Button>
        </>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Onay / gerekçe diyaloğu + seri saati
// ---------------------------------------------------------------------------

function AskDialog({ ask, onClose }: { ask: NonNullable<ReasonAsk>; onClose: () => void }) {
  const [reason, setReason] = React.useState("");
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{ask.title}</DialogTitle>
          <DialogDescription>{ask.description}</DialogDescription>
        </DialogHeader>
        {ask.withReason ? (
          <label className="block text-sm">
            <span className="font-medium">Sebep (isteğe bağlı)</span>
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3}
              data-testid="ask-reason"
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm" />
          </label>
        ) : null}
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="outline" onClick={onClose}>Vazgeç</Button>
          <Button type="button" data-testid="ask-confirm"
            className={cn("text-white hover:text-white", ask.danger ? "bg-rose-600 hover:bg-rose-700" : "bg-cyan-700 hover:bg-cyan-800")}
            onClick={() => { ask.onConfirm(reason.trim()); onClose(); }}>
            {ask.confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function SeriesTimeDialog({ series, onClose }: { series: SeriesItem; onClose: () => void }) {
  const update = useUpdateSeries();
  const [time, setTime] = React.useState(series.start_time);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Haftalık görüşme saati</DialogTitle>
          <DialogDescription>
            {series.student_name} · her {series.weekday_label}. Gelecekteki planlı görüşmeler yeni saate taşınır.
          </DialogDescription>
        </DialogHeader>
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="outline" onClick={onClose}>Vazgeç</Button>
          <Button type="button" disabled={!time || time === series.start_time || update.isPending}
            className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white"
            onClick={() => update.mutate({ seriesId: series.id, start_time: time }, { onSuccess: onClose })}>
            Kaydet
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Yeni görüşme dialogu
// ---------------------------------------------------------------------------

function CreateDialog({
  open,
  onClose,
  students,
}: {
  open: boolean;
  onClose: () => void;
  students: TeacherStudentListItem[];
}) {
  const create = useCreateAppointment();
  const [studentId, setStudentId] = React.useState<string>("");
  const [date, setDate] = React.useState("");
  const [time, setTime] = React.useState("17:00");
  const [duration, setDuration] = React.useState(40);
  const [link, setLink] = React.useState("");
  const [note, setNote] = React.useState("");
  const [weekly, setWeekly] = React.useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!studentId || !date || !time) {
      toast.error("Öğrenci, tarih ve saat zorunlu");
      return;
    }
    create.mutate(
      {
        student_id: Number(studentId),
        date,
        start_time: time,
        duration_min: duration,
        meeting_link: link.trim() || undefined,
        note: note.trim() || undefined,
        weekly,
      },
      { onSuccess: () => onClose() },
    );
  }

  const activeStudents = students.filter((s) => s.is_active);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Yeni görüşme planla</DialogTitle>
          <DialogDescription>
            Öğrenci ve velisi otomatik bilgilendirilir; görüşmeden önce
            hatırlatma gider.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm">
            <span className="font-medium">Öğrenci</span>
            <select
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              required
            >
              <option value="">Seç…</option>
              {activeStudents.map((s) => (
                <option key={s.id} value={s.id}>{s.full_name}</option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="font-medium">Tarih</span>
              <input
                type="date" value={date}
                onChange={(e) => setDate(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                required
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium">Saat</span>
              <input
                type="time" value={time}
                onChange={(e) => setTime(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                required
              />
            </label>
          </div>
          <label className="block text-sm">
            <span className="font-medium">Süre</span>
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {[30, 40, 50, 60, 90].map((m) => (
                <option key={m} value={m}>{m} dakika</option>
              ))}
            </select>
          </label>
          <label className="flex items-start gap-2 text-sm rounded-lg border border-border px-3 py-2.5 cursor-pointer">
            <input
              type="checkbox" checked={weekly}
              onChange={(e) => setWeekly(e.target.checked)}
              className="size-4 mt-0.5 accent-cyan-700"
            />
            <span>
              <span className="font-medium inline-flex items-center gap-1">
                <Repeat className="size-3.5" aria-hidden /> Her hafta tekrarla
              </span>
              <span className="block text-xs text-muted-foreground">
                Seçilen gün ve saatte sistem her hafta randevuyu kendiliğinden
                oluşturur.
              </span>
            </span>
          </label>
          <label className="block text-sm">
            <span className="font-medium">Görüşme linki (isteğe bağlı)</span>
            <input
              type="url" value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="https://meet.google.com/… veya Zoom linki"
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
            <span className="block text-xs text-muted-foreground mt-1">
              Boş bırakırsan: Google bağlıysa Meet linki otomatik oluşturulur;
              değilse sonradan ekleyebilirsin.
            </span>
          </label>
          <label className="block text-sm">
            <span className="font-medium">Not (isteğe bağlı)</span>
            <input
              type="text" value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Örn. deneme analizini konuşacağız"
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" onClick={onClose}>
              Vazgeç
            </Button>
            <Button
              type="submit"
              className="bg-cyan-700 hover:bg-cyan-800 text-white hover:text-white"
              disabled={create.isPending}
            >
              {create.isPending ? "Kaydediliyor…" : "Planla"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Randevu düzenleme dialogu
// ---------------------------------------------------------------------------

function EditDialog({
  appt,
  onClose,
}: {
  appt: AppointmentItem;
  onClose: () => void;
}) {
  const update = useUpdateAppointment(appt.id);
  const [date, setDate] = React.useState(appt.date);
  const [time, setTime] = React.useState(appt.start_time);
  const [duration, setDuration] = React.useState(appt.duration_min);
  const [link, setLink] = React.useState(appt.meeting_link ?? "");
  const [note, setNote] = React.useState(appt.note ?? "");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    update.mutate(
      {
        date,
        start_time: time,
        duration_min: duration,
        meeting_link: link.trim() || "",
        note,
      },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Görüşmeyi düzenle — {appt.student_name}</DialogTitle>
          <DialogDescription>
            Saat değişirse öğrenci ve veliye güncelleme bildirimi gider.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="font-medium">Tarih</span>
              <input
                type="date" value={date}
                onChange={(e) => setDate(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium">Saat</span>
              <input
                type="time" value={time}
                onChange={(e) => setTime(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
          </div>
          <label className="block text-sm">
            <span className="font-medium">Süre</span>
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {[30, 40, 50, 60, 90].map((m) => (
                <option key={m} value={m}>{m} dakika</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium">Görüşme linki</span>
            <input
              type="url" value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="https://…"
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium">Not</span>
            <input
              type="text" value={note}
              onChange={(e) => setNote(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" onClick={onClose}>
              Vazgeç
            </Button>
            <Button
              type="submit"
              className="bg-cyan-700 hover:bg-cyan-800 text-white hover:text-white"
              disabled={update.isPending}
            >
              {update.isPending ? "Kaydediliyor…" : "Kaydet"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// F4 — Seansı kaydet dialogu (randevu → KS1 seans + KS2 tahsilat)
// ---------------------------------------------------------------------------

function RecordSessionDialog({
  appt,
  onClose,
}: {
  appt: AppointmentItem;
  onClose: () => void;
}) {
  const record = useRecordSession();
  const [outcome, setOutcome] = React.useState<"done" | "no_show">("done");
  const [agenda, setAgenda] = React.useState("");
  const [note, setNote] = React.useState("");
  const [mood, setMood] = React.useState<string>("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (outcome === "done" && !agenda.trim()) {
      toast.error("Yapılan seans için gündem (ne konuşuldu) zorunlu");
      return;
    }
    record.mutate(
      {
        apptId: appt.id,
        outcome,
        agenda: agenda.trim() || undefined,
        coach_note: note.trim() || undefined,
        mood: mood ? Number(mood) : undefined,
      },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Seansı kaydet — {appt.student_name}</DialogTitle>
          <DialogDescription>
            {fmtShort(appt.date)} {appt.weekday_label} {appt.start_time} görüşmesi
            seans kaydına dönüşür; yapılan seans tahsilat panosuna otomatik işlenir.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setOutcome("done")}
              className={cn(
                "rounded-lg border px-3 py-2.5 text-sm font-semibold transition-colors",
                outcome === "done"
                  ? "border-emerald-600 bg-emerald-600 text-white"
                  : "border-border bg-background hover:bg-muted",
              )}
            >
              Yapıldı
            </button>
            <button
              type="button"
              onClick={() => setOutcome("no_show")}
              className={cn(
                "rounded-lg border px-3 py-2.5 text-sm font-semibold transition-colors",
                outcome === "no_show"
                  ? "border-rose-600 bg-rose-600 text-white"
                  : "border-border bg-background hover:bg-muted",
              )}
            >
              Öğrenci gelmedi
            </button>
          </div>
          {outcome === "done" && (
            <>
              <label className="block text-sm">
                <span className="font-medium">Gündem — ne konuşuldu?</span>
                <textarea
                  value={agenda}
                  onChange={(e) => setAgenda(e.target.value)}
                  rows={3}
                  placeholder="Örn. deneme analizi + haftalık plan + motivasyon"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  required
                />
              </label>
              <label className="block text-sm">
                <span className="font-medium">Görüşme notu (isteğe bağlı)</span>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </label>
              <label className="block text-sm">
                <span className="font-medium">Öğrencinin ruh hali (isteğe bağlı)</span>
                <select
                  value={mood}
                  onChange={(e) => setMood(e.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="">Seçme</option>
                  <option value="1">1 — Çok düşük</option>
                  <option value="2">2 — Düşük</option>
                  <option value="3">3 — Orta</option>
                  <option value="4">4 — İyi</option>
                  <option value="5">5 — Çok iyi</option>
                </select>
              </label>
            </>
          )}
          {outcome === "no_show" && (
            <p className="text-xs text-muted-foreground rounded-lg border border-border px-3 py-2.5">
              &quot;Gelmedi&quot; kaydı iz bırakır ama tahsilata SAYILMAZ. İstersen
              not ekleyebilirsin.
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" onClick={onClose}>
              Vazgeç
            </Button>
            <Button
              type="submit"
              className="bg-cyan-700 hover:bg-cyan-800 text-white hover:text-white"
              disabled={record.isPending}
            >
              {record.isPending ? "Kaydediliyor…" : "Kaydet"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Uygunluk saatleri dialogu
// ---------------------------------------------------------------------------

function AvailabilityDialog({
  open,
  onClose,
  initial,
}: {
  open: boolean;
  onClose: () => void;
  initial: AvailabilityWindowItem[];
}) {
  const save = useReplaceAvailability();
  const [rows, setRows] = React.useState<AvailabilityWindowItem[]>(initial);

  // Dialog her açıldığında sunucu değerleriyle tazele
  const wasOpen = React.useRef(false);
  React.useEffect(() => {
    if (open && !wasOpen.current) setRows(initial);
    wasOpen.current = open;
  }, [open, initial]);

  function setRow(i: number, patch: Partial<AvailabilityWindowItem>) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    save.mutate({ windows: rows }, { onSuccess: () => onClose() });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Uygunluk saatleri</DialogTitle>
          <DialogDescription>
            Öğrencilerin görüşme isteyebileceği saat aralıkları. Boş bırakırsan
            öğrenciler saat seçemez — görüşmeleri yalnız sen planlarsın.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {rows.length === 0 && (
              <div className="text-sm text-muted-foreground rounded-lg border border-dashed border-border px-3 py-4 text-center">
                Henüz pencere yok — &quot;Aralık ekle&quot; ile başla.
              </div>
            )}
            {rows.map((r, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-border px-3 py-2">
                <select
                  value={r.weekday}
                  onChange={(e) => setRow(i, { weekday: Number(e.target.value) })}
                  className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                  aria-label="Gün"
                >
                  {WEEKDAYS.map((w, idx) => (
                    <option key={idx} value={idx}>{w}</option>
                  ))}
                </select>
                <input
                  type="time" value={r.start_time}
                  onChange={(e) => setRow(i, { start_time: e.target.value })}
                  className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                  aria-label="Başlangıç"
                />
                <span className="text-xs text-muted-foreground">–</span>
                <input
                  type="time" value={r.end_time}
                  onChange={(e) => setRow(i, { end_time: e.target.value })}
                  className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                  aria-label="Bitiş"
                />
                <select
                  value={r.slot_minutes}
                  onChange={(e) => setRow(i, { slot_minutes: Number(e.target.value) })}
                  className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                  aria-label="Görüşme süresi"
                >
                  {[30, 40, 50, 60].map((m) => (
                    <option key={m} value={m}>{m} dk</option>
                  ))}
                </select>
                <Button
                  type="button" variant="ghost" size="sm"
                  className="h-8 px-2 text-rose-700 dark:text-rose-400 ml-auto"
                  onClick={() => setRows((rs) => rs.filter((_, idx) => idx !== i))}
                  aria-label="Aralığı sil"
                >
                  <X className="size-4" aria-hidden />
                </Button>
              </div>
            ))}
          </div>
          <Button
            type="button" variant="outline" size="sm"
            onClick={() =>
              setRows((rs) => [
                ...rs,
                { weekday: 0, start_time: "16:00", end_time: "20:00", slot_minutes: 40 },
              ])
            }
          >
            <Plus className="size-4 mr-1" aria-hidden />
            Aralık ekle
          </Button>
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" onClick={onClose}>
              Vazgeç
            </Button>
            <Button
              type="submit"
              className="bg-cyan-700 hover:bg-cyan-800 text-white hover:text-white"
              disabled={save.isPending}
            >
              {save.isPending ? "Kaydediliyor…" : "Kaydet"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
