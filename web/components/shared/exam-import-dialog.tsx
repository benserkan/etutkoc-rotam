"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  FileUp,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import {
  studentAnalyzeExamPdf,
  studentConfirmExamImport,
  teacherAnalyzeExamPdf,
  teacherConfirmExamImport,
} from "@/lib/api/exam-import";
import { applyInvalidate } from "@/lib/invalidate";
import type {
  ConfirmRow,
  ExamImportConfirmResult,
  ExamImportDraft,
  ImportDraftRow,
  ImportResultValue,
} from "@/lib/types/exam-import";
import { cn } from "@/lib/utils";

/**
 * Deneme PDF içe aktarma akışı — yükle → Gemini çift okuma → önizleme/düzelt →
 * kaydet. Koç (studentId verilir) + öğrenci (verilmez) aynı bileşeni kullanır.
 *
 * Uydurma önleme UI'ı: şüpheli hücreler sarı; başarısız iç tutarlılık
 * kontrolleri banner; koç her satırın konu/DC/ÖC/sonucunu düzeltebilir
 * (düzeltme öğrenen sözlüğe yazılır → sonraki denemeler otomatik doğru çözülür).
 */

const RESULT_LABELS: Record<ImportResultValue, string> = {
  dogru: "Doğru",
  yanlis: "Yanlış",
  bos: "Boş",
};

const RESULT_TONE: Record<ImportResultValue, string> = {
  dogru: "text-emerald-700 dark:text-emerald-300",
  yanlis: "text-rose-700 dark:text-rose-300",
  bos: "text-slate-500 dark:text-slate-400",
};

const SOURCE_LABELS: Record<string, string> = {
  alias: "sözlük",
  auto: "otomatik",
  ai: "AI",
  none: "eşleşmedi",
};

interface EditRow extends ImportDraftRow {
  manually_edited: boolean;
}

type Step = "pick" | "analyzing" | "preview" | "saving" | "done";

export function ExamImportDialog({
  open,
  onOpenChange,
  studentId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** Verilirse koç yüzeyi (o öğrenci adına); verilmezse öğrenci kendi adına. */
  studentId?: number;
}) {
  // Dialog yalnız açıkken mount edilir → kapatınca state sıfırlanır
  if (!open) return null;
  return (
    <ImportFlow
      onClose={() => onOpenChange(false)}
      studentId={studentId}
    />
  );
}

