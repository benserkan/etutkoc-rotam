"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ClipboardX,
  ShieldAlert,
  Target,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";
import { Card } from "@/components/ui/card";
import { institutionKeys, getInstitutionActionCenter } from "@/lib/api/institution";
import type { ActionCenterItem, ActionCenterResponse } from "@/lib/types/institution";

interface Props {
  initial: ActionCenterResponse;
}

const SEV_CARD: Record<string, string> = {
  critical: "border-l-rose-500 bg-rose-50/40",
  warn: "border-l-amber-500 bg-amber-50/40",
  info: "border-l-sky-500 bg-sky-50/40",
};
const SEV_ICON_COLOR: Record<string, string> = {
  critical: "text-rose-600",
  warn: "text-amber-600",
  info: "text-sky-600",
};
const CAT_ICON: Record<string, LucideIcon> = {
  empty_program: ClipboardX,
  low_compliance: Target,
  at_risk: ShieldAlert,
  inactive_program: CalendarClock,
};
const CAT_LABEL: Record<string, string> = {
  empty_program: "Boş program",
  low_compliance: "Düşük uyum",
  at_risk: "Riskli öğrenci",
  inactive_program: "Programı var, yapmıyor",
};

export function ActionCenterClient({ initial }: Props) {
  const q = useQuery<ActionCenterResponse>({
    queryKey: institutionKeys.actionCenter(),
    queryFn: getInstitutionActionCenter,
    initialData: initial,
    staleTime: 30_000,
  });
  const d = q.data ?? initial;
  const s = d.summary;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <AlertTriangle className="size-6 text-rose-600" aria-hidden />
          Müdahale Merkezi
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Bugün acil ilgi gerektiren durumlar tek listede, öncelik sırasıyla. Boş
          program, düşük uyum ve riskli öğrenci sinyalleri burada birleşir.
        </p>
        <DemoHint contextKey="analysis" role="institution_admin" className="mt-2" />
      </header>

      {/* Özet */}
      <section className="grid grid-cols-3 gap-3">
        <Card className={cn("p-4", s.critical > 0 && "border-rose-300 bg-rose-50/40")}>
          <div className="text-[11px] font-semibold uppercase text-rose-700">Kritik</div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{s.critical}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">acil müdahale sinyali</div>
        </Card>
        <Card className={cn("p-4", s.warn > 0 && "border-amber-300 bg-amber-50/40")}>
          <div className="text-[11px] font-semibold uppercase text-amber-700">Uyarı</div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{s.warn}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">dikkat sinyali</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] font-semibold uppercase text-muted-foreground">Toplam</div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{s.total}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">aksiyon kartı (şu an)</div>
        </Card>
      </section>

      {/* Kartlar */}
      {d.items.length === 0 ? (
        <Card className="flex items-center gap-3 border-emerald-200 bg-emerald-50/40 p-6 text-sm text-emerald-800">
          <CheckCircle2 className="size-6 shrink-0 text-emerald-600" aria-hidden />
          Şu an acil müdahale gerektiren bir durum yok. Tüm sınıflar yolunda görünüyor.
        </Card>
      ) : (
        <div className="space-y-3">
          {d.items.map((it: ActionCenterItem, i) => {
            const Icon = CAT_ICON[it.category] ?? AlertTriangle;
            return (
              <Card key={i} className={cn("border-l-4 p-4", SEV_CARD[it.severity] ?? SEV_CARD.info)}>
                <div className="flex items-start gap-3">
                  <Icon className={cn("mt-0.5 size-5 shrink-0", SEV_ICON_COLOR[it.severity] ?? SEV_ICON_COLOR.info)} aria-hidden />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-border bg-card px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                        {CAT_LABEL[it.category] ?? it.category}
                      </span>
                      <h3 className="text-sm font-semibold">{it.title}</h3>
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">{it.description}</p>
                    <p className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-indigo-700">
                      → {it.suggestion}
                    </p>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
