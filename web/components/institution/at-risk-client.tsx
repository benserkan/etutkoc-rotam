"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Info, PartyPopper, Printer } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  getInstitutionAtRisk,
  institutionKeys,
} from "@/lib/api/institution";
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
  const { institution, counts, total_students, healthy_count, at_risk } = data;

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
            {institution.name} — kurum genelinde {at_risk.length}/
            {total_students} öğrenci risk altında, {healthy_count} tanesi
            sağlıklı.
          </p>
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Öğrenci</th>
                  <th className="text-left px-4 py-2 font-medium">Öğretmen</th>
                  <th className="text-left px-4 py-2 font-medium">Seviye</th>
                  <th
                    className="text-right px-4 py-2 font-medium"
                    title="Risk puanı 0-100. Yüksek puan = öğrenci daha çok ilgi istiyor demek. Hesaplama: 5+ gün giriş yok, düşük tamamlama, üst üste boş günler, performans düşüşü, programsız kalma gibi belirtilerin toplamı."
                  >
                    Risk Puanı
                  </th>
                  <th className="text-left px-4 py-2 font-medium">
                    Niye risk altında
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {at_risk.map((r) => (
                  <AtRiskRow key={r.student_id} row={r} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function PrivacyNote() {
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50 text-sky-900 px-3 py-2.5 text-xs flex items-start gap-2">
      <Info className="size-4 shrink-0 mt-0.5" aria-hidden />
      <div>
        <strong>Gizlilik:</strong> Bu panel öğrenci programını veya öğretmen
        notlarını GÖSTERMEZ — sadece &ldquo;kim risk altında ve niye&rdquo;
        bilgisini sunar. Müdahale gerekiyorsa öğretmenle{" "}
        <strong>doğrudan iletişime geçin</strong>.
      </div>
    </div>
  );
}

function CountCards({ counts }: { counts: AtRiskCountsInfo }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      <CountCard
        label="🔴 Kritik"
        value={counts.critical}
        sub="acil müdahale önerilir"
        cardClass="border-rose-200"
        valueClass="text-rose-700"
      />
      <CountCard
        label="🟠 Risk"
        value={counts.high}
        sub="öğretmen takip ediyor olmalı"
        cardClass="border-orange-200"
        valueClass="text-orange-700"
      />
      <CountCard
        label="🟡 Dikkat"
        value={counts.medium}
        sub="erken sinyal — izlemde"
        cardClass="border-amber-200"
        valueClass="text-amber-700"
      />
    </div>
  );
}

function CountCard({
  label,
  value,
  sub,
  cardClass,
  valueClass,
}: {
  label: string;
  value: number;
  sub: string;
  cardClass?: string;
  valueClass?: string;
}) {
  return (
    <Card className={cardClass}>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
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

function AtRiskRow({ row }: { row: AtRiskRowItem }) {
  return (
    <tr className={riskRowBgClass(row.level, row.is_paused)}>
      <td className="px-4 py-3 align-top">
        <div className="font-medium flex items-center gap-2 flex-wrap">
          {row.full_name}
          {row.is_paused && <PauseBadge reason={row.pause_reason} />}
        </div>
        <div className="text-[11px] text-muted-foreground mt-0.5">
          {row.grade_level ? `${row.grade_level}. sınıf` : null}
          {row.weekly_planned > 0 ? (
            <>
              {row.grade_level ? " · " : null}
              {row.weekly_completed}/{row.weekly_planned} (%
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
                🔕 öğretmen susturmuş
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
    </tr>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardContent className="p-12 text-center">
        <PartyPopper
          className="size-12 mx-auto text-emerald-600 mb-3"
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
