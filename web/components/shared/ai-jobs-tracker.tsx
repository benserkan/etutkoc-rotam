"use client";

/**
 * Arka planda okunan karneler — "havada kalmasın" (2026-10-29).
 *
 * AiJobsTracker: koç ve öğrenci panelinin HER sayfasında köşede durur. Okuma
 * bitince kalıcı bir kutu çıkar ("Zeynep'in karnesi okundu — Önizle"); kutu
 * kendi kendine kaybolmaz, kullanıcı önizleyene ya da kapatana kadar her
 * sayfada görünür. Okuma sürerken küçük bir "N karne okunuyor" satırı durur.
 *
 * ExamImportJobsBand: öğrencinin Denemeler sekmesinde, o öğrencinin açık
 * işleri (okunuyor / önizleme bekliyor / okunamadı) — kutu kapatılsa bile
 * taslak burada kaydedilene ya da vazgeçilene kadar bekler (7 gün).
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileText, Loader2, RefreshCw, X } from "lucide-react";
import { toast } from "sonner";

import { ExamImportDialog } from "@/components/shared/exam-import-dialog";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { aiJobAction, aiJobsKey, getAiJobs } from "@/lib/api/exam-import";
import { applyInvalidate } from "@/lib/invalidate";
import type { AiJobBrief } from "@/lib/types/exam-import";

type Audience = "teacher" | "student";

function useJobAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: "ack" | "dismiss" | "retry" }) =>
      aiJobAction(id, action),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
    onError: (e) => {
      toast.error("İşlem yapılamadı", {
        description: e instanceof ApiError ? e.message : undefined,
      });
    },
  });
}

function jobTitle(j: AiJobBrief, audience: Audience): string {
  if (audience === "student" || j.own_upload) return "Deneme karnen";
  return j.student_name ? `${j.student_name} — deneme karnesi` : "Deneme karnesi";
}

function OpenDialog({
  job,
  audience,
  onClose,
}: {
  job: AiJobBrief;
  audience: Audience;
  onClose: () => void;
}) {
  return (
    <ExamImportDialog
      open
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
      jobId={job.id}
      studentId={audience === "teacher" ? (job.student_id ?? undefined) : undefined}
    />
  );
}

export function AiJobsTracker({ audience }: { audience: Audience }) {
  const { data } = useQuery({
    queryKey: aiJobsKey(),
    queryFn: () => getAiJobs(),
    refetchInterval: (q) => ((q.state.data?.active_count ?? 0) > 0 ? 4000 : 30000),
    refetchOnWindowFocus: true,
    staleTime: 2000,
  });
  const act = useJobAction();
  const [opened, setOpened] = React.useState<AiJobBrief | null>(null);

  const items = data?.items ?? [];
  const notices = items.filter(
    (j) => (j.status === "done" || j.status === "failed") && !j.acknowledged,
  );
  const active = items.filter((j) => j.status === "queued" || j.status === "running");
  if (!notices.length && !active.length && !opened) return null;

  return (
    <>
      <div
        className="fixed right-4 top-[4.5rem] z-[60] flex w-[min(23rem,calc(100vw-2rem))] flex-col gap-2 lg:top-4"
        aria-live="polite"
        data-section="ai-jobs-tracker"
      >
        {notices.slice(0, 3).map((j) => (
          <div
            key={j.id}
            role="status"
            className={
              j.status === "done"
                ? "rounded-2xl border border-emerald-300 bg-white p-4 shadow-lg ring-1 ring-emerald-500/20"
                : "rounded-2xl border border-rose-300 bg-white p-4 shadow-lg ring-1 ring-rose-500/20"
            }
          >
            <div className="flex items-start gap-3">
              {j.status === "done" ? (
                <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" aria-hidden />
              ) : (
                <AlertTriangle className="mt-0.5 size-5 shrink-0 text-rose-600" aria-hidden />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-900">
                  {j.status === "done" ? "Karne okundu" : "Karne okunamadı"}
                </p>
                <p className="mt-0.5 text-sm text-slate-600">
                  {jobTitle(j, audience)}
                  {j.status === "done"
                    ? " hazır. Kontrol edip kaydetmen gerekiyor."
                    : `: ${j.error_message ?? "okuma tamamlanamadı."}`}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {j.status === "done" ? (
                    <Button
                      size="sm"
                      className="bg-emerald-700 text-white hover:bg-emerald-800"
                      onClick={() => {
                        setOpened(j);
                        act.mutate({ id: j.id, action: "ack" });
                      }}
                    >
                      Önizle ve kaydet
                    </Button>
                  ) : j.retryable ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1.5"
                      disabled={act.isPending}
                      onClick={() => act.mutate({ id: j.id, action: "retry" })}
                    >
                      <RefreshCw className="size-3.5" aria-hidden />
                      Tekrar dene (ücretsiz)
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-slate-600"
                    onClick={() => act.mutate({ id: j.id, action: "ack" })}
                  >
                    {j.status === "done" ? "Sonra" : "Tamam"}
                  </Button>
                </div>
              </div>
              <button
                type="button"
                aria-label="Bildirimi kapat"
                className="rounded-md p-1 text-slate-400 hover:text-slate-700"
                onClick={() => act.mutate({ id: j.id, action: "ack" })}
              >
                <X className="size-4" />
              </button>
            </div>
          </div>
        ))}
        {notices.length > 3 ? (
          <p className="rounded-xl bg-white px-3 py-2 text-xs text-slate-600 ring-1 ring-slate-200">
            +{notices.length - 3} karne daha hazır — öğrencinin Denemeler sekmesinden açabilirsin.
          </p>
        ) : null}
        {active.length ? (
          <div className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-xs text-slate-700 ring-1 ring-slate-200">
            <Loader2 className="size-3.5 animate-spin text-violet-600" aria-hidden />
            {active.length === 1
              ? `${jobTitle(active[0], audience)} okunuyor…`
              : `${active.length} karne okunuyor…`}
          </div>
        ) : null}
      </div>
      {opened ? <OpenDialog job={opened} audience={audience} onClose={() => setOpened(null)} /> : null}
    </>
  );
}

/** Denemeler sekmesinde o öğrencinin açık işleri (kutu kapatılsa da burada kalır). */
export function ExamImportJobsBand({
  studentId,
  audience,
}: {
  studentId?: number;
  audience: Audience;
}) {
  const { data } = useQuery({
    queryKey: aiJobsKey(studentId ?? null),
    queryFn: () => getAiJobs(studentId ?? null),
    refetchInterval: (q) => ((q.state.data?.active_count ?? 0) > 0 ? 4000 : 30000),
  });
  const act = useJobAction();
  const [opened, setOpened] = React.useState<AiJobBrief | null>(null);
  const items = data?.items ?? [];
  if (!items.length && !opened) return null;

  return (
    <div className="space-y-2" data-section="exams:import-jobs">
      {items.map((j) => (
        <div
          key={j.id}
          className="flex flex-wrap items-center gap-3 rounded-xl border border-violet-200 bg-violet-50 px-4 py-3"
        >
          {j.status === "queued" || j.status === "running" ? (
            <Loader2 className="size-4 shrink-0 animate-spin text-violet-700" aria-hidden />
          ) : j.status === "failed" ? (
            <AlertTriangle className="size-4 shrink-0 text-rose-700" aria-hidden />
          ) : (
            <FileText className="size-4 shrink-0 text-emerald-700" aria-hidden />
          )}
          <div className="min-w-0 flex-1 text-sm">
            <span className="font-medium text-slate-900">
              {j.filename ?? "Deneme karnesi"}
            </span>
            <span className="text-slate-600">
              {" · "}
              {j.status === "failed" ? (j.error_message ?? j.status_label) : (j.stage ?? j.status_label)}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {j.status === "done" ? (
              <Button
                size="sm"
                className="bg-emerald-700 text-white hover:bg-emerald-800"
                onClick={() => {
                  setOpened(j);
                  if (!j.acknowledged) act.mutate({ id: j.id, action: "ack" });
                }}
              >
                Önizle ve kaydet
              </Button>
            ) : null}
            {j.status === "failed" && j.retryable ? (
              <Button
                size="sm"
                variant="outline"
                disabled={act.isPending}
                onClick={() => act.mutate({ id: j.id, action: "retry" })}
              >
                Tekrar dene
              </Button>
            ) : null}
            {j.status === "done" || j.status === "failed" ? (
              <Button
                size="sm"
                variant="ghost"
                className="text-slate-600"
                disabled={act.isPending}
                onClick={() => {
                  if (j.status === "done" && !window.confirm("Bu karneyi kaydetmeden silmek istiyor musun?")) return;
                  act.mutate({ id: j.id, action: "dismiss" });
                }}
              >
                {j.status === "done" ? "Vazgeç" : "Kaldır"}
              </Button>
            ) : null}
          </div>
        </div>
      ))}
      {opened ? <OpenDialog job={opened} audience={audience} onClose={() => setOpened(null)} /> : null}
    </div>
  );
}
