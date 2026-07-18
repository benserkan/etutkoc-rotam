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

import { ArchiveExamWrongsButton } from "@/components/shared/archive-exam-wrongs-button";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import {
  getExamImportRows,
  studentAnalyzeExamPdf,
  studentConfirmExamImport,
  teacherAnalyzeExamPdf,
  teacherConfirmExamImport,
  updateExamImportRows,
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
  kayitli: "kayıtlı",
};

interface EditRow extends ImportDraftRow {
  manually_edited: boolean;
}

type Step = "pick" | "analyzing" | "preview" | "saving" | "done";

// Beyan seçicileri (BEYAN ESAS — tespit bekçiye döner): sınıfa göre tür listesi
const GRADE_CHOICES: { value: string; label: string }[] = [
  { value: "", label: "Otomatik tespit" },
  ...[5, 6, 7, 8, 9, 10, 11, 12].map((g) => ({
    value: String(g),
    label: `${g}. Sınıf`,
  })),
  { value: "mezun", label: "Mezun" },
];

function sectionChoicesFor(grade: string): { value: string; label: string }[] {
  const auto = { value: "", label: "Otomatik tespit" };
  if (!grade) {
    return [auto];
  }
  const g = grade === "mezun" ? 13 : Number(grade);
  if (g >= 5 && g <= 8) {
    return [auto, { value: "lgs", label: "LGS" },
            { value: "okul", label: "Okul Sınavı / Yazılı" }];
  }
  if (g >= 9 && g <= 10) {
    return [
      auto,
      { value: "tyt", label: "Sınıf İzleme / TYT formatı" },
      { value: "okul", label: "Okul Sınavı / Yazılı" },
    ];
  }
  return [
    auto,
    { value: "tyt", label: "TYT" },
    { value: "ayt_say", label: "AYT (Sayısal)" },
    { value: "ayt_ea", label: "AYT (Eşit Ağırlık)" },
    { value: "ayt_soz", label: "AYT (Sözel)" },
    { value: "ayt_dil", label: "AYT (Dil)" },
    { value: "okul", label: "Okul Sınavı / Yazılı" },
  ];
}

export function ExamImportDialog({
  open,
  onOpenChange,
  studentId,
  editExamId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** Verilirse koç yüzeyi (o öğrenci adına); verilmezse öğrenci kendi adına. */
  studentId?: number;
  /** Verilirse DÜZENLEME modu: kayıtlı içe-aktarım satır satır açılır (PDF
   *  yeniden okunmaz, kredi düşmez); kaydet → mevcut kayıt güncellenir. */
  editExamId?: number;
}) {
  // Dialog yalnız açıkken mount edilir → kapatınca state sıfırlanır
  if (!open) return null;
  return (
    <ImportFlow
      onClose={() => onOpenChange(false)}
      studentId={studentId}
      editExamId={editExamId}
    />
  );
}

