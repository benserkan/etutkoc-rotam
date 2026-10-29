"use client";

/**
 * "Analitik" sekmesi — koçun program süreci panosu.
 *
 * 2026-10-15 yeniden tasarım + veri denetimi (koç: "grafikler kolay yorumlanmalı; havuzda kaynaklı ve
 * kaynaksız çalışma analize giriyor mu?"):
 *   · Tüm test sayıları artık KİTAPLI + KAYNAKSIZ (konulu) kalemleri sayar; havuz seans işaretleri ayrıca
 *     gösterilir. Deneme hiçbir test sayısına girmez (DENEME≠TEST).
 *   · Her kart: ne gösterdiği (birim + dönem) + nasıl okunacağı tek cümle.
 *   · En üstte "Kısa okuma": verilerden çıkarılan 3-5 cümle (yorum koçun işi; sistem işaret eder).
 *   · Sınava yetişme iki ayrı soruya bölündü: MÜFREDAT (konu) ve KİTAP bitirme (kaynak envanteri).
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  CalendarDays,
  ChevronDown,
  Flame,
  GraduationCap,
  Layers,
  Lightbulb,
  Loader2,
  Map as MapIcon,
  Minus,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { ExamReadinessCard } from "@/components/teacher/exam-readiness-card";
import { subjectColors } from "@/components/shared/subject-tag";
import { getTeacherStudentAnalytics, teacherKeys } from "@/lib/api/teacher";
import type {
  AnalyticsCurriculum,
  AnalyticsDayFlag,
  AnalyticsDowAll,
  AnalyticsExamPoint,
  AnalyticsMix,
  AnalyticsSubjectRow,
  AnalyticsSubjectWork,
  AnalyticsSummary,
  AnalyticsTrendPoint,
  AnalyticsWarningItem,
  AnalyticsWeekPoint,
  TeacherStudentAnalyticsResponse,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

const DOW_LABELS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
// Kaynak renkleri — dolgulu, iki temada da okunur
const SRC = {
  book: { bar: "bg-cyan-600", dot: "bg-cyan-600", label: "Kitaplı" },
  sourceless: { bar: "bg-violet-600", dot: "bg-violet-600", label: "Kaynaksız (konulu)" },
  session: { bar: "bg-amber-500", dot: "bg-amber-500", label: "Seansta işaretlenen" },
} as const;

function fmt(n: number, d = 1): string {
  return n.toLocaleString("tr-TR", { maximumFractionDigits: d });
}

function accText(pct: number | null | undefined): string {
  if (pct == null) return "text-muted-foreground";
  if (pct >= 70) return "text-emerald-700";
  if (pct >= 50) return "text-amber-700";
  return "text-rose-700";
}

export function StudentAnalyticsPanel({ studentId }: { studentId: number }) {
  const q = useQuery<TeacherStudentAnalyticsResponse>({
    queryKey: teacherKeys.studentAnalytics(studentId),
    queryFn: () => getTeacherStudentAnalytics(studentId),
    staleTime: 30_000,
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
      </div>
    );
  }
  if (q.error || !q.data) {
    return <div className="text-sm text-rose-700">Analitik verileri yüklenemedi.</div>;
  }

  const d = q.data;
  const activeWarnings = d.warnings.filter((w) => w.level !== "green");
  const firstActive = firstActivityIndex(d.trend);
  // Sınav kartı yalnız sınava girecek öğrencide: mezun (odak yok), 12. ve 8. sınıf.
  // 9-11 sınava girmez → yalnız eğitim yılı sonu müfredat projeksiyonu (koç, 2026-10-15).
  const fg = d.curriculum?.focus_grade ?? null;
  const showExamReadiness = d.curriculum == null || fg == null || fg === 12 || fg === 8;

  return (
    <div className="space-y-4" data-section="analytics">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,420px)]">
        {d.mix ? <MixHero mix={d.mix} summary={d.summary} /> : null}
        <Insights d={d} />
      </div>

      <PaceStrip s={d.summary} />

      <div className="grid gap-4 lg:grid-cols-2">
        <DailyTrendCard trend={d.trend.slice(firstActive)} windowDays={d.window_days} />
        <WeeklyTrendCard weeks={d.weekly_trend} />
      </div>

      {(d.subject_work ?? []).length > 0 ? <SubjectWorkCard rows={d.subject_work ?? []} /> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <DowCard rows={d.dow_all ?? []} />
        <ActivityCalendarCard days={d.activity_calendar} />
      </div>

      <section className="space-y-2" data-section="analytics:readiness">
        <h3 className="px-1 text-sm font-semibold text-foreground">
          {showExamReadiness ? "Yetişme — iki ayrı soru" : "Bu yılın müfredatına yetişme"}
        </h3>
        <div className={cn("grid gap-4", showExamReadiness && "lg:grid-cols-2")}>
          {d.curriculum ? <CurriculumCard c={d.curriculum} /> : null}
          {showExamReadiness ? (
            <div className="min-w-0">
              <ExamReadinessCard studentId={studentId} />
            </div>
          ) : null}
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <ExamTrendCard exams={d.exam_trend} delta={d.exam_trend_delta} section={d.exam_trend_section} />
        {activeWarnings.length > 0 ? <WarningsCard warnings={activeWarnings} /> : <BookInventory subjects={d.subjects} />}
      </div>
      {activeWarnings.length > 0 ? <BookInventory subjects={d.subjects} /> : null}
    </div>
  );
}

function firstActivityIndex(trend: AnalyticsTrendPoint[]): number {
  const i = trend.findIndex((p) => p.planned > 0 || p.completed > 0);
  if (i <= 0) return 0;
  // ilk hareketten 2 gün önce başla (bağlam) ama en az 14 gün göster — az günde sütunlar dev olmasın
  return Math.max(0, Math.min(i - 2, trend.length - 14));
}

/** Öğrencinin ilk görevinden bugüne kaç gün geçti (trend penceresinde). */
function daysSinceStart(trend: AnalyticsTrendPoint[]): number {
  const i = trend.findIndex((p) => p.planned > 0 || p.completed > 0);
  return i < 0 ? 0 : trend.length - i;
}

