"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { ExamTrendTopics } from "@/components/shared/exam-trend-topics";
import { OvSection, RatioLegend, SplitBar, TopicHeatTable, fmtNum, pct, ratioClass } from "@/components/shared/exam-ov/ov-ui";

import { getExamTopicAnalysis } from "@/lib/api/exam-import";
import type { OvHeatRow } from "@/lib/api/exam-overview";
import type { ExamTopicAnalysisResponse } from "@/lib/types/exam-import";
import { cn } from "@/lib/utils";

/**
 * Deneme analizi · KONU ANALİZİ (2026-10-20 yeni tasarım).
 * PDF'ten aktarılan denemelerin soru satırları: özet şerit · ders ders tablo ·
 * net fırsatı tablosu · unutulan / gelişen (kanıtlı) · tam konu × deneme ısı haritası.
 * Koç (studentId), öğrenci (null) ve veli (parentStudentId) aynı bileşeni kullanır.
 * Salt-okuma; kredi düşmez.
 */

const OPP_STEP = 10;
const HEAT_STEP = 20;

function dayMonth(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  const months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
  return m && d ? `${d} ${months[m - 1]}` : iso;
}

export function ExamTopicAnalysis({
  studentId = null,
  parentStudentId = null,
  section,
  period,
}: {
  /** Veli yüzeyi: çocuğun id'si (salt okuma). */
  parentStudentId?: number | null;
  /** Koç yüzeyi: öğrenci id; öğrenci yüzeyi: null (kendi verisi). */
  studentId?: number | null;
  /** Panelin seçili sınav serisi (tek seriye filtreli analiz). */
  section: string | null;
  /** Panelin dönem seçimi. Yoksa güncel dönem. */
  period?: string;
}) {
  const q = useQuery<ExamTopicAnalysisResponse>({
    queryKey:
      parentStudentId != null
        ? ["parent", "students", String(parentStudentId), "topic-analysis", section ?? "auto", period ?? "current"]
        : studentId != null
          ? ["teacher", "me", "students", String(studentId), "exams", "topic-analysis", section ?? "auto", period ?? "current"]
          : ["student", "exams", "topic-analysis", section ?? "auto", period ?? "current"],
    queryFn: () => getExamTopicAnalysis(studentId, section, parentStudentId, period),
    staleTime: 30_000,
  });
  const [subj, setSubj] = React.useState<string>("");
  const [oppLimit, setOppLimit] = React.useState(OPP_STEP);
  const [heatLimit, setHeatLimit] = React.useState(HEAT_STEP);
  const [heatSort, setHeatSort] = React.useState<"total" | "weak">("total");

  const d = q.data;
  if (q.isLoading) return <div className="h-64 animate-pulse rounded-2xl bg-muted" aria-label="Yükleniyor" />;
  if (!d) return null;

  if (d.series_missing || d.exams.length === 0) {
    return (
      <OvSection eyebrow="KONU ANALİZİ" title="Bu seride konu analizi yok">
        <p className="text-sm leading-relaxed text-muted-foreground">
          {d.series_missing
            ? "Seçili seride PDF'ten aktarılmış (soru soru okunmuş) deneme yok. "
            : "Bu dönemde konu analizine girecek deneme yok. "}
          Konu analizi yalnız PDF&apos;ten aktarılan denemelerden hesaplanır; elle girilen denemelerde soru bilgisi
          olmadığı için buraya girmez.
        </p>
      </OvSection>
    );
  }

  const subjectsAll = [...new Set(d.topics.map((t) => t.subject_name))];
  const activeSubj = subjectsAll.includes(subj) ? subj : "";
  const bySubj = <T extends { subject_name: string }>(arr: T[]) =>
    activeSubj ? arr.filter((x) => x.subject_name === activeSubj) : arr;

  const topics = bySubj(d.topics);
  const oppsAll = bySubj(d.opportunities);
  const opps = oppsAll.slice(0, oppLimit);
  const forgotten = bySubj(d.forgotten);
  const improved = bySubj(d.improved);
  const oppSum = oppsAll.reduce((a, o) => a + o.net_gain_per_exam, 0);
  const maxGain = oppsAll[0]?.net_gain_per_exam ?? 0;
  const weakCount = topics.filter((t) => t.total >= 2 && t.accuracy < 0.5).length;
  const qCount = topics.reduce((a, t) => a + t.total, 0);

  // Ders ders özet (tüm dersler; süzgeçten bağımsız — satıra tıklayınca süzer)
  const bySubject = subjectsAll
    .map((name) => {
      const ts = d.topics.filter((t) => t.subject_name === name);
      const total = ts.reduce((a, t) => a + t.total, 0);
      const correct = ts.reduce((a, t) => a + t.correct, 0);
      const wrong = ts.reduce((a, t) => a + t.wrong, 0);
      const blank = ts.reduce((a, t) => a + t.blank, 0);
      const gain = d.opportunities.filter((o) => o.subject_name === name).reduce((a, o) => a + o.net_gain_per_exam, 0);
      const weakest = [...ts].filter((t) => t.total >= 2).sort((a, z) => a.accuracy - z.accuracy)[0];
      return { name, topics: ts.length, total, correct, wrong, blank, acc: total ? correct / total : null, gain, weakest };
    })
    .sort((a, z) => z.gain - a.gain);

  // Isı haritası satırları (sütunlar = denemeler, kronolojik)
  const examIdx = new Map(d.exams.map((e, i) => [e.id, i]));
  const heatSorted = [...topics].sort((a, z) =>
    heatSort === "weak" ? a.accuracy - z.accuracy || z.total - a.total : z.total - a.total || a.accuracy - z.accuracy,
  );
  const heatRows: OvHeatRow[] = heatSorted.slice(0, heatLimit).map((t) => {
    const cells: OvHeatRow["cells"] = d.exams.map(() => null);
    for (const c of t.cells) {
      const i = examIdx.get(c.exam_id);
      if (i !== undefined) cells[i] = { correct: c.correct, total: c.total, accuracy: c.accuracy };
    }
    return { topic_id: t.topic_id, topic_name: t.topic_name, subject_name: t.subject_name, total: t.total, accuracy: t.accuracy, cells };
  });
  const labels = d.exams.map((e) => dayMonth(e.exam_date));

  return (
    <div className="flex flex-col gap-4" data-section="exam-topics-v2">
      <OvSection
        eyebrow="KONU ANALİZİ"
        title={`${d.section_label ?? "Seçili seri"} · ${d.exams.length} denemede ${d.analyzed_question_count} soru konu konu`}
        desc="Her soru karnedeki konusuyla müfredat konusuna bağlanır, konu konu toplanır. Elle girilen denemeler (soru bilgisi yok) bu analize girmez."
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Analiz edilen soru" value={String(activeSubj ? qCount : d.analyzed_question_count)} sub={activeSubj ? activeSubj : `${d.exams.length} deneme`} />
          <Stat label="Konu" value={String(topics.length)} sub="en az 1 soru gelen" />
          <Stat label="Zayıf konu" value={String(weakCount)} sub="doğruluk %50 altı · 2+ soru" tone="rose" />
          <Stat label="Toplam net fırsatı" value={`+${fmtNum(oppSum)}`} sub="deneme başına" tone="cyan" />
        </div>
        {subjectsAll.length > 1 ? (
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Ders süzgeci">
            {["", ...subjectsAll].map((sn) => (
              <button
                key={sn || "all"}
                type="button"
                onClick={() => {
                  setSubj(sn);
                  setOppLimit(OPP_STEP);
                  setHeatLimit(HEAT_STEP);
                }}
                aria-pressed={activeSubj === sn}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-semibold",
                  activeSubj === sn
                    ? "border-cyan-700 bg-cyan-700 text-white"
                    : "border-border bg-background text-foreground hover:bg-muted",
                )}
              >
                {sn || "Tüm dersler"}
              </button>
            ))}
          </div>
        ) : null}
      </OvSection>

      {!activeSubj && bySubject.length > 1 ? (
        <OvSection eyebrow="DERS DERS" title="Hangi derste ne kadar net kaçıyor?" desc="Satıra tıklayınca analiz o derse süzülür." right={<RatioLegend />}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted-foreground">
                  <th scope="col" className="py-2 pr-2 text-left font-semibold">Ders</th>
                  <th scope="col" className="py-2 pr-2 text-right font-semibold">Soru</th>
                  <th scope="col" className="py-2 pr-2 text-center font-semibold">Doğruluk</th>
                  <th scope="col" className="w-40 py-2 pr-2 text-left font-semibold">D · Y · B</th>
                  <th scope="col" className="py-2 pr-2 text-left font-semibold">En zayıf konu</th>
                  <th scope="col" className="py-2 text-right font-semibold">Net fırsatı</th>
                </tr>
              </thead>
              <tbody>
                {bySubject.map((s) => (
                  <tr
                    key={s.name}
                    className="cursor-pointer border-b border-border last:border-0 hover:bg-muted/50"
                    onClick={() => setSubj(s.name)}
                  >
                    <th scope="row" className="py-2 pr-2 text-left font-semibold">
                      <button type="button" className="text-left hover:underline" onClick={() => setSubj(s.name)}>
                        {s.name}
                      </button>
                      <span className="block text-[11px] font-normal text-muted-foreground">{s.topics} konu</span>
                    </th>
                    <td className="py-2 pr-2 text-right tabular-nums">{s.total}</td>
                    <td className="py-2 pr-2 text-center">
                      <span className={cn("inline-block min-w-12 rounded-md px-1.5 py-0.5 text-xs font-bold tabular-nums", ratioClass(s.acc))}>
                        {pct(s.acc)}
                      </span>
                    </td>
                    <td className="py-2 pr-2">
                      <SplitBar
                        parts={[
                          { value: s.correct, className: "bg-emerald-500", label: `${s.correct} doğru` },
                          { value: s.wrong, className: "bg-rose-600", label: `${s.wrong} yanlış` },
                          { value: s.blank, className: "bg-slate-400", label: `${s.blank} boş` },
                        ]}
                      />
                      <div className="mt-1 text-[11px] tabular-nums text-muted-foreground">
                        {s.correct}D · {s.wrong}Y · {s.blank}B
                      </div>
                    </td>
                    <td className="py-2 pr-2 text-[13px] leading-snug">
                      {s.weakest ? (
                        <>
                          {s.weakest.topic_name}{" "}
                          <span className="text-muted-foreground">
                            ({s.weakest.correct}/{s.weakest.total})
                          </span>
                        </>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="py-2 text-right font-bold tabular-nums text-rose-700 dark:text-rose-300">
                      {s.gain > 0 ? `+${fmtNum(s.gain)}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </OvSection>
      ) : null}

      <OvSection
        eyebrow="NET FIRSATI"
        tone="rose"
        title={oppsAll.length ? `Bu konular kapanırsa deneme başına +${fmtNum(oppSum)} net` : "Net fırsatı yok"}
        desc={
          oppsAll.length
            ? "Yanlış ve boşlar doğru olsaydı deneme başına kazanılacak net (yanlış, cezasıyla birlikte). En büyük fırsat en üstte — programda öncelik bu konulara verilir."
            : `${activeSubj || "Bu seri"} için en az 2 soru gelen konularda yanlış ya da boş yok.`
        }
      >
        {oppsAll.length ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground">
                    <th scope="col" className="w-8 py-2 pr-2 text-left font-semibold">#</th>
                    <th scope="col" className="py-2 pr-2 text-left font-semibold">Konu</th>
                    <th scope="col" className="py-2 pr-2 text-right font-semibold">Soru</th>
                    <th scope="col" className="w-36 py-2 pr-2 text-left font-semibold">Yanlış · boş</th>
                    <th scope="col" className="py-2 pr-2 text-center font-semibold">Doğruluk</th>
                    <th scope="col" className="py-2 text-right font-semibold">Deneme başına</th>
                  </tr>
                </thead>
                <tbody>
                  {opps.map((o, i) => (
                    <tr key={o.topic_id} className="border-b border-border last:border-0">
                      <td className="py-2 pr-2 tabular-nums text-muted-foreground">{i + 1}</td>
                      <th scope="row" className="py-2 pr-2 text-left font-semibold leading-snug">
                        {o.topic_name}
                        <span className="block text-[11px] font-normal text-muted-foreground">{o.subject_name}</span>
                      </th>
                      <td className="py-2 pr-2 text-right tabular-nums">{o.total}</td>
                      <td className="py-2 pr-2">
                        <SplitBar
                          parts={[
                            { value: o.wrong, className: "bg-rose-600", label: `${o.wrong} yanlış` },
                            { value: o.blank, className: "bg-slate-400", label: `${o.blank} boş` },
                          ]}
                        />
                        <div className="mt-1 text-[11px] tabular-nums text-muted-foreground">
                          {o.wrong} yanlış · {o.blank} boş
                        </div>
                      </td>
                      <td className="py-2 pr-2 text-center">
                        <span className={cn("inline-block min-w-12 rounded-md px-1.5 py-0.5 text-xs font-bold tabular-nums", ratioClass(o.accuracy))}>
                          {pct(o.accuracy)}
                        </span>
                      </td>
                      <td className="py-2">
                        <div className="flex items-center justify-end gap-2">
                          <div className="hidden h-2 w-20 overflow-hidden rounded-full bg-muted sm:block">
                            <div
                              className="h-full bg-rose-500"
                              style={{ width: `${maxGain ? Math.max((100 * o.net_gain_per_exam) / maxGain, 6) : 0}%` }}
                            />
                          </div>
                          <b className="tabular-nums text-rose-700 dark:text-rose-300">+{fmtNum(o.net_gain_per_exam)}</b>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {oppsAll.length > OPP_STEP ? (
              <ShowMore
                shown={opps.length}
                total={oppsAll.length}
                onMore={() => setOppLimit(oppsAll.length)}
                onLess={() => setOppLimit(OPP_STEP)}
                noun="konu"
              />
            ) : null}
          </>
        ) : null}
      </OvSection>

      {d.exams.length >= 2 ? (
        <>
          <ExamTrendTopics forgotten={forgotten} improved={improved} studentId={studentId} />
          {forgotten.length === 0 && improved.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-border px-4 py-3 text-xs leading-relaxed text-muted-foreground">
              {activeSubj ? <b className="text-foreground">{activeSubj} için </b> : null}
              belirgin unutulan ya da gelişen konu yok. Bir konunun işaretlenmesi için ilk ve son denemelerin her birinde o
              konudan en az 2 soru gelmesi ve doğruluğun en az 34 puan değişmesi gerekir.
            </p>
          ) : null}

          <OvSection
            eyebrow="KONU × DENEME"
            title="Konu konu, deneme deneme"
            desc="Her satır bir konu, her sütun bir deneme; hücrede o denemede o konudan gelen soruların kaçının doğru yapıldığı yazar. Satır boyunca açık kırmızı kalan konu kalıcı zayıflıktır."
            right={<RatioLegend />}
          >
            <div className="flex flex-wrap items-center gap-1.5 text-xs" role="group" aria-label="Sıralama">
              <span className="text-muted-foreground">Sırala:</span>
              {(
                [
                  ["total", "En çok soru gelen"],
                  ["weak", "En zayıf"],
                ] as const
              ).map(([k, l]) => (
                <button
                  key={k}
                  type="button"
                  aria-pressed={heatSort === k}
                  onClick={() => setHeatSort(k)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 font-semibold",
                    heatSort === k ? "border-cyan-700 bg-cyan-700 text-white" : "border-border bg-background hover:bg-muted",
                  )}
                >
                  {l}
                </button>
              ))}
            </div>
            <TopicHeatTable rows={heatRows} labels={labels} />
            {topics.length > HEAT_STEP ? (
              <ShowMore
                shown={heatRows.length}
                total={topics.length}
                onMore={() => setHeatLimit(topics.length)}
                onLess={() => setHeatLimit(HEAT_STEP)}
                noun="konu"
              />
            ) : null}
          </OvSection>
        </>
      ) : (
        <p className="rounded-2xl border border-dashed border-border px-4 py-3 text-xs leading-relaxed text-muted-foreground">
          Konu × deneme tablosu ile <b className="text-foreground">unutulan / gelişen konular</b>, bu seride en az{" "}
          <b className="text-foreground">2 deneme</b> aktarılınca görünür.
        </p>
      )}

      {d.unmatched_questions > 0 ? (
        <p className="rounded-xl bg-amber-100 px-3 py-2 text-xs text-amber-950 dark:bg-amber-500/15 dark:text-amber-100">
          {d.unmatched_questions} soru müfredat konusuna bağlanmadan kaydedilmiş; bu sorular konu analizine girmiyor.
          {studentId != null ? " Denemenin yanındaki “Satırları düzelt” ile bağlarsan analize girer." : ""}
        </p>
      ) : null}
    </div>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub: string; tone?: "rose" | "cyan" }) {
  return (
    <div
      className={cn(
        "rounded-xl px-3 py-2.5",
        tone === "rose" ? "bg-rose-50 dark:bg-rose-500/10" : tone === "cyan" ? "bg-cyan-50 dark:bg-cyan-500/10" : "bg-muted/60",
      )}
    >
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={cn(
          "text-xl font-extrabold tabular-nums",
          tone === "rose" ? "text-rose-700 dark:text-rose-300" : tone === "cyan" ? "text-cyan-800 dark:text-cyan-300" : "",
        )}
      >
        {value}
      </div>
      <div className="text-[11px] text-muted-foreground">{sub}</div>
    </div>
  );
}

function ShowMore({
  shown,
  total,
  onMore,
  onLess,
  noun,
}: {
  shown: number;
  total: number;
  onMore: () => void;
  onLess: () => void;
  noun: string;
}) {
  return (
    <button
      type="button"
      onClick={shown < total ? onMore : onLess}
      className="self-start rounded-full border border-border px-3 py-1 text-xs font-semibold hover:bg-muted"
    >
      {shown < total ? `Tümünü göster (${total} ${noun})` : "Daha az göster"}
    </button>
  );
}