function ImportFlow({
  onClose,
  studentId,
  editExamId,
}: {
  onClose: () => void;
  studentId?: number;
  editExamId?: number;
}) {
  const qc = useQueryClient();
  const editMode = editExamId != null;
  const [step, setStep] = React.useState<Step>(editMode ? "analyzing" : "pick");
  // Beyan (kullanıcı seçimi — boş = otomatik tespit)
  const [declGrade, setDeclGrade] = React.useState("");
  const [declSection, setDeclSection] = React.useState("");
  const [file, setFile] = React.useState<File | null>(null);
  const [draft, setDraft] = React.useState<ExamImportDraft | null>(null);
  const [rows, setRows] = React.useState<EditRow[]>([]);
  const [title, setTitle] = React.useState("");
  const [titleTouched, setTitleTouched] = React.useState(false);
  const [examDate, setExamDate] = React.useState("");
  const [section, setSection] = React.useState("");
  // Birleşik belge (TG kitapçığı): seçili oturum — yalnız o oturumun soruları
  // kaydedilir; koç ikinci oturum için tekrar "kaydet" yapar (analiz tek, kredi tek).
  const [selectedPart, setSelectedPart] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<ExamImportConfirmResult | null>(null);
  const [needForce, setNeedForce] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const multi = (draft?.parts.length ?? 0) > 1;

  function autoTitle(base: string | null, d: ExamImportDraft, part: string | null): string {
    // Birleşik belgede oturum adı eklenir — iki oturum ayrı kayıt olduğundan
    // aynı ad+tarih mükerrer uyarısına takılmasın.
    const t = base ?? "";
    if (d.parts.length <= 1) return t;
    const p = d.parts.find((x) => x.part === part);
    return p ? `${t} — ${p.section_label}` : t;
  }

  function applyDraft(d: ExamImportDraft) {
    const firstPart = d.parts[0]?.part ?? null;
    setDraft(d);
    setRows(d.rows.map((r) => ({ ...r, manually_edited: false })));
    setSelectedPart(firstPart);
    setTitle(autoTitle(d.title, d, firstPart));
    setTitleTouched(false);
    setExamDate(d.exam_date ?? "");
    setSection(d.parts[0]?.section ?? d.section);
    setStep("preview");
  }

  async function analyze(f: File) {
    setFile(f);
    setStep("analyzing");
    const decl = {
      declaredSection: declSection || null,
      declaredGrade:
        declGrade && declGrade !== "mezun" ? Number(declGrade) : null,
    };
    try {
      const d = studentId != null
        ? await teacherAnalyzeExamPdf(studentId, f, decl)
        : await studentAnalyzeExamPdf(f, decl);
      applyDraft(d);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Belge analiz edilemedi.";
      toast.error("Analiz başarısız", { description: msg });
      setStep("pick");
    }
  }

  // Düzenleme modu: mount'ta kayıtlı denemeyi taslak olarak yükle (PDF okunmaz)
  React.useEffect(() => {
    if (editExamId == null) return;
    let alive = true;
    getExamImportRows(editExamId)
      .then((d) => { if (alive) applyDraft(d); })
      .catch((e) => {
        if (!alive) return;
        const msg = e instanceof ApiError ? e.message : "Deneme yüklenemedi.";
        toast.error("Düzenleme açılamadı", { description: msg });
        onClose();
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- yalnız mount'ta (dialog açıkken remount edilir)
  }, []);

  function switchPart(part: string | null) {
    if (!draft) return;
    setSelectedPart(part);
    const p = draft.parts.find((x) => x.part === part);
    if (p) setSection(p.section);
    if (!titleTouched) setTitle(autoTitle(draft.title, draft, part));
  }

  function editRow(idx: number, patch: Partial<EditRow>) {
    setRows((prev) => prev.map((r, i) =>
      i === idx
        ? { ...r, ...patch, manually_edited: true, is_suspect: false }
        : r,
    ));
  }

  // Birleşik belgede yalnız SEÇİLİ oturumun satırları görünür/kaydedilir
  const activeRows = React.useMemo(
    () => (multi ? rows.filter((r) => r.exam_part === selectedPart) : rows),
    [rows, multi, selectedPart],
  );

  async function save(force: boolean) {
    if (!draft) return;
    const missing = activeRows.filter((r) => r.result == null).length;
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
      rows: activeRows.map((r): ConfirmRow => ({
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
      const res = editExamId != null
        ? await updateExamImportRows(editExamId, body)
        : studentId != null
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

  // canlı toplamlar (düzeltmeler anında yansır; birleşik belgede seçili oturum)
  const tally = React.useMemo(() => {
    const t = { dogru: 0, yanlis: 0, bos: 0, eksik: 0 };
    for (const r of activeRows) {
      if (r.result) t[r.result] += 1;
      else t.eksik += 1;
    }
    const penalty = section === "lgs" ? 3 : 4;
    const net = Math.max(t.dogru - t.yanlis / penalty, 0);
    return { ...t, net: Math.round(net * 100) / 100 };
  }, [activeRows, section]);

  return (
    <Dialog open onOpenChange={(v) => { if (!v && step !== "analyzing" && step !== "saving") onClose(); }}>
      <DialogContent className="flex max-h-[92vh] max-w-4xl flex-col overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4">
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileUp className="size-4 text-violet-600" aria-hidden />
            {editMode ? "İçe aktarılan denemeyi düzenle" : "Deneme sonucunu PDF'ten aktar"}
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
              declGrade={declGrade}
              declSection={declSection}
              onDeclGrade={(v) => {
                setDeclGrade(v);
                setDeclSection("");
              }}
              onDeclSection={setDeclSection}
            />
          ) : null}

          {step === "analyzing" ? (
            <div className="flex flex-col items-center gap-3 py-14 text-center">
              <Loader2 className="size-8 animate-spin text-violet-600" aria-hidden />
              <div className="text-sm font-medium text-foreground">
                {editMode ? "Kayıtlı deneme açılıyor…" : "Yapay zekâ belgeyi okuyor…"}
              </div>
              <p className="max-w-sm text-xs text-muted-foreground">
                {editMode ? (
                  <>
                    PDF yeniden okunmaz, <b>kredi düşmez</b> — eşleşmemiş konular
                    güncel müfredat sözlüğüyle yeniden denenir.
                  </>
                ) : (
                  <>
                    Uydurmayı önlemek için belge <b>iki kez bağımsız</b> okunur ve
                    sonuçlar karşılaştırılır — uzun belgelerde <b>1-2 dakika</b>{" "}
                    sürebilir, sayfayı kapatma.
                  </>
                )}
              </p>
            </div>
          ) : null}

          {(step === "preview" || step === "saving") && draft ? (
            <PreviewStep
              draft={draft}
              rows={rows}
              selectedPart={selectedPart}
              multi={multi}
              title={title}
              examDate={examDate}
              section={section}
              needForce={needForce}
              onTitle={(v) => { setTitle(v); setTitleTouched(true); }}
              onDate={setExamDate}
              onSection={setSection}
              onSwitchPart={switchPart}
              onEditRow={editRow}
            />
          ) : null}

          {step === "done" && result ? (
            <DoneStep result={result} updated={editMode} studentId={studentId} />
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
  declGrade,
  declSection,
  onDeclGrade,
  onDeclSection,
}: {
  fileRef: React.RefObject<HTMLInputElement | null>;
  onPick: (f: File) => void;
  declGrade: string;
  declSection: string;
  onDeclGrade: (v: string) => void;
  onDeclSection: (v: string) => void;
}) {
  const sectionChoices = sectionChoicesFor(declGrade);
  return (
    <div className="space-y-4">
      {/* BEYAN ESAS: sınıf + tür seçilirse tespit bekçiye döner (çelişkide uyarır) */}
      <div className="rounded-md border border-border bg-muted/30 p-3">
        <p className="mb-2 text-xs font-medium text-foreground">
          Denemenin sınıfı ve türünü biliyorsan seç — yanlış tür ihtimali
          sıfırlanır. Bilmiyorsan &quot;Otomatik tespit&quot; bırak.
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs text-muted-foreground">
            Sınıf
            <select
              value={declGrade}
              onChange={(e) => onDeclGrade(e.target.value)}
              className="mt-1 h-9 w-full rounded-md border border-border bg-card px-2 text-sm text-foreground"
            >
              {GRADE_CHOICES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-muted-foreground">
            Sınav türü
            <select
              value={declSection}
              onChange={(e) => onDeclSection(e.target.value)}
              disabled={!declGrade}
              className="mt-1 h-9 w-full rounded-md border border-border bg-card px-2 text-sm text-foreground disabled:opacity-60"
            >
              {sectionChoices.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </label>
        </div>
      </div>
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
  selectedPart,
  multi,
  title,
  examDate,
  section,
  needForce,
  onTitle,
  onDate,
  onSection,
  onSwitchPart,
  onEditRow,
}: {
  draft: ExamImportDraft;
  rows: EditRow[];
  selectedPart: string | null;
  multi: boolean;
  title: string;
  examDate: string;
  section: string;
  needForce: boolean;
  onTitle: (v: string) => void;
  onDate: (v: string) => void;
  onSection: (v: string) => void;
  onSwitchPart: (part: string | null) => void;
  onEditRow: (idx: number, patch: Partial<EditRow>) => void;
}) {
  const failing = draft.checks.filter((c) => !c.ok);
  const stats = draft.match_stats;

  // satırlar ders grubuna göre (orijinal indeks korunur — düzenleme için);
  // birleşik belgede yalnız seçili oturumun satırları
  const groups = React.useMemo(() => {
    const out = new Map<string, { idx: number; row: EditRow }[]>();
    rows.forEach((row, idx) => {
      if (multi && row.exam_part !== selectedPart) return;
      // okul-müfredat sınavında sunum = sınıf dersinin adı (display_subject)
      const key = row.display_subject ?? row.subject_name ?? row.subject_raw ?? "Diğer";
      if (!out.has(key)) out.set(key, []);
      out.get(key)!.push({ idx, row });
    });
    return Array.from(out.entries());
  }, [rows, multi, selectedPart]);

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
      {/* Birleşik belge (TG kitapçığı) — oturum seçici */}
      {multi ? (
        <div className="rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2.5 dark:border-cyan-500/30 dark:bg-cyan-500/10">
          <div className="text-xs font-medium text-cyan-900 dark:text-cyan-200">
            Bu belgede <b>{draft.parts.length} sınav oturumu</b> var — hangisini
            kaydedeceğini seç (diğerini sonra aynı belgeyi seçip tekrar
            kaydedebilirsin; analiz tek yapıldı, tekrar kredi düşmez):
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {draft.parts.map((p) => (
              <button
                key={p.part ?? "tek"}
                type="button"
                onClick={() => onSwitchPart(p.part)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-semibold transition",
                  selectedPart === p.part
                    ? "border-cyan-600 bg-cyan-600 text-white"
                    : "border-cyan-300 bg-card text-cyan-800 hover:bg-cyan-500/10 dark:text-cyan-300",
                )}
              >
                {p.section_label} · {p.question_count} soru
              </button>
            ))}
          </div>
        </div>
      ) : null}

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

function DoneStep({
  result,
  updated,
  studentId,
}: {
  result: ExamImportConfirmResult;
  updated?: boolean;
  studentId?: number;
}) {
  return (
    <div className="py-6 text-center">
      <CheckCircle2 className="mx-auto size-10 text-emerald-500" aria-hidden />
      <h3 className="mt-3 text-base font-semibold text-foreground">
        {updated ? "Deneme güncellendi" : "Deneme kaydedildi"}
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
      {result.total_wrong > 0 ? (
        <div className="mt-4 flex flex-col items-center gap-1.5">
          <ArchiveExamWrongsButton
            examId={result.exam_id}
            studentId={studentId}
            wrongCount={result.total_wrong}
          />
          <p className="text-[11px] text-muted-foreground">
            Yanlışlar arşive girer ve aralıklı tekrar kuyruğunda yeniden çözülür.
          </p>
        </div>
      ) : null}
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
