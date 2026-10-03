"use client";

/**
 * Süper admin — "Tam kitap tara" (arka plan işi).
 *
 * Tam kitap PDF'i yüklenir → sunucu içindekileri okur, test sayısı yazmayan
 * konuları GÖVDEDEN sayar (metin katmanı ya da iki bağımsız görüntü geçişi) →
 * sağlamlık kapılarıyla birlikte TASLAK üretir. Admin sonucu açar, kapıları
 * görür ve "Kataloğa aktar" ile kayıt formunda düzeltip kaydeder. Tarama
 * hiçbir zaman doğrudan yayına çıkmaz.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  FileSearch,
  Loader2,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { bookCatalogKeys, getAdminScanJob, getAdminScanJobs } from "@/lib/api/book-catalog";
import { useCreateScanJob, useDeleteScanJob } from "@/lib/hooks/use-book-catalog-mutations";
import type { BookScanJobItem, BookScanResult } from "@/lib/types/book-catalog";

const STATUS_CLS: Record<string, string> = {
  queued: "bg-slate-600 text-white",
  running: "bg-cyan-700 text-white",
  done: "bg-emerald-600 text-white",
  failed: "bg-rose-600 text-white",
};

const SOURCE_LABELS: Record<string, string> = {
  toc: "içindekiler",
  scan: "görüntü taraması",
  scan_text: "metin katmanı",
  unknown: "taranamadı",
};

const FLAG_LABELS: Record<string, string> = {
  scan_mismatch: "iki tarama farklı",
  no_banner: "bant bulunamadı",
  no_page: "sayfa no yok",
  toc_count_mismatch: "içindekiler okumaları farklı",
};

const MODE_LABELS: Record<string, string> = {
  toc: "Sayılar içindekilerden alındı (gövde taranmadı)",
  text: "Gövde metin katmanından tarandı (dijital PDF)",
  vision: "Gövde görüntüden iki bağımsız geçişle tarandı (taranmış PDF)",
};

function fmtSize(b: number): string {
  return b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.round(b / 1024)} KB`;
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function ScanJobsPanel({ onImport }: { onImport: (r: BookScanResult) => void }) {
  const [file, setFile] = React.useState<File | null>(null);
  const [tocPages, setTocPages] = React.useState("12");
  const [offset, setOffset] = React.useState("");
  const [openId, setOpenId] = React.useState<number | null>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const listQ = useQuery({
    queryKey: bookCatalogKeys.adminScanJobs(),
    queryFn: getAdminScanJobs,
    refetchInterval: (q) =>
      q.state.data?.items.some((j) => j.status === "queued" || j.status === "running")
        ? 3000
        : false,
  });
  const create = useCreateScanJob();
  const del = useDeleteScanJob();
  const jobs = listQ.data?.items ?? [];

  const start = () => {
    if (!file) return;
    const tp = Math.max(2, Math.min(40, Number(tocPages) || 12));
    const off = offset.trim() === "" ? null : Number(offset);
    create.mutate(
      { file, tocPages: tp, pageOffset: Number.isFinite(off as number) ? off : null },
      {
        onSuccess: () => {
          setFile(null);
          if (fileRef.current) fileRef.current.value = "";
        },
      },
    );
  };

  return (
    <section className="mt-4 rounded-xl border border-border bg-card p-5" data-testid="scan-jobs-panel">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300">
          <FileSearch className="size-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Tam kitap tara (arka planda)</h2>
          <p className="mt-0.5 max-w-3xl text-sm text-muted-foreground">
            Kitabın tam PDF&apos;ini yükle (450 MB&apos;a kadar). Sistem içindekileri okur; test
            sayısı yazmayan konuları <strong>kitabın gövdesinden sayar</strong> (dijital PDF&apos;te
            metin katmanından, taranmış PDF&apos;te iki bağımsız görüntü geçişiyle). Sonuç bir{" "}
            <strong>taslaktır</strong>: sağlamlık kapılarını gör, &quot;Kataloğa aktar&quot; ile
            düzeltip kaydet. Taranmış 300 sayfalık bir kitap 10-20 dakika sürebilir — sayfayı
            kapatabilirsin.
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <label className="text-xs font-medium text-muted-foreground" htmlFor="scan-file">
            Kitap PDF&apos;i
          </label>
          <input
            ref={fileRef}
            id="scan-file"
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm file:mr-3 file:rounded-md file:border file:border-border file:bg-muted file:px-3 file:py-1.5 file:text-sm"
            data-testid="scan-file"
          />
          {file ? (
            <p className="mt-1 break-words text-xs text-muted-foreground">
              {file.name} · {fmtSize(file.size)}
            </p>
          ) : null}
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground" htmlFor="scan-toc">
            İçindekiler ilk kaç sayfada?
          </label>
          <Input
            id="scan-toc"
            value={tocPages}
            onChange={(e) => setTocPages(e.target.value)}
            inputMode="numeric"
            className="mt-1 h-9 w-24"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground" htmlFor="scan-offset">
            Sayfa kayması (boş = otomatik)
          </label>
          <Input
            id="scan-offset"
            value={offset}
            onChange={(e) => setOffset(e.target.value)}
            inputMode="numeric"
            placeholder="otomatik"
            className="mt-1 h-9 w-28"
          />
        </div>
        <Button onClick={start} disabled={!file || create.isPending} data-testid="scan-start">
          {create.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <Upload className="size-4" aria-hidden />
          )}
          {create.isPending ? "Yükleniyor…" : "Taramayı başlat"}
        </Button>
      </div>

      {jobs.length > 0 ? (
        <ul className="mt-4 divide-y divide-border rounded-lg border border-border" data-testid="scan-jobs">
          {jobs.map((j) => (
            <JobRow
              key={j.id}
              job={j}
              onOpen={() => setOpenId(j.id)}
              onDelete={() => del.mutate(j.id)}
              deleting={del.isPending && del.variables === j.id}
            />
          ))}
        </ul>
      ) : null}

      {openId != null ? (
        <ResultDialog
          jobId={openId}
          onClose={() => setOpenId(null)}
          onImport={(r) => {
            setOpenId(null);
            onImport(r);
          }}
        />
      ) : null}
    </section>
  );
}

function JobRow({
  job: j,
  onOpen,
  onDelete,
  deleting,
}: {
  job: BookScanJobItem;
  onOpen: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  const active = j.status === "queued" || j.status === "running";
  return (
    <li className="space-y-1.5 px-3 py-2.5" data-testid="scan-job-row">
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", STATUS_CLS[j.status])}>
          {j.status_label}
        </span>
        <span className="min-w-0 flex-1 break-words text-sm font-medium">{j.filename}</span>
        <span className="text-xs text-muted-foreground">
          {j.page_count ? `${j.page_count} sayfa · ` : ""}
          {fmtSize(j.file_size)} · {fmtTime(j.created_at)}
          {j.created_by_name ? ` · ${j.created_by_name}` : ""}
        </span>
      </div>
      {active ? (
        <div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-cyan-600 transition-all"
              style={{ width: `${Math.max(3, j.progress)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            %{j.progress} · {j.stage ?? "…"}
          </p>
        </div>
      ) : null}
      {j.status === "failed" && j.error ? (
        <p className="text-xs text-rose-700 dark:text-rose-300">{j.error}</p>
      ) : null}
      {j.status === "done" ? (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {j.book_title ? <span className="break-words font-medium">{j.book_title}</span> : null}
          <span className="text-muted-foreground">
            {j.section_count} bölüm · {j.total_tests} test
          </span>
          {j.needs_review ? (
            <span className="rounded-full bg-amber-500 px-2 py-0.5 font-semibold text-slate-950">
              Elle incele
            </span>
          ) : (
            <span className="rounded-full bg-emerald-600 px-2 py-0.5 font-semibold text-white">
              Kapılar temiz
            </span>
          )}
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {j.status === "done" ? (
          <Button size="sm" onClick={onOpen} data-testid="scan-open">
            Sonucu aç
          </Button>
        ) : null}
        {!active ? (
          <Button size="sm" variant="outline" onClick={onDelete} disabled={deleting}>
            <Trash2 className="size-4" aria-hidden /> Sil
          </Button>
        ) : null}
      </div>
    </li>
  );
}

function ResultDialog({
  jobId,
  onClose,
  onImport,
}: {
  jobId: number;
  onClose: () => void;
  onImport: (r: BookScanResult) => void;
}) {
  const q = useQuery({
    queryKey: bookCatalogKeys.adminScanJob(jobId),
    queryFn: () => getAdminScanJob(jobId),
  });
  const r = q.data?.result;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Tarama sonucu</DialogTitle>
          <DialogDescription className="break-words">
            {q.data?.filename}
            {r ? ` · ${r.sections.length} bölüm · ${r.total_tests} test` : ""}
          </DialogDescription>
        </DialogHeader>
        {q.isLoading ? (
          <p className="text-sm text-muted-foreground">
            <Loader2 className="mr-1 inline size-4 animate-spin" aria-hidden /> Yükleniyor…
          </p>
        ) : !r ? (
          <p className="text-sm text-muted-foreground">Sonuç yok.</p>
        ) : (
          <div className="space-y-4" data-testid="scan-result">
            <div className="grid gap-1 text-sm">
              {r.book_title ? (
                <p className="break-words">
                  <span className="text-muted-foreground">Kitap: </span>
                  <strong>{r.book_title}</strong>
                  {r.publisher ? ` · ${r.publisher}` : ""}
                </p>
              ) : null}
              <p className="text-muted-foreground">
                {MODE_LABELS[r.mode] ?? r.mode}
                {r.offset ? ` · sayfa kayması ${r.offset}` : ""}
              </p>
            </div>

            <div>
              <h3 className="mb-1.5 text-sm font-semibold">Sağlamlık kapıları</h3>
              <ul className="space-y-1" data-testid="scan-gates">
                {r.gates.map((g) => (
                  <li key={g.code} className="flex items-start gap-2 text-sm">
                    {g.ok ? (
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-300" aria-hidden />
                    ) : (
                      <XCircle className="mt-0.5 size-4 shrink-0 text-rose-600 dark:text-rose-300" aria-hidden />
                    )}
                    <span className="min-w-0 break-words">
                      <strong>{g.label}</strong> — {g.detail}
                    </span>
                  </li>
                ))}
              </ul>
              {r.needs_review ? (
                <p className="mt-2 rounded-md bg-amber-500 px-3 py-2 text-sm text-slate-950">
                  <AlertTriangle className="mr-1 inline size-4" aria-hidden />
                  Kapılardan geçemeyen var — kataloğa aktarmadan önce işaretli bölümleri kitapla
                  karşılaştır.
                </p>
              ) : null}
            </div>

            <div>
              <h3 className="mb-1.5 text-sm font-semibold">Bölümler</h3>
              <ol className="space-y-1">
                {r.sections.map((s, i) => (
                  <li
                    key={i}
                    className={cn(
                      "flex flex-wrap items-start gap-2 rounded-md border px-2 py-1.5 text-sm",
                      s.flag || s.test_count == null
                        ? "border-amber-300 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10"
                        : "border-border",
                    )}
                  >
                    <span className="w-6 shrink-0 text-right text-xs text-muted-foreground">{i + 1}.</span>
                    <span className="min-w-0 flex-1 break-words">
                      {s.label}
                      {s.page ? <span className="text-xs text-muted-foreground"> · s. {s.page}</span> : null}
                    </span>
                    <span className="shrink-0 font-semibold tabular-nums">
                      {s.test_count ?? "?"} test
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {SOURCE_LABELS[s.source ?? ""] ?? s.source}
                    </span>
                    {s.flag ? (
                      <span className="shrink-0 rounded bg-amber-500 px-1.5 py-0.5 text-[10px] font-semibold text-slate-950">
                        {FLAG_LABELS[s.flag] ?? s.flag}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ol>
            </div>

            {r.warnings.length > 0 ? (
              <details className="text-xs text-muted-foreground">
                <summary className="cursor-pointer">Ayrıntılı uyarılar ({r.warnings.length})</summary>
                <ul className="mt-1 space-y-0.5">
                  {r.warnings.map((w, i) => (
                    <li key={i} className="break-words">• {w}</li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Kapat
          </Button>
          <Button disabled={!r} onClick={() => r && onImport(r)} data-testid="scan-import">
            Kataloğa aktar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
