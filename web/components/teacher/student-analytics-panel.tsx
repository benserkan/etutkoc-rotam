"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, LineChart, Loader2, TrendingUp } from "lucide-react";

import { getTeacherStudentAnalytics, teacherKeys } from "@/lib/api/teacher";
import type {
  AnalyticsSubjectRow,
  AnalyticsTrendPoint,
  TeacherStudentAnalyticsResponse,
} from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <TrendChartCard trend={q.data.trend} windowDays={q.data.window_days} />
      <SubjectBarsCard subjects={q.data.subjects} />
    </div>
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
