"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarDays,
  ChevronRight,
  Receipt,
  Target,
  TrendingUp,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  getParentStudentOverview,
  parentKeys,
} from "@/lib/api/parent";
import type {
  ParentProjectionInfo,
  ParentStudentInfo,
  ParentStudentOverviewResponse,
  ParentSubjectItem,
  ParentTeacherNoteItem,
  ParentTrendPoint,
  WarningLevel,
} from "@/lib/types/parent";
import { ParentTrendBarChart } from "@/components/parent/parent-trend-bar-chart";

interface Props {
  initial: ParentStudentOverviewResponse;
  studentId: number;
}

/**
 * Öğrenci detay — Jinja `student_detail.html` feature parity.
 *
 * Bölümler:
 *  - Header (öğrenci kimliği + breadcrumb)
 *  - 4 metrik kart (bugün / bu hafta / 7g rate / istikrar)
 *  - Projeksiyon paneli (status renkli)
 *  - Ders bazlı progress
 *  - Recharts 30g trend (Chart.js yerine)
 *  - Öğretmen notları (indigo left-border)
 */
export function ParentStudentDetailClient({ initial, studentId }: Props) {
  const q = useQuery<ParentStudentOverviewResponse>({
    queryKey: parentKeys.student(studentId),
    queryFn: () => getParentStudentOverview(studentId),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const tone = warningTone(data.warning_level);

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/parent"
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          Tüm öğrenciler
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
          {data.student.full_name}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          <StudentMeta student={data.student} />
        </p>
      </header>

      {/* Hızlı erişim — program + seanslar (en üstte, kolay bulunur) */}
      <div className="flex flex-wrap gap-2">
        <Button asChild className="bg-[#117A86] hover:bg-[#0E5F69] text-white">
          <Link href={`/parent/students/${data.student.id}/week`}>
            <CalendarDays className="size-4" aria-hidden />
            Haftalık Programı Gör
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        </Button>
        <Button asChild variant="outline">
          <Link href={`/parent/students/${data.student.id}/sessions`}>
            <Receipt className="size-4" aria-hidden />
            Seans Hareketleri
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        </Button>
      </div>

      {/* 4 metrik kart */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="Bugün"
          value={
            data.today.planned > 0
              ? `${data.today.completed}/${data.today.planned}`
              : "—"
          }
          hint={
            data.today.planned > 0 ? "görev tamamlandı" : "bugün görev yok"
          }
        />
        <MetricCard
          label="Bu Hafta"
          value={data.week.rate != null ? `%${data.week.rate}` : "—"}
          hint={
            data.week.planned > 0
              ? `${data.week.completed} / ${data.week.planned} görev`
              : "bu hafta görev yok"
          }
        />
        <MetricCard
          label="Son 7 Gün Oran"
          value={data.rate_7d_pct != null ? `%${data.rate_7d_pct}` : "—"}
          hint="tamamlama"
          tone={tone.text}
        />
        <MetricCard
          label="İstikrar"
          value={
            data.consistency_7d_pct != null
              ? `%${data.consistency_7d_pct}`
              : "—"
          }
          hint="7 günde aktif gün"
        />
      </div>

      {/* Projeksiyon + ders bazlı (2 sütun) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ProjectionCard
          student={data.student}
          projection={data.projection}
        />
        <SubjectsCard subjects={data.subjects} />
      </div>

      {/* 30g trend (Recharts) */}
      {data.trend.length > 0 && (
        <Card>
          <CardContent className="p-5">
            <div className="flex items-baseline justify-between mb-1">
              <h2 className="font-semibold inline-flex items-center gap-1.5">
                <TrendingUp className="size-4 text-[#117A86]" aria-hidden />
                Son 30 Gün Tamamlama
              </h2>
            </div>
            <p className="text-xs text-muted-foreground mb-3">
              <span className="inline-block size-2 rounded-sm bg-emerald-600 mr-1" />
              Tamamlanan ·{" "}
              <span className="inline-block size-2 rounded-sm bg-muted-foreground/50 ml-1 mr-1" />
              Planlanan
            </p>
            <ParentTrendBarChart trend={data.trend} />
          </CardContent>
        </Card>
      )}

      {/* Öğretmen notları */}
      <TeacherNotesCard notes={data.teacher_notes} />
    </div>
  );
}

// ============================================================================
// Header meta
// ============================================================================

function StudentMeta({ student }: { student: ParentStudentInfo }) {
  const parts: string[] = [];
  if (student.display_grade_label) parts.push(student.display_grade_label);
  if (student.academic_year) parts.push(student.academic_year);
  if (student.exam_date && student.exam_label) {
    parts.push(
      `${student.exam_label}: ${student.exam_date.replaceAll("-", ".")}`,
    );
  }
  return <>{parts.join(" · ")}</>;
}

// ============================================================================
// Metric kart
// ============================================================================

function MetricCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div
          className={cn(
            "text-2xl font-semibold mt-1 tabular-nums",
            tone ?? "text-foreground",
          )}
        >
          {value}
        </div>
        {hint && (
          <div className="text-[11px] text-muted-foreground mt-1">{hint}</div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Projeksiyon
// ============================================================================

function ProjectionCard({
  student,
  projection,
}: {
  student: ParentStudentInfo;
  projection: ParentProjectionInfo;
}) {
  const isYearEnd =
    student.exam_target === "none" || student.exam_label === "Yıl Sonu";
  const title = isYearEnd
    ? "Yıl Sonuna Doğru Projeksiyon"
    : `${student.exam_label ?? ""}'e Doğru Projeksiyon`;
  const tone = warningTone(projection.status);
  const statusLabel =
    projection.status === "red"
      ? "Hedefin gerisinde"
      : projection.status === "amber"
        ? "Tedbirli ilerliyor"
        : "Hedefe yakın";

  return (
    <Card className="lg:col-span-2">
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
          <h2 className="font-semibold inline-flex items-center gap-1.5">
            <Target className="size-4 text-[#117A86]" aria-hidden />
            {title}
          </h2>
          <span
            className={cn(
              "text-xs px-2 py-1 rounded-full font-medium",
              tone.pill,
            )}
          >
            {statusLabel}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-3 text-sm">
          <StatBlock label="Toplam Hedef" value={projection.total_tests} />
          <StatBlock
            label="Tamamlandı"
            value={projection.completed_tests}
            tone="text-emerald-700"
          />
          <StatBlock label="Kalan" value={projection.remaining_tests} />
          {projection.days_left_to_exam != null && (
            <>
              <StatBlock
                label={
                  isYearEnd ? "Yıl sonuna" : `${student.exam_label ?? ""}'e`
                }
                value={`${projection.days_left_to_exam} gün`}
              />
              <StatBlock
                label="Günlük Hız"
                value={projection.rate_per_day ?? "—"}
              />
              <StatBlock
                label="Beklenen Erim"
                value={projection.expected_completed_by_exam}
                tone={tone.text}
              />
            </>
          )}
        </div>

        <p className="text-[11px] text-muted-foreground italic mt-3 leading-relaxed">
          Bu projeksiyon mevcut günlük çalışma temposuna ve geçmiş 28 günlük
          desene göre hesaplanır.{" "}
          {isYearEnd ? "Yıl sonuna" : `${student.exam_label ?? ""}'e`} kadar
          tutarlı çalışma sürdürülürse erişilebilecek tahmini görev sayısını
          gösterir.
        </p>
      </CardContent>
    </Card>
  );
}

function StatBlock({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone?: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "text-base font-semibold mt-0.5 tabular-nums",
          tone ?? "text-foreground",
        )}
      >
        {value}
      </div>
    </div>
  );
}

// ============================================================================
// Ders bazlı progress
// ============================================================================

function SubjectsCard({ subjects }: { subjects: ParentSubjectItem[] }) {
  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-semibold mb-3">Ders Bazında İlerleme</h2>
        {subjects.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">
            Henüz atanmış kitap yok.
          </p>
        ) : (
          <div className="space-y-2.5">
            {subjects.map((s, idx) => {
              const hue =
                s.subject_id != null ? (s.subject_id * 67) % 360 : 0;
              return (
                <div key={s.subject_id ?? idx}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-medium truncate">{s.name}</span>
                    <span className="text-muted-foreground tabular-nums">
                      %{s.percent_done}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(100, s.percent_done)}%`,
                        background: `hsl(${hue}, 60%, 50%)`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Öğretmen notları
// ============================================================================

function TeacherNotesCard({ notes }: { notes: ParentTeacherNoteItem[] }) {
  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-semibold mb-3">Öğretmen Notları</h2>
        {notes.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">
            Henüz öğretmen tarafından sizinle paylaşılmış bir not yok.
          </p>
        ) : (
          <div className="space-y-3">
            {notes.map((n) => (
              <div
                key={n.id}
                className="border-l-4 border-[#117A86] bg-[#117A86]/5 pl-4 py-2.5 rounded-r"
              >
                <p className="text-sm whitespace-pre-line">{n.body}</p>
                <div className="text-[11px] text-muted-foreground mt-1.5">
                  {n.teacher_name ?? "—"}
                  {n.created_at && (
                    <span> · {n.created_at.slice(0, 10).replaceAll("-", ".")}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Tone helper
// ============================================================================

function warningTone(level: WarningLevel): {
  text: string;
  pill: string;
} {
  if (level === "red") {
    return {
      text: "text-rose-700",
      pill: "bg-rose-50 text-rose-700 border border-rose-200",
    };
  }
  if (level === "amber") {
    return {
      text: "text-amber-700",
      pill: "bg-amber-50 text-amber-700 border border-amber-200",
    };
  }
  return {
    text: "text-emerald-700",
    pill: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  };
}

// Re-export for trend chart
export type { ParentTrendPoint };
