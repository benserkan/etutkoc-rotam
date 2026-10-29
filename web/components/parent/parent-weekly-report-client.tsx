"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  Minus,
  TrendingDown,
  TrendingUp,
  Trophy,
  AlertTriangle,
  GraduationCap,
  MessageSquare,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DemoHint } from "@/components/demos/demo-hint";
import { getParentWeeklyReport, parentKeys } from "@/lib/api/parent";
import type {
  WeeklyReportResponse,
  WeeklyReportComparison,
  WeeklyReportDaily,
  WeeklyReportExam,
  WeeklyReportSubject,
  WeeklyVerdictLevel,
} from "@/lib/types/parent";

interface Props {
  initial: WeeklyReportResponse;
  studentId: number;
  weekStartParam: string | null;
}

const DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

function fmtRange(startIso: string, endIso: string): string {
  const [, sm, sd] = startIso.split("-").map(Number);
  const [, em, ed] = endIso.split("-").map(Number);
  if (sm === em) return `${sd}–${ed} ${TR_MONTHS[em - 1]}`;
  return `${sd} ${TR_MONTHS[sm - 1]} – ${ed} ${TR_MONTHS[em - 1]}`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const [, m, d] = iso.split("-").map(Number);
  return `${d} ${TR_MONTHS[m - 1]}`;
}

