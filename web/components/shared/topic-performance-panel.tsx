"use client";

/**
 * Ders → Konu performans paneli — koç / öğrenci / veli ortak.
 *
 * 2026-10-14 yeniden tasarım (koç: "sayfa çok önemli ama içerik önemini yansıtmıyor"):
 *   1. Özet: çözülen test · doğruluk · SONUÇ GİRİLEN test oranı · zayıf konu sayısı (her sayı açıklamalı)
 *   2. Veri kalitesi uyarısı: test çözülüyor ama D/Y/B girilmiyorsa tespit yapılamaz — açıkça söylenir
 *   3. "Nerede kaybediyor": zayıf/dikkat konular kayıp puanına göre (görev + deneme; yalnız denemede
 *      zayıf görünen konular dahil)
 *   4. Ders kartları: D/Y/B çubuğu, sonuç oranı, konular seviyeye göre (zayıf önce)
 * Doğruluk renk eşikleri: ≥70 yeşil · 50–69 kehribar · <50 kırmızı (seviye, servis ile aynı).
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ClipboardCheck, Crosshair, GraduationCap, Info, Target } from "lucide-react";

import { DemoHint } from "@/components/demos/demo-hint";
import { PeriodContextNote, PeriodSwitcher } from "@/components/shared/period-switcher";
import { subjectColors } from "@/components/shared/subject-tag";
import {
  getParentTopicPerformance,
  getStudentTopicPerformance,
  getTeacherTopicPerformance,
  topicPerfKeys,
  type SubjectPerfRow,
  type TopicPerfRow,
  type TopicPerformanceResponse,
} from "@/lib/api/topic-performance";
import { cn } from "@/lib/utils";

type Audience = "coach" | "student" | "parent";
type Level = NonNullable<TopicPerfRow["level"]>;

const LEVEL: Record<Level, { label: string; badge: string; rank: number }> = {
  zayif: { label: "Zayıf", badge: "bg-rose-700 text-white", rank: 0 },
  dikkat: { label: "Dikkat", badge: "bg-amber-500 text-amber-950", rank: 1 },
  iyi: { label: "İyi", badge: "bg-emerald-700 text-white", rank: 2 },
  veri_yok: { label: "Sonuç yok", badge: "bg-slate-600 text-white", rank: 3 },
};

function accText(pct: number | null | undefined): string {
  if (pct == null) return "text-muted-foreground";
  if (pct >= 70) return "text-emerald-700 dark:text-emerald-300";
  if (pct >= 50) return "text-amber-700 dark:text-amber-300";
  return "text-rose-700 dark:text-rose-300";
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/** Doğru / yanlış / boş soru çubuğu (girilmemişse boş gri). */
function DybBar({ c, w, b, className }: { c: number; w: number; b: number; className?: string }) {
  const total = c + w + b;
  return (
    <div className={cn("flex h-2 w-full overflow-hidden rounded-full bg-muted", className)} aria-hidden>
      {total > 0 ? (
        <>
          <span className="bg-emerald-500" style={{ width: `${(100 * c) / total}%` }} />
          <span className="bg-rose-500" style={{ width: `${(100 * w) / total}%` }} />
          <span className="bg-slate-400" style={{ width: `${(100 * b) / total}%` }} />
        </>
      ) : null}
    </div>
  );
}

function LevelBadge({ level }: { level: Level | undefined }) {
  const m = LEVEL[level ?? "veri_yok"];
  return <span className={cn("inline-flex shrink-0 rounded px-1.5 py-0.5 text-[11px] font-semibold", m.badge)}>{m.label}</span>;
}

