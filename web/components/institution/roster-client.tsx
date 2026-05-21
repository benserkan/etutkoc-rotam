"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  getInstitutionRoster,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  InstitutionRosterResponse,
  RosterListParams,
  RosterRowItem,
} from "@/lib/types/institution";

interface Props {
  initial: InstitutionRosterResponse;
  params: Required<{
    teacher_id: number | null;
    grade: number | null;
    is_graduate: boolean | null;
  }>;
}

/**
 * Roster — Jinja `institution/roster.html` ile birebir.
 *
 * Filtreler URL state'ten beslenir (geri/ileri navigasyon parite).
 * Filter form submit URL'yi günceller → server fetch yenilenir → initial yenilenir.
 */
export function RosterClient({ initial, params }: Props) {
  const router = useRouter();
  const q = useQuery<InstitutionRosterResponse>({
    queryKey: institutionKeys.roster(params as RosterListParams),
    queryFn: () => getInstitutionRoster(params as RosterListParams),
    initialData: initial,
    staleTime: 15_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const { items, filters } = data;

  // Local form state — URL state ile senkronize tutuluyor
  const [teacherId, setTeacherId] = React.useState<string>(
    params.teacher_id != null ? String(params.teacher_id) : "",
  );
  const [grade, setGrade] = React.useState<string>(
    params.is_graduate ? "graduate" : params.grade != null ? String(params.grade) : "",
  );

  function applyFilters(e: React.FormEvent) {
    e.preventDefault();
    const qs = new URLSearchParams();
    if (teacherId) qs.set("teacher_id", teacherId);
    if (grade) qs.set("grade", grade);
    const suffix = qs.toString();
    router.push(`/institution/roster${suffix ? `?${suffix}` : ""}`);
  }

  function reset() {
    setTeacherId("");
    setGrade("");
    router.push("/institution/roster");
  }

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/institution"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
          Roster
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Tüm öğrenciler ve haftalık tamamlama yüzdeleri
        </p>
      </header>

      <Card>
        <form
          onSubmit={applyFilters}
          className="p-3 flex flex-wrap items-end gap-3"
        >
          <div className="space-y-1 min-w-[180px]">
            <Label
              htmlFor="rs-teacher"
              className="text-[11px] uppercase tracking-wider text-muted-foreground"
            >
              Öğretmen
            </Label>
            <select
              id="rs-teacher"
              value={teacherId}
              onChange={(e) => setTeacherId(e.target.value)}
              className="block w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">— Tümü —</option>
              {filters.teachers.map((t) => (
                <option key={t.id} value={String(t.id)}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1 min-w-[140px]">
            <Label
              htmlFor="rs-grade"
              className="text-[11px] uppercase tracking-wider text-muted-foreground"
            >
              Sınıf
            </Label>
            <select
              id="rs-grade"
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
              className="block w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">— Tümü —</option>
              {[5, 6, 7, 8, 9, 10, 11, 12].map((g) => (
                <option key={g} value={String(g)}>
                  {g}. sınıf
                </option>
              ))}
              <option value="graduate">Mezun</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <Button type="submit" size="sm">
              Filtrele
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={reset}
            >
              Temizle
            </Button>
          </div>
          <div className="ml-auto text-sm text-muted-foreground">
            {items.length} kayıt
          </div>
        </form>
      </Card>

      {items.length === 0 ? (
        <Card>
          <div className="p-12 text-center text-sm text-muted-foreground">
            Filtreyle eşleşen öğrenci yok.
          </div>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Öğrenci</th>
                  <th className="text-left px-4 py-2 font-medium">Sınıf</th>
                  <th className="text-left px-4 py-2 font-medium">Öğretmen</th>
                  <th className="text-right px-4 py-2 font-medium">Plan</th>
                  <th className="text-right px-4 py-2 font-medium">
                    Tamamlanan
                  </th>
                  <th className="text-right px-4 py-2 font-medium">Oran</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((r) => (
                  <RosterRow key={r.student_id} row={r} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function RosterRow({ row }: { row: RosterRowItem }) {
  return (
    <tr className={cn(!row.is_active && "bg-muted/30 text-muted-foreground")}>
      <td className="px-4 py-2 font-medium">{row.full_name}</td>
      <td className="px-4 py-2 text-muted-foreground">
        {row.display_grade_label ?? "—"}
      </td>
      <td className="px-4 py-2 text-muted-foreground">
        {row.teacher_name ?? "—"}
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {row.weekly_planned}
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {row.weekly_completed}
      </td>
      <td
        className={cn(
          "px-4 py-2 text-right tabular-nums font-semibold",
          rateColorClass(row.weekly_rate_pct),
        )}
      >
        {row.weekly_rate_pct == null ? "—" : `%${row.weekly_rate_pct}`}
      </td>
    </tr>
  );
}

function rateColorClass(pct: number | null): string {
  if (pct == null) return "text-muted-foreground";
  if (pct >= 70) return "text-emerald-700";
  if (pct >= 40) return "text-amber-700";
  return "text-rose-700";
}
