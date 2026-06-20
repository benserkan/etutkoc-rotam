"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Info, Printer, Users } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  getInstitutionActivityHeatmap,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  ActivityHeatmapResponse,
  TeacherHeatmapRow,
} from "@/lib/types/institution";
import {
  HeatmapAxis,
  HeatmapGrid,
  HeatmapLegend,
} from "@/components/institution/heatmap-grid";

interface Props {
  initial: ActivityHeatmapResponse;
  weeks: number;
}

/**
 * Öğretmen Aktivite Haritası — Jinja `activity_heatmap.html` ile birebir.
 *
 * 4/12 hafta segmented buttons → URL state (?weeks=4|12)
 * GitHub-style heatmap grid + tooltip
 * Pasif öğretmen rozet (rose) + deaktif hesap rozet (slate)
 */
export function ActivityHeatmapClient({ initial, weeks }: Props) {
  const q = useQuery<ActivityHeatmapResponse>({
    queryKey: institutionKeys.activityHeatmap(weeks),
    queryFn: () => getInstitutionActivityHeatmap(weeks),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const {
    institution,
    days_count,
    inactive_threshold_days,
    inactive_count,
    teachers,
  } = data;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href="/institution"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Panel
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
            Öğretmen Aktivite Haritası
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {institution.name} — son {weeks} hafta. Her kare bir gün; daha
            koyu yeşil = daha fazla aktivite.
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link
            href={`/institution/activity-heatmap/print?weeks=${weeks}`}
            target="_blank"
          >
            <Printer className="size-4" aria-hidden />
            Yazdır / PDF
          </Link>
        </Button>
      </header>

      <InfoBanner inactive_threshold_days={inactive_threshold_days} />

      <div className="flex items-center justify-between flex-wrap gap-3">
        <PeriodSwitch active={weeks} />
        {inactive_count > 0 && (
          <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 px-3 py-1.5 rounded inline-flex items-center gap-1.5 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200">
            <AlertCircle className="size-3.5" aria-hidden />
            {inactive_count} öğretmen son {inactive_threshold_days} gündür
            pasif
          </div>
        )}
      </div>

      <HeatmapLegend />

      {teachers.length === 0 ? (
        <EmptyState />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium w-48">
                    Öğretmen
                  </th>
                  <th className="text-left px-4 py-2 font-medium align-bottom">
                    <div className="mb-1 text-[11px] text-muted-foreground">Son {weeks} hafta — hafta başı tarihleri:</div>
                    {teachers[0]?.cells?.length ? <HeatmapAxis cells={teachers[0].cells} /> : null}
                  </th>
                  <th className="text-right px-4 py-2 font-medium whitespace-nowrap">
                    Toplam
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {teachers.map((t) => (
                  <HeatmapRow
                    key={t.teacher_id}
                    row={t}
                    days_count={days_count}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function InfoBanner({
  inactive_threshold_days,
}: {
  inactive_threshold_days: number;
}) {
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50 text-sky-900 px-3 py-2.5 text-xs flex items-start gap-2 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200">
      <Info className="size-4 shrink-0 mt-0.5" aria-hidden />
      <div>
        <strong>Aktivite nasıl ölçülür?</strong> Öğretmen o gün sisteme girmiş
        (1 puan) + öğrencisine yeni görev oluşturmuş (her görev için 1 puan,
        en fazla 10) + veliye not yazmış (her not için 1 puan, en fazla 5).
        Toplam puan ne kadar yüksekse hücre o kadar koyu yeşildir.{" "}
        <strong>Hücreye fareyle dokun</strong> — o günkü detay (kaç görev, kaç
        not, giriş var mı) görünür.
        <span className="block mt-1">
          &ldquo;Pasif&rdquo; işareti = son {inactive_threshold_days} gündür
          sisteme hiç dokunmamış.
        </span>
      </div>
    </div>
  );
}

function PeriodSwitch({ active }: { active: number }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">Periyot:</span>
      <PeriodButton active={active === 4} weeks={4} label="4 hafta" />
      <PeriodButton active={active === 12} weeks={12} label="12 hafta" />
    </div>
  );
}

function PeriodButton({
  active,
  weeks,
  label,
}: {
  active: boolean;
  weeks: number;
  label: string;
}) {
  return (
    <Link
      href={`/institution/activity-heatmap?weeks=${weeks}`}
      className={cn(
        "px-3 py-1 rounded text-xs border transition-colors",
        active
          ? "bg-foreground text-background border-foreground"
          : "border-border hover:bg-muted",
      )}
      aria-pressed={active}
    >
      {label}
    </Link>
  );
}

function HeatmapRow({
  row,
  days_count,
}: {
  row: TeacherHeatmapRow;
  days_count: number;
}) {
  return (
    <tr className={cn(row.is_inactive && "bg-rose-50/30")}>
      <td className="px-4 py-3 align-top">
        <div className="font-medium flex items-center gap-2 flex-wrap">
          {row.full_name}
          {row.is_inactive && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 border border-rose-200">
              pasif
            </span>
          )}
          {row.is_new && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-100 text-sky-700 border border-sky-200">
              yeni
            </span>
          )}
        </div>
        <div className="text-[11px] text-muted-foreground mt-0.5">
          {row.last_active_day
            ? `son aktivite ${row.days_since_active}g önce`
            : row.is_new
              ? "yeni hesap — henüz giriş yok"
              : "hiç aktivite yok"}
        </div>
      </td>
      <td className="px-4 py-3">
        {row.cells.length === days_count ? (
          <HeatmapGrid cells={row.cells} />
        ) : (
          <HeatmapGrid cells={row.cells} />
        )}
      </td>
      <td className="px-4 py-3 text-right text-xs whitespace-nowrap align-top">
        <div className="font-semibold tabular-nums">
          {row.total_logins} giriş
        </div>
        <div className="text-muted-foreground mt-0.5 tabular-nums">
          {row.total_tasks} task · {row.total_notes} not
        </div>
      </td>
    </tr>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardContent className="p-12 text-center">
        <Users className="size-12 mx-auto text-muted-foreground mb-3" aria-hidden />
        <h2 className="text-lg font-semibold mb-1">Henüz öğretmen yok</h2>
        <p className="text-sm text-muted-foreground">
          Aktivite haritası için en az bir öğretmen eklenmiş olmalı.{" "}
          <Link
            href="/institution/teachers"
            className="text-accent hover:underline"
          >
            Öğretmen ekle →
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
