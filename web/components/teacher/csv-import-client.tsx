"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardPaste,
  Download,
  FileSpreadsheet,
  Loader2,
  Upload,
  Users,
  X,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import { academicKeys, convertStudentsXlsx, getAcademicYears } from "@/lib/api/academic";

import {
  useCsvImportCommit,
  useCsvImportPreview,
} from "@/lib/hooks/use-academic-mutations";
import type {
  CsvCommitResult,
  CsvPreviewResponse,
} from "@/lib/types/academic";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { LoginCardsActions } from "@/components/teacher/login-cards";

type Step = "input" | "preview" | "result";

export function CsvImportClient() {
  const [step, setStep] = React.useState<Step>("input");
  const [csvText, setCsvText] = React.useState("");
  const [preview, setPreview] = React.useState<CsvPreviewResponse | null>(null);
  const [result, setResult] = React.useState<CsvCommitResult | null>(null);
  const [yearId, setYearId] = React.useState<number | null>(null);
  const yearsQ = useQuery({ queryKey: academicKeys.years(), queryFn: getAcademicYears });
  const years = yearsQ.data?.items ?? [];

  const previewMut = useCsvImportPreview();
  const commitMut = useCsvImportCommit();

  function onPreview(e: React.FormEvent) {
    e.preventDefault();
    if (!csvText.trim()) return;
    previewMut.mutate(
      { body: { csv_text: csvText } },
      {
        onSuccess: (data) => {
          setPreview(data);
          setStep("preview");
        },
      },
    );
  }

  function onCommit() {
    commitMut.mutate(
      { body: { csv_text: csvText, academic_year_id: yearId } },
      {
        onSuccess: (res) => {
          setResult(res.data);
          setStep("result");
        },
      },
    );
  }

  function onReset() {
    setStep("input");
    setCsvText("");
    setPreview(null);
    setResult(null);
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Link href="/teacher/students" className="hover:underline">
            Öğrenciler
          </Link>
          <span className="mx-1.5">/</span>Toplu ekleme
        </p>
        <h1 className="font-display text-2xl font-bold tracking-tight">Toplu öğrenci ekle</h1>
        <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
          Öğrenci listeni Excel ya da CSV dosyası olarak yükle; kaydetmeden önce her satırı
          kontrol edersin. Her öğrenci için hesap açılır ve geçici şifresi verilir. Satırda
          veli e-postası varsa veliye davet de gider.
        </p>
      </header>

      <StepIndicator step={step} />

      {step === "input" ? (
        <InputStep
          csvText={csvText}
          setCsvText={setCsvText}
          onSubmit={onPreview}
          isPending={previewMut.isPending}
        />
      ) : null}

      {step === "preview" && preview ? (
        <PreviewStep
          preview={preview}
          years={years}
          yearId={yearId}
          setYearId={setYearId}
          onBack={() => setStep("input")}
          onCommit={onCommit}
          isPending={commitMut.isPending}
        />
      ) : null}

      {step === "result" && result ? (
        <ResultStep result={result} onReset={onReset} />
      ) : null}
    </div>
  );
}

const STEPS: Array<{ key: Step; title: string; hint: string }> = [
  { key: "input", title: "Dosyayı yükle", hint: "Excel veya CSV" },
  { key: "preview", title: "Kontrol et", hint: "Satır satır önizleme" },
  { key: "result", title: "Hesaplar hazır", hint: "Giriş bilgileri" },
];

