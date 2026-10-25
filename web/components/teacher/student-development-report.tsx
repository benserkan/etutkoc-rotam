"use client";

/**
 * Öğrenci Gelişim Raporu (360°) — Denemeler sekmesinin ilk alt sekmesi.
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
  Activity,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Compass,
  Flag,
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
  type DRCompare,
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

const DAY_STATE: Record<string, { cls: string; label: string }> = {
  done: { cls: "bg-emerald-600 text-white", label: "tamam" },
  partial: { cls: "bg-amber-500 text-amber-950", label: "kısmen" },
  missed: { cls: "bg-rose-600 text-white", label: "yapılmadı" },
  none: { cls: "bg-muted text-muted-foreground", label: "görev yok" },
  today: { cls: "bg-cyan-700 text-white", label: "bugün" },
  future: { cls: "border border-dashed border-border text-muted-foreground", label: "gelecek" },
};

const STATUS: Record<string, { label: string; cls: string }> = {
  above: { label: "Normalinden iyi", cls: "bg-emerald-700 text-white" },
  normal: { label: "Her zamanki", cls: "bg-slate-600 text-white" },
  below: { label: "Normalin altında", cls: "bg-amber-600 text-white" },
  critical: { label: "Geçmişin en kötüsü", cls: "bg-rose-700 text-white" },
  high: { label: "Normalden yüksek", cls: "bg-sky-700 text-white" },
  low: { label: "Normalden düşük", cls: "bg-sky-700 text-white" },
  insufficient: { label: "Veri az", cls: "bg-muted text-muted-foreground" },
  info: { label: "Bilgi", cls: "bg-muted text-muted-foreground" },
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
    return <p className="text-sm text-rose-700 dark:text-rose-400">Gelişim raporu yüklenemedi.</p>;
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

  return (
    <div className="space-y-4" data-section="dev-report">
      <Header d={d} fetching={q.isFetching} onRefresh={() => q.refetch()} />

      {d.this_week ? <ThisWeek d={d} /> : (
        <p className="rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground">
          Bu öğrencinin henüz program haftası yok; haftalık kıyas program verildikçe oluşur.
        </p>
      )}

      {d.weeks.length || d.exam.exams.length ? <WeeksSection d={d} /> : null}

      {d.journey ? <Journey d={d} /> : null}

      <div className="grid gap-3 lg:grid-cols-2">
        <FindingBox
          icon={Compass}
          title="Mevcut durum"
          desc="Ölçülen gerçekler: bu hafta, haftalar boyunca ve denemelerde neredesin."
          tone="info"
          items={d.state}
          sel={sel}
        />
        <FindingBox
          icon={Sparkles}
          title="Güçlü yanlar"
          desc="Öğrencinin kendi normalinin üstünde olduğu ya da yükselen alanlar."
          tone="good"
          items={d.strengths}
          sel={sel}
          empty="Şu an normalinin belirgin üstünde olduğu bir alan yok."
        />
        <FindingBox
          icon={TrendingUp}
          title="Fırsatlar"
          desc="Az emekle net ya da uyum kazandıracak noktalar."
          tone="info"
          items={d.opportunities}
          sel={sel}
          empty="Konu bazlı fırsat için soru satırlı (PDF karne) deneme gerekir."
        />
        <FindingBox
          icon={ShieldAlert}
          title="Riskler"
          desc="Normalin altına düşen, kötüleşen ya da ölçülemeyen alanlar."
          tone="warn"
          items={d.risks}
          sel={sel}
          empty="Belirgin bir risk yok."
        />
      </div>

      <ActionPlan actions={d.actions} sel={sel} />

      <div
        className={cn(
          "sticky bottom-3 z-20 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-cyan-700/40 bg-card px-4 py-2.5 shadow-lg",
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

// ---------------------------------------------------------------- başlık

function Header({ d, fetching, onRefresh }: { d: DRReport; fetching: boolean; onRefresh: () => void }) {
  const lvl = {
    risk: "border-rose-300 bg-rose-50 text-rose-950 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-100",
    watch: "border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100",
    good: "border-emerald-300 bg-emerald-50 text-emerald-950 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-100",
  }[d.headline.level];
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="flex items-center gap-2 text-base font-semibold">
            <Gauge className="size-5 text-cyan-700 dark:text-cyan-300" aria-hidden />
            Gelişim Raporu (360°)
          </h4>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Bu hafta, geçmiş haftalar ve denemeler birlikte. Rapor saklanmaz; her açılışta güncel veriden
            yeniden hesaplanır. Son hesaplama {ago(d.generated_at)} · son görev işaretleme{" "}
            {ago(d.activity.last_tick_at)} · son deneme kaydı {ago(d.activity.last_exam_at)}
            {d.queue_count ? ` · seans gündeminde ${d.queue_count} madde` : ""}.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={onRefresh} disabled={fetching}>
          <RefreshCw className={cn("size-4", fetching && "animate-spin")} aria-hidden />
          {fetching ? "Güncelleniyor…" : "Yenile"}
        </Button>
      </div>
      <p className={cn("rounded-lg border px-3 py-2 text-sm font-medium", lvl)} data-testid="dev-report-headline">
        {d.headline.text}
      </p>
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
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h5 className="flex items-center gap-2 text-sm font-semibold">
            <Icon className="size-4 text-cyan-700 dark:text-cyan-300" aria-hidden />
            {title}
          </h5>
          {desc ? <p className="mt-0.5 text-xs text-muted-foreground">{desc}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------- bu hafta

function ThisWeek({ d }: { d: DRReport }) {
  const tw = d.this_week!;
  const w = tw.week;
  return (
    <Section
      icon={Activity}
      title={w.ended ? `Son program haftası · ${w.label}` : `Bu hafta · ${w.label}`}
      desc={
        w.ended
          ? "Hafta tamamlandı; geçmiş haftalarla tam hafta olarak kıyaslanır."
          : `${w.day_index}/${w.days}. gün. Kıyas, geçmiş haftaların aynı gününe kadar yapılır (${w.compare_days} gün); bugün henüz sürdüğü için sayılmaz.`
      }
    >
      <div className="mb-4 grid grid-cols-7 gap-1.5">
        {tw.days.map((day) => {
          const s = DAY_STATE[day.state] ?? DAY_STATE.none;
          return (
            <div
              key={day.date}
              className={cn("rounded-lg px-1 py-1.5 text-center", s.cls)}
              title={
                day.missing.length
                  ? `Yapılmayan: ${day.missing.map((m) => m.title).join(", ")}`
                  : s.label
              }
            >
              <p className="text-[11px] font-semibold">{day.day}</p>
              <p className="text-sm font-bold tabular-nums">
                {day.total ? `${day.done}/${day.total}` : "—"}
              </p>
              <p className="text-[10px]">{s.label}</p>
            </div>
          );
        })}
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {tw.compare.map((c) => (
          <CompareCard key={c.key} c={c} />
        ))}
      </div>
    </Section>
  );
}

function CompareCard({ c }: { c: DRCompare }) {
  const st = STATUS[c.status] ?? STATUS.info;
  const showBand = c.low != null && c.high != null;
  return (
    <div className="rounded-lg border border-border p-3" title={c.hint}>
      <div className="flex flex-wrap items-center justify-between gap-1">
        <p className="text-xs font-medium text-muted-foreground">{c.name}</p>
        <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold", st.cls)}>{st.label}</span>
      </div>
      <p className="mt-1 text-xl font-semibold tabular-nums">{c.value_label}</p>
      <p className="text-[11px] text-muted-foreground">
        Geçen hafta {c.prev_label}
        {showBand ? ` · genelde ${Math.round(c.low!)}–${Math.round(c.high!)}${c.unit === "%" ? "%" : ` ${c.unit}`}` : ""}
      </p>
      <p className="mt-1 text-xs leading-relaxed">{c.verdict}</p>
    </div>
  );
}

// ---------------------------------------------------------------- haftalar

function WeeksSection({ d }: { d: DRReport }) {
  const rows = d.weeks;
  const chart = rows.map((w) => ({
    label: w.label,
    pct: w.gorev_pct,
    net: w.exam_nets.length ? Math.round((w.exam_nets.reduce((a, b) => a + b, 0) / w.exam_nets.length) * 100) / 100 : null,
    current: w.current,
    exams: w.exam_titles.join(", "),
  }));
  const hasNet = chart.some((c) => c.net != null);
  return (
    <Section
      icon={TrendingUp}
      title="Haftadan haftaya: görev uyumu ve deneme neti"
      desc={`Sınıf dönemindeki tüm program haftaları. Sütun = görev uyumu (yapılan ÷ verilen); nokta = o hafta girilen ${d.exam.section_label ?? "genel deneme"} neti. Koyu sütun bu hafta.`}
    >
      {rows.length ? (
        <div className="relative -mx-1 overflow-x-auto px-1">
          <div className="h-[240px]" style={{ minWidth: Math.max(420, rows.length * 46) }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chart} margin={{ top: 8, right: 8, bottom: 4, left: -8 }}>
                <CartesianGrid stroke="currentColor" strokeOpacity={0.08} vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }}
                  stroke="currentColor" strokeOpacity={0.15} interval={0} />
                <YAxis yAxisId="p" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]}
                  tickFormatter={(v: number) => `%${v}`} width={42}
                  tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }} stroke="currentColor" strokeOpacity={0.15} />
                {hasNet ? (
                  <YAxis yAxisId="n" orientation="right" width={36} domain={["auto", "auto"]}
                    tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }} stroke="currentColor" strokeOpacity={0.15} />
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
        <div className="relative mt-3 overflow-x-auto">
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
                <WeekRow key={w.start} w={w} prev={arr[i + 1] ?? null} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Section>
  );
}

function WeekRow({ w, prev }: { w: DRWeekRow; prev: DRWeekRow | null }) {
  const diff = w.gorev_pct != null && prev?.gorev_pct != null ? Math.round(w.gorev_pct - prev.gorev_pct) : null;
  return (
    <tr className={cn("border-b border-border/60 last:border-0", w.current && "bg-cyan-500/10 font-medium")}>
      <td className="py-1.5 pr-3">
        {w.label}
        {w.current ? <span className="ml-1.5 rounded bg-cyan-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">bu hafta</span> : null}
        {w.cut ? <span className="ml-1.5 text-[11px] text-muted-foreground">(kısa hafta)</span> : null}
      </td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{w.gorev_done}/{w.gorev_total}</td>
      <td className={cn("py-1.5 pr-3 text-right font-semibold tabular-nums",
        w.gorev_pct != null && w.gorev_pct >= 80 && "text-emerald-700 dark:text-emerald-400",
        w.gorev_pct != null && w.gorev_pct < 60 && "text-rose-700 dark:text-rose-400")}>
        {pct(w.gorev_pct)}
      </td>
      <td className={cn("py-1.5 pr-3 text-right tabular-nums",
        diff != null && diff >= 5 && "text-emerald-700 dark:text-emerald-400",
        diff != null && diff <= -5 && "text-rose-700 dark:text-rose-400")}>
        {diff == null ? "—" : `${diff > 0 ? "+" : ""}${diff}`}
      </td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{w.test_done}/{w.test_planned}</td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{pct(w.ontime_pct)}</td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{w.empty_days}</td>
      <td className="py-1.5 pr-3 text-right tabular-nums">
        {w.tests_done_items ? `${w.tests_with_result}/${w.tests_done_items}` : "—"}
      </td>
      <td className="py-1.5 text-right tabular-nums" title={w.exam_titles.join(", ")}>
        {w.exam_nets.length ? w.exam_nets.map((n) => fmtNet(n)).join(" · ") : "—"}
      </td>
    </tr>
  );
}

function WeekTip({ active, payload }: { active?: boolean; payload?: { payload: { label: string; pct: number | null; net: number | null; exams: string } }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow">
      <p className="font-semibold">{p.label}</p>
      <p>Görev uyumu {pct(p.pct)}</p>
      {p.net != null ? <p>Deneme neti {fmtNet(p.net)}{p.exams ? ` (${p.exams})` : ""}</p> : null}
    </div>
  );
}

// ---------------------------------------------------------------- gelinen nokta

function Journey({ d }: { d: DRReport }) {
  const j = d.journey!;
  const ex = j.exam;
  return (
    <Section
      icon={Flag}
      title="Gelişim döneminde gelinen nokta"
      desc={`İlk haftalar ile son haftalar ve ilk deneme ile son deneme karşılaştırması${j.first_week ? ` (ilk hafta ${j.first_week})` : ""}.`}
    >
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Program haftası" value={`${j.weeks} hafta`}
          sub={`toplam ${j.tests_total} test çözüldü${j.median_gorev_pct != null ? ` · ortanca uyum ${pct(j.median_gorev_pct)}` : ""}`} />
        <Stat label="Görev uyumu (ilk 3 → son 3 hafta)"
          value={`${pct(j.start_gorev_pct)} → ${pct(j.recent_gorev_pct)}`}
          sub={j.best_week ? `en iyi ${j.best_week.label} ${pct(j.best_week.value)}${j.worst_week ? ` · en düşük ${j.worst_week.label} ${pct(j.worst_week.value)}` : ""}` : undefined}
          tone={j.start_gorev_pct != null && j.recent_gorev_pct != null ? (j.recent_gorev_pct - j.start_gorev_pct >= 5 ? "good" : j.recent_gorev_pct - j.start_gorev_pct <= -5 ? "bad" : null) : null} />
        <Stat label="Haftalık test (ilk 3 → son 3 hafta)"
          value={`${j.start_tests_per_week == null ? "—" : Math.round(j.start_tests_per_week)} → ${j.recent_tests_per_week == null ? "—" : Math.round(j.recent_tests_per_week)}`}
          sub="test / hafta, deneme hariç" />
        <Stat label={`${j.exam_label ?? "Deneme"} neti`}
          value={ex ? `${fmtNet(ex.first_net)} → ${fmtNet(ex.last_net)}` : "—"}
          sub={ex ? `${ex.count} deneme · en iyi ${fmtNet(ex.best_net)}${ex.slope != null ? ` · deneme başına ${fmtSigned(ex.slope)}` : ""}${j.target?.gap != null ? ` · hedefe ${j.target.gap <= 0 ? "ulaştı" : `${fmtNet(j.target.gap)} net`}` : ""}` : "Henüz genel deneme yok"}
          tone={ex ? (ex.change >= 1 ? "good" : ex.change <= -1 ? "bad" : null) : null} />
      </div>
      {d.exam.subjects.length ? (
        <div className="relative mt-3 overflow-x-auto">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Ders</th>
                <th className="py-2 pr-3 text-right font-medium">İlk deneme</th>
                <th className="py-2 pr-3 text-right font-medium">Son deneme</th>
                <th className="py-2 pr-3 text-right font-medium">Değişim</th>
                <th className="py-2 text-right font-medium">Deneme başına eğim</th>
              </tr>
            </thead>
            <tbody>
              {d.exam.subjects.map((s) => (
                <tr key={s.name} className="border-b border-border/60 last:border-0">
                  <td className="py-1.5 pr-3">{s.name}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmtNet(s.first)}</td>
                  <td className="py-1.5 pr-3 text-right font-medium tabular-nums">{fmtNet(s.last)}</td>
                  <td className={cn("py-1.5 pr-3 text-right tabular-nums",
                    (s.change ?? 0) >= 1 && "text-emerald-700 dark:text-emerald-400",
                    (s.change ?? 0) <= -1 && "text-rose-700 dark:text-rose-400")}>
                    {s.change == null ? "—" : fmtSigned(s.change)}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{s.slope == null ? "—" : fmtSigned(s.slope)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {d.exam.exams.length ? (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Denemeler: {d.exam.exams.map((e) => `${fmtTRDate(e.exam_date)} ${fmtNet(e.net)}`).join(" · ")}
        </p>
      ) : null}
    </Section>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "bad" | null }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-lg font-semibold tabular-nums",
        tone === "good" && "text-emerald-700 dark:text-emerald-400",
        tone === "bad" && "text-rose-700 dark:text-rose-400")}>
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
    <section className={cn("rounded-xl border border-border border-t-4 bg-card p-4", BOX_TONE[tone])}>
      <h5 className="flex items-center gap-2 text-sm font-semibold">
        <Icon className="size-4" aria-hidden />
        {title}
        <span className="rounded-full bg-muted px-1.5 text-[11px] tabular-nums">{items.length}</span>
      </h5>
      <p className="mt-0.5 text-xs text-muted-foreground">{desc}</p>
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

function ActionPlan({ actions, sel }: { actions: DRAction[]; sel: Sel }) {
  const selectable = actions.filter((a) => !a.queued);
  const allPicked = selectable.length > 0 && selectable.every((a) => sel.picked.has(a.key));
  return (
    <Section
      icon={ListChecks}
      title="Aksiyon planı"
      desc="Haftalık programdan, denemelerden ve veri girişinden türetilen öneriler; öncelik sırasıyla. Seçtiklerini seans gündemine taşıyabilirsin (yukarıdaki bulgular da seçilebilir)."
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
          {actions.map((a) => (
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
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Şu an önerilen bir aksiyon yok.</p>
      )}
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
      <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{detail}</p>
      {ctaHref ? (
        <Link
          href={ctaHref}
          className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-cyan-700 hover:underline dark:text-cyan-300"
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
