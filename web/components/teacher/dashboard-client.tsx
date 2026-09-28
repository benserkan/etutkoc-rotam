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
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  HeartPulse,
  Hourglass,
  Info,
  Loader2,
  RotateCcw,
  TrendingUp,
  Users,
  type LucideIcon,
} from "lucide-react";

import { QuickAccessStrip } from "@/components/quick-access-strip";
import { useTeacherDashboard } from "@/lib/hooks/use-teacher-queries";
import { getTeacherWarningsFeed, teacherKeys } from "@/lib/api/teacher";
import { useAckWarning, useUnackWarning } from "@/lib/hooks/use-teacher-mutations";
import type {
  DashboardWarningRow,
  DashboardWarningsFeedResponse,
  TeacherDashboardResponse,
  WarningLevel,
} from "@/lib/types/teacher";
import { REQUEST_TYPE_LABELS_TR, RISK_LABELS_TR } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";
import { ShareExperiencePrompt } from "@/components/testimonials/share-experience-prompt";

interface Props {
  initial: TeacherDashboardResponse;
}

const TR_DAYS = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

function todayLabel(): string {
  const d = new Date();
  return `${d.getDate()} ${TR_MONTHS[d.getMonth()]} ${TR_DAYS[d.getDay()]}`;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toLocaleUpperCase("tr-TR"))
    .join("");
}

/**
 * Koç panosu — öğrencilerin durumu, risk listesi, uyarı akışı, son talepler.
 * 2026-09-29 yeniden tasarım: KPI şeridi + dağılım barı + öğrenci bazlı
 * gruplanmış, kanıtlı uyarı akışı.
 */
export function DashboardClient({ initial }: Props) {
  const q = useTeacherDashboard(initial);
  const data = q.data ?? initial;
  const isStale = q.isFetching && !q.isLoading;

  const weekPct = Math.round(
    ((data.gorev_week_total ?? 0) > 0
      ? (data.gorev_week_rate ?? 0)
      : (data.week_completion_rate ?? 0)) * 100,
  );
  const todayTotal = data.gorev_today_total ?? 0;
  const todayPct =
    todayTotal > 0
      ? Math.round((data.gorev_today_done / todayTotal) * 100)
      : data.today_planned > 0
        ? Math.round((data.today_completed / data.today_planned) * 100)
        : 0;
  const openQ = data.open_question_count ?? 0;

  return (
    <div className="space-y-6">
      <ShareExperiencePrompt />
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {todayLabel()}
          </p>
          <h1 className="font-display text-2xl font-semibold tracking-tight">Pano</h1>
          <p className="text-sm text-muted-foreground">
            Bütün öğrencilerinin durumuna tek bakışta göz at.
            {isStale ? (
              <span className="ml-2 text-xs text-muted-foreground/70" aria-live="polite">
                · güncelleniyor…
              </span>
            ) : null}
          </p>
        </div>
      </header>

      <QuickAccessStrip excludeHrefs={["/teacher/students"]} />

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          href="/teacher/students"
          icon={Users}
          accent="indigo"
          label="Aktif öğrenci"
          value={String(data.active_student_count)}
          sub={`Toplam ${data.student_count} öğrenci kaydı`}
        />
        <KpiCard
          href={data.at_risk_count > 0 ? "/teacher/students?risk=at_risk" : "/teacher/students"}
          icon={AlertTriangle}
          accent={data.at_risk_count > 0 ? "amber" : "slate"}
          label="Risk altında"
          value={String(data.at_risk_count)}
          sub={
            data.at_risk_critical > 0
              ? `öğrenci · ${data.at_risk_critical} kritik`
              : "öğrenci · risk puanına göre"
          }
        />
        <KpiCard
          href="/teacher/requests"
          icon={Hourglass}
          accent={data.pending_requests_count > 0 || openQ > 0 ? "amber" : "slate"}
          label="Bekleyen talep"
          value={String(data.pending_requests_count)}
          sub={
            openQ > 0
              ? `onayını bekliyor · +${openQ} soru/not mesajı`
              : "onayını bekliyor"
          }
        />
        <KpiCard
          icon={TrendingUp}
          accent="emerald"
          label="Görev tamamlama"
          value={`%${weekPct}`}
          sub={
            (data.gorev_week_total ?? 0) > 0
              ? `son 7 gün · ${data.gorev_week_done}/${data.gorev_week_total} görev · ${data.test_week_completed}/${data.test_week_planned} test`
              : `son 7 gün · ${data.week_completed}/${data.week_planned} test`
          }
        />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <FleetCard data={data} todayPct={todayPct} />
        <TopRiskCard data={data} />
      </section>

      <WarningsFeedSection />

      <RecentRequestsCard data={data} />
    </div>
  );
}

