"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CalendarDays,
  Flame,
  Gauge,
  GraduationCap,
  LineChart,
  Loader2,
  Minus,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { getTeacherStudentAnalytics, teacherKeys } from "@/lib/api/teacher";
import type {
  AnalyticsDayFlag,
  AnalyticsDow,
  AnalyticsExamPoint,
  AnalyticsProjection,
  AnalyticsSubjectRow,
  AnalyticsSummary,
  AnalyticsTrendPoint,
  AnalyticsWarningItem,
  AnalyticsWeekPoint,
  TeacherStudentAnalyticsResponse,
} from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const DOW_LABELS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

interface Props {
  studentId: number;
}

/**
 * "Analitik" sekmesi — son 30 gün aktivite çizgisi + ders bazlı ilerleme.
 *
 * Parite: Jinja `partials/daily_trend_chart.html` + `subject_chart.html`. Chart.js
 * yerine SVG inline (Next.js bundle hafif, dark-mode uyumlu, hover tooltip).
 */
export function StudentAnalyticsPanel({ studentId }: Props) {
  const q = useQuery<TeacherStudentAnalyticsResponse>({
    queryKey: teacherKeys.studentAnalytics(studentId),
    queryFn: () => getTeacherStudentAnalytics(studentId),
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
    return (
      <div className="text-sm text-rose-500">Analitik verileri yüklenemedi.</div>
    );
  }

  const d = q.data;
  const activeWarnings = d.warnings.filter((w) => w.level !== "green");

  return (
    <div className="space-y-4">
      <SummaryStrip summary={d.summary} />
      <ProjectionCard projection={d.projection} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <WeeklyTrendCard weeks={d.weekly_trend} />
        <DowCard dows={d.dow_performance} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TrendChartCard trend={d.trend} windowDays={d.window_days} />
        <ActivityCalendarCard days={d.activity_calendar} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SubjectBarsCard subjects={d.subjects} />
        <ExamTrendCard
          exams={d.exam_trend}
          delta={d.exam_trend_delta}
          section={d.exam_trend_section}
        />
      </div>
      {activeWarnings.length > 0 ? (
        <WarningsCard warnings={activeWarnings} />
      ) : null}
    </div>
  );
}

// ============================================================================
// Tempo + istikrar manşeti
// ============================================================================

function levelTone(level: "green" | "amber" | "red") {
  if (level === "red") return { text: "text-rose-700", bg: "bg-rose-50", border: "border-rose-200", label: "Acil" };
  if (level === "amber") return { text: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", label: "Dikkat" };
  return { text: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200", label: "Yolunda" };
}

function StatTile({
  label,
  value,
  unit,
  sub,
  tone,
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("text-xl font-bold mt-0.5 tabular-nums", tone ?? "text-foreground")}>
        {value}
        {unit ? <span className="text-[11px] font-normal text-muted-foreground ml-1">{unit}</span> : null}
      </div>
      {sub ? <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div> : null}
    </div>
  );
}

function SummaryStrip({ summary: s }: { summary: AnalyticsSummary }) {
  const t = levelTone(s.worst_warning_level);
  return (
    <Card>
      <CardHeader className="pb-2 flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <Gauge className="size-4 text-cyan-600" aria-hidden />
          Çalışma Temposu
        </CardTitle>
        <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium border", t.bg, t.text, t.border)}>
          {t.label}
        </span>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          <StatTile label="Hız (7g)" value={`${s.rate_7d}`} unit="test/gün" />
          <StatTile label="Hız (30g)" value={`${s.rate_30d}`} unit="test/gün" />
          <StatTile label="Tutturma (7g)" value={`%${s.hit_rate_7d_pct}`} sub="planlanana göre" tone={t.text} />
          <StatTile label="İstikrar (7g)" value={`%${s.consistency_7d_pct}`} sub="aktif gün oranı" />
          <StatTile label="Aktif gün (30g)" value={`${s.active_days_30}/30`} sub={`en uzun seri ${s.longest_streak_30} gün`} />
          <StatTile label="İstikrar (30g)" value={`%${s.consistency_30d_pct}`} />
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Projeksiyon
// ============================================================================

function ProjectionCard({ projection: p }: { projection: AnalyticsProjection }) {
  const t = levelTone(p.status);
  const isYearEnd = !p.exam_label || p.exam_label === "Yıl Sonu";
  const title = isYearEnd ? "Yıl Sonuna Projeksiyon" : `${p.exam_label}'e Projeksiyon`;
  const statusLabel =
    p.status === "red" ? "Hedefin gerisinde" : p.status === "amber" ? "Tedbirli ilerliyor" : "Hedefe uygun";
  const confLabel =
    p.confidence_level === "high" ? "yüksek güven" : p.confidence_level === "medium" ? "orta güven" : "düşük güven";

  return (
    <Card>
      <CardHeader className="pb-2 flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <Target className="size-4 text-cyan-600" aria-hidden />
          {title}
        </CardTitle>
        <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium border", t.bg, t.text, t.border)}>
          {statusLabel}
        </span>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {p.days_left != null ? (
            <StatTile label={isYearEnd ? "Yıl sonuna" : "Sınava"} value={`${p.days_left}`} unit="gün" />
          ) : null}
          <StatTile label="Toplam hedef" value={`${p.total_tests}`} unit="test" />
          <StatTile label="Tamamlandı" value={`${p.completed}`} unit="test" tone="text-emerald-700" />
          <StatTile label="Kalan" value={`${p.remaining}`} unit="test" />
          <StatTile label="Beklenen erim" value={`${p.projected_completable}`} unit="test" tone={t.text} />
          <StatTile label="Günlük hız" value={`${p.rate_per_day}`} unit="test/gün" sub={`gereken ${p.required_rate}`} />
        </div>
        <p className="text-[11px] text-muted-foreground italic mt-3 leading-relaxed">
          Mevcut tempo ve son 28 günlük desene göre ({confLabel}) tahmin. Açık (gap):{" "}
          <b className={cn(p.gap < 0 ? "text-rose-600" : "text-emerald-600")}>
            {p.gap > 0 ? "+" : ""}{p.gap} test
          </b>{" "}
          {p.gap < 0 ? "— mevcut tempoyla hedefin altında kalır." : "— mevcut tempoyla hedefe ulaşır."}
        </p>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Haftalık tamamlama trendi
// ============================================================================

function barColor(pct: number): string {
  return pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-400" : "bg-rose-500";
}

function WeeklyTrendCard({ weeks }: { weeks: AnalyticsWeekPoint[] }) {
  const shown = weeks.filter((w) => w.planned > 0);
  const last = shown[shown.length - 1];
  const prev = shown[shown.length - 2];
  const delta = last && prev ? last.pct - prev.pct : null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <BarChart3 className="size-4 text-cyan-600" aria-hidden />
          Haftalık Tamamlama Trendi
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-0.5">
          Her haftanın görev tamamlama oranı — yükseliyor mu, düşüyor mu.
        </p>
      </CardHeader>
      <CardContent>
        {shown.length === 0 ? (
          <div className="h-[140px] flex items-center justify-center text-sm text-muted-foreground italic">
            Henüz haftalık veri yok.
          </div>
        ) : (
          <>
            <div className="flex items-end gap-1.5 h-[140px]">
              {shown.map((w) => (
                <div key={w.week_start} className="flex-1 flex flex-col items-center justify-end gap-1 group">
                  <span className="text-[9px] text-muted-foreground tabular-nums opacity-0 group-hover:opacity-100 transition-opacity">
                    %{w.pct}
                  </span>
                  <div className="w-full rounded-t bg-muted overflow-hidden flex items-end" style={{ height: "100%" }}>
                    <div
                      className={cn("w-full rounded-t transition-all", barColor(w.pct))}
                      style={{ height: `${Math.max(2, Math.min(100, w.pct))}%` }}
                      title={`${w.label}: %${w.pct} (${w.completed}/${w.planned})`}
                    />
                  </div>
                  <span className="text-[8px] text-muted-foreground">{w.label.split(" ")[0]}</span>
                </div>
              ))}
            </div>
            {delta != null ? (
              <div className="mt-2 text-xs inline-flex items-center gap-1">
                {delta > 0 ? (
                  <TrendingUp className="size-3.5 text-emerald-600" />
                ) : delta < 0 ? (
                  <TrendingDown className="size-3.5 text-rose-600" />
                ) : (
                  <Minus className="size-3.5 text-muted-foreground" />
                )}
                <span className={cn("font-semibold tabular-nums", delta > 0 ? "text-emerald-700" : delta < 0 ? "text-rose-700" : "text-muted-foreground")}>
                  {delta > 0 ? "+" : ""}{delta} puan
                </span>
                <span className="text-muted-foreground">geçen haftaya göre</span>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Haftanın günleri performansı
// ============================================================================

function DowCard({ dows }: { dows: AnalyticsDow[] }) {
  const maxAvg = Math.max(1, ...dows.map((d) => d.avg_completed));
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <CalendarDays className="size-4 text-cyan-600" aria-hidden />
          Haftanın Günleri
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-0.5">
          Hangi günler güçlü, hangileri zayıf (ortalama çözülen test + tutturma).
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {dows.map((dw) => (
            <div key={dw.weekday} className="flex items-center gap-3">
              <span className="w-8 text-xs font-medium text-muted-foreground">{dw.label}</span>
              <div className="flex-1 h-2.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn("h-full rounded-full", dw.measured ? barColor(dw.hit_pct) : "bg-muted-foreground/30")}
                  style={{ width: `${Math.min(100, (dw.avg_completed / maxAvg) * 100)}%` }}
                />
              </div>
              <span className="w-28 text-right text-[11px] text-muted-foreground tabular-nums">
                {dw.avg_completed} test
                {dw.measured ? <span className="ml-1">· %{dw.hit_pct}</span> : <span className="ml-1 italic">· veri yok</span>}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Aktivite takvimi (35 gün)
// ============================================================================

function ActivityCalendarCard({ days }: { days: AnalyticsDayFlag[] }) {
  // Pazartesi başlangıçlı haftalara böl (her hafta 7 hücre)
  const weeks: AnalyticsDayFlag[][] = [];
  let cur: AnalyticsDayFlag[] = [];
  for (const d of days) {
    if (d.weekday === 0 && cur.length > 0) {
      weeks.push(cur);
      cur = [];
    }
    cur.push(d);
  }
  if (cur.length > 0) weeks.push(cur);

  function cellTone(d: AnalyticsDayFlag): string {
    if (d.active) return "bg-emerald-500";
    if (d.has_plan) return "bg-rose-400/70"; // planlı ama tik yok
    return "bg-muted";
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <Activity className="size-4 text-cyan-600" aria-hidden />
          Aktivite Takvimi (35 gün)
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-0.5">
          Her gün öğrenci en az bir görev tikledi mi.
        </p>
      </CardHeader>
      <CardContent>
        <div className="flex gap-1.5">
          {/* gün etiketleri */}
          <div className="flex flex-col gap-1 pr-1 justify-between py-0.5">
            {DOW_LABELS.map((l, i) => (
              <span key={l} className="text-[8px] text-muted-foreground leading-none h-3 flex items-center">
                {i % 2 === 0 ? l : ""}
              </span>
            ))}
          </div>
          <div className="flex gap-1 flex-1">
            {weeks.map((wk, wi) => (
              <div key={wi} className="flex flex-col gap-1 flex-1">
                {Array.from({ length: 7 }).map((_, dow) => {
                  const cell = wk.find((c) => c.weekday === dow);
                  if (!cell) return <div key={dow} className="h-3 rounded-sm bg-transparent" />;
                  return (
                    <div
                      key={dow}
                      className={cn("h-3 rounded-sm", cellTone(cell))}
                      title={`${cell.date}: ${cell.active ? "aktif" : cell.has_plan ? "planlı ama tik yok" : "plan yok"}`}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
        <div className="mt-3 flex items-center gap-3 text-[10px] text-muted-foreground flex-wrap">
          <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-emerald-500" /> aktif</span>
          <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-rose-400/70" /> planlı, tik yok</span>
          <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-muted" /> plan yok</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Deneme net trendi
// ============================================================================

function ExamTrendCard({
  exams,
  delta,
  section,
}: {
  exams: AnalyticsExamPoint[];
  delta: number | null;
  section: string | null;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <GraduationCap className="size-4 text-cyan-600" aria-hidden />
          Deneme Net Trendi
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-0.5">Son denemeler ve net değişimi.</p>
      </CardHeader>
      <CardContent>
        {exams.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground italic">
            Son 60 günde girilmiş deneme yok.
          </div>
        ) : (
          <>
            {delta != null && section ? (
              <div className="mb-2 inline-flex items-center gap-1.5 text-sm">
                {delta > 0 ? (
                  <TrendingUp className="size-4 text-emerald-600" />
                ) : delta < 0 ? (
                  <TrendingDown className="size-4 text-rose-600" />
                ) : (
                  <Minus className="size-4 text-muted-foreground" />
                )}
                <span className={cn("font-semibold tabular-nums", delta > 0 ? "text-emerald-700" : delta < 0 ? "text-rose-700" : "text-muted-foreground")}>
                  {delta > 0 ? "+" : ""}{delta} net
                </span>
                <span className="text-xs text-muted-foreground">son {section} denemesi</span>
              </div>
            ) : null}
            <div className="divide-y divide-border">
              {exams.map((e, i) => (
                <div key={i} className="flex items-center justify-between gap-2 py-1.5 text-sm">
                  <div className="min-w-0">
                    <span className="font-medium truncate">{e.title}</span>
                    <span className="text-[11px] text-muted-foreground ml-2">
                      {e.section_label}
                      {e.exam_date ? ` · ${e.exam_date.slice(5).replace("-", ".")}` : ""}
                    </span>
                  </div>
                  <span className="font-bold tabular-nums text-cyan-700 shrink-0">
                    {e.net.toLocaleString("tr-TR", { maximumFractionDigits: 2 })} net
                  </span>
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
// Risk sinyalleri
// ============================================================================

function WarningsCard({ warnings }: { warnings: AnalyticsWarningItem[] }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <AlertTriangle className="size-4 text-amber-500" aria-hidden />
          Dikkat Sinyalleri
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {warnings.map((w, i) => {
            const isRed = w.level === "red";
            return (
              <div
                key={i}
                className={cn(
                  "rounded-lg border-l-4 px-3 py-2",
                  isRed ? "border-l-rose-500 bg-rose-50" : "border-l-amber-400 bg-amber-50",
                )}
              >
                <div className={cn("text-sm font-semibold inline-flex items-center gap-1.5", isRed ? "text-rose-800" : "text-amber-800")}>
                  {isRed ? <Flame className="size-3.5" /> : <AlertTriangle className="size-3.5" />}
                  {w.title}
                </div>
                {w.detail ? (
                  <div className={cn("text-xs mt-0.5", isRed ? "text-rose-700" : "text-amber-700")}>{w.detail}</div>
                ) : null}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function TrendChartCard({
  trend,
  windowDays,
}: {
  trend: AnalyticsTrendPoint[];
  windowDays: number;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <LineChart className="size-4 text-emerald-500" aria-hidden />
          Son {windowDays} Gün Aktivite
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-0.5">
          Günlük tamamlanan test (yeşil) ile o güne atanan plan (kesik gri).
        </p>
      </CardHeader>
      <CardContent>
        <TrendChartSvg trend={trend} />
        <div className="mt-3 flex items-center gap-4 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-3 h-0.5 bg-emerald-500" />
            Tamamlanan
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block w-3 h-0.5"
              style={{
                background:
                  "repeating-linear-gradient(90deg, currentColor 0 4px, transparent 4px 8px)",
                color: "rgb(148 163 184)",
              }}
            />
            Planlanan
          </span>
          <span className="ml-auto text-muted-foreground/80 italic hidden sm:inline">
            Yeşil grinin üstündeyse o gün hedef tutturulmuştur.
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function TrendChartSvg({ trend }: { trend: AnalyticsTrendPoint[] }) {
  const [hover, setHover] = React.useState<number | null>(null);
  const width = 600;
  const height = 200;
  const padding = { top: 16, right: 12, bottom: 28, left: 28 };

  const maxY = React.useMemo(() => {
    let m = 1;
    for (const p of trend) {
      if (p.completed > m) m = p.completed;
      if (p.planned > m) m = p.planned;
    }
    return Math.ceil(m * 1.1);
  }, [trend]);

  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  if (trend.length === 0) {
    return (
      <div className="h-[200px] flex items-center justify-center text-sm text-muted-foreground italic">
        Henüz veri yok.
      </div>
    );
  }

  const xStep = trend.length > 1 ? innerW / (trend.length - 1) : 0;
  const xAt = (i: number) => padding.left + i * xStep;
  const yAt = (v: number) => padding.top + innerH - (v / maxY) * innerH;

  const completedPath = trend
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(p.completed).toFixed(1)}`)
    .join(" ");
  const plannedPath = trend
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(p.planned).toFixed(1)}`)
    .join(" ");
  const fillPath =
    completedPath +
    ` L ${xAt(trend.length - 1).toFixed(1)} ${(padding.top + innerH).toFixed(1)}` +
    ` L ${xAt(0).toFixed(1)} ${(padding.top + innerH).toFixed(1)} Z`;

  const yTicks = [0, Math.round(maxY / 2), maxY];

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Son 30 gün aktivite çizgisi"
      >
        {/* Yatay grid */}
        {yTicks.map((t) => (
          <line
            key={`g-${t}`}
            x1={padding.left}
            y1={yAt(t)}
            x2={width - padding.right}
            y2={yAt(t)}
            stroke="currentColor"
            className="text-border"
            strokeWidth="1"
            strokeDasharray={t === 0 ? "0" : "2 3"}
          />
        ))}
        {/* Y-axis labels */}
        {yTicks.map((t) => (
          <text
            key={`yt-${t}`}
            x={padding.left - 6}
            y={yAt(t) + 3}
            textAnchor="end"
            className="fill-muted-foreground"
            fontSize="9"
          >
            {t}
          </text>
        ))}
        {/* Fill */}
        <path d={fillPath} className="fill-emerald-500/10" />
        {/* Planlanan (dashed gri) */}
        <path
          d={plannedPath}
          fill="none"
          stroke="currentColor"
          className="text-muted-foreground/60"
          strokeWidth="1.5"
          strokeDasharray="4 4"
        />
        {/* Tamamlanan (yeşil) */}
        <path
          d={completedPath}
          fill="none"
          stroke="currentColor"
          className="text-emerald-500"
          strokeWidth="2"
        />
        {/* Points */}
        {trend.map((p, i) => (
          <circle
            key={`pt-${i}`}
            cx={xAt(i)}
            cy={yAt(p.completed)}
            r={hover === i ? 4 : 2}
            className={cn(
              "fill-emerald-500 transition-all",
              hover === i ? "stroke-emerald-300" : "",
            )}
            strokeWidth={hover === i ? 1.5 : 0}
          />
        ))}
        {/* Hover overlays */}
        {trend.map((p, i) => (
          <rect
            key={`hv-${i}`}
            x={xAt(i) - xStep / 2}
            y={padding.top}
            width={xStep}
            height={innerH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            style={{ cursor: "pointer" }}
          />
        ))}
        {/* X-axis ticks — her 5. günde bir */}
        {trend.map((p, i) => {
          if (i % 5 !== 0 && i !== trend.length - 1) return null;
          return (
            <text
              key={`xt-${i}`}
              x={xAt(i)}
              y={height - padding.bottom + 14}
              textAnchor="middle"
              className="fill-muted-foreground"
              fontSize="9"
            >
              {p.label}
            </text>
          );
        })}
      </svg>
      {hover !== null ? (
        <div
          className="absolute pointer-events-none rounded-md border border-border bg-popover px-2 py-1.5 shadow-md text-xs"
          style={{
            left: `${(xAt(hover) / width) * 100}%`,
            top: `${(yAt(trend[hover].completed) / height) * 100}%`,
            transform: "translate(-50%, calc(-100% - 8px))",
          }}
        >
          <div className="font-semibold text-foreground">{trend[hover].label}</div>
          <div className="text-emerald-500 tabular-nums">
            Tamamlanan: {trend[hover].completed}
          </div>
          <div className="text-muted-foreground tabular-nums">
            Planlanan: {trend[hover].planned}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SubjectBarsCard({ subjects }: { subjects: AnalyticsSubjectRow[] }) {
  const totalDone = subjects.reduce((sum, s) => sum + s.completed, 0);
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <BarChart3 className="size-4 text-indigo-500" aria-hidden />
          Ders Bazında İlerleme
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-0.5">
          Her ders için tamamlanma (yeşil) ve rezerv (sarı) oranı.
        </p>
      </CardHeader>
      <CardContent>
        {subjects.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground italic">
            Henüz veri yok.
          </div>
        ) : (
          <div className="space-y-3">
            {subjects.map((s) => (
              <SubjectBar key={s.subject_id} row={s} />
            ))}
            <div className="pt-2 mt-2 border-t border-border text-[11px] text-muted-foreground inline-flex items-center gap-1.5">
              <TrendingUp className="size-3" aria-hidden />
              Toplam <b className="text-foreground tabular-nums">{totalDone}</b>{" "}
              test tamamlandı.
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SubjectBar({ row }: { row: AnalyticsSubjectRow }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm mb-1 gap-2">
        <span className="font-medium text-foreground truncate">{row.name}</span>
        <span className="text-xs text-muted-foreground whitespace-nowrap tabular-nums">
          <b className="text-emerald-500">{row.completed}</b> / {row.total}
          <span className="text-muted-foreground/70 ml-1.5">
            %{row.percent_done}
          </span>
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden flex">
        <div
          className="bg-emerald-500 h-full transition-all"
          style={{ width: `${row.percent_done}%` }}
        />
        <div
          className="bg-amber-500 h-full transition-all"
          style={{ width: `${row.percent_reserved}%` }}
        />
      </div>
      {row.reserved > 0 ? (
        <div className="text-[11px] text-muted-foreground mt-0.5">
          {row.reserved} rezerv · {row.remaining} kalan
        </div>
      ) : null}
    </div>
  );
}
