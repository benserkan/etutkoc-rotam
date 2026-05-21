"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, Download, Loader2, Upload } from "lucide-react";

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
      { body: { csv_text: csvText } },
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
          için bir öğrenci hesabı oluşturulur ve geçici şifre döner.
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
            <span className="text-xs text-muted-foreground">
              · Zorunlu sütunlar: full_name, email · isteğe bağlı: grade_level,
              track, is_graduate, graduate_mode
            </span>
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
                "full_name,email,grade_level,track,is_graduate,graduate_mode\nAli Veli,ali@x.com,8,,,\n"
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
  onBack,
  onCommit,
  isPending,
}: {
  preview: CsvPreviewResponse;
  onBack: () => void;
  onCommit: () => void;
  isPending: boolean;
}) {
  const fatal = preview.header_errors.length > 0;
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
        <CardContent className="p-4 grid grid-cols-3 gap-3 text-sm">
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
                  <div className="flex items-center gap-2">
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
                    <span className="font-medium truncate">
                      {r.full_name ?? "—"}
                    </span>
                    <span className="text-xs text-muted-foreground truncate">
                      {r.email ?? "—"}
                      {r.grade_level !== null
                        ? ` · ${r.grade_level}. sınıf`
                        : r.is_graduate
                          ? " · mezun"
                          : ""}
                      {r.track ? ` · ${r.track}` : ""}
                    </span>
                  </div>
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
        <CardContent className="p-4 grid grid-cols-2 gap-3 text-sm">
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
        </CardContent>
      </Card>

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
                    <span className="font-medium truncate block">
                      {c.full_name}
                    </span>
                    <span className="text-xs text-muted-foreground truncate block">
                      {c.email} · {c.grade_label}
                    </span>
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