// ---------------------------------------------------------------- KPI

const ACCENT: Record<string, { chip: string; value: string; bar: string }> = {
  indigo: { chip: "bg-indigo-600 text-white", value: "text-foreground", bar: "bg-indigo-500" },
  amber: { chip: "bg-amber-500 text-slate-950", value: "text-amber-600 dark:text-amber-400", bar: "bg-amber-500" },
  emerald: { chip: "bg-emerald-600 text-white", value: "text-emerald-600 dark:text-emerald-400", bar: "bg-emerald-500" },
  slate: { chip: "bg-slate-600 text-white", value: "text-foreground", bar: "bg-slate-400" },
};

function KpiCard({
  href,
  icon: Icon,
  accent,
  label,
  value,
  sub,
}: {
  href?: string;
  icon: LucideIcon;
  accent: keyof typeof ACCENT;
  label: string;
  value: string;
  sub: string;
}) {
  const a = ACCENT[accent] ?? ACCENT.slate;
  const body = (
    <div className="relative flex h-full items-start gap-3 overflow-hidden rounded-xl border border-border bg-card p-4 shadow-sm transition group-hover:shadow-md">
      <span className={cn("absolute inset-x-0 top-0 h-1", a.bar)} aria-hidden />
      <span className={cn("grid size-10 shrink-0 place-items-center rounded-lg", a.chip)}>
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className={cn("text-3xl font-bold tabular-nums leading-tight", a.value)}>{value}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>
      </div>
      {href ? (
        <ArrowRight
          className="mt-1 size-4 shrink-0 text-muted-foreground/50 transition group-hover:translate-x-0.5 group-hover:text-foreground"
          aria-hidden
        />
      ) : null}
    </div>
  );
  if (!href) return body;
  return (
    <Link
      href={href}
      className="group block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {body}
    </Link>
  );
}

// ---------------------------------------------------------------- Öğrencilerin durumu

