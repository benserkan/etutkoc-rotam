"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Info, PartyPopper, Printer, Send } from "lucide-react";

import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ColumnHint } from "@/components/ui/column-hint";
import {
  buildInterventionMap,
  getInstitutionAtRisk,
  getInstitutionCoachInterventions,
  institutionKeys,
  type CoachInterventionItem,
} from "@/lib/api/institution";
import {
  NotifyCoachDialog,
  type NotifyCoachTarget,
} from "@/components/institution/notify-coach-dialog";
import type {
  AtRiskCountsInfo,
  AtRiskResponse,
  AtRiskRowItem,
} from "@/lib/types/institution";
import {
  PauseBadge,
  RiskLevelBadge,
  riskRowBgClass,
  riskScoreColorClass,
} from "@/components/institution/level-badge";

interface Props {
  initial: AtRiskResponse;
}

/**
 * Risk Paneli — Jinja `at_risk_list.html` ile birebir.
 *
 * Sayım kartları: 🔴 Kritik / 🟠 Risk / 🟡 Dikkat
 * Tablo: Öğrenci / Öğretmen / Seviye / Risk Puanı (tooltip) / Niye risk altında
 */
export function AtRiskClient({ initial }: Props) {
  const q = useQuery<AtRiskResponse>({
    queryKey: institutionKeys.atRisk(),
    queryFn: () => getInstitutionAtRisk(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;

  // P4b — geçmiş "Koça ilet" müdahaleleri (ad-bazlı eşleşme)
  const intQ = useQuery({
    queryKey: institutionKeys.interventions(),
    queryFn: getInstitutionCoachInterventions,
    staleTime: 30_000,
  });
  const intMap = React.useMemo(
    () => buildInterventionMap(intQ.data?.items ?? []),
    [intQ.data],
  );
  const { institution, counts, total_students, healthy_count, at_risk } = data;

  const [target, setTarget] = React.useState<NotifyCoachTarget | null>(null);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href="/institution"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Panel
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
            Risk altındaki öğrenciler
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {institution.name} — {total_students} aktif öğrenciden{" "}
            {at_risk.length} tanesinin risk puanı 30 ve üstü (Dikkat, Risk ya da
            Kritik); {healthy_count} öğrencide belirgin risk sinyali yok.
          </p>
          <DemoHint contextKey="analysis" role="institution_admin" className="mt-2" />
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/institution/at-risk/print" target="_blank">
            <Printer className="size-4" aria-hidden />
            Yazdır / PDF
          </Link>
        </Button>
      </header>

      <PrivacyNote />

      <CountCards counts={counts} />

      {at_risk.length === 0 ? (
        <EmptyState />
      ) : (
        <Card>
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">
                    <ColumnHint
                      label="Öğrenci"
                      hint="Adın altındaki “çözülen/planlanan (%)”: son 7 günde (bugün dahil) yayınlanan soru bankası testlerinden çözülenler (deneme ve etkinlik görevleri hariç). “plan yok” = son 7 günde hiç test verilmemiş."
                    />
                  </th>
                  <th className="text-left px-4 py-2 font-medium">Öğretmen</th>
                  <th className="text-left px-4 py-2 font-medium">
                    <ColumnHint
                      label="Seviye"
                      hint="Risk puanına göre: 80 ve üstü Kritik, 60–79 Risk, 30–59 Dikkat."
                    />
                  </th>
                  <th className="text-right px-4 py-2 font-medium">
                    <ColumnHint
                      label="Risk puanı"
                      hint="0–100; yüksek puan = öğrenci daha çok ilgi istiyor. Sinyallerin toplamı: 5+ gündür görülmedi — web ya da mobilde hiç açmadı (25), son 7 günde tamamlama %40 altı (30), 3+ gün üst üste hiçbir şey yapılmamış (20), önceki 7 güne göre %30+ düşüş (15), bu hafta hiç görev verilmemiş (10). Tamamlama yalnız yayınlanmış soru bankası testlerinden hesaplanır (deneme ve etkinlik görevleri hariç); “görev verilmemiş” ise her görev türüne bakar. Yeni öğrencide ilk 3 gün sinyal üretilmez."
                    />
                  </th>
                  <th className="text-left px-4 py-2 font-medium">
                    <ColumnHint
                      label="Neden risk altında"
                      hint="Öğrencide tetiklenen sinyaller. Sinyalin üzerine gelince ayrıntısı görünür."
                    />
                  </th>
                  <th className="text-right px-4 py-2 font-medium w-32">
                    Müdahale
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {at_risk.map((r) => (
                  <AtRiskRow
                    key={r.student_id}
                    row={r}
                    intervention={intMap.get(r.full_name.trim().toLocaleLowerCase("tr")) ?? null}
                    onNotify={() =>
                      r.teacher_id
                        ? setTarget({
                            student_name: r.full_name,
                            teacher_id: r.teacher_id,
                            teacher_name: r.teacher_name,
                          })
                        : undefined
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <NotifyCoachDialog target={target} onClose={() => setTarget(null)} context="at_risk" />
    </div>
  );
}

function PrivacyNote() {
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50 text-sky-900 px-3 py-2.5 text-xs flex items-start gap-2 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200">
      <Info className="size-4 shrink-0 mt-0.5" aria-hidden />
      <div>
        <strong>Gizlilik:</strong> Bu panel öğrenci programını veya öğretmen
        notlarını GÖSTERMEZ — sadece &ldquo;kim risk altında ve niye&rdquo;
        bilgisini sunar. Müdahale için ilgili koça{" "}
        <strong>“Koça ilet”</strong> ile talep açabilirsiniz.
      </div>
    </div>
  );
}

function CountCards({ counts }: { counts: AtRiskCountsInfo }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      <CountCard
        label="Kritik"
        dot="bg-rose-500"
        hint="Risk puanı 80 ve üstü öğrenci sayısı. Birden çok sinyal aynı anda var; hemen koçla konuşulmalı."
        value={counts.critical}
        sub="öğrenci · acil müdahale önerilir"
        cardClass="border-rose-200 dark:border-rose-500/30"
        valueClass="text-rose-700 dark:text-rose-400"
      />
      <CountCard
        label="Risk"
        dot="bg-orange-500"
        hint="Risk puanı 60–79 öğrenci sayısı. Koçun yakından takip etmesi gerekir."
        value={counts.high}
        sub="öğrenci · koç takip etmeli"
        cardClass="border-orange-200 dark:border-orange-500/30"
        valueClass="text-orange-700 dark:text-orange-400"
      />
      <CountCard
        label="Dikkat"
        dot="bg-amber-500"
        hint="Risk puanı 30–59 öğrenci sayısı. Erken sinyal; henüz ciddi değil ama izlenmeli."
        value={counts.medium}
        sub="öğrenci · erken sinyal"
        cardClass="border-amber-200 dark:border-amber-500/30"
        valueClass="text-amber-700 dark:text-amber-400"
      />
    </div>
  );
}

function CountCard({
  label,
  dot,
  hint,
  value,
  sub,
  cardClass,
  valueClass,
}: {
  label: string;
  dot: string;
  hint: string;
  value: number;
  sub: string;
  cardClass?: string;
  valueClass?: string;
}) {
  return (
    <Card className={cardClass}>
      <CardContent className="p-4">
        <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
          <span className={cn("inline-block size-2 rounded-full", dot)} aria-hidden />
          <ColumnHint label={label} hint={hint} />
        </div>
        <div
          className={cn(
            "text-3xl font-semibold mt-1 tabular-nums",
            valueClass,
          )}
        >
          {value}
        </div>
        <div className="text-[11px] text-muted-foreground mt-1">{sub}</div>
      </CardContent>
    </Card>
  );
}

export function InterventionBadge({ it }: { it: CoachInterventionItem }) {
  const d = new Date(it.created_at);
  const dt = `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
  return (
    <span
      className="mt-1 inline-flex items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
      title={`${dt} tarihinde ${it.coach_name ?? "koça"} iletildi — ${it.status_label}`}
    >
      <CheckCircle2 className="size-3" aria-hidden />
      {dt} koça iletildi · {it.status_label}
    </span>
  );
}

function AtRiskRow({
  row,
  intervention,
  onNotify,
}: {
  row: AtRiskRowItem;
  intervention?: CoachInterventionItem | null;
  onNotify: () => void;
}) {
  return (
    <tr className={riskRowBgClass(row.level, row.is_paused)}>
      <td className="px-4 py-3 align-top">
        <div className="font-medium flex items-center gap-2 flex-wrap">
          {row.full_name}
          {row.is_paused && <PauseBadge reason={row.pause_reason} />}
        </div>
        {intervention ? <InterventionBadge it={intervention} /> : null}
        <div className="text-[11px] text-muted-foreground mt-0.5">
          {row.grade_level ? `${row.grade_level}. sınıf` : null}
          {row.weekly_planned > 0 ? (
            <>
              {row.grade_level ? " · " : null}
              {row.weekly_completed}/{row.weekly_planned} test çözüldü (%
              {row.weekly_rate_pct ?? 0})
            </>
          ) : (
            <>
              {row.grade_level ? " · " : null}plan yok
            </>
          )}
        </div>
      </td>
      <td className="px-4 py-3 align-top">
        {row.teacher_name ? (
          <>
            <div className="text-sm">{row.teacher_name}</div>
            {row.is_muted && (
              <div className="text-[10px] text-muted-foreground mt-0.5">
                öğretmen uyarıları susturmuş
              </div>
            )}
          </>
        ) : (
          <span className="text-muted-foreground text-xs">öğretmensiz</span>
        )}
      </td>
      <td className="px-4 py-3 align-top">
        <RiskLevelBadge
          level={row.level}
          label={row.level_label}
          emoji={row.level_emoji}
        />
      </td>
      <td className="px-4 py-3 text-right align-top">
        <span
          className={cn(
            "text-lg font-semibold tabular-nums",
            riskScoreColorClass(row.score),
          )}
        >
          {row.score}
        </span>
        <span className="text-xs text-muted-foreground">/100</span>
      </td>
      <td className="px-4 py-3 align-top">
        <div className="flex flex-wrap gap-1">
          {row.indicators.map((ind) => (
            <span
              key={ind.code}
              className="text-[10px] px-2 py-0.5 rounded bg-muted text-foreground/80 border border-border"
              title={ind.detail}
            >
              {ind.title}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3 text-right align-top">
        {row.teacher_id ? (
          <Button size="sm" variant="outline" onClick={onNotify}>
            <Send className="size-3.5" aria-hidden />
            Koça ilet
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardContent className="p-12 text-center">
        <PartyPopper
          className="size-12 mx-auto text-emerald-600 dark:text-emerald-300 mb-3"
          aria-hidden
        />
        <h2 className="text-lg font-semibold mb-1">
          Tüm öğrenciler sağlıklı
        </h2>
        <p className="text-sm text-muted-foreground">
          Şu an hiçbir öğrenci risk altında değil. Sürekli izlemde — bir şey
          değişirse burada görüneceksin.
        </p>
      </CardContent>
    </Card>
  );
}
