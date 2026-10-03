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
import { ColumnHint } from "@/components/ui/column-hint";
import { DemoHint } from "@/components/demos/demo-hint";
import { Card } from "@/components/ui/card";
import { institutionKeys, getInstitutionActionCenter } from "@/lib/api/institution";
import type { ActionCenterItem, ActionCenterResponse } from "@/lib/types/institution";

interface Props {
  initial: ActionCenterResponse;
}

const SEV_CARD: Record<string, string> = {
  critical: "border-l-rose-500 bg-rose-50/40 dark:bg-rose-500/10",
  warn: "border-l-amber-500 bg-amber-50/40 dark:bg-amber-500/10",
  info: "border-l-sky-500 bg-sky-50/40 dark:bg-sky-500/10",
};
const SEV_ICON_COLOR: Record<string, string> = {
  critical: "text-rose-600 dark:text-rose-300",
  warn: "text-amber-600 dark:text-amber-300",
  info: "text-sky-600 dark:text-sky-300",
};
const CAT_ICON: Record<string, LucideIcon> = {
  empty_program: ClipboardX,
  low_compliance: Target,
  at_risk: ShieldAlert,
  inactive_program: CalendarClock,
};
const CAT_LABEL: Record<string, string> = {
  empty_program: "Programı yok",
  low_compliance: "Düşük tamamlama",
  at_risk: "Riskli öğrenci",
  inactive_program: "Programı var, yapmıyor",
};

// Kart türü rozetinin üzerine gelince açılan açıklama — neye bakılarak üretildiği
const CAT_HINT: Record<string, string> = {
  empty_program:
    "Bu takvim haftasında (Pazartesi–Pazar, ileri günler dahil) hiç yayınlanmış görevi olmayan aktif öğrenciler. Koçluğu sonlandırılmış öğrenciler ve 3 günden yeni hesaplar sayılmaz. Bir koçta 3 ve üstü öğrenci varsa kritik.",
  low_compliance:
    "Koçun öğrencilerinin son 7 günde (bugün dahil) planlanan testlerden çözdüğü oran; yalnız yayınlanmış soru bankası testleri, deneme ve etkinlik görevleri hariç. Panel ve tüm sayfalarda aynı ölçü. %40 altı uyarı, %25 altı kritik. Doğruluk = çözülen sorularda doğru ÷ (doğru + yanlış).",
  at_risk:
    "Risk puanı 0–100: 5+ gündür görülmedi — web ya da mobilde hiç açmadı (25) · haftalık tamamlama %40 altı (30) · 3+ gün üst üste hiçbir şey yapılmamış (20) · önceki haftaya göre %30+ düşüş (15) · bu hafta hiç görev yok (10). 60 ve üstü Risk, 80 ve üstü Kritik.",
  inactive_program:
    "Programı olduğu hâlde 3 veya daha fazla gündür üst üste hiçbir görevi tamamlamayan öğrenci.",
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
          <AlertTriangle className="size-6 text-rose-600 dark:text-rose-300" aria-hidden />
          Müdahale Merkezi
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Bugün ilgi gerektiren durumlar tek listede, önem sırasıyla: programı
          olmayan öğrenciler, testlerin az çözüldüğü koçlar ve riskli öğrenciler.
          Kartın türüne (sol üstteki etiket) gelince neye bakılarak üretildiği açılır.
        </p>
        <DemoHint contextKey="analysis" role="institution_admin" className="mt-2" />
      </header>

      {/* Özet */}
      <section className="grid grid-cols-3 gap-3">
        <Card className={cn("p-4", s.critical > 0 && "border-rose-300 bg-rose-50/40 dark:bg-rose-500/10")}>
          <div className="text-[11px] font-semibold uppercase text-rose-700 dark:text-rose-300">
            <ColumnHint label="Kritik" hint="Hemen ilgilenilmesi gereken kart sayısı (öğrenci sayısı değil; bir kart bir koçun birden çok öğrencisini kapsayabilir)." />
          </div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{s.critical}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">acil ilgi gereken durum</div>
        </Card>
        <Card className={cn("p-4", s.warn > 0 && "border-amber-300 bg-amber-50/40 dark:bg-amber-500/10")}>
          <div className="text-[11px] font-semibold uppercase text-amber-700 dark:text-amber-300">
            <ColumnHint label="Uyarı" hint="Yakından takip edilmesi gereken kart sayısı; acil değil ama büyümeden konuşulmalı." />
          </div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{s.warn}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">takip edilmesi gereken durum</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] font-semibold uppercase text-muted-foreground">
            <ColumnHint label="Toplam" hint="Şu an listelenen tüm kartlar (kritik + uyarı). Sayfa her açılışta güncel veriden yeniden hesaplanır." />
          </div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{s.total}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">şu an listelenen kart</div>
        </Card>
      </section>

      {/* Kartlar */}
      {d.items.length === 0 ? (
        <Card className="flex items-center gap-3 border-emerald-200 bg-emerald-50/40 p-6 text-sm text-emerald-800 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200">
          <CheckCircle2 className="size-6 shrink-0 text-emerald-600 dark:text-emerald-300" aria-hidden />
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
                        {CAT_HINT[it.category] ? (
                          <ColumnHint
                            label={CAT_LABEL[it.category] ?? it.category}
                            hint={CAT_HINT[it.category]}
                          />
                        ) : (
                          CAT_LABEL[it.category] ?? it.category
                        )}
                      </span>
                      <h3 className="text-sm font-semibold">{it.title}</h3>
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">{it.description}</p>
                    <p className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-indigo-700 dark:text-indigo-300">
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