function FleetCard({ data, todayPct }: { data: TeacherDashboardResponse; todayPct: number }) {
  const total = data.fleet_green + data.fleet_amber + data.fleet_red;
  const seg = (n: number) => (total > 0 ? `${(n / total) * 100}%` : "0%");
  const rows: { href: string; icon: LucideIcon; label: string; value: number; dot: string; text: string }[] = [
    { href: "/teacher/students?risk=ok", icon: CheckCircle2, label: "Yolunda", value: data.fleet_green, dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" },
    { href: "/teacher/students?risk=medium", icon: AlertCircle, label: "Uyarı", value: data.fleet_amber, dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400" },
    { href: "/teacher/students?risk=critical", icon: AlertOctagon, label: "Kritik", value: data.fleet_red, dot: "bg-rose-500", text: "text-rose-600 dark:text-rose-400" },
  ];
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="inline-flex items-center gap-2 text-base font-semibold">
        <HeartPulse className="size-4 text-indigo-500" aria-hidden />
        Öğrencilerin durumu
      </h2>
      <p className="mt-0.5 text-xs text-muted-foreground">
        Aktif öğrencilerin risk puanına göre dağılımı. Satıra tıkla, o öğrencileri gör.
      </p>
      <div
        className="mt-4 flex h-3 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`${data.fleet_green} yolunda, ${data.fleet_amber} uyarı, ${data.fleet_red} kritik`}
      >
        <span className="bg-emerald-500" style={{ width: seg(data.fleet_green) }} />
        <span className="bg-amber-500" style={{ width: seg(data.fleet_amber) }} />
        <span className="bg-rose-500" style={{ width: seg(data.fleet_red) }} />
      </div>
      <ul className="mt-3 space-y-1">
        {rows.map((r) => (
          <li key={r.label}>
            <Link
              href={r.href}
              className="group flex items-center gap-2.5 rounded-lg px-2 py-2 transition hover:bg-muted/60"
            >
              <span className={cn("size-2.5 rounded-full", r.dot)} aria-hidden />
              <span className="flex-1 text-sm group-hover:underline">{r.label}</span>
              <span className={cn("text-sm font-bold tabular-nums", r.text)}>
                {r.value} öğrenci
              </span>
              <ArrowRight className="size-3.5 text-muted-foreground/50 group-hover:text-foreground" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
      <div className="mt-3 rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
        {(data.gorev_today_total ?? 0) > 0
          ? `Bugün ${data.gorev_today_done}/${data.gorev_today_total} görev tamamlandı (%${todayPct})`
          : `Bugün planlanan ${data.today_planned} test · tamamlanan ${data.today_completed} test (%${todayPct})`}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Risk listesi

const RISK_BADGE: Record<string, string> = {
  critical: "bg-rose-600 text-white",
  high: "bg-orange-500 text-white",
  medium: "bg-amber-400 text-slate-950",
  ok: "bg-emerald-600 text-white",
};

function TopRiskCard({ data }: { data: TeacherDashboardResponse }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm lg:col-span-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="inline-flex items-center gap-2 text-base font-semibold">
          <AlertTriangle className="size-4 text-amber-500" aria-hidden />
          En çok risk altındaki 5 öğrenci
        </h2>
        {data.top_5_at_risk.length > 0 ? (
          <Link
            href="/teacher/students?risk=at_risk"
            className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
          >
            Tümünü gör <ArrowRight className="size-3" aria-hidden />
          </Link>
        ) : null}
      </div>
      {data.top_5_at_risk.length === 0 ? (
        <p className="mt-4 inline-flex items-center gap-2 text-sm text-muted-foreground">
          <CheckCircle2 className="size-4 text-emerald-500" aria-hidden />
          Şu an risk altındaki bir öğrenci yok.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {data.top_5_at_risk.map((r) => (
            <li key={r.student_id}>
              <Link
                href={`/teacher/students/${r.student_id}`}
                className="group flex items-start gap-3 rounded-lg px-2 py-2.5 transition hover:bg-muted/60"
              >
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-muted text-xs font-semibold">
                  {initials(r.full_name)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block break-words text-sm font-medium group-hover:underline">
                    {r.full_name}
                  </span>
                  {r.reasons.length > 0 ? (
                    <span className="mt-0.5 flex flex-wrap gap-1">
                      {r.reasons.map((why) => (
                        <span
                          key={why}
                          className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
                        >
                          {why}
                        </span>
                      ))}
                    </span>
                  ) : null}
                </span>
                <span
                  className={cn(
                    "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                    RISK_BADGE[r.level] ?? RISK_BADGE.medium,
                  )}
                >
                  {RISK_LABELS_TR[r.level]}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Uyarı akışı

const LEVEL_META: Record<WarningLevel, { icon: LucideIcon; tone: string; badge: string; label: string; rail: string }> = {
  red: { icon: AlertOctagon, tone: "text-rose-600 dark:text-rose-400", badge: "bg-rose-600 text-white", label: "Acil", rail: "border-l-rose-500" },
  amber: { icon: AlertCircle, tone: "text-amber-600 dark:text-amber-400", badge: "bg-amber-500 text-slate-950", label: "Dikkat", rail: "border-l-amber-500" },
  green: { icon: CheckCircle2, tone: "text-emerald-600 dark:text-emerald-400", badge: "bg-emerald-600 text-white", label: "Bilgi", rail: "border-l-emerald-500" },
};
const LEVEL_RANK: Record<WarningLevel, number> = { red: 0, amber: 1, green: 2 };
const GROUPS_INITIAL = 6;

interface StudentGroup {
  student_id: number;
  student_name: string;
  is_paused: boolean;
  worst: WarningLevel;
  rows: DashboardWarningRow[];
}

function groupByStudent(rows: DashboardWarningRow[]): StudentGroup[] {
  const map = new Map<number, StudentGroup>();
  for (const r of rows) {
    const g = map.get(r.student_id) ?? {
      student_id: r.student_id,
      student_name: r.student_name,
      is_paused: r.is_paused,
      worst: r.level,
      rows: [],
    };
    g.rows.push(r);
    if (LEVEL_RANK[r.level] < LEVEL_RANK[g.worst]) g.worst = r.level;
    map.set(r.student_id, g);
  }
  const groups = [...map.values()];
  for (const g of groups) g.rows.sort((a, b) => LEVEL_RANK[a.level] - LEVEL_RANK[b.level]);
  groups.sort(
    (a, b) =>
      LEVEL_RANK[a.worst] - LEVEL_RANK[b.worst] ||
      b.rows.length - a.rows.length ||
      a.student_name.localeCompare(b.student_name, "tr"),
  );
  return groups;
}

function WarningsFeedSection() {
  const q = useQuery<DashboardWarningsFeedResponse>({
    queryKey: teacherKeys.warningsFeed(),
    queryFn: getTeacherWarningsFeed,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const [showAll, setShowAll] = React.useState(false);
  const groups = React.useMemo(() => groupByStudent(q.data?.rows ?? []), [q.data]);
  const redCount = (q.data?.rows ?? []).filter((r) => r.level === "red").length;
  const visible = showAll ? groups : groups.slice(0, GROUPS_INITIAL);

  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm" data-section="dashboard:warnings">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="inline-flex items-center gap-2 text-base font-semibold">
            <AlertCircle className="size-4 text-amber-500" aria-hidden />
            Uyarı Akışı
          </h2>
          {q.data ? (
            <p className="mt-0.5 text-sm text-muted-foreground" data-testid="warnings-summary">
              {q.data.total === 0
                ? "Aktif uyarı yok."
                : `${groups.length} öğrencide ${q.data.total} uyarı` +
                  (redCount > 0 ? ` · ${redCount} acil` : "")}
            </p>
          ) : null}
        </div>
      </div>
      <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          Uyarılar her açılışta öğrencinin güncel verisinden yeniden hesaplanır; haftalık
          sıfırlanmaz. Koşul düzelince uyarı kendiliğinden kalkar. “Gördüm” 3 gün, “7 gün”
          bir hafta gizler; koşul o süre sonunda hâlâ sürüyorsa uyarı geri gelir. Her
          uyarıda “Neden?” ile hesabın dayandığı veriyi görebilirsin.
        </span>
      </p>

      <div className="mt-4">
        {q.isLoading ? (
          <p className="text-sm text-muted-foreground">Yükleniyor…</p>
        ) : q.error || !q.data ? (
          <p className="text-sm text-rose-600">Uyarı akışı yüklenemedi.</p>
        ) : groups.length === 0 ? (
          <p className="inline-flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-4" aria-hidden />
            Aktif uyarı yok — herkes yolunda.
          </p>
        ) : (
          <>
            <ul className="space-y-3">
              {visible.map((g) => (
                <StudentWarningGroup key={g.student_id} group={g} />
              ))}
            </ul>
            {groups.length > GROUPS_INITIAL ? (
              <button
                type="button"
                onClick={() => setShowAll((v) => !v)}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-muted"
              >
                <ChevronDown className={cn("size-4 transition", showAll && "rotate-180")} aria-hidden />
                {showAll ? "Daha az göster" : `Tüm öğrencileri göster (${groups.length})`}
              </button>
            ) : null}
          </>
        )}
        {q.data && q.data.snoozed_count > 0 ? (
          <SnoozedSection rows={q.data.snoozed_rows} count={q.data.snoozed_count} />
        ) : null}
      </div>
    </section>
  );
}

function StudentWarningGroup({ group }: { group: StudentGroup }) {
  const meta = LEVEL_META[group.worst];
  return (
    <li
      className={cn(
        "rounded-lg border border-border border-l-4 bg-background/40",
        meta.rail,
        group.is_paused && "opacity-70",
      )}
      data-testid="warning-group"
    >
      <div className="flex flex-wrap items-center gap-2.5 px-3 py-2.5">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-muted text-xs font-semibold">
          {initials(group.student_name)}
        </span>
        <Link
          href={`/teacher/students/${group.student_id}`}
          className="min-w-0 flex-1 break-words text-sm font-semibold hover:underline"
        >
          {group.student_name}
        </Link>
        <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", meta.badge)}>
          {meta.label}
        </span>
        <span className="text-xs text-muted-foreground">{group.rows.length} uyarı</span>
      </div>
      <ul className="divide-y divide-border border-t border-border">
        {group.rows.map((w) => (
          <WarningItemRow key={w.code} row={w} />
        ))}
      </ul>
    </li>
  );
}

function ageLabel(days: number): string {
  if (days <= 0) return "bugün başladı";
  if (days === 1) return "1 gündür";
  return `${days} gündür`;
}

function WarningItemRow({ row }: { row: DashboardWarningRow }) {
  const meta = LEVEL_META[row.level];
  const Icon = meta.icon;
  const ack = useAckWarning();
  const [open, setOpen] = React.useState(false);
  const evidence = row.evidence ?? [];
  return (
    <li className="px-3 py-2.5" data-testid="warning-item" data-code={row.code}>
      <div className="flex flex-wrap items-start gap-2">
        <Icon className={cn("mt-0.5 size-4 shrink-0", meta.tone)} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className={cn("text-sm font-semibold", meta.tone)}>{row.title}</p>
          <p className="mt-0.5 text-xs text-foreground/80">{row.detail}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1" title="Bu uyarı kaç gündür sürüyor">
              <Clock className="size-3" aria-hidden />
              {ageLabel(row.age_days)}
            </span>
            {evidence.length > 0 ? (
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                className="inline-flex items-center gap-0.5 font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                data-testid="warning-why"
              >
                <ChevronDown className={cn("size-3 transition", open && "rotate-180")} aria-hidden />
                Neden?
              </button>
            ) : null}
            {row.link ? (
              <Link
                href={row.link}
                className="inline-flex items-center gap-0.5 font-medium text-indigo-600 hover:underline dark:text-indigo-400"
              >
                {row.link_label ?? "İncele"} <ArrowRight className="size-3" aria-hidden />
              </Link>
            ) : null}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={() => ack.mutate({ student_id: row.student_id, code: row.code, snooze_days: 3 })}
            disabled={ack.isPending}
            title="Gördüm — 3 gün akıştan gizle (koşul sürerse geri döner)"
            className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
          >
            {ack.isPending ? <Loader2 className="size-3 animate-spin" aria-hidden /> : <Check className="size-3" aria-hidden />}
            Gördüm
          </button>
          <button
            type="button"
            onClick={() => ack.mutate({ student_id: row.student_id, code: row.code, snooze_days: 7 })}
            disabled={ack.isPending}
            title="7 gün ertele"
            className="rounded-md border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
          >
            7 gün
          </button>
        </div>
      </div>
      {open && evidence.length > 0 ? (
        <dl
          className="ml-6 mt-2 grid grid-cols-1 gap-x-4 gap-y-1 rounded-md bg-muted/60 px-3 py-2 text-xs sm:grid-cols-[auto_1fr]"
          data-testid="warning-evidence"
        >
          {evidence.map((e) => (
            <React.Fragment key={e.label}>
              <dt className="font-medium text-muted-foreground">{e.label}</dt>
              <dd className="break-words text-foreground">{e.value}</dd>
            </React.Fragment>
          ))}
        </dl>
      ) : null}
    </li>
  );
}

function SnoozedSection({ rows, count }: { rows: DashboardWarningRow[]; count: number }) {
  const [open, setOpen] = React.useState(false);
  const unack = useUnackWarning();
  return (
    <div className="mt-4 border-t border-border pt-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronDown className={cn("size-3.5 transition", open && "rotate-180")} aria-hidden />
        Gizlediğin uyarılar ({count})
      </button>
      {open ? (
        <ul className="mt-2 divide-y divide-border/60">
          {rows.map((w) => (
            <li key={`sn-${w.student_id}-${w.code}`} className="flex flex-wrap items-center gap-2 py-1.5">
              <div className="min-w-0 flex-1 text-xs">
                <Link href={`/teacher/students/${w.student_id}`} className="font-medium hover:underline">
                  {w.student_name}
                </Link>
                <span className="text-muted-foreground"> · {w.title}</span>
              </div>
              <button
                type="button"
                onClick={() => unack.mutate({ student_id: w.student_id, code: w.code })}
                disabled={unack.isPending}
                title="Geri al — uyarıyı akışa döndür"
                className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-[11px] font-medium hover:bg-muted"
              >
                <RotateCcw className="size-3" aria-hidden />
                Geri al
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- Son talepler

function RecentRequestsCard({ data }: { data: TeacherDashboardResponse }) {
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="inline-flex items-center gap-2 text-base font-semibold">
          <Bell className="size-4 text-sky-500" aria-hidden />
          Son talepler
        </h2>
        {data.recent_requests.length > 0 ? (
          <Link
            href="/teacher/requests"
            className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
          >
            Tümünü gör <ArrowRight className="size-3" aria-hidden />
          </Link>
        ) : null}
      </div>
      {data.recent_requests.length === 0 ? (
        <p className="mt-3 inline-flex items-center gap-2 text-sm text-muted-foreground">
          <CheckCircle2 className="size-4 text-emerald-500" aria-hidden />
          Bekleyen talep yok.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {data.recent_requests.map((req) => (
            <li key={req.id}>
              <Link
                href={`/teacher/requests/${req.id}`}
                className="group flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-2 py-2.5 text-sm transition hover:bg-muted/60"
              >
                <span className="rounded-md bg-sky-600 px-1.5 py-0.5 text-[11px] font-semibold text-white">
                  {REQUEST_TYPE_LABELS_TR[req.type]}
                </span>
                <span className="font-medium group-hover:underline">{req.student_name}</span>
                <span className="min-w-0 flex-1 break-words text-xs text-muted-foreground">
                  {req.task_title ?? "—"}
                </span>
                <ArrowRight className="size-3.5 text-muted-foreground/50 group-hover:text-foreground" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
