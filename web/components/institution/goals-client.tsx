"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Info } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { ColumnHint } from "@/components/ui/column-hint";
import {
  getInstitutionGoals,
  institutionKeys,
} from "@/lib/api/institution";
import type { InstitutionGoalsResponse } from "@/lib/types/institution";

interface Props {
  initial: InstitutionGoalsResponse;
}

/**
 * Kurum geneli hedef özeti — Jinja `goals/institution_summary.html` ile birebir.
 *
 * GİZLİLİK: öğrenci-bazlı detay görünmez; sadece agregalar + hedefsiz uyarı.
 */
export function GoalsClient({ initial }: Props) {
  const q = useQuery<InstitutionGoalsResponse>({
    queryKey: institutionKeys.goals(),
    queryFn: () => getInstitutionGoals(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const {
    students_with_goals,
    students_without_goals,
    total_goals,
    achieved_goals,
    active_goals,
    avg_overall_pct,
  } = data;

  const totalStudents = students_with_goals + students_without_goals;

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/institution"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <p className="text-xs uppercase tracking-[0.2em] text-emerald-700 dark:text-emerald-300 font-semibold mt-2">
          Kurum Geneli
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
          Hedef Analizi
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          Kurumdaki tüm öğrencilerin hedeflerinin toplu özeti. Öğrenci bazlı
          öğrenci-bazlı görünüm gizlilik kuralı gereği yalnızca öğretmen
          panelinde görünür.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <KpiCard
          label="Hedefi olan öğrenci"
          hint="En az bir hedefi tanımlanmış aktif öğrenci sayısı (hedefin durumu ne olursa olsun)."
          value={students_with_goals}
          sub={`${totalStudents} aktif öğrenciden`}
        />
        <KpiCard
          label="Toplam hedef"
          hint="Kurumdaki öğrencilerin tüm hedefleri: süren, başarılan ve vazgeçilenler dahil."
          value={total_goals}
          sub={`${active_goals} süren · ${achieved_goals} başarılan`}
        />
        <KpiCard
          label="Ortalama ilerleme"
          hint="Her öğrencinin ana hedeflerinin ortalama ilerleme yüzdesi hesaplanır; bu kart, hedefi olan öğrencilerin bu yüzdelerinin ortalamasıdır."
          value={avg_overall_pct == null ? "—" : `%${avg_overall_pct}`}
          sub="hedefi olan öğrencilerin ortalaması"
          accent
        />
      </div>

      {students_without_goals > 0 && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 flex items-start gap-3 dark:border-amber-500/30 dark:bg-amber-500/10">
          <AlertTriangle
            className="size-6 shrink-0 text-amber-600 dark:text-amber-300 mt-0.5"
            aria-hidden
          />
          <div>
            <h3 className="font-semibold text-amber-900 dark:text-amber-200">
              {students_without_goals} öğrenci hedefsiz
            </h3>
            <p className="text-sm text-amber-800 mt-1 dark:text-amber-200/90">
              Hedef koymak motivasyonu artırır ve ilerlemeyi ölçülebilir
              kılar. Öğretmenlerinize öğrencilerinin hedef ağacını
              tanımlamasını öneriniz.
            </p>
          </div>
        </div>
      )}

      <Card>
        <CardContent className="p-5">
          <div className="flex items-start gap-2">
            <Info
              className="size-4 shrink-0 text-muted-foreground mt-0.5"
              aria-hidden
            />
            <div>
              <h3 className="font-semibold text-sm">Bilgi notu</h3>
              <p className="text-sm text-muted-foreground leading-relaxed mt-1">
                Bu sayfada öğrenci-bazlı detay görünmez (gizlilik kuralı).
                Detaylı hedef yönetimi için öğretmen, öğrenci profil sayfası →
                &ldquo;Hedef Ağacı&rdquo; sekmesinden işlem yapar.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function KpiCard({
  label,
  hint,
  value,
  sub,
  accent,
}: {
  label: string;
  hint: string;
  value: number | string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <Card className={accent ? "border-emerald-300/60" : undefined}>
      <CardContent className="p-5">
        <div
          className={
            "text-[11px] uppercase tracking-wider " +
            (accent ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground")
          }
        >
          <ColumnHint label={label} hint={hint} />
        </div>
        <div
          className={
            "text-3xl font-semibold mt-1 tabular-nums " +
            (accent ? "text-emerald-800 dark:text-emerald-300" : "")
          }
        >
          {value}
        </div>
        {sub ? (
          <div className="text-xs text-muted-foreground mt-1">{sub}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}