/* ============================================================== ortak kart */

function Panel({
  icon: Icon,
  title,
  desc,
  children,
  section,
  right,
}: {
  icon: React.ElementType;
  title: string;
  desc: string;
  children: React.ReactNode;
  section?: string;
  right?: React.ReactNode;
}) {
  return (
    <section className="min-w-0 rounded-2xl border border-border bg-card p-4" data-section={section}>
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
            <Icon className="size-4 text-cyan-700" aria-hidden /> {title}
          </h3>
          <p className="mt-0.5 text-[12px] leading-snug text-muted-foreground">{desc}</p>
        </div>
        {right}
      </header>
      {children}
    </section>
  );
}

/* ============================================================== kaynak dağılımı */

function MixHero({ mix, summary }: { mix: AnalyticsMix; summary: AnalyticsSummary }) {
  const total = mix.total_tests;
  const parts = [
    { key: "book" as const, n: mix.book_completed },
    { key: "sourceless" as const, n: mix.sourceless_completed },
    { key: "session" as const, n: mix.session_tests },
  ];
  const planned = mix.book_planned + mix.sourceless_planned;
  const doneOfPlanned = mix.book_completed + mix.sourceless_completed;
  return (
    <section
      className="rounded-2xl border border-cyan-700/30 bg-gradient-to-br from-cyan-700 to-cyan-900 p-4 text-white"
      data-section="analytics:mix"
    >
      <p className="text-[12px] font-medium text-cyan-100">Son {mix.window_days} gün · çözülen test (deneme hariç)</p>
      <div className="mt-1 flex flex-wrap items-end gap-x-6 gap-y-2">
        <p className="text-4xl font-extrabold tabular-nums">
          {total}
          <span className="ml-1.5 text-base font-semibold text-cyan-100">test</span>
        </p>
        <p className="pb-1 text-[13px] text-cyan-50">
          planlanan {planned} testten <strong className="tabular-nums">{doneOfPlanned}</strong> tanesi çözüldü
          {mix.session_tests > 0 ? ` · +${mix.session_tests} seansta işaretlendi` : ""}
        </p>
      </div>
      <div className="mt-3 flex h-3 w-full overflow-hidden rounded-full bg-white/20" aria-hidden>
        {parts.map((p) =>
          p.n > 0 ? <span key={p.key} className={SRC[p.key].bar} style={{ width: `${(100 * p.n) / Math.max(1, total)}%` }} /> : null,
        )}
      </div>
      <ul className="mt-2.5 grid gap-x-4 gap-y-1.5 text-[12.5px] sm:grid-cols-3">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-1.5">
            <span className={cn("size-2.5 shrink-0 rounded-sm ring-1 ring-white/60", SRC[p.key].dot)} aria-hidden />
            <span className="text-cyan-50">{SRC[p.key].label}</span>
            <strong className="ml-auto tabular-nums sm:ml-1">{p.n}</strong>
          </li>
        ))}
      </ul>
      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-white/20 pt-3 text-[12.5px]">
        <div>
          <p className="text-cyan-100">Doğruluk</p>
          <p className="text-lg font-bold tabular-nums">{mix.accuracy_pct == null ? "—" : `%${mix.accuracy_pct}`}</p>
          <p className="text-[11.5px] text-cyan-100">
            {mix.correct + mix.wrong > 0 ? `${mix.correct} D · ${mix.wrong} Y · ${mix.blank} B soru` : "sonuç girilmemiş"}
          </p>
        </div>
        <div>
          <p className="text-cyan-100">Sonucu girilen</p>
          <p className="text-lg font-bold tabular-nums">
            {mix.tests_with_result}/{mix.book_completed + mix.sourceless_completed}
          </p>
          <p className="text-[11.5px] text-cyan-100">test · doğruluk yalnız bunlardan</p>
        </div>
      </div>
      <p className="sr-only">Uyarı düzeyi {summary.worst_warning_level}</p>
    </section>
  );
}

