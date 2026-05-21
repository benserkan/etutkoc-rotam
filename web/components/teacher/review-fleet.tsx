"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Brain,
  CheckCircle2,
  Info,
  Loader2,
  Sigma,
} from "lucide-react";

import { getTeacherReviewFleet, teacherKeys } from "@/lib/api/teacher";
import type {
  TeacherReviewFleetResponse,
  TeacherReviewFleetRow,
} from "@/lib/types/teacher";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ReviewFleet() {
  const q = useQuery<TeacherReviewFleetResponse>({
    queryKey: teacherKeys.reviewFleet(),
    queryFn: getTeacherReviewFleet,
    staleTime: 30_000,
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-12">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
      </div>
    );
  }
  if (q.error || !q.data) {
    return <div className="text-sm text-rose-500">Veri yüklenemedi.</div>;
  }

  const d = q.data;

  return (
    <div className="space-y-6 max-w-6xl">
      <header>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          <Link href="/teacher/dashboard" className="hover:underline">
            ← Panel
          </Link>
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
          <Brain className="size-6 text-emerald-500" aria-hidden />
          Tekrar Yükü Panosu
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Tüm öğrencilerinizin aralıklı tekrar (FSRS) durumu.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <SummaryCard
          icon={Brain}
          label="Bugün vade"
          value={String(d.total_due)}
          tone="text-rose-500"
          hint="Bekleyen kart sayısı"
        />
        <SummaryCard
          icon={Sigma}
          label="Toplam kart"
          value={String(d.total_cards)}
          tone="text-foreground"
          hint="Tüm öğrencilerin kart havuzu"
        />
        <SummaryCard
          icon={CheckCircle2}
          label="Öğrenci"
          value={String(d.rows.length)}
          tone="text-emerald-500"
          hint="Aktif liste boyutu"
        />
      </div>

      {d.rows.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="text-center py-12 text-sm text-muted-foreground">
            Henüz öğrenciniz yok.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {d.rows.map((row) => (
            <FleetRow key={row.student_id} row={row} />
          ))}
        </div>
      )}

      <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground leading-relaxed inline-flex items-start gap-2">
        <Info
          className="size-4 text-muted-foreground flex-shrink-0 mt-0.5"
          aria-hidden
        />
        <div>
          <b>Vade gelen</b>: bugün/şimdiye kadar tekrar edilmesi gereken kart
          sayısı. Yüksekse öğrenciyi yönlendirin; öğrenci kendi panelinden
          tekrarları yapacak.
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  tone,
  hint,
}: {
  icon: typeof Brain;
  label: string;
  value: string;
  tone: string;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted-foreground">
          <Icon className={cn("size-3.5", tone)} aria-hidden />
          {label}
        </div>
        <div className={cn("text-2xl font-bold mt-1 tabular-nums", tone)}>
          {value}
        </div>
        {hint ? (
          <div className="text-[11px] text-muted-foreground mt-0.5">{hint}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function FleetRow({ row }: { row: TeacherReviewFleetRow }) {
  const duePill =
    row.due_now >= 20
      ? "bg-rose-500/15 text-rose-500 ring-1 ring-inset ring-rose-500/20"
      : row.due_now >= 10
        ? "bg-amber-500/15 text-amber-500 ring-1 ring-inset ring-amber-500/20"
        : row.due_now > 0
          ? "bg-emerald-500/15 text-emerald-500 ring-1 ring-inset ring-emerald-500/20"
          : "bg-muted text-muted-foreground";
  const accent =
    row.due_now >= 20
      ? "border-l-rose-500"
      : row.due_now >= 10
        ? "border-l-amber-500"
        : row.due_now > 0
          ? "border-l-emerald-500/60"
          : "border-l-border";

  return (
    <Card
      className={cn(
        "border-l-4 hover:bg-muted/30 transition",
        accent,
        !row.is_active && "opacity-60",
      )}
    >
      <CardContent className="p-3 flex items-center gap-3 flex-wrap">
        <Brain className="size-5 text-emerald-500 flex-shrink-0" aria-hidden />
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-foreground truncate inline-flex items-center gap-2">
            {row.full_name}
            {!row.is_active ? (
              <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-muted text-muted-foreground">
                Pasif
              </span>
            ) : null}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5 tabular-nums">
            Toplam <b className="text-foreground">{row.total}</b> kart
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Vade gelen
          </div>
          {row.due_now > 0 ? (
            <span
              className={cn(
                "text-sm font-bold tabular-nums px-2 py-0.5 rounded-md inline-block mt-0.5",
                duePill,
              )}
            >
              {row.due_now}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground/70 tabular-nums mt-0.5 inline-block">
              —
            </span>
          )}
        </div>
        <Button asChild size="sm" variant="outline">
          <Link href={`/teacher/students/${row.student_id}/review`}>
            Detay
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
