"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity, Lock, PartyPopper, Send, UserCog } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  buildInterventionMap,
  getInstitutionBurnout,
  getInstitutionCoachInterventions,
  institutionKeys,
  type CoachInterventionItem,
} from "@/lib/api/institution";
import {
  NotifyCoachDialog,
  type NotifyCoachTarget,
} from "@/components/institution/notify-coach-dialog";
import { InterventionBadge } from "@/components/institution/at-risk-client";
import type { BurnoutResponse, BurnoutRowItem } from "@/lib/types/institution";
import {
  BurnoutLevelBadge,
  burnoutScoreColorClass,
} from "@/components/institution/level-badge";

interface Props {
  initial: BurnoutResponse;
}

/**
 * Tükenmişlik Panosu — risk altındaki öğrenciler + koç müdahale kolu.
 *
 * Gözlem + EYLEM: gizlilik gereği yönetici öğrenci detayına inemez; müdahale
 * kolu KOÇtur. "Koça ilet" ile ilgili koça müdahale talebi açılır (koçun
 * "Destek → Gelen kutusu"nda görünür).
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

  const intQ = useQuery({
    queryKey: institutionKeys.interventions(),
    queryFn: getInstitutionCoachInterventions,
    staleTime: 30_000,
  });
  const intMap = React.useMemo(() => buildInterventionMap(intQ.data?.items ?? []), [intQ.data]);

  const [target, setTarget] = React.useState<NotifyCoachTarget | null>(null);

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
          Kurumun risk altındaki öğrencileri, aktif sinyalleri ve sorumlu koçları.
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
                  <th className="text-left px-4 py-2.5 font-medium">Öğrenci</th>
                  <th className="text-left px-4 py-2.5 font-medium">Sorumlu koç</th>
                  <th className="text-right px-4 py-2.5 font-medium w-28">Risk</th>
                  <th className="text-center px-4 py-2.5 font-medium w-32">Seviye</th>
                  <th className="text-right px-4 py-2.5 font-medium w-24">Sinyal</th>
                  <th className="text-right px-4 py-2.5 font-medium w-32">Müdahale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((r) => (
                  <BurnoutRow
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

      <div className="text-xs text-muted-foreground leading-relaxed flex items-start gap-2">
        <Lock className="size-3.5 shrink-0 mt-0.5" aria-hidden />
        <span>
          <strong>Gizlilik notu:</strong> bu panoda öğrenci detay sayfası yoktur —
          öğrenciyi koç kendi panelinden inceler. Müdahale için{" "}
          <strong>“Koça ilet”</strong> ile ilgili koça talep açabilirsiniz.
        </span>
      </div>

      <NotifyCoachDialog target={target} onClose={() => setTarget(null)} context="burnout" />
    </div>
  );
}

function BurnoutRow({
  row,
  intervention,
  onNotify,
}: {
  row: BurnoutRowItem;
  intervention?: CoachInterventionItem | null;
  onNotify: () => void;
}) {
  return (
    <tr className="hover:bg-muted/30">
      <td className="px-4 py-2.5 font-medium">
        {row.full_name}
        {intervention ? <div><InterventionBadge it={intervention} /></div> : null}
      </td>
      <td className="px-4 py-2.5 text-muted-foreground">
        {row.teacher_name ? (
          <span className="inline-flex items-center gap-1.5">
            <UserCog className="size-3.5 shrink-0" aria-hidden />
            {row.teacher_name}
          </span>
        ) : (
          <span className="italic">Koçu atanmamış</span>
        )}
      </td>
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
      <td className="px-4 py-2.5 text-right">
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
