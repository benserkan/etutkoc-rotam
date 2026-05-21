"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Award, GraduationCap, Trophy } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { institutionKeys, getInstitutionTeacherScorecard } from "@/lib/api/institution";
import type {
  TeacherScorecardResponse,
  TeacherScorecardRow,
} from "@/lib/types/institution";

interface Props {
  initial: TeacherScorecardResponse;
}

const SCORE_TEXT: Record<string, string> = {
  emerald: "text-emerald-700",
  sky: "text-sky-700",
  amber: "text-amber-700",
  rose: "text-rose-700",
};
const SCORE_BADGE: Record<string, string> = {
  emerald: "bg-emerald-100 text-emerald-800",
  sky: "bg-sky-100 text-sky-800",
  amber: "bg-amber-100 text-amber-800",
  rose: "bg-rose-100 text-rose-800",
};
const BAR: Record<string, string> = {
  emerald: "bg-emerald-500",
  sky: "bg-sky-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
};

function pct(v: number | null): string {
  return v == null ? "—" : `%${v}`;
}

export function TeacherScorecardClient({ initial }: Props) {
  const q = useQuery<TeacherScorecardResponse>({
    queryKey: institutionKeys.teacherScorecard(4),
    queryFn: () => getInstitutionTeacherScorecard(4),
    initialData: initial,
    staleTime: 30_000,
  });
  const d = q.data ?? initial;
  const s = d.summary;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <GraduationCap className="size-6 text-indigo-700" aria-hidden />
          Öğretmen Etkililik Karnesi
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          &quot;Kim sonuç alıyor?&quot; — son {s.weeks} hafta. Etkililik skoru = %40
          tamamlama + %25 doğruluk + %20 program disiplini + %15 düşük risk. En iyi
          pratiği örnek gösterin, düşük skorlu koçu yönlendirin.
        </p>
      </header>

      {/* Özet */}
      <section className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <div className="text-[11px] font-semibold uppercase text-muted-foreground">Ortalama skor</div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{s.avg_score}</div>
          <div className="text-[11px] text-muted-foreground">{s.teacher_count} öğretmen</div>
        </Card>
        <Card className="p-4 sm:col-span-2 border-emerald-200 bg-emerald-50/40">
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-emerald-700">
            <Trophy className="size-3.5" aria-hidden /> En etkili koç
          </div>
          {s.top_name ? (
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-lg font-semibold">{s.top_name}</span>
              <span className="text-sm text-emerald-700">skor {s.top_score}</span>
            </div>
          ) : (
            <div className="mt-1 text-sm text-muted-foreground">Henüz veri yok.</div>
          )}
        </Card>
      </section>

      {/* Karne tablosu */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-2.5">
          <h2 className="text-sm font-semibold">Karne (skora göre sıralı)</h2>
          <p className="text-xs text-muted-foreground">Disiplin = öğrenci başına haftalık planlanan soru.</p>
        </div>
        {d.teachers.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Öğretmen verisi yok.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-1.5 text-left">Koç</th>
                  <th className="px-3 py-1.5 text-left">Skor</th>
                  <th className="px-3 py-1.5 text-right">Öğrenci</th>
                  <th className="px-3 py-1.5 text-right">Tamamlama</th>
                  <th className="px-3 py-1.5 text-right">Doğruluk</th>
                  <th className="px-3 py-1.5 text-right">Disiplin</th>
                  <th className="px-3 py-1.5 text-right">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.teachers.map((t: TeacherScorecardRow, i) => (
                  <tr key={t.teacher_id ?? `none-${i}`} className="hover:bg-muted/40">
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1.5 font-medium">
                        {i === 0 && t.score >= 75 ? <Award className="size-4 text-amber-500" aria-hidden /> : null}
                        {t.teacher_name}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-16 overflow-hidden rounded bg-slate-100">
                          <div className={cn("h-full rounded", BAR[t.score_color] ?? BAR.amber)} style={{ width: `${t.score}%` }} />
                        </div>
                        <span className={cn("text-sm font-bold tabular-nums", SCORE_TEXT[t.score_color] ?? "")}>{t.score}</span>
                        <span className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-medium", SCORE_BADGE[t.score_color] ?? SCORE_BADGE.amber)}>{t.score_label}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{t.student_count}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{pct(t.completion_rate)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{pct(t.accuracy)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground" title="Öğrenci başına haftalık planlanan soru">{t.discipline_per_student_week} soru</td>
                    <td className="px-3 py-2 text-right">
                      {t.risk_students > 0 ? (
                        <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-medium text-rose-700">{t.risk_students}</span>
                      ) : (
                        <span className="text-[11px] text-emerald-600">0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