export function ParentWeeklyReportClient({
  initial,
  studentId,
  weekStartParam,
}: Props) {
  const [weekStart, setWeekStart] = React.useState<string | null>(
    weekStartParam,
  );

  const q = useQuery<WeeklyReportResponse>({
    queryKey: parentKeys.weeklyReport(studentId, weekStart),
    queryFn: () => getParentWeeklyReport(studentId, weekStart),
    initialData: weekStart === weekStartParam ? initial : undefined,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  // Bugünün haftasından ileri gitmeyi engelle (gelecek hafta anlamsız)
  const todayMonday = mondayOfToday();
  const isCurrentOrFuture = data.start >= todayMonday;

  return (
    <div className="space-y-6">
      <header>
        <Link
          href={`/parent/students/${studentId}`}
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          Öğrenci özeti
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
          Haftalık Rapor
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {data.student.full_name}
        </p>
        <DemoHint contextKey="weekly-report" role="parent" className="mt-2" />
      </header>

      {/* Hafta gezgini */}
      <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1"
          onClick={() => setWeekStart(data.prev_start)}
        >
          <ChevronLeft className="size-4" aria-hidden />
          Önceki hafta
        </Button>
        <span className="text-sm font-medium inline-flex items-center gap-1.5">
          <CalendarRange className="size-4 text-[#117A86]" aria-hidden />
          {fmtRange(data.start, data.end)}
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="gap-1"
          disabled={isCurrentOrFuture}
          onClick={() => setWeekStart(data.next_start)}
        >
          Sonraki hafta
          <ChevronRight className="size-4" aria-hidden />
        </Button>
      </div>

      <VerdictBanner level={data.verdict_level} text={data.verdict_text} />

      <ComparisonHero data={data} />

      <SubjectSection
        subjects={data.subjects}
        mostCompleted={data.most_completed_subject}
        mostNeglected={data.most_neglected_subject}
        mostNeglectedPct={data.most_neglected_pct}
      />

      <ExamSection
        exams={data.exams}
        trendDelta={data.exam_trend_delta}
        trendSection={data.exam_trend_section}
      />

      <DailySection daily={data.daily} />

      <NotesSection notes={data.teacher_notes} />

      <p className="text-[11px] text-muted-foreground leading-relaxed px-1">
        Bu rapor çocuğunuzun bir haftalık çalışma programı ve deneme sonuçlarını
        özetler. Konu bazında ayrıntılar ve koçluk notlarının tamamı, öğrenci ile
        koç arasındaki çalışma alanına aittir.
      </p>
    </div>
  );
}

function mondayOfToday(): string {
  const d = new Date();
  const dow = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - dow);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// ============================================================================
// Verdict
// ============================================================================

function verdictTone(level: WeeklyVerdictLevel) {
  if (level === "good")
    return {
      wrap: "border-emerald-300 bg-emerald-50",
      text: "text-emerald-900",
      sub: "text-emerald-800",
      label: "Yolunda",
    };
  if (level === "warn")
    return {
      wrap: "border-amber-300 bg-amber-50",
      text: "text-amber-900",
      sub: "text-amber-800",
      label: "Dikkat",
    };
  return {
    wrap: "border-rose-300 bg-rose-50",
    text: "text-rose-900",
    sub: "text-rose-800",
    label: "Acil",
  };
}

function VerdictBanner({
  level,
  text,
}: {
  level: WeeklyVerdictLevel;
  text: string;
}) {
  const t = verdictTone(level);
  return (
    <div className={cn("rounded-xl border-2 px-5 py-4", t.wrap)}>
      <div
        className={cn(
          "text-[11px] font-bold uppercase tracking-wider",
          t.sub,
        )}
      >
        Bu haftanın değerlendirmesi · {t.label}
      </div>
      <p className={cn("text-base font-semibold mt-1 leading-snug", t.text)}>
        {text}
      </p>
    </div>
  );
}

// ============================================================================
// Karşılaştırma — bu hafta vs geçen hafta (MANŞET)
// ============================================================================

function ComparisonHero({ data }: { data: WeeklyReportResponse }) {
  const c = data.comparison;
  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-semibold inline-flex items-center gap-1.5 mb-1">
          <TrendingUp className="size-4 text-[#117A86]" aria-hidden />
          Geçen Haftaya Göre
        </h2>
        <p className="text-xs text-muted-foreground mb-4">
          Çocuğunuzun bu haftaki temposu, bir önceki haftayla karşılaştırılır.
        </p>
        <div className="grid grid-cols-3 gap-3">
          <CompareStat
            label="Tamamlama"
            value={`%${c.this_completion_pct}`}
            prev={
              c.last_completion_pct != null
                ? `geçen %${c.last_completion_pct}`
                : "geçen hafta veri yok"
            }
            delta={c.completion_delta}
            deltaSuffix="puan"
          />
          <CompareStat
            label="Çözülen test"
            value={`${c.this_test_completed}`}
            prev={
              c.last_test_completed != null
                ? `geçen ${c.last_test_completed}`
                : "—"
            }
            delta={c.test_delta}
            deltaSuffix=""
          />
          <CompareStat
            label="Çalışılan gün"
            value={`${data.active_days}/7`}
            prev={`${data.gorev_done}/${data.gorev_total} görev`}
            delta={null}
            deltaSuffix=""
          />
        </div>
      </CardContent>
    </Card>
  );
}

function CompareStat({
  label,
  value,
  prev,
  delta,
  deltaSuffix,
}: {
  label: string;
  value: string;
  prev: string;
  delta: number | null;
  deltaSuffix: string;
}) {
  const dir = delta == null ? "flat" : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const Icon = dir === "up" ? TrendingUp : dir === "down" ? TrendingDown : Minus;
  const tone =
    dir === "up"
      ? "text-emerald-700"
      : dir === "down"
        ? "text-rose-700"
        : "text-muted-foreground";
  return (
    <div className="text-center">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="text-2xl font-bold mt-0.5 tabular-nums text-foreground">
        {value}
      </div>
      {delta != null && (
        <div
          className={cn(
            "mt-1 inline-flex items-center gap-0.5 text-xs font-semibold tabular-nums",
            tone,
          )}
        >
          <Icon className="size-3.5" aria-hidden />
          {delta > 0 ? "+" : ""}
          {delta}
          {deltaSuffix ? ` ${deltaSuffix}` : ""}
        </div>
      )}
      <div className="text-[10px] text-muted-foreground mt-0.5">{prev}</div>
    </div>
  );
}

// ============================================================================
// Ders kırılımı
// ============================================================================

function SubjectSection({
  subjects,
  mostCompleted,
  mostNeglected,
  mostNeglectedPct,
}: {
  subjects: WeeklyReportSubject[];
  mostCompleted: string | null;
  mostNeglected: string | null;
  mostNeglectedPct: number | null;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-semibold mb-3">Bu Hafta Dersler</h2>

        {subjects.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">
            Bu hafta planlanmış test görevi yok.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
              {mostCompleted && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-emerald-800">
                    <Trophy className="size-3.5" aria-hidden />
                    En çok çözülen
                  </div>
                  <div className="text-base font-bold text-emerald-900 mt-0.5">
                    {mostCompleted}
                  </div>
                </div>
              )}
              {mostNeglected && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-amber-800">
                    <AlertTriangle className="size-3.5" aria-hidden />
                    En çok aksatılan
                  </div>
                  <div className="text-base font-bold text-amber-900 mt-0.5">
                    {mostNeglected}
                    {mostNeglectedPct != null && (
                      <span className="text-sm font-semibold ml-1">
                        (%{mostNeglectedPct})
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-2.5">
              {subjects.map((s) => (
                <div key={s.subject_name}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-medium truncate">{s.subject_name}</span>
                    <span className="text-muted-foreground tabular-nums">
                      {s.completed}/{s.planned} test · %{s.pct}
                    </span>
                  </div>
                  <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        s.pct >= 70
                          ? "bg-emerald-500"
                          : s.pct >= 40
                            ? "bg-amber-500"
                            : "bg-rose-500",
                      )}
                      style={{ width: `${Math.min(100, s.pct)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Deneme performansı
// ============================================================================

function ExamSection({
  exams,
  trendDelta,
  trendSection,
}: {
  exams: WeeklyReportExam[];
  trendDelta: number | null;
  trendSection: string | null;
}) {
  if (exams.length === 0) {
    return (
      <Card>
        <CardContent className="p-5">
          <h2 className="font-semibold inline-flex items-center gap-1.5 mb-1">
            <GraduationCap className="size-4 text-[#117A86]" aria-hidden />
            Deneme Performansı
          </h2>
          <p className="text-xs text-muted-foreground italic mt-1">
            Son 60 günde girilmiş bir deneme sonucu yok.
          </p>
        </CardContent>
      </Card>
    );
  }
  const latest = exams[0];
  const TrendIcon =
    trendDelta == null
      ? Minus
      : trendDelta > 0
        ? TrendingUp
        : trendDelta < 0
          ? TrendingDown
          : Minus;
  const trendTone =
    trendDelta == null
      ? "text-muted-foreground"
      : trendDelta > 0
        ? "text-emerald-700"
        : trendDelta < 0
          ? "text-rose-700"
          : "text-muted-foreground";

  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-semibold inline-flex items-center gap-1.5 mb-3">
          <GraduationCap className="size-4 text-[#117A86]" aria-hidden />
          Deneme Performansı
        </h2>

        {/* Son deneme — büyük net */}
        <div className="rounded-lg border border-[#117A86]/20 bg-[#117A86]/5 px-4 py-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-semibold truncate" title={latest.title}>
              {latest.title}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
              <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-semibold text-[#117A86]">
                {latest.section_label}
              </span>
              <span>{fmtDate(latest.exam_date)}</span>
              <span className="text-muted-foreground/70">
                D {latest.total_correct} · Y {latest.total_wrong} · B{" "}
                {latest.total_blank}
              </span>
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Net
            </div>
            <div className="text-3xl font-extrabold tabular-nums text-[#117A86] leading-none">
              {latest.net.toLocaleString("tr-TR", { maximumFractionDigits: 2 })}
            </div>
            {trendDelta != null && trendSection && (
              <div
                className={cn(
                  "mt-1 inline-flex items-center gap-0.5 text-xs font-semibold tabular-nums",
                  trendTone,
                )}
              >
                <TrendIcon className="size-3.5" aria-hidden />
                {trendDelta > 0 ? "+" : ""}
                {trendDelta} net
              </div>
            )}
          </div>
        </div>
        {trendDelta != null && trendSection && (
          <p className="text-[11px] text-muted-foreground mt-2">
            {trendSection} türündeki bir önceki denemeye göre{" "}
            {trendDelta > 0
              ? "yükseliş"
              : trendDelta < 0
                ? "düşüş"
                : "değişim yok"}
            .
          </p>
        )}

        {/* Son denemeler listesi */}
        {exams.length > 1 && (
          <div className="mt-3 divide-y divide-border border-t border-border">
            {exams.slice(1).map((e, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-2 py-2 text-sm"
              >
                <div className="min-w-0">
                  <span className="font-medium truncate">{e.title}</span>
                  <span className="text-[11px] text-muted-foreground ml-2">
                    {e.section_label} · {fmtDate(e.exam_date)}
                  </span>
                </div>
                <span className="font-semibold tabular-nums text-foreground shrink-0">
                  {e.net.toLocaleString("tr-TR", { maximumFractionDigits: 2 })}{" "}
                  net
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Gün gün
// ============================================================================

function DailySection({ daily }: { daily: WeeklyReportDaily[] }) {
  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-semibold mb-1">Gün Gün</h2>
        <p className="text-xs text-muted-foreground mb-3">
          Her gün tamamlanan görev oranı ve çözülen test sayısı.
        </p>
        <div className="space-y-2">
          {daily.map((d) => (
            <DayRow key={d.date} day={d} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function DayRow({ day }: { day: WeeklyReportDaily }) {
  const empty = day.gorev_total === 0;
  const bar = day.pct >= 100 ? "bg-emerald-500" : day.pct > 0 ? "bg-amber-400" : "bg-muted";
  return (
    <div className="flex items-center gap-3">
      <span className="w-9 text-xs font-medium text-muted-foreground">
        {DAYS[day.weekday] ?? ""}
      </span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
        {!empty && (
          <div
            className={cn("h-full rounded-full", bar)}
            style={{ width: `${Math.min(100, day.pct)}%` }}
          />
        )}
      </div>
      <span className="w-36 text-right text-xs text-muted-foreground tabular-nums">
        {empty ? (
          <span className="italic">program yok</span>
        ) : (
          <>
            <span className="font-semibold text-foreground">%{day.pct}</span>
            {" · "}
            {day.gorev_done}/{day.gorev_total} görev
            {day.test_completed > 0 ? ` · ${day.test_completed} test` : ""}
          </>
        )}
      </span>
    </div>
  );
}

// ============================================================================
// Koç notları
// ============================================================================

function NotesSection({
  notes,
}: {
  notes: WeeklyReportResponse["teacher_notes"];
}) {
  if (notes.length === 0) return null;
  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-semibold inline-flex items-center gap-1.5 mb-3">
          <MessageSquare className="size-4 text-[#117A86]" aria-hidden />
          Koçtan Notlar
        </h2>
        <div className="space-y-3">
          {notes.map((n, i) => (
            <div
              key={i}
              className="border-l-4 border-[#117A86] bg-[#117A86]/5 pl-4 pr-3 py-2.5 rounded-r"
            >
              <div className="text-[11px] font-medium text-foreground/70 mb-1">
                {n.teacher_name ?? "Koç"}
                {n.created_at && (
                  <span className="text-muted-foreground font-normal">
                    {" · "}
                    {n.created_at.slice(0, 10).replaceAll("-", ".")}
                  </span>
                )}
              </div>
              <p className="text-sm whitespace-pre-line leading-relaxed">
                {n.body}
              </p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export type { WeeklyReportComparison };