/* ============================================================== kısa okuma */

function buildInsights(d: TeacherStudentAnalyticsResponse): { tone: "good" | "warn" | "info"; text: string }[] {
  const out: { tone: "good" | "warn" | "info"; text: string }[] = [];
  const s = d.summary;
  const mix = d.mix;
  const started = daysSinceStart(d.trend);
  if (started > 0 && started < 14) {
    out.push({ tone: "info", text: `Programa ${started} gün önce başladı — tempo kıyası için en az 2 hafta veri gerekir; şimdilik günde ${fmt(s.rate_7d)} test.` });
  } else if (s.rate_30d > 0 || s.rate_7d > 0) {
    if (s.rate_30d > 0 && s.rate_7d >= s.rate_30d * 1.3)
      out.push({ tone: "good", text: `Tempo yükseliyor: son 7 günde günde ${fmt(s.rate_7d)} test (30 günlük ortalama ${fmt(s.rate_30d)}).` });
    else if (s.rate_30d > 0 && s.rate_7d <= s.rate_30d * 0.7)
      out.push({ tone: "warn", text: `Tempo düşüyor: son 7 günde günde ${fmt(s.rate_7d)} test (30 günlük ortalama ${fmt(s.rate_30d)}).` });
    else out.push({ tone: "info", text: `Günde ortalama ${fmt(s.rate_7d)} test çözüyor (son 7 gün).` });
  }
  if (s.hit_rate_7d_pct > 0 && s.hit_rate_7d_pct < 60)
    out.push({ tone: "warn", text: `Son 7 günde planlanan testlerin yapılma oranı %${s.hit_rate_7d_pct} — program yükü ya da zamanlama konuşulmalı.` });
  else if (s.hit_rate_7d_pct >= 85)
    out.push({ tone: "good", text: `Son 7 günde planlanan testlerin yapılma oranı %${s.hit_rate_7d_pct}.` });
  if (mix) {
    const enterable = mix.book_completed + mix.sourceless_completed;
    if (enterable >= 5 && (mix.result_coverage_pct ?? 0) < 50)
      out.push({ tone: "warn", text: `Çözülen ${enterable} testin ${enterable - mix.tests_with_result} tanesinde doğru/yanlış girilmemiş — doğruluk ve zayıf konu ölçülemiyor.` });
    else if (mix.accuracy_pct != null && mix.accuracy_pct < 60)
      out.push({ tone: "warn", text: `Doğruluk %${mix.accuracy_pct} — Konu Performansı sekmesinde hangi konuda kaybettiğine bak.` });
    if (mix.total_tests > 0 && mix.sourceless_completed > 0) {
      const share = Math.round((100 * mix.sourceless_completed) / mix.total_tests);
      out.push({ tone: "info", text: `Kaynaksız (konuya bağlı) çalışmanın payı %${share} — bu testler kitap sayacına değil müfredat haritasına yazılır.` });
    }
  }
  const idle = (d.subject_work ?? []).filter((w) => w.planned > 0 && w.total === 0).map((w) => w.name);
  if (idle.length > 0)
    out.push({ tone: "warn", text: `${idle.join(", ")} için görev verildi ama son 30 günde hiç test çözülmedi.` });
  const dows = (d.dow_all ?? []).filter((r) => r.programmed_days > 0 && r.hit_pct != null);
  if (dows.length >= 3) {
    const worst = [...dows].sort((a, b) => (a.hit_pct ?? 0) - (b.hit_pct ?? 0))[0];
    if ((worst.hit_pct ?? 100) < 50)
      out.push({ tone: "warn", text: `${worst.label} günleri zayıf: planlananın yapılma oranı ortalama %${worst.hit_pct}.` });
  }
  const c = d.curriculum;
  if (c && c.verdict === "yetismez")
    out.push({ tone: "warn", text: `Müfredat temposu ${c.target_kind === "okul_yili_sonu" ? "eğitim yılı sonuna" : "sınava"} yetmiyor: haftada ${fmt(c.pace_per_week ?? 0)} konu, bu hızla %${c.projected_coverage_pct ?? 0} kapsama.` });
  else if (c && c.verdict === "yetisir")
    out.push({ tone: "good", text: `Müfredat temposu ${c.target_kind === "okul_yili_sonu" ? "eğitim yılı sonuna" : "sınava"} yetişiyor (tahmini %${c.projected_coverage_pct ?? 0} kapsama).` });
  return out.slice(0, 6);
}

