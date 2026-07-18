"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, FileUp, TrendingDown, TrendingUp } from "lucide-react";

import { ExamImportDialog } from "@/components/shared/exam-import-dialog";
import { ExamTopicAnalysis } from "@/components/shared/exam-topic-analysis";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getStudentExams, studentKeys } from "@/lib/api/student";
import type { StudentExamsResponse } from "@/lib/types/student";
import type { ExamResultRow, ExamSectionValue } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

/**
 * Denemelerim (Faz 2b) — öğrenci yüzeyi: deneme listesi (salt-okuma) +
 * PDF'ten aktarma (kredi/paket KOÇUN — YSA deseni) + konu × deneme analizi
 * (paylaşılan ExamTopicAnalysis, öğrenci ucu). Düzeltme/silme koçta.
 */

const SECTION_TONE: Record<string, string> = {
  lgs: "border-cyan-200 bg-cyan-50 text-cyan-700 dark:bg-cyan-500/10 dark:border-cyan-500/30 dark:text-cyan-200",
  tyt: "border-indigo-200 bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
  ayt_say: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  ayt_ea: "border-amber-200 bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  ayt_soz: "border-violet-200 bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:border-violet-500/30 dark:text-violet-200",
  ayt_dil: "border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
  okul: "border-slate-200 bg-slate-100 text-slate-700 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-200",
};

function formatTRDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}.${y}`;
}

export function StudentExamsClient({ initial }: { initial: StudentExamsResponse }) {
  const q = useQuery<StudentExamsResponse>({
    queryKey: studentKeys.exams(),
    queryFn: getStudentExams,
    initialData: initial,
    staleTime: 30_000,
  });
  const [importOpen, setImportOpen] = React.useState(false);
  const rows = React.useMemo(() => q.data?.rows ?? [], [q.data]);

  // türler farklı ölçekte (TYT/120 · AYT/80 · LGS) → özet + analiz TEK türe göre
  const sectionsInfo = React.useMemo(() => {
    const map = new Map<ExamSectionValue, { label: string; count: number }>();
    for (const r of rows) {
      const e = map.get(r.section);
      if (e) e.count += 1;
      else map.set(r.section, { label: r.section_label, count: 1 });
    }
    return [...map.entries()]
      .map(([value, v]) => ({ value, label: v.label, count: v.count }))
      .sort((a, b) => b.count - a.count);
  }, [rows]);
  const [selSection, setSelSection] = React.useState<ExamSectionValue | null>(null);
  const activeSection =
    selSection && sectionsInfo.some((s) => s.value === selSection)
      ? selSection
      : sectionsInfo[0]?.value ?? null;
  const sectionRows = React.useMemo(
    () => rows.filter((r) => r.section === activeSection),
    [rows, activeSection],
  );

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Denemelerim</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Deneme sonuçların ve konu analizin — sonuç PDF&apos;ini kendin de
            yükleyebilirsin, koçun kontrol edip düzeltebilir.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="gap-1.5 border-violet-300 text-violet-700 hover:bg-violet-500/10 hover:text-violet-800 dark:border-violet-500/40 dark:text-violet-300"
          onClick={() => setImportOpen(true)}
          title="Yayınevi/okul sonuç PDF'ini yükle — sorular konu konu okunur"
        >
          <FileUp className="size-4" aria-hidden />
          PDF&apos;ten aktar
        </Button>
      </div>

      <ExamImportDialog open={importOpen} onOpenChange={setImportOpen} />

      {rows.length === 0 ? (
        <Card>
          <CardContent className="space-y-2 p-6 text-center">
            <p className="text-sm text-muted-foreground">
              Henüz deneme sonucun yok. Deneme sonuç PDF&apos;ini yüklersen
              sorular konu konu okunur ve analizin burada oluşur.
            </p>
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
              <FileUp className="size-4" aria-hidden />
              İlk denemeni aktar
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {sectionsInfo.length > 1 ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                Özet ve analiz seçili sınav türüne göre — türler ayrı
                ölçektedir, karıştırılmaz.
              </p>
              <select
                value={activeSection ?? ""}
                onChange={(e) => setSelSection(e.target.value as ExamSectionValue)}
                aria-label="Sınav türü"
                className="h-8 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {sectionsInfo.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label} ({s.count})
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <SummaryStrip rows={sectionRows} />
          <ExamTopicAnalysis section={activeSection} />

          <ul className="space-y-2">
            {rows.map((row) => (
              <StudentExamRow key={row.id} row={row} />
            ))}
          </ul>
        </>
      )}

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        PDF analizi yapay zekâ ile yapılır ve koçunun kredi havuzundan düşer.
        Satır düzeltmeleri (konu/sonuç) koçun panelinden yapılır.
      </p>
    </div>
  );
}

function SummaryStrip({ rows }: { rows: ExamResultRow[] }) {
  // rows: TEK sınav türü, DESC (en yeni ilk)
  const count = rows.length;
  const nets = rows.map((r) => r.net);
  const avg = count ? nets.reduce((a, b) => a + b, 0) / count : 0;
  const best = count ? Math.max(...nets) : 0;
  const last = count ? rows[0].net : null;
  const first = count ? rows[count - 1].net : null;
  const delta = count >= 2 && last != null && first != null ? last - first : null;
  const items: { label: string; value: string; extra?: React.ReactNode }[] = [
    { label: "Deneme", value: String(count) },
    { label: "Ortalama net", value: avg.toFixed(2) },
    { label: "En iyi net", value: best.toFixed(2) },
    {
      label: "Son net",
      value: last != null ? last.toFixed(2) : "—",
      extra:
        delta != null ? (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 text-[10px] font-medium",
              delta >= 0
                ? "text-emerald-700 dark:text-emerald-300"
                : "text-rose-700 dark:text-rose-300",
            )}
          >
            {delta >= 0 ? (
              <TrendingUp className="size-3" aria-hidden />
            ) : (
              <TrendingDown className="size-3" aria-hidden />
            )}
            {delta >= 0 ? "+" : ""}
            {delta.toFixed(2)}
          </span>
        ) : undefined,
    },
  ];
  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {items.map((it) => (
        <div key={it.label} className="rounded-md border border-border bg-card px-3 py-2">
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-semibold tabular-nums text-foreground">
              {it.value}
            </span>
            {it.extra}
          </div>
          <div className="text-[11px] text-muted-foreground">{it.label}</div>
        </div>
      ))}
    </section>
  );
}

function StudentExamRow({ row }: { row: ExamResultRow }) {
  const [open, setOpen] = React.useState(false);
  const hasSubjects = row.subjects.length > 0;
  return (
    <li>
      <Card>
        <CardContent className="p-3">
          <div className="flex items-center gap-3">
            <div className="w-16 shrink-0 text-center">
              <p className="text-2xl font-semibold leading-none tabular-nums">
                {row.net.toFixed(2)}
              </p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                net
              </p>
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate font-medium">{row.title}</span>
                <span
                  className={cn(
                    "inline-flex items-center rounded border px-1.5 py-0.5 text-[10px]",
                    SECTION_TONE[row.section],
                  )}
                >
                  {row.section_label}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {formatTRDate(row.exam_date)} ·{" "}
                <span className="text-emerald-600">{row.total_correct}D</span>{" "}
                <span className="text-rose-600">{row.total_wrong}Y</span>{" "}
                <span className="text-muted-foreground">{row.total_blank}B</span>
                {" · "}
                {row.total_questions} soru
              </p>
            </div>
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
          </div>
          {open && hasSubjects ? (
            <div className="mt-2 overflow-x-auto rounded-md border border-border">
              <table className="w-full min-w-[360px] text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-muted-foreground">
                    <th className="px-2 py-1">Ders</th>
                    <th className="px-2 py-1 text-right">D</th>
                    <th className="px-2 py-1 text-right">Y</th>
                    <th className="px-2 py-1 text-right">B</th>
                    <th className="px-2 py-1 text-right">Net</th>
                  </tr>
                </thead>
                <tbody>
                  {row.subjects.map((s) => (
                    <tr key={s.name} className="border-b border-border/60 last:border-0">
                      <td className="px-2 py-1">{s.name}</td>
                      <td className="px-2 py-1 text-right tabular-nums text-emerald-700 dark:text-emerald-300">
                        {s.correct}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-rose-700 dark:text-rose-300">
                        {s.wrong}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">
                        {s.blank}
                      </td>
                      <td className="px-2 py-1 text-right font-medium tabular-nums">
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