function ImportFlow({
  onClose,
  studentId,
}: {
  onClose: () => void;
  studentId?: number;
}) {
  const qc = useQueryClient();
  const [step, setStep] = React.useState<Step>("pick");
  const [file, setFile] = React.useState<File | null>(null);
  const [draft, setDraft] = React.useState<ExamImportDraft | null>(null);
  const [rows, setRows] = React.useState<EditRow[]>([]);
  const [title, setTitle] = React.useState("");
  const [examDate, setExamDate] = React.useState("");
  const [section, setSection] = React.useState("");
  const [result, setResult] = React.useState<ExamImportConfirmResult | null>(null);
  const [needForce, setNeedForce] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  async function analyze(f: File) {
    setFile(f);
    setStep("analyzing");
    try {
      const d = studentId != null
        ? await teacherAnalyzeExamPdf(studentId, f)
        : await studentAnalyzeExamPdf(f);
      setDraft(d);
      setRows(d.rows.map((r) => ({ ...r, manually_edited: false })));
      setTitle(d.title ?? "");
      setExamDate(d.exam_date ?? "");
      setSection(d.section);
      setStep("preview");
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Belge analiz edilemedi.";
      toast.error("Analiz başarısız", { description: msg });
      setStep("pick");
    }
  }

  function editRow(idx: number, patch: Partial<EditRow>) {
    setRows((prev) => prev.map((r, i) =>
      i === idx
        ? { ...r, ...patch, manually_edited: true, is_suspect: false }
        : r,
    ));
  }

  async function save(force: boolean) {
    if (!draft) return;
    const missing = rows.filter((r) => r.result == null).length;
    if (missing > 0) {
      toast.error(`${missing} sorunun sonucu boş`, {
        description: "Sarı işaretli satırlarda Doğru/Yanlış/Boş seçimi yapın.",
      });
      return;
    }
    if (!title.trim() || !examDate) {
      toast.error("Deneme adı ve tarihi zorunlu.");
      return;
    }
    setStep("saving");
    const body = {
      title: title.trim(),
      exam_date: examDate,
      section,
      scope: draft.scope,
      grade_hint: draft.grade_hint,
      score_info: draft.score_info,
      force,
      rows: rows.map((r): ConfirmRow => ({
        subject_raw: r.subject_raw,
        question_no: r.question_no,
        topic_raw: r.topic_raw,
        topic_id: r.topic_id,
        correct_answer: r.correct_answer,
        student_answer: r.student_answer,
        result: r.result as ImportResultValue,
        is_suspect: r.is_suspect,
        manually_edited: r.manually_edited,
      })),
    };
    try {
      const res = studentId != null
        ? await teacherConfirmExamImport(studentId, body, file)
        : await studentConfirmExamImport(body, file);
      applyInvalidate(qc, res.invalidate);
      setResult(res.data);
      setStep("done");
    } catch (e) {
      if (e instanceof ApiError && e.detail?.code === "duplicate_exam") {
        setNeedForce(true);
        setStep("preview");
        return;
      }
      const msg = e instanceof ApiError ? e.message : "Kaydedilemedi.";
      toast.error("Kayıt başarısız", { description: msg });
      setStep("preview");
    }
  }

  // canlı toplamlar (düzeltmeler anında yansır)
  const tally = React.useMemo(() => {
    const t = { dogru: 0, yanlis: 0, bos: 0, eksik: 0 };
    for (const r of rows) {
      if (r.result) t[r.result] += 1;
      else t.eksik += 1;
    }
    const penalty = section === "lgs" ? 3 : 4;
    const net = Math.max(t.dogru - t.yanlis / penalty, 0);
    return { ...t, net: Math.round(net * 100) / 100 };
  }, [rows, section]);

  return (
    <Dialog open onOpenChange={(v) => { if (!v && step !== "analyzing" && step !== "saving") onClose(); }}>
      <DialogContent className="flex max-h-[92vh] max-w-4xl flex-col overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4">
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileUp className="size-4 text-violet-600" aria-hidden />
            Deneme sonucunu PDF&apos;ten aktar
            {draft ? (
              <span className="text-xs font-normal text-muted-foreground">
                {draft.section_label}
                {draft.scope === "brans" ? " · branş" : ""}
              </span>
            ) : null}
          </DialogTitle>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {step === "pick" ? (
            <PickStep
              fileRef={fileRef}
              onPick={(f) => void analyze(f)}
            />
          ) : null}

          {step === "analyzing" ? (
            <div className="flex flex-col items-center gap-3 py-14 text-center">
              <Loader2 className="size-8 animate-spin text-violet-600" aria-hidden />
              <div className="text-sm font-medium text-foreground">
                Yapay zekâ belgeyi okuyor…
              </div>
              <p className="max-w-sm text-xs text-muted-foreground">
                Uydurmayı önlemek için belge <b>iki kez bağımsız</b> okunur ve
                sonuçlar karşılaştırılır — uzun belgelerde <b>1-2 dakika</b>{" "}
                sürebilir, sayfayı kapatma.
              </p>
            </div>
          ) : null}

          {(step === "preview" || step === "saving") && draft ? (
            <PreviewStep
              draft={draft}
              rows={rows}
              title={title}
              examDate={examDate}
              section={section}
              needForce={needForce}
              onTitle={setTitle}
              onDate={setExamDate}
              onSection={setSection}
              onEditRow={editRow}
            />
          ) : null}

          {step === "done" && result ? (
            <DoneStep result={result} />
          ) : null}
        </div>

        {/* Sabit alt aksiyon çubuğu */}
        <div className="shrink-0 border-t border-border bg-card px-5 py-3">
          {step === "preview" || step === "saving" ? (
            <div className="flex flex-wrap items-center gap-3">
              <div className="text-xs text-muted-foreground">
                <b className="text-foreground tabular-nums">{tally.net}</b> net ·{" "}
                <span className="text-emerald-700 dark:text-emerald-300">{tally.dogru}D</span>{" "}
                <span className="text-rose-700 dark:text-rose-300">{tally.yanlis}Y</span>{" "}
                <span>{tally.bos}B</span>
                {tally.eksik > 0 ? (
                  <span className="ml-1 text-amber-700 dark:text-amber-300">
                    · {tally.eksik} sonuç eksik
                  </span>
                ) : null}
              </div>
              <div className="ml-auto flex gap-2">
                <Button variant="outline" onClick={onClose} disabled={step === "saving"}>
                  Vazgeç
                </Button>
                <Button
                  onClick={() => void save(needForce)}
                  disabled={step === "saving"}
                  className={cn("gap-1.5", needForce && "bg-amber-600 hover:bg-amber-700")}
                >
                  {step === "saving" ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                  ) : (
                    <CheckCircle2 className="size-4" aria-hidden />
                  )}
                  {needForce ? "Yine de kaydet (mükerrer)" : "Kontrol ettim, kaydet"}
                </Button>
              </div>
            </div>
          ) : step === "done" ? (
            <div className="flex justify-end">
              <Button onClick={onClose}>Kapat</Button>
            </div>
          ) : (
            <p className="text-[11px] text-muted-foreground">
              <ShieldCheck className="mr-1 inline size-3.5" aria-hidden />
              Belge yapay zekâ ile işlenir (Google Gemini) · analiz{" "}
              <b>6 kredi</b> (koç havuzundan) · kayıttan önce her satırı kontrol
              edip düzeltebilirsin.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function PickStep({
  fileRef,
  onPick,
}: {
  fileRef: React.RefObject<HTMLInputElement | null>;
  onPick: (f: File) => void;
}) {
  return (
    <div className="space-y-4">
      <input
        ref={fileRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        className="flex w-full flex-col items-center gap-2 rounded-lg border-2 border-dashed border-border bg-muted/30 px-4 py-10 text-sm text-muted-foreground transition hover:border-violet-400 hover:text-foreground"
      >
        <FileUp className="size-8" aria-hidden />
        <span className="font-medium">Deneme sonuç PDF&apos;ini seç</span>
        <span className="text-xs">
          Yayınevi/okul sisteminden aldığın konu analizli sonuç belgesi (≤10 MB)
        </span>
      </button>
      <ul className="space-y-1.5 text-xs text-muted-foreground">
        <li>• Sınav türü (TYT/AYT/LGS/okul) otomatik tanınır — yanlışsa önizlemede değiştirirsin.</li>
        <li>• Yayınevi konu adları <b>senin müfredatına</b> otomatik çevrilir (örn. &quot;İşlem Yeteneği&quot; → &quot;Temel Kavramlar&quot;).</li>
        <li>• Okuma şüpheli olan hücreler <b>sarı</b> işaretlenir; kaydetmeden düzeltebilirsin.</li>
      </ul>
    </div>
  );
}

function PreviewStep({
  draft,
  rows,
  title,
  examDate,
  section,
  needForce,
  onTitle,
  onDate,
  onSection,
  onEditRow,
}: {
  draft: ExamImportDraft;
  rows: EditRow[];
  title: string;
  examDate: string;
  section: string;
  needForce: boolean;
  onTitle: (v: string) => void;
  onDate: (v: string) => void;
  onSection: (v: string) => void;
  onEditRow: (idx: number, patch: Partial<EditRow>) => void;
}) {
  const failing = draft.checks.filter((c) => !c.ok);
  const stats = draft.match_stats;

  // satırlar ders grubuna göre (orijinal indeks korunur — düzenleme için)
  const groups = React.useMemo(() => {
    const out = new Map<string, { idx: number; row: EditRow }[]>();
    rows.forEach((row, idx) => {
      const key = row.subject_name ?? row.subject_raw ?? "Diğer";
      if (!out.has(key)) out.set(key, []);
      out.get(key)!.push({ idx, row });
    });
    return Array.from(out.entries());
  }, [rows]);

  // konu seçici — ders adına göre gruplu optgroup
  const topicGroups = React.useMemo(() => {
    const m = new Map<string, { id: number; name: string }[]>();
    for (const t of draft.topic_choices) {
      if (!m.has(t.subject_name)) m.set(t.subject_name, []);
      m.get(t.subject_name)!.push({ id: t.id, name: t.name });
    }
    return Array.from(m.entries());
  }, [draft.topic_choices]);

  return (
    <div className="space-y-4">
      {/* Kimlik + tür */}
      <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
        <input
          value={title}
          onChange={(e) => onTitle(e.target.value)}
          placeholder="Deneme adı"
          className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground"
          aria-label="Deneme adı"
        />
        <input
          type="date"
          value={examDate}
          onChange={(e) => onDate(e.target.value)}
          className="h-9 rounded-md border border-border bg-card px-2 text-sm text-foreground"
          aria-label="Sınav tarihi"
        />
        <select
          value={section}
          onChange={(e) => onSection(e.target.value)}
          className={cn(
            "h-9 rounded-md border bg-card px-2 text-sm text-foreground",
            draft.confidence === "high" ? "border-border" : "border-amber-400",
          )}
          aria-label="Sınav türü"
        >
          {draft.section_choices.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>
      {draft.confidence !== "high" ? (
        <p className="text-xs text-amber-800 dark:text-amber-300">
          <AlertTriangle className="mr-1 inline size-3.5" aria-hidden />
          Sınav türünden tam emin olamadım — üstteki seçiciden kontrol et.
        </p>
      ) : null}

      {/* Mükerrer / kontrol uyarıları */}
      {needForce || draft.duplicate_exam_id ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
          Bu deneme (aynı ad + tarih) daha önce kaydedilmiş görünüyor.
          Yeniden kaydedersen <b>iki ayrı kayıt</b> oluşur.
        </div>
      ) : null}
      {failing.map((c) => (
        <div
          key={c.code}
          className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200"
        >
          <AlertTriangle className="mr-1 inline size-3.5" aria-hidden />
          <b>{c.label}:</b> {c.detail}
        </div>
      ))}

      {/* Eşleşme istatistiği */}
      <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
        <Sparkles className="size-3.5 text-violet-600" aria-hidden />
        <Chip tone="emerald">{stats.alias + stats.auto} otomatik eşleşti</Chip>
        {stats.ai > 0 ? <Chip tone="violet">{stats.ai} AI eşledi</Chip> : null}
        {stats.none > 0 ? <Chip tone="amber">{stats.none} eşleşmedi — elle seç</Chip> : null}
        {draft.suspect_count > 0 ? (
          <Chip tone="amber">{draft.suspect_count} şüpheli hücre</Chip>
        ) : null}
      </div>

      {/* Ders grupları — soru tabloları */}
      {groups.map(([gname, items]) => (
        <section key={gname}>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {gname} <span className="font-normal">({items.length} soru)</span>
          </h4>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full min-w-[560px] text-xs">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-muted-foreground">
                  <th className="px-2 py-1.5 w-8">No</th>
                  <th className="px-2 py-1.5">Konu (belgede → müfredatta)</th>
                  <th className="px-2 py-1.5 w-14">DC</th>
                  <th className="px-2 py-1.5 w-14">ÖC</th>
                  <th className="px-2 py-1.5 w-28">Sonuç</th>
                </tr>
              </thead>
              <tbody>
                {items.map(({ idx, row }) => (
                  <tr
                    key={idx}
                    className={cn(
                      "border-b border-border/60 last:border-0",
                      row.is_suspect && "bg-amber-50 dark:bg-amber-500/10",
                    )}
                  >
                    <td className="px-2 py-1 tabular-nums text-muted-foreground">
                      {row.question_no ?? "—"}
                    </td>
                    <td className="px-2 py-1">
                      <div className="flex flex-col gap-0.5">
                        <span className="text-muted-foreground">
                          {row.topic_raw || "—"}
                          {row.topic_source && row.topic_source !== "none" ? (
                            <span className="ml-1 rounded bg-muted px-1 text-[9px] uppercase">
                              {SOURCE_LABELS[row.topic_source]}
                            </span>
                          ) : null}
                        </span>
                        <select
                          value={row.topic_id ?? ""}
                          onChange={(e) =>
                            onEditRow(idx, {
                              topic_id: e.target.value ? Number(e.target.value) : null,
                            })
                          }
                          className={cn(
                            "h-7 w-full max-w-72 rounded border bg-card px-1 text-xs text-foreground",
                            row.topic_id == null
                              ? "border-amber-400"
                              : "border-border",
                          )}
                          aria-label="Müfredat konusu"
                        >
                          <option value="">— eşleşmedi (birikime girmez) —</option>
                          {topicGroups.map(([sname, topics]) => (
                            <optgroup key={sname} label={sname}>
                              {topics.map((t) => (
                                <option key={t.id} value={t.id}>{t.name}</option>
                              ))}
                            </optgroup>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="px-2 py-1">
                      <AnswerInput
                        value={row.correct_answer}
                        onChange={(v) => onEditRow(idx, { correct_answer: v })}
                        label="Doğru cevap"
                      />
                    </td>
                    <td className="px-2 py-1">
                      <AnswerInput
                        value={row.student_answer}
                        onChange={(v) => onEditRow(idx, { student_answer: v })}
                        label="Öğrenci cevabı"
                      />
                    </td>
                    <td className="px-2 py-1">
                      <select
                        value={row.result ?? ""}
                        onChange={(e) =>
                          onEditRow(idx, {
                            result: (e.target.value || null) as ImportResultValue | null,
                          })
                        }
                        className={cn(
                          "h-7 w-full rounded border bg-card px-1 text-xs font-medium",
                          row.result ? RESULT_TONE[row.result] : "border-amber-400 text-amber-700",
                          "border-border",
                        )}
                        aria-label="Sonuç"
                      >
                        <option value="">— seç —</option>
                        {(Object.keys(RESULT_LABELS) as ImportResultValue[]).map((k) => (
                          <option key={k} value={k}>{RESULT_LABELS[k]}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <p className="text-[11px] text-muted-foreground">
        Sarı satırlar: iki okuma birbirini tutmadı veya sonuç türetilemedi —
        belgeyle karşılaştırıp düzelt. Konu düzeltmelerin <b>öğrenilir</b>:
        aynı yayınevi etiketi bir daha geldiğinde otomatik doğru eşleşir.
      </p>
    </div>
  );
}

function AnswerInput({
  value,
  onChange,
  label,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  label: string;
}) {
  return (
    <input
      value={value ?? ""}
      onChange={(e) => {
        const v = e.target.value.trim().toUpperCase().slice(0, 2);
        onChange(v || null);
      }}
      placeholder="—"
      maxLength={2}
      className="h-7 w-10 rounded border border-border bg-card px-1 text-center text-xs font-semibold text-foreground uppercase"
      aria-label={label}
    />
  );
}

function DoneStep({ result }: { result: ExamImportConfirmResult }) {
  return (
    <div className="py-6 text-center">
      <CheckCircle2 className="mx-auto size-10 text-emerald-500" aria-hidden />
      <h3 className="mt-3 text-base font-semibold text-foreground">
        Deneme kaydedildi
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        {result.title} · {result.section_label} ·{" "}
        {new Date(result.exam_date).toLocaleDateString("tr-TR")}
      </p>
      <div className="mx-auto mt-4 grid max-w-md grid-cols-4 gap-3">
        <Stat label="Net" value={String(result.net)} tone="cyan" />
        <Stat label="Doğru" value={String(result.total_correct)} tone="emerald" />
        <Stat label="Yanlış" value={String(result.total_wrong)} tone="rose" />
        <Stat label="Boş" value={String(result.total_blank)} tone="slate" />
      </div>
      <p className="mx-auto mt-4 max-w-md text-xs text-muted-foreground">
        {result.question_count} sorunun {result.matched_topic_count}&apos;i müfredat
        konusuna bağlandı — konu bazlı hata birikimi bu denemeyle güncellendi.
        {result.wrong_topic_ids.length > 0
          ? ` ${result.wrong_topic_ids.length} konuda yanlış var.`
          : ""}
      </p>
    </div>
  );
}

function Chip({
  tone,
  children,
}: {
  tone: "emerald" | "violet" | "amber";
  children: React.ReactNode;
}) {
  const cls = {
    emerald: "bg-emerald-50 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300",
    violet: "bg-violet-50 text-violet-800 dark:bg-violet-500/10 dark:text-violet-300",
    amber: "bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300",
  }[tone];
  return (
    <span className={cn("rounded-full px-2 py-0.5 font-medium", cls)}>{children}</span>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "cyan" | "emerald" | "rose" | "slate";
}) {
  const cls = {
    cyan: "text-cyan-700 dark:text-cyan-300",
    emerald: "text-emerald-700 dark:text-emerald-300",
    rose: "text-rose-700 dark:text-rose-300",
    slate: "text-foreground",
  }[tone];
  return (
    <div className="rounded-md border border-border bg-card px-2 py-2">
      <div className={cn("text-xl font-semibold tabular-nums", cls)}>{value}</div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}
