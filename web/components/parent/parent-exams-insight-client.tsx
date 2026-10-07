"use client";

/**
 * Veli — Deneme Analizi (2026-10-02): koç ve öğrenciyle AYNI sekmeler, salt okuma.
 *
 * Genel Bakış · Net Gelişimi · Konu Analizi · Sınav Davranışı · Gelişim ve Hedef ·
 * Puan Tahmini · Tüm Denemeler. Gizlilik: koça özel not ve koçun öğrenciye
 * yazdığı not veliye gösterilmez; çeldirici analizinde diğer öğrencilerle kıyas
 * kapalıdır (yalnız çocuğun kendi işaretleme eğilimi).
 * Rota'nın Yorumu (yapay zekâ anlatımı) çocuk sayfasında kalır.
 */
import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, Eye, MessageSquarePlus, Sparkles } from "lucide-react";

import { DemoHint } from "@/components/demos/demo-hint";
import { ScoreEstimatePanel } from "@/components/shared/exam-faz3";
import { ExamProgressReport } from "@/components/shared/exam-progress-report";
import { ExamTopicAnalysis } from "@/components/shared/exam-topic-analysis";
import {
  BehaviorTab,
  OverviewTab,
  ProgressTab,
  previousExam,
} from "@/components/teacher/exams/exam-analytics";
import { ExamDetailDialog } from "@/components/teacher/exams/exam-detail-dialog";
import { Button } from "@/components/ui/button";
import { getParentExams, parentP2Keys } from "@/lib/api/parent";
import { fmtNet, fmtTRDate } from "@/lib/exam-format";
import type { ExamResultRow } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";
import { examSeriesOptions, rowSeries } from "@/lib/exam-format";

const SECTION_TONE: Record<string, string> = {
  lgs: "bg-cyan-50 text-cyan-800 dark:bg-cyan-500/15 dark:text-cyan-200",
  tyt: "bg-violet-50 text-violet-800 dark:bg-violet-500/15 dark:text-violet-200",
  ayt_say: "bg-emerald-50 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200",
  ayt_ea: "bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200",
  ayt_soz: "bg-rose-50 text-rose-800 dark:bg-rose-500/15 dark:text-rose-200",
  ayt_dil: "bg-sky-50 text-sky-800 dark:bg-sky-500/15 dark:text-sky-200",
};

type Tab = "overview" | "progress" | "topics" | "behavior" | "report" | "score" | "list";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Genel Bakış" },
  { key: "progress", label: "Net Gelişimi" },
  { key: "topics", label: "Konu Analizi" },
  { key: "behavior", label: "Sınav Davranışı" },
  { key: "report", label: "Gelişim ve Hedef" },
  { key: "score", label: "Puan Tahmini" },
  { key: "list", label: "Tüm Denemeler" },
];