function Insights({ d }: { d: TeacherStudentAnalyticsResponse }) {
  const items = buildInsights(d);
  const tone = {
    good: "bg-emerald-700",
    warn: "bg-amber-500",
    info: "bg-slate-500",
  } as const;
  return (
    <Panel icon={Lightbulb} title="Kısa okuma" desc="Verilerden çıkan işaretler — yorum ve karar koçta." section="analytics:insights">
      {items.length === 0 ? (
        <p className="text-[13px] text-muted-foreground">Yorum için henüz yeterli veri yok.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2 text-[13px] leading-snug text-foreground">
              <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", tone[it.tone])} aria-hidden />
              <span>{it.text}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/* ============================================================== tempo şeridi */

function PaceStrip({ s }: { s: AnalyticsSummary }) {
  const tiles = [
    { label: "Hız · 7 gün", value: fmt(s.rate_7d), unit: "test/gün", note: "son 7 günde günlük ortalama çözülen test" },
    { label: "Hız · 30 gün", value: fmt(s.rate_30d), unit: "test/gün", note: "son 30 günün günlük ortalaması" },
    { label: "Tutturma · 7 gün", value: `%${s.hit_rate_7d_pct}`, note: "planlanan testin ne kadarı çözüldü",
      tone: s.hit_rate_7d_pct >= 80 ? "text-emerald-700" : s.hit_rate_7d_pct >= 50 ? "text-amber-700" : "text-rose-700" },
    { label: "İstikrar · 7 gün", value: `%${s.consistency_7d_pct}`, note: "programlı günlerin kaçında en az bir işaret var" },
    { label: "Aktif gün · 30 gün", value: `${s.active_days_30}`, unit: "gün", note: `en uzun kesintisiz seri ${s.longest_streak_30} gün` },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" data-section="analytics:pace">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-xl border border-border bg-card px-3 py-2.5">
          <p className="text-[12px] font-medium text-muted-foreground">{t.label}</p>
          <p className={cn("mt-0.5 text-xl font-bold tabular-nums text-foreground", t.tone)}>
            {t.value}
            {t.unit ? <span className="ml-1 text-[12px] font-medium text-muted-foreground">{t.unit}</span> : null}
          </p>
          <p className="text-[11.5px] leading-snug text-muted-foreground">{t.note}</p>
        </div>
      ))}
    </div>
  );
}

/* ============================================================== günlük trend */

function DailyTrendCard({ trend, windowDays }: { trend: AnalyticsTrendPoint[]; windowDays: number }) {
  const max = Math.max(1, ...trend.map((p) => Math.max(p.planned, p.completed)));
  const hasAny = trend.some((p) => p.planned > 0 || p.completed > 0);
  return (
    <Panel
      icon={BarChart3}
      title="Gün gün: planlanan ve çözülen"
      desc={`Son ${windowDays} gün (ilk hareketten itibaren). Açık sütun planlanan, koyu sütun çözülen test — kitaplı + kaynaksız. Arada boşluk = plan yetişmedi.`}
      section="analytics:daily"
    >
      {!hasAny ? (
        <p className="py-8 text-center text-sm text-muted-foreground">Bu dönemde test görevi yok.</p>
      ) : (
        <>
          <div className="flex h-40 items-end gap-[3px]" role="img" aria-label="Günlük planlanan ve çözülen test">
            {trend.map((p) => {
              const ph = (100 * p.planned) / max;
              const ch = (100 * p.completed) / max;
              const full = p.planned > 0 && p.completed >= p.planned;
              return (
                <div key={p.date} className="group relative flex h-full flex-1 items-end" title={`${p.label}: ${p.completed} / ${p.planned} test`}>
                  <div className="absolute bottom-0 w-full rounded-t bg-slate-300" style={{ height: `${ph}%` }} />
                  <div
                    className={cn("relative w-full rounded-t", full ? "bg-emerald-600" : "bg-cyan-600")}
                    style={{ height: `${Math.max(p.completed > 0 ? 3 : 0, ch)}%` }}
                  />
                </div>
              );
            })}
          </div>
          <div className="mt-1 flex justify-between text-[11px] text-muted-foreground">
            <span>{trend[0]?.label}</span>
            <span>{trend[trend.length - 1]?.label}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-3 text-[11.5px] text-muted-foreground">
            <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-slate-300" /> planlanan</span>
            <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-cyan-600" /> çözülen (eksik)</span>
            <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-emerald-600" /> planın tamamı</span>
          </div>
        </>
      )}
    </Panel>
  );
}

/* ============================================================== haftalık trend */

function WeeklyTrendCard({ weeks }: { weeks: AnalyticsWeekPoint[] }) {
  const shown = weeks.filter((w) => w.planned > 0);
  const last = shown[shown.length - 1];
  const prev = shown[shown.length - 2];
  const delta = last && prev ? last.pct - prev.pct : null;
  return (
    <Panel
      icon={TrendingUp}
      title="Hafta hafta tamamlama"
      desc="Her haftanın planlanan testlerinin yüzde kaçı çözüldü (Pazartesi başlangıçlı). 70+ yeşil, 50–69 sarı, altı kırmızı."
      section="analytics:weekly"
      right={
        delta != null ? (
          <span className={cn("inline-flex items-center gap-1 text-[12px] font-semibold", delta > 0 ? "text-emerald-700" : delta < 0 ? "text-rose-700" : "text-muted-foreground")}>
            {delta > 0 ? <TrendingUp className="size-3.5" /> : delta < 0 ? <TrendingDown className="size-3.5" /> : <Minus className="size-3.5" />}
            {delta > 0 ? "+" : ""}{delta} puan · geçen hafta
          </span>
        ) : null
      }
    >
      {shown.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">Henüz haftalık veri yok.</p>
      ) : (
        <ul className="space-y-2">
          {shown.map((w) => (
            <li key={w.week_start} className="grid grid-cols-[4.5rem_minmax(0,1fr)_6.5rem] items-center gap-2 text-[12.5px]">
              <span className="text-muted-foreground">{w.label}</span>
              <span className="h-3 overflow-hidden rounded-full bg-muted">
                <span
                  className={cn("block h-full rounded-full", w.pct >= 70 ? "bg-emerald-600" : w.pct >= 50 ? "bg-amber-500" : "bg-rose-600")}
                  style={{ width: `${Math.min(100, w.pct)}%` }}
                />
              </span>
              <span className="text-right tabular-nums text-foreground">
                <strong>%{w.pct}</strong> <span className="text-muted-foreground">{w.completed}/{w.planned}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/* ============================================================== ders bazında */

function SubjectWorkCard({ rows }: { rows: AnalyticsSubjectWork[] }) {
  const max = Math.max(1, ...rows.map((r) => r.total));
  return (
    <Panel
      icon={Layers}
      title="Derslere göre çalışma ve müfredat"
      desc="Son 30 günde çözülen test (kaynağa göre renkli), doğruluk ve müfredat haritasında konuların ne kadarına girildiği. Görevi olup hiç çözülmeyen ders kırmızı yazılır."
      section="analytics:subjects"
    >
      <div className="mb-3 flex flex-wrap gap-3 text-[11.5px] text-muted-foreground">
        {(["book", "sourceless", "session"] as const).map((k) => (
          <span key={k} className="inline-flex items-center gap-1">
            <span className={cn("size-2.5 rounded-sm", SRC[k].dot)} /> {SRC[k].label}
          </span>
        ))}
      </div>
      <ul className="divide-y divide-border">
        {rows.map((r) => {
          const c = subjectColors(r.name);
          const idle = r.planned > 0 && r.total === 0;
          return (
            <li
              key={r.subject_id}
              className="grid gap-x-4 gap-y-1.5 py-2.5 md:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_minmax(0,14rem)]"
              data-testid="analytics-subject"
            >
              <div className="flex min-w-0 items-start gap-2">
                <span className="mt-1 h-4 w-1 shrink-0 rounded-full" style={{ backgroundColor: c.rail }} aria-hidden />
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-foreground">{r.name}</p>
                  <p className={cn("text-[11.5px]", idle ? "font-semibold text-rose-700" : "text-muted-foreground")}>
                    {idle ? `${r.planned} test verildi, çözülmedi` : `${r.total} test · plan ${r.planned}`}
                  </p>
                </div>
              </div>
              <div className="min-w-0 space-y-1">
                <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
                  {r.book_tests > 0 ? <span className={SRC.book.bar} style={{ width: `${(100 * r.book_tests) / max}%` }} /> : null}
                  {r.sourceless_tests > 0 ? <span className={SRC.sourceless.bar} style={{ width: `${(100 * r.sourceless_tests) / max}%` }} /> : null}
                  {r.session_tests > 0 ? <span className={SRC.session.bar} style={{ width: `${(100 * r.session_tests) / max}%` }} /> : null}
                </div>
                <p className="text-[11.5px] tabular-nums text-muted-foreground">
                  {[r.book_tests ? `kitaplı ${r.book_tests}` : null, r.sourceless_tests ? `kaynaksız ${r.sourceless_tests}` : null, r.session_tests ? `seansta ${r.session_tests}` : null]
                    .filter(Boolean)
                    .join(" · ") || "çözülen yok"}
                  {" · "}
                  doğruluk{" "}
                  <strong className={cn("font-semibold", accText(r.accuracy_pct))}>{r.accuracy_pct == null ? "—" : `%${r.accuracy_pct}`}</strong>
                </p>
              </div>
              <div className="min-w-0 space-y-1">
                {r.total_topics > 0 ? (
                  <>
                    <div className="flex items-center justify-between text-[11.5px] text-muted-foreground">
                      <span>müfredat</span>
                      <span className="tabular-nums text-foreground">
                        {r.started_topics}/{r.total_topics} konu · <strong>%{r.coverage_pct ?? 0}</strong>
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
                      <span className="block h-full rounded-full" style={{ width: `${r.coverage_pct ?? 0}%`, backgroundColor: c.rail }} />
                    </div>
                    {r.next_topic ? <p className="text-[11.5px] text-muted-foreground">sıradaki: {r.next_topic}</p> : null}
                  </>
                ) : (
                  <p className="text-[11.5px] text-muted-foreground">müfredat konusu yok</p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

/* ============================================================== haftanın günleri */

function DowCard({ rows }: { rows: AnalyticsDowAll[] }) {
  const max = Math.max(1, ...rows.map((r) => r.avg_completed));
  const any = rows.some((r) => r.programmed_days > 0);
  return (
    <Panel
      icon={CalendarDays}
      title="Haftanın günleri"
      desc="Her gün ortalama kaç test çözüyor (sütun) ve o gün planlananın yüzde kaçını yapıyor (alt yazı). Son 8 hafta, öğrencinin ilk görevinden itibaren."
      section="analytics:dow"
    >
      {!any ? (
        <p className="py-8 text-center text-sm text-muted-foreground">Programlı gün henüz yok.</p>
      ) : (
        <div className="grid grid-cols-7 gap-2">
          {rows.map((r) => (
            <div key={r.weekday} className="flex flex-col items-center gap-1">
              <span className="text-[11.5px] font-semibold tabular-nums text-foreground">{fmt(r.avg_completed)}</span>
              <div className="flex h-28 w-full items-end overflow-hidden rounded-md bg-muted">
                <div
                  className={cn(
                    "w-full rounded-t-md",
                    r.hit_pct == null ? "bg-slate-400" : r.hit_pct >= 70 ? "bg-emerald-600" : r.hit_pct >= 50 ? "bg-amber-500" : "bg-rose-600",
                  )}
                  style={{ height: `${(100 * r.avg_completed) / max}%` }}
                  title={`${r.label}: ortalama ${fmt(r.avg_completed)} test · ${r.programmed_days} programlı gün`}
                />
              </div>
              <span className="text-[12px] font-medium text-foreground">{r.label}</span>
              <span className="text-[11px] tabular-nums text-muted-foreground">{r.hit_pct == null ? "plan yok" : `%${r.hit_pct}`}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

/* ============================================================== aktivite takvimi */

function ActivityCalendarCard({ days }: { days: AnalyticsDayFlag[] }) {
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
  const todayIso = days.length ? days[days.length - 1].date : "";
  const isOpenToday = (d: AnalyticsDayFlag) => d.date === todayIso && !d.active;
  const tone = (d: AnalyticsDayFlag) =>
    d.active ? "bg-emerald-600" : isOpenToday(d) && d.has_plan ? "bg-muted ring-2 ring-inset ring-cyan-600" : d.has_plan ? "bg-rose-500" : "bg-muted";
  const active = days.filter((d) => d.active).length;
  const missed = days.filter((d) => !d.active && d.has_plan && !isOpenToday(d)).length;
  return (
    <Panel
      icon={Activity}
      title="Aktivite takvimi · 35 gün"
      desc="Her kare bir gün: yeşil = en az bir görev işaretledi, kırmızı = programı vardı ama hiç işaretlemedi, gri = programsız, mavi çerçeve = bugün (gün sürüyor)."
      section="analytics:calendar"
      right={<span className="text-[12px] text-muted-foreground"><strong className="text-foreground">{active}</strong> aktif · <strong className="text-foreground">{missed}</strong> boş geçen</span>}
    >
      <div className="flex gap-2">
        <div className="flex flex-col justify-between gap-1 py-0.5">
          {DOW_LABELS.map((l) => (
            <span key={l} className="flex h-4 items-center text-[10.5px] leading-none text-muted-foreground">{l}</span>
          ))}
        </div>
        <div className="flex flex-1 gap-1">
          {weeks.map((wk, wi) => (
            <div key={wi} className="flex flex-1 flex-col gap-1">
              {Array.from({ length: 7 }).map((_, dow) => {
                const cell = wk.find((c) => c.weekday === dow);
                if (!cell) return <div key={dow} className="h-4 rounded-sm" />;
                return (
                  <div
                    key={dow}
                    className={cn("h-4 rounded-sm", tone(cell))}
                    title={`${cell.date}: ${cell.active ? "aktif" : isOpenToday(cell) ? "bugün — gün sürüyor" : cell.has_plan ? "programı vardı, işaret yok" : "programsız"}`}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

/* ============================================================== müfredat yetişme */

const VERDICT: Record<string, { label: string; badge: string }> = {
  yetisir: { label: "Yetişir", badge: "bg-emerald-700 text-white" },
  risk: { label: "Riskli", badge: "bg-amber-500 text-amber-950" },
  yetismez: { label: "Yetişmez", badge: "bg-rose-700 text-white" },
  sinav_yok: { label: "Sınav tarihi yok", badge: "bg-slate-600 text-white" },
  veri_yok: { label: "Veri yok", badge: "bg-slate-600 text-white" },
};

function CurriculumCard({ c }: { c: AnalyticsCurriculum }) {
  const v = VERDICT[c.verdict ?? "veri_yok"];
  const school = c.target_kind === "okul_yili_sonu";
  return (
    <Panel
      icon={MapIcon}
      title={school ? `${c.focus_grade}. sınıf müfredatı eğitim yılı sonuna biter mi?` : "Müfredat sınava kadar biter mi?"}
      desc={school
        ? "Yalnız bu yılın konuları sayılır (önceki sınıflardan verilen konular hesaba girmez; TYT/AYT dersinde dersin tüm konuları). Hız = son 2 haftada işlenen farklı konu / hafta; hedef 15 Haziran."
        : "Mezun: 9–12 tüm konular. Hız = son 2 haftada işlenen farklı konu / hafta; hedef sınav günü."}
      section="analytics:curriculum"
      right={<span className={cn("rounded-full px-2 py-0.5 text-[11.5px] font-semibold", v.badge)}>{v.label}</span>}
    >
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-muted/60 px-1 py-2">
          <p className="text-lg font-bold tabular-nums text-foreground">%{c.coverage_pct}</p>
          <p className="text-[11px] text-muted-foreground">
            {c.focus_grade ? `${c.focus_grade}. sınıf kapsaması` : "kapsama"} ({c.started_topics}/{c.total_topics} konu)
          </p>
        </div>
        <div className="rounded-lg bg-muted/60 px-1 py-2">
          <p className="text-lg font-bold tabular-nums text-foreground">{fmt(c.pace_per_week ?? 0)}</p>
          <p className="text-[11px] text-muted-foreground">konu / hafta (son 2 hafta)</p>
        </div>
        <div className="rounded-lg bg-muted/60 px-1 py-2">
          <p className="text-lg font-bold tabular-nums text-foreground">{c.days_to_exam ?? "—"}</p>
          <p className="text-[11px] text-muted-foreground">{school ? "gün (15 Haziran)" : "sınava gün"}</p>
        </div>
      </div>
      {c.projected_coverage_pct != null && c.verdict !== "sinav_yok" ? (
        <div className="mt-3">
          <div className="flex justify-between text-[12px] text-muted-foreground">
            <span>{school ? "Bu hızla 15 Haziran’a kadar kapsama" : "Bu hızla sınav gününe kadar kapsama"}</span>
            <strong className="tabular-nums text-foreground">%{c.projected_coverage_pct}</strong>
          </div>
          <div className="relative mt-1 h-2.5 overflow-hidden rounded-full bg-muted">
            <span className="absolute inset-y-0 left-0 bg-cyan-600" style={{ width: `${Math.min(100, c.coverage_pct)}%` }} />
            <span
              className="absolute inset-y-0 bg-cyan-600/40"
              style={{ left: `${Math.min(100, c.coverage_pct)}%`, width: `${Math.max(0, Math.min(100, c.projected_coverage_pct) - c.coverage_pct)}%` }}
            />
            <span className="absolute inset-y-0 w-0.5 bg-foreground/60" style={{ left: "90%" }} title="yetişir eşiği %90" />
          </div>
          <p className="mt-1 text-[11.5px] text-muted-foreground">
            Koyu: bugüne kadar · açık: tahmini artış · çizgi: %90 (yetişir eşiği). Kalan {c.remaining_topics ?? 0} konu.
          </p>
        </div>
      ) : (
        <p className="mt-3 text-[12px] text-muted-foreground">
          {school ? "Tahmin için yeterli veri yok." : "Sınav tarihi girilince tahmin hesaplanır."}
        </p>
      )}
    </Panel>
  );
}

/* ============================================================== deneme */

function ExamTrendCard({ exams, delta, section }: { exams: AnalyticsExamPoint[]; delta: number | null; section: string | null }) {
  return (
    <Panel icon={GraduationCap} title="Deneme netleri · son 60 gün" desc="Değişim aynı türde (genel/branş) bir önceki denemeye göre." section="analytics:exams">
      {exams.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Son 60 günde girilmiş deneme yok.</p>
      ) : (
        <>
          {delta != null && section ? (
            <p className={cn("mb-2 inline-flex items-center gap-1.5 text-sm font-semibold", delta > 0 ? "text-emerald-700" : delta < 0 ? "text-rose-700" : "text-muted-foreground")}>
              {delta > 0 ? <TrendingUp className="size-4" /> : delta < 0 ? <TrendingDown className="size-4" /> : <Minus className="size-4" />}
              {delta > 0 ? "+" : ""}{fmt(delta, 2)} net <span className="text-xs font-normal text-muted-foreground">son {section} denemesi</span>
            </p>
          ) : null}
          <ul className="divide-y divide-border">
            {exams.map((e, i) => (
              <li key={i} className="flex items-center justify-between gap-2 py-1.5 text-sm">
                <span className="min-w-0">
                  <span className="font-medium text-foreground">{e.title}</span>
                  <span className="ml-2 text-[11.5px] text-muted-foreground">
                    {e.section_label}
                    {e.exam_date ? ` · ${e.exam_date.slice(5).replace("-", ".")}` : ""}
                  </span>
                </span>
                <span className="shrink-0 font-bold tabular-nums text-cyan-700">{fmt(e.net, 2)} net</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}

function WarningsCard({ warnings }: { warnings: AnalyticsWarningItem[] }) {
  return (
    <Panel icon={AlertTriangle} title="Dikkat sinyalleri" desc="Durum özetindeki uyarılarla aynı kaynak." section="analytics:warnings">
      <ul className="space-y-2">
        {warnings.map((w, i) => {
          const red = w.level === "red";
          return (
            <li key={i} className={cn("rounded-lg border-l-4 px-3 py-2", red ? "border-l-rose-600 bg-rose-500/10" : "border-l-amber-500 bg-amber-500/10")}>
              <p className={cn("inline-flex items-center gap-1.5 text-sm font-semibold", red ? "text-rose-800" : "text-amber-900")}>
                {red ? <Flame className="size-3.5" /> : <AlertTriangle className="size-3.5" />} {w.title}
              </p>
              {w.detail ? <p className="mt-0.5 text-xs text-foreground/80">{w.detail}</p> : null}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

/* ============================================================== kitap envanteri */

function BookInventory({ subjects }: { subjects: AnalyticsSubjectRow[] }) {
  const [open, setOpen] = React.useState(false);
  if (subjects.length === 0) return null;
  return (
    <section className="rounded-2xl border border-border bg-card" data-section="analytics:books">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-2 px-4 py-3 text-left"
      >
        <BookOpen className="mt-0.5 size-4 shrink-0 text-cyan-700" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-foreground">Kitap envanteri</span>
          <span className="block text-[12px] text-muted-foreground">
            Atanmış kitaplarda çözülen / ayrılan / kalan test. Kaynaksız çalışma burada yok — o müfredat kartında.
          </span>
        </span>
        <ChevronDown className={cn("mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open ? (
        <ul className="space-y-2.5 border-t border-border px-4 py-3">
          {subjects.map((r) => (
            <li key={r.subject_id} className="space-y-1">
              <div className="flex justify-between gap-2 text-[12.5px]">
                <span className="font-medium text-foreground">{r.name}</span>
                <span className="tabular-nums text-muted-foreground">
                  {r.completed} çözüldü · {r.reserved} ayrıldı · {r.remaining} kaldı / {r.total}
                </span>
              </div>
              <div className="flex h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
                <span className="bg-emerald-600" style={{ width: `${r.percent_done}%` }} />
                <span className="bg-amber-400" style={{ width: `${r.percent_reserved}%` }} />
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
