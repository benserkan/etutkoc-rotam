"use client";

import { Compass } from "lucide-react";

import { GuidePlayer } from "@/components/guide/guide-player";
import { GUIDES } from "@/components/guide/coach-guide-data";
import { useGuide, useGuideProgress } from "@/lib/hooks/use-guide";

interface Props {
  /** Rehber anahtarı (coach_onboarding | student_onboarding). */
  guideKey: string;
  title: string;
  description: string;
}

/** Rehber sayfası istemcisi — durum + kontrol listesi + oynatıcı (rol bazlı). */
export function GuideClient({ guideKey, title, description }: Props) {
  const content = GUIDES[guideKey];
  const q = useGuide(guideKey);
  const progress = useGuideProgress(guideKey);

  const doneCount = q.data?.state.chapters_done.length ?? 0;
  const total = content.chapters.length;
  const pct = Math.round((doneCount / total) * 100);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 p-4 sm:p-6">
      <header className="flex flex-wrap items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-600 text-white">
          <Compass className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-semibold sm:text-xl">{title}</h1>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-28 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-xs font-medium text-muted-foreground">
            {doneCount}/{total} bölüm
          </span>
        </div>
      </header>

      {q.isLoading ? (
        <div className="flex h-64 items-center justify-center rounded-xl border bg-card text-sm text-muted-foreground">
          Rehber yükleniyor…
        </div>
      ) : q.data ? (
        <GuidePlayer
          guide={q.data}
          content={content}
          busy={progress.isPending}
          refreshing={q.isRefetching}
          onProgress={(body) => progress.mutateAsync(body)}
          onRefresh={() => void q.refetch()}
        />
      ) : (
        <div className="flex h-64 items-center justify-center rounded-xl border bg-card text-sm text-muted-foreground">
          Rehber yüklenemedi. Sayfayı yenilemeyi dene.
        </div>
      )}
    </div>
  );
}
