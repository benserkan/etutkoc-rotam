"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { CalendarDays, ChevronLeft, ChevronRight, PlusCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/locale";
import type { StudentDayResponse } from "@/lib/types/student";
import { PrintMenu } from "./print-menu";

interface Props {
  day: StudentDayResponse;
  /** Yeni görev iste — parent CommModal'ı açar. */
  onRequestAdd: () => void;
}

/**
 * Gün başlığı — Önceki / Bugün / Sonraki + gün adı + tarih + özet rozeti +
 * "Yeni görev iste" butonu.
 *
 * Navigasyon: `/student/day?date=YYYY-MM-DD` query string ile gün değişir;
 * Server Component re-fetch eder, client cache layout aynı.
 */
export function DayHeader({ day, onRequestAdd }: Props) {
  const router = useRouter();
  const today = todayIso();
  const isOnToday = day.is_today;
  const pct = Math.round(day.summary.pct * 100);

  function nav(target: string) {
    router.push(`/student/day?date=${target}`);
  }

  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="icon"
          onClick={() => nav(day.prev_date)}
          aria-label="Önceki gün"
        >
          <ChevronLeft className="size-4" />
        </Button>

        <DateInput value={day.date} onChange={nav} />

        <Button
          variant="outline"
          size="icon"
          onClick={() => nav(day.next_date)}
          aria-label="Sonraki gün"
        >
          <ChevronRight className="size-4" />
        </Button>

        <Button
          variant={isOnToday ? "ghost" : "outline"}
          size="sm"
          onClick={() => nav(today)}
          disabled={isOnToday}
          className="ml-1"
        >
          <CalendarDays className="size-3.5" /> Bugün
        </Button>

        <div className="flex-1" />

        <PrintMenu startDate={day.date} />

        <Button onClick={onRequestAdd} variant="default" size="sm">
          <PlusCircle className="size-4" />
          Yeni görev iste
        </Button>
      </div>

      <div className="flex flex-col gap-1">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
          {formatDate(day.date)}
          {day.is_today ? (
            <span className="ml-2 text-base font-normal text-muted-foreground">
              · bugün
            </span>
          ) : null}
        </h1>
        <p className="text-sm text-muted-foreground">
          {day.summary.gorev_done}/{day.summary.gorev_total} görev
          {day.summary.test_planned > 0 ? (
            <> · {day.summary.test_completed}/{day.summary.test_planned} test</>
          ) : null}
          {day.summary.deneme_count > 0 ? (
            <> · {day.summary.deneme_count} deneme</>
          ) : null}
          {day.summary.etkinlik_count > 0 ? (
            <> · {day.summary.etkinlik_count} etkinlik</>
          ) : null}{" "}
          · <span className="font-medium text-foreground">%{pct} tamam</span>
        </p>
        <div className="h-1.5 w-full max-w-md rounded-full bg-muted overflow-hidden">
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${pct}%` }}
            aria-hidden="true"
          />
        </div>
      </div>
    </header>
  );
}

function DateInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (iso: string) => void;
}) {
  return (
    <label className="relative inline-flex items-center">
      <span className="sr-only">Tarih seç</span>
      <input
        type="date"
        value={value}
        onChange={(e) => {
          if (e.target.value) onChange(e.target.value);
        }}
        className="h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
    </label>
  );
}

function todayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const da = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${da}`;
}
