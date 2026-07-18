"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Target, TrendingDown, TrendingUp } from "lucide-react";

import { getExamTopicAnalysis } from "@/lib/api/exam-import";
import type {
  AnalysisOpportunity,
  AnalysisTrendTopic,
  ExamTopicAnalysisResponse,
} from "@/lib/types/exam-import";
import { cn } from "@/lib/utils";

/**
 * Konu × deneme analizi (Faz 2) — PDF'ten aktarılan denemelerin soru satırları:
 * net fırsat listesi (sıklık × hata = "+X net/deneme") + konu×deneme ısı
 * haritası + unutulan/gelişen konular. Koç (studentId) + öğrenci (Faz 2b)
 * aynı bileşeni kullanır. Salt-okuma; kredi düşmez.
 */

function fmtDayMonth(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  return m && d
    ? `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}`
    : iso;
}

function pct(v: number): string {
  return `%${Math.round(v * 100)}`;
}

// ısı haritası hücre tonu — purge-safe statik sınıflar, iki temada okunur
function cellTone(acc: number): string {
  if (acc >= 0.75) return "bg-emerald-500/85 text-white";
  if (acc >= 0.5) return "bg-emerald-300/70 text-emerald-950";
  if (acc > 0) return "bg-amber-300/75 text-amber-950";
  return "bg-rose-400/85 text-white";
}

export function ExamTopicAnalysis({
  studentId = null,
  section,
}: {
  /** Koç yüzeyi: öğrenci id; öğrenci yüzeyi: null (kendi verisi). */
  studentId?: number | null;
  /** Panelin seçili sınav türü (tek türe filtreli analiz). */
  section: string | null;
}) {
  const q = useQuery<ExamTopicAnalysisResponse>({
    queryKey:
      studentId != null
        ? ["teacher", "me", "students", String(studentId), "exams",
           "topic-analysis", section ?? "auto"]
        : ["student", "exams", "topic-analysis", section ?? "auto"],
    queryFn: () => getExamTopicAnalysis(studentId, section),
    staleTime: 30_000,
  });
  const d = q.data;
  if (!d || d.exams.length === 0) return null;

  const examById = new Map(d.exams.map((e, i) => [e.id, i]));
  const heatTopics = d.topics.slice(0, 14);
  const maxGain = d.opportunities[0]?.net_gain_per_exam ?? 0;

  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground">
          Konu Analizi{" "}
          <span className="font-normal text-muted-foreground">
            · {d.section_label} · {d.exams.length} deneme ·{" "}
            {d.analyzed_question_count} soru
          </span>
        </h4>
        <p className="text-[11px] text-muted-foreground">
          PDF&apos;ten aktarılan denemelerin soru satırlarından hesaplanır.
        </p>
      </div>

      {d.opportunities.length > 0 ? (
        <div>
          <h5 className="mb-1.5 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Target className="size-3.5 text-rose-600" aria-hidden />
            Net fırsatı — bu konular kapanırsa deneme başına kazanç
          </h5>
          <ul className="space-y-1">
            {d.opportunities.slice(0, 6).map((o: AnalysisOpportunity) => (
              <li key={o.topic_id} className="text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate">
                    <b className="text-foreground">{o.topic_name}</b>{" "}
                    <span className="text-muted-foreground">
                      · {o.subject_name}
                    </span>
                  </span>
                  <span className="shrink-0 font-semibold tabular-nums text-rose-700 dark:text-rose-300">
                    +{o.net_gain_per_exam} net/deneme
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded bg-muted">
                    <div
                      className="h-full rounded bg-rose-400 dark:bg-rose-500"
                      style={{
                        width: `${maxGain ? Math.max((o.net_gain_per_exam / maxGain) * 100, 6) : 0}%`,
                      }}
                    />
                  </div>
                  <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
                    {o.wrong}Y {o.blank}B / {o.total} soru · doğruluk {pct(o.accuracy)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {(d.forgotten.length > 0 || d.improved.length > 0) ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {d.forgotten.length > 0 ? (
            <div className="rounded-md border border-rose-200 bg-rose-50 px-2.5 py-2 dark:border-rose-500/30 dark:bg-rose-500/10">
              <h5 className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-rose-900 dark:text-rose-200">
                <TrendingDown className="size-3.5" aria-hidden />
                Unutulan konular (önce biliyordu, son denemelerde düştü)
              </h5>
              <ul className="space-y-0.5 text-[11px] text-rose-800 dark:text-rose-300">
                {d.forgotten.map((t: AnalysisTrendTopic) => (
                  <li key={t.topic_id}>
                    <b>{t.topic_name}</b> · {t.subject_name} —{" "}
                    {pct(t.first_accuracy)} → {pct(t.last_accuracy)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {d.improved.length > 0 ? (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-2 dark:border-emerald-500/30 dark:bg-emerald-500/10">
              <h5 className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-emerald-900 dark:text-emerald-200">
                <TrendingUp className="size-3.5" aria-hidden />
                Gelişen konular
              </h5>
              <ul className="space-y-0.5 text-[11px] text-emerald-800 dark:text-emerald-300">
                {d.improved.map((t: AnalysisTrendTopic) => (
                  <li key={t.topic_id}>
                    <b>{t.topic_name}</b> · {t.subject_name} —{" "}
                    {pct(t.first_accuracy)} → {pct(t.last_accuracy)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {d.exams.length >= 2 && heatTopics.length > 0 ? (
        <div>
          <h5 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Konu × deneme ısı haritası{" "}
            <span className="font-normal normal-case">
              (hücre = o denemedeki doğru/soru; yeşil iyi, kırmızı kötü)
            </span>
          </h5>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full min-w-[480px] text-[11px]">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-muted-foreground">
                  <th className="px-2 py-1 font-medium">Konu</th>
                  {d.exams.map((e) => (
                    <th
                      key={e.id}
                      className="px-1 py-1 text-center font-medium tabular-nums"
                      title={e.title}
                    >
                      {fmtDayMonth(e.exam_date)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {heatTopics.map((t) => {
                  const cells: (typeof t.cells[number] | null)[] =
                    d.exams.map(() => null);
                  for (const c of t.cells) {
                    const i = examById.get(c.exam_id);
                    if (i !== undefined) cells[i] = c;
                  }
                  return (
                    <tr key={t.topic_id} className="border-b border-border/60 last:border-0">
                      <td
                        className="max-w-44 truncate px-2 py-1 text-foreground"
                        title={`${t.topic_name} · ${t.subject_name}`}
                      >
                        {t.topic_name}
                      </td>
                      {cells.map((c, i) => (
                        <td key={i} className="px-0.5 py-0.5 text-center">
                          {c ? (
                            <span
                              className={cn(
                                "inline-block min-w-8 rounded px-1 py-0.5 font-medium tabular-nums",
                                cellTone(c.accuracy),
                              )}
                              title={`${c.correct}D ${c.wrong}Y ${c.blank}B`}
                            >
                              {c.correct}/{c.total}
                            </span>
                          ) : (
                            <span className="text-muted-foreground/50">·</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {d.unmatched_questions > 0 ? (
        <p className="text-[11px] text-amber-800 dark:text-amber-300">
          {d.unmatched_questions} soru müfredat konusuna bağlanmadan kaydedilmiş —
          denemenin yanındaki &quot;Satırları düzelt&quot; ile bağlarsan analize girer.
        </p>
      ) : null}
    </section>
  );
}
