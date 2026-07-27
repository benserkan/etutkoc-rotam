"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CalendarClock,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  Link2,
  Pencil,
  Plus,
  Repeat,
  Video,
  X,
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
 * Koç görüşme takvimi — 14 günlük görünüm + bekleyen istekler + haftalık
 * planlar + uygunluk saatleri + Google Meet bağlantısı.
 */

const WEEKDAYS = [
  "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
];

const STATUS_TONE: Record<string, string> = {
  scheduled: "border-l-cyan-500 bg-cyan-50 dark:bg-cyan-500/10",
  pending: "border-l-amber-500 bg-amber-50 dark:bg-amber-500/10",
  cancelled: "border-l-slate-300 bg-slate-50 dark:bg-slate-500/10 opacity-70",
  rejected: "border-l-slate-300 bg-slate-50 dark:bg-slate-500/10 opacity-70",
  done: "border-l-emerald-500 bg-emerald-50 dark:bg-emerald-500/10",
  no_show: "border-l-rose-500 bg-rose-50 dark:bg-rose-500/10",
};

const STATUS_CHIP: Record<string, string> = {
  scheduled: "bg-cyan-100 text-cyan-900 dark:bg-cyan-500/20 dark:text-cyan-200",
  pending: "bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-200",
  cancelled: "bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300",
  rejected: "bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300",
  done: "bg-emerald-100 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200",
  no_show: "bg-rose-100 text-rose-900 dark:bg-rose-500/20 dark:text-rose-200",
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

interface Props {
  initial: TeacherAppointmentsResponse;
  students: TeacherStudentListItem[];
}

export function AppointmentsClient({ initial, students }: Props) {
  const [weekStart, setWeekStart] = React.useState(() => mondayOf(todayISO()));
  const isDefaultRange = weekStart === mondayOf(todayISO());

  const q = useQuery<TeacherAppointmentsResponse>({
    queryKey: appointmentKeys.teacher("me", weekStart),
    queryFn: () => getTeacherAppointments(weekStart, addDays(weekStart, 13)),
    initialData: isDefaultRange ? initial : undefined,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;

  // Google OAuth dönüş bildirimi (?google=connected|error|denied)
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

  const days = React.useMemo(() => {
    const out: { date: string; items: AppointmentItem[] }[] = [];
    for (let i = 0; i < 14; i++) {
      const d = addDays(weekStart, i);
      out.push({ date: d, items: data.items.filter((a) => a.date === d) });
    }
    return out;
  }, [weekStart, data.items]);

  const activeCount = data.items.filter((a) => a.status === "scheduled").length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold inline-flex items-center gap-2">
            <Video className="size-5 text-cyan-700" aria-hidden />
            Görüşmeler
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-xl">
            Online koçluk görüşmelerini planla; öğrenci ve veli otomatik
            bilgilendirilir, görüşmeden önce hatırlatma gider.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setAvailOpen(true)}>
            <Clock className="size-4 mr-1.5" aria-hidden />
            Uygunluk saatleri
          </Button>
          <Button
            className="bg-cyan-700 hover:bg-cyan-800 text-white hover:text-white"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="size-4 mr-1.5" aria-hidden />
            Yeni görüşme
          </Button>
        </div>
      </div>

      <GoogleCard google={data.google} />

      {data.pending.length > 0 && (
        <PendingBand pending={data.pending} />
      )}

      {/* Takvim gezgini */}
      <div className="rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="text-sm font-semibold inline-flex items-center gap-2">
            <CalendarDays className="size-4 text-cyan-700" aria-hidden />
            {fmtShort(weekStart)} – {fmtShort(addDays(weekStart, 13))}
            <span className="text-xs font-normal text-muted-foreground">
              · {activeCount} planlı görüşme
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="outline" size="sm"
              onClick={() => setWeekStart((w) => addDays(w, -7))}
              aria-label="Önceki hafta"
            >
              <ChevronLeft className="size-4" aria-hidden />
            </Button>
            <Button
              variant="outline" size="sm"
              onClick={() => setWeekStart(mondayOf(todayISO()))}
            >
              Bugün
            </Button>
            <Button
              variant="outline" size="sm"
              onClick={() => setWeekStart((w) => addDays(w, 7))}
              aria-label="Sonraki hafta"
            >
              <ChevronRight className="size-4" aria-hidden />
            </Button>
          </div>
        </div>

        <div className="divide-y divide-border">
          {days.map(({ date, items }) => (
            <DayRow
              key={date}
              date={date}
              items={items}
              isToday={date === todayISO()}
              onEdit={setEditing}
              onRecord={setRecording}
            />
          ))}
        </div>
      </div>

      {data.series.length > 0 && <SeriesSection series={data.series} />}

      <CreateDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        students={students}
      />
      <AvailabilityDialog
        open={availOpen}
        onClose={() => setAvailOpen(false)}
        initial={data.availability}
      />
      {editing && (
        <EditDialog appt={editing} onClose={() => setEditing(null)} />
      )}
      {recording && (
        <RecordSessionDialog
          appt={recording}
          onClose={() => setRecording(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Google kartı
// ---------------------------------------------------------------------------

function GoogleCard({ google }: { google: TeacherAppointmentsResponse["google"] }) {
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
    <div className="rounded-xl border border-border bg-card px-4 py-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3 min-w-0">
        <div className="size-9 rounded-lg bg-cyan-50 dark:bg-cyan-500/10 flex items-center justify-center shrink-0">
          <Link2 className="size-4 text-cyan-700" aria-hidden />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold">Google Meet bağlantısı</div>
          {google.connected ? (
            <div className="text-xs text-muted-foreground truncate">
              {google.email ?? "Bağlı"} — yeni randevulara Meet linki otomatik eklenir
              {google.last_error && (
                <span className="text-rose-600 dark:text-rose-400">
                  {" "}· Son hata: {google.last_error}
                </span>
              )}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">
              Google hesabını bağlarsan görüşme linkleri senin hesabından
              otomatik oluşturulur (ücretsiz Gmail yeterli). Bağlamazsan linki
              elle yapıştırabilirsin.
            </div>
          )}
        </div>
      </div>
      {google.connected ? (
        <Button
          variant="outline" size="sm"
          onClick={() => {
            if (window.confirm("Google bağlantısı kaldırılsın mı? Mevcut linkler silinmez; yeni randevularda otomatik link üretilmez.")) {
              disconnect.mutate();
            }
          }}
          disabled={disconnect.isPending}
        >
          Bağlantıyı kaldır
        </Button>
      ) : (
        <Button
          size="sm"
          className="bg-cyan-700 hover:bg-cyan-800 text-white hover:text-white"
          onClick={connect}
          disabled={loading}
        >
          {loading ? "Yönlendiriliyor…" : "Google ile bağlan"}
        </Button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bekleyen istekler
// ---------------------------------------------------------------------------

function PendingBand({ pending }: { pending: AppointmentItem[] }) {
  const approve = useApproveAppointment();
  const reject = useRejectAppointment();
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30 p-4">
      <div className="text-sm font-semibold text-amber-900 dark:text-amber-200 inline-flex items-center gap-2">
        <CalendarClock className="size-4" aria-hidden />
        Onay bekleyen görüşme istekleri ({pending.length})
      </div>
      <div className="mt-3 space-y-2">
        {pending.map((p) => (
          <div
            key={p.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white dark:bg-slate-900/40 border border-amber-200 dark:border-amber-500/30 px-3 py-2"
          >
            <div className="min-w-0 text-sm">
              <span className="font-semibold">{p.student_name}</span>
              <span className="text-muted-foreground">
                {" "}· {fmtShort(p.date)} {p.weekday_label} {p.start_time}
                {" "}· {p.duration_min} dk
              </span>
              {p.request_note && (
                <div className="text-xs text-muted-foreground mt-0.5">
                  &quot;{p.request_note}&quot;
                </div>
              )}
            </div>
            <div className="flex gap-1.5">
              <Button
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700 text-white hover:text-white"
                disabled={approve.isPending}
                onClick={() => approve.mutate({ apptId: p.id })}
              >
                <Check className="size-3.5 mr-1" aria-hidden />
                Onayla
              </Button>
              <Button
                size="sm" variant="outline"
                disabled={reject.isPending}
                onClick={() => {
                  const reason = window.prompt(
                    "Reddetme sebebi (öğrenciye iletilir, boş bırakılabilir):",
                  );
                  if (reason === null) return;
                  reject.mutate({ apptId: p.id, reason: reason || undefined });
                }}
              >
                <X className="size-3.5 mr-1" aria-hidden />
                Reddet
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gün satırı + randevu kartı
// ---------------------------------------------------------------------------

function DayRow({
  date,
  items,
  isToday,
  onEdit,
  onRecord,
}: {
  date: string;
  items: AppointmentItem[];
  isToday: boolean;
  onEdit: (a: AppointmentItem) => void;
  onRecord: (a: AppointmentItem) => void;
}) {
  const weekday = WEEKDAYS[new Date(`${date}T12:00:00`).getDay() === 0 ? 6 : new Date(`${date}T12:00:00`).getDay() - 1];
  if (items.length === 0) {
    return (
      <div className="flex items-center gap-3 px-4 py-1.5 text-xs text-muted-foreground/60">
        <span className={cn("w-28 shrink-0", isToday && "font-bold text-cyan-700 dark:text-cyan-400")}>
          {fmtShort(date)} {weekday}{isToday ? " · Bugün" : ""}
        </span>
        <span>—</span>
      </div>
    );
  }
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-2 px-4 py-2.5">
      <span className={cn(
        "w-28 shrink-0 text-xs pt-1.5 font-medium",
        isToday ? "font-bold text-cyan-700 dark:text-cyan-400" : "text-muted-foreground",
      )}>
        {fmtShort(date)} {weekday}{isToday ? " · Bugün" : ""}
      </span>
      <div className="flex-1 space-y-1.5">
        {items.map((a) => (
          <AppointmentCard key={a.id} appt={a} onEdit={onEdit} onRecord={onRecord} />
        ))}
      </div>
    </div>
  );
}

function AppointmentCard({
  appt,
  onEdit,
  onRecord,
}: {
  appt: AppointmentItem;
  onEdit: (a: AppointmentItem) => void;
  onRecord: (a: AppointmentItem) => void;
}) {
  const setStatus = useSetAppointmentStatus();
  const active = appt.status === "scheduled" || appt.status === "pending";
  return (
    <div className={cn(
      "rounded-lg border border-border border-l-4 px-3 py-2",
      STATUS_TONE[appt.status] ?? "",
    )}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0 text-sm">
          <span className="font-semibold text-slate-900 dark:text-slate-100">
            {appt.start_time}
          </span>
          <span className="text-slate-700 dark:text-slate-300">
            {" "}· {appt.student_name} · {appt.duration_min} dk
          </span>
          {appt.series_id && (
            <span title="Haftalık tekrarlayan görüşme">
              <Repeat className="inline size-3.5 ml-1.5 text-cyan-700 dark:text-cyan-400" aria-hidden />
            </span>
          )}
          <span className={cn(
            "ml-2 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold",
            STATUS_CHIP[appt.status] ?? "",
          )}>
            {appt.status_label}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {appt.meeting_link && active && (
            <a
              href={appt.meeting_link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-md bg-cyan-700 hover:bg-cyan-800 text-white px-2.5 py-1 text-xs font-semibold"
            >
              <Video className="size-3.5" aria-hidden />
              Katıl
            </a>
          )}
          {/* F4 — seans kaydedildiyse rozet; biten görüşmede "Seansı kaydet" */}
          {appt.session_id ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 px-1.5">
              <Check className="size-3.5" aria-hidden />
              Seans kaydedildi
            </span>
          ) : (appt.status === "done" || appt.status === "no_show") ? (
            <Button
              variant="ghost" size="sm"
              className="h-7 px-2 text-cyan-700 dark:text-cyan-400"
              onClick={() => onRecord(appt)}
            >
              Seansı kaydet
            </Button>
          ) : null}
          {appt.status === "scheduled" && (
            <>
              <Button
                variant="ghost" size="sm" className="h-7 px-2"
                onClick={() => onEdit(appt)}
                aria-label="Düzenle"
              >
                <Pencil className="size-3.5" aria-hidden />
              </Button>
              {appt.is_past ? (
                <Button
                  size="sm"
                  className="h-7 px-2.5 bg-cyan-700 hover:bg-cyan-800 text-white hover:text-white text-xs"
                  onClick={() => onRecord(appt)}
                >
                  Seansı kaydet
                </Button>
              ) : (
                <Button
                  variant="ghost" size="sm"
                  className="h-7 px-2 text-rose-700 dark:text-rose-400"
                  disabled={setStatus.isPending}
                  onClick={() => {
                    const reason = window.prompt(
                      "İptal sebebi (öğrenci ve veliye iletilir, boş bırakılabilir):",
                    );
                    if (reason === null) return;
                    setStatus.mutate({
                      apptId: appt.id, status: "cancelled",
                      reason: reason || undefined,
                    });
                  }}
                >
                  İptal
                </Button>
              )}
            </>
          )}
        </div>
      </div>
      {appt.note && (
        <div className="text-xs text-muted-foreground mt-1">{appt.note}</div>
      )}
      {appt.cancel_reason && (
        <div className="text-xs text-muted-foreground mt-1">
          Sebep: {appt.cancel_reason}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Haftalık planlar
// ---------------------------------------------------------------------------

function SeriesSection({ series }: { series: SeriesItem[] }) {
  const update = useUpdateSeries();
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="px-4 py-3 border-b border-border">
        <div className="text-sm font-semibold inline-flex items-center gap-2">
          <Repeat className="size-4 text-cyan-700" aria-hidden />
          Haftalık görüşme planları
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          Sabit gün/saat — sistem her hafta randevuyu kendiliğinden oluşturur.
        </p>
      </div>
      <div className="divide-y divide-border">
        {series.map((s) => (
          <div key={s.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm">
            <div className="min-w-0">
              <span className="font-semibold">{s.student_name}</span>
              <span className="text-muted-foreground">
                {" "}· her {s.weekday_label} {s.start_time} · {s.duration_min} dk
              </span>
              {s.meeting_link && (
                <span className="text-xs text-muted-foreground block truncate max-w-md">
                  {s.link_source === "google" ? "Meet (otomatik): " : "Link: "}
                  {s.meeting_link}
                </span>
              )}
            </div>
            <div className="flex gap-1.5">
              <Button
                variant="outline" size="sm"
                disabled={update.isPending}
                onClick={() => {
                  const t = window.prompt("Yeni saat (SS:DD):", s.start_time);
                  if (!t || t === s.start_time) return;
                  update.mutate({ seriesId: s.id, start_time: t });
                }}
              >
                Saati değiştir
              </Button>
              <Button
                variant="outline" size="sm"
                className="text-rose-700 dark:text-rose-400"
                disabled={update.isPending}
                onClick={() => {
                  if (window.confirm(`${s.student_name} ile haftalık görüşme planı kapatılsın mı? Gelecekteki planlı görüşmeler iptal edilir.`)) {
                    update.mutate({ seriesId: s.id, active: false });
                  }
                }}
              >
                Kapat
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
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
