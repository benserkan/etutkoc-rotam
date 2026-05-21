"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Dna,
  Info,
  Loader2,
  type LucideIcon,
} from "lucide-react";

import { getTeacherBurnoutFleet, teacherKeys } from "@/lib/api/teacher";
import type {
  BurnoutRiskLevel,
  TeacherBurnoutFleetResponse,
  TeacherBurnoutFleetRow,
} from "@/lib/types/teacher";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const RISK_META: Record<
  BurnoutRiskLevel,
  { label: string; icon: LucideIcon; tone: string; pill: string; row: string }
> = {
  healthy: {
    label: "Sağlıklı",
    icon: CheckCircle2,
    tone: "text-emerald-500",
    pill: "bg-emerald-500/15 text-emerald-500 ring-1 ring-inset ring-emerald-500/20",
    row: "border-l-emerald-500/40",
  },
  watch: {
    label: "Dikkat",
    icon: AlertCircle,
    tone: "text-sky-500",
    pill: "bg-sky-500/15 text-sky-500 ring-1 ring-inset ring-sky-500/20",
    row: "border-l-sky-500/60",
  },
  warn: {
    label: "Uyarı",
    icon: AlertTriangle,
    tone: "text-amber-500",
    pill: "bg-amber-500/15 text-amber-500 ring-1 ring-inset ring-amber-500/20",
    row: "border-l-amber-500/70",
  },
  critical: {
    label: "Kritik",
    icon: AlertOctagon,
    tone: "text-rose-500",
    pill: "bg-rose-500/15 text-rose-500 ring-1 ring-inset ring-rose-500/20",
    row: "border-l-rose-500",
  },
};

export function BurnoutFleet() {
  const q = useQuery<TeacherBurnoutFleetResponse>({
    queryKey: teacherKeys.burnoutFleet(),
    queryFn: getTeacherBurnoutFleet,
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
          <Dna className="size-6 text-sky-500" aria-hidden />
          Tükenmişlik Panosu
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Tüm öğrencileriniz için aktif burnout sinyalleri ve risk skoru.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard
          icon={CheckCircle2}
          label="Sağlıklı"
          count={d.healthy_count}
          tone="text-emerald-500"
        />
        <SummaryCard
          icon={AlertCircle}
          label="Dikkat"
          count={d.watch_count}
          tone="text-sky-500"
        />
        <SummaryCard
          icon={AlertTriangle}
          label="Uyarı"
          count={d.warn_count}
          tone="text-amber-500"
        />
        <SummaryCard
          icon={AlertOctagon}
          label="Kritik"
          count={d.critical_count}
          tone="text-rose-500"
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
          <b>Risk skoru</b>: en yüksek 3 sinyalin ağırlıklı ortalaması. ≥75
          kritik, ≥50 uyarı, ≥25 dikkat. Sinyaller: gece geç saatte aşırı
          çalışma, hafta sonu mola yok, yoğunluk artışı, tamamlama düşüşü,
          çalışma serisinde kopma.
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  count,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  count: number;
  tone: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted-foreground">
          <Icon className={cn("size-3.5", tone)} aria-hidden />
          {label}
        </div>
        <div className={cn("text-2xl font-bold mt-1 tabular-nums", tone)}>
          {count}
        </div>
      </CardContent>
    </Card>
  );
}

function FleetRow({ row }: { row: TeacherBurnoutFleetRow }) {
  const meta = RISK_META[row.risk_level];
  const Icon = meta.icon;
  return (
    <Card
      className={cn(
        "border-l-4 hover:bg-muted/30 transition",
        meta.row,
        !row.is_active && "opacity-60",
      )}
    >
      <CardContent className="p-3 flex items-center gap-3 flex-wrap">
        <Icon
          className={cn("size-5 flex-shrink-0", meta.tone)}
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-foreground truncate inline-flex items-center gap-2">
            {row.full_name}
            {!row.is_active ? (
              <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-muted text-muted-foreground">
                Pasif
              </span>
            ) : null}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {row.signal_count > 0
              ? `${row.signal_count} aktif sinyal`
              : "Aktif sinyal yok"}
          </div>
        </div>
        <div className="text-right">
          <div
            className={cn(
              "text-lg font-bold tabular-nums leading-none",
              meta.tone,
            )}
          >
            {row.risk_score}
            <span className="text-xs text-muted-foreground/70 ml-0.5">
              /100
            </span>
          </div>
          <span
            className={cn(
              "text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md inline-block mt-1",
              meta.pill,
            )}
          >
            {meta.label}
          </span>
        </div>
        <Button asChild size="sm" variant="outline">
          <Link href={`/teacher/students/${row.student_id}/dna`}>
            Detay
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
