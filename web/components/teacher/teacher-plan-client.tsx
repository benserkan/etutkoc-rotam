"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Gem, Loader2, Lock, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getTeacherPlan, teacherKeys } from "@/lib/api/teacher";
import { useUpgradePlan } from "@/lib/hooks/use-teacher-mutations";
import type { TeacherPlanOption, TeacherPlanResponse } from "@/lib/types/teacher";

function priceLabel(p: number): string {
  if (p === 0) return "Ücretsiz";
  if (p < 0) return "Görüşme";
  return `${p.toLocaleString("tr-TR")} ₺/ay`;
}

export function TeacherPlanClient({ initial }: { initial: TeacherPlanResponse }) {
  const q = useQuery<TeacherPlanResponse>({
    queryKey: teacherKeys.plan(),
    queryFn: getTeacherPlan,
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const upgrade = useUpgradePlan();
  const [target, setTarget] = React.useState<TeacherPlanOption | null>(null);

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
        <div className="grid gap-3 sm:grid-cols-3">
          {data.options.map((opt) => (
            <Card
              key={opt.code}
              className={cn(opt.is_current && "ring-2 ring-cyan-500")}
            >
              <CardContent className="flex h-full flex-col gap-2 p-4">
                <div className="flex items-center justify-between">
                  <p className="font-semibold">{opt.label}</p>
                  {opt.is_current ? (
                    <span className="rounded bg-cyan-100 px-1.5 py-0.5 text-[10px] font-bold text-cyan-700">MEVCUT</span>
                  ) : null}
                </div>
                <p className="text-sm font-medium">{priceLabel(opt.price_monthly_try)}</p>
                <p className="text-xs text-muted-foreground">{opt.short_description}</p>
                <p className={cn("mt-1 inline-flex items-center gap-1 text-xs", opt.ai_included ? "text-emerald-600" : "text-muted-foreground")}>
                  {opt.ai_included ? <Sparkles className="size-3.5" aria-hidden /> : <Lock className="size-3.5" aria-hidden />}
                  Yapay zekâ {opt.ai_included ? "dahil" : "yok"}
                </p>
                <div className="mt-auto pt-2">
                  {opt.is_upgrade ? (
                    <Button size="sm" className="w-full" onClick={() => setTarget(opt)}>
                      Bu pakete geç
                    </Button>
                  ) : opt.is_current ? (
                    <Button size="sm" variant="outline" className="w-full" disabled>
                      <Check className="size-4" aria-hidden /> Aktif
                    </Button>
                  ) : (
                    <span className="block text-center text-[11px] text-muted-foreground">—</span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <p className="text-[11px] text-muted-foreground">
        Yapay zekâ özellikleri (sesle/fotoğraftan seans doldurma, koçluk içgörüsü)
        yalnız ücretli paketlerde açıktır ve kendi kredinizden düşer.
      </p>

      <Dialog open={!!target} onOpenChange={(o) => { if (!o) setTarget(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Pakete geç</DialogTitle>
          </DialogHeader>
          {target ? (
            <p className="text-sm text-muted-foreground">
              <strong>{target.label}</strong> ({priceLabel(target.price_monthly_try)}) paketine
              geçmek istediğinize emin misiniz? Yapay zekâ özellikleri açılacaktır.
            </p>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTarget(null)} disabled={upgrade.isPending}>
              Vazgeç
            </Button>
            <Button
              onClick={() => {
                if (!target) return;
                upgrade.mutate({ plan: target.code }, { onSuccess: () => setTarget(null) });
              }}
              disabled={upgrade.isPending}
            >
              {upgrade.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Gem className="size-4" aria-hidden />}
              Geç
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
