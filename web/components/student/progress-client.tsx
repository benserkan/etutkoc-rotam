"use client";

/**
 * Öğrenci "Gelişim" sayfası (2026-10-21).
 *
 * Koçun öğrenci detayında gördüğü göstergelerin öğrenciye görünen hâli — sayılar koç
 * ekranıyla AYNI servislerden gelir (birebir). Dil "sen"; koça yönelik uyarılar ve
 * "Seansa ekle" önlemleri yok. Akış: sınava hazırlık özeti → bu hafta → haftalar arası
 * gidişat → derslerim → denemelerim → net kaybettiğim konular → ritmim → daha derine in.
 */
import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookX,
  CalendarCheck2,
  Crosshair,
  Flame,
  Gauge,
  GraduationCap,
  LineChart,
  Loader2,
  RotateCcw,
  Target,
  Timer,
  TrendingDown,
  TrendingUp,
  Trophy,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { SubjectTag } from "@/components/shared/subject-tag";
import { Ruler, StatusChip } from "@/components/teacher/student-weekly-progress";
import {
  getStudentAnalytics,
  getStudentWeeklyProgress,
  studentProgressKeys,
} from "@/lib/api/student-progress";
import { getStudentTopicPerformance, topicPerfKeys } from "@/lib/api/topic-performance";
import type { TeacherStudentAnalyticsResponse } from "@/lib/types/teacher";
import type { WeeklyProgressResponse, WPDay } from "@/lib/api/weekly-progress";

const nf = (n: number, d = 1) => n.toLocaleString("tr-TR", { maximumFractionDigits: d });

export function StudentProgressClient() {
  const a = useQuery({ queryKey: studentProgressKeys.analytics(), queryFn: getStudentAnalytics, staleTime: 30_000 });
  const w = useQuery({ queryKey: studentProgressKeys.weekly(), queryFn: getStudentWeeklyProgress, staleTime: 30_000 });
  const tp = useQuery({
    queryKey: topicPerfKeys.student(),
    queryFn: () => getStudentTopicPerformance(),
    staleTime: 60_000,
  });

  if (a.isLoading) {
    return (
      <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Gelişimin hazırlanıyor…
      </div>
    );
  }
  if (a.isError || !a.data) {
    return <p className="py-10 text-sm text-rose-700">Gelişim verileri yüklenemedi.</p>;
  }
  const d = a.data;

  return (
    <div className="space-y-6" data-section="student:progress">
      <Hero d={d} />
      {w.data ? <ThisWeek data={w.data} /> : null}
      <div className="grid gap-6 lg:grid-cols-2">
        {w.data ? <WeeksTrend data={w.data} /> : null}
        <Rhythm d={d} />
      </div>
      <Subjects d={d} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Exams d={d} />
        <WeakTopics focus={tp.data?.focus ?? []} loading={tp.isLoading} />
      </div>
      <DeepLinks />
    </div>
  );
}

/* ============================================================== ortak */

function Section({
  icon: Icon,
  title,
  desc,
  href,
  hrefLabel,
  children,
  id,
}: {
  icon: React.ElementType;
  title: string;
  desc?: string;
  href?: string;
  hrefLabel?: string;
  children: React.ReactNode;
  id?: string;
}) {
  return (
    <section id={id} data-section={id ? `progress:${id}` : undefined} className="min-w-0 rounded-2xl border border-border bg-card p-5">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="inline-flex items-center gap-2 text-base font-bold text-foreground">
            <span className="grid size-8 place-items-center rounded-lg bg-cyan-700 text-white">
              <Icon className="size-4" aria-hidden />
            </span>
            {title}
          </h2>
          {desc ? <p className="mt-1 text-[13px] leading-snug text-muted-foreground">{desc}</p> : null}
        </div>
        {href ? (
          <Link
            href={href}
            className="inline-flex items-center gap-1 text-[13px] font-semibold text-cyan-800 hover:underline"
          >
            {hrefLabel ?? "Ayrıntı"} <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        ) : null}
      </header>
      {children}
    </section>
  );
}

/* ============================================================== 1 hero */

