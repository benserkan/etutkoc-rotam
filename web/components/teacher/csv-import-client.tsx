"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Download, Loader2, Upload, Users } from "lucide-react";

import { academicKeys, getAcademicYears } from "@/lib/api/academic";

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

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    file.text().then((text) => setCsvText(text));
  }

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
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          <Link href="/teacher/students" className="hover:underline">
            Öğrenciler
          </Link>
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          CSV ile öğrenci ekle
        </h1>
        <p className="text-sm text-muted-foreground">
          1. CSV yükle/yapıştır → 2. Önizleme → 3. Onayla. Her başarılı satır
          için bir öğrenci hesabı oluşturulur ve geçici şifre döner. Satırda
          veli e-postası varsa veliye davet bağlantısı otomatik gönderilir.
        </p>
      </header>

      <StepIndicator step={step} />

      {step === "input" ? (
        <InputStep
          csvText={csvText}
          setCsvText={setCsvText}
          onFile={onFile}
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

function StepIndicator({ step }: { step: Step }) {
  const steps: Array<{ key: Step; label: string }> = [
    { key: "input", label: "1. Yükle" },
    { key: "preview", label: "2. Önizleme" },
    { key: "result", label: "3. Sonuç" },
  ];
  return (
    <div className="flex items-center gap-2 text-xs">
      {steps.map((s, i) => {
        const isActive = step === s.key;
        const isPast =
          (step === "preview" && i === 0) ||
          (step === "result" && i < 2);
        return (
          <span
            key={s.key}
            className={cn(
              "px-2 py-1 rounded-md border",
              isActive
                ? "border-foreground font-medium"
                : isPast
                  ? "border-border bg-muted text-muted-foreground"
                  : "border-border text-muted-foreground",
            )}
          >
            {s.label}
          </span>
        );
      })}
    </div>
  );
}

function InputStep({
  csvText,
  setCsvText,
  onFile,
  onSubmit,
  isPending,
}: {
  csvText: string;
  setCsvText: (s: string) => void;
  onFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (e: React.FormEvent) => void;
  isPending: boolean;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">CSV içeriği</CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <a
              href="/api/v2/teacher/csv/import/students/template"
              className="inline-flex items-center gap-1 text-foreground underline-offset-4 hover:underline"
            >
              <Download className="size-3.5" aria-hidden />
              Örnek şablon indir
            </a>
          </div>
          <div className="rounded-md border border-border p-3 text-xs text-muted-foreground space-y-1">
            <p>
              <span className="font-medium text-foreground">Zorunlu:</span>{" "}
              full_name (ad soyad), email
            </p>
            <p>
              <span className="font-medium text-foreground">Öğrenci:</span>{" "}
              grade_level (5-12 ya da &quot;mezun&quot;), track (11. sınıf ve
              mezun için sayisal/ea/sozel/dil), graduate_mode (mezun için
              full_time/dershane), phone, class_group (şube, örn. 10-A)
            </p>
            <p>
              <span className="font-medium text-foreground">Veli:</span>{" "}
              parent_name, parent_email, parent_phone, parent_relation
              (anne/baba/vasi/diğer). Veli e-postası verilirse davet otomatik
              gider; ad ve telefon velinin kayıt formunda dolu gelir.
            </p>
            <p>Türkçe başlıklar da tanınır: ad soyad, e-posta, sınıf, alan, şube, telefon, veli adı, veli e-posta, veli telefonu, yakınlık.</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="csv-file">Dosyadan yükle</Label>
            <input
              id="csv-file"
              type="file"
              accept=".csv,text/csv"
              onChange={onFile}
              className="text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="csv-text">veya doğrudan yapıştır</Label>
            <textarea
              id="csv-text"
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              rows={10}
              className={cn(
                "w-full rounded-md border border-input bg-background p-3 font-mono text-xs",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
              placeholder={
                "full_name,email,grade_level,track,class_group,parent_name,parent_email\nAli Veli,ali@x.com,8,,8-A,Ayşe Veli,ayse@x.com\n"
              }
            />
          </div>
        </CardContent>
      </Card>
      <div className="flex items-center justify-end gap-2">
        <Button type="submit" disabled={isPending || !csvText.trim()}>
          {isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <Upload className="size-4" aria-hidden />
          )}
          Önizleme
        </Button>
      </div>
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
          <CardHeader>
            <CardTitle className="text-base">
              Geçici şifreler ({result.created.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <p className="text-xs text-muted-foreground px-4 pt-3">
              Şifreler tek seferlik gösterilir. Bu sayfadan ayrıldığınızda
              tekrar görüntülenemez — gerekirse not alın veya öğrencilere
              güvenli yoldan iletin.
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
          className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted"
        >
          Öğrenci listesine git
        </Link>
        <Button onClick={onReset}>Yeni içe aktarma</Button>
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