export function TopicPerformancePanel({
  source,
  studentId,
}: {
  source: "teacher" | "student" | "parent";
  studentId?: number;
}) {
  const audience: Audience = source === "teacher" ? "coach" : source;
  // P3: varsayılan GÜNCEL dönem (parametresiz istek).
  const [period, setPeriod] = React.useState<string | undefined>(undefined);
  const queryKey =
    source === "student"
      ? topicPerfKeys.student(period)
      : source === "parent"
        ? topicPerfKeys.parent(studentId ?? 0, period)
        : topicPerfKeys.teacher(studentId ?? 0, period);
  const fetcher = (): Promise<TopicPerformanceResponse> =>
    source === "student"
      ? getStudentTopicPerformance(period)
      : source === "parent"
        ? getParentTopicPerformance(studentId ?? 0, period)
        : getTeacherTopicPerformance(studentId ?? 0, period);
  const q = useQuery({ queryKey, queryFn: fetcher });
  const periodMeta = q.data?.period ?? null;

  if (q.isLoading) {
    return <div className="py-10 text-center text-sm text-muted-foreground">Yükleniyor…</div>;
  }
  if (q.isError || !q.data) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-muted-foreground">Veri yüklenemedi.</p>
        <button onClick={() => q.refetch()} className="mt-2 rounded-md bg-foreground px-4 py-1.5 text-sm font-medium text-background">
          Tekrar dene
        </button>
      </div>
    );
  }

  const { overall, subjects } = q.data;
  const focus = q.data.focus ?? [];
  const who = audience === "parent" ? "Çocuğunuzun" : audience === "student" ? "Senin" : "Öğrencinin";

  return (
    <div className="space-y-4" data-section="topic-perf">
      {source === "teacher" ? <DemoHint contextKey="topic-performance" role="teacher" /> : null}
      <PeriodSwitcher meta={periodMeta} value={period} onChange={setPeriod} />
      <PeriodContextNote meta={periodMeta} value={period} />

      {subjects.length === 0 && focus.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center">
          <Target className="mx-auto mb-2 size-7 text-muted-foreground" aria-hidden />
          <p className="text-sm font-medium text-foreground">Henüz konu performansı yok</p>
          <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
            {audience === "student"
              ? "Test çözüp doğru/yanlış/boş sayını girdikçe her dersin konularındaki performansın burada birikir."
              : `${who} çözdüğü testlerde doğru/yanlış/boş girildikçe ders ve konu bazında performans burada görünür.`}
          </p>
        </div>
      ) : (
        <>
          <Overview data={q.data} audience={audience} />
          <ResultGapBanner data={q.data} audience={audience} />
          <FocusList focus={focus} audience={audience} coverage={overall.result_coverage_pct ?? null} />
          <section className="space-y-2" data-section="topic-perf:subjects">
            <h3 className="px-1 text-sm font-semibold text-foreground">Derslere göre</h3>
            {subjects.map((s) => (
              <SubjectCard key={s.subject_id} s={s} />
            ))}
          </section>
          <Legend />
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Özet */

function Overview({ data, audience }: { data: TopicPerformanceResponse; audience: Audience }) {
  const o = data.overall;
  const withRes = o.tests_with_result ?? 0;
  const session = o.session_tests ?? 0;
  const enterable = Math.max(0, o.tests_solved - session);
  const cov = o.result_coverage_pct ?? null;
  const weak = o.weak_topics ?? 0;
  const focusN = (data.focus ?? []).length;
  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4" data-section="topic-perf:overview">
      <Stat
        icon={Target}
        value={String(o.tests_solved)}
        unit="test"
        label="Çözülen test"
        note={session > 0 ? `${session} tanesi koçun seansta işaretlediği test (sonuçsuz)` : "görevlerde çözülen, deneme hariç"}
      />
      <Stat
        icon={Crosshair}
        value={o.accuracy_pct == null ? "—" : `%${o.accuracy_pct}`}
        label="Doğruluk"
        valueCls={accText(o.accuracy_pct)}
        note={o.answered > 0 ? `${o.correct} doğru · ${o.wrong} yanlış · ${o.blank ?? 0} boş soru` : "sonuç girilmediği için hesaplanamıyor"}
      />
      <Stat
        icon={ClipboardCheck}
        value={`${withRes}/${enterable}`}
        unit="test"
        label="Sonucu girilen"
        valueCls={cov == null ? undefined : cov >= 70 ? "text-emerald-700 dark:text-emerald-300" : cov >= 30 ? "text-amber-700 dark:text-amber-300" : "text-rose-700 dark:text-rose-300"}
        note={cov == null ? "henüz test yok" : `doğru/yanlış/boş girilen test oranı: %${cov}`}
      />
      <Stat
        icon={AlertTriangle}
        value={String(Math.max(weak, focusN))}
        unit="konu"
        label="Zayıf / dikkat"
        valueCls={weak + focusN > 0 ? "text-rose-700 dark:text-rose-300" : undefined}
        note={audience === "parent" ? "çalışılması gereken konular" : "aşağıda kayıp sırasıyla"}
      />
    </div>
  );
}

function Stat({ icon: Icon, value, unit, label, note, valueCls }: {
  icon: React.ElementType; value: string; unit?: string; label: string; note: string; valueCls?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2.5">
      <p className="flex items-center gap-1.5 text-[12px] font-medium text-muted-foreground">
        <Icon className="size-3.5" aria-hidden /> {label}
      </p>
      <p className={cn("mt-0.5 text-2xl font-bold tabular-nums text-foreground", valueCls)}>
        {value}
        {unit ? <span className="ml-1 text-sm font-medium text-muted-foreground">{unit}</span> : null}
      </p>
      <p className="text-[11.5px] leading-snug text-muted-foreground">{note}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ Veri kalitesi */

function ResultGapBanner({ data, audience }: { data: TopicPerformanceResponse; audience: Audience }) {
  const o = data.overall;
  const cov = o.result_coverage_pct ?? null;
  const enterable = Math.max(0, o.tests_solved - (o.session_tests ?? 0));
  if (cov == null || enterable < 3 || cov >= 70) return null;
  const missing = enterable - (o.tests_with_result ?? 0);
  const action =
    audience === "coach"
      ? "Öğrenciden testi işaretlerken doğru / yanlış / boş sayısını da girmesini iste (Bugün sayfasında testin yanındaki ayar düğmesi). Sonuç girilmeden zayıf konu tespiti yapılamaz."
      : audience === "student"
        ? "Testi işaretlerken doğru / yanlış / boş sayını da gir (Bugün sayfasında testin yanındaki ayar düğmesi). Böylece hangi konuda zorlandığın burada görünür."
        : "Doğru / yanlış sayıları girildikçe hangi konularda zorlandığı burada görünür.";
  return (
    <div
      className="flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-[13px] text-amber-950 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
      data-section="topic-perf:gap"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p>
        <strong>{enterable} testin {missing} tanesinde sonuç girilmemiş</strong> (sonuç girilen test oranı: %{cov}).{" "}
        {action}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ Nerede kaybediyor */

function FocusList({ focus, audience, coverage }: { focus: TopicPerfRow[]; audience: Audience; coverage: number | null }) {
  const title = audience === "student" ? "Nerede puan kaybediyorsun?" : "Nerede puan kaybediyor?";
  return (
    <section className="rounded-xl border border-border bg-card" data-section="topic-perf:focus">
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-1 border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <p className="text-[12px] text-muted-foreground">
          Görevlerde ve son 90 gün denemelerde doğruluğu düşük konular — en çok soru kaybettiren önde.
        </p>
      </header>
      {focus.length === 0 ? (
        <p className="px-4 py-4 text-[13px] text-muted-foreground">
          {coverage != null && coverage < 30
            ? "Sonuç girilmediği için zayıf konu tespiti yapılamıyor."
            : "Şu an zayıf görünen konu yok."}
        </p>
      ) : (
        <ol className="divide-y divide-border/70">
          {focus.map((t, i) => (
            <li
              key={`${t.topic_id ?? "l"}-${t.topic_name}-${i}`}
              className="grid gap-x-4 gap-y-1 px-4 py-2.5 sm:grid-cols-[minmax(0,1fr)_auto]"
              data-testid="topic-perf-focus"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-sm font-medium text-foreground">{t.topic_name}</span>
                  <LevelBadge level={t.level} />
                  {t.exam_only ? (
                    <span className="rounded bg-violet-700 px-1.5 py-0.5 text-[11px] font-semibold text-white">
                      yalnız denemede
                    </span>
                  ) : null}
                </div>
                <p className="text-[12px] text-muted-foreground">{t.subject_name ?? "—"}</p>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground sm:justify-end">
                {t.answered > 0 ? (
                  <span>
                    görevde <strong className={cn("tabular-nums", accText(t.accuracy_pct))}>%{t.accuracy_pct}</strong>{" "}
                    <span className="tabular-nums">({t.answered} soru)</span>
                  </span>
                ) : null}
                {(t.exam_answered ?? 0) > 0 ? (
                  <span className="inline-flex items-center gap-1">
                    <GraduationCap className="size-3.5" aria-hidden />
                    denemede <strong className={cn("tabular-nums", accText(t.exam_accuracy_pct))}>%{t.exam_accuracy_pct}</strong>{" "}
                    <span className="tabular-nums">({t.exam_answered} soru)</span>
                  </span>
                ) : null}
                <span>
                  kaybedilen <strong className="tabular-nums text-foreground">{t.loss_score ?? 0}</strong> soru
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ Ders kartı */

function SubjectCard({ s }: { s: SubjectPerfRow }) {
  const [open, setOpen] = React.useState(false);
  const c = subjectColors(s.subject_name);
  const session = s.session_tests ?? 0;
  const enterable = Math.max(0, s.tests_solved - session);
  const withRes = s.tests_with_result ?? 0;
  const weak = s.weak_topics ?? 0;
  const topics = [...s.topics].sort(
    (a, b) => LEVEL[a.level ?? "veri_yok"].rank - LEVEL[b.level ?? "veri_yok"].rank || b.tests_solved - a.tests_solved,
  );
  return (
    <div className="overflow-hidden rounded-xl border border-l-4 border-border bg-card" style={{ borderLeftColor: c.rail }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="grid w-full gap-x-4 gap-y-1.5 px-4 py-3 text-left transition hover:bg-muted/40 sm:grid-cols-[minmax(0,1fr)_minmax(160px,240px)_auto]"
        data-testid="topic-perf-subject"
      >
        <div className="flex min-w-0 items-start gap-2">
          <ChevronDown className={cn("mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">{s.subject_name}</p>
            <p className="text-[12px] text-muted-foreground">
              {s.tests_solved} test · {s.topics.length} konu · sonucu girilen {withRes}/{enterable} test
              {session > 0 ? ` · ${session} seansta` : ""}
            </p>
          </div>
        </div>
        <div className="flex flex-col justify-center gap-1">
          <DybBar c={s.correct} w={s.wrong} b={s.blank ?? 0} />
          <p className="text-[11.5px] tabular-nums text-muted-foreground">
            <span className="text-emerald-700 dark:text-emerald-300">{s.correct} D</span> ·{" "}
            <span className="text-rose-700 dark:text-rose-300">{s.wrong} Y</span> · {s.blank ?? 0} B
          </p>
        </div>
        <div className="flex items-center gap-2 sm:justify-end">
          {weak > 0 ? (
            <span className="rounded bg-rose-700 px-1.5 py-0.5 text-[11px] font-semibold text-white">{weak} zayıf/dikkat</span>
          ) : null}
          <span className={cn("text-lg font-bold tabular-nums", accText(s.accuracy_pct))}>
            {s.accuracy_pct == null ? "—" : `%${s.accuracy_pct}`}
          </span>
        </div>
      </button>
      {open ? (
        <ul className="divide-y divide-border/60 border-t border-border/60">
          {topics.map((tp) => {
            const sess = tp.session_tests ?? 0;
            return (
              <li
                key={`${tp.topic_id ?? "l"}-${tp.topic_name}`}
                className="grid gap-x-4 gap-y-1 px-4 py-2.5 sm:grid-cols-[minmax(0,1fr)_minmax(140px,220px)_auto]"
                data-testid="topic-perf-topic"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[13px] font-medium text-foreground">{tp.topic_name}</span>
                    <LevelBadge level={tp.level} />
                  </div>
                  <p className="text-[11.5px] text-muted-foreground">
                    {tp.tests_solved} test{sess > 0 ? ` (${sess} tanesi seansta)` : ""}
                    {tp.last_solved_at ? ` · son: ${fmtDate(tp.last_solved_at)}` : ""}
                    {(tp.exam_answered ?? 0) > 0 ? ` · denemede %${tp.exam_accuracy_pct} (${tp.exam_answered} soru)` : ""}
                  </p>
                </div>
                <div className="flex flex-col justify-center gap-1">
                  <DybBar c={tp.correct} w={tp.wrong} b={tp.blank ?? 0} />
                  <p className="text-[11.5px] tabular-nums text-muted-foreground">
                    {tp.answered + (tp.blank ?? 0) > 0 ? (
                      <>
                        <span className="text-emerald-700 dark:text-emerald-300">{tp.correct} D</span> ·{" "}
                        <span className="text-rose-700 dark:text-rose-300">{tp.wrong} Y</span> · {tp.blank ?? 0} B
                      </>
                    ) : (
                      "sonuç girilmemiş"
                    )}
                  </p>
                </div>
                <span className={cn("self-center text-sm font-bold tabular-nums sm:text-right", accText(tp.accuracy_pct))}>
                  {tp.accuracy_pct == null ? "—" : `%${tp.accuracy_pct}`}
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

function Legend() {
  return (
    <details className="rounded-lg bg-muted/50 px-3 py-2 text-[12px] text-muted-foreground">
      <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-foreground">
        <Info className="size-3.5 shrink-0" aria-hidden /> Hesap nasıl yapılır?
      </summary>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li><strong className="text-foreground">Doğruluk</strong> = doğru ÷ (doğru + yanlış). Boş ayrıca gösterilir, doğruluğa girmez.</li>
        <li><strong className="text-foreground">Seviye:</strong> en az 8 soruda sonuç girilmişse — %50 altı zayıf, %50–69 dikkat, %70+ iyi. Son 90 gün denemede en az 3 soruda %40 altı ise konu en az “dikkat” olur.</li>
        <li><strong className="text-foreground">Kaybedilen soru</strong> = görevde yanlış + boş + denemede yanlışın iki katı (deneme gerçek sınav koşulu).</li>
        <li>Kitaplı ve kaynaksız (konuya bağlı) görevler sayılır; koçun seansta işaretlediği testler test sayısına girer ama sonuç taşımaz. Deneme kitapları burada sayılmaz.</li>
      </ul>
    </details>
  );
}
