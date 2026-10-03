"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Target } from "lucide-react";

import { ExamTrendTopics } from "@/components/shared/exam-trend-topics";

import { getExamTopicAnalysis } from "@/lib/api/exam-import";
import type {
  AnalysisOpportunity,
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
  if (acc >= 0.5) return "bg-emerald-300/70 text-emerald-950 dark:text-emerald-200";
  if (acc > 0) return "bg-amber-300/75 text-amber-950 dark:text-amber-200";
  return "bg-rose-400/85 text-white";
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
  /** Panelin seçili sınav türü (tek türe filtreli analiz). */
  section: string | null;
  /** Panelin dönem seçimi (koç: "Tümü" / önceki dönem). Yoksa güncel dönem. */
  period?: string;
}) {
  const q = useQuery<ExamTopicAnalysisResponse>({
    queryKey:
      parentStudentId != null
        ? ["parent", "students", String(parentStudentId), "topic-analysis", section ?? "auto", period ?? "current"]
        : studentId != null
          ? ["teacher", "me", "students", String(studentId), "exams",
             "topic-analysis", section ?? "auto", period ?? "current"]
          : ["student", "exams", "topic-analysis", section ?? "auto", period ?? "current"],
    queryFn: () => getExamTopicAnalysis(studentId, section, parentStudentId, period),
    staleTime: 30_000,
  });
  const d = q.data;
  const [subj, setSubj] = React.useState<string>("");
  if (!d) return null;
  if (d.exams.length === 0)
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
        Bu dönemde konu analizine girecek deneme yok. Analiz, PDF&apos;ten aktarılan (soru soru
        okunan) denemelerden hesaplanır; elle girilen denemeler buraya girmez.
      </p>
    );

  const subjectsAll = [...new Set(d.topics.map((t) => t.subject_name))];
  const activeSubj = subjectsAll.includes(subj) ? subj : "";
  const bySubj = <T extends { subject_name: string }>(arr: T[]) =>
    activeSubj ? arr.filter((x) => x.subject_name === activeSubj) : arr;
  const examById = new Map(d.exams.map((e, i) => [e.id, i]));
  const heatTopics = bySubj(d.topics).slice(0, 20);
  const opps = bySubj(d.opportunities).slice(0, 10);
  const forgotten = bySubj(d.forgotten);
  const improved = bySubj(d.improved);
  const maxGain = opps[0]?.net_gain_per_exam ?? 0;

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-border bg-card px-4 py-3">
        <h4 className="text-sm font-semibold text-foreground">
          Konu Analizi{" "}
          <span className="font-normal text-muted-foreground">
            · {d.section_label} · {d.exams.length} deneme · {d.analyzed_question_count} soru
          </span>
        </h4>
        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
          PDF&apos;ten aktarılan denemelerin soru satırlarından hesaplanır: her soru karnedeki
          konusuyla müfredat konusuna bağlanır, konu konu toplanır. Elle girilen denemeler
          (soru satırı yok) bu analize girmez.
        </p>
        {subjectsAll.length > 1 ? (
          <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label="Ders süzgeci">
            {["", ...subjectsAll].map((sn) => (
              <button
                key={sn || "all"}
                type="button"
                onClick={() => setSubj(sn)}
                aria-pressed={activeSubj === sn}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-xs font-medium",
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
      </div>

      {opps.length > 0 ? (
        <div className="rounded-xl border border-border bg-card px-4 py-3">
          <h5 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
            <Target className="size-4 text-rose-600 dark:text-rose-300" aria-hidden />
            Net fırsatı
          </h5>
          <p className="mb-3 mt-0.5 text-xs leading-relaxed text-muted-foreground">
            Bu konulardaki yanlış ve boşlar doğru olsaydı deneme başına kazanılacak net.
            En büyük fırsat en üstte — programda öncelik bu konulara verilir.
          </p>
          <ul className="space-y-2">
            {opps.map((o: AnalysisOpportunity) => (
              <li key={o.topic_id} className="text-sm">
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0 break-words">
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
                  <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
                    {o.wrong} yanlış · {o.blank} boş / {o.total} soru · doğruluk {pct(o.accuracy)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {activeSubj && opps.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-3 text-xs text-muted-foreground">
          <b className="text-foreground">{activeSubj}</b> için net fırsatı yok — bu denemelerde bu dersten yanlış
          ya da boş bırakılan soru (en az 2 soru gelen konularda) bulunmuyor.
        </p>
      ) : null}

      <ExamTrendTopics forgotten={forgotten} improved={improved} studentId={studentId} />
      {activeSubj && d.exams.length >= 2 && forgotten.length === 0 && improved.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-3 text-xs text-muted-foreground">
          <b className="text-foreground">{activeSubj}</b> için belirgin unutulan ya da gelişen konu yok. Bir konunun
          işaretlenmesi için ilk ve son denemelerin her birinde o konudan en az 2 soru gelmesi ve doğruluğun en
          az 34 puan değişmesi gerekir.
        </p>
      ) : null}

      {d.exams.length < 2 ? (
        <p className="rounded-md bg-muted/40 px-2.5 py-2 text-[11px] text-muted-foreground">
          Konu × deneme <b>ısı haritası</b> ile <b>unutulan / gelişen konular</b>,
          aynı türde en az <b>2 deneme</b> aktarılınca burada görünür — yeni
          deneme ekledikçe analiz derinleşir.
        </p>
      ) : null}

      {d.exams.length >= 2 && heatTopics.length > 0 ? (
        <div className="rounded-xl border border-border bg-card px-4 py-3">
          <h5 className="text-sm font-semibold text-foreground">Konu × deneme ısı haritası</h5>
          <p className="mb-3 mt-0.5 text-xs leading-relaxed text-muted-foreground">
            Her satır bir konu, her sütun bir deneme. Hücrede o denemede o konudan kaç sorunun
            kaçını doğru yaptığı yazar; yeşil iyi, kırmızı zayıf. Satır boyunca kırmızı kalan
            konu kalıcı zayıflıktır. En çok soru gelen {heatTopics.length} konu gösterilir.
          </p>
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
                        className="min-w-40 px-2 py-1 text-foreground"
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
          {`${d.unmatched_questions} soru müfredat konusuna bağlanmadan kaydedilmiş — denemenin yanındaki "Satırları düzelt" ile bağlarsan analize girer.`}
        </p>
      ) : null}
    </section>
  );
}
