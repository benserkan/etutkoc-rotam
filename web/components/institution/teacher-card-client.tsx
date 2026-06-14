"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Lock, MessageSquare } from "lucide-react";

import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";
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
  const {
    teacher, students, total_planned, total_completed, overall_rate_pct,
    total_deneme_planned, total_deneme_completed,
  } = data;
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
            <DemoHint contextKey="teacher-detail" role="institution_admin" className="mt-2" />
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
        <KpiCard label="Öğrenci" value={students.length} sub="bu koça bağlı" />
        <KpiCard
          label="Planlanan test"
          value={total_planned}
          unit="soru"
          sub={`${total_completed} çözüldü · soru bankası · son 7 gün`}
        />
        <KpiCard
          label="Planlanan deneme"
          value={total_deneme_planned}
          unit="adet"
          sub={`${total_deneme_completed} tamamlandı · deneme adedi · son 7 gün`}
        />
        <KpiCard
          label="Test tamamlama"
          value={overall_rate_pct == null ? "—" : `%${overall_rate_pct}`}
          valueClassName={rateColorClass(overall_rate_pct)}
          sub="çözülen ÷ planlanan · yalnız test"
        />
      </div>

      {/* Kart sayılarının ne anlama geldiğini her zaman görünür biçimde açıkla
          (admin/kurum panelinde açıklamasız sayı yasak — jargon kuralı). */}
      <div className="rounded-md border border-border bg-muted/30 px-3 py-2.5 text-xs text-muted-foreground leading-relaxed">
        Yukarıdaki ve aşağıdaki sayılar <strong>son 7 günde</strong> planlanan ve
        çözülen <strong>test (soru) adedini</strong> gösterir.{" "}
        <strong>Plan</strong> = koçun bu öğrenciye 7 günde atadığı test sayısı ·{" "}
        <strong>Tamamlanan</strong> = öğrencinin çözüp işaretlediği test ·{" "}
        <strong>Oran</strong> = çözülen ÷ planlanan. (Aylık/kümülatif değil — kayan
        son 7 gün.)
      </div>

      <Card>
        <div className="px-4 py-3 border-b border-border">
          <h2 className="font-medium">Öğrenciler</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Son 7 gün — planlanan ve çözülen <strong>test adedi</strong> (öğrenci
            başına)
          </p>
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
                  <th className="text-right px-4 py-2 font-medium">
                    Planlanan test
                  </th>
                  <th className="text-right px-4 py-2 font-medium">
                    Çözülen test
                  </th>
                  <th className="text-right px-4 py-2 font-medium">
                    Deneme (tam/plan)
                  </th>
                  <th className="text-right px-4 py-2 font-medium">
                    Test&nbsp;%
                  </th>
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
      <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
        {student.weekly_deneme_planned > 0
          ? `${student.weekly_deneme_completed}/${student.weekly_deneme_planned}`
          : "—"}
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
  unit,
  sub,
}: {
  label: string;
  value: number | string;
  valueClassName?: string;
  unit?: string;
  sub?: string;
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
          {unit ? (
            <span className="ml-1 text-sm font-medium text-muted-foreground">
              {unit}
            </span>
          ) : null}
        </div>
        {sub ? (
          <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>
        ) : null}
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
