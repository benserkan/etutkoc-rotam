"use client";

/**
 * Öğrenci Gelişim Raporu (360°) — öğrenci detayında Genel'in yanındaki kendi sekmesi
 * (2026-10-27'ye kadar Denemeler'in alt sekmesiydi).
 *
 * Bu hafta (aynı güne kadar kıyas) · hafta hafta tablo + deneme netleri · gelişim döneminde
 * gelinen nokta · mevcut durum / güçlü yanlar / fırsatlar / riskler · aksiyon planı.
 * Her madde seçilip sıradaki seansın gündemine eklenebilir.
 *
 * Rapor SAKLANMAZ: her açılışta, pencereye dönüşte ve dakikada bir güncel veriden yeniden
 * hesaplanır (app/services/development_report.py).
 */

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Gauge,
  ListChecks,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import {
  developmentReportKeys,
  getDevelopmentReport,
  type DRAction,
  type DRExamSeries,
  type DRItem,
  type DRReport,
  type DRWeekRow,
} from "@/lib/api/development-report";
import { fmtNet, fmtSigned, fmtTRDate } from "@/lib/exam-format";
import { useAddAgendaItems } from "@/lib/hooks/use-exam-progress-mutations";
import { cn } from "@/lib/utils";

const PRIORITY: Record<number, { label: string; cls: string }> = {
  1: { label: "Öncelikli", cls: "bg-rose-600 text-white" },
  2: { label: "Önemli", cls: "bg-amber-600 text-white" },
  3: { label: "Takip", cls: "bg-slate-600 text-white" },
};

const SOURCE_LABEL: Record<string, string> = {
  weekly: "Haftalık program",
  exam: "Deneme",
  data: "Veri girişi",
};



function pct(v: number | null | undefined): string {
  return v == null ? "—" : `%${Math.round(v)}`;
}

