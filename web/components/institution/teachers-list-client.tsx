"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  getInstitutionTeachers,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  InstitutionTeacherListResponse,
  TeacherSummaryItem,
} from "@/lib/types/institution";
import { formatLastLogin } from "@/components/institution/dashboard-client";
import { NewTeacherDialog } from "@/components/institution/new-teacher-dialog";
import { TeacherRowActions } from "@/components/institution/teacher-row-actions";

interface Props {
  initial: InstitutionTeacherListResponse;
}

/**
 * Öğretmen listesi — Jinja `institution/teachers_list.html` ile birebir:
 *   - "+ Öğretmen Ekle" dialog (geçici şifre yanıtta)
 *   - is_paused rozet ayrımı (auto vs manuel)
 *   - 2 eylem grubu (pause/resume + activate/deactivate)
 *   - Onay metinleri Jinja ile aynı
 */
export function TeachersListClient({ initial }: Props) {
  const q = useQuery<InstitutionTeacherListResponse>({
    queryKey: institutionKeys.teachers(),
    queryFn: () => getInstitutionTeachers(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const { institution, items } = data;
  const [createOpen, setCreateOpen] = React.useState(false);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link
            href="/institution"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Panel
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
            Öğretmenler
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {institution.name} — {items.length} öğretmen
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" aria-hidden />
          Öğretmen Ekle
        </Button>
      </header>

      {items.length === 0 ? (
        <Card>
          <div className="p-12 text-center text-sm text-muted-foreground">
            Henüz öğretmen yok. Sağ üstten ekle.
          </div>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Öğretmen</th>
                  <th className="text-right px-4 py-2 font-medium">Öğrenci</th>
                  <th className="text-right px-4 py-2 font-medium">Plan</th>
                  <th className="text-right px-4 py-2 font-medium">
                    Tamamlanan
                  </th>
                  <th className="text-right px-4 py-2 font-medium">Oran</th>
                  <th className="text-right px-4 py-2 font-medium">
                    Son Giriş
                  </th>
                  <th className="text-right px-4 py-2 font-medium">
                    <span className="sr-only">Eylemler</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((t) => (
                  <TeacherRow key={t.id} teacher={t} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <NewTeacherDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
      />
    </div>
  );
}

function TeacherRow({ teacher }: { teacher: TeacherSummaryItem }) {
  return (
    <tr className={cn(!teacher.is_active && "bg-muted/30 text-muted-foreground")}>
      <td className="px-4 py-2">
        <Link
          href={`/institution/teachers/${teacher.id}`}
          className="font-medium hover:text-accent hover:underline"
        >
          {teacher.full_name}
        </Link>
        {!teacher.is_active && (
          <span className="ml-1.5 inline-flex items-center text-[10px] px-1.5 py-0.5 rounded bg-muted border border-border text-muted-foreground">
            pasif
          </span>
        )}
        {teacher.is_paused && <PauseBadge reason={teacher.pause_reason} />}
        <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
          {teacher.email}
        </div>
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {teacher.student_count}
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {teacher.weekly_planned}
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {teacher.weekly_completed}
      </td>
      <td
        className={cn(
          "px-4 py-2 text-right tabular-nums font-semibold",
          rateColorClass(teacher.weekly_rate_pct),
        )}
      >
        {teacher.weekly_rate_pct == null
          ? "—"
          : `%${teacher.weekly_rate_pct}`}
      </td>
      <td className="px-4 py-2 text-right text-xs text-muted-foreground">
        {formatLastLogin(teacher.last_login_days)}
      </td>
      <td className="px-4 py-2 text-right whitespace-nowrap">
        <TeacherRowActions teacher={teacher} />
      </td>
    </tr>
  );
}

function PauseBadge({ reason }: { reason: string | null }) {
  if (reason && reason.startsWith("auto")) {
    return (
      <span
        className="ml-1.5 inline-flex items-center text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-300"
        title="Sistem tarafından sessizlik nedeniyle otomatik pasifleştirildi (uyarılar susturulmuş)"
      >
        🤖 Otomatik pasif
      </span>
    );
  }
  return (
    <span
      className="ml-1.5 inline-flex items-center text-[10px] px-1.5 py-0.5 rounded bg-muted border border-border text-foreground/70"
      title="Manuel olarak pasifleştirildi — uyarılar susturulmuş"
    >
      ⏸ Uyarılar sessiz
    </span>
  );
}

function rateColorClass(pct: number | null): string {
  if (pct == null) return "text-muted-foreground";
  if (pct >= 70) return "text-emerald-700";
  if (pct >= 40) return "text-amber-700";
  return "text-rose-700";
}
