"use client";

import { Check, PlayCircle } from "lucide-react";

import { COACH_GUIDE, estimateDurationMs } from "@/components/guide/coach-guide-data";
import { GuideAvatar } from "@/components/guide/guide-avatar";
import { useGuide } from "@/lib/hooks/use-guide";
import { cn } from "@/lib/utils";

/**
 * Sayfa içi "Nasıl kullanılır?" eğitimi — Rota Rehberi'nin ilgili KONUSUNU açar.
 *
 * İçerik TEK KAYNAK: coach-guide-content.json (ilk giriş rehberiyle aynı bölümler).
 * Konunun bölümleri henüz izlenmemişse sayfanın üstünde dikkat çeken bir kart
 * görünür (yeni koç); hepsi izlendiyse küçük bir düğmeye iner.
 *
 * Kullanım: <GuideHint module="Kitaplar" />
 */
export function GuideHint({ module, className }: { module: string; className?: string }) {
  const chapters = COACH_GUIDE.chapters.filter((c) => c.module === module);
  const q = useGuide(COACH_GUIDE.guideKey);
  if (chapters.length === 0) return null;

  const watched = q.data?.state.steps_watched ?? {};
  const done = new Set(q.data?.state.chapters_done ?? []);
  const isFinished = (key: string) => {
    const ch = chapters.find((c) => c.key === key);
    if (!ch) return false;
    return done.has(key) || (watched[key]?.length ?? 0) >= ch.steps.length;
  };
  const finishedCount = chapters.filter((c) => isFinished(c.key)).length;
  const allFinished = finishedCount === chapters.length;
  const started = chapters.some((c) => (watched[c.key]?.length ?? 0) > 0);
  const next = chapters.find((c) => !isFinished(c.key)) ?? chapters[0];
  const minutes = Math.max(
    1,
    Math.round(
      chapters.reduce(
        (sum, c) => sum + c.steps.reduce((t, st) => t + estimateDurationMs(st.caption), 0),
        0,
      ) / 60000,
    ),
  );
  const href = `/teacher/guide?bolum=${encodeURIComponent(next.key)}`;

  // Veri yüklenene kadar yer kaplama (kartın açılıp kapanıp zıplamasın)
  if (q.isLoading) return null;

  if (allFinished) {
    return (
      <a
        data-section="guide-hint"
        href={`/teacher/guide?bolum=${encodeURIComponent(chapters[0].key)}`}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border border-cyan-300 bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-800 transition hover:bg-cyan-100 dark:border-cyan-500/30 dark:bg-cyan-500/15 dark:text-cyan-200",
          className,
        )}
      >
        <Check className="size-3.5" aria-hidden />
        Nasıl kullanılır? · eğitimi yeniden izle
      </a>
    );
  }

  return (
    <div
      data-section="guide-hint"
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-cyan-300 bg-gradient-to-r from-cyan-50 to-white p-3 shadow-sm sm:flex-row sm:items-center sm:p-4 dark:border-cyan-500/30 dark:from-cyan-500/15 dark:to-transparent",
        className,
      )}
    >
      <GuideAvatar size={56} className="shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-cyan-950 dark:text-cyan-100">
          {started
            ? `${module} eğitimine kaldığın yerden devam et`
            : `Bu sayfayı ilk kez mi kullanıyorsun? ${module} eğitimini izle`}
        </p>
        <p className="mt-0.5 text-xs text-slate-700 dark:text-slate-300">
          Rota, gerçek ekranlar üzerinde sesli anlatıyor · {chapters.length} bölüm · yaklaşık{" "}
          {minutes} dakika
          {finishedCount > 0 ? ` · ${finishedCount}/${chapters.length} bölüm izlendi` : ""}
        </p>
      </div>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-cyan-700"
      >
        <PlayCircle className="size-4" aria-hidden />
        {started ? "Devam et" : "Eğitimi izle"}
      </a>
    </div>
  );
}
