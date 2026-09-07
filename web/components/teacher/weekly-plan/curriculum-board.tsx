"use client";

/**
 * Müfredat paneli — "kapatayım mı, ek görev mi vereyim?" (P5, 2026-09-07).
 *
 * KOÇ İHTİYACI (birebir): "hangi konuya geçeceğiz? hangi konuları gördük?
 * her görevden ne kadar soru çözüldü, konunun çözülecek testi kaldı mı?
 * biten ünitenin performansını görmek isteyecek ve ek görev mi vereceğine
 * yoksa konuyu kapatacağına karar verecek."
 *
 * Bu beş bilgi sistemde vardı ama beş ayrı yüzeye dağılmıştı. Panel hepsini
 * konu ekseninde birleştirir ve karar butonlarını yanına koyar.
 *
 * Sağ panel dar olduğu için (koç daha önce "kart dar kaldı" demişti) liste
 * kompakt: satır = ad + durum + kısa metrik; tıklayınca detay + aksiyonlar.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Loader2,
  RotateCcw,
  TriangleAlert,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { getTopicBoard, teacherKeys } from "@/lib/api/teacher";
import {
  useCloseTopic,
  useCreateTask,
  useReopenTopic,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  BoardTopicItem,
  TopicBoardResponse,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

const DOT: Record<string, string> = {
  kapali: "bg-emerald-500",
  devam: "bg-cyan-500",
  planlandi: "bg-amber-400",
  baslanmadi: "bg-slate-300 dark:bg-slate-600",
  kaynak_yok: "bg-slate-200 dark:bg-slate-700",
};

function metricLine(t: BoardTopicItem): string {
  if (t.closed) return "kapatıldı";
  const solved = t.tests_solved + t.sourceless_completed;
  if (solved <= 0) return t.remaining > 0 ? `${t.remaining} test hazır` : "—";
  const acc =
    t.accuracy_pct === null || t.accuracy_pct === undefined
      ? "D/Y girilmedi"
      : `%${t.accuracy_pct}`;
  return `${solved} test · ${acc}`;
}

export function CurriculumBoard({
  studentId,
  dayDate,
}: {
  studentId: number;
  /** Aktif gün — "+N test" bu güne yazar */
  dayDate: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  const [expanded, setExpanded] = React.useState<number | null>(null);

  const boardQ = useQuery<TopicBoardResponse>({
    queryKey: teacherKeys.studentTopicBoard(studentId, subjectId),
    queryFn: () =>
      getTopicBoard(studentId, subjectId === "" ? null : subjectId),
    enabled: open,
    staleTime: 30_000,
  });

  const closeM = useCloseTopic(studentId);
  const reopenM = useReopenTopic(studentId);
  const create = useCreateTask(studentId);

  const subjects = boardQ.data?.subjects ?? [];
  const active =
    subjectId === ""
      ? subjects[0]
      : subjects.find((s) => s.subject_id === subjectId);

  function assign(t: BoardTopicItem, count: number, sourceless: boolean) {
    const src = t.sources[0];
    const title = sourceless || !src
      ? `${t.name} — ${count} test`
      : `${src.book_name} — ${src.section_label}: ${count} test`;
    create.mutate({
      body: {
        date: dayDate,
        type: "test",
        title,
        scheduled_hour: null,
        period: null,
        items: [
          sourceless || !src
            ? {
                book_id: null,
                section_id: null,
                topic_id: t.topic_id,
                label: t.name,
                planned_count: count,
              }
            : {
                book_id: src.book_id,
                section_id: src.section_id,
                planned_count: count,
                allow_over_capacity: count > src.remaining,
              },
        ],
      },
    });
  }

  return (
    <div className="border-b border-border/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-muted/40"
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
        )}
        <span className="text-sm font-semibold text-foreground">Müfredat</span>
        {active ? (
          <span className="ml-auto text-[11px] tabular-nums text-muted-foreground">
            {active.closed_topics}/{active.total_topics} kapalı · %
            {active.coverage_pct}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="px-4 pb-3">
          {subjects.length > 1 ? (
            <select
              value={subjectId === "" ? String(subjects[0]?.subject_id ?? "") : String(subjectId)}
              onChange={(e) => setSubjectId(Number(e.target.value))}
              className="mb-2 w-full rounded-md border border-border bg-background px-2 py-1 text-[12px]"
              aria-label="Ders seç"
            >
              {subjects.map((s) => (
                <option key={s.subject_id} value={s.subject_id}>
                  {s.name}
                </option>
              ))}
            </select>
          ) : null}

          {boardQ.isLoading ? (
            <p className="py-3 text-center text-xs text-muted-foreground">
              <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />
              yükleniyor…
            </p>
          ) : !active ? (
            <p className="py-3 text-center text-xs text-muted-foreground">
              Bu öğrenci için müfredat konusu bulunamadı.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {active.topics.map((t) => {
                const isOpen = expanded === t.topic_id;
                const solved = t.tests_solved + t.sourceless_completed;
                return (
                  <li key={t.topic_id}>
                    <button
                      type="button"
                      onClick={() =>
                        setExpanded(isOpen ? null : t.topic_id)
                      }
                      className="flex w-full items-center gap-2 rounded px-1.5 py-1.5 text-left hover:bg-muted/50"
                    >
                      <span
                        className={cn(
                          "h-1.5 w-1.5 shrink-0 rounded-full",
                          DOT[t.status] ?? DOT.baslanmadi,
                        )}
                        aria-hidden
                      />
                      <span
                        className={cn(
                          "truncate text-[12.5px]",
                          t.closed
                            ? "text-muted-foreground line-through"
                            : "text-foreground",
                        )}
                      >
                        {t.name}
                      </span>
                      {t.readiness === "caution" ? (
                        <TriangleAlert className="h-3 w-3 shrink-0 text-amber-600 dark:text-amber-400" />
                      ) : null}
                      {t.readiness === "ready" ? (
                        <Check className="h-3 w-3 shrink-0 text-emerald-600 dark:text-emerald-400" />
                      ) : null}
                      <span className="ml-auto whitespace-nowrap text-[10.5px] tabular-nums text-muted-foreground">
                        {metricLine(t)}
                      </span>
                    </button>

                    {isOpen ? (
                      <div className="mb-1 ml-3.5 space-y-1.5 rounded-md border border-border bg-muted/30 p-2">
                        {/* Kapatma kararının gerekçesi — sistem ipucu verir, koç karar verir */}
                        <p
                          className={cn(
                            "text-[11px] leading-snug",
                            t.readiness === "caution"
                              ? "text-amber-800 dark:text-amber-200"
                              : t.readiness === "ready"
                                ? "text-emerald-800 dark:text-emerald-200"
                                : "text-muted-foreground",
                          )}
                        >
                          {t.readiness_note}
                        </p>

                        <dl className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[11px]">
                          <dt className="text-muted-foreground">Çözülen</dt>
                          <dd className="text-right tabular-nums text-foreground">
                            {solved} test
                            {t.sourceless_completed > 0
                              ? ` (${t.sourceless_completed} kaynaksız)`
                              : ""}
                          </dd>
                          <dt className="text-muted-foreground">Doğruluk</dt>
                          <dd className="text-right tabular-nums text-foreground">
                            {t.accuracy_pct === null ||
                            t.accuracy_pct === undefined
                              ? "—"
                              : `%${t.accuracy_pct} (${t.correct}D/${t.wrong}Y)`}
                          </dd>
                          <dt className="text-muted-foreground">Kalan</dt>
                          <dd className="text-right tabular-nums text-foreground">
                            {t.remaining} test
                          </dd>
                          {t.exam_wrong > 0 ? (
                            <>
                              <dt className="text-amber-700 dark:text-amber-300">
                                Denemede
                              </dt>
                              <dd className="text-right tabular-nums text-amber-700 dark:text-amber-300">
                                {t.exam_wrong} yanlış
                              </dd>
                            </>
                          ) : null}
                          {t.open_wrongs > 0 ? (
                            <>
                              <dt className="text-amber-700 dark:text-amber-300">
                                Arşivde
                              </dt>
                              <dd className="text-right tabular-nums text-amber-700 dark:text-amber-300">
                                {t.open_wrongs} açık
                              </dd>
                            </>
                          ) : null}
                        </dl>

                        {t.sources.length > 0 ? (
                          <p className="truncate text-[10.5px] text-muted-foreground">
                            {t.sources[0].book_name} ·{" "}
                            {t.sources[0].full
                              ? "kapasite doldu"
                              : `${t.sources[0].remaining} kaldı`}
                          </p>
                        ) : (
                          <p className="text-[10.5px] text-muted-foreground">
                            Bu konuda kaynak yok
                          </p>
                        )}

                        <div className="flex flex-wrap gap-1.5 pt-0.5">
                          {t.closed ? (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 px-2 text-[11px]"
                              disabled={reopenM.isPending}
                              onClick={() =>
                                reopenM.mutate({ topicId: t.topic_id })
                              }
                            >
                              <RotateCcw className="mr-1 h-3 w-3" />
                              Yeniden aç
                            </Button>
                          ) : (
                            <>
                              {t.sources.length > 0 ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 px-2 text-[11px]"
                                  disabled={create.isPending}
                                  onClick={() => assign(t, 3, false)}
                                >
                                  +3 test
                                </Button>
                              ) : null}
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 px-2 text-[11px]"
                                disabled={create.isPending}
                                onClick={() => assign(t, 3, true)}
                              >
                                <Zap className="mr-1 h-3 w-3" />
                                Kaynaksız ver
                              </Button>
                              <Button
                                size="sm"
                                className="h-7 bg-emerald-600 px-2 text-[11px] text-white hover:bg-emerald-700"
                                disabled={closeM.isPending}
                                onClick={() =>
                                  closeM.mutate({ topicId: t.topic_id })
                                }
                              >
                                <Check className="mr-1 h-3 w-3" />
                                Konuyu kapat
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