function ago(iso: string | null): string {
  if (!iso) return "—";
  const t = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).getTime();
  const m = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (m < 1) return "az önce";
  if (m < 60) return `${m} dk önce`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} saat önce`;
  return `${Math.round(h / 24)} gün önce`;
}

/**
 * Sekme sarmalayıcısı. Seri seçici BİLİNÇLİ yok (2026-10-27, koç: "gerek var mı?"):
 * rapor öğrencinin bütününe dair; deneme bölümü ana sınav serisinden (genel deneme,
 * en çok kaydı olan; okul yazılısı en sona) sunucuda seçilir. Seri seri inceleme Denemeler'de.
 */
export function StudentDevelopmentReportTab({ studentId }: { studentId: number }) {
  return <StudentDevelopmentReport studentId={studentId} series={null} />;
}

export function StudentDevelopmentReport({
  studentId,
  series,
  period,
}: {
  studentId: number;
  series: string | null;
  period?: string;
}) {
  const q = useQuery({
    queryKey: developmentReportKeys.report(studentId, series, period),
    queryFn: () => getDevelopmentReport(studentId, series, period),
    // Rapor her zaman güncel veriden: önbellek tutulmaz, sekmeye dönüşte ve dakikada bir yenilenir.
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
    refetchInterval: 60_000,
  });
  const [picked, setPicked] = React.useState<Map<string, string>>(() => new Map());
  const add = useAddAgendaItems(studentId);

  if (q.isLoading) return <p className="text-sm text-muted-foreground">Gelişim raporu hesaplanıyor…</p>;
  if (q.isError || !q.data) {
    return <p className="text-sm text-rose-700">Gelişim raporu yüklenemedi.</p>;
  }
  const d = q.data;

  const toggle = (key: string, agenda: string) =>
    setPicked((m) => {
      const n = new Map(m);
      if (n.has(key)) n.delete(key);
      else n.set(key, agenda);
      return n;
    });
  const sendPicked = () => {
    const items = [...picked.entries()].map(([key, text]) => ({
      key,
      text: text.slice(0, 400),
      source: "report",
    }));
    if (!items.length) return;
    const chunks: (typeof items)[] = [];
    for (let i = 0; i < items.length; i += 20) chunks.push(items.slice(i, i + 20));
    chunks.forEach((c, i) =>
      add.mutate(c, { onSuccess: i === chunks.length - 1 ? () => setPicked(new Map()) : undefined }),
    );
  };
  const sel = { picked, toggle };

  const periodActions = d.actions.filter((a) => a.source !== "weekly");
  const strengths = d.strengths.filter((it) => isPeriodItem(it.key));
  const risks = notInPlan(d.risks.filter((it) => isPeriodItem(it.key)), periodActions);
  const opportunities = notInPlan(d.opportunities, periodActions);

  return (
    <div className="space-y-5" data-section="dev-report">
      <Header d={d} fetching={q.isFetching} onRefresh={() => q.refetch()} />

      <PeriodSummary d={d} />

      {d.weeks.length || d.exam.exams.length ? <WeeksSection d={d} /> : null}
      {(d.exam_series ?? []).length ? <ExamSeriesSection series={d.exam_series ?? []} /> : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FindingBox
          icon={Sparkles}
          title="Dönemin güçlü yanları"
          desc="Başlangıca göre yükselen ya da öğrencinin normalinin üstündeki alanlar."
          tone="good"
          items={strengths}
          sel={sel}
          empty="Dönem boyunca belirgin bir yükseliş görünmüyor."
        />
        <FindingBox
          icon={ShieldAlert}
          title="Dönemin riskleri"
          desc="Başlangıca göre gerileyen ya da süregelen sorunlar."
          tone="warn"
          items={risks}
          sel={sel}
          empty="Dönem boyunca süregelen bir sorun görünmüyor."
        />
      </div>

      <ActionPlan actions={periodActions} opportunities={opportunities} sel={sel} />

      <div
        className={cn(
          // sağda Rota asistan balonuna yer bırak (balon fixed right-4/6 · bottom-5/6)
          "sticky bottom-3 z-20 mr-16 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-cyan-700/40 bg-card px-4 py-2.5 shadow-lg sm:mr-20",
          !picked.size && "hidden",
        )}
        data-testid="dev-report-bar"
      >
        <p className="text-sm">
          <span className="font-semibold">{picked.size} madde seçili</span>
          <span className="ml-2 text-xs text-muted-foreground">
            Sıradaki seansın gündemine eklenir; yeni seans formunda işaretli gelir.
          </span>
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setPicked(new Map())}>
            Seçimi temizle
          </Button>
          <Button
            size="sm"
            className="bg-cyan-700 text-white hover:bg-cyan-800"
            onClick={sendPicked}
            disabled={add.isPending}
          >
            <ClipboardList className="size-4" aria-hidden />
            Seansa ekle ({picked.size})
          </Button>
        </div>
      </div>
    </div>
  );
}

type Sel = { picked: Map<string, string>; toggle: (key: string, agenda: string) => void };

/** Aynı bulgu hem Riskler/Fırsatlar'da hem Aksiyon planında çıkmasın (2026-11-14):
 *  başlığı bir aksiyonun başlığında geçen madde (seri öneki ve parantez hariç) plandadır. */
function coreTitle(t: string): string {
  return t
    .replace(/^[^:]*\(genel deneme\):\s*/i, "")
    .replace(/^[A-ZÇĞİÖŞÜ][^·:]{0,30} · /, "")
    .replace(/\s*\([^)]*\)\s*$/, "")
    .replace(/ konusunu kapat$/i, "")
    .toLocaleLowerCase("tr")
    .trim();
}

function notInPlan(items: DRItem[], actions: DRAction[]): DRItem[] {
  const plan = actions.map((a) => coreTitle(a.title));
  return items.filter((it) => {
    const c = coreTitle(it.title);
    return !plan.some((p) => p === c || (c.length >= 6 && p.length >= 6 && (p.includes(c) || c.includes(p))));
  });
}

/** Bu haftaya ait bulgular (haftalık ölçü kartları, ders dengesi) Genel sekmesinde; dönem
 *  raporu yalnız dönem boyunca süren eğilimleri gösterir (2026-11-14). */
function isPeriodItem(key: string): boolean {
  return !key.startsWith("risk:wk:") && !key.startsWith("good:wk:") && key !== "risk:balance";
}

// ---------------------------------------------------------------- başlık

function Header({ d, fetching, onRefresh }: { d: DRReport; fetching: boolean; onRefresh: () => void }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 max-w-2xl">
        <h2 className="flex items-center gap-2 text-xl font-bold">
          <Gauge className="size-5 text-cyan-700" aria-hidden />
          Dönem Raporu
        </h2>
        <p className="mt-1 text-[15px] leading-relaxed text-muted-foreground">
          Öğrencinin dönem başından bugüne nereden nereye geldiğini tek sayfada gösterir. Aylık
          değerlendirmede ve veli görüşmesinden önce hazırlık için kullan.
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Son işaretleme {ago(d.activity.last_tick_at)} · son deneme {ago(d.activity.last_exam_at)}
          {d.queue_count ? ` · seans gündeminde ${d.queue_count} madde` : ""}
        </p>
      </div>
      <Button size="sm" variant="outline" onClick={onRefresh} disabled={fetching}>
        <RefreshCw className={cn("size-4", fetching && "animate-spin")} aria-hidden />
        {fetching ? "Güncelleniyor…" : "Yenile"}
      </Button>
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  desc,
  children,
  actions,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-base font-bold">
            <Icon className="size-5 text-cyan-700" aria-hidden />
            {title}
          </h3>
          {desc ? <p className="mt-0.5 text-sm text-muted-foreground">{desc}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------- bu hafta

function WeeksSection({ d }: { d: DRReport }) {
  const rows = d.weeks;
  const ended = d.this_week?.week.ended ?? false;
  const chart = rows.map((w) => ({
    label: w.label,
    pct: w.gorev_pct,
    net: w.exam_nets.length ? Math.round((w.exam_nets.reduce((a, b) => a + b, 0) / w.exam_nets.length) * 100) / 100 : null,
    current: w.current,
    exams: (w.exam_marks ?? []).map((m) => `${m.series_label ?? ""} ${fmtNet(m.net)}`.trim()).join(" · ") || w.exam_titles.join(", "),
  }));
  const hasNet = chart.some((c) => c.net != null);
  return (
    <Section
      icon={TrendingUp}
      title="Haftadan haftaya"
      desc={`Sütun: görev uyumu. Mor nokta: o hafta girilen ${(d.exam.section_label ?? "genel deneme").replace(/\s*\(genel deneme\)$/, "")} neti.`}
    >
      {rows.length ? (
        <div className="relative -mx-1 overflow-x-auto px-1">
          <div className="h-[240px]" style={{ minWidth: Math.max(420, rows.length * 46) }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chart} margin={{ top: 8, right: 8, bottom: 4, left: -8 }}>
                <CartesianGrid stroke="currentColor" strokeOpacity={0.22} vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }}
                  stroke="currentColor" strokeOpacity={0.3} interval={0} />
                <YAxis yAxisId="p" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]}
                  tickFormatter={(v: number) => `%${v}`} width={42}
                  tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }} stroke="currentColor" strokeOpacity={0.3} />
                {hasNet ? (
                  <YAxis yAxisId="n" orientation="right" width={36} domain={["auto", "auto"]}
                    tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }} stroke="currentColor" strokeOpacity={0.3} />
                ) : null}
                <Tooltip content={<WeekTip />} cursor={{ fill: "currentColor", fillOpacity: 0.05 }} />
                <Bar yAxisId="p" dataKey="pct" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {chart.map((c) => (
                    <Cell key={c.label} fill={c.current ? "#0e7490" : "#67b7c6"} />
                  ))}
                </Bar>
                {hasNet ? (
                  <Line yAxisId="n" dataKey="net" stroke="#7c3aed" strokeWidth={2} connectNulls
                    dot={{ r: 4, fill: "#7c3aed", stroke: "var(--card)", strokeWidth: 2 }} isAnimationActive={false} />
                ) : null}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : null}

      {rows.length ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-semibold text-cyan-800 hover:underline">
            Hafta hafta tablo ({rows.length} hafta)
          </summary>
        <div className="relative mt-2 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm" data-testid="dev-report-weeks">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Hafta</th>
                <th className="py-2 pr-3 text-right font-medium">Görev</th>
                <th className="py-2 pr-3 text-right font-medium">Uyum</th>
                <th className="py-2 pr-3 text-right font-medium" title="Önceki haftaya göre uyum farkı">Fark</th>
                <th className="py-2 pr-3 text-right font-medium">Test</th>
                <th className="py-2 pr-3 text-right font-medium">Gününde</th>
                <th className="py-2 pr-3 text-right font-medium">Boş gün</th>
                <th className="py-2 pr-3 text-right font-medium" title="Doğru/yanlış girilen test / çözülen test">D/Y girilen</th>
                <th className="py-2 text-right font-medium">Deneme neti</th>
              </tr>
            </thead>
            <tbody>
              {[...rows].reverse().map((w, i, arr) => (
                <WeekRow key={w.start} w={w} prev={arr[i + 1] ?? null} ended={ended} />
              ))}
            </tbody>
          </table>
        </div>
        </details>
      ) : null}
    </Section>
  );
}

function WeekRow({ w, prev, ended }: { w: DRWeekRow; prev: DRWeekRow | null; ended: boolean }) {
  const diff = w.gorev_pct != null && prev?.gorev_pct != null ? Math.round(w.gorev_pct - prev.gorev_pct) : null;
  return (
    <tr className={cn("border-b border-border last:border-0", w.current && "bg-cyan-500/10 font-medium")}>
      <td className="py-1.5 pr-3">
        {w.label}
        {w.current ? <span className="ml-1.5 rounded bg-cyan-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">{ended ? "son hafta" : "bu hafta"}</span> : null}
        {w.cut ? <span className="ml-1.5 text-[11px] text-muted-foreground">(kısa hafta)</span> : null}
      </td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{w.gorev_done}/{w.gorev_total}</td>
      <td className={cn("py-1.5 pr-3 text-right font-semibold tabular-nums",
        w.gorev_pct != null && w.gorev_pct >= 80 && "text-emerald-700",
        w.gorev_pct != null && w.gorev_pct < 60 && "text-rose-700")}>
        {pct(w.gorev_pct)}
      </td>
      <td className={cn("py-1.5 pr-3 text-right tabular-nums",
        diff != null && diff >= 5 && "text-emerald-700",
        diff != null && diff <= -5 && "text-rose-700")}>
        {diff == null ? "—" : `${diff > 0 ? "+" : ""}${diff}`}
      </td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{w.test_done}/{w.test_planned}{w.questions_done ? <span className="block text-xs text-muted-foreground">+{w.questions_done} soru</span> : null}</td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{pct(w.ontime_pct)}</td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{w.empty_days}</td>
      <td className="py-1.5 pr-3 text-right tabular-nums">
        {w.tests_done_items ? `${w.tests_with_result}/${w.tests_done_items}` : "—"}
      </td>
      <td className="py-1.5 text-right tabular-nums" title={(w.exam_marks ?? []).map((m) => m.title).join(", ") || w.exam_titles.join(", ")}>
        {w.exam_marks?.length
          ? w.exam_marks.map((m) => `${m.series_label ?? ""} ${fmtNet(m.net)}`.trim()).join(" · ")
          : w.exam_nets.length
            ? w.exam_nets.map((n) => fmtNet(n)).join(" · ")
            : "—"}
      </td>
    </tr>
  );
}

function WeekTip({ active, payload }: { active?: boolean; payload?: { payload: { label: string; pct: number | null; net: number | null; exams: string } }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground">
      <p className="font-semibold">{p.label}</p>
      <p>Görev uyumu {pct(p.pct)}</p>
      {p.exams ? <p>Denemeler: {p.exams}</p> : null}
    </div>
  );
}

// ---------------------------------------------------------------- gelinen nokta

function PeriodSummary({ d }: { d: DRReport }) {
  const j = d.journey;
  const main = (d.exam_series ?? []).find((x) => x.stats && x.exams.length >= 2) ?? null;
  if (!j && !main) {
    return (
      <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground" data-testid="dev-report-headline">
        Dönem özeti için birkaç program haftası ya da en az iki deneme gerekiyor.
      </p>
    );
  }
  const uyumDiff =
    j && j.start_gorev_pct != null && j.recent_gorev_pct != null ? j.recent_gorev_pct - j.start_gorev_pct : null;
  const label = main ? (main.label ?? "Deneme").replace(/\s*\(genel deneme\)$/, "") : "";
  const slope = main?.stats?.slope ?? null;
  const parts: string[] = [];
  if (j) {
    parts.push(
      `${j.weeks} tamamlanan haftada görev uyumu ${pct(j.start_gorev_pct)} → ${pct(j.recent_gorev_pct)}` +
        (uyumDiff == null ? "" : uyumDiff >= 5 ? " (yükseliyor)" : uyumDiff <= -5 ? " (düşüyor)" : " (yatay)"),
    );
  }
  if (main?.stats) {
    parts.push(
      `${label} neti ${fmtNet(main.stats.first_net)} → ${fmtNet(main.stats.last_net)}` +
        (slope == null ? "" : slope >= 0.5 ? " (yükseliyor)" : slope <= -0.5 ? " (düşüyor)" : " (yatay)"),
    );
  }
  return (
    <section
      className="rounded-xl border border-border border-l-4 border-l-cyan-700 bg-card p-4 sm:p-5"
      data-section="dev-report:summary"
    >
      <p className="text-xs font-bold tracking-wide text-cyan-800">
        DÖNEM ÖZETİ{j?.first_week ? ` · ${j.first_week} haftasından bugüne` : ""}
      </p>
      <p className="mt-1 text-lg font-semibold leading-snug" data-testid="dev-report-headline">
        {parts.join("; ")}.
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {j ? (
          <>
            <Stat label="Tamamlanan hafta" value={`${j.weeks} hafta`} sub={`${j.tests_total} test çözüldü`} />
            <Stat
              label="Görev uyumu"
              value={`${pct(j.start_gorev_pct)} → ${pct(j.recent_gorev_pct)}`}
              sub="ilk 3 hafta → son 3 hafta"
              tone={uyumDiff == null ? null : uyumDiff >= 5 ? "good" : uyumDiff <= -5 ? "bad" : null}
            />
            <Stat
              label="Haftalık test"
              value={`${j.start_tests_per_week == null ? "—" : Math.round(j.start_tests_per_week)} → ${j.recent_tests_per_week == null ? "—" : Math.round(j.recent_tests_per_week)}`}
              sub="ilk 3 hafta → son 3 hafta"
            />
          </>
        ) : null}
        {main?.stats ? (
          <Stat
            label={`${label} neti`}
            value={`${fmtNet(main.stats.first_net)} → ${fmtNet(main.stats.last_net)}`}
            sub={
              main.target
                ? `hedef ${fmtNet(main.target.target_net)} · son 3 ort. ${fmtNet(main.stats.avg_last3)}`
                : `son 3 ortalama ${fmtNet(main.stats.avg_last3)}`
            }
            tone={slope == null ? null : slope >= 0.5 ? "good" : slope <= -0.5 ? "bad" : null}
          />
        ) : null}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- denemeler (seri seri)

/** 2026-10-27 (koç): seri seçtirilmez — TYT, AYT, okul denemesi her biri kendi kartında, kendi
 *  ölçeğinde. Soru sayısı değişen seride (okul denemesi: 40 / 80 / 20+20) net tek başına
 *  kıyaslanamaz → net yüzdesi (net ÷ soru) öne alınır. */
function ExamSeriesSection({ series }: { series: DRExamSeries[] }) {
  return (
    <Section
      icon={ClipboardList}
      title="Denemeler"
      desc="Her deneme türü kendi içinde kıyaslanır; TYT ile AYT karıştırılmaz."
    >
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {series.map((x) => (
          <ExamSeriesCard key={x.series ?? x.label ?? "seri"} x={x} />
        ))}
      </div>
    </Section>
  );
}

function netPct(net: number, q?: number | null): number | null {
  return q ? Math.round((net / q) * 100) : null;
}

function ExamSeriesCard({ x }: { x: DRExamSeries }) {
  const st = x.stats;
  const first = x.exams[0];
  const last = x.exams[x.exams.length - 1];
  const pctMode = x.varying_questions;
  const fp = first ? netPct(first.net, first.questions) : null;
  const lp = last ? netPct(last.net, last.questions) : null;
  const pctChange = fp != null && lp != null ? lp - fp : null;
  const pcts = x.exams.map((e) => netPct(e.net, e.questions)).filter((v): v is number => v != null);
  const last3 = pcts.slice(-3);
  const avgPct = last3.length ? Math.round(last3.reduce((a, b) => a + b, 0) / last3.length) : null;
  return (
    <div className="min-w-0 rounded-lg border border-border p-3" data-testid="dev-report-series">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold">{x.label ?? "Deneme"}</p>
        <p className="text-xs text-muted-foreground">
          {x.exams.length} deneme{pctMode ? " · soru sayısı değişiyor, net yüzdesiyle kıyas" : ""}
        </p>
      </div>
      {st ? (
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {pctMode ? (
            <Stat
              label="Net yüzdesi (ilk → son)"
              value={`%${fp ?? "—"} → %${lp ?? "—"}`}
              sub={`son: ${fmtNet(last.net)} net / ${last.questions ?? "?"} soru`}
              tone={pctChange == null ? null : pctChange >= 3 ? "good" : pctChange <= -3 ? "bad" : null}
            />
          ) : (
            <Stat
              label="Net (ilk → son)"
              value={`${fmtNet(st.first_net)} → ${fmtNet(st.last_net)}`}
              sub={st.slope != null ? `deneme başına ${fmtSigned(st.slope)}` : undefined}
              tone={st.change >= 1 ? "good" : st.change <= -1 ? "bad" : null}
            />
          )}
          {pctMode ? (
            <Stat label="Son 3 ortalama" value={avgPct == null ? "—" : `%${avgPct}`}
              sub={pcts.length ? `en iyi %${Math.max(...pcts)}` : undefined} />
          ) : (
            <Stat label="Son 3 ortalama" value={fmtNet(st.avg_last3)} sub={`en iyi ${fmtNet(st.best_net)}`} />
          )}
          <Stat
            label="Hedef"
            value={x.target ? fmtNet(x.target.target_net) : "—"}
            sub={x.target?.gap != null ? (x.target.gap <= 0 ? "ulaştı" : `${fmtNet(x.target.gap)} net kaldı`) : "hedef girilmedi"}
          />
        </div>
      ) : null}
      {pctMode ? (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Ders netleri, soru sayısı denemeden denemeye değiştiği için burada kıyaslanmaz; ders ders
          inceleme Denemeler sekmesinde.
        </p>
      ) : !x.subjects.length && (st?.count ?? 0) === 1 ? (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Bu türde tek deneme var; ders ders değişim ikinci denemeden sonra görünür. Ders netleri
          Denemeler sekmesinde.
        </p>
      ) : x.subjects.length ? (
        <div className="relative mt-3 overflow-x-auto">
          <table className="w-full min-w-[360px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-1.5 pr-3 font-medium">Ders</th>
                <th className="py-1.5 pr-3 text-right font-medium">İlk</th>
                <th className="py-1.5 pr-3 text-right font-medium">Son</th>
                <th className="py-1.5 text-right font-medium">Değişim</th>
              </tr>
            </thead>
            <tbody>
              {x.subjects.map((s) => (
                <tr key={s.name} className="border-b border-border last:border-0">
                  <td className="py-1 pr-3">{s.name}</td>
                  <td className="py-1 pr-3 text-right tabular-nums">{fmtNet(s.first)}</td>
                  <td className="py-1 pr-3 text-right font-medium tabular-nums">{fmtNet(s.last)}</td>
                  <td className={cn("py-1 text-right tabular-nums",
                    (s.change ?? 0) >= 1 && "text-emerald-700",
                    (s.change ?? 0) <= -1 && "text-rose-700")}>
                    {s.change == null ? "—" : fmtSigned(s.change)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <ul className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
        {x.exams.map((e) => (
          <li key={e.id} className="rounded-full bg-muted px-2 py-0.5 text-foreground" title={e.title}>
            {fmtTRDate(e.exam_date)} · {fmtNet(e.net)} net
            {pctMode && e.questions ? ` / ${e.questions} soru (%${netPct(e.net, e.questions)})` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "bad" | null }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-lg font-semibold tabular-nums",
        tone === "good" && "text-emerald-700",
        tone === "bad" && "text-rose-700")}>
        {value}
      </p>
      {sub ? <p className="mt-0.5 text-[11px] text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

// ---------------------------------------------------------------- 360 kutuları

const BOX_TONE = {
  info: "border-t-sky-600",
  good: "border-t-emerald-600",
  warn: "border-t-rose-600",
};

function FindingBox({
  icon: Icon,
  title,
  desc,
  tone,
  items,
  sel,
  empty,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
  tone: keyof typeof BOX_TONE;
  items: DRItem[];
  sel: Sel;
  empty?: string;
}) {
  return (
    <section className={cn("rounded-xl border border-border border-t-4 bg-card p-4 sm:p-5", BOX_TONE[tone])}>
      <h3 className="flex items-center gap-2 text-base font-bold">
        <Icon className="size-5" aria-hidden />
        {title}
        <span className="rounded-full bg-muted px-2 text-xs tabular-nums">{items.length}</span>
      </h3>
      <p className="mt-0.5 text-sm text-muted-foreground">{desc}</p>
      {items.length ? (
        <ul className="mt-3 space-y-2">
          {items.map((it) => (
            <SelectableRow
              key={it.key}
              id={it.key}
              agenda={it.agenda}
              queued={it.queued}
              sel={sel}
              title={it.title}
              badge={it.tone === "bad" || (it.priority === 1 && tone === "warn") ? PRIORITY[1] : null}
              detail={it.text}
              ctaLabel={it.cta_label}
              ctaHref={it.cta_href}
            />
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">{empty ?? "—"}</p>
      )}
    </section>
  );
}

function ActionPlan({ actions, opportunities, sel }: { actions: DRAction[]; opportunities: DRItem[]; sel: Sel }) {
  const selectable = actions.filter((a) => !a.queued);
  const allPicked = selectable.length > 0 && selectable.every((a) => sel.picked.has(a.key));
  const top = actions.filter((a) => a.priority === 1).slice(0, 6);
  const shown = top.length ? top : actions.slice(0, 4);
  const rest = actions.filter((a) => !shown.includes(a));
  const row = (a: DRAction) => (
    <SelectableRow
      key={a.key}
      id={a.key}
      agenda={a.agenda}
      queued={a.queued}
      sel={sel}
      title={a.title}
      badge={PRIORITY[a.priority] ?? PRIORITY[3]}
      tag={SOURCE_LABEL[a.source]}
      detail={a.detail}
      ctaLabel={a.cta_label}
      ctaHref={a.cta_href}
    />
  );
  return (
    <Section
      icon={ListChecks}
      title="Sonraki adımlar"
      desc="Dönemin verisinden çıkan öneriler, önem sırasıyla. İşaretlediklerin seans gündemine eklenir."
      actions={
        selectable.length ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              selectable.forEach((a) => {
                if (allPicked === sel.picked.has(a.key)) sel.toggle(a.key, a.agenda);
              })
            }
          >
            {allPicked ? "Seçimi kaldır" : "Tümünü seç"}
          </Button>
        ) : null
      }
    >
      {actions.length ? (
        <ul className="space-y-2" data-testid="dev-report-actions">
          {shown.map(row)}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Şu an önerilen bir adım yok.</p>
      )}
      {rest.length ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-semibold text-cyan-800 hover:underline">
            {rest.length} öneri daha
          </summary>
          <ul className="mt-2 space-y-2">{rest.map(row)}</ul>
        </details>
      ) : null}
      {opportunities.length ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-semibold text-cyan-800 hover:underline">
            Diğer fırsatlar ({opportunities.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {opportunities.map((it) => (
              <SelectableRow
                key={it.key}
                id={it.key}
                agenda={it.agenda}
                queued={it.queued}
                sel={sel}
                title={it.title}
                detail={it.text}
                ctaLabel={it.cta_label}
                ctaHref={it.cta_href}
              />
            ))}
          </ul>
        </details>
      ) : null}
    </Section>
  );
}

function SelectableRow({
  id,
  agenda,
  queued,
  sel,
  title,
  badge,
  tag,
  detail,
  ctaLabel,
  ctaHref,
}: {
  id: string;
  agenda: string;
  queued: boolean;
  sel: Sel;
  title: string;
  badge?: { label: string; cls: string } | null;
  tag?: string;
  detail: string;
  ctaLabel?: string | null;
  ctaHref?: string | null;
}) {
  const checked = sel.picked.has(id);
  const body = (
    <div className="min-w-0 flex-1">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-medium">{title}</span>
        {badge ? <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold", badge.cls)}>{badge.label}</span> : null}
        {tag ? <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-foreground">{tag}</span> : null}
        {queued ? (
          <span className="inline-flex items-center gap-1 rounded bg-cyan-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">
            <CheckCircle2 className="size-3" aria-hidden />
            Seans gündeminde
          </span>
        ) : null}
      </div>
      <p className="mt-0.5 text-[13px] leading-relaxed text-muted-foreground">{detail}</p>
      {ctaHref ? (
        <Link
          href={ctaHref}
          className="mt-1 inline-flex items-center gap-1 text-[13px] font-medium text-cyan-800 hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {ctaLabel ?? "Aç"}
          <ArrowRight className="size-3" aria-hidden />
        </Link>
      ) : null}
    </div>
  );
  if (queued) {
    return <li className="flex gap-3 rounded-lg border border-border px-3 py-2 text-sm opacity-80">{body}</li>;
  }
  return (
    <li>
      <label
        className={cn(
          "flex cursor-pointer gap-3 rounded-lg border px-3 py-2 text-sm transition-colors",
          checked ? "border-cyan-600 bg-cyan-500/5" : "border-border hover:bg-muted/40",
        )}
      >
        <input
          type="checkbox"
          checked={checked}
          onChange={() => sel.toggle(id, agenda)}
          className="mt-1 size-4 shrink-0 accent-cyan-700"
          aria-label={`${title} seans gündemine eklenecek`}
        />
        {body}
      </label>
    </li>
  );
}
