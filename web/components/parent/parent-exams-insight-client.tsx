"use client";

/**
 * Veli — deneme geçmişi (net + D/Y + ders kırılımı).
 *
 * Eski "AI Durum Analizi" kartı Rota'nın Yorumu'na GÖMÜLDÜ (2026-07-26):
 * tek kapı çocuk detay sayfasındaki RotaCommentaryCard — burada yalnız
 * yönlendirme kutusu kalır.
 */
import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Sparkles, TrendingUp, TrendingDown, MessageSquarePlus } from "lucide-react";

import { getParentExams, parentP2Keys } from "@/lib/api/parent";
import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";

const SECTION_TONE: Record<string, string> = {
  lgs: "bg-cyan-50 text-cyan-700",
  tyt: "bg-violet-50 text-violet-700",
  ayt_say: "bg-emerald-50 text-emerald-700",
  ayt_ea: "bg-amber-50 text-amber-700",
  ayt_soz: "bg-rose-50 text-rose-700",
  ayt_dil: "bg-sky-50 text-sky-700",
  okul: "bg-slate-100 text-slate-700",
};

export function ParentExamsInsightClient({ studentId, studentName }: { studentId: number; studentName?: string }) {
  const examsQ = useQuery({ queryKey: parentP2Keys.exams(studentId), queryFn: () => getParentExams(studentId) });

  const exams = examsQ.data;

  return (
    <div className="space-y-5">
      <div>
        <Link href={`/parent/students/${studentId}`} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3.5" aria-hidden /> Geri
        </Link>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight font-display">Denemeler & Analiz</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {studentName ? `${studentName} için ` : ""}deneme geçmişi ve yapay zekâ destekli durum analizi.
        </p>
        <DemoHint contextKey="ai-insight" role="parent" className="mt-2" />
      </div>

      {/* Rota'nın Yorumu'na yönlendirme — eski AI kartı oraya gömüldü */}
      <Link
        href={`/parent/students/${studentId}`}
        className="flex items-center gap-3 rounded-2xl border border-cyan-200 bg-cyan-50/40 p-4 hover:bg-cyan-50 dark:border-cyan-500/30 dark:bg-cyan-500/10"
      >
        <Sparkles className="size-5 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
        <span className="text-sm text-cyan-950 dark:text-cyan-100">
          <span className="font-semibold">Rota&apos;nın Yorumu</span> — deneme
          sonuçlarının yapay zekâ anlatımı artık çocuğunun sayfasında; okuyabilir
          ya da sesli dinleyebilirsin.
        </span>
      </Link>

      {/* Deneme geçmişi */}
      <div>
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-foreground">Deneme Geçmişi</h2>
          <Link
            href={`/parent/support?child=${studentId}&category=exam_comment`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#117A86]/40 px-3 py-1.5 text-xs font-semibold text-[#117A86] hover:bg-[#117A86]/5"
          >
            <MessageSquarePlus className="size-3.5" aria-hidden /> Koça deneme hakkında sor
          </Link>
        </div>
        {examsQ.isLoading ? (
          <p className="text-sm text-muted-foreground">Yükleniyor…</p>
        ) : !exams || exams.rows.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
            Henüz deneme sonucu girilmemiş.
          </div>
        ) : (
          <>
            <div className="mb-3 grid grid-cols-3 gap-2">
              <Stat label="Deneme" value={String(exams.summary.count)} />
              <Stat label="Ortalama net" value={String(exams.summary.avg_net)} />
              <Stat label="En iyi net" value={String(exams.summary.best_net)} />
            </div>
            <div className="space-y-2">
              {exams.rows.map((e) => (
                <div key={e.id} className="rounded-xl border border-border bg-card p-4">
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 flex-1 text-sm font-semibold text-foreground">{e.title}</p>
                    <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", SECTION_TONE[e.section] ?? "bg-muted text-muted-foreground")}>
                      {e.section_label}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{e.exam_date}</p>
                  <div className="mt-2 flex items-end justify-between">
                    <div>
                      <p className="text-2xl font-extrabold text-foreground">{e.net}</p>
                      <p className="text-[11px] text-muted-foreground">net</p>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      <span className="font-semibold text-emerald-600">D {e.total_correct}</span>{"  "}
                      <span className="font-semibold text-rose-600">Y {e.total_wrong}</span>{"  "}
                      <span>B {e.total_blank}</span>
                    </p>
                  </div>
                  {e.subjects && e.subjects.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5 border-t border-border/60 pt-2">
                      {e.subjects.map((s, i) => (
                        <span key={i} className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                          {s.name}: <span className="font-semibold text-foreground">{s.net}</span>
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
            {exams.summary.trend_delta != null ? (
              <div className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-muted px-3 py-1.5 text-xs">
                {exams.summary.trend_delta >= 0 ? <TrendingUp className="size-3.5 text-emerald-600" aria-hidden /> : <TrendingDown className="size-3.5 text-rose-600" aria-hidden />}
                <span className={cn("font-semibold", exams.summary.trend_delta >= 0 ? "text-emerald-700" : "text-rose-700")}>
                  İlk denemeden bu yana {exams.summary.trend_delta >= 0 ? "+" : ""}{exams.summary.trend_delta} net
                </span>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2.5 text-center">
      <p className="text-xl font-bold text-foreground">{value}</p>
      <p className="text-[11px] text-muted-foreground">{label}</p>
    </div>
  );
}
