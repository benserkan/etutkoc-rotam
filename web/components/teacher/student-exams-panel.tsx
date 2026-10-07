"use client";

import { GuideHint } from "@/components/guide/guide-hint";
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Mail,
  MailCheck,
  ChevronDown,
  Eye,
  FileCog,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";

import { ArchiveExamWrongsButton } from "@/components/shared/archive-exam-wrongs-button";
import { ExamAddActions } from "@/components/shared/exam-add-actions";
import { ExamImportDialog } from "@/components/shared/exam-import-dialog";
import {
  PeriodContextNote,
  PeriodSwitcher,
} from "@/components/shared/period-switcher";
import { ExamTopicAnalysis } from "@/components/shared/exam-topic-analysis";
import { ExamParentAnnounceDialog } from "@/components/teacher/exam-parent-announce-dialog";
import {
  BehaviorTab,
  OverviewTab,
  ProgressTab,
  previousExam,
} from "@/components/teacher/exams/exam-analytics";
import { examSeriesOptions, rowSeries } from "@/lib/exam-format";
import { ExamDetailDialog } from "@/components/teacher/exams/exam-detail-dialog";
import { ExamStudentShareButton } from "@/components/teacher/exams/exam-student-share";
import { ScoreEstimatePanel } from "@/components/shared/exam-faz3";
import { ExamProgressReport } from "@/components/shared/exam-progress-report";
import { examProgressKeys, getExamShares } from "@/lib/api/exam-progress";
import type { ExamShareInfo } from "@/lib/types/exam-progress";

import { getTeacherStudentExams, teacherKeys } from "@/lib/api/teacher";
import {
  useCreateExam,
  useDeleteExam,
  useSetExamScope,
  useUpdateExam,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  ExamCreateBody,
  ExamResultRow,
  ExamSectionValue,
  ExamSubjectInput,
  StudentExamListResponse,
} from "@/lib/types/teacher";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

// Sınav türü → sabit ton (Tailwind purge güvenli)
const SECTION_TONE: Record<ExamSectionValue, string> = {
  lgs: "border-sky-200 bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
  tyt: "border-indigo-200 bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
  ayt_say: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  ayt_ea: "border-amber-200 bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  ayt_soz: "border-violet-200 bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:border-violet-500/30 dark:text-violet-200",
  ayt_dil: "border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
  okul: "border-slate-200 bg-slate-100 text-slate-700 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-200",
  maarif_1: "border-teal-200 bg-teal-50 text-teal-700 dark:bg-teal-500/10 dark:border-teal-500/30 dark:text-teal-200",
  maarif_2: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700 dark:bg-fuchsia-500/10 dark:border-fuchsia-500/30 dark:text-fuchsia-200",
  maarif_9: "border-lime-200 bg-lime-50 text-lime-800 dark:bg-lime-500/10 dark:border-lime-500/30 dark:text-lime-200",
  maarif_10: "border-sky-200 bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
  maarif_11: "border-blue-200 bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-200",
};

function sectionPenalty(section: ExamSectionValue): number {
  return section === "lgs" ? 3 : 4;
}

function computeNet(correct: number, wrong: number, section: ExamSectionValue): number {
  const raw = correct - wrong / sectionPenalty(section);
  return Math.round(Math.max(raw, 0) * 100) / 100;
}

function formatTRDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}.${y}`;
}

type ExamTab = "overview" | "progress" | "topics" | "behavior" | "report" | "score" | "list";

const EXAM_TABS: { key: ExamTab; label: string; hint: string }[] = [
  { key: "overview", label: "Genel Bakış", hint: "Son deneme, puan, öne çıkanlar" },
  { key: "progress", label: "Net Gelişimi", hint: "Ders ders net değişimi" },
  { key: "topics", label: "Konu Analizi", hint: "Net fırsatı, zayıf konular" },
  { key: "behavior", label: "Sınav Davranışı", hint: "Boş, yanlış, işaretleme eğilimi" },
  { key: "report", label: "Gelişim Raporu", hint: "Hedef net, otomatik yorum, aksiyon planı" },
  { key: "score", label: "Puan Tahmini", hint: "Son netlerden yaklaşık TYT/AYT/LGS puanı" },
  { key: "list", label: "Tüm Denemeler", hint: "Tüm denemeler ve işlemler" },
];

interface Props {
  studentId: number;
  studentName?: string | null;
}

export function StudentExamsPanel({ studentId, studentName }: Props) {
  // P3: varsayılan GÜNCEL dönem — geçen yılın denemeleri "bu yılın gidişatı"
  // tablosunu bozmaz; seçiciyle geri getirilir (veri hiçbir zaman silinmez).
  const [period, setPeriod] = React.useState<string | undefined>(undefined);
  const q = useQuery<StudentExamListResponse>({
    queryKey: teacherKeys.studentExams(studentId, period),
    queryFn: () => getTeacherStudentExams(studentId, period),
    staleTime: 30_000,
  });
  const periodMeta = q.data?.period ?? null;
  const [addOpen, setAddOpen] = React.useState(false);
  const [importOpen, setImportOpen] = React.useState(false);
  const [importFile, setImportFile] = React.useState<File | null>(null);
  const [tab, setTab] = React.useState<ExamTab>("overview");
  const [detailId, setDetailId] = React.useState<number | null>(null);
  const data = q.data;
  const sharesQ = useQuery({
    queryKey: examProgressKeys.shares({ kind: "teacher", studentId }),
    queryFn: () => getExamShares({ kind: "teacher", studentId }),
    staleTime: 30_000,
  });
  const shares = sharesQ.data?.shares ?? {};

  // Sınav türleri farklı ölçekte (TYT/120·AYT/80·LGS) ve AYNI türde genel deneme
  // ile branş denemesi (90 soru vs 20 soru) kıyaslanamaz → analizler tek SERİYE
  // göre hesaplanır (2026-10-06). Genel deneme serisi varsayılan seçili.
  const rows = React.useMemo(() => data?.rows ?? [], [data]);
  const sectionsInfo = React.useMemo(() => examSeriesOptions(rows), [rows]);
  const [selSection, setSelSection] = React.useState<string | null>(null);
  const activeSeries =
    selSection && sectionsInfo.some((s) => s.value === selSection)
      ? selSection
      : sectionsInfo[0]?.value ?? null;
  const sectionRows = React.useMemo(
    () => rows.filter((r) => rowSeries(r) === activeSeries),
    [rows, activeSeries],
  );
  // detay penceresi: satır + aynı seride bir önceki deneme
  const detailRow = detailId != null ? rows.find((r) => r.id === detailId) ?? null : null;
  const detailPrev = detailRow
    ? previousExam(rows.filter((r) => rowSeries(r) === rowSeries(detailRow)), detailRow)
    : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold">Deneme Analizi</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Netler sınav türüne göre hesaplanır (LGS: doğru − yanlış/3 · YKS: doğru − yanlış/4).
            Farklı türler ve aynı türün genel denemesiyle branş denemesi (ör. 90 soruluk LGS
            ile 20 soruluk Matematik branşı) ayrı ölçekte olduğu için analizler seçili seriye göredir.
          </p>
        </div>
      </div>

      <GuideHint module="Denemeler" />

      <ExamAddActions
        onImport={(f) => {
          setImportFile(f);
          setImportOpen(true);
        }}
        onManual={() => setAddOpen(true)}
        pdfCount={(data?.rows ?? []).filter((r) => r.import_source === "pdf_import").length}
        total={data?.rows.length ?? 0}
      />

      <ExamImportDialog
        open={importOpen}
        onOpenChange={(v) => {
          setImportOpen(v);
          if (!v) setImportFile(null);
        }}
        studentId={studentId}
        initialFile={importFile}
      />

      <PeriodSwitcher meta={periodMeta} value={period} onChange={setPeriod} />
      <PeriodContextNote meta={periodMeta} value={period} />

      {q.isLoading && !data ? (
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      ) : !data || data.rows.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              {period && period !== "current"
                ? "Bu dönemde deneme sonucu yok."
                : "Henüz deneme sonucu girilmemiş."}
            </p>
            <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
              <Plus className="size-4" aria-hidden />
              İlk denemeyi ekle
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border">
            <div role="tablist" aria-label="Deneme analizi bölümleri" className="-mb-px flex flex-wrap gap-1">
              {EXAM_TABS.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.key}
                  onClick={() => setTab(t.key)}
                  title={t.hint}
                  className={cn(
                    "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                    tab === t.key
                      ? "border-cyan-700 text-foreground dark:border-cyan-400"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t.label}
                  {t.key === "list" ? (
                    <span className="ml-1.5 rounded-full bg-muted px-1.5 text-[11px] tabular-nums">
                      {rows.length}
                    </span>
                  ) : null}
                </button>
              ))}
            </div>
            {tab !== "list" && tab !== "score" && sectionsInfo.length > 1 ? (
              <label className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                Deneme serisi
                <select
                  value={activeSeries ?? ""}
                  onChange={(e) => setSelSection(e.target.value)}
                  aria-label="Deneme serisi"
                  className={cn(
                    "h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  )}
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
              <OverviewTab
                rows={sectionRows}
                studentId={studentId}
                studentName={studentName}
                onOpenDetail={(r) => setDetailId(r.id)}
              />
            ) : tab === "progress" ? (
              <ProgressTab rows={sectionRows} />
            ) : tab === "topics" ? (
              <ExamTopicAnalysis studentId={studentId} section={activeSeries} period={period} />
            ) : tab === "behavior" ? (
              <BehaviorTab rows={sectionRows} />
            ) : tab === "score" ? (
              <ScoreEstimatePanel source={{ kind: "teacher", studentId }} />
            ) : tab === "report" ? (
              <ExamProgressReport
                source={{ kind: "teacher", studentId }}
                section={activeSeries}
                period={period}
                studentName={studentName}
              />
            ) : (
              <ul className="space-y-2">
                {data.rows.map((row) => (
                  <ExamRow
                    key={row.id}
                    row={row}
                    studentId={studentId}
                    sectionOptions={data.section_options ?? []}
                    share={shares[String(row.id)] ?? null}
                    onOpenDetail={() => setDetailId(row.id)}
                  />
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
          studentId={studentId}
          studentName={studentName}
          open
          onOpenChange={(v) => {
            if (!v) setDetailId(null);
          }}
        />
      ) : null}

      <p className="text-[11px] text-muted-foreground leading-relaxed">
        Deneme adı, tarihi ve netler öğrenci ve veli panelinde de görünür; koça özel
        notlar paylaşılmaz. Öğrenciye özel değerlendirme için “Öğrenciyle paylaş”.
      </p>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Deneme sonucu ekle</DialogTitle>
          </DialogHeader>
          <ExamForm
            studentId={studentId}
            sectionOptions={data?.section_options ?? []}
            onDone={() => setAddOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Genel / branş işareti — sistem tanır, koç düzeltir (2026-10-06). */
function ExamScopeSelect({ row }: { row: ExamResultRow }) {
  const mut = useSetExamScope();
  const isBranch = row.scope === "brans";
  const value = row.scope_forced ? (row.scope ?? "genel") : "auto";
  return (
    <select
      value={value}
      disabled={mut.isPending}
      onChange={(e) =>
        mut.mutate({ examId: row.id, scope: e.target.value as "auto" | "genel" | "brans" })
      }
      aria-label="Deneme kapsamı (genel ya da branş)"
      title="Netler yalnız aynı kapsamdaki denemelerle kıyaslanır. Sistem soru sayısından tanır; yanlışsa buradan düzelt."
      className={cn(
        "h-6 rounded border px-1 text-[11px] font-medium",
        isBranch
          ? "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-200"
          : "border-border bg-background text-foreground",
      )}
    >
      <option value="auto">
        {row.scope_forced
          ? "Sisteme bırak"
          : `${isBranch ? `${row.scope_subject ?? "Branş"} branş` : "Genel deneme"} (otomatik)`}
      </option>
      <option value="genel">Genel deneme</option>
      <option value="brans">
        {isBranch && row.scope_subject ? `${row.scope_subject} branş` : "Branş denemesi"}
      </option>
    </select>
  );
}

function ExamRow({
  row,
  studentId,
  sectionOptions,
  share,
  onOpenDetail,
}: {
  row: ExamResultRow;
  studentId: number;
  sectionOptions: StudentExamListResponse["section_options"];
  share: ExamShareInfo | null;
  onOpenDetail: () => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [editOpen, setEditOpen] = React.useState(false);
  const [importEditOpen, setImportEditOpen] = React.useState(false);
  // Veliye duyur: window.confirm YERİNE önizle-düzenle-gönder modalı
  // (koç isteği 2026-09-10) — koç neyin gideceğini görmeden onaylamasın.
  const [announceOpen, setAnnounceOpen] = React.useState(false);
  const del = useDeleteExam();
  const hasSubjects = row.subjects.length > 0;

  function onDelete() {
    if (
      !window.confirm(
        `"${row.title}" (${formatTRDate(row.exam_date)}) denemesini silmek istiyor musunuz?`,
      )
    ) {
      return;
    }
    del.mutate({ examId: row.id });
  }

  return (
    <li>
      <Card>
        <CardContent className="p-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {/* Net kutusu: "120.00" 6 haneye kadar çıkar — dar sabit genişlikte
                başlığa yapışıyordu (saha, 2026-09-05). */}
            <div className="text-center shrink-0 w-24">
              <p className="text-2xl font-semibold tabular-nums leading-none whitespace-nowrap">
                {row.net.toFixed(2)}
              </p>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground mt-0.5">
                net
              </p>
            </div>
            <div className="min-w-0 flex-1 basis-48">
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={onOpenDetail}
                  className="text-left font-medium break-words hover:underline"
                  title="Deneme detayını aç"
                >
                  {row.title}
                </button>
                <span
                  className={cn(
                    "inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border",
                    SECTION_TONE[row.section],
                  )}
                >
                  {row.section_label}
                </span>
                <ExamScopeSelect row={row} />
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {formatTRDate(row.exam_date)} ·{" "}
                <span className="text-emerald-600 dark:text-emerald-300">{row.total_correct}D</span>{" "}
                <span className="text-rose-600 dark:text-rose-300">{row.total_wrong}Y</span>{" "}
                <span className="text-muted-foreground">{row.total_blank}B</span>
                {" · "}
                {row.total_questions} soru
              </p>
              {row.note ? (
                <p className="text-xs text-muted-foreground mt-1 italic">
                  {row.note}
                </p>
              ) : null}
            </div>
            {/* dar ekranda işlemler alt satıra iner (390px'te satırı taşırıyordu) */}
            <div className="flex w-full flex-wrap items-center justify-end gap-1 sm:w-auto sm:shrink-0">
              <Button
                variant="ghost"
                size="sm"
                onClick={onOpenDetail}
                aria-label="Deneme detayı"
                title="Deneme detayı: karne, soru soru tablo, yazdır ve paylaş"
              >
                <Eye className="size-4 text-cyan-700 dark:text-cyan-400" aria-hidden />
              </Button>
              {hasSubjects ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setOpen((v) => !v)}
                  aria-label={open ? "Ders kırılımını gizle" : "Ders kırılımını göster"}
                  aria-expanded={open}
                >
                  <ChevronDown
                    className={cn("size-4 transition-transform", open && "rotate-180")}
                    aria-hidden
                  />
                </Button>
              ) : null}
              {row.import_source === "pdf_import" ? (
                <ArchiveExamWrongsButton
                  examId={row.id}
                  studentId={studentId}
                  wrongCount={row.total_wrong}
                  compact
                />
              ) : null}
              {row.import_source === "pdf_import" ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setImportEditOpen(true)}
                  aria-label="İçe aktarılan satırları düzenle"
                  title="Soru satırlarını düzelt (konu/sonuç) — net yeniden hesaplanır, kredi düşmez"
                >
                  <FileCog className="size-4 text-violet-600 dark:text-violet-300" aria-hidden />
                </Button>
              ) : null}
              <ExamStudentShareButton row={row} share={share} />
              {/* Veliye duyur — duyurulduysa düğme "Duyuruldu"ya döner (2026-09-05) */}
              {row.parent_notified_at ? (
                /* Duyurulmuş olsa da TIKLANABİLİR: koç gönderdiği maili
                   yeniden görüntüleyip PDF olarak indirebilmeli (saha
                   bulgusu 2026-09-10: "duyurulduktan sonra PDF'e
                   ulaşamıyorum"). Tekrar gönderim modalda kapalı. */
                <button
                  type="button"
                  onClick={() => setAnnounceOpen(true)}
                  className="inline-flex items-center gap-1 rounded border border-emerald-300 bg-emerald-50 px-1.5 py-1 text-[11px] font-medium text-emerald-800 hover:bg-emerald-100 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-300 dark:hover:bg-emerald-500/20"
                  title={`Veliye duyuruldu · ${formatTRDate(row.parent_notified_at.slice(0, 10))} — gönderilen maili gör / PDF olarak indir`}
                >
                  <MailCheck className="size-3.5" aria-hidden />
                  Duyuruldu
                </button>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setAnnounceOpen(true)}
                  aria-label="Sonucu veliye duyur"
                  title="Veliye gidecek maili önizle, düzenle ve gönder"
                >
                  <Mail className="size-4 text-teal-600 dark:text-teal-300" aria-hidden />
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditOpen(true)}
                aria-label="Denemeyi düzenle"
              >
                <Pencil className="size-4" aria-hidden />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={onDelete}
                disabled={del.isPending}
                aria-label="Denemeyi sil"
              >
                {del.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Trash2 className="size-4" aria-hidden />
                )}
              </Button>
            </div>
          </div>

          <ExamImportDialog
            open={importEditOpen}
            onOpenChange={setImportEditOpen}
            studentId={studentId}
            editExamId={row.id}
          />

          {/* Veliye duyur — önizle + düzenle + gönder. Yalnız açıkken mount
              edilir ki önizleme sorgusu her satır için boşuna koşmasın. */}
          {announceOpen ? (
            <ExamParentAnnounceDialog
              examId={row.id}
              studentId={studentId}
              open={announceOpen}
              onOpenChange={setAnnounceOpen}
            />
          ) : null}

          <Dialog open={editOpen} onOpenChange={setEditOpen}>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Denemeyi düzenle</DialogTitle>
              </DialogHeader>
              <ExamForm
                studentId={studentId}
                sectionOptions={sectionOptions}
                editRow={row}
                onDone={() => setEditOpen(false)}
              />
            </DialogContent>
          </Dialog>

          {open && hasSubjects ? (
            <div className="mt-3 border-t border-border pt-2">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-muted-foreground text-left">
                    <th className="font-medium py-1">Ders</th>
                    <th className="font-medium py-1 text-right">D</th>
                    <th className="font-medium py-1 text-right">Y</th>
                    <th className="font-medium py-1 text-right">B</th>
                    <th className="font-medium py-1 text-right">Net</th>
                  </tr>
                </thead>
                <tbody>
                  {row.subjects.map((s, i) => (
                    <tr key={i} className="border-t border-border/50">
                      <td className="py-1">
                        {s.name}
                        {s.unmatched ? (
                          <span
                            className="ml-1.5 inline-flex items-center rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200"
                            title="Bu satır bir Rotam dersine bağlanmadı — ad denemenin kendi başlığından geldi. 'Satırları düzelt' ile konuları bağlayınca doğru derse geçer."
                          >
                            müfredata bağlanmadı
                          </span>
                        ) : null}
                      </td>
                      <td className="py-1 text-right tabular-nums text-emerald-600 dark:text-emerald-300">
                        {s.correct}
                      </td>
                      <td className="py-1 text-right tabular-nums text-rose-600 dark:text-rose-300">
                        {s.wrong}
                      </td>
                      <td className="py-1 text-right tabular-nums text-muted-foreground">
                        {s.blank}
                      </td>
                      <td className="py-1 text-right tabular-nums font-medium">
                        {s.net.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </li>
  );
}

type FormMode = "total" | "subjects";

function ExamForm({
  studentId,
  sectionOptions,
  editRow = null,
  onDone,
}: {
  studentId: number;
  sectionOptions: StudentExamListResponse["section_options"];
  editRow?: ExamResultRow | null;
  onDone: () => void;
}) {
  const create = useCreateExam(studentId);
  const update = useUpdateExam();
  const busy = create.isPending || update.isPending;
  const today = new Date().toISOString().slice(0, 10);
  const editSubjects = !!editRow && editRow.subjects.length > 0;

  const [title, setTitle] = React.useState(editRow?.title ?? "");
  const [examDate, setExamDate] = React.useState(editRow?.exam_date ?? today);
  const [section, setSection] = React.useState<ExamSectionValue>(
    editRow?.section ?? sectionOptions[0]?.value ?? "lgs",
  );
  const [mode, setMode] = React.useState<FormMode>(editSubjects ? "subjects" : "total");
  const [correct, setCorrect] = React.useState(
    editRow && !editSubjects ? String(editRow.total_correct) : "",
  );
  const [wrong, setWrong] = React.useState(
    editRow && !editSubjects ? String(editRow.total_wrong) : "",
  );
  const [blank, setBlank] = React.useState(
    editRow && !editSubjects ? String(editRow.total_blank) : "",
  );
  const [subjects, setSubjects] = React.useState<ExamSubjectInput[]>(
    editSubjects && editRow
      ? editRow.subjects.map((s) => ({
          name: s.name, correct: s.correct, wrong: s.wrong, blank: s.blank,
        }))
      : [{ name: "", correct: 0, wrong: 0, blank: 0 }],
  );
  const [note, setNote] = React.useState(editRow?.note ?? "");
  const [error, setError] = React.useState<string | null>(null);
  // Mükerrer uyarısı (aynı ad + aynı/yakın tarih): sunucu 409 döner, koç
  // bilinçli "yine de kaydet" derse force ile tekrar gönderilir.
  const [dupWarn, setDupWarn] = React.useState<string | null>(null);

  // Canlı net önizlemesi
  const previewNet = React.useMemo(() => {
    if (mode === "total") {
      return computeNet(Number(correct) || 0, Number(wrong) || 0, section);
    }
    const tc = subjects.reduce((a, s) => a + (Number(s.correct) || 0), 0);
    const tw = subjects.reduce((a, s) => a + (Number(s.wrong) || 0), 0);
    return computeNet(tc, tw, section);
  }, [mode, correct, wrong, subjects, section]);

  function updateSubject(idx: number, patch: Partial<ExamSubjectInput>) {
    setSubjects((prev) =>
      prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)),
    );
  }
  function addSubjectRow() {
    setSubjects((prev) => [...prev, { name: "", correct: 0, wrong: 0, blank: 0 }]);
  }
  function removeSubjectRow(idx: number) {
    setSubjects((prev) => prev.filter((_, i) => i !== idx));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const t = title.trim();
    if (!t) {
      setError("Deneme adı zorunlu.");
      return;
    }
    let body: ExamCreateBody;
    if (mode === "total") {
      const c = Number(correct) || 0;
      const w = Number(wrong) || 0;
      const b = Number(blank) || 0;
      if (c + w + b <= 0) {
        setError("En az bir doğru/yanlış/boş değeri girin.");
        return;
      }
      body = {
        title: t,
        exam_date: examDate,
        section,
        total_correct: c,
        total_wrong: w,
        total_blank: b,
        note: note.trim() || null,
      };
    } else {
      const cleaned = subjects
        .map((s) => ({
          name: s.name.trim(),
          correct: Number(s.correct) || 0,
          wrong: Number(s.wrong) || 0,
          blank: Number(s.blank) || 0,
        }))
        .filter((s) => s.name.length > 0);
      if (cleaned.length === 0) {
        setError("En az bir ders satırı girin.");
        return;
      }
      const total = cleaned.reduce(
        (a, s) => a + s.correct + s.wrong + s.blank,
        0,
      );
      if (total <= 0) {
        setError("Ders satırlarında en az bir değer girin.");
        return;
      }
      body = {
        title: t,
        exam_date: examDate,
        section,
        subjects: cleaned,
        note: note.trim() || null,
      };
    }
    if (editRow) {
      update.mutate({ examId: editRow.id, body }, { onSuccess: () => onDone() });
    } else {
      setDupWarn(null);
      create.mutate(
        { body },
        {
          onSuccess: () => onDone(),
          onError: (err) => {
            if (err.status === 409 && err.detail?.code === "duplicate_exam") {
              setDupWarn(err.message);
            }
          },
        },
      );
    }
  }

  function submitForce() {
    // Aynı gövdeyi force ile yeniden gönder (koç kararı: ayrı deneme)
    const t = title.trim();
    const base = { title: t, exam_date: examDate, section, note: note.trim() || null, force: true };
    const body: ExamCreateBody =
      mode === "total"
        ? { ...base, total_correct: Number(correct) || 0, total_wrong: Number(wrong) || 0, total_blank: Number(blank) || 0 }
        : {
            ...base,
            subjects: subjects
              .map((s) => ({ name: s.name.trim(), correct: Number(s.correct) || 0, wrong: Number(s.wrong) || 0, blank: Number(s.blank) || 0 }))
              .filter((s) => s.name.length > 0),
          };
    setDupWarn(null);
    create.mutate({ body }, { onSuccess: () => onDone() });
  }

  return (
    <form onSubmit={submit} className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
      <div className="space-y-1">
        <Label htmlFor="ex-title">Deneme adı</Label>
        <Input
          id="ex-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="örn. 3D Yayınları LGS Deneme 5"
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="ex-date">Tarih</Label>
          <Input
            id="ex-date"
            type="date"
            value={examDate}
            onChange={(e) => setExamDate(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="ex-section">Sınav türü</Label>
          <select
            id="ex-section"
            value={section}
            onChange={(e) => setSection(e.target.value as ExamSectionValue)}
            className={cn(
              "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            {sectionOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Mod seçici */}
      <div className="inline-flex rounded-md border border-border p-0.5 text-xs">
        <button
          type="button"
          onClick={() => setMode("total")}
          className={cn(
            "px-3 py-1 rounded transition-colors",
            mode === "total"
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Toplam
        </button>
        <button
          type="button"
          onClick={() => setMode("subjects")}
          className={cn(
            "px-3 py-1 rounded transition-colors",
            mode === "subjects"
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Ders kırılımı
        </button>
      </div>

      {mode === "total" ? (
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1">
            <Label htmlFor="ex-c" className="text-emerald-700 dark:text-emerald-300">Doğru</Label>
            <Input
              id="ex-c"
              type="number"
              min={0}
              value={correct}
              onChange={(e) => setCorrect(e.target.value)}
              placeholder="0"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ex-w" className="text-rose-700 dark:text-rose-300">Yanlış</Label>
            <Input
              id="ex-w"
              type="number"
              min={0}
              value={wrong}
              onChange={(e) => setWrong(e.target.value)}
              placeholder="0"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ex-b">Boş</Label>
            <Input
              id="ex-b"
              type="number"
              min={0}
              value={blank}
              onChange={(e) => setBlank(e.target.value)}
              placeholder="0"
            />
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-[1fr_3rem_3rem_3rem_1.75rem] gap-1.5 text-[10px] uppercase tracking-wide text-muted-foreground px-0.5">
            <span>Ders</span>
            <span className="text-center">D</span>
            <span className="text-center">Y</span>
            <span className="text-center">B</span>
            <span />
          </div>
          {subjects.map((s, i) => (
            <div
              key={i}
              className="grid grid-cols-[1fr_3rem_3rem_3rem_1.75rem] gap-1.5 items-center"
            >
              <Input
                value={s.name}
                onChange={(e) => updateSubject(i, { name: e.target.value })}
                placeholder="Matematik"
                className="h-8"
              />
              <Input
                type="number"
                min={0}
                value={s.correct || ""}
                onChange={(e) => updateSubject(i, { correct: Number(e.target.value) })}
                className="h-8 px-1 text-center"
              />
              <Input
                type="number"
                min={0}
                value={s.wrong || ""}
                onChange={(e) => updateSubject(i, { wrong: Number(e.target.value) })}
                className="h-8 px-1 text-center"
              />
              <Input
                type="number"
                min={0}
                value={s.blank || ""}
                onChange={(e) => updateSubject(i, { blank: Number(e.target.value) })}
                className="h-8 px-1 text-center"
              />
              <button
                type="button"
                onClick={() => removeSubjectRow(i)}
                disabled={subjects.length <= 1}
                className="text-muted-foreground hover:text-rose-600 disabled:opacity-30"
                aria-label="Ders satırını kaldır"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={addSubjectRow}>
            <Plus className="size-4" aria-hidden />
            Ders ekle
          </Button>
        </div>
      )}

      <div className="space-y-1">
        <Label htmlFor="ex-note">Not (opsiyonel)</Label>
        <textarea
          id="ex-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          rows={2}
          placeholder="Deneme hakkında kısa not..."
          className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring/30 resize-y"
        />
      </div>

      <div className="rounded-md bg-muted px-3 py-2 text-sm flex items-center justify-between">
        <span className="text-muted-foreground">Hesaplanan net</span>
        <span className="text-lg font-semibold tabular-nums">
          {previewNet.toFixed(2)}
        </span>
      </div>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {dupWarn ? (
        <div
          role="alert"
          className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200"
        >
          <p>
            <b>Mükerrer olabilir:</b> {dupWarn} Aynı denemeyse kaydetme; listedeki
            kaydı düzenle. Gerçekten ayrı bir denemeyse yine de kaydedebilirsin.
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mt-2"
            disabled={busy}
            onClick={submitForce}
          >
            Ayrı deneme olarak yine de kaydet
          </Button>
        </div>
      ) : null}

      <div className="flex items-center justify-end gap-2 pt-1">
        <Button type="button" variant="ghost" onClick={onDone} disabled={busy}>
          İptal
        </Button>
        <Button type="submit" disabled={busy}>
          {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {editRow ? "Güncelle" : "Kaydet"}
        </Button>
      </div>
    </form>
  );
}

