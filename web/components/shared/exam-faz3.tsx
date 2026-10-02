"use client";

/**
 * Deneme analizi Faz 3 — çeldirici analizi (deneme detayında) ve birleşik puan
 * tahmini (ayrı sekme). Koç ve öğrenci ortak; hesap app/services/exam_faz3.py.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Calculator, Crosshair, Info, TriangleAlert } from "lucide-react";

import { ExamSection } from "@/components/teacher/exams/exam-analytics";
import type { ProgressSource } from "@/lib/api/exam-progress";
import { faz3Keys, getDistractors, getScoreEstimate } from "@/lib/api/exam-faz3";
import { fmtNet, fmtSigned, fmtTRDate } from "@/lib/exam-format";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------- çeldirici

export function DistractorPanel({
  examId,
  source,
  enabled,
}: {
  examId: number;
  source: ProgressSource;
  enabled: boolean;
}) {
  const q = useQuery({
    queryKey: faz3Keys.distractors(source, examId),
    queryFn: () => getDistractors(source, examId),
    enabled,
    staleTime: 60_000,
  });
  if (!enabled) return null;
  if (q.isLoading) return <p className="text-sm text-muted-foreground">Çeldirici analizi hazırlanıyor…</p>;
  if (!q.data) return null;
  const d = q.data;
  if (!d.answered) return null;
  const maxPct = Math.max(1, ...d.letters.flatMap((l) => [l.chosen_pct, l.key_pct]));
  return (
    <ExamSection
      icon={Crosshair}
      title="Çeldirici analizi"
      description="Hangi şıkları ne sıklıkla işaretlediği (cevap anahtarındaki payla kıyas) ve yanlışlarda hangi şıkka düştüğü."
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            İşaretleme dağılımı · {d.answered} cevap, {d.wrong_count} yanlış
          </p>
          <div className="space-y-1.5">
            {d.letters.map((l) => (
              <div key={l.letter} className="grid grid-cols-[1.25rem_1fr_auto] items-center gap-2 text-xs">
                <span className="font-semibold">{l.letter}</span>
                <div className="space-y-0.5">
                  <div className="h-2 rounded bg-cyan-600" style={{ width: `${(l.chosen_pct / maxPct) * 100}%` }} />
                  <div className="h-1.5 rounded bg-slate-400/60" style={{ width: `${(l.key_pct / maxPct) * 100}%` }} />
                </div>
                <span className="whitespace-nowrap tabular-nums text-muted-foreground">
                  %{String(l.chosen_pct).replace(".", ",")} · yanlış {l.wrong_chosen}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-2 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <span className="inline-block h-2 w-3 rounded bg-cyan-600" /> öğrencinin işaretlediği
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="inline-block h-1.5 w-3 rounded bg-slate-400/60" /> cevap anahtarındaki pay
            </span>
          </p>
        </div>
        <div>
          {d.notes.length ? (
            <ul className="space-y-2">
              {d.notes.map((n) => (
                <li
                  key={n}
                  className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100"
                >
                  <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  <span>{n}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Belirgin bir şık eğilimi görünmüyor.</p>
          )}
        </div>
      </div>

      <div className="mt-4">
        {d.peer_count ? (
          <>
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Aynı denemeye giren {d.peer_count} öğrenci{source.kind === "teacher" ? "n" : ""} — öğrencinin yanlış/boş
              bıraktığı sorular (en zor olandan)
            </p>
            <div className="relative overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-1.5 pr-2 font-medium">Soru</th>
                    <th className="px-2 py-1.5 font-medium">Konu</th>
                    <th className="px-2 py-1.5 text-center font-medium">Doğru / öğrenci</th>
                    <th className="px-2 py-1.5 text-right font-medium">Diğerlerinde doğru</th>
                    <th className="py-1.5 pl-2 text-right font-medium">En çok seçilen yanlış</th>
                  </tr>
                </thead>
                <tbody>
                  {d.questions.slice(0, 15).map((r) => (
                    <tr key={`${r.subject}-${r.question_no}`} className="border-b border-border/60 last:border-0">
                      <td className="py-1.5 pr-2 whitespace-nowrap">
                        {r.subject} {r.question_no}
                      </td>
                      <td className="px-2 py-1.5 text-xs text-muted-foreground">{r.topic ?? "—"}</td>
                      <td className="px-2 py-1.5 text-center tabular-nums">
                        {r.correct_answer ?? "—"} / {r.student_answer ?? "boş"}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums">%{r.peer_correct_pct}</td>
                      <td className="py-1.5 pl-2 text-right">
                        {r.top_wrong_option ? (
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold",
                              r.same_as_student ? "bg-rose-600 text-white" : "bg-muted text-foreground",
                            )}
                            title={r.same_as_student ? "Öğrenci de bu çeldiriciyi seçti" : undefined}
                          >
                            {r.top_wrong_option} · {r.top_wrong_count} kişi
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : source.kind === "parent" ? null : (
          <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Soru bazında çeldirici karşılaştırması için aynı denemeye giren en az {d.peer_min} öğrenci daha
            gerekir (aynı ad, tür ve tarih).
          </p>
        )}
      </div>
    </ExamSection>
  );
}

// ---------------------------------------------------------------- puan tahmini

export function ScoreEstimatePanel({ source }: { source: ProgressSource }) {
  const q = useQuery({
    queryKey: faz3Keys.score(source),
    queryFn: () => getScoreEstimate(source),
    staleTime: 60_000,
  });
  if (q.isLoading) return <p className="text-sm text-muted-foreground">Puan tahmini hesaplanıyor…</p>;
  if (!q.data) return <p className="text-sm text-rose-700 dark:text-rose-400">Puan tahmini yüklenemedi.</p>;
  const d = q.data;
  return (
    <div className="space-y-4">
      <ExamSection
        icon={Calculator}
        title={d.kind === "lgs" ? "Tahmini LGS puanı" : "Tahmini YKS puanları"}
        description={d.disclaimer}
      >
        {!d.scores.length ? (
          <p className="text-sm text-muted-foreground">
            Puan tahmini için TYT ya da LGS denemesi gerekir.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {d.scores.map((s) => (
              <div
                key={s.key}
                className={cn(
                  "rounded-lg border p-3",
                  s.is_student_track ? "border-cyan-600 bg-cyan-500/5" : "border-border",
                )}
              >
                <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  {s.label}
                  {s.is_student_track ? (
                    <span className="rounded bg-cyan-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                      öğrencinin alanı
                    </span>
                  ) : null}
                </p>
                <p className="mt-1 text-3xl font-semibold tabular-nums">~{fmtNet(s.score)}</p>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-cyan-600" style={{ width: `${Math.min(100, (s.score / s.max) * 100)}%` }} />
                </div>
                {s.detail ? <p className="mt-1.5 text-[11px] text-muted-foreground">{s.detail}</p> : null}
              </div>
            ))}
          </div>
        )}
        {d.warnings.length ? (
          <ul className="mt-3 space-y-1">
            {d.warnings.map((w) => (
              <li key={w} className="flex gap-1.5 text-xs text-amber-800 dark:text-amber-300">
                <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                {w}
              </li>
            ))}
          </ul>
        ) : null}
      </ExamSection>

      {d.inputs.length ? (
        <ExamSection title="Hesaba giren denemeler" description="Her türün en son denemesi kullanılır.">
          <ul className="space-y-1.5 text-sm">
            {d.inputs.map((i) => (
              <li key={i.id} className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="min-w-0 break-words">
                  {i.title} <span className="text-xs text-muted-foreground">· {i.section_label} · {fmtTRDate(i.exam_date)}</span>
                </span>
                <span className="tabular-nums">
                  {fmtNet(i.net)} net{i.karne_score != null ? ` · karne puanı ${fmtNet(i.karne_score)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </ExamSection>
      ) : null}

      {d.calibration.length ? (
        <ExamSection
          title="Tahmin ile karne puanı"
          description="Karnede puan yazan denemelerde aynı yöntemle yapılan tahminin karne puanından farkı — tahminin bu öğrenci için ne kadar sapabileceğini gösterir."
        >
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[460px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-1.5 pr-2 font-medium">Deneme</th>
                  <th className="px-2 py-1.5 text-right font-medium">Karne</th>
                  <th className="px-2 py-1.5 text-right font-medium">Tahmin</th>
                  <th className="py-1.5 pl-2 text-right font-medium">Fark</th>
                </tr>
              </thead>
              <tbody>
                {d.calibration.map((c) => (
                  <tr key={c.exam_id} className="border-b border-border/60 last:border-0">
                    <td className="py-1.5 pr-2">
                      {c.title} <span className="text-xs text-muted-foreground">· {fmtTRDate(c.exam_date)}</span>
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{fmtNet(c.karne_score)}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{fmtNet(c.estimate)}</td>
                    <td className="py-1.5 pl-2 text-right tabular-nums">{fmtSigned(c.diff)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ExamSection>
      ) : null}
    </div>
  );
}
