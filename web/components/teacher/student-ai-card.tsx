"use client";

/**
 * Öğrenci detay — "Yapay zekâ erişimi" kartı (2026-08-03).
 *
 * Koç, kredisinin bu öğrenci üzerinden harcanmasını kişi bazında yönetir:
 *  - Öğrenci özellikleri: YSA yapay zekâ etiketleme + deneme PDF okutma
 *    (öğrencinin KENDİ tetiklemesi; koçun tetiklemeleri her zaman açık).
 *  - Veli asistanı: Rota yorumu/sohbeti/sesli özellikler (bu öğrencinin velileri).
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import { getTeacherAiToggles, teacherKeys } from "@/lib/api/teacher";
import { useSetStudentAiToggles } from "@/lib/hooks/use-teacher-mutations";
import type { AiTogglesResponse } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

function ToggleRow({
  title,
  description,
  enabled,
  pending,
  onToggle,
}: {
  title: string;
  description: string;
  enabled: boolean;
  pending: boolean;
  onToggle: (next: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 py-2">
      <div className="min-w-0">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <button
        type="button"
        onClick={() => onToggle(!enabled)}
        disabled={pending}
        className={cn(
          "shrink-0 rounded-full px-3 py-1 text-xs font-semibold transition",
          pending && "opacity-60",
          enabled
            ? "bg-emerald-600 text-white hover:bg-emerald-700"
            : "bg-slate-200 text-slate-700 hover:bg-slate-300 dark:bg-slate-500/20 dark:text-slate-300",
        )}
      >
        {pending ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : enabled ? (
          "Açık"
        ) : (
          "Kapalı"
        )}
      </button>
    </div>
  );
}

export function StudentAiCard({ studentId }: { studentId: number }) {
  const q = useQuery<AiTogglesResponse>({
    queryKey: teacherKeys.aiToggles(studentId),
    queryFn: () => getTeacherAiToggles(studentId),
    staleTime: 30_000,
  });
  const mut = useSetStudentAiToggles(studentId);
  const d = q.data;
  if (!d) return null;

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <Sparkles className="size-4 text-violet-600" aria-hidden />
        Yapay zekâ erişimi
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Bu öğrenci üzerinden yapılan yapay zekâ harcamaları senin kredinden düşer;
        buradan kişiye özel kapatabilirsin. Kendi tetiklediğin araçlar etkilenmez.
      </p>
      <div className="mt-2 divide-y divide-border">
        <ToggleRow
          title="Öğrenci özellikleri"
          description="Yanlış soru yapay zekâ etiketleme + deneme PDF okutma (öğrencinin tetiklemesi)"
          enabled={d.student_ai_enabled}
          pending={mut.isPending && mut.variables?.student_ai_enabled !== undefined}
          onToggle={(next) => mut.mutate({ student_ai_enabled: next })}
        />
        <ToggleRow
          title="Veli asistanı (Rota)"
          description="Velinin yapay zekâ yorumu, sohbeti ve sesli özellikleri"
          enabled={d.parent_ai_enabled}
          pending={mut.isPending && mut.variables?.parent_ai_enabled !== undefined}
          onToggle={(next) => mut.mutate({ parent_ai_enabled: next })}
        />
      </div>
    </section>
  );
}