function StepIndicator({ step }: { step: Step }) {
  const current = STEPS.findIndex((s) => s.key === step);
  return (
    <ol className="grid grid-cols-3 gap-2 sm:gap-4" aria-label="Adımlar">
      {STEPS.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li
            key={s.key}
            aria-current={active ? "step" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors",
              active
                ? "border-cyan-600 bg-cyan-600/10 dark:border-cyan-500"
                : "border-border bg-card",
            )}
          >
            <span
              className={cn(
                "flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-bold",
                done
                  ? "bg-emerald-600 text-white"
                  : active
                    ? "bg-cyan-700 text-white"
                    : "bg-muted text-muted-foreground",
              )}
            >
              {done ? <Check className="size-4" aria-hidden /> : i + 1}
            </span>
            <span className="min-w-0">
              <span
                className={cn(
                  "block text-xs font-semibold leading-tight sm:text-sm",
                  active || done ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {s.title}
              </span>
              <span className="hidden text-xs text-muted-foreground sm:block">{s.hint}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

const COLUMNS: Array<{ name: string; desc: string; required?: boolean }> = [
  { name: "Ad Soyad", desc: "Öğrencinin adı ve soyadı", required: true },
  { name: "E-posta", desc: "Giriş adresi; her öğrencide farklı olmalı", required: true },
  { name: "Sınıf", desc: "5–12 ya da “mezun”" },
  { name: "Alan", desc: "11. sınıf ve mezun: sayısal / ea / sözel / dil" },
  { name: "Çalışma şekli", desc: "Mezun için: tam zamanlı / dershane" },
  { name: "Telefon", desc: "Öğrencinin cep telefonu" },
  { name: "Şube", desc: "Boş bırakılabilir; sonradan da atanır" },
  { name: "Veli adı · e-posta · telefon", desc: "Veli e-postası varsa veliye davet gider" },
  { name: "Yakınlık", desc: "anne / baba / vasi / diğer" },
];

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function countDataRows(text: string): number {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  return Math.max(0, lines.length - 1);
}

function InputStep({
  csvText,
  setCsvText,
  onSubmit,
  isPending,
}: {
  csvText: string;
  setCsvText: (s: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isPending: boolean;
}) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [file, setFile] = React.useState<{ name: string; size: number; sheet?: string } | null>(
    null,
  );
  const [reading, setReading] = React.useState(false);
  const [fileError, setFileError] = React.useState<string | null>(null);
  const [dragging, setDragging] = React.useState(false);
  const [showText, setShowText] = React.useState(false);

  async function handleFile(f: File) {
    setFileError(null);
    const lower = f.name.toLowerCase();
    if (lower.endsWith(".xls")) {
      setFileError(
        "Eski .xls biçimi okunamıyor. Dosyayı Excel'de “Farklı kaydet → .xlsx” ile kaydedip tekrar yükle.",
      );
      return;
    }
    if (!lower.endsWith(".xlsx") && !lower.endsWith(".csv") && !lower.endsWith(".txt")) {
      setFileError("Yalnız Excel (.xlsx) ya da CSV (.csv) dosyası yüklenebilir.");
      return;
    }
    setReading(true);
    try {
      if (lower.endsWith(".xlsx")) {
        const res = await convertStudentsXlsx(f);
        setCsvText(res.csv_text);
        setFile({ name: f.name, size: f.size, sheet: res.sheet });
      } else {
        setCsvText(await f.text());
        setFile({ name: f.name, size: f.size });
      }
    } catch (err) {
      setFileError(err instanceof ApiError ? err.message : "Dosya okunamadı.");
    } finally {
      setReading(false);
    }
  }

  function clearFile() {
    setFile(null);
    setCsvText("");
    setFileError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  const rows = countDataRows(csvText);

  return (
    <form onSubmit={onSubmit} className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="min-w-0 space-y-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) void handleFile(f);
          }}
          className={cn(
            "rounded-2xl border-2 border-dashed p-6 text-center transition-colors sm:p-10",
            dragging
              ? "border-cyan-500 bg-cyan-500/10"
              : "border-border bg-card hover:border-cyan-600/60",
          )}
          data-testid="import-dropzone"
        >
          <input
            ref={inputRef}
            id="csv-file"
            type="file"
            accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleFile(f);
            }}
          />
          <span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-cyan-700 text-white shadow-sm">
            {reading ? (
              <Loader2 className="size-7 animate-spin" aria-hidden />
            ) : (
              <FileSpreadsheet className="size-7" aria-hidden />
            )}
          </span>
          <p className="mt-4 text-base font-semibold text-foreground">
            {reading ? "Dosya okunuyor…" : "Öğrenci listeni buraya sürükle bırak"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Excel (.xlsx) ya da CSV (.csv) · en fazla 5 MB
          </p>
          <Button
            type="button"
            className="mt-5 bg-cyan-700 text-white hover:bg-cyan-800"
            onClick={() => inputRef.current?.click()}
            disabled={reading}
          >
            <Upload className="size-4" aria-hidden />
            Bilgisayardan dosya seç
          </Button>
        </div>

        {fileError ? (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200"
          >
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
            {fileError}
          </p>
        ) : null}

        {file ? (
          <div
            className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 dark:border-emerald-500/30 dark:bg-emerald-500/10"
            data-testid="import-file-chip"
          >
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-white">
              <FileSpreadsheet className="size-5" aria-hidden />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block break-all text-sm font-semibold text-emerald-950 dark:text-emerald-100">
                {file.name}
              </span>
              <span className="block text-xs text-emerald-800 dark:text-emerald-200/80">
                {formatBytes(file.size)}
                {file.sheet ? ` · “${file.sheet}” sayfası` : ""} · {rows} öğrenci satırı okundu
              </span>
            </span>
            <button
              type="button"
              onClick={clearFile}
              className="rounded-md p-1.5 text-emerald-800 hover:bg-emerald-100 dark:text-emerald-200 dark:hover:bg-emerald-500/20"
              aria-label="Dosyayı kaldır"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
        ) : null}

        <div className="rounded-xl border border-border bg-card">
          <button
            type="button"
            onClick={() => setShowText((v) => !v)}
            aria-expanded={showText}
            className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium text-foreground"
          >
            <ClipboardPaste className="size-4 text-muted-foreground" aria-hidden />
            <span className="flex-1">
              {file ? "Okunan metni gör / düzelt" : "Dosyan yoksa listeyi elle yapıştır"}
            </span>
            <ChevronDown
              className={cn(
                "size-4 text-muted-foreground transition-transform",
                showText && "rotate-180",
              )}
              aria-hidden
            />
          </button>
          {showText ? (
            <div className="space-y-2 border-t border-border px-4 pb-4 pt-3">
              <p className="text-xs text-muted-foreground">
                İlk satır başlık olmalı; sütunlar virgül, noktalı virgül ya da sekmeyle
                ayrılabilir (Excel&apos;den kopyalayıp yapıştırmak da olur).
              </p>
              <textarea
                id="csv-text"
                aria-label="Öğrenci listesi metni"
                value={csvText}
                onChange={(e) => setCsvText(e.target.value)}
                rows={10}
                className={cn(
                  "w-full rounded-lg border border-input bg-background p-3 font-mono text-xs",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
                placeholder={
                  "Ad Soyad,E-posta,Sınıf,Şube,Veli Adı,Veli E-posta\nAli Veli,ali@ornek.com,8,A,Ayşe Veli,ayse@ornek.com\n"
                }
              />
            </div>
          ) : null}
        </div>

        <div className="flex flex-col-reverse items-stretch gap-3 rounded-xl border border-border bg-card px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            {rows > 0
              ? `${rows} öğrenci satırı hazır. Sonraki adımda her satırı kontrol edeceksin; henüz hiçbir hesap açılmadı.`
              : "Önce bir dosya yükle ya da listeyi yapıştır."}
          </p>
          <Button
            type="submit"
            disabled={isPending || reading || !csvText.trim()}
            className="shrink-0 bg-cyan-700 text-white hover:bg-cyan-800"
          >
            {isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <ArrowRight className="size-4" aria-hidden />
            )}
            Kontrol et
          </Button>
        </div>
      </div>

      <aside className="space-y-4">
        <div className="rounded-2xl border border-border bg-card p-5">
          <h2 className="text-sm font-semibold text-foreground">Şablonla başla</h2>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Sütun adları hazır örnek dosya. Excel&apos;de açıp öğrencilerini gir, kaydet ve
            buraya yükle.
          </p>
          <a
            href="/api/v2/teacher/csv/import/students/template"
            className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
          >
            <Download className="size-4" aria-hidden />
            Örnek şablonu indir
          </a>
        </div>
        <div className="rounded-2xl border border-border bg-card p-5">
          <h2 className="text-sm font-semibold text-foreground">Tanınan sütunlar</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Sütun sırası önemli değil; Türkçe ya da İngilizce başlık olabilir.
          </p>
          <ul className="mt-3 space-y-2.5">
            {COLUMNS.map((c) => (
              <li key={c.name} className="text-sm">
                <span className="flex flex-wrap items-center gap-1.5">
                  <span className="font-medium text-foreground">{c.name}</span>
                  {c.required ? (
                    <span className="rounded bg-cyan-700 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                      Zorunlu
                    </span>
                  ) : null}
                </span>
                <span className="block text-xs leading-snug text-muted-foreground">{c.desc}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </form>
  );
}

function PreviewStep({
  preview,
  years,
  yearId,
  setYearId,
  onBack,
  onCommit,
  isPending,
}: {
  preview: CsvPreviewResponse;
  years: { id: number; name: string; exam_label: string }[];
  yearId: number | null;
  setYearId: (v: number | null) => void;
  onBack: () => void;
  onCommit: () => void;
  isPending: boolean;
}) {
  const fatal = preview.header_errors.length > 0;
  const withParent = preview.rows.filter((r) => r.is_valid && r.parent_email).length;
  const groups = Array.from(
    new Set(preview.rows.filter((r) => r.is_valid && r.class_group).map((r) => r.class_group as string)),
  ).sort((a, b) => a.localeCompare(b, "tr"));
  return (
    <div className="space-y-3">
      {fatal ? (
        <Card className="border-destructive/40">
          <CardContent className="p-4">
            <p className="font-medium text-destructive">CSV içe aktarılamaz</p>
            <ul className="text-sm mt-2 space-y-1">
              {preview.header_errors.map((e, i) => (
                <li key={i}>• {e}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
      <Card>
        <CardContent className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <Stat label="Toplam satır" value={preview.total_rows} />
          <Stat
            label="Geçerli"
            value={preview.valid_count}
            tone="success"
          />
          <Stat
            label="Hatalı"
            value={preview.invalid_count}
            tone={preview.invalid_count > 0 ? "warn" : undefined}
          />
          <Stat label="Veli daveti gidecek" value={withParent} />
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-4 space-y-3 text-sm">
          {groups.length > 0 ? (
            <p className="text-muted-foreground">
              <span className="font-medium text-foreground">Şubeler:</span>{" "}
              {groups.join(" · ")}
            </p>
          ) : null}
          <div className="space-y-1">
            <Label htmlFor="csv-year">Akademik yıl (isteğe bağlı)</Label>
            <select
              id="csv-year"
              value={yearId ?? ""}
              onChange={(e) => setYearId(e.target.value ? Number(e.target.value) : null)}
              className="w-full max-w-md rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">Seçme — sonra öğrenci profilinden atanır</option>
              {years.map((y) => (
                <option key={y.id} value={y.id}>
                  {y.name} · {y.exam_label}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Seçilen yıl bu dosyadaki tüm öğrencilere atanır (sınav tarihi ve
              dönem takvimi buradan gelir).
            </p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Satırlar</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {preview.rows.length === 0 ? (
            <p className="text-sm text-muted-foreground p-4">
              Hiç satır okunamadı.
            </p>
          ) : (
            <ul className="divide-y divide-border text-sm">
              {preview.rows.map((r) => (
                <li key={r.row_num} className="px-4 py-2">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span
                      className={cn(
                        "text-xs font-mono",
                        r.is_valid
                          ? "text-emerald-600"
                          : "text-rose-600",
                      )}
                    >
                      {r.is_valid ? "✓" : "✗"} #{r.row_num}
                    </span>
                    <span className="font-medium break-words">
                      {r.full_name ?? "—"}
                    </span>
                    <span className="text-xs text-muted-foreground break-all">
                      {r.email ?? "—"}
                      {r.grade_level !== null
                        ? ` · ${r.grade_level}. sınıf`
                        : r.is_graduate
                          ? " · mezun"
                          : ""}
                      {r.track ? ` · ${r.track}` : ""}
                      {r.phone ? ` · tel ${r.phone}` : ""}
                    </span>
                    {r.class_group ? (
                      <span className="rounded bg-slate-700 px-1.5 py-0.5 text-[11px] font-medium text-white">
                        {r.class_group}
                      </span>
                    ) : null}
                  </div>
                  {r.parent_email ? (
                    <p className="mt-0.5 flex items-start gap-1 text-xs text-muted-foreground break-words">
                      <Users className="mt-0.5 size-3 shrink-0" aria-hidden />
                      Veli: {r.parent_name ? `${r.parent_name} · ` : ""}
                      {r.parent_email}
                      {r.parent_phone ? ` · ${r.parent_phone}` : ""}
                      {r.parent_relation && r.parent_relation !== "diger" ? ` · ${r.parent_relation}` : ""}
                    </p>
                  ) : null}
                  {r.errors.length > 0 ? (
                    <p className="text-xs text-rose-600 mt-0.5">
                      {r.errors.join(" · ")}
                    </p>
                  ) : null}
                  {r.warnings.length > 0 ? (
                    <p className="text-xs text-amber-600 mt-0.5">
                      uyarı: {r.warnings.join(" · ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      <div className="flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={onBack} disabled={isPending}>
          Geri
        </Button>
        <Button
          onClick={onCommit}
          disabled={fatal || preview.valid_count === 0 || isPending}
        >
          {isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <CheckCircle2 className="size-4" aria-hidden />
          )}
          {preview.valid_count} öğrenciyi onayla ve oluştur
        </Button>
      </div>
    </div>
  );
}

function ResultStep({
  result,
  onReset,
}: {
  result: CsvCommitResult;
  onReset: () => void;
}) {
  const hasPasswords = result.created.length > 0;
  // Geçici şifreler yalnız bu ekranda var — sekme kapanırken/ yenilenirken uyar.
  React.useEffect(() => {
    if (!hasPasswords) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [hasPasswords]);

  function confirmLeave(e?: React.MouseEvent): boolean {
    if (!hasPasswords) return true;
    const ok = window.confirm(
      "Geçici şifreler bu sayfadan ayrılınca bir daha gösterilemez. Giriş kartlarını yazdırdın ya da Excel'e indirdin mi?",
    );
    if (!ok) e?.preventDefault();
    return ok;
  }

  return (
    <div className="space-y-3">
      {result.header_errors.length > 0 ? (
        <Card className="border-destructive/40">
          <CardContent className="p-4">
            <p className="font-medium text-destructive">Uyarı</p>
            <ul className="text-sm mt-2 space-y-1">
              {result.header_errors.map((e, i) => (
                <li key={i}>• {e}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <Stat
            label="Oluşturuldu"
            value={result.created_count}
            tone="success"
          />
          <Stat
            label="Atlandı"
            value={result.skipped_count}
            tone={result.skipped_count > 0 ? "warn" : undefined}
          />
          <Stat label="Veli daveti gönderildi" value={result.parents_invited ?? 0} tone="success" />
          <Stat
            label="Veli daveti gitmedi"
            value={result.parents_failed ?? 0}
            tone={(result.parents_failed ?? 0) > 0 ? "warn" : undefined}
          />
        </CardContent>
      </Card>

      {(result.parents_failed ?? 0) > 0 ? (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
          Bazı velilere davet gitmedi. Öğrencinin Veliler sekmesinden daveti
          yeniden gönderebilirsin (e-posta başka rolde kayıtlıysa farklı bir
          e-posta gerekir).
        </p>
      ) : null}

      {result.created.length > 0 ? (
        <Card>
          <CardHeader className="space-y-3">
            <CardTitle className="text-base">
              Geçici şifreler ({result.created.length})
            </CardTitle>
            <LoginCardsActions students={result.created} />
          </CardHeader>
          <CardContent className="p-0">
            <p className="mx-4 mt-1 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
              Şifreler yalnız bu ekranda görünür; sayfadan ayrılınca tekrar
              gösterilemez. Önce <b>giriş kartlarını yazdır</b> (A4&apos;e 8 kesilebilir
              kart: ad, e-posta, geçici şifre, giriş adresi ve QR) ya da{" "}
              <b>Excel&apos;e indir</b>. Öğrenci ilk girişte kendi şifresini belirler.
            </p>
            <ul className="divide-y divide-border text-sm mt-2">
              {result.created.map((c) => (
                <li
                  key={c.row_num}
                  className="px-4 py-2 flex items-center gap-3"
                >
                  <span className="flex-1 min-w-0">
                    <span className="font-medium break-words block">
                      {c.full_name}
                    </span>
                    <span className="text-xs text-muted-foreground break-all block">
                      {c.email} · {c.grade_label}
                      {c.class_group ? ` · ${c.class_group}` : ""}
                    </span>
                    {c.parent_status ? (
                      <span
                        className={cn(
                          "mt-0.5 inline-block rounded px-1.5 py-0.5 text-[11px] font-medium text-white",
                          c.parent_status === "invited" ? "bg-emerald-700" : "bg-amber-700",
                        )}
                      >
                        {c.parent_status === "invited"
                          ? `Veli daveti gönderildi · ${c.parent_email}`
                          : c.parent_status === "skipped_other_role"
                            ? `Veli e-postası başka rolde kayıtlı · ${c.parent_email}`
                            : `Veli daveti gitmedi · ${c.parent_email}`}
                      </span>
                    ) : null}
                  </span>
                  <span className="font-mono text-xs bg-muted px-2 py-1 rounded select-all">
                    {c.temp_password}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {result.skipped_existing_email.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Atlanan (e-posta zaten kayıtlı)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y divide-border text-sm">
              {result.skipped_existing_email.map((r) => (
                <li key={r.row_num} className="px-4 py-2">
                  #{r.row_num} {r.full_name} ({r.email})
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {result.skipped_invalid.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Atlanan (hatalı satır)</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y divide-border text-sm">
              {result.skipped_invalid.map((r) => (
                <li key={r.row_num} className="px-4 py-2">
                  <span className="font-medium">
                    #{r.row_num} {r.full_name ?? "—"}
                  </span>
                  <p className="text-xs text-rose-600 mt-0.5">
                    {r.errors.join(" · ")}
                  </p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <div className="flex items-center justify-end gap-2">
        <Link
          href="/teacher/students"
          onClick={(e) => confirmLeave(e)}
          className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted"
        >
          Öğrenci listesine git
        </Link>
        <Button onClick={() => { if (confirmLeave()) onReset(); }}>Yeni içe aktarma</Button>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "success" | "warn";
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "text-2xl font-semibold tabular-nums",
          tone === "success"
            ? "text-emerald-600"
            : tone === "warn"
              ? "text-amber-600"
              : "",
        )}
      >
        {value}
      </p>
    </div>
  );
}
