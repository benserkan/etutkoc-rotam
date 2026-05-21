"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity, Lock, PartyPopper } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import {
  getInstitutionBurnout,
  institutionKeys,
} from "@/lib/api/institution";
import type { BurnoutResponse, BurnoutRowItem } from "@/lib/types/institution";
import {
  BurnoutLevelBadge,
  burnoutScoreColorClass,
} from "@/components/institution/level-badge";

interface Props {
  initial: BurnoutResponse;
}

/**
 * Tükenmişlik Panosu — Jinja `burnout.html` ile birebir.
 *
 * Tablo: Öğrenci / Risk (0-100) / Seviye / Sinyal sayısı
 * Risk skoru sıralı, risk=0 olanlar yok (backend filtreler).
 */
export function BurnoutClient({ initial }: Props) {
  const q = useQuery<BurnoutResponse>({
    queryKey: institutionKeys.burnout(),
    queryFn: () => getInstitutionBurnout(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const { items } = data;

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/institution"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 flex items-center gap-2">
          <Activity className="size-6 text-rose-600" aria-hidden />
          Kurum Tükenmişlik Panosu
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Kurumun risk altındaki öğrencileri ve aktif sinyal sayıları.
        </p>
      </header>

      {items.length === 0 ? (
        <EmptyState />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium">
                    Öğrenci
                  </th>
                  <th className="text-right px-4 py-2.5 font-medium w-28">
                    Risk
                  </th>
                  <th className="text-center px-4 py-2.5 font-medium w-32">
                    Seviye
                  </th>
                  <th className="text-right px-4 py-2.5 font-medium w-28">
                    Sinyal
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((r) => (
                  <BurnoutRow key={r.student_id} row={r} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="text-xs text-muted-foreground leading-relaxed flex items-start gap-2">
        <Lock className="size-3.5 shrink-0 mt-0.5" aria-hidden />
        <span>
          <strong>Gizlilik notu:</strong> bu panoda öğretmen-öğrenci eşleşmesi
          gösterilmez ve detay sayfasına link yoktur. Detay için öğretmen kendi
          panelinden inceler.
        </span>
      </div>
    </div>
  );
}

function BurnoutRow({ row }: { row: BurnoutRowItem }) {
  return (
    <tr className="hover:bg-muted/30">
      <td className="px-4 py-2.5">{row.full_name}</td>
      <td className="px-4 py-2.5 text-right">
        <span
          className={cn(
            "font-bold tabular-nums",
            burnoutScoreColorClass(row.risk_level),
          )}
        >
          {row.risk_score}
        </span>
        <span className="text-muted-foreground text-xs"> / 100</span>
      </td>
      <td className="px-4 py-2.5 text-center">
        <BurnoutLevelBadge level={row.risk_level} />
      </td>
      <td className="px-4 py-2.5 text-right text-muted-foreground tabular-nums">
        {row.signal_count} aktif
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
        <p className="text-sm text-muted-foreground">
          Şu an kurumda burnout sinyali olan öğrenci yok.
        </p>
      </CardContent>
    </Card>
  );
}