const STATUS_TEXT = {
  green: { chip: "Yetişiyorsun", cls: "bg-emerald-400 text-emerald-950" },
  amber: { chip: "Biraz hızlanmalısın", cls: "bg-amber-300 text-amber-950" },
  red: { chip: "Hızlanman gerekiyor", cls: "bg-rose-300 text-rose-950" },
} as const;

function Hero({ d }: { d: TeacherStudentAnalyticsResponse }) {
  const p = d.projection;
  const s = d.summary;
  const st = STATUS_TEXT[p.status];
  const donePct = p.total_tests > 0 ? Math.min(100, Math.round((100 * p.completed) / p.total_tests)) : 0;
  const sentence =
    p.total_tests === 0
      ? "Kaynakların atanınca tempon ve sınava yetişme durumun burada görünür."
      : p.remaining <= 0
        ? "Kaynaklarındaki bütün testleri bitirdin — harika!"
        : p.gap >= 0
          ? `Bu tempoyla sınava kadar ${nf(p.projected_completable, 0)} test çözersin; kalan ${nf(p.remaining, 0)} testi rahat bitirirsin.`
          : `Bu tempoyla ${nf(Math.abs(p.gap), 0)} test eksik kalır. Günde ${nf(p.required_rate)} test çözersen yetişirsin.`;

  return (
    <section
      className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-cyan-800 via-cyan-900 to-indigo-950 p-6 text-white shadow-lg sm:p-8"
      data-section="progress:hero"
    >
      <div className="pointer-events-none absolute -right-16 -top-20 size-72 rounded-full bg-white/5" aria-hidden />
      <div className="pointer-events-none absolute -bottom-24 right-24 size-56 rounded-full bg-white/5" aria-hidden />
      <div className="relative grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-100">Sınava hazırlık</p>
          {p.days_left != null ? (
            <div className="mt-2 flex flex-wrap items-end gap-x-3 gap-y-1">
              <span className="font-display text-6xl font-extrabold leading-none tabular-nums">{p.days_left}</span>
              <span className="pb-1.5 text-lg font-semibold text-cyan-50">
                gün kaldı{p.exam_label ? ` · ${p.exam_label}` : ""}
              </span>
            </div>
          ) : (
            <p className="mt-2 text-2xl font-bold">Sınav tarihin henüz tanımlı değil</p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {p.total_tests > 0 ? (
              <span className={cn("rounded-full px-3 py-1 text-xs font-bold", st.cls)}>{st.chip}</span>
            ) : null}
            <span className="text-sm text-cyan-50">{sentence}</span>
          </div>
          {p.total_tests > 0 ? (
            <div className="mt-5">
              <div className="flex justify-between text-xs text-cyan-100">
                <span>Kaynaklarındaki testler</span>
                <span className="tabular-nums">
                  {nf(p.completed, 0)} / {nf(p.total_tests, 0)} · %{donePct}
                </span>
              </div>
              <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-white/15">
                <div className="h-full rounded-full bg-gradient-to-r from-emerald-300 to-cyan-200" style={{ width: `${donePct}%` }} />
              </div>
            </div>
          ) : null}
        </div>

        <div className="grid grid-cols-2 gap-3 self-start">
          <HeroTile
            icon={Gauge}
            label="Günlük tempon"
            value={`${nf(s.rate_7d)} test`}
            note={p.required_rate > 0 ? `gereken ${nf(p.required_rate)} · son 7 gün` : "son 7 günün ortalaması"}
            good={p.required_rate <= 0 || s.rate_7d >= p.required_rate}
          />
          <HeroTile
            icon={CalendarCheck2}
            label="Düzenlilik"
            value={`%${s.consistency_7d_pct}`}
            note="programlı günlerin kaçında çalıştın (7 gün)"
            good={s.consistency_7d_pct >= 70}
          />
          <HeroTile
            icon={Flame}
            label="En uzun seri"
            value={`${s.longest_streak_30} gün`}
            note="son 30 günde üst üste çalıştığın gün"
            good={s.longest_streak_30 >= 5}
          />
          <HeroTile
            icon={Activity}
            label="Aktif gün"
            value={`${s.active_days_30} / 30`}
            note="son 30 günde çalıştığın gün"
            good={s.active_days_30 >= 20}
          />
        </div>
      </div>
    </section>
  );
}

function HeroTile({
  icon: Icon,
  label,
  value,
  note,
  good,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  note: string;
  good: boolean;
}) {
  return (
    <div className="min-w-0 rounded-2xl bg-white/10 p-3.5 ring-1 ring-white/15 backdrop-blur-sm">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-cyan-100">
        <Icon className="size-3.5" aria-hidden />
        {label}
      </div>
      <div className="mt-1 flex items-center gap-1.5 text-2xl font-extrabold tabular-nums">
        {value}
        <span className={cn("size-2 rounded-full", good ? "bg-emerald-300" : "bg-amber-300")} aria-hidden />
      </div>
      <p className="mt-0.5 text-[11px] leading-snug text-cyan-100/90">{note}</p>
    </div>
  );
}

/* ============================================================== 2 bu hafta */

const DAY_STATE: Record<WPDay["state"], { cls: string; label: string }> = {
  done: { cls: "bg-emerald-600 text-white", label: "tamam" },
  partial: { cls: "bg-amber-400 text-amber-950", label: "kısmen" },
  missed: { cls: "bg-rose-600 text-white", label: "yapılmadı" },
  today: { cls: "bg-cyan-700 text-white ring-2 ring-cyan-300", label: "bugün" },
  future: { cls: "bg-muted text-muted-foreground", label: "gelecek" },
  none: { cls: "border border-dashed border-border text-muted-foreground", label: "görev yok" },
};

function ThisWeek({ data }: { data: WeeklyProgressResponse }) {
  if (!data.has_program || !data.week) return null;
  const wk = data.week;
  const cards = [data.headline.gorev_pct, data.headline.test_done].filter(Boolean);
  const pr = data.projection;
  const isPeriod = wk.kind === "donem";
  return (
    <Section
      id="week"
      icon={Target}
      title={isPeriod ? "Bu dönem nasıl gidiyor?" : "Bu hafta nasıl gidiyor?"}
      desc={`${wk.label} · ${wk.ended ? "hafta bitti" : `${wk.day_index}. gün / ${wk.days}`} — kendi geçmiş haftalarının aynı gününe göre`}
      href={isPeriod ? "/student/pool" : `/student/week?start=${wk.start}`}
      hrefLabel={isPeriod ? "Havuzum" : "Haftayı aç"}
    >
      <div className="grid gap-4 md:grid-cols-2">
        {cards.map((c) => (
          <div key={c.key} className="rounded-xl border border-border bg-background/40 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-foreground">{c.name}</p>
                <p className="mt-0.5 text-3xl font-extrabold tabular-nums text-foreground">{c.value_label}</p>
              </div>
              <StatusChip card={c} />
            </div>
            <div className="mt-3">
              <Ruler card={c} />
            </div>
            <p className="mt-2 text-[13px] text-muted-foreground">{c.verdict}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-7 gap-1.5" aria-label="Gün gün">
        {data.days.map((dd) => {
          const st = DAY_STATE[dd.state];
          return (
            <div
              key={dd.date}
              className={cn("rounded-lg px-1 py-2 text-center", st.cls)}
              title={
                dd.missing.length > 0
                  ? `Yapılmayan: ${dd.missing.map((m) => m.title).join(", ")}`
                  : `${dd.label} · ${st.label}`
              }
            >
              <div className="text-[11px] font-bold uppercase">{dd.day}</div>
              <div className="text-sm font-extrabold tabular-nums">{dd.total > 0 ? `${dd.done}/${dd.total}` : "—"}</div>
              <div className="text-[10px] opacity-90">{st.label}</div>
            </div>
          );
        })}
      </div>

      {pr?.projected_pct != null && !wk.ended ? (
        <p className="mt-3 rounded-lg bg-cyan-500/10 px-3 py-2 text-[13px] text-foreground">
          Böyle giderse hafta sonunda görevlerinin <b>%{Math.round(pr.projected_pct)}</b>&apos;ini tamamlamış olursun
          {pr.band_low != null && pr.band_high != null
            ? ` — genelde %${Math.round(pr.band_low)}–${Math.round(pr.band_high)} arasındasın.`
            : "."}
        </p>
      ) : null}
    </Section>
  );
}

/* ============================================================== 3 haftalar arası */

function WeeksTrend({ data }: { data: WeeklyProgressResponse }) {
  const pts = data.chart.filter((c) => c.value != null);
  if (pts.length < 2) return null;
  const ps = data.period_summary;
  return (
    <Section
      id="weeks"
      icon={LineChart}
      title="Haftadan haftaya"
      desc="Son haftalarda görevlerinin yüzde kaçını tamamladın. Gölgeli alan senin normalin."
    >
      <div className="relative h-44">
        {ps?.band_low != null && ps.band_high != null ? (
          <div
            className="absolute inset-x-0 rounded border-y border-cyan-600/50 bg-cyan-600/25"
            style={{ bottom: `${ps.band_low}%`, height: `${Math.max(2, ps.band_high - ps.band_low)}%` }}
            aria-hidden
          />
        ) : null}
        <div className="relative flex h-full items-end gap-2">
          {pts.map((c) => (
            <div key={c.label + c.range} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1" title={c.range}>
              <span className={cn("text-[11px] font-bold tabular-nums", c.current ? "text-cyan-800" : "text-muted-foreground")}>
                %{Math.round(c.value ?? 0)}
              </span>
              <div
                className={cn(
                  "w-full max-w-10 rounded-t-md",
                  c.current ? "bg-cyan-600" : "bg-slate-300",
                )}
                style={{ height: `${Math.max(3, c.value ?? 0)}%` }}
              />
              <span className="text-[10px] text-muted-foreground">{c.current ? "bu hafta" : c.label}</span>
            </div>
          ))}
        </div>
      </div>
      {ps && ps.weeks > 0 ? (
        <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
          <Mini label="Ortanca" value={ps.median != null ? `%${Math.round(ps.median)}` : "—"} />
          <Mini label="En iyi" value={ps.best ? `%${Math.round(ps.best.value)}` : "—"} hint={ps.best?.label} />
          <Mini label="En düşük" value={ps.worst ? `%${Math.round(ps.worst.value)}` : "—"} hint={ps.worst?.label} />
        </dl>
      ) : null}
    </Section>
  );
}

function Mini({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg bg-muted/60 px-2 py-2">
      <dt className="text-[11px] font-semibold text-muted-foreground">{label}</dt>
      <dd className="text-lg font-extrabold tabular-nums text-foreground">{value}</dd>
      {hint ? <dd className="text-[10px] text-muted-foreground">{hint}</dd> : null}
    </div>
  );
}

/* ============================================================== 4 ritim */

function Rhythm({ d }: { d: TeacherStudentAnalyticsResponse }) {
  const cal = d.activity_calendar;
  const dow = d.dow_all ?? [];
  const lead = cal.length ? cal[0].weekday : 0; // Pzt = 0
  return (
    <Section
      id="rhythm"
      icon={CalendarCheck2}
      title="Çalışma ritmim"
      desc="Son 5 hafta gün gün: yeşil çalıştığın gün, kırmızı görevin olup çalışmadığın gün."
    >
      <div className="mx-auto max-w-xs"><div className="grid grid-cols-7 gap-1 text-center text-[10px] font-semibold text-muted-foreground">
        {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((x) => (
          <span key={x}>{x}</span>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-7 gap-1">
        {Array.from({ length: lead }).map((_, i) => (
          <span key={`p${i}`} />
        ))}
        {cal.map((c) => (
          <span
            key={c.date}
            title={`${c.date} · ${c.active ? "çalıştın" : c.has_plan ? "görev vardı, çalışılmadı" : "görev yoktu"}`}
            className={cn(
              "h-6 rounded",
              c.active
                ? "bg-emerald-500"
                : c.has_plan
                  ? "bg-rose-500/80"
                  : "bg-muted",
            )}
          />
        ))}
      </div>
      </div>
      {dow.length > 0 ? (
        <div className="mt-4">
          <p className="mb-1.5 text-[12px] font-semibold text-foreground">Hangi gün ne kadar tamamlıyorum?</p>
          <div className="grid grid-cols-7 gap-1.5">
            {dow.map((r) => (
              <div key={r.weekday} className="text-center">
                <div className="flex h-16 items-end justify-center rounded-md bg-muted/50">
                  <div
                    className={cn(
                      "w-full rounded-md",
                      r.hit_pct == null ? "" : r.hit_pct >= 75 ? "bg-emerald-500" : r.hit_pct >= 50 ? "bg-amber-400" : "bg-rose-500",
                    )}
                    style={{ height: `${Math.max(4, r.hit_pct ?? 0)}%` }}
                  />
                </div>
                <div className="mt-0.5 text-[10px] font-semibold text-muted-foreground">{r.label}</div>
                <div className="text-[11px] font-bold tabular-nums text-foreground">
                  {r.hit_pct == null ? "—" : `%${r.hit_pct}`}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </Section>
  );
}

/* ============================================================== 5 derslerim */

function Subjects({ d }: { d: TeacherStudentAnalyticsResponse }) {
  const rows = (d.subject_work ?? []).filter((r) => r.total > 0 || (r.total_topics ?? 0) > 0);
  const c = d.curriculum;
  if (rows.length === 0 && !c) return null;
  return (
    <Section
      id="subjects"
      icon={BarChart3}
      title="Derslerim"
      desc="Son 30 günde her derste çözdüğün test, doğruluğun ve müfredatta nereye geldiğin."
      href="/student/topics"
      hrefLabel="Konu performansı"
    >
      {c ? (
        <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl bg-indigo-500/10 px-4 py-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wide text-indigo-800">
              {c.focus_grade ? `${c.focus_grade}. sınıf müfredatı` : "Müfredat"}
            </p>
            <p className="text-2xl font-extrabold tabular-nums text-foreground">%{Math.round(c.coverage_pct)}</p>
          </div>
          <p className="min-w-0 flex-1 text-[13px] text-foreground">
            {c.total_topics} konunun <b>{c.started_topics}</b> tanesine başladın.
            {c.projected_coverage_pct != null && c.target_label
              ? ` Bu hızla ${c.target_label.toLocaleLowerCase("tr")} konuların ~%${Math.round(c.projected_coverage_pct)}'ini görmüş olursun.`
              : ""}
          </p>
        </div>
      ) : null}
      <div className="grid gap-2.5 md:grid-cols-2">
        {rows.map((r) => (
          <div key={r.subject_id} className="rounded-xl border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <SubjectTag name={r.name} size="sm" />
              <span className="text-[12px] tabular-nums text-muted-foreground">
                {r.total} test · {r.accuracy_pct != null ? (
                  <b className={accCls(r.accuracy_pct)}>%{Math.round(r.accuracy_pct)} doğru</b>
                ) : (
                  "sonuç girilmedi"
                )}
              </span>
            </div>
            {r.coverage_pct != null && r.total_topics > 0 ? (
              <div className="mt-2">
                <div className="flex justify-between text-[11px] text-muted-foreground">
                  <span>Müfredat</span>
                  <span className="tabular-nums">
                    {r.started_topics}/{r.total_topics} konu · %{Math.round(r.coverage_pct)}
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-indigo-600" style={{ width: `${Math.min(100, r.coverage_pct)}%` }} />
                </div>
              </div>
            ) : null}
            {r.next_topic ? (
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Sıradaki konu: <span className="font-semibold text-foreground">{r.next_topic}</span>
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </Section>
  );
}

function accCls(p: number) {
  return p >= 70
    ? "text-emerald-700"
    : p >= 50
      ? "text-amber-700"
      : "text-rose-700";
}

/* ============================================================== 6 denemelerim */

function Exams({ d }: { d: TeacherStudentAnalyticsResponse }) {
  const ex = d.exam_trend;
  return (
    <Section
      id="exams"
      icon={Trophy}
      title="Denemelerim"
      desc="Son 60 gündeki denemelerin. Netler yalnız aynı türdeki denemelerle kıyaslanır."
      href="/student/exams"
      hrefLabel="Tüm denemeler"
    >
      {ex.length === 0 ? (
        <p className="text-sm text-muted-foreground">Son 60 günde deneme sonucu yok.</p>
      ) : (
        <>
          {d.exam_trend_delta != null ? (
            <div
              className={cn(
                "mb-3 flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold text-white",
                d.exam_trend_delta >= 0 ? "bg-emerald-600" : "bg-rose-600",
              )}
            >
              {d.exam_trend_delta >= 0 ? <TrendingUp className="size-4" aria-hidden /> : <TrendingDown className="size-4" aria-hidden />}
              Son {d.exam_trend_section} denemende bir öncekine göre {d.exam_trend_delta >= 0 ? "+" : ""}
              {nf(d.exam_trend_delta, 2)} net
            </div>
          ) : null}
          <ul className="divide-y divide-border">
            {ex.map((e, i) => (
              <li key={`${e.title}-${i}`} className="flex items-center justify-between gap-3 py-2">
                <div className="min-w-0">
                  <p className="break-words text-sm font-medium text-foreground">{e.title}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {e.section_label}
                    {e.exam_date ? ` · ${e.exam_date.split("-").reverse().join(".")}` : ""}
                  </p>
                </div>
                <span className="shrink-0 text-lg font-extrabold tabular-nums text-foreground">{nf(e.net, 2)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
}

/* ============================================================== 7 zayıf konular */

const LEVEL = {
  zayif: { label: "Zayıf", cls: "bg-rose-600 text-white" },
  dikkat: { label: "Dikkat", cls: "bg-amber-400 text-amber-950" },
} as const;

function WeakTopics({
  focus,
  loading,
}: {
  focus: { topic_name: string; subject_name?: string | null; accuracy_pct: number | null; level?: string; exam_only?: boolean; wrong: number; blank?: number }[];
  loading: boolean;
}) {
  const rows = focus.slice(0, 6);
  return (
    <Section
      id="weak"
      icon={Crosshair}
      title="Net kaybettiğim konular"
      desc="Testlerde ve denemelerde en çok yanlış/boş bıraktığın konular — çalışma önceliğin."
      href="/student/topics"
      hrefLabel="Konu performansı"
    >
      {loading ? (
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Henüz belirgin bir zayıf konu yok. Testlerinde doğru/yanlış girdikçe burası dolar.
        </p>
      ) : (
        <ol className="space-y-2">
          {rows.map((r, i) => {
            const lv = r.level === "zayif" || r.level === "dikkat" ? LEVEL[r.level] : null;
            return (
              <li key={`${r.topic_name}-${i}`} className="flex items-start gap-3 rounded-xl border border-border p-2.5">
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-slate-800 text-xs font-bold text-white">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="break-words text-sm font-semibold text-foreground">{r.topic_name}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {r.subject_name ?? ""}
                    {r.exam_only ? " · denemede" : ""}
                    {r.accuracy_pct != null ? ` · %${Math.round(r.accuracy_pct)} doğru` : ""}
                    {r.wrong > 0 ? ` · ${r.wrong} yanlış` : ""}
                  </p>
                </div>
                {lv ? <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold", lv.cls)}>{lv.label}</span> : null}
              </li>
            );
          })}
        </ol>
      )}
    </Section>
  );
}

/* ============================================================== 8 daha derine */

const DEEP = [
  { href: "/student/topics", label: "Konu performansı", desc: "Ders ders, konu konu doğruluğun", icon: Crosshair },
  { href: "/student/exams", label: "Denemelerim", desc: "Net gelişimi ve konu analizi", icon: GraduationCap },
  { href: "/student/wrong-questions", label: "Yanlışlarım", desc: "Yanlış soru arşivi ve tekrar", icon: BookX },
  { href: "/student/dna", label: "Çalışma DNA", desc: "En verimli saatlerin ve günlerin", icon: BarChart3 },
  { href: "/student/review", label: "Tekrar", desc: "Unutmadan tekrar edeceğin konular", icon: RotateCcw },
  { href: "/student/goals", label: "Hedeflerim", desc: "Hedef koy, ilerlemeni izle", icon: Target },
  { href: "/student/focus", label: "Odak", desc: "Süre tutarak çalış", icon: Timer },
] as const;

function DeepLinks() {
  return (
    <section data-section="progress:deep">
      <h2 className="mb-3 text-base font-bold text-foreground">Daha derine in</h2>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4">
        {DEEP.map((x) => (
          <Link
            key={x.href}
            href={x.href}
            className="group flex items-start gap-3 rounded-xl border border-border bg-card p-3 transition-colors hover:border-cyan-600 hover:bg-cyan-500/5"
          >
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-cyan-500/15 text-cyan-800">
              <x.icon className="size-4" aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-foreground group-hover:underline">{x.label}</span>
              <span className="block text-[11px] leading-snug text-muted-foreground">{x.desc}</span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
