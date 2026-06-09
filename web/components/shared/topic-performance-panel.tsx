"use client";

/**
 * Ders → Konu performans paneli (P1) — koç / öğrenci / veli ortak.
 * Her ders için: çözülen test + doğru/yanlış soru + doğruluk %; konulara açılır.
 * Doğruluk renk eşiği (D4): ≥70 emerald · ≥40 amber · <40 rose.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Target, CheckCircle2, XCircle } from "lucide-react";

import { DemoHint } from "@/components/demos/demo-hint";

import {
  getParentTopicPerformance,
  getStudentTopicPerformance,
  getTeacherTopicPerformance,
  topicPerfKeys,
  type TopicPerformanceResponse,
} from "@/lib/api/topic-performance";
import { cn } from "@/lib/utils";

function accTone(pct: number | null): { text: string; bar: string; bg: string } {
  if (pct == null) return { text: "text-muted-foreground", bar: "bg-slate-300", bg: "bg-muted" };
  if (pct >= 70) return { text: "text-emerald-700", bar: "bg-emerald-500", bg: "bg-emerald-50" };
  if (pct >= 40) return { text: "text-amber-700", bar: "bg-amber-500", bg: "bg-amber-50" };
  return { text: "text-rose-700", bar: "bg-rose-500", bg: "bg-rose-50" };
}

function AccBadge({ pct }: { pct: number | null }) {
  const t = accTone(pct);
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", t.bg, t.text)}>
      {pct == null ? "D/Y girilmemiş" : `%${pct} doğru`}
    </span>
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function TopicPerformancePanel({
  source,
  studentId,
}: {
  source: "teacher" | "student" | "parent";
  studentId?: number;
}) {
  const audience: "coach" | "student" | "parent" = source === "teacher" ? "coach" : source;
  const queryKey =
    source === "student"
      ? topicPerfKeys.student()
      : source === "parent"
        ? topicPerfKeys.parent(studentId ?? 0)
        : topicPerfKeys.teacher(studentId ?? 0);
  const fetcher = (): Promise<TopicPerformanceResponse> =>
    source === "student"
      ? getStudentTopicPerformance()
      : source === "parent"
        ? getParentTopicPerformance(studentId ?? 0)
        : getTeacherTopicPerformance(studentId ?? 0);
  const q = useQuery({ queryKey, queryFn: fetcher });
  const [open, setOpen] = React.useState<Set<number>>(new Set());

  if (q.isLoading) {
    return <div className="py-10 text-center text-sm text-muted-foreground">Yükleniyor…</div>;
  }
  if (q.isError || !q.data) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-muted-foreground">Veri yüklenemedi.</p>
        <button onClick={() => q.refetch()} className="mt-2 rounded-md bg-foreground px-4 py-1.5 text-sm font-medium text-background">
          Tekrar dene
        </button>
      </div>
    );
  }

  const { overall, subjects } = q.data;
  const who = audience === "parent" ? "Çocuğunuzun" : audience === "student" ? "Senin" : "Öğrencinin";

  if (subjects.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-center">
        <Target className="mx-auto mb-2 size-7 text-muted-foreground" aria-hidden />
        <p className="text-sm font-medium text-foreground">Henüz konu performansı yok</p>
        <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
          {audience === "student"
            ? "Test çözüp doğru/yanlış sayını girdikçe her dersin konularındaki performansın burada birikir."
            : `${who} çözdüğü testlerde doğru/yanlış girildikçe ders ve konu bazında performans burada görünür.`}
        </p>
      </div>
    );
  }

  function toggle(id: number) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      {source === "teacher" ? (
        <DemoHint contextKey="topic-performance" role="teacher" />
      ) : null}
      {/* Açıklama */}
      <div className="rounded-lg border border-border bg-muted/40 px-4 py-3">
        <p className="text-xs leading-relaxed text-muted-foreground">
          <span className="font-semibold text-foreground">Konu performansı</span> — her dersin konularında çözülen
          test sayısı ve doğru/yanlış oranı. <span className="font-medium">Doğruluk</span> = doğru ÷ (doğru+yanlış).
          Düşük doğruluklu konular (kırmızı) tekrar/pekiştirme ister.
        </p>
      </div>

      {/* Genel özet */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <SummaryCard label="Çözülen test" value={String(overall.tests_solved)} />
        <SummaryCard label="Doğru soru" value={String(overall.correct)} tone="emerald" />
        <SummaryCard label="Yanlış soru" value={String(overall.wrong)} tone="rose" />
        <SummaryCard
          label="Genel doğruluk"
          value={overall.accuracy_pct == null ? "—" : `%${overall.accuracy_pct}`}
          tone={overall.accuracy_pct == null ? undefined : overall.accuracy_pct >= 70 ? "emerald" : overall.accuracy_pct >= 40 ? "amber" : "rose"}
        />
      </div>

      {/* Ders kartları */}
      <div className="space-y-2">
        {subjects.map((s) => {
          const isOpen = open.has(s.subject_id);
          const t = accTone(s.accuracy_pct);
          return (
            <div key={s.subject_id} className="overflow-hidden rounded-xl border border-border bg-card">
              <button
                onClick={() => toggle(s.subject_id)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-muted/40"
              >
                <ChevronDown className={cn("size-4 shrink-0 text-muted-foreground transition-transform", isOpen && "rotate-180")} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground">{s.subject_name}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {s.tests_solved} test · {s.topics.length} konu · <span className="text-emerald-600">{s.correct}D</span> / <span className="text-rose-600">{s.wrong}Y</span>
                  </p>
                </div>
                <AccBadge pct={s.accuracy_pct} />
              </button>
              {/* Ders doğruluk barı */}
              {s.accuracy_pct != null ? (
                <div className="mx-4 mb-1 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className={cn("h-full rounded-full", t.bar)} style={{ width: `${s.accuracy_pct}%` }} />
                </div>
              ) : null}

              {isOpen ? (
                <div className="border-t border-border/60 px-2 py-2">
                  {s.topics.map((tp) => {
                    const tt = accTone(tp.accuracy_pct);
                    return (
                      <div key={`${tp.topic_id ?? "l"}-${tp.topic_name}`} className="rounded-lg px-2 py-2 hover:bg-muted/30">
                        <div className="flex items-center justify-between gap-2">
                          <p className="min-w-0 flex-1 truncate text-[13px] font-medium text-foreground">{tp.topic_name}</p>
                          <span className={cn("text-xs font-semibold", tt.text)}>
                            {tp.accuracy_pct == null ? "—" : `%${tp.accuracy_pct}`}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center gap-3 text-[11px] text-muted-foreground">
                          <span className="inline-flex items-center gap-0.5"><Target className="size-3" aria-hidden /> {tp.tests_solved} test</span>
                          <span className="inline-flex items-center gap-0.5 text-emerald-600"><CheckCircle2 className="size-3" aria-hidden /> {tp.correct}</span>
                          <span className="inline-flex items-center gap-0.5 text-rose-600"><XCircle className="size-3" aria-hidden /> {tp.wrong}</span>
                          {tp.last_solved_at ? <span className="ml-auto">son: {fmtDate(tp.last_solved_at)}</span> : null}
                        </div>
                        {tp.accuracy_pct != null ? (
                          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted">
                            <div className={cn("h-full rounded-full", tt.bar)} style={{ width: `${tp.accuracy_pct}%` }} />
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SummaryCard({ label, value, tone }: { label: string; value: string; tone?: "emerald" | "amber" | "rose" }) {
  const toneCls =
    tone === "emerald" ? "text-emerald-700" : tone === "amber" ? "text-amber-700" : tone === "rose" ? "text-rose-700" : "text-foreground";
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2.5">
      <p className={cn("text-xl font-bold tabular-nums", toneCls)}>{value}</p>
      <p className="text-[11px] text-muted-foreground">{label}</p>
    </div>
  );
}
