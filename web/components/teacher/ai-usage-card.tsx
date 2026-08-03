"use client";

/**
 * Paketim — "Yapay zekâ kullanımı" kartı (2026-08-03).
 *
 * Koçun sorusu: "kredimi kim, hangi özellikte, ne kadar harcıyor?"
 * Tür kırılımı + kişi kırılımı (öğrenci/veli/koç) + son işlemler.
 * Kurum koçunda yalnız kendi alt-ağacı görünür (backend filtreler).
 *
 * Altında AI onay kartı: onay durumu + GERİ AL (toptan kapatma anahtarı).
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, ShieldCheck, ShieldOff, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getTeacherAiConsent, getTeacherAiUsage, teacherKeys } from "@/lib/api/teacher";
import { useRevokeAiConsent, useSetAiConsent } from "@/lib/hooks/use-teacher-mutations";
import type { AiConsentResponse, AiUsageResponse } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

const DAY_OPTIONS = [7, 30, 90] as const;

function fmtShort(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" }) +
    " " + d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

const ROLE_TONE: Record<string, string> = {
  "Öğrenci": "bg-sky-50 text-sky-800 dark:bg-sky-500/10 dark:text-sky-200",
  "Veli": "bg-emerald-50 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-200",
  "Koç (sen)": "bg-cyan-50 text-cyan-800 dark:bg-cyan-500/10 dark:text-cyan-200",
  "Sistem": "bg-slate-100 text-slate-600 dark:bg-slate-500/10 dark:text-slate-300",
};

export function AiUsageCard() {
  const [days, setDays] = React.useState<number>(30);
  const q = useQuery<AiUsageResponse>({
    queryKey: teacherKeys.aiUsage(days),
    queryFn: () => getTeacherAiUsage(days),
    staleTime: 60_000,
  });
  const d = q.data;

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles className="size-4 text-violet-600" aria-hidden />
          Yapay zekâ kullanımı
        </h2>
        <div className="flex gap-1">
          {DAY_OPTIONS.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => setDays(opt)}
              className={cn(
                "rounded-md px-2 py-1 text-xs font-medium",
                days === opt
                  ? "bg-violet-600 text-white"
                  : "bg-muted text-muted-foreground hover:text-foreground",
              )}
            >
              {opt} gün
            </button>
          ))}
        </div>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Kredini kim, hangi özellikte harcıyor — öğrenci ve veli kullanımı dahil.
      </p>

      {q.isLoading ? (
        <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
        </div>
      ) : !d || d.total_count === 0 ? (
        <p className="py-5 text-sm text-muted-foreground">
          Son {days} günde yapay zekâ kullanımı yok.
        </p>
      ) : (
        <div className="mt-3 space-y-4">
          <p className="text-sm">
            Son {d.days} günde toplam{" "}
            <span className="font-semibold">{d.total_credits} kredi</span>{" "}
            ({d.total_count} işlem) kullanıldı.
          </p>

          <div className="grid gap-4 md:grid-cols-2">
            {/* Tür kırılımı */}
            <div>
              <h3 className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground">
                Özelliğe göre
              </h3>
              <ul className="space-y-1.5">
                {d.kinds.map((k) => (
                  <li key={k.kind} className="flex items-center gap-2 text-sm">
                    <span className="min-w-0 flex-1 truncate">{k.label}</span>
                    <span className="text-xs text-muted-foreground">{k.count}×</span>
                    <span className="w-16 text-right font-medium tabular-nums">
                      {k.credits} kredi
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Kişi kırılımı */}
            <div>
              <h3 className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground">
                Kişiye göre
              </h3>
              <ul className="space-y-1.5">
                {d.persons.map((p) => (
                  <li
                    key={p.user_id ?? "system"}
                    className="flex items-center gap-2 text-sm"
                  >
                    <span className="min-w-0 flex-1 truncate">{p.name}</span>
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-medium",
                        ROLE_TONE[p.role_label] ?? ROLE_TONE["Sistem"],
                      )}
                    >
                      {p.role_label}
                    </span>
                    <span className="w-16 text-right font-medium tabular-nums">
                      {p.credits} kredi
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <details className="text-sm">
            <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
              Son işlemler ({d.events.length})
            </summary>
            <ul className="mt-2 space-y-1">
              {d.events.map((e, i) => (
                <li
                  key={`${e.at}-${i}`}
                  className="flex items-center gap-2 text-xs text-muted-foreground"
                >
                  <span className="w-24 shrink-0 tabular-nums">{fmtShort(e.at)}</span>
                  <span className="min-w-0 flex-1 truncate">{e.kind_label}</span>
                  <span className="min-w-0 max-w-32 truncate">{e.actor_name}</span>
                  <span className="w-14 text-right tabular-nums">{e.credits} kr</span>
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </section>
  );
}

export function AiConsentCard() {
  const q = useQuery<AiConsentResponse>({
    queryKey: teacherKeys.aiConsent(),
    queryFn: getTeacherAiConsent,
    staleTime: 30_000,
  });
  const grant = useSetAiConsent();
  const revoke = useRevokeAiConsent();
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const d = q.data;
  if (!d) return null;

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            {d.consented ? (
              <ShieldCheck className="size-4 text-emerald-600" aria-hidden />
            ) : (
              <ShieldOff className="size-4 text-rose-600" aria-hidden />
            )}
            Yapay zekâ onayı
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {d.consented
              ? "Onay verilmiş — sen, öğrencilerin ve veliler yapay zekâ özelliklerini kullanabilir."
              : "Onay yok — tüm yapay zekâ özellikleri (senin araçların + öğrenci ve veli özellikleri) kapalı."}
          </p>
        </div>
        {d.consented ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirmOpen(true)}
            disabled={revoke.isPending}
            className="text-rose-700 hover:text-rose-800"
          >
            Onayı geri al
          </Button>
        ) : (
          <Button size="sm" onClick={() => grant.mutate()} disabled={grant.isPending}>
            {grant.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            Onay ver
          </Button>
        )}
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Yapay zekâ onayını geri al?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Bu, toptan kapatma anahtarıdır: senin araçların (dikte, foto, içgörü),
            öğrencilerinin yapay zekâ etiketlemesi ve velilerin Rota asistanı{" "}
            <span className="font-medium text-foreground">tamamen durur</span>.
            İstediğin an yeniden onay verebilirsin; kayıtlı veriler silinmez.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Vazgeç
            </Button>
            <Button
              className="bg-rose-600 text-white hover:bg-rose-700"
              onClick={() =>
                revoke.mutate(undefined, { onSuccess: () => setConfirmOpen(false) })
              }
              disabled={revoke.isPending}
            >
              {revoke.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              Geri al
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
