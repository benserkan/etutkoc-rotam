"use client";

/**
 * Öğrenci "Program geçmişim" (2026-10-22): önceki gün gün haftaları ve havuz dönemleri tek
 * çizelgede. Hafta açılınca o haftanın sayfasına gidilir (salt okuma; geçmiş gün işaretlenemez),
 * dönem açılınca kalem kalem + gün gün dönem penceresi.
 */
import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, History } from "lucide-react";

import { getStudentProgramHistory, programHistoryKeys, type ProgramHistoryResponse } from "@/lib/api/program-history";
import { getStudentPoolPeriod, studentPoolPeriodKey } from "@/lib/api/pool-student";
import { PoolPeriodDialog } from "@/components/shared/pool-period-dialog";
import { ProgramHistoryTimeline } from "@/components/shared/program-history-timeline";

export function StudentHistoryClient({ initial }: { initial: ProgramHistoryResponse }) {
  const q = useQuery({
    queryKey: programHistoryKeys.student(),
    queryFn: getStudentProgramHistory,
    initialData: initial,
  });
  const [periodId, setPeriodId] = React.useState<number | null>(null);
  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold text-foreground">
          <History className="size-5" aria-hidden /> Program geçmişim
        </h1>
        <p className="text-sm text-muted-foreground">
          Önceki haftaların ve havuz dönemlerin. Bir haftaya ya da döneme dokun: ne verildi, ne yaptın.
        </p>
      </div>
      <ProgramHistoryTimeline
        data={q.data}
        onOpenPeriod={setPeriodId}
        renderWeekDetail={(w) => (
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="text-muted-foreground">
              {w.gorev_done}/{w.gorev_total} görev · {w.days_with_tasks} gün çalışma
            </span>
            <Link href={`/student/week?start=${w.start}`}
                  className="inline-flex items-center gap-1 rounded-md bg-cyan-700 px-3 py-1.5 font-medium text-white hover:bg-cyan-800">
              Haftayı aç <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        )}
      />
      <PoolPeriodDialog open={periodId != null} onOpenChange={(v) => { if (!v) setPeriodId(null); }}
                        queryKey={studentPoolPeriodKey(periodId ?? 0)} queryFn={() => getStudentPoolPeriod(periodId!)} />
    </div>
  );
}
