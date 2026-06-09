import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { apiServer } from "@/lib/api-server";
import type { StudentWeekResponse } from "@/lib/types/student";
import { Button } from "@/components/ui/button";
import { PrintMenu } from "@/components/student/print-menu";
import { StudentWeekGrid } from "@/components/student/student-week-grid";
import { DemoHint } from "@/components/demos/demo-hint";

export const metadata = { title: "Hafta" };
export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function StudentWeekPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const raw = sp.start;
  const start = typeof raw === "string" ? raw : undefined;
  const qs = start ? `?start=${encodeURIComponent(start)}` : "";
  const week = await apiServer<StudentWeekResponse>(`/api/v2/student/week${qs}`);
  const totalPct = Math.round(week.total_pct * 100);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="icon" asChild aria-label="Önceki hafta">
          <Link href={`/student/week?start=${week.prev_start}`}>
            <ChevronLeft className="size-4" aria-hidden />
          </Link>
        </Button>
        <Button variant="outline" size="icon" asChild aria-label="Sonraki hafta">
          <Link href={`/student/week?start=${week.next_start}`}>
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/student/week">Bu hafta</Link>
        </Button>
        <div className="flex-1" />
        <p className="text-sm text-muted-foreground tabular-nums">
          {week.start_date} – {week.end_date} · {week.total_gorev_done}/
          {week.total_gorev} görev
          {week.total_test_planned > 0 ? (
            <> · {week.total_test_completed}/{week.total_test_planned} test</>
          ) : null}{" "}
          · <span className="font-medium text-foreground">%{totalPct}</span>
        </p>
        <PrintMenu startDate={week.start_date} />
      </header>

      <DemoHint contextKey="week" role="student" />
      <StudentWeekGrid days={week.days} />
    </div>
  );
}
