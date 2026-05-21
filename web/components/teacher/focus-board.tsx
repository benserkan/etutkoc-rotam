"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Award,
  Coffee,
  Flame,
  Loader2,
  Medal,
  Sparkles,
  Timer,
  Trees,
  TrendingUp,
  Trophy,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { getTeacherStudentFocus, teacherKeys } from "@/lib/api/teacher";
import type {
  FocusBadge as FocusBadgeT,
  FocusKind,
  TeacherFocusResponse,
} from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Props {
  studentId: number;
}

export function FocusBoard({ studentId }: Props) {
  const q = useQuery<TeacherFocusResponse>({
    queryKey: teacherKeys.studentFocus(studentId),
    queryFn: () => getTeacherStudentFocus(studentId),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-12">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
      </div>
    );
  }
  if (q.error || !q.data) {
    return (
      <div className="text-sm text-rose-500">Odak verileri yüklenemedi.</div>
    );
  }

  const d = q.data;

  return (
    <div className="space-y-6 max-w-6xl">
      <header>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          <Link
            href={`/teacher/students/${studentId}`}
            className="hover:underline"
          >
            ← {d.student_name}
          </Link>
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
          <Timer className="size-6 text-rose-500" aria-hidden />
          Odak &amp; Rozetler
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Pomodoro istatistikleri, kazanılmış rozetler ve son seans tarihçesi.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <Kpi
          icon={Flame}
          label="Şu anki seri"
          value={`${d.streak_days} gün`}
          tone="text-amber-500"
        />
        <Kpi
          icon={TrendingUp}
          label="En uzun seri"
          value={`${d.longest_streak} gün`}
          tone="text-foreground"
        />
        <Kpi
          icon={Timer}
          label="30g odak"
          value={`${d.work_minutes_30d} dk`}
          tone="text-indigo-500"
        />
        <Kpi
          icon={Medal}
          label="Rozet"
          value={String(d.badges.length)}
          tone="text-emerald-500"
        />
        <Kpi
          icon={Sparkles}
          label="Toplam puan"
          value={String(d.points_total)}
          tone="text-violet-500"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Bugün</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <Row label="Odak seansı" value={String(d.today_work_sessions)} />
              <Row label="Odak dakikası" value={String(d.today_work_minutes)} />
              <Row label="Mola dakikası" value={String(d.today_break_minutes)} />
              {d.today_interrupted_count > 0 ? (
                <Row
                  label="Yarıda bırakılan"
                  value={String(d.today_interrupted_count)}
                  rowTone="rose"
                />
              ) : null}
            </dl>
            {d.today_work_sessions === 0 ? (
              <p className="text-xs text-muted-foreground italic mt-3">
                Bugün henüz seans yok.
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">
              Rozetler ({d.badges.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {d.badges.length === 0 ? (
              <p className="text-sm text-muted-foreground">Henüz rozet yok.</p>
            ) : (
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                {d.badges.map((b) => (
                  <BadgeChip key={b.kind} badge={b} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">
            Son {d.recent_sessions.length} Seans
          </CardTitle>
        </CardHeader>
        <CardContent>
          {d.recent_sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              Henüz seans kaydı yok.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Tarih</th>
                    <th className="text-left px-3 py-2 font-medium">Tür</th>
                    <th className="text-left px-3 py-2 font-medium">Etiket</th>
                    <th className="text-right px-3 py-2 font-medium">Dakika</th>
                  </tr>
                </thead>
                <tbody>
                  {d.recent_sessions.map((s) => (
                    <tr
                      key={s.id}
                      className="border-b border-border last:border-0 hover:bg-muted/20"
                    >
                      <td className="px-3 py-2 text-muted-foreground tabular-nums">
                        {formatSessionDate(s.started_at)}
                      </td>
                      <td className="px-3 py-2">
                        <KindLabel kind={s.kind} />
                      </td>
                      <td className="px-3 py-2 text-foreground/80 truncate max-w-[12rem]">
                        {s.label || "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {s.ended_at ? (
                          <>
                            <span className="text-foreground">
                              {s.actual_minutes}
                            </span>
                            <span className="text-muted-foreground">
                              /{s.planned_minutes}
                            </span>
                            {s.interrupted ? (
                              <span className="text-rose-500 ml-1.5 text-xs">
                                (yarıda)
                              </span>
                            ) : null}
                          </>
                        ) : (
                          <span className="text-amber-500">devam</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
          <Icon className={cn("size-3.5", tone)} aria-hidden />
          {label}
        </div>
        <div className={cn("text-2xl font-bold mt-1.5 tabular-nums", tone)}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  value,
  rowTone,
}: {
  label: string;
  value: string;
  rowTone?: "rose";
}) {
  return (
    <div className="flex justify-between items-center text-sm">
      <span
        className={cn(
          rowTone === "rose" ? "text-rose-500" : "text-muted-foreground",
        )}
      >
        {label}
      </span>
      <span
        className={cn(
          "font-semibold tabular-nums",
          rowTone === "rose" ? "text-rose-500" : "text-foreground",
        )}
      >
        {value}
      </span>
    </div>
  );
}

const KIND_META: Record<FocusKind, { icon: LucideIcon; tone: string; label: string }> = {
  work: { icon: Timer, tone: "text-rose-500", label: "Odak" },
  short_break: { icon: Coffee, tone: "text-sky-500", label: "Kısa Mola" },
  long_break: { icon: Trees, tone: "text-emerald-500", label: "Uzun Mola" },
};

function KindLabel({ kind }: { kind: FocusKind }) {
  const meta = KIND_META[kind];
  const Icon = meta.icon;
  return (
    <span className={cn("inline-flex items-center gap-1.5", meta.tone)}>
      <Icon className="size-3.5" aria-hidden />
      {meta.label}
    </span>
  );
}

/**
 * Rozet kind'inden Lucide ikon JSX'i — backend `kind` string'leri varsayılan
 * gamification listesinden gelir; bilinmeyen kind'ler için fallback Award.
 */
function BadgeIcon({ kind, className }: { kind: string; className?: string }) {
  const k = kind.toLowerCase();
  if (k.includes("streak") || k.includes("seri") || k.includes("fire"))
    return <Flame className={className} aria-hidden />;
  if (k.includes("trophy") || k.includes("champion") || k.includes("master"))
    return <Trophy className={className} aria-hidden />;
  if (k.includes("zap") || k.includes("hız") || k.includes("speed"))
    return <Zap className={className} aria-hidden />;
  if (k.includes("medal") || k.includes("rozet"))
    return <Medal className={className} aria-hidden />;
  if (k.includes("spark") || k.includes("yıldız"))
    return <Sparkles className={className} aria-hidden />;
  return <Award className={className} aria-hidden />;
}

function BadgeChip({ badge }: { badge: FocusBadgeT }) {
  return (
    <div
      title={`${badge.title} — ${badge.description}`}
      className="text-center p-2.5 rounded-lg border border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10 transition"
    >
      <BadgeIcon
        kind={badge.kind}
        className="size-5 mx-auto text-amber-500"
      />
      <div className="text-[10px] text-foreground mt-1 leading-tight font-medium line-clamp-2">
        {badge.title}
      </div>
    </div>
  );
}

function formatSessionDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mi}`;
}
