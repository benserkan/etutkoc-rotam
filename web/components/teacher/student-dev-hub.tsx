"use client";

/**
 * Gelişim sekmesi — koçluğun sırrı dört araç tek yerde (2026-09-08).
 *
 * Eskiden başlıkta dört ayrı renkli düğmeydi (Hedefler · Tekrar · DNA · Odak);
 * dokuz düğmeyle yan yana "amatör ve sıkışık" görünüyordu (koç ekran
 * görüntüsü). Şimdi bir sekme: her araç bir kart — ne işe yarar + o anki
 * özet ölçü + "Aç". Mobil "Gelişim" hub'ının web karşılığı.
 */

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Brain, Dna, Target, Timer } from "lucide-react";

import {
  getTeacherStudentDna,
  getTeacherStudentFocus,
  getTeacherStudentGoals,
  getTeacherStudentReview,
  teacherKeys,
} from "@/lib/api/teacher";
import type {
  BurnoutRiskLevel,
  DnaChronotype,
  TeacherDnaResponse,
  TeacherFocusResponse,
  TeacherGoalsResponse,
  TeacherReviewResponse,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

const CHRONO: Record<DnaChronotype, string> = {
  morning: "Sabahçı",
  afternoon: "Öğlenci",
  evening: "Akşamcı",
  night: "Gececi",
  unknown: "Belirsiz",
};
const BURNOUT: Record<BurnoutRiskLevel, { label: string; cls: string }> = {
  healthy: { label: "sağlıklı", cls: "text-emerald-700 dark:text-emerald-300" },
  watch: { label: "izle", cls: "text-amber-700 dark:text-amber-300" },
  warn: { label: "uyarı", cls: "text-amber-800 dark:text-amber-200" },
  critical: { label: "kritik", cls: "text-rose-700 dark:text-rose-300" },
};

export function StudentDevHub({ studentId }: { studentId: number }) {
  const goalsQ = useQuery<TeacherGoalsResponse>({
    queryKey: teacherKeys.studentGoals(studentId),
    queryFn: () => getTeacherStudentGoals(studentId),
    staleTime: 60_000,
  });
  const reviewQ = useQuery<TeacherReviewResponse>({
    queryKey: teacherKeys.studentReview(studentId),
    queryFn: () => getTeacherStudentReview(studentId),
    staleTime: 60_000,
  });
  const dnaQ = useQuery<TeacherDnaResponse>({
    queryKey: teacherKeys.studentDna(studentId),
    queryFn: () => getTeacherStudentDna(studentId),
    staleTime: 60_000,
  });
  const focusQ = useQuery<TeacherFocusResponse>({
    queryKey: teacherKeys.studentFocus(studentId),
    queryFn: () => getTeacherStudentFocus(studentId),
    staleTime: 60_000,
  });

  const g = goalsQ.data;
  const r = reviewQ.data;
  const d = dnaQ.data;
  const f = focusQ.data;
  const base = `/teacher/students/${studentId}`;

  return (
    <div className="space-y-3" data-dev-hub>
      <p className="text-sm text-muted-foreground">
        Program takibinin ötesi: hedef ağacı, aralıklı tekrar, çalışma DNA&apos;sı ve
        odak. Her kart o anki özeti gösterir; ayrıntı ve yönetim için aç.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <HubCard
          href={`${base}/goals`}
          icon={<Target className="size-5" aria-hidden />}
          tone="amber"
          title="Hedefler"
          what="Sınav, ders ve operasyonel hedef ağacı"
          loading={goalsQ.isLoading}
          stat={
            g
              ? g.summary.total > 0
                ? `${g.summary.active} aktif · ${g.summary.achieved} başarıldı${
                    g.summary.overall_pct != null ? ` · %${Math.round(g.summary.overall_pct)}` : ""
                  }`
                : "Henüz hedef yok"
              : null
          }
          sub={
            g && g.topic_count > 0
              ? `${g.finished_topic_count}/${g.topic_count} konu bitti`
              : null
          }
        />
        <HubCard
          href={`${base}/review`}
          icon={<Brain className="size-5" aria-hidden />}
          tone="emerald"
          title="Tekrar"
          what="Aralıklı tekrar kartları (unutmadan önce hatırlat)"
          loading={reviewQ.isLoading}
          stat={
            r
              ? r.breakdown.total > 0
                ? `${r.breakdown.due_now} kart vadesi geldi · ${r.breakdown.total} toplam`
                : "Henüz tekrar kartı yok"
              : null
          }
          sub={
            r && r.struggle_cards.length > 0
              ? `${r.struggle_cards.length} konuda zorlanıyor`
              : null
          }
        />
        <HubCard
          href={`${base}/dna`}
          icon={<Dna className="size-5" aria-hidden />}
          tone="sky"
          title="Çalışma DNA'sı"
          what="Ne zaman, hangi derste verimli; tükenmişlik sinyali"
          loading={dnaQ.isLoading}
          stat={
            d
              ? d.has_enough_data
                ? `${CHRONO[d.chronotype] ?? "Belirsiz"}${
                    d.peak_day_name ? ` · zirve ${d.peak_day_name}` : ""
                  }`
                : "Yeterli veri yok"
              : null
          }
          sub={
            d && d.has_enough_data ? (
              <>
                Tükenmişlik:{" "}
                <span className={cn("font-medium", BURNOUT[d.burnout_risk_level]?.cls)}>
                  {BURNOUT[d.burnout_risk_level]?.label ?? d.burnout_risk_level}
                </span>
              </>
            ) : null
          }
        />
        <HubCard
          href={`${base}/focus`}
          icon={<Timer className="size-5" aria-hidden />}
          tone="rose"
          title="Odak"
          what="Pomodoro oturumları, seri ve rozetler"
          loading={focusQ.isLoading}
          stat={
            f
              ? f.streak_days > 0 || f.work_minutes_30d > 0
                ? `${f.streak_days} gün seri · son 30 günde ${f.work_minutes_30d} dk`
                : "Henüz odak oturumu yok"
              : null
          }
          sub={f && f.badges.length > 0 ? `${f.badges.length} rozet` : null}
        />
      </div>
    </div>
  );
}

const TONE = {
  amber: "border-amber-200 bg-amber-50/60 text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200",
  emerald: "border-emerald-200 bg-emerald-50/60 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200",
  sky: "border-sky-200 bg-sky-50/60 text-sky-800 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200",
  rose: "border-rose-200 bg-rose-50/60 text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200",
} as const;

function HubCard({
  href,
  icon,
  tone,
  title,
  what,
  stat,
  sub,
  loading,
}: {
  href: string;
  icon: React.ReactNode;
  tone: keyof typeof TONE;
  title: string;
  what: string;
  stat: React.ReactNode | null;
  sub?: React.ReactNode | null;
  loading: boolean;
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col gap-2 rounded-xl border border-border bg-card p-4 transition hover:border-foreground/30 hover:shadow-sm"
      data-hub-card={title}
    >
      <div className="flex items-center gap-2.5">
        <span className={cn("inline-flex size-9 items-center justify-center rounded-lg border", TONE[tone])}>
          {icon}
        </span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          <p className="text-[11px] leading-snug text-muted-foreground">{what}</p>
        </div>
      </div>
      <div className="min-h-[2.5rem] text-sm">
        {loading ? (
          <span className="inline-block h-4 w-32 animate-pulse rounded bg-muted" />
        ) : stat ? (
          <p className="font-medium text-foreground">{stat}</p>
        ) : (
          <p className="text-muted-foreground">Yüklenemedi</p>
        )}
        {sub ? <p className="text-[11px] text-muted-foreground">{sub}</p> : null}
      </div>
      <span className="mt-auto inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition group-hover:text-foreground">
        Aç <ArrowRight className="size-3.5" aria-hidden />
      </span>
    </Link>
  );
}
