"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, RotateCcw } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { getStudentReview, studentKeys } from "@/lib/api/student";
import { useReviewRate } from "@/lib/hooks/use-student-mutations";
import type { ReviewResponse } from "@/lib/types/student";

interface Props {
  initial: ReviewResponse;
}

const RATINGS = [
  { value: 1 as const, label: "Tekrar", color: "bg-rose-100 text-rose-800 hover:bg-rose-200 dark:bg-rose-900/40 dark:text-rose-200" },
  { value: 2 as const, label: "Zor", color: "bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-900/40 dark:text-amber-200" },
  { value: 3 as const, label: "İyi", color: "bg-emerald-100 text-emerald-800 hover:bg-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200" },
  { value: 4 as const, label: "Kolay", color: "bg-sky-100 text-sky-800 hover:bg-sky-200 dark:bg-sky-900/40 dark:text-sky-200" },
];

/**
 * Tekrar paneli — FSRS spaced repetition kuyruğu.
 *
 * Optimistic strateji (kullanıcı kararı): rated kart anında listeden çıkar +
 * breakdown'da counter düşer. Backend invalidate sonrası gerçek snapshot oturur.
 * Boş kuyrukta tebrik mesajı.
 */
export function ReviewClient({ initial }: Props) {
  const qc = useQueryClient();
  const q = useQuery<ReviewResponse>({
    queryKey: studentKeys.review(),
    queryFn: () => getStudentReview(),
    initialData: initial,
    staleTime: 60_000,
  });
  const rate = useReviewRate();
  const [revealed, setRevealed] = React.useState(false);

  if (q.isError) {
    return <ErrorState onRetry={() => q.refetch()} />;
  }
  const data = q.data ?? initial;
  const due = data.due_cards;
  const current = due[0];

  function submitRating(rating: 1 | 2 | 3 | 4) {
    if (!current) return;
    // Optimistic: kartı listeden çıkar + breakdown'u rating'e göre kabaca güncelle
    const key = studentKeys.review();
    qc.setQueryData<ReviewResponse>(key, (prev) => {
      if (!prev) return prev;
      const nextBreakdown = { ...prev.breakdown };
      nextBreakdown.due_now = Math.max(0, nextBreakdown.due_now - 1);
      // Yeni kart ise: new -1, learning +1 (kabaca)
      if (current.state === "new") {
        nextBreakdown.new = Math.max(0, nextBreakdown.new - 1);
        if (rating === 1) {
          nextBreakdown.learning += 1;
        } else {
          nextBreakdown.review += 1;
        }
      } else if (current.state === "learning") {
        if (rating >= 3) {
          nextBreakdown.learning = Math.max(0, nextBreakdown.learning - 1);
          nextBreakdown.review += 1;
        }
      } else if (rating === 1) {
        // review/relearning + AGAIN → relearning
        nextBreakdown.review = Math.max(0, nextBreakdown.review - 1);
        nextBreakdown.relearning += 1;
      }
      return {
        ...prev,
        due_cards: prev.due_cards.filter((c) => c.id !== current.id),
        breakdown: nextBreakdown,
      };
    });
    setRevealed(false);
    rate.mutate({ cardId: current.id, rating });
  }

  return (
    <div className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
          Tekrar kuyruğu
        </h1>
        <p className="text-sm text-muted-foreground">
          Konularını aralıklı tekrar et — sistem zorlandığın konuları daha sık
          önüne getirir.
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <BreakdownPill label="Şu an" value={data.breakdown.due_now} tone="dikkat" />
          <BreakdownPill label="Yeni" value={data.breakdown.new} />
          <BreakdownPill label="Öğreniliyor" value={data.breakdown.learning} />
          <BreakdownPill label="Pekiştirme" value={data.breakdown.review} />
          <BreakdownPill label="Yeniden" value={data.breakdown.relearning} />
          <span className="ml-auto text-muted-foreground">
            Toplam {data.breakdown.total} kart
          </span>
        </div>
      </header>

      {!current ? (
        <div className="rounded-xl border border-emerald-300/40 bg-emerald-50 dark:bg-emerald-950/20 px-6 py-10 text-center">
          <CheckCircle2 className="size-10 mx-auto text-emerald-500" aria-hidden />
          <p className="font-display text-xl font-semibold mt-3">
            Bu an için kart yok 🎉
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            Yeni kartlar koçun seed&apos;lediğinde veya vade dolduğunda burada
            çıkar.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card p-6 space-y-5">
          <div className="flex items-baseline justify-between">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {current.subject_name ?? "Konu"} · {STATE_LABEL[current.state]}
            </p>
            <p className="text-xs text-muted-foreground tabular-nums">
              {current.review_count} tekrar · {current.lapse_count} hata
            </p>
          </div>

          <p className="font-display text-3xl font-bold tracking-tight">
            {current.topic_name}
          </p>

          {revealed ? (
            <div className="rounded-md bg-muted/50 p-4 text-sm">
              <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                Kendine sor:
              </p>
              <p>
                Bu konunun temel kavramlarını, formüllerini ve tipik soru
                örüntüsünü 1-2 dakika içinde aklında canlandırabiliyor musun?
                Aşağıdaki butonla kendini değerlendir.
              </p>
            </div>
          ) : (
            <Button
              type="button"
              variant="outline"
              onClick={() => setRevealed(true)}
              className="w-full"
            >
              <RotateCcw className="size-4" aria-hidden /> Hatırlamayı dene
            </Button>
          )}

          {revealed ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {RATINGS.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => submitRating(r.value)}
                  disabled={rate.isPending}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    r.color,
                    rate.isPending ? "opacity-50 cursor-not-allowed" : "",
                  )}
                >
                  {rate.isPending ? <Loader2 className="size-3.5 animate-spin inline mr-1" /> : null}
                  {r.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

const STATE_LABEL: Record<string, string> = {
  new: "Yeni",
  learning: "Öğreniliyor",
  review: "Pekiştirme",
  relearning: "Yeniden öğrenme",
};

function BreakdownPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "dikkat";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 tabular-nums",
        tone === "dikkat"
          ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
          : "bg-muted text-foreground",
      )}
    >
      <span className="opacity-70">{label}</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}
