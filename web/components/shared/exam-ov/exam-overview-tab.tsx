"use client";

/**
 * Deneme analizi · GENEL BAKIŞ (2026-10-20 yeni tasarım; koç + öğrenci + veli).
 * Veri: GET …/exam-overview (app/services/exam_overview.py — tek merkez).
 * Sıra koç toplantısının soru sırası: son deneme → kaçan net → gidişat → ders × deneme →
 * net fırsatı / unutulan / gelişen → konu × deneme → davranış + puan → seans gündemi.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarPlus, Eye, Loader2, TrendingDown, TrendingUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ProgressSource } from "@/lib/api/exam-progress";
import { examOverviewKeys, getExamOverview, type ExamOverviewResponse } from "@/lib/api/exam-overview";
import { useAddAgendaItems } from "@/lib/hooks/use-exam-progress-mutations";
import type { ExamResultRow } from "@/lib/types/teacher";
import { ExamAveragesButton } from "@/components/teacher/exams/exam-averages-dialog";
import { ExamShareMenu, SubjectTable } from "@/components/teacher/exams/exam-analytics";
import {
  OvSection,
  RatioLegend,
  SplitBar,
  SubjectMatrix,
  TopicHeatTable,
  TrendChart,
  fmtNum,
  pct,
} from "@/components/shared/exam-ov/ov-ui";

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  const months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
  return `${Number(d)} ${months[Number(m) - 1]} ${y}`;
}

export function useExamOverview(src: ProgressSource, series: string | null, period?: string) {
  return useQuery<ExamOverviewResponse>({
    queryKey: examOverviewKeys.overview(src, series, period),
    queryFn: () => getExamOverview(src, series, period),
    staleTime: 30_000,
  });
}

export function ExamOverviewTab({
  source,
  series,
  period,
  rows,
  studentName,
  onOpenDetail,
}: {
  source: ProgressSource;
  series: string | null;
  period?: string;
  /** Seçili serinin satırları (yeniden eskiye) — paylaş/ders tablosu için */
  rows: ExamResultRow[];
  studentName?: string | null;
  onOpenDetail: (row: ExamResultRow) => void;
}) {
  const q = useExamOverview(source, series, period);
  if (q.isLoading) return <div className="h-72 animate-pulse rounded-2xl bg-muted" aria-label="Yükleniyor" />;
  if (q.isError || !q.data) {
    return <p className="rounded-2xl border border-border bg-card p-4 text-sm text-muted-foreground">Genel bakış yüklenemedi.</p>;
  }
  const d = q.data;
  if (!d.last || !d.trend) return null;
  const lastRow = rows.find((r) => r.id === d.last!.id) ?? rows[0] ?? null;
  const prevRow = lastRow ? rows[rows.indexOf(lastRow) + 1] ?? null : null;
  const coach = source.kind === "teacher";
  const labels = d.trend.points.map((p) => p.label);

  return (
    <div className="flex flex-col gap-4" data-section="exam-overview">
      <div className="grid gap-4 lg:grid-cols-2">
        <LastExamHero d={d} lastRow={lastRow} prevRow={prevRow} source={source} studentName={studentName} onOpenDetail={onOpenDetail} />
        <LossCard d={d} />
      </div>

      {lastRow && lastRow.subjects.length ? (
        <details className="group rounded-2xl border border-border bg-card" data-section="exam-overview:last-table">
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 text-sm font-semibold">
            <span>
              Son deneme ders ders
              <span className="ml-2 font-normal text-muted-foreground">
                doğru · yanlış · boş · net{lastRow.averages ? " · genel ortalamayla fark" : ""} · önceki denemeye göre
              </span>
            </span>
            <span className="text-xs text-muted-foreground group-open:hidden">aç</span>
          </summary>
          <div className="flex flex-col gap-3 border-t border-border p-5">
            {coach ? (
              <div className="flex justify-end">
                <ExamAveragesButton row={lastRow} />
              </div>
            ) : null}
            <SubjectTable row={lastRow} prev={prevRow} />
          </div>
        </details>
      ) : null}

      <OvSection
        eyebrow="GİDİŞAT"
        title={
          d.trend.points.length > 1
            ? `${d.trend.points.length} denemede ${fmtNum(d.trend.first_net)} → ${fmtNum(d.trend.last_net)} net`
            : `İlk deneme: ${fmtNum(d.trend.last_net)} net`
        }
        dataSection="exam-overview:trend"
        right={
          <div className="flex flex-wrap gap-2">
            <Stat label="Deneme başına" value={d.trend.slope != null ? `${fmtNum(d.trend.slope, { plus: true })} net` : "—"} tone="cyan" />
            <Stat label="Ortalama" value={fmtNum(d.trend.avg_net)} />
            <Stat label="En iyi" value={fmtNum(d.trend.best_net)} />
            {d.trend.target != null ? <Stat label="Hedef" value={fmtNum(d.trend.target)} tone="violet" /> : null}
          </div>
        }
      >
        {d.trend.points.length > 1 ? (
          <TrendChart trend={d.trend} />
        ) : (
          <p className="text-sm text-muted-foreground">Gidişat ikinci denemeden sonra çizilir.</p>
        )}
        {d.trend.readings.length ? (
          <div className="grid gap-3 md:grid-cols-3">
            {d.trend.readings.map((r) => (
              <div
                key={r.title}
                className={cn(
                  "rounded-xl border p-3 text-sm leading-relaxed",
                  r.tone === "warn"
                    ? "border-orange-300 bg-orange-50 text-orange-950"
                    : r.tone === "good"
                      ? "border-emerald-300 bg-emerald-50 text-emerald-950"
                      : "border-border bg-muted/40",
                )}
              >
                <b>{r.title}</b> {r.text}
              </div>
            ))}
          </div>
        ) : null}
        {d.trend.band_low == null && d.trend.points.length > 1 ? (
          <p className="text-xs text-muted-foreground">Öğrencinin normal aralığı 4 denemeden sonra gösterilir.</p>
        ) : null}
      </OvSection>

      {d.subjects.length ? (
        <OvSection
          eyebrow="DERS DERS"
          title="Her ders, her denemede — tam puana göre"
          desc="Hücre = ders neti; renk = netin dersin soru sayısına oranı. Farklı soru sayılı dersler aynı ölçekte okunur. Hücrenin üzerine gelince D/Y/B."
          right={<RatioLegend />}
          dataSection="exam-overview:subjects"
        >
          <SubjectMatrix rows={d.subjects} labels={labels} />
        </OvSection>
      ) : null}

      {d.topics ? <TopicsBlock d={d} /> : null}

      <div className="grid gap-4 lg:grid-cols-3">
        {d.behavior && d.behavior.subjects.length ? <BehaviorCard d={d} /> : null}
        {d.behavior && d.behavior.series.length > 1 ? <WrongBlankCard d={d} /> : null}
        {d.score && d.score.scores.length ? <ScoreCard d={d} /> : null}
      </div>

      {coach && d.agenda.length ? <AgendaBlock d={d} studentId={source.studentId} /> : null}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "cyan" | "violet" }) {
  return (
    <div
      className={cn(
        "rounded-xl px-3.5 py-2",
        tone === "cyan" ? "bg-cyan-50" : tone === "violet" ? "bg-violet-50" : "bg-muted/60",
      )}
    >
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={cn(
          "text-lg font-extrabold tabular-nums",
          tone === "cyan" ? "text-cyan-800" : tone === "violet" ? "text-violet-800" : "",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function LastExamHero({
  d,
  lastRow,
  prevRow,
  source,
  studentName,
  onOpenDetail,
}: {
  d: ExamOverviewResponse;
  lastRow: ExamResultRow | null;
  prevRow: ExamResultRow | null;
  source: ProgressSource;
  studentName?: string | null;
  onOpenDetail: (row: ExamResultRow) => void;
}) {
  const L = d.last!;
  const total = L.correct + L.wrong + L.blank || 1;
  const karne = L.karne_score ?? lastRow?.score?.score ?? null;
  const rank = lastRow?.score?.rank_overall ?? null;
  const participants = lastRow?.score?.participants ?? null;
  return (
    <section
      data-section="exam-overview:last"
      className="flex min-w-0 flex-col gap-4 rounded-2xl bg-slate-900 p-5 text-white sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-bold tracking-wider text-cyan-300">SON DENEME · {fmtDate(L.date).toLocaleUpperCase("tr-TR")}</div>
          <div className="mt-1 text-[15px] font-semibold leading-snug">{L.title}</div>
        </div>
        {L.is_record ? <span className="rounded-full bg-emerald-400 px-2.5 py-1 text-xs font-extrabold text-emerald-950">Kişisel rekor</span> : null}
      </div>
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="text-6xl font-extrabold leading-none tracking-tight tabular-nums">{fmtNum(L.net)}</span>
        <span className="text-base text-slate-300">net / {L.questions} soru</span>
      </div>
      <div className="flex flex-wrap gap-2 text-sm">
        {L.delta != null ? (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 font-bold",
              L.delta >= 0 ? "bg-emerald-400/15 text-emerald-300" : "bg-rose-400/15 text-rose-300",
            )}
          >
            {L.delta >= 0 ? <TrendingUp className="size-4" aria-hidden /> : <TrendingDown className="size-4" aria-hidden />}
            {fmtNum(L.delta, { plus: true })} önceki denemeye göre
          </span>
        ) : (
          <span className="rounded-lg bg-white/10 px-2.5 py-1.5 text-slate-200">Bu serinin ilk denemesi</span>
        )}
        {d.count >= 3 ? <span className="rounded-lg bg-white/10 px-2.5 py-1.5 text-slate-200">Son 3 ortalaması {fmtNum(L.avg_last3)}</span> : null}
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex h-3 overflow-hidden rounded-full">
          <div className="bg-emerald-400" style={{ width: `${(100 * L.correct) / total}%` }} />
          <div className="bg-rose-400" style={{ width: `${(100 * L.wrong) / total}%` }} />
          <div className="bg-slate-500" style={{ width: `${(100 * L.blank) / total}%` }} />
        </div>
        <div className="flex gap-4 text-[13px] text-slate-300">
          <span><b className="text-emerald-300">{L.correct}</b> doğru</span>
          <span><b className="text-rose-300">{L.wrong}</b> yanlış</span>
          <span><b className="text-white">{L.blank}</b> boş</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 border-t border-white/10 pt-3 sm:grid-cols-3">
        <div>
          <div className="text-xs text-slate-400">Karnedeki puan</div>
          <div className="text-lg font-extrabold tabular-nums">{karne != null ? fmtNum(karne) : "—"}</div>
        </div>
        <div>
          <div className="text-xs text-slate-400">Tahminimiz</div>
          <div className="text-lg font-extrabold tabular-nums">{L.estimate != null ? fmtNum(L.estimate) : "—"}</div>
          {L.calibration_mae != null ? <div className="text-[11px] text-slate-400">karnelere ort. ±{fmtNum(L.calibration_mae, { digits: 1 })}</div> : null}
        </div>
        <div>
          <div className="text-xs text-slate-400">Sıralama</div>
          <div className="text-lg font-extrabold tabular-nums">{rank ? rank.toLocaleString("tr-TR") : "—"}</div>
          {participants ? <div className="text-[11px] text-slate-400">{participants.toLocaleString("tr-TR")} katılımcı</div> : null}
        </div>
      </div>
      {lastRow ? (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => onOpenDetail(lastRow)} className="bg-cyan-600 text-white hover:bg-cyan-700">
            <Eye className="size-4" aria-hidden /> Deneme detayı
          </Button>
          {source.kind === "teacher" ? (
            <div className="[&_button]:border-white/20 [&_button]:bg-white/5 [&_button]:text-white [&_button:hover]:bg-white/15 [&_button:hover]:text-white">
              <ExamShareMenu row={lastRow} prev={prevRow} studentId={source.studentId} studentName={studentName} />
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function LossCard({ d }: { d: ExamOverviewResponse }) {
  const loss = d.loss;
  if (!loss) return null;
  const rows = [...loss.subjects];
  const max = Math.max(...rows.map((r) => r.lost), loss.others?.lost ?? 0, 0.01);
  const penaltyText = d.last!.penalty === 3 ? "3 yanlış 1 doğruyu götürür" : "4 yanlış 1 doğruyu götürür";
  return (
    <OvSection
      eyebrow="KAÇAN NET"
      tone="rose"
      title={`${fmtNum(loss.total)} net nerede kaldı?`}
      desc={`Tam puana göre kayıp. Yanlış soru ${fmtNum(loss.wrong_cost)} net götürür (1 doğru + ceza; ${penaltyText}), boş soru 1 net.`}
      dataSection="exam-overview:loss"
    >
      {loss.total > 0 ? (
        <>
          <SplitBar
            className="h-3.5"
            parts={[
              { value: loss.from_wrong, className: "bg-rose-600" },
              { value: loss.from_blank, className: "bg-slate-400" },
            ]}
          />
          <div className="flex flex-wrap gap-4 text-[13px]">
            <span><b className="text-rose-700">{fmtNum(loss.from_wrong)}</b> yanlıştan ({d.last!.wrong} soru)</span>
            <span><b>{fmtNum(loss.from_blank)}</b> boştan ({d.last!.blank} soru)</span>
          </div>
          <ul className="flex flex-col gap-2">
            {rows.map((r) => (
              <li key={r.name} className="grid grid-cols-[minmax(0,8rem)_1fr_3.5rem] items-center gap-3 text-sm">
                <span className="font-semibold leading-tight">{r.name}</span>
                <div className="flex h-2.5 overflow-hidden rounded-full bg-muted" title={`${r.wrong} yanlış · ${r.blank} boş`}>
                  <div className="bg-rose-600" style={{ width: `${(100 * r.lost_wrong) / max}%` }} />
                  <div className="bg-slate-400" style={{ width: `${(100 * r.lost_blank) / max}%` }} />
                </div>
                <span className="text-right font-bold tabular-nums">{fmtNum(r.lost)}</span>
              </li>
            ))}
            {loss.others ? (
              <li className="grid grid-cols-[minmax(0,8rem)_1fr_3.5rem] items-center gap-3 text-sm text-muted-foreground">
                <span>Diğer {loss.others.count} ders</span>
                <div className="flex h-2.5 overflow-hidden rounded-full bg-muted">
                  <div className="bg-rose-300" style={{ width: `${(100 * loss.others.lost_wrong) / max}%` }} />
                  <div className="bg-slate-300" style={{ width: `${(100 * loss.others.lost_blank) / max}%` }} />
                </div>
                <span className="text-right font-bold tabular-nums">{fmtNum(loss.others.lost)}</span>
              </li>
            ) : null}
          </ul>
          {loss.note ? (
            <p className="rounded-xl bg-rose-50 px-3 py-2.5 text-[13px] text-rose-950">{loss.note}</p>
          ) : null}
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Kayıp yok — tam net.</p>
      )}
    </OvSection>
  );
}

function TopicsBlock({ d }: { d: ExamOverviewResponse }) {
  const t = d.topics!;
  const labels = t.exams.map((e) => e.label);
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-2">
        <OvSection
          eyebrow="NET FIRSATI"
          tone="emerald"
          title={
            t.opportunities.length
              ? `Bu ${t.opportunities.length} konu kapanırsa deneme başına ${fmtNum(t.opportunities_sum, { plus: true })} net`
              : "Belirgin net fırsatı yok"
          }
          desc={`Son ${t.pdf_exams} karnedeki yanlış ve boşlardan; deneme başına kazanç. Tamamı (${t.opportunities_total} konu) Konu Analizi sekmesinde.`}
          dataSection="exam-overview:opportunities"
        >
          <ul className="flex flex-col gap-3">
            {t.opportunities.map((o) => {
              const max = t.opportunities[0]?.net_gain_per_exam || 1;
              return (
                <li key={o.topic_id} className="grid grid-cols-[1fr_6rem_3.5rem] items-center gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold leading-snug">{o.topic_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {o.subject_name} · {o.wrong ? `${o.wrong} yanlış` : ""}
                      {o.wrong && o.blank ? " · " : ""}
                      {o.blank ? `${o.blank} boş` : ""} / {o.total} soru
                    </div>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                    <div className="h-full bg-emerald-500" style={{ width: `${(100 * o.net_gain_per_exam) / max}%` }} />
                  </div>
                  <div className="text-right font-extrabold tabular-nums text-emerald-700">
                    {fmtNum(o.net_gain_per_exam, { plus: true })}
                  </div>
                </li>
              );
            })}
          </ul>
        </OvSection>
        <div className="flex flex-col gap-4">
          <TrendTopicCard
            title="Eskiden yapıyordu, son denemelerde kaçırıyor"
            eyebrow="UNUTULUYOR"
            tone="orange"
            items={t.forgotten}
            empty="Unutulma işareti yok."
          />
          <TrendTopicCard
            title="Çalışmanın karşılığı görünen konular"
            eyebrow="GELİŞİYOR"
            tone="emerald"
            items={t.improved}
            empty="Henüz belirgin gelişen konu yok."
          />
        </div>
      </div>
      {t.heatmap.length ? (
        <OvSection
          eyebrow="KONU × DENEME"
          title={`En çok soru gelen ${t.heatmap.length} konu`}
          desc="Hücre = doğru / soru. Soldan sağa kızaran satır unutmayı, yeşillenen satır gelişmeyi gösterir. Tire = o denemede sorulmadı."
          right={<RatioLegend />}
          dataSection="exam-overview:heat"
        >
          <TopicHeatTable rows={t.heatmap} labels={labels} />
          <p className="text-xs text-muted-foreground">
            {t.analyzed} sorunun {t.analyzed - t.unmatched} tanesi müfredat konusuna bağlı
            {t.unmatched ? ` · ${t.unmatched} soru eşleşmedi (deneme satırlarından düzeltilebilir)` : ""}.
          </p>
        </OvSection>
      ) : null}
    </>
  );
}

function TrendTopicCard({
  title,
  eyebrow,
  tone,
  items,
  empty,
}: {
  title: string;
  eyebrow: string;
  tone: "orange" | "emerald";
  items: { topic_id: number; topic_name: string; subject_name: string; first_accuracy: number; last_accuracy: number }[];
  empty: string;
}) {
  return (
    <OvSection
      eyebrow={eyebrow}
      tone={tone}
      title={title}
      className={tone === "orange" ? "border-orange-300" : "border-emerald-300"}
    >
      {items.length ? (
        <ul className="flex flex-col gap-2 text-sm">
          {items.map((it) => (
            <li key={it.topic_id} className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="min-w-0">
                <b>{it.topic_name}</b> <span className="text-muted-foreground">· {it.subject_name}</span>
              </span>
              <span
                className={cn(
                  "font-bold tabular-nums",
                  tone === "orange" ? "text-orange-700" : "text-emerald-700",
                )}
              >
                {pct(it.first_accuracy)} → {pct(it.last_accuracy)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{empty}</p>
      )}
      <p className="text-xs text-muted-foreground">İlk yarı ↔ son yarı denemeler; her yarıda en az 2 soru. Kanıt Konu Analizi sekmesinde soru soru.</p>
    </OvSection>
  );
}

const TENDENCY: Record<string, { label: string; cls: string }> = {
  riskli: { label: "hep işaretliyor", cls: "text-rose-700" },
  cekingen: { label: "çekingen", cls: "text-slate-600" },
  dengeli: { label: "dengeli", cls: "text-foreground" },
};

function BehaviorCard({ d }: { d: ExamOverviewResponse }) {
  const b = d.behavior!;
  return (
    <OvSection eyebrow="SINAV DAVRANIŞI" tone="violet" title="Bilmediği soruda ne yapıyor?" dataSection="exam-overview:behavior">
      <ul className="flex flex-col gap-2.5">
        {b.subjects.slice(0, 6).map((s) => (
          <li key={s.name} className="grid grid-cols-[6.5rem_1fr_6.5rem] items-center gap-2.5 text-sm">
            <b className="leading-tight">{s.name}</b>
            <SplitBar
              parts={[
                { value: s.wrong, className: "bg-rose-600", label: `${s.wrong} yanlış` },
                { value: s.blank, className: "bg-slate-400", label: `${s.blank} boş` },
              ]}
            />
            <span className={cn("text-right text-[13px] font-semibold", TENDENCY[s.tendency ?? ""]?.cls ?? "text-muted-foreground")}>
              {s.tendency ? TENDENCY[s.tendency].label : `${s.wrong}Y ${s.blank}B`}
            </span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-rose-600" />yanlış</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-slate-400" />boş</span>
        <span>{d.count} denemenin toplamı</span>
      </div>
    </OvSection>
  );
}

function WrongBlankCard({ d }: { d: ExamOverviewResponse }) {
  const s = d.behavior!.series;
  const W = 360;
  const H = 140;
  const max = Math.max(1, ...s.map((x) => Math.max(x.wrong, x.blank)));
  const x = (i: number) => 24 + (i * (W - 48)) / Math.max(1, s.length - 1);
  const y = (v: number) => 14 + (1 - v / max) * (H - 40);
  const line = (k: "wrong" | "blank") => s.map((p, i) => `${x(i)},${y(p[k])}`).join(" ");
  return (
    <OvSection eyebrow="BOŞ ve YANLIŞ" tone="violet" title="Denemeden denemeye">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label={`Yanlış: ${s.map((p) => p.wrong).join(", ")}; boş: ${s.map((p) => p.blank).join(", ")}`}
      >
        <line x1={24} x2={W - 24} y1={H - 26} y2={H - 26} className="stroke-border" />
        <polyline points={line("wrong")} fill="none" className="stroke-rose-600" strokeWidth={3} />
        <polyline points={line("blank")} fill="none" className="stroke-slate-500" strokeWidth={3} strokeDasharray="5 4" />
        {s.map((p, i) => (
          <g key={p.date + i}>
            <title>{`${p.label}: ${p.wrong} yanlış · ${p.blank} boş`}</title>
            <circle cx={x(i)} cy={y(p.wrong)} r={3.5} className="fill-rose-600" />
            <circle cx={x(i)} cy={y(p.blank)} r={3.5} className="fill-slate-500" />
          </g>
        ))}
        <text x={24} y={H - 8} className="fill-muted-foreground text-[11px]">{s[0].label}</text>
        <text x={W - 24} y={H - 8} textAnchor="end" className="fill-muted-foreground text-[11px]">{s[s.length - 1].label}</text>
      </svg>
      {d.behavior!.reading ? <p className="text-sm leading-relaxed">{d.behavior!.reading}</p> : null}
    </OvSection>
  );
}

function ScoreCard({ d }: { d: ExamOverviewResponse }) {
  const sc = d.score!;
  const main = sc.scores[0];
  return (
    <OvSection eyebrow="PUAN TAHMİNİ" title={`${main.label} ${fmtNum(main.score)}`} dataSection="exam-overview:score">
      <p className="text-[13px] text-muted-foreground">
        Son genel denemenin netleri ve resmi katsayılarla ham puan. Gerçek puan o yılın ortalamasına göre değişir
        {sc.kind === "yks" ? "; diploma notu (OBP) dahil değildir" : ""}.
      </p>
      {sc.scores.length > 1 ? (
        <ul className="flex flex-wrap gap-2 text-sm">
          {sc.scores.slice(1).map((s) => (
            <li key={s.key} className="rounded-lg bg-muted/60 px-2.5 py-1.5">
              {s.label} <b className="tabular-nums">{fmtNum(s.score)}</b>
            </li>
          ))}
        </ul>
      ) : null}
      {sc.calibration.length ? (
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-xs text-muted-foreground">
              <th scope="col" className="py-1 text-left font-medium">Deneme</th>
              <th scope="col" className="py-1 text-right font-medium">Karne</th>
              <th scope="col" className="py-1 text-right font-medium">Tahmin</th>
            </tr>
          </thead>
          <tbody>
            {sc.calibration.slice(0, 4).map((c) => (
              <tr key={c.exam_id} className="border-t border-border">
                <td className="py-1">{fmtDate(c.exam_date)}</td>
                <td className="py-1 text-right font-bold tabular-nums">{fmtNum(c.karne_score)}</td>
                <td className="py-1 text-right tabular-nums">{fmtNum(c.estimate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {sc.warnings.length ? (
        <ul className="flex flex-col gap-1 text-xs text-amber-900">
          {sc.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
    </OvSection>
  );
}

function AgendaBlock({ d, studentId }: { d: ExamOverviewResponse; studentId: number }) {
  const add = useAddAgendaItems(studentId);
  return (
    <section
      data-section="exam-overview:agenda"
      className="flex flex-col gap-4 rounded-2xl border border-cyan-300 bg-cyan-50 p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs font-bold tracking-wider text-cyan-800">SEANS İÇİN</div>
          <h3 className="mt-1 text-lg font-extrabold text-cyan-950 sm:text-xl">
            Bu denemelerden konuşulacak {d.agenda.length} şey
          </h3>
        </div>
        <Button
          className="bg-cyan-700 text-white hover:bg-cyan-800"
          disabled={add.isPending}
          onClick={() =>
            add.mutate(d.agenda.map((a) => ({ text: a.agenda.slice(0, 400), key: a.key, source: "exam" })))
          }
        >
          {add.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <CalendarPlus className="size-4" aria-hidden />}
          Hepsini seans gündemine ekle
        </Button>
      </div>
      <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {d.agenda.map((a, i) => (
          <li key={a.key} className="flex flex-col gap-1.5 rounded-xl bg-card p-4">
            <b className="text-sm leading-snug">
              {i + 1} · {a.title}
            </b>
            <span className="text-xs text-muted-foreground">{a.subject}</span>
            <span className="text-[13px] leading-relaxed">{a.text}</span>
            <Button
              size="sm"
              variant="outline"
              className="mt-auto self-start"
              disabled={add.isPending}
              onClick={() => add.mutate([{ text: a.agenda.slice(0, 400), key: a.key, source: "exam" }])}
            >
              Seansa ekle
            </Button>
          </li>
        ))}
      </ol>
    </section>
  );
}
