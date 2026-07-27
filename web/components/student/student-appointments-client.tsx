"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CalendarClock,
  CalendarPlus,
  Clock,
  Video,
  X,
} from "lucide-react";

import {
  appointmentKeys,
  getStudentAppointmentSlots,
  getStudentAppointments,
} from "@/lib/api/appointments";
import {
  useRequestAppointment,
  useWithdrawAppointment,
} from "@/lib/hooks/use-appointment-mutations";
import type {
  AppointmentItem,
  StudentAppointmentsResponse,
  StudentSlotsResponse,
} from "@/lib/types/appointment";
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
 * Öğrenci "Görüşmelerim" — sıradaki koçluk görüşmesi (katıl butonu) +
 * boş saatten görüşme isteme + bekleyen isteği geri çekme.
 */

function fmtDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}.${m}`;
}

export function StudentAppointmentsClient({
  initial,
}: {
  initial: StudentAppointmentsResponse;
}) {
  const q = useQuery<StudentAppointmentsResponse>({
    queryKey: appointmentKeys.student(),
    queryFn: getStudentAppointments,
    initialData: initial,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;
  const [requestOpen, setRequestOpen] = React.useState(false);
  const withdraw = useWithdrawAppointment();

  const next = data.upcoming[0] ?? null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold inline-flex items-center gap-2">
            <Video className="size-5 text-cyan-700" aria-hidden />
            Görüşmelerim
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data.coach_name
              ? `${data.coach_name} ile koçluk görüşmelerin`
              : "Koçluk görüşmelerin"}
          </p>
        </div>
        {data.can_request && !data.has_pending && (
          <Button
            className="bg-cyan-700 hover:bg-cyan-800 text-white hover:text-white"
            onClick={() => setRequestOpen(true)}
          >
            <CalendarPlus className="size-4 mr-1.5" aria-hidden />
            Görüşme iste
          </Button>
        )}
      </div>

      {/* Sıradaki görüşme */}
      {next ? (
        <div className="rounded-xl border border-cyan-200 bg-cyan-50 dark:bg-cyan-500/10 dark:border-cyan-500/30 p-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-cyan-800 dark:text-cyan-300">
            Sıradaki görüşmen
          </div>
          <div className="mt-1.5 text-lg font-bold text-slate-900 dark:text-slate-100">
            {fmtDate(next.date)} {next.weekday_label} · {next.start_time}
          </div>
          <div className="text-sm text-slate-700 dark:text-slate-300 mt-0.5">
            {next.coach_name ?? "Koçun"} ile · {next.duration_min} dakika
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {next.meeting_link ? (
              <a
                href={next.meeting_link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-700 hover:bg-cyan-800 text-white px-4 py-2 text-sm font-semibold"
              >
                <Video className="size-4" aria-hidden />
                Görüşmeye katıl
              </a>
            ) : (
              <span className="text-xs text-slate-600 dark:text-slate-400">
                Görüşme bağlantısını koçun paylaşacak — saat gelince buradan
                katılabileceksin.
              </span>
            )}
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          Planlanmış bir görüşmen yok.
          {data.can_request && !data.has_pending &&
            " İstersen “Görüşme iste” ile koçundan saat isteyebilirsin."}
          {!data.can_request && data.coach_name &&
            " Koçun görüşme planladığında burada göreceksin."}
        </div>
      )}

      {/* Bekleyen istek */}
      {data.pending.map((p) => (
        <div
          key={p.id}
          className="rounded-xl border border-amber-200 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30 px-4 py-3 flex flex-wrap items-center justify-between gap-2"
        >
          <div className="text-sm text-amber-900 dark:text-amber-200">
            <CalendarClock className="inline size-4 mr-1.5 -mt-0.5" aria-hidden />
            <span className="font-semibold">
              {fmtDate(p.date)} {p.weekday_label} {p.start_time}
            </span>{" "}
            için isteğin koçunun onayını bekliyor.
          </div>
          <Button
            variant="outline" size="sm"
            disabled={withdraw.isPending}
            onClick={() => withdraw.mutate({ apptId: p.id })}
          >
            <X className="size-3.5 mr-1" aria-hidden />
            Geri çek
          </Button>
        </div>
      ))}

      {/* Diğer yaklaşan görüşmeler */}
      {data.upcoming.length > 1 && (
        <div className="rounded-xl border border-border bg-card">
          <div className="px-4 py-2.5 border-b border-border text-sm font-semibold">
            Sonraki görüşmeler
          </div>
          <div className="divide-y divide-border">
            {data.upcoming.slice(1).map((a) => (
              <UpcomingRow key={a.id} appt={a} />
            ))}
          </div>
        </div>
      )}

      {/* Geçmiş */}
      {data.past.length > 0 && (
        <div className="rounded-xl border border-border bg-card">
          <div className="px-4 py-2.5 border-b border-border text-sm font-semibold">
            Geçmiş görüşmeler
          </div>
          <div className="divide-y divide-border">
            {data.past.map((a) => (
              <div key={a.id} className="px-4 py-2.5 text-sm flex items-center justify-between gap-2">
                <span className="text-muted-foreground">
                  {fmtDate(a.date)} {a.weekday_label} · {a.start_time}
                </span>
                <span className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                  a.status === "done"
                    ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200"
                    : a.status === "no_show"
                      ? "bg-rose-100 text-rose-900 dark:bg-rose-500/20 dark:text-rose-200"
                      : "bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300",
                )}>
                  {a.status_label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <RequestDialog
        open={requestOpen}
        onClose={() => setRequestOpen(false)}
      />
    </div>
  );
}

function UpcomingRow({ appt }: { appt: AppointmentItem }) {
  return (
    <div className="px-4 py-2.5 text-sm flex flex-wrap items-center justify-between gap-2">
      <span>
        <Clock className="inline size-3.5 mr-1.5 -mt-0.5 text-muted-foreground" aria-hidden />
        {fmtDate(appt.date)} {appt.weekday_label} · {appt.start_time} ·{" "}
        {appt.duration_min} dk
      </span>
      {appt.meeting_link && (
        <a
          href={appt.meeting_link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-semibold text-cyan-700 dark:text-cyan-400 hover:underline"
        >
          Görüşme linki
        </a>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Görüşme isteme dialogu — gün seç → boş saat çipleri
// ---------------------------------------------------------------------------

function RequestDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const slotsQ = useQuery<StudentSlotsResponse>({
    queryKey: appointmentKeys.studentSlots(),
    queryFn: getStudentAppointmentSlots,
    enabled: open,
    staleTime: 10_000,
  });
  const request = useRequestAppointment();
  const [selDate, setSelDate] = React.useState<string | null>(null);
  const [selTime, setSelTime] = React.useState<string | null>(null);
  const [note, setNote] = React.useState("");

  const days = slotsQ.data?.days ?? [];
  const selDay = days.find((d) => d.date === selDate) ?? null;

  function submit() {
    if (!selDate || !selTime) return;
    request.mutate(
      { date: selDate, start_time: selTime, note: note.trim() || undefined },
      {
        onSuccess: () => {
          setSelDate(null); setSelTime(null); setNote("");
          onClose();
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Görüşme iste</DialogTitle>
          <DialogDescription>
            Koçunun boş saatlerinden birini seç — onaylayınca haber vereceğiz.
          </DialogDescription>
        </DialogHeader>

        {slotsQ.isLoading ? (
          <div className="text-sm text-muted-foreground py-4 text-center">
            Boş saatler yükleniyor…
          </div>
        ) : days.length === 0 ? (
          <div className="text-sm text-muted-foreground py-4 text-center">
            Önümüzdeki iki haftada boş saat görünmüyor — koçunla mesajlaşarak
            saat belirleyebilirsin.
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <div className="text-xs font-semibold text-muted-foreground mb-1.5">
                Gün
              </div>
              <div className="flex flex-wrap gap-1.5">
                {days.map((d) => (
                  <button
                    key={d.date}
                    type="button"
                    onClick={() => { setSelDate(d.date); setSelTime(null); }}
                    className={cn(
                      "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                      selDate === d.date
                        ? "border-cyan-600 bg-cyan-700 text-white"
                        : "border-border bg-background hover:bg-muted",
                    )}
                  >
                    {fmtDate(d.date)} {d.weekday_label.slice(0, 3)}
                  </button>
                ))}
              </div>
            </div>
            {selDay && (
              <div>
                <div className="text-xs font-semibold text-muted-foreground mb-1.5">
                  Saat ({selDay.slots[0]?.duration_min ?? 40} dk görüşme)
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {selDay.slots.map((s) => (
                    <button
                      key={s.start_time}
                      type="button"
                      onClick={() => setSelTime(s.start_time)}
                      className={cn(
                        "rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors",
                        selTime === s.start_time
                          ? "border-cyan-600 bg-cyan-700 text-white"
                          : "border-border bg-background hover:bg-muted",
                      )}
                    >
                      {s.start_time}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <label className="block text-sm">
              <span className="text-xs font-semibold text-muted-foreground">
                Not (isteğe bağlı)
              </span>
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Örn. deneme sonucumu konuşmak istiyorum"
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                maxLength={200}
              />
            </label>
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="outline" onClick={onClose}>
                Vazgeç
              </Button>
              <Button
                type="button"
                className="bg-cyan-700 hover:bg-cyan-800 text-white hover:text-white"
                disabled={!selDate || !selTime || request.isPending}
                onClick={submit}
              >
                {request.isPending ? "Gönderiliyor…" : "İsteği gönder"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
