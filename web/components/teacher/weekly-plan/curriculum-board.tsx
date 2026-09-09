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
import Link from "next/link";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Check,
  ChevronDown,
  ChevronRight,
  ListChecks,
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
  BoardSourceItem,
  BoardSubjectItem,
  BoardTopicItem,
  TopicBoardResponse,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";
import { PinnableSection } from "./pinnable-section";

const DOT: Record<string, string> = {
  kapali: "bg-emerald-500",
  tamamlandi: "bg-emerald-300 ring-1 ring-emerald-500",
  devam: "bg-cyan-500",
  planlandi: "bg-amber-400",
  baslanmadi: "bg-slate-300 dark:bg-slate-600",
  kaynak_yok: "bg-slate-200 dark:bg-slate-700",
};

function metricLine(t: BoardTopicItem): string {
  if (t.closed) return "kapatıldı";
  if (t.status === "tamamlandi") {
    const acc =
      t.accuracy_pct === null || t.accuracy_pct === undefined
        ? ""
        : ` · %${t.accuracy_pct}`;
    return `kaynak bitti${acc}`;
  }
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
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  const [expanded, setExpanded] = React.useState<number | null>(null);

  const boardQ = useQuery<TopicBoardResponse>({
    queryKey: teacherKeys.studentTopicBoard(studentId, subjectId),
    queryFn: () =>
      getTopicBoard(studentId, subjectId === "" ? null : subjectId),
    // Ders değişince eski liste kalsın (seçici kaybolmasın, boş flaş olmasın)
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const closeM = useCloseTopic(studentId);
  const reopenM = useReopenTopic(studentId);
  const create = useCreateTask(studentId);

  const subjects = boardQ.data?.subjects ?? [];
  // SAHA BUG'I (2026-09-08): seçici `subjects` listesinden kuruluyordu; ders
  // seçilince yanıt yalnız o dersi taşıdığından seçici KAYBOLUYORDU. Artık
  // filtreden bağımsız `subject_options`.
  const options = boardQ.data?.subject_options ?? [];
  const active =
    (subjectId === ""
      ? subjects[0]
      : subjects.find((s) => s.subject_id === subjectId)) ?? subjects[0];

  /**
   * Görev yaz. `src` verilmezse kaynaksız (konuya bağlı, kitapsız) kalem.
   *
   * KOÇ (2026-09-09): eskiden kaynak `t.sources[0]` ile SESSİZCE seçiliyordu;
   * iki kaynaklı konuda koç hangi kitaba yazdığını bilmiyordu. Artık kaynak
   * satırdan seçilir — tık sayısı aynı (konu → satırdaki +N).
   */
  function assign(
    t: BoardTopicItem,
    count: number,
    src: BoardSourceItem | null,
  ) {
    const title = !src
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
          !src
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
    <PinnableSection
      id="week:curriculum"
      title="Müfredat"
      icon={<ListChecks className="size-4" aria-hidden />}
      summary={
        active
          ? `${active.closed_topics}/${active.total_topics} kapalı · %${active.coverage_pct}`
          : undefined
      }
    >
      {(
        <div className="px-4 pb-3">
          {options.length > 1 ? (
            <select
              value={
                subjectId === ""
                  ? String(active?.subject_id ?? options[0]?.subject_id ?? "")
                  : String(subjectId)
              }
              onChange={(e) => setSubjectId(Number(e.target.value))}
              className="mb-2 w-full rounded-md border border-border bg-background px-2 py-1 text-[12px]"
              aria-label="Ders seç"
            >
              {options.map((s) => (
                <option key={s.subject_id} value={s.subject_id}>
                  {s.has_source ? s.name : `${s.name} (kaynak yok)`}
                </option>
              ))}
            </select>
          ) : null}

          {/* Müfredata BAĞLI OLMAYAN bölümler: sayıma girmez, GÖSTERİLİR — listenin
              ÜSTÜNDE ki koç aşağıdaki sayıların eksik olduğunu önce görsün. Koç
              (2026-09-08): ikinci kaynağın "Bölme ve Bölünebilme Kuralları"
              bölümü bağlı olmadığı için panel yalnız birinci kaynağı sayıyordu. */}
          {active && (active.unmapped_sections?.length ?? 0) > 0 ? (
            <UnmappedNote items={active.unmapped_sections} />
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
                      className="flex w-full items-start gap-2 rounded px-1.5 py-1.5 text-left hover:bg-muted/50"
                    >
                      <span
                        className={cn(
                          "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                          DOT[t.status] ?? DOT.baslanmadi,
                        )}
                        aria-hidden
                      />
                      <span
                        className={cn(
                          // KIRPMA YOK: uzun konu adı ikinci satıra sarar
                          "min-w-0 flex-1 whitespace-normal break-words text-[12.5px] leading-snug",
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
                      <span className="ml-auto shrink-0 whitespace-nowrap pt-px text-[10.5px] tabular-nums text-muted-foreground">
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

                        {/* KAYNAK SEÇİMİ (2026-09-09): "+3 test" hangi kitaba
                            yazıyor sorusunun cevabı. Her kaynak kendi satırında,
                            kendi butonuyla — koç görerek seçer, tık sayısı aynı
                            (konu → satırdaki +3). Sistem "devam" ettiğini önerir
                            ama dayatmaz. */}
                        {t.closed ? null : t.sources.length > 0 ? (
                          <div className="space-y-1">
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                              {t.sources.length > 1
                                ? `Kaynak seç (${t.sources.length})`
                                : "Kaynak"}
                            </p>
                            <ul className="space-y-1">
                              {t.sources.map((s) => (
                                <li
                                  key={s.section_id}
                                  className={cn(
                                    "flex items-center gap-1.5 rounded-md border px-1.5 py-1",
                                    s.recommended && t.sources.length > 1
                                      ? "border-cyan-300 bg-cyan-50/60 dark:border-cyan-500/40 dark:bg-cyan-500/10"
                                      : "border-border bg-background",
                                  )}
                                >
                                  {/* KIRPMA YOK — uzun kitap/bölüm adı sarar */}
                                  <span className="min-w-0 flex-1 whitespace-normal break-words text-[11px] leading-snug">
                                    <span className="font-medium text-foreground">
                                      {s.book_name}
                                    </span>
                                    <span className="text-muted-foreground">
                                      {" · "}
                                      {s.section_label}
                                    </span>
                                    <span className="mt-0.5 block text-[10px] tabular-nums text-muted-foreground">
                                      {/* Rozet DOLGULU: ton + dark: varyantı
                                          koyu temada kontrastı yitiriyordu
                                          (ölçüm: 1.09). Dolgu iki temada okunur. */}
                                      {s.recommended && t.sources.length > 1 ? (
                                        <span className="mr-1 rounded bg-cyan-600 px-1 py-px text-[9px] font-semibold uppercase tracking-wide text-white">
                                          devam
                                        </span>
                                      ) : null}
                                      {s.completed}/{s.total} çözüldü ·{" "}
                                      {s.full ? (
                                        <span className="text-amber-700 dark:text-amber-300">
                                          kapasite doldu
                                        </span>
                                      ) : (
                                        `${s.remaining} kaldı`
                                      )}
                                    </span>
                                  </span>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 shrink-0 px-2 text-[11px]"
                                    disabled={create.isPending}
                                    onClick={() => assign(t, 3, s)}
                                    title={
                                      s.full
                                        ? `${s.book_name} — kapasite dolu, yine de 3 test yaz (uyarı verilir)`
                                        : `${s.book_name} — bu kaynaktan 3 test yaz`
                                    }
                                  >
                                    +3 test
                                  </Button>
                                </li>
                              ))}
                            </ul>
                          </div>
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
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 px-2 text-[11px]"
                                disabled={create.isPending}
                                onClick={() => assign(t, 3, null)}
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
      )}
    </PinnableSection>
  );
}

function UnmappedNote({ items }: { items: BoardSubjectItem["unmapped_sections"] }) {
  // KOÇ (ekran görüntüsü, 2026-09-08): dar panelde "345 TYT Matematik Soru
  // Bankası: Ta…" — kırpılmış metin bilgi vermiyor, sinir bozuyor. KURAL: bu
  // panelde metin KIRPILMAZ; sığmıyorsa satır kaydırılır ya da açılır ayrıntıya
  // alınır. Varsayılan tek satır (sayı + test), açınca kitap başına tam ad +
  // bölüm adları alt alta.
  const [open, setOpen] = React.useState(false);
  const byBook = new Map<number, { name: string; labels: string[]; tests: number }>();
  for (const u of items) {
    const b = byBook.get(u.book_id) ?? { name: u.book_name, labels: [], tests: 0 };
    b.labels.push(u.label);
    b.tests += u.test_count;
    byBook.set(u.book_id, b);
  }
  const total = items.reduce((s, u) => s + u.test_count, 0);
  return (
    <div
      className="mb-2 rounded-md border border-amber-200 bg-amber-50/60 text-[11px] leading-snug text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200"
      data-unmapped-note
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-1.5 px-2 py-1.5 text-left"
      >
        <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
        <span className="min-w-0 flex-1 whitespace-normal">
          <span className="font-medium">{items.length} bölüm müfredata bağlı değil</span>
          {" · "}
          {total} test aşağıdaki sayımlarda yok
        </span>
        {open ? (
          <ChevronDown className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
        ) : (
          <ChevronRight className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
        )}
      </button>
      {open ? (
        <ul className="space-y-1.5 px-2 pb-2">
          {[...byBook.entries()].map(([bookId, b]) => (
            <li
              key={bookId}
              className="rounded border border-amber-200/70 bg-background/50 px-2 py-1.5 dark:border-amber-500/20"
            >
              <p className="whitespace-normal break-words font-medium">{b.name}</p>
              <p className="mt-0.5 whitespace-normal break-words text-[10.5px] opacity-90">
                {b.labels.join(" · ")}
              </p>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="text-[10.5px] tabular-nums">
                  {b.labels.length} bölüm · {b.tests} test
                </span>
                <Link
                  href={`/teacher/library/books/${bookId}?map=1`}
                  className="shrink-0 font-semibold underline underline-offset-2 hover:text-amber-950 dark:hover:text-amber-100"
                >
                  Eşleştir →
                </Link>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
