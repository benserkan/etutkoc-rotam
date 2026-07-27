"use client";

import { useQuery } from "@tanstack/react-query";
import { Video } from "lucide-react";

import {
  appointmentKeys,
  getParentChildAppointments,
} from "@/lib/api/appointments";
import type { ParentAppointmentsResponse } from "@/lib/types/appointment";

/**
 * Veli — "Sıradaki koçluk görüşmesi" kartı (çocuk detay sayfası).
 * Planlanmış görüşme yoksa hiç render olmaz (boş kutu gürültüsü yok).
 */
export function ParentAppointmentsCard({ studentId }: { studentId: number }) {
  const q = useQuery<ParentAppointmentsResponse>({
    queryKey: appointmentKeys.parentChild(studentId),
    queryFn: () => getParentChildAppointments(studentId),
    staleTime: 60_000,
  });
  const upcoming = q.data?.upcoming ?? [];
  if (upcoming.length === 0) return null;
  const next = upcoming[0];
  const [, m, d] = next.date.split("-");

  return (
    <div className="rounded-xl border border-cyan-200 bg-cyan-50 dark:bg-cyan-500/10 dark:border-cyan-500/30 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-800 dark:text-cyan-300 inline-flex items-center gap-1.5">
          <Video className="size-3.5" aria-hidden />
          Sıradaki koçluk görüşmesi
        </div>
        <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
          {d}.{m} {next.weekday_label} · {next.start_time}
          <span className="font-normal text-slate-600 dark:text-slate-400">
            {" "}· {next.coach_name ?? "Koç"} ile · {next.duration_min} dk
          </span>
        </div>
        {upcoming.length > 1 && (
          <div className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
            +{upcoming.length - 1} planlı görüşme daha
          </div>
        )}
      </div>
      {next.meeting_link && (
        <a
          href={next.meeting_link}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-700 hover:bg-cyan-800 text-white px-3 py-1.5 text-xs font-semibold shrink-0"
        >
          <Video className="size-3.5" aria-hidden />
          Görüşmeye katıl
        </a>
      )}
    </div>
  );
}
