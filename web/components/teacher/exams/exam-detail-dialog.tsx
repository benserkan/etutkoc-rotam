"use client";

/**
 * Deneme detayı — tek denemenin karnesi (Faz 1, 2026-10-02).
 *
 * Puan/sıralama · ders tablosu (önceki denemeye fark) · soru tablosu (süzgeçli)
 * · test içinde ilerleyiş (ilk yarı ↔ ikinci yarı doğruluk) · yazdır/paylaş.
 * Soru bazlı bölümler yalnız PDF'ten aktarılan denemede vardır (elle girilende
 * soru satırı yok).
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ListChecks, TimerReset } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DistractorPanel } from "@/components/shared/exam-faz3";
import { api } from "@/lib/api";
import { getTeacherExamQuestions, teacherKeys } from "@/lib/api/teacher";
import type { ExamQuestionsResponse, ExamResultRow } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

import {
  DybBar,
  ExamSection,
  ExamShareMenu,
  SubjectTable,
} from "./exam-analytics";
import { fmtNet, fmtTRDate, halfDrop, percentile } from "@/lib/exam-format";

type Filter = "all" | "yanlis" | "bos" | "dogru";

const RESULT_LABEL: Record<string, string> = { dogru: "Doğru", yanlis: "Yanlış", bos: "Boş" };
const RESULT_TONE: Record<string, string> = {
  dogru: "bg-emerald-600 text-white",
  yanlis: "bg-rose-600 text-white",
  bos: "bg-slate-500 text-white",
};

export function ExamDetailDialog({
  row,
  prev,
  studentId,
  parentStudentId = null,
  studentName,
  open,
  onOpenChange,
}: {
  row: ExamResultRow;
  prev: ExamResultRow | null;
  /** null → öğrenci kendi denemesine bakıyor (öğrenci ucu, paylaş/yazdır yok). */
  studentId: number | null;
  /** Veli görünümü: çocuğun id'si (studentId null olmalı) — salt okuma, paylaş yok. */
  parentStudentId?: number | null;
  studentName?: string | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const hasQuestions = row.import_source === "pdf_import";
  const q = useQuery({
    queryKey: parentStudentId != null
      ? (["parent", "students", String(parentStudentId), "exams", String(row.id), "questions"] as const)
      : studentId == null
        ? (["student", "exams", String(row.id), "questions"] as const)
        : teacherKeys.examQuestions(row.id),
    queryFn: () =>
      parentStudentId != null
        ? api<ExamQuestionsResponse>(`/api/v2/parent/students/${parentStudentId}/exams/${row.id}/questions`)
        : studentId == null
          ? api<ExamQuestionsResponse>(`/api/v2/student/exams/${row.id}/questions`)
          : getTeacherExamQuestions(row.id),
    enabled: open && hasQuestions,
    staleTime: 60_000,
  });
  const items = React.useMemo(() => q.data?.items ?? [], [q.data]);
  const [filter, setFilter] = React.useState<Filter>("all");
  const [subject, setSubject] = React.useState<string>("");
  const subjects = React.useMemo(() => [...new Set(items.map((i) => i.subject))], [items]);
  const shown = items.filter(
    (i) => (filter === "all" || i.result === filter) && (!subject || i.subject === subject),
  );
  const drops = React.useMemo(() => halfDrop(items), [items]);
  const pctl = percentile(row);
  const counts = {
    all: items.length,
    yanlis: items.filter((i) => i.result === "yanlis").length,
    bos: items.filter((i) => i.result === "bos").length,
    dogru: items.filter((i) => i.result === "dogru").length,
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[92vh] max-w-5xl flex-col overflow-hidden p-0"
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4">
          <DialogTitle className="pr-8 text-base leading-snug">{row.title}</DialogTitle>
          <DialogDescription>
            {row.section_label} · {fmtTRDate(row.exam_date)} · {row.total_questions} soru
          </DialogDescription>
          {studentId != null ? (
            <div className="pt-2">
              <ExamShareMenu row={row} prev={prev} studentId={studentId} studentName={studentName} />
            </div>
          ) : null}
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Toplam net" value={fmtNet(row.net)}>
              {prev ? (
                <span className="text-xs text-muted-foreground">
                  önceki: {fmtNet(prev.net)} ({row.net - prev.net >= 0 ? "+" : "−"}
                  {fmtNet(Math.abs(row.net - prev.net))})
                </span>
              ) : (
                <span className="text-xs text-muted-foreground">bu türde ilk deneme</span>
              )}
            </Stat>
            <Stat label="Doğru · Yanlış · Boş" value={`${row.total_correct} · ${row.total_wrong} · ${row.total_blank}`}>
              <DybBar d={row.total_correct} y={row.total_wrong} b={row.total_blank} />
            </Stat>
            <Stat label="Puan" value={row.score?.score != null ? fmtNet(row.score.score) : "—"} />
            <Stat
              label="Sıralama"
              value={row.score?.rank_overall ? row.score.rank_overall.toLocaleString("tr-TR") : "—"}
            >
              {row.score?.participants ? (
                <span className="text-xs text-muted-foreground">
                  {row.score.participants.toLocaleString("tr-TR")} katılımcı
                  {pctl != null ? ` · ilk %${String(pctl).replace(".", ",")}` : ""}
                </span>
              ) : null}
            </Stat>
          </div>

          {row.note ? (
            <p className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
              <b>Koç notu:</b> {row.note}
            </p>
          ) : null}

          {row.subjects.length ? (
            <ExamSection title="Ders bazında sonuç" description="Son sütun: önceki aynı tür denemeye göre net farkı.">
              <SubjectTable row={row} prev={prev} />
            </ExamSection>
          ) : null}

          {!hasQuestions ? (
            <p className="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-muted-foreground">
              Bu deneme elle girildi — soru bazlı tablo ve test içi ilerleyiş yalnız PDF&apos;ten
              aktarılan denemelerde görünür.
            </p>
          ) : q.isLoading ? (
            <p className="text-sm text-muted-foreground">Sorular yükleniyor…</p>
          ) : (
            <>
              {drops.length ? (
                <ExamSection
                  icon={TimerReset}
                  title="Test içinde ilerleyiş"
                  description="Her dersin ilk yarısındaki ve ikinci yarısındaki doğruluk. İkinci yarıda belirgin düşüş (20 puan ve üstü) süre yetmemesi ya da dikkat dağılmasına işaret edebilir."
                >
                  <ul className="space-y-2">
                    {drops.map((d) => {
                      const diff = Math.round((d.second - d.first) * 100);
                      const warn = diff <= -20;
                      return (
                        <li key={d.subject} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                          <span className="min-w-40 font-medium text-foreground">{d.subject}</span>
                          <span className="tabular-nums text-muted-foreground">
                            ilk yarı %{Math.round(d.first * 100)} → ikinci yarı %{Math.round(d.second * 100)}
                          </span>
                          {warn ? (
                            <span className="rounded bg-amber-600 px-1.5 py-0.5 text-[11px] font-semibold text-white">
                              sona doğru düşüş ({diff})
                            </span>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </ExamSection>
              ) : null}

              <ExamSection
                icon={ListChecks}
                title="Soru soru"
                description="Karnede yazan konu ve sistemin bağladığı müfredat konusu. Yanlış ya da boş soruları süzerek seansta birlikte bakabilirsin."
                actions={
                  subjects.length > 1 ? (
                    <select
                      value={subject}
                      onChange={(e) => setSubject(e.target.value)}
                      aria-label="Ders süzgeci"
                      className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                    >
                      <option value="">Tüm dersler</option>
                      {subjects.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  ) : null
                }
              >
                <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Sonuç süzgeci">
                  {(["all", "yanlis", "bos", "dogru"] as Filter[]).map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => setFilter(f)}
                      aria-pressed={filter === f}
                      className={cn(
                        "rounded-full border px-2.5 py-1 text-xs font-medium",
                        filter === f
                          ? "border-cyan-700 bg-cyan-700 text-white"
                          : "border-border bg-background text-foreground hover:bg-muted",
                      )}
                    >
                      {f === "all" ? "Tümü" : RESULT_LABEL[f]} ({counts[f]})
                    </button>
                  ))}
                </div>
                {shown.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Bu süzgeçte soru yok.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[720px] text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-xs text-muted-foreground">
                          <th className="py-2 pr-2 font-medium">Ders</th>
                          <th className="px-2 py-2 font-medium">No</th>
                          <th className="px-2 py-2 font-medium">Konu (karnede)</th>
                          <th className="px-2 py-2 font-medium">Müfredat konusu</th>
                          <th className="px-2 py-2 text-center font-medium">Cevap anahtarı</th>
                          <th className="px-2 py-2 text-center font-medium">Öğrenci</th>
                          <th className="py-2 pl-2 font-medium">Sonuç</th>
                        </tr>
                      </thead>
                      <tbody>
                        {shown.map((i, idx) => (
                          <tr key={`${i.subject}-${i.question_no}-${idx}`} className="border-b border-border/60 align-top last:border-0">
                            <td className="py-1.5 pr-2 text-xs text-muted-foreground">{i.subject}</td>
                            <td className="px-2 py-1.5 tabular-nums">{i.question_no ?? "—"}</td>
                            <td className="px-2 py-1.5">{i.topic_label ?? "—"}</td>
                            <td className="px-2 py-1.5 text-xs">
                              {i.topic_name ?? <span className="text-amber-700 dark:text-amber-400">bağlanmadı</span>}
                            </td>
                            <td className="px-2 py-1.5 text-center font-medium">{i.correct_answer ?? "—"}</td>
                            <td className="px-2 py-1.5 text-center font-medium">{i.student_answer ?? "—"}</td>
                            <td className="py-1.5 pl-2">
                              <span className={cn("rounded px-1.5 py-0.5 text-[11px] font-semibold", RESULT_TONE[i.result] ?? "bg-muted")}>
                                {RESULT_LABEL[i.result] ?? i.result}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </ExamSection>
              <DistractorPanel
                examId={row.id}
                source={
                  parentStudentId != null
                    ? { kind: "parent", studentId: parentStudentId }
                    : studentId == null
                      ? { kind: "student" }
                      : { kind: "teacher", studentId }
                }
                enabled={open && hasQuestions}
              />
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Stat({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-background p-3">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="text-xl font-semibold tabular-nums">{value}</span>
      {children}
    </div>
  );
}
