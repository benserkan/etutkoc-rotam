"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Lock, MessageSquare, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { WaSendDialog } from "@/components/messaging/wa-send-dialog";
import { ColumnHint } from "@/components/ui/column-hint";
import { useTeacherAiToggle } from "@/lib/hooks/use-institution-mutations";
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

      <div className="rounded-md border border-sky-200 bg-sky-50 text-sky-900 px-3 py-2.5 text-xs flex items-start gap-2 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200">
        <Lock className="size-4 shrink-0 mt-0.5" aria-hidden />
        <div>
          Görev içeriklerini, veli notlarını ve öğrenci ayrıntılarını görme yetkin
          yok. Burada yalnız <strong>programın ne zaman hazırlandığı</strong> ve
          öğrencinin <strong>gün gün görev tamamlama oranı</strong> görünür.
          Ayrıntı için koçla doğrudan iletişime geç.
        </div>
      </div>

      {/* AI erişimi — kurum, koçun (ve alt-ağacının) havuz harcamasını yönetir */}
      <AiAccessCard teacherId={teacherId} enabled={data.ai_enabled} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Öğrenci"
          hint="Bu koça bağlı öğrenci sayısı (pasifler dahil)."
          value={students.length}
          sub="bu koça bağlı"
        />
        <KpiCard
          label="Planlanan test"
          hint="Son 7 günde (bugün dahil) bu koçun öğrencilerine soru bankalarından atadığı test sayısı. Denemeler ve etkinlik görevleri (video, özet vb.) bu sayıya girmez."
          value={total_planned}
          unit="test"
          sub={`${total_completed} çözüldü · soru bankası · son 7 gün`}
        />
        <KpiCard
          label="Planlanan deneme"
          hint="Son 7 günde programa konan deneme sayısı (branş ya da genel deneme). Soru sayısı değil, deneme ADEDİ."
          value={total_deneme_planned}
          unit="adet"
          sub={`${total_deneme_completed} tamamlandı · deneme adedi · son 7 gün`}
        />
        <KpiCard
          label="Test tamamlama"
          hint="Çözülen test ÷ planlanan test (son 7 gün). Yalnız soru bankası testleri; deneme ve etkinlik görevleri hariç."
          value={overall_rate_pct == null ? "—" : `%${overall_rate_pct}`}
          valueClassName={rateColorClass(overall_rate_pct)}
          sub="çözülen ÷ planlanan · yalnız test"
        />
      </div>

      <Card>
        <div className="px-4 py-3 border-b border-border">
          <h2 className="font-medium">Öğrenciler</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Programın ne zaman hazırlandığı ve son 7 günün gün gün görev
            tamamlaması. Sütun başlığının üzerine gel ya da dokun: ne ölçtüğü
            açılır.
          </p>
        </div>
        {students.length === 0 ? (
          <div className="px-4 py-12 text-center text-sm text-muted-foreground italic">
            Bu öğretmenin henüz öğrencisi yok.
          </div>
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Öğrenci</th>
                  <th className="text-left px-4 py-2 font-medium">
                    <ColumnHint
                      label="Program"
                      hint="Koçun bu öğrenciye EN SON görev yayınladığı gün ve programın hangi güne kadar uzandığı. Uzun süredir yeni program yoksa öğrenci programsız kalıyor olabilir."
                    />
                  </th>
                  <th className="text-left px-4 py-2 font-medium">
                    <ColumnHint
                      label="Son 7 gün"
                      hint="Her kare bir gün (soldan sağa 6 gün önceden bugüne). Renk o günün görev tamamlama oranı: yeşil %70 ve üstü, sarı %40–69, kırmızı %40 altı, gri o gün görev yok. Kareye gelince ya da dokununca sayılar görünür. Video, özet gibi etkinlik görevleri dahil."
                    />
                  </th>
                  <th className="text-right px-4 py-2 font-medium">
                    <ColumnHint
                      label="Görev %"
                      hint="Son 7 günde tamamlanan görev ÷ verilen görev. Her görev bir sayılır (test, deneme, video, özet…)."
                    />
                  </th>
                  <th className="text-right px-4 py-2 font-medium">
                    <ColumnHint
                      label="Test"
                      hint="Son 7 günde çözülen / planlanan test sayısı. Yalnız soru bankası testleri; denemeler ayrı sütunda."
                    />
                  </th>
                  <th className="text-right px-4 py-2 font-medium">
                    <ColumnHint
                      label="Deneme"
                      hint="Son 7 günde tamamlanan / programa konan deneme sayısı (branş ya da genel deneme)."
                    />
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

const TR_DAY = ["Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"];
const TR_DAY2 = ["Pz", "Pt", "Sa", "Ça", "Pe", "Cu", "Ct"];

function fmtDay(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  return `${TR_DAY[d.getDay()]} ${d.toLocaleDateString("tr-TR", { day: "numeric", month: "short" })}`;
}

function relDays(iso: string): string {
  const d = new Date(iso);
  const start = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const n = Math.round((start(new Date()) - start(d)) / 86_400_000);
  if (n <= 0) return "bugün";
  if (n === 1) return "dün";
  return `${n} gün önce`;
}

function StudentRow({ student }: { student: TeacherCardStudentRow }) {
  const days = student.days ?? [];
  const wt = student.week_gorev_total ?? 0;
  const wd = student.week_gorev_done ?? 0;
  const gorevPct = wt > 0 ? Math.round((wd / wt) * 100) : null;
  return (
    <tr
      className={cn(!student.is_active && "bg-muted/30 text-muted-foreground")}
      data-testid="teacher-card-student"
    >
      <td className="px-4 py-2.5 align-top">
        <span className="break-words">{student.full_name}</span>
        {!student.is_active && (
          <span className="ml-1.5 text-[10px] text-muted-foreground">(pasif)</span>
        )}
        <span className="block text-xs text-muted-foreground">
          {student.display_grade_label ?? "—"}
        </span>
      </td>
      <td className="px-4 py-2.5 align-top text-xs">
        {student.last_published_at ? (
          <>
            <span className="block text-sm text-foreground">
              {relDays(student.last_published_at)}
            </span>
            <span className="block text-muted-foreground">
              yayınlandı{student.program_until ? ` · son gün ${fmtDay(student.program_until)}` : ""}
            </span>
          </>
        ) : (
          <span className="text-muted-foreground">Henüz program yok</span>
        )}
      </td>
      <td className="px-4 py-2.5 align-top">
        <div className="flex items-end gap-1" data-testid="day-strip">
          {days.map((d) => (
            <DaySquare key={d.date} day={d} />
          ))}
        </div>
      </td>
      <td
        className={cn(
          "px-4 py-2.5 text-right tabular-nums align-top font-semibold",
          rateColorClass(gorevPct),
        )}
      >
        {gorevPct == null ? "—" : `%${gorevPct}`}
        {wt > 0 ? (
          <span className="block text-[11px] font-normal text-muted-foreground">
            {wd}/{wt} görev
          </span>
        ) : null}
      </td>
      <td className="px-4 py-2.5 text-right tabular-nums align-top">
        {student.weekly_planned > 0 ? (
          <>
            {student.weekly_completed}/{student.weekly_planned}
            <span
              className={cn("block text-[11px]", rateColorClass(student.weekly_rate_pct))}
            >
              {student.weekly_rate_pct == null ? "" : `%${student.weekly_rate_pct}`}
            </span>
          </>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-2.5 text-right tabular-nums align-top text-muted-foreground">
        {student.weekly_deneme_planned > 0
          ? `${student.weekly_deneme_completed}/${student.weekly_deneme_planned}`
          : "—"}
      </td>
    </tr>
  );
}

function DaySquare({ day }: { day: { date: string; total: number; done: number } }) {
  const pct = day.total > 0 ? Math.round((day.done / day.total) * 100) : null;
  const tone =
    pct == null
      ? "bg-muted border border-border"
      : pct >= 70
        ? "bg-emerald-500"
        : pct >= 40
          ? "bg-amber-500"
          : "bg-rose-500";
  const label = fmtDay(day.date);
  const text =
    pct == null ? `${label}: görev yok` : `${label}: ${day.done}/${day.total} görev (%${pct})`;
  return (
    <span className="flex flex-col items-center gap-0.5">
      <ColumnHint
        label={<span className={cn("block size-4 rounded-[4px]", tone)} aria-label={text} />}
        hint={text}
        className="no-underline [&>svg]:hidden"
      />
      <span className="text-[9px] leading-none text-muted-foreground">
        {TR_DAY2[new Date(`${day.date}T12:00:00`).getDay()]}
      </span>
    </span>
  );
}

function KpiCard({
  label,
  hint,
  value,
  valueClassName,
  unit,
  sub,
}: {
  label: string;
  hint?: string;
  value: number | string;
  valueClassName?: string;
  unit?: string;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {hint ? <ColumnHint label={label} hint={hint} /> : label}
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
  if (pct >= 70) return "text-emerald-700 dark:text-emerald-400";
  if (pct >= 40) return "text-amber-700 dark:text-amber-400";
  return "text-rose-700 dark:text-rose-400";
}

/**
 * Yapay zekâ erişim kartı (2026-08-03) — kurum yöneticisi koçun AI kullanımını
 * kapatabilir. Kapalıyken koç + öğrencileri + velileri kurum kredi havuzundan
 * HİÇ harcayamaz (tek anahtar, alt-ağaç dahil). Audit'e işlenir.
 */
function AiAccessCard({ teacherId, enabled }: { teacherId: number; enabled: boolean }) {
  const mut = useTeacherAiToggle(teacherId);
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  return (
    <section
      className={cn(
        "rounded-lg border p-4",
        enabled
          ? "border-border bg-card"
          : "border-amber-300 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="size-4 text-violet-600" aria-hidden />
            Yapay zekâ kullanımı
            {!enabled ? (
              <span className="rounded bg-amber-200 px-1.5 py-0.5 text-[10px] font-bold text-amber-900 dark:bg-amber-500/30 dark:text-amber-200">
                KAPALI
              </span>
            ) : null}
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {enabled
              ? "Bu koç, öğrencileri ve velileri yapay zekâ özelliklerinde kurum kredi havuzunu kullanabilir."
              : "Kapalı — koç, öğrencileri ve velileri kurum havuzundan yapay zekâ harcaması yapamaz."}
          </p>
        </div>
        {enabled ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirmOpen(true)}
            disabled={mut.isPending}
            className="text-rose-700 hover:text-rose-800 dark:text-rose-300 dark:hover:text-rose-200"
          >
            Kapat
          </Button>
        ) : (
          <Button size="sm" onClick={() => mut.mutate(true)} disabled={mut.isPending}>
            Aç
          </Button>
        )}
      </div>
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Yapay zekâ kullanımını kapat?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Bu koçun kendi araçları, öğrencilerinin yapay zekâ tetiklemeleri ve
            velilerinin Rota asistanı{" "}
            <span className="font-medium text-foreground">tamamen durur</span>;
            kurum kredi havuzundan harcama yapılmaz. İstediğinde yeniden
            açabilirsin; kayıtlı veriler silinmez.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Vazgeç
            </Button>
            <Button
              className="bg-rose-600 text-white hover:bg-rose-700"
              onClick={() =>
                mut.mutate(false, { onSuccess: () => setConfirmOpen(false) })
              }
              disabled={mut.isPending}
            >
              Kapat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
