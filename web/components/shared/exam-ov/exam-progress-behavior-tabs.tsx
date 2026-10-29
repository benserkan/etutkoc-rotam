"use client";

/**
 * Deneme analizi · NET GELİŞİMİ ve SINAV DAVRANIŞI sekmeleri (2026-10-20 yeni tasarım).
 * Veri Genel Bakış ile AYNI paketten (exam_overview) — üç sekmedeki sayılar ayrışamaz.
 */
import * as React from "react";

import { cn } from "@/lib/utils";
import type { ProgressSource } from "@/lib/api/exam-progress";
import type { ExamOverviewResponse, OvSubjectRow } from "@/lib/api/exam-overview";
import { useExamOverview } from "@/components/shared/exam-ov/exam-overview-tab";
import { OvSection, RatioLegend, SplitBar, SubjectMatrix, TrendChart, fmtNum, ratioClass } from "@/components/shared/exam-ov/ov-ui";

function Loading({ q }: { q: { isLoading: boolean; isError: boolean } }) {
  if (q.isLoading) return <div className="h-64 animate-pulse rounded-2xl bg-muted" aria-label="Yükleniyor" />;
  return <p className="rounded-2xl border border-border bg-card p-4 text-sm text-muted-foreground">Yüklenemedi.</p>;
}

// ---------------------------------------------------------------- NET GELİŞİMİ

