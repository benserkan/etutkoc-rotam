"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Lock, MessageSquare } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WaSendDialog } from "@/components/messaging/wa-send-dialog";
import {
  getInstitutionTeacherCard,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  TeacherCardResponse,
  TeacherCardStudentRow,
} from "@/lib/types/institution";

interface Props {
  initial: TeacherCardResponse;
  teacherId: number;
}

/**
 * Öğretmen kartı — Jinja `institution/teacher_card.html` ile birebir:
 *   - Gizlilik banner (program/not/detay görünmez)
 *   - 4 KPI (öğrenci, plan, tamamlanan, oran)
 *   - Öğrenci listesi (detay linki YOK — sıradan tablo)
 *   - Pasif satırlar silikleştirilir
 */
export function TeacherCardClient({ initial, teacherId }: Props) {
  const q = useQuery<TeacherCardResponse>({
    queryKey: institutionKeys.teacher(teacherId),
    queryFn: () => getInstitutionTeacherCard(teacherId),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const { teacher, students, total_planned, total_completed, overall_rate_pct } =
    data;
  const [waOpen, setWaOpen] = React.useState(false);

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/institution/teachers"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Öğretmenler
        </Link>
        <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight font-display">
              {teacher.full_name}
            </h1>
            <div className="text-sm text-muted-foreground font-mono mt-1">
              {teacher.email}
            </div>
          </div>
          <Button
            onClick={() => setWaOpen(true)}
            className="shrink-0 bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white"
          >
            <MessageSquare className="size-4" aria-hidden />
            WA Gönder
          </Button>
        </div>
      </header>

      <WaSendDialog
        open={waOpen}
        onOpenChange={setWaOpen}
        targetUserId={teacherId}
        targetNameFallback={teacher.full_name}
        title={`${teacher.full_name} (Öğretmen) — WhatsApp`}
        defaultCategory="kurum_ogretmen"
      />

      <div className="rounded-md border border-sky-200 bg-sky-50 text-sky-900 px-3 py-2.5 text-xs flex items-start gap-2">
        <Lock className="size-4 shrink-0 mt-0.5" aria-hidden />
        <div>
          Bu sayfada öğretmenin programını, veli notlarını veya öğrenci görev
          detaylarını görme yetkin yok. Yalnızca <strong>roster</strong> ve{" "}
          <strong>haftalık tamamlama yüzdesi</strong> görünür. Ayrıntı için
          doğrudan iletişime geç.
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Öğrenci" value={students.length} />
        <KpiCard label="Planlanan (7 gün)" value={total_planned} />
        <KpiCard label="Tamamlanan" value={total_completed} />
        <KpiCard
          label="Tamamlama Oranı"
          value={overall_rate_pct == null ? "—" : `%${overall_rate_pct}`}
          valueClassName={rateColorClass(overall_rate_pct)}
        />
      </div>

      <Card>
        <div className="px-4 py-3 border-b border-border">
          <h2 className="font-medium">Öğrenciler</h2>
        </div>
        {students.length === 0 ? (
          <div className="px-4 py-12 text-center text-sm text-muted-foreground italic">
            Bu öğretmenin henüz öğrencisi yok.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Öğrenci</th>
                  <th className="text-left px-4 py-2 font-medium">Sınıf</th>
                  <th className="text-right px-4 py-2 font-medium">Plan</th>
                  <th className="text-right px-4 py-2 font-medium">
                    Tamamlanan
                  </th>
                  <th className="text-right px-4 py-2 font-medium">Oran</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {students.map((s) => (
                  <StudentRow key={s.id} student={s} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function StudentRow({ student }: { student: TeacherCardStudentRow }) {
  return (
    <tr
      className={cn(!student.is_active && "bg-muted/30 text-muted-foreground")}
    >
      <td className="px-4 py-2">
        {student.full_name}
        {!student.is_active && (
          <span className="ml-1.5 text-[10px] text-muted-foreground">
            (pasif)
          </span>
        )}
      </td>
      <td className="px-4 py-2 text-muted-foreground">
        {student.display_grade_label ?? "—"}
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {student.weekly_planned}
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {student.weekly_completed}
      </td>
      <td
        className={cn(
          "px-4 py-2 text-right tabular-nums font-semibold",
          rateColorClass(student.weekly_rate_pct),
        )}
      >
        {student.weekly_rate_pct == null
          ? "—"
          : `%${student.weekly_rate_pct}`}
      </td>
    </tr>
  );
}

function KpiCard({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: number | string;
  valueClassName?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div
          className={cn(
            "text-2xl font-semibold mt-1 tabular-nums",
            valueClassName,
          )}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function rateColorClass(pct: number | null): string {
  if (pct == null) return "text-muted-foreground";
  if (pct >= 70) return "text-emerald-700";
  if (pct >= 40) return "text-amber-700";
  return "text-rose-700";
}
