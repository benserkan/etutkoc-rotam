"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Bell,
  CheckCircle2,
  ExternalLink,
  HeartPulse,
  Hourglass,
  Info,
  TrendingUp,
  Users,
  type LucideIcon,
} from "lucide-react";

import { useTeacherDashboard } from "@/lib/hooks/use-teacher-queries";
import {
  getTeacherWarningsFeed,
  teacherKeys,
} from "@/lib/api/teacher";
import type {
  DashboardWarningRow,
  DashboardWarningsFeedResponse,
  TeacherDashboardResponse,
  WarningLevel,
} from "@/lib/types/teacher";
import { REQUEST_TYPE_LABELS_TR, RISK_LABELS_TR } from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Props {
  initial: TeacherDashboardResponse;
}

/**
 * Pano — filo durumu özeti, risk listesi, uyarı akışı ve son talepler.
 *
 * Paket 3.5d.2: Filo açıklamaları + tıklanabilir KPI'lar + Uyarı Akışı paneli.
 */
export function DashboardClient({ initial }: Props) {
  const q = useTeacherDashboard(initial);
  const data = q.data ?? initial;
  const isStale = q.isFetching && !q.isLoading;

  const weekPct = Math.round((data.week_completion_rate ?? 0) * 100);
  const todayPct =
    data.today_planned > 0
      ? Math.round((data.today_completed / data.today_planned) * 100)
      : 0;

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight font-display">
            Pano
          </h1>
          <p className="text-sm text-muted-foreground">
            Bütün öğrencilerinin durumuna tek bakışta göz at.
            {isStale ? (
              <span
                className="ml-2 text-xs text-muted-foreground/70"
                aria-live="polite"
              >
                · güncelleniyor…
              </span>
            ) : null}
          </p>
        </div>
      </header>

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          href="/teacher/students"
          icon={Users}
          label="Öğrenci"
          value={String(data.active_student_count)}
          sub={`Toplam ${data.student_count}`}
          tone="text-foreground"
        />
        <KpiCard
          href={
            data.at_risk_count > 0
              ? "/teacher/students?risk=critical"
              : "/teacher/students"
          }
          icon={AlertTriangle}
          label="Risk altı"
          value={String(data.at_risk_count)}
          sub={
            data.at_risk_critical > 0
              ? `${data.at_risk_critical} kritik · tıkla → listele`
              : "Tıkla → liste"
          }
          tone={
            data.at_risk_count > 0 ? "text-amber-500" : "text-muted-foreground"
          }
        />
        <KpiCard
          href="/teacher/requests"
          icon={Hourglass}
          label="Bekleyen talep"
          value={String(data.pending_requests_count)}
          sub="Onayını bekliyor"
          tone={
            data.pending_requests_count > 0
              ? "text-amber-500"
              : "text-muted-foreground"
          }
        />
        <KpiCard
          icon={TrendingUp}
          label="Bu hafta"
          value={`%${weekPct}`}
          sub={`${data.week_completed} / ${data.week_planned} tamam`}
          tone="text-emerald-500"
        />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-1 border-l-4 border-l-indigo-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
              <HeartPulse className="size-4 text-indigo-500" aria-hidden />
              Filo durumu
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
              Filo, tüm aktif öğrencilerin tek-bakışta sağlık durumu. Her öğrenci
              en kötü uyarısına göre yeşil/amber/kırmızıdır.
            </p>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <FleetRow
              href="/teacher/students?risk=ok"
              icon={CheckCircle2}
              label="Yolunda"
              value={data.fleet_green}
              tone="text-emerald-500"
            />
            <FleetRow
              href="/teacher/students?risk=medium"
              icon={AlertCircle}
              label="Uyarı"
              value={data.fleet_amber}
              tone="text-amber-500"
            />
            <FleetRow
              href="/teacher/students?risk=critical"
              icon={AlertOctagon}
              label="Kritik"
              value={data.fleet_red}
              tone="text-rose-500"
            />
            <div className="mt-3 pt-3 border-t border-border text-xs text-muted-foreground">
              Bugün planlanan: {data.today_planned} · tamamlanan{" "}
              {data.today_completed} (%{todayPct})
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
              <AlertTriangle className="size-4 text-amber-500" aria-hidden />
              En çok risk altındaki 5
            </CardTitle>
            {data.top_5_at_risk.length > 0 ? (
              <Link
                href="/teacher/students?risk=critical"
                className="text-xs text-indigo-500 hover:underline inline-flex items-center gap-1"
              >
                Tümünü gör
                <ArrowRight className="size-3" aria-hidden />
              </Link>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-1.5">
            {data.top_5_at_risk.length === 0 ? (
              <p className="text-sm text-muted-foreground inline-flex items-center gap-2">
                <CheckCircle2
                  className="size-4 text-emerald-500"
                  aria-hidden
                />
                Şu an risk altındaki bir öğrenci yok.
              </p>
            ) : (
              data.top_5_at_risk.map((r) => (
                <Link
                  key={r.student_id}
                  href={`/teacher/students/${r.student_id}`}
                  className="group flex items-start gap-3 rounded-md px-3 py-2 text-sm hover:bg-muted transition-colors"
                >
                  <RiskDot level={r.level} />
                  <span className="flex-1 min-w-0">
                    <span className="font-medium truncate block group-hover:underline">
                      {r.full_name}
                    </span>
                    {r.reasons.length > 0 ? (
                      <span className="text-xs text-muted-foreground line-clamp-1">
                        {r.reasons.join(" · ")}
                      </span>
                    ) : null}
                  </span>
                  <span className="text-xs text-muted-foreground shrink-0 inline-flex items-center gap-1">
                    {RISK_LABELS_TR[r.level]}
                    <ArrowRight
                      className="size-3 text-muted-foreground/60 group-hover:text-foreground transition"
                      aria-hidden
                    />
                  </span>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </section>

      <WarningsFeedSection />

      <section>
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
              <Bell className="size-4 text-sky-500" aria-hidden />
              Son talepler
            </CardTitle>
            {data.recent_requests.length > 0 ? (
              <Link
                href="/teacher/requests"
                className="text-xs text-indigo-500 hover:underline inline-flex items-center gap-1"
              >
                Tümünü gör
                <ArrowRight className="size-3" aria-hidden />
              </Link>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-1">
            {data.recent_requests.length === 0 ? (
              <p className="text-sm text-muted-foreground inline-flex items-center gap-2">
                <CheckCircle2
                  className="size-4 text-emerald-500"
                  aria-hidden
                />
                Bekleyen talep yok.
              </p>
            ) : (
              data.recent_requests.map((req) => (
                <Link
                  key={req.id}
                  href={`/teacher/requests/${req.id}`}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-muted transition-colors"
                >
                  <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground shrink-0 w-28 truncate">
                    {REQUEST_TYPE_LABELS_TR[req.type]}
                  </span>
                  <span className="font-medium truncate">{req.student_name}</span>
                  <span className="text-xs text-muted-foreground truncate flex-1">
                    {req.task_title ?? "—"}
                  </span>
                  <ExternalLink
                    className="size-3 text-muted-foreground/60 shrink-0"
                    aria-hidden
                  />
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function WarningsFeedSection() {
  const q = useQuery<DashboardWarningsFeedResponse>({
    queryKey: teacherKeys.warningsFeed(),
    queryFn: getTeacherWarningsFeed,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });

  return (
    <section>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
            <AlertCircle className="size-4 text-amber-500" aria-hidden />
            Uyarı Akışı
            {q.data ? (
              <span className="text-xs font-medium text-muted-foreground">
                — {q.data.total} aktif
              </span>
            ) : null}
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5 inline-flex items-start gap-1.5">
            <Info
              className="size-3 text-muted-foreground/70 flex-shrink-0 mt-0.5"
              aria-hidden
            />
            Tüm öğrencilerinin akıllı uyarıları — en kritikten başlayarak listelenir.
          </p>
        </CardHeader>
        <CardContent>
          {q.isLoading ? (
            <p className="text-sm text-muted-foreground">Yükleniyor…</p>
          ) : q.error || !q.data ? (
            <p className="text-sm text-rose-500">Uyarı akışı yüklenemedi.</p>
          ) : q.data.rows.length === 0 ? (
            <p className="text-sm text-emerald-500 inline-flex items-center gap-2">
              <CheckCircle2 className="size-4" aria-hidden />
              Aktif uyarı yok — herkes yolunda.
            </p>
          ) : (
            <ul className="divide-y divide-border max-h-[500px] overflow-y-auto -mx-2">
              {q.data.rows.map((w, idx) => (
                <WarningRow key={`${w.student_id}-${idx}`} row={w} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

function WarningRow({ row }: { row: DashboardWarningRow }) {
  const meta = LEVEL_META[row.level];
  const Icon = meta.icon;
  return (
    <li>
      <Link
        href={`/teacher/students/${row.student_id}`}
        className={cn(
          "flex items-start gap-2.5 px-3 py-2 hover:bg-muted/40 transition rounded-md",
          row.is_paused && "opacity-60",
        )}
      >
        <Icon
          className={cn("size-4 mt-0.5 flex-shrink-0", meta.tone)}
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between gap-2 flex-wrap">
            <span className={cn("text-sm font-semibold truncate", meta.tone)}>
              {row.title}
            </span>
            <span className="text-[11px] text-muted-foreground whitespace-nowrap inline-flex items-center gap-1">
              {row.is_paused ? (
                <span
                  className="text-[10px] uppercase tracking-wider px-1 py-0.5 rounded bg-muted text-muted-foreground"
                  title="Pasif — uyarı sessiz"
                >
                  pasif
                </span>
              ) : null}
              {row.student_name.split(" ")[0]}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
            {row.detail}
          </p>
        </div>
      </Link>
    </li>
  );
}

const LEVEL_META: Record<WarningLevel, { icon: LucideIcon; tone: string }> = {
  green: { icon: CheckCircle2, tone: "text-emerald-500" },
  amber: { icon: AlertCircle, tone: "text-amber-500" },
  red: { icon: AlertOctagon, tone: "text-rose-500" },
};

function KpiCard({
  href,
  icon: Icon,
  label,
  value,
  sub,
  tone,
}: {
  href?: string;
  icon: LucideIcon;
  label: string;
  value: string;
  sub?: string;
  tone: string;
}) {
  const body = (
    <CardContent className="p-4 space-y-1">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
        <Icon className={cn("size-3.5", tone)} aria-hidden />
        {label}
      </div>
      <p className={cn("text-2xl font-bold tabular-nums", tone)}>{value}</p>
      {sub ? (
        <p className="text-xs text-muted-foreground inline-flex items-center gap-1">
          {sub}
          {href ? (
            <ArrowRight
              className="size-3 text-muted-foreground/60 group-hover:text-foreground transition"
              aria-hidden
            />
          ) : null}
        </p>
      ) : null}
    </CardContent>
  );
  if (!href) return <Card>{body}</Card>;
  return (
    <Card className="group hover:bg-muted/30 transition cursor-pointer">
      <Link href={href} className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg">
        {body}
      </Link>
    </Card>
  );
}

function FleetRow({
  href,
  icon: Icon,
  label,
  value,
  tone,
}: {
  href: string;
  icon: LucideIcon;
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/40 transition"
    >
      <Icon className={cn("size-4", tone)} aria-hidden />
      <span className="text-sm flex-1 group-hover:underline">{label}</span>
      <span className={cn("text-sm font-bold tabular-nums", tone)}>{value}</span>
      <ArrowRight
        className="size-3 text-muted-foreground/60 group-hover:text-foreground transition"
        aria-hidden
      />
    </Link>
  );
}

function RiskDot({ level }: { level: WarningLevel | "critical" | "high" | "medium" | "ok" }) {
  const cls =
    level === "red" || level === "critical"
      ? "bg-rose-500"
      : level === "amber" || level === "high"
        ? "bg-amber-500"
        : level === "medium"
          ? "bg-yellow-400"
          : "bg-emerald-500";
  return (
    <span
      className={"mt-0.5 inline-block size-2 rounded-full " + cls}
      aria-hidden
    />
  );
}
