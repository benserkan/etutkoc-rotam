"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Gem, Lock, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getTeacherPlan, teacherKeys } from "@/lib/api/teacher";
import type { TeacherPlanResponse } from "@/lib/types/teacher";

export function TeacherPlanClient({ initial }: { initial: TeacherPlanResponse }) {
  const q = useQuery<TeacherPlanResponse>({
    queryKey: teacherKeys.plan(),
    queryFn: getTeacherPlan,
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <Gem className="size-5 text-cyan-700" aria-hidden /> Paket
        </h1>
        <p className="text-sm text-muted-foreground">
          Mevcut paketiniz ve yapay zekâ özelliklerine erişim durumu.
        </p>
      </header>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Mevcut paket</p>
            <p className="text-lg font-semibold">{data.plan_label}</p>
            {data.trial_active && data.trial_days_left != null ? (
              <p className="text-xs text-amber-700">Deneme sürümü — {data.trial_days_left} gün kaldı</p>
            ) : null}
          </div>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium",
              data.ai_premium
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-amber-200 bg-amber-50 text-amber-800",
            )}
          >
            {data.ai_premium ? <Sparkles className="size-3.5" aria-hidden /> : <Lock className="size-3.5" aria-hidden />}
            Yapay zekâ özellikleri {data.ai_premium ? "açık" : "kapalı"}
          </span>
        </CardContent>
      </Card>

      {!data.is_solo ? (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
          {data.note ?? "Paketiniz kurumunuz tarafından yönetilir."}
        </div>
      ) : (
        <Card>
          <CardContent className="space-y-3 p-4">
            {data.ai_premium ? (
              <p className="text-sm text-emerald-700">
                Ücretli paketiniz aktif — tüm yapay zekâ özellikleri açık.
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                Şu an ücretsiz paktesiniz. Daha fazla öğrenci + yapay zekâ özellikleri
                (sesli dikte, fotoğraftan doldurma, koçluk içgörüsü) için ücretli pakete geçin.
                Öğrenci sayınıza göre fiyatları planlar sayfasında görebilirsiniz.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <Link href="/pricing">
                  <ExternalLink className="size-4" aria-hidden /> Planları ve fiyatları gör
                </Link>
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Yükseltme manuel aktivasyonla yapılır — planı seçtikten sonra hesabınız
              aktive edilir. Sorular için bizimle iletişime geçin.
            </p>
          </CardContent>
        </Card>
      )}

      <p className="text-[11px] text-muted-foreground">
        Yapay zekâ özellikleri (sesli dikte, fotoğraftan seans doldurma, koçluk içgörüsü)
        yalnız ücretli paketlerde açıktır ve kendi kredinizden düşer.
      </p>
    </div>
  );
}