export function ParentExamsInsightClient({ studentId, studentName }: { studentId: number; studentName?: string }) {
  const examsQ = useQuery({ queryKey: parentP2Keys.exams(studentId), queryFn: () => getParentExams(studentId) });
  const rows = React.useMemo(() => examsQ.data?.rows ?? [], [examsQ.data]);
  const [tab, setTab] = React.useState<Tab>("overview");
  const [detailId, setDetailId] = React.useState<number | null>(null);

  const sectionsInfo = React.useMemo(() => examSeriesOptions(rows), [rows]);
  const [selSection, setSelSection] = React.useState<string | null>(null);
  const activeSection =
    selSection && sectionsInfo.some((s) => s.value === selSection) ? selSection : sectionsInfo[0]?.value ?? null;
  const sectionRows = React.useMemo(() => rows.filter((r) => rowSeries(r) === activeSection), [rows, activeSection]);
  const detailRow = detailId != null ? rows.find((r) => r.id === detailId) ?? null : null;
  const detailPrev = detailRow ? previousExam(rows.filter((r) => rowSeries(r) === rowSeries(detailRow)), detailRow) : null;

  return (
    <div className="space-y-5">
      <div>
        <Link
          href={`/parent/students/${studentId}`}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" aria-hidden /> Geri
        </Link>
        <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight">Deneme Analizi</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {studentName ? `${studentName} için ` : ""}deneme sonuçları, gelişim, hedef ve tahmini puan. Netler
          sınav türüne göre hesaplanır; farklı türler ayrı ölçekte olduğu için analizler seçili türe göredir.
        </p>
        <DemoHint contextKey="ai-insight" role="parent" className="mt-2" />
      </div>

      <div className="flex flex-wrap gap-2">
        <Link
          href={`/parent/students/${studentId}`}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-2xl border border-cyan-200 bg-cyan-50/40 p-3 hover:bg-cyan-50 dark:border-cyan-500/30 dark:bg-cyan-500/10"
        >
          <Sparkles className="size-5 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
          <span className="text-sm text-cyan-950 dark:text-cyan-100">
            <span className="font-semibold">Rota&apos;nın Yorumu</span> — deneme sonuçlarının yapay zekâ
            anlatımı çocuğunuzun sayfasında; okuyabilir ya da sesli dinleyebilirsiniz.
          </span>
        </Link>
        <Link
          href={`/parent/support?child=${studentId}&category=exam_comment`}
          className="inline-flex items-center gap-1.5 self-center rounded-lg border border-[#117A86]/40 px-3 py-2 text-xs font-semibold text-[#117A86] dark:text-teal-300 hover:bg-[#117A86]/5 dark:text-cyan-300"
        >
          <MessageSquarePlus className="size-3.5" aria-hidden /> Koça deneme hakkında sor
        </Link>
      </div>

      {examsQ.isLoading ? (
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Henüz deneme sonucu girilmemiş.
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border">
            <div role="tablist" aria-label="Deneme analizi bölümleri" className="-mb-px flex flex-wrap gap-1">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.key}
                  onClick={() => setTab(t.key)}
                  className={cn(
                    "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                    tab === t.key
                      ? "border-cyan-700 text-foreground dark:border-cyan-400"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {tab !== "list" && tab !== "score" && sectionsInfo.length > 1 ? (
              <label className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                Deneme serisi
                <select
                  value={activeSection ?? ""}
                  onChange={(e) => setSelSection(e.target.value)}
                  aria-label="Deneme serisi"
                  className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {sectionsInfo.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label} ({s.count})
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>

          <div role="tabpanel">
            {tab === "overview" ? (
              <OverviewTab rows={sectionRows} studentId={null} onOpenDetail={(r) => setDetailId(r.id)} />
            ) : tab === "progress" ? (
              <ProgressTab rows={sectionRows} />
            ) : tab === "topics" ? (
              <ExamTopicAnalysis parentStudentId={studentId} section={activeSection} />
            ) : tab === "behavior" ? (
              <BehaviorTab rows={sectionRows} />
            ) : tab === "report" ? (
              <ExamProgressReport
                source={{ kind: "parent", studentId }}
                section={activeSection}
                studentName={studentName}
              />
            ) : tab === "score" ? (
              <ScoreEstimatePanel source={{ kind: "parent", studentId }} />
            ) : (
              <ul className="space-y-2">
                {rows.map((row) => (
                  <ParentExamRow key={row.id} row={row} onOpenDetail={() => setDetailId(row.id)} />
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      {detailRow ? (
        <ExamDetailDialog
          row={detailRow}
          prev={detailPrev}
          studentId={null}
          parentStudentId={studentId}
          open
          onOpenChange={(v) => {
            if (!v) setDetailId(null);
          }}
        />
      ) : null}
    </div>
  );
}

function ParentExamRow({ row, onOpenDetail }: { row: ExamResultRow; onOpenDetail: () => void }) {
  const [open, setOpen] = React.useState(false);
  return (
    <li className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="w-20 shrink-0 text-center">
          <p className="whitespace-nowrap text-2xl font-semibold leading-none tabular-nums">{fmtNet(row.net)}</p>
          <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">net</p>
        </div>
        <div className="min-w-0 flex-1 basis-48">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={onOpenDetail} className="break-words text-left font-medium hover:underline">
              {row.title}
            </button>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                SECTION_TONE[row.section] ?? "bg-muted text-muted-foreground",
              )}
            >
              {row.section_label}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {fmtTRDate(row.exam_date)} · <span className="text-emerald-700 dark:text-emerald-400">{row.total_correct}D</span>{" "}
            <span className="text-rose-700 dark:text-rose-400">{row.total_wrong}Y</span> {row.total_blank}B ·{" "}
            {row.total_questions} soru
            {row.averages?.total != null ? ` · ${row.averages.label.toLocaleLowerCase("tr-TR")} ${fmtNet(row.averages.total)}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={onOpenDetail} aria-label="Deneme detayı">
            <Eye className="size-4 text-cyan-700 dark:text-cyan-400" aria-hidden />
          </Button>
          {row.subjects.length ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setOpen((v) => !v)}
              aria-label={open ? "Ders kırılımını gizle" : "Ders kırılımını göster"}
              aria-expanded={open}
            >
              <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} aria-hidden />
            </Button>
          ) : null}
        </div>
      </div>
      {open ? (
        <div className="mt-2 flex flex-wrap gap-1.5 border-t border-border/60 pt-2">
          {row.subjects.map((s) => (
            <span key={s.name} className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
              {s.name}: <span className="font-semibold text-foreground">{fmtNet(s.net)}</span>
            </span>
          ))}
        </div>
      ) : null}
    </li>
  );
}
