import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { apiServer } from "@/lib/api-server";
import type { StudentWeekResponse } from "@/lib/types/student";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { PrintMenu } from "@/components/student/print-menu";

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

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3">
        {week.days.map((d) => {
          const pct = Math.round(d.pct * 100);
          return (
            <Link
              key={d.date}
              href={`/student/day?date=${d.date}`}
              className={cn(
                "group rounded-lg border bg-card p-3 transition-colors hover:bg-muted/40",
                d.is_today ? "border-primary" : "border-border",
                d.is_past ? "opacity-90" : "",
              )}
            >
              <div className="flex items-baseline justify-between">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {d.dow_label}
                </p>
                {d.is_today ? (
                  <span className="inline-flex items-center rounded-full bg-primary/15 text-primary px-2 py-0.5 text-[10px] font-medium">
                    Bugün
                  </span>
                ) : null}
              </div>
              <p className="font-medium tabular-nums mt-1">{d.date}</p>
              <p className="text-xs text-muted-foreground mt-2 tabular-nums">
                {d.gorev_done}/{d.gorev_total} görev
              </p>
              <p className="text-[11px] text-muted-foreground tabular-nums">
                {d.test_planned > 0 ? `${d.test_completed}/${d.test_planned} test` : null}
                {d.test_planned > 0 && d.deneme_count > 0 ? " · " : null}
                {d.deneme_count > 0 ? `${d.deneme_count} deneme` : null}
                {(d.test_planned > 0 || d.deneme_count > 0) && d.etkinlik_count > 0 ? " · " : null}
                {d.etkinlik_count > 0 ? `${d.etkinlik_count} etkinlik` : null}
                {d.test_planned === 0 && d.deneme_count === 0 && d.etkinlik_count === 0 ? "—" : null}
              </p>
              <div className="mt-2 h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className={cn(
                    "h-full transition-all",
                    pct >= 100 ? "bg-emerald-500" : pct > 0 ? "bg-amber-400" : "bg-muted-foreground/20",
                  )}
                  style={{ width: `${Math.min(100, pct)}%` }}
                  aria-hidden
                />
              </div>
              <p className="text-[11px] text-muted-foreground tabular-nums mt-1">
                %{pct}
              </p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