export function ExamProgressTab({ source, series, period }: { source: ProgressSource; series: string | null; period?: string }) {
  const q = useExamOverview(source, series, period);
  if (!q.data) return <Loading q={q} />;
  const d = q.data;
  if (!d.trend) return null;
  const t = d.trend;
  if (t.points.length < 2) {
    return (
      <OvSection eyebrow="NET GELİŞİMİ" title="İkinci denemeden sonra gelişim çizilir">
        <p className="text-sm text-muted-foreground">
          Bu seride şimdilik tek deneme var ({fmtNum(t.last_net)} net). Yeni deneme ekledikçe gidişat, deneme deneme
          tablo ve ders ders gelişim burada oluşur.
        </p>
      </OvSection>
    );
  }
  const labels = t.points.map((p) => p.label);
  return (
    <div className="flex flex-col gap-4" data-section="exam-progress-v2">
      <OvSection
        eyebrow="NET GELİŞİMİ"
        title={`${t.points.length} denemede ${fmtNum(t.first_net)} → ${fmtNum(t.last_net)} net`}
        desc="Noktanın üzerine gelince deneme adı ve D/Y/B. Gölgeli alan öğrencinin normal aralığı (denemelerinin ortadaki yarısı); turuncu nokta normalin altında kalan deneme."
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Mini label="İlk" value={fmtNum(t.first_net)} />
          <Mini label="Son" value={fmtNum(t.last_net)} />
          <Mini label="En iyi" value={fmtNum(t.best_net)} tone="good" />
          <Mini label="En düşük" value={fmtNum(t.worst_net)} />
          <Mini label="Ortalama" value={fmtNum(t.avg_net)} />
          <Mini label="Deneme başına" value={t.slope != null ? fmtNum(t.slope, { plus: true }) : "—"} tone="cyan" />
        </div>
        <TrendChart trend={t} height={280} />
      </OvSection>

      <OvSection eyebrow="DENEME DENEME" title="Her denemenin sonucu ve bir öncekine göre farkı">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground">
                <th scope="col" className="py-2 pr-2 text-left font-semibold">Tarih</th>
                <th scope="col" className="py-2 pr-2 text-left font-semibold">Deneme</th>
                <th scope="col" className="py-2 pr-2 text-right font-semibold">Net</th>
                <th scope="col" className="w-40 py-2 pr-2 text-left font-semibold">D · Y · B</th>
                <th scope="col" className="py-2 pr-2 text-right font-semibold">Fark</th>
                <th scope="col" className="py-2 text-left font-semibold">Konum</th>
              </tr>
            </thead>
            <tbody>
              {[...t.points].reverse().map((p, idx, arr) => {
                const prev = arr[idx + 1];
                const diff = prev ? p.net - prev.net : null;
                const pos =
                  t.band_low == null ? null : p.net < t.band_low ? "below" : t.band_high != null && p.net > t.band_high ? "above" : "within";
                return (
                  <tr key={p.id} className="border-b border-border last:border-0">
                    <td className="whitespace-nowrap py-2 pr-2 text-muted-foreground">{p.label}</td>
                    <td className="py-2 pr-2 font-medium leading-snug">{p.title}</td>
                    <td className="py-2 pr-2 text-right font-extrabold tabular-nums">{fmtNum(p.net)}</td>
                    <td className="py-2 pr-2">
                      <SplitBar
                        parts={[
                          { value: p.correct, className: "bg-emerald-500", label: `${p.correct} doğru` },
                          { value: p.wrong, className: "bg-rose-600", label: `${p.wrong} yanlış` },
                          { value: p.blank, className: "bg-slate-400", label: `${p.blank} boş` },
                        ]}
                      />
                      <div className="mt-1 text-[11px] tabular-nums text-muted-foreground">
                        {p.correct}D · {p.wrong}Y · {p.blank}B
                      </div>
                    </td>
                    <td
                      className={cn(
                        "py-2 pr-2 text-right font-bold tabular-nums",
                        diff == null ? "text-muted-foreground" : diff > 0 ? "text-emerald-700" : diff < 0 ? "text-rose-700" : "",
                      )}
                    >
                      {diff == null ? "—" : fmtNum(diff, { plus: true })}
                    </td>
                    <td className="py-2 text-[13px]">
                      {pos === "below" ? (
                        <span className="font-semibold text-orange-700">normalin altında</span>
                      ) : pos === "above" ? (
                        <span className="font-semibold text-emerald-700">normalin üstünde</span>
                      ) : pos === "within" ? (
                        <span className="text-muted-foreground">normal aralıkta</span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </OvSection>

      {d.subjects.length ? (
        <>
          <OvSection eyebrow="DERS DERS" title="Her dersin gidişatı" desc="Kartta son net / soru, ilk denemeye göre fark ve deneme deneme çizgi. Renk son denemedeki oranı gösterir.">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {d.subjects.map((s) => (
                <SubjectSpark key={s.name} s={s} />
              ))}
            </div>
          </OvSection>
          <OvSection eyebrow="DERS × DENEME" title="Tablo görünümü" right={<RatioLegend />}>
            <SubjectMatrix rows={d.subjects} labels={labels} />
          </OvSection>
        </>
      ) : null}
    </div>
  );
}

function Mini({ label, value, tone }: { label: string; value: string; tone?: "good" | "cyan" }) {
  return (
    <div className={cn("rounded-xl px-3 py-2", tone === "cyan" ? "bg-cyan-50" : "bg-muted/60")}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={cn(
          "text-lg font-extrabold tabular-nums",
          tone === "good" ? "text-emerald-700" : tone === "cyan" ? "text-cyan-800" : "",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function SubjectSpark({ s }: { s: OvSubjectRow }) {
  const cells = s.cells.map((c, i) => ({ c, i })).filter((x) => x.c);
  const last = cells[cells.length - 1]?.c ?? null;
  const W = 160;
  const H = 44;
  const max = s.questions || 1;
  const n = s.cells.length;
  const x = (i: number) => (n > 1 ? 4 + (i * (W - 8)) / (n - 1) : W / 2);
  const y = (v: number) => 4 + (1 - Math.max(0, v) / max) * (H - 8);
  const line = cells.map(({ c, i }) => `${x(i)},${y(c!.net)}`).join(" ");
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-xl border border-border p-3">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-bold leading-tight">{s.name}</span>
        {last ? (
          <span className={cn("shrink-0 rounded-md px-1.5 py-0.5 text-xs font-bold tabular-nums", ratioClass(last.ratio))}>
            {fmtNum(last.net)}/{last.questions}
          </span>
        ) : null}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={`${s.name} netleri: ${cells.map(({ c }) => fmtNum(c!.net)).join(", ")}`}>
        <polyline points={line} fill="none" className="stroke-cyan-700" strokeWidth={2} />
        {cells.map(({ c, i }) => (
          <circle key={i} cx={x(i)} cy={y(c!.net)} r={2.5} className="fill-cyan-700" />
        ))}
      </svg>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">ilk → son</span>
        <span
          className={cn(
            "font-bold tabular-nums",
            s.change == null ? "text-muted-foreground" : s.change > 0 ? "text-emerald-700" : s.change < 0 ? "text-rose-700" : "",
          )}
        >
          {s.change == null ? "—" : fmtNum(s.change, { plus: true })}
        </span>
      </div>
      {s.reading ? <p className="text-xs leading-snug text-muted-foreground">{s.reading}</p> : null}
    </div>
  );
}

// ---------------------------------------------------------------- SINAV DAVRANIŞI

const TENDENCY_TEXT: Record<string, { label: string; cls: string; hint: string }> = {
  riskli: {
    label: "Hep işaretliyor",
    cls: "bg-rose-100 text-rose-900",
    hint: "Bilmediği soruyu boş bırakmıyor; yanlışlar ceza ile net götürüyor.",
  },
  cekingen: {
    label: "Çekingen",
    cls: "bg-slate-200 text-slate-900",
    hint: "Çoğunu boş bırakıyor; konuya giremiyor ya da süre yetmiyor.",
  },
  dengeli: {
    label: "Dengeli",
    cls: "bg-muted text-foreground",
    hint: "Yanlış ve boş dengeli.",
  },
};

export function ExamBehaviorTab({ source, series, period }: { source: ProgressSource; series: string | null; period?: string }) {
  const q = useExamOverview(source, series, period);
  if (!q.data) return <Loading q={q} />;
  const d: ExamOverviewResponse = q.data;
  const b = d.behavior;
  if (!b || !d.last) return null;
  const pen = d.last.penalty;
  const cost = 1 + 1 / pen;
  const present = new Map(d.subjects.map((s) => [s.name, s.cells.filter(Boolean).length]));
  const rows = b.subjects.map((s) => {
    const n = present.get(s.name) || d.count || 1;
    return { ...s, perExam: (s.wrong * cost + s.blank) / n, n };
  });
  rows.sort((a, z) => z.perExam - a.perExam);
  const maxPer = Math.max(0.01, ...rows.map((r) => r.perExam));
  const totalPer = rows.reduce((a, r) => a + r.perExam, 0);

  return (
    <div className="flex flex-col gap-4" data-section="exam-behavior-v2">
      <OvSection
        eyebrow="SINAV DAVRANIŞI"
        tone="violet"
        title="Bilmediği soruda ne yapıyor, ne kadar net kaçıyor?"
        desc={
          <>
            Seçili serinin {d.count} denemesinin toplamı. Yanlış soru {fmtNum(cost)} net götürür (1 doğru +{" "}
            {pen === 3 ? "ceza; 3 yanlış 1 doğruyu götürür" : "ceza; 4 yanlış 1 doğruyu götürür"}), boş soru 1 net.
            Deneme başına toplam kaçan: <b>{fmtNum(totalPer)} net</b>.
          </>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground">
                <th scope="col" className="py-2 pr-2 text-left font-semibold">Ders</th>
                <th scope="col" className="py-2 pr-2 text-right font-semibold">Yanlış</th>
                <th scope="col" className="py-2 pr-2 text-right font-semibold">Boş</th>
                <th scope="col" className="w-48 py-2 pr-2 text-left font-semibold">Yanlış / boş payı</th>
                <th scope="col" className="py-2 pr-2 text-right font-semibold">Deneme başına kaçan</th>
                <th scope="col" className="py-2 text-left font-semibold">Eğilim</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name} className="border-b border-border last:border-0">
                  <th scope="row" className="py-2 pr-2 text-left font-semibold">
                    {r.name}
                    <span className="block text-[11px] font-normal text-muted-foreground">{r.n} denemede</span>
                  </th>
                  <td className="py-2 pr-2 text-right tabular-nums text-rose-700">{r.wrong}</td>
                  <td className="py-2 pr-2 text-right tabular-nums">{r.blank}</td>
                  <td className="py-2 pr-2">
                    <SplitBar
                      parts={[
                        { value: r.wrong, className: "bg-rose-600", label: `${r.wrong} yanlış` },
                        { value: r.blank, className: "bg-slate-400", label: `${r.blank} boş` },
                      ]}
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <div className="flex items-center justify-end gap-2">
                      <div className="hidden h-2 w-20 overflow-hidden rounded-full bg-muted sm:block">
                        <div className="h-full bg-violet-600" style={{ width: `${(100 * r.perExam) / maxPer}%` }} />
                      </div>
                      <b className="tabular-nums">{fmtNum(r.perExam)}</b>
                    </div>
                  </td>
                  <td className="py-2">
                    {r.tendency ? (
                      <span
                        className={cn("rounded-full px-2.5 py-1 text-xs font-semibold", TENDENCY_TEXT[r.tendency].cls)}
                        title={TENDENCY_TEXT[r.tendency].hint}
                      >
                        {TENDENCY_TEXT[r.tendency].label}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">az veri</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="grid gap-2 text-xs text-muted-foreground md:grid-cols-3">
          {Object.values(TENDENCY_TEXT).map((t) => (
            <li key={t.label}>
              <b className="text-foreground">{t.label}:</b> {t.hint}
            </li>
          ))}
        </ul>
      </OvSection>

      {b.series.length > 1 ? (
        <OvSection eyebrow="DENEMEDEN DENEMEYE" tone="violet" title="Yanlış ve boş sayısı" desc={b.reading ?? undefined}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-separate border-spacing-[3px] text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground">
                  <th scope="col" className="px-2 text-left font-semibold">Sayı</th>
                  {b.series.map((p, i) => (
                    <th key={p.date + i} scope="col" className="font-semibold">
                      {p.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(["wrong", "blank"] as const).map((k) => {
                  const vals = b.series.map((p) => p[k]);
                  const mx = Math.max(1, ...vals);
                  return (
                    <tr key={k}>
                      <th scope="row" className="px-2 text-left font-semibold">
                        {k === "wrong" ? "Yanlış" : "Boş"}
                      </th>
                      {vals.map((v, i) => (
                        <td key={i} className="h-10 min-w-[56px] rounded-md p-0 text-center align-bottom">
                          <div className="relative flex h-10 items-end justify-center overflow-hidden rounded-md bg-muted/50">
                            <div
                              className={cn("absolute inset-x-0 bottom-0", k === "wrong" ? "bg-rose-500/35" : "bg-slate-400/45")}
                              style={{ height: `${(100 * v) / mx}%` }}
                            />
                            <span className="relative pb-1.5 text-[13px] font-bold tabular-nums">{v}</span>
                          </div>
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </OvSection>
      ) : null}
    </div>
  );
}
