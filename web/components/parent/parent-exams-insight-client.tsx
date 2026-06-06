"use client";

/**
 * Veli — deneme geçmişi + AI içgörü (P2). Üstte "çocuğum için analiz oluştur"
 * (Gemini, koçun kredisinden), altta tüm deneme geçmişi (net + D/Y + ders kırılımı).
 */
import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Sparkles, RefreshCw, TrendingUp, TrendingDown, Heart, Target, AlertCircle, MessageSquarePlus } from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  generateParentInsight,
  getParentExams,
  getParentInsight,
  parentP2Keys,
} from "@/lib/api/parent";
import { cn } from "@/lib/utils";

const SECTION_TONE: Record<string, string> = {
  lgs: "bg-cyan-50 text-cyan-700",
  tyt: "bg-violet-50 text-violet-700",
  ayt_say: "bg-emerald-50 text-emerald-700",
  ayt_ea: "bg-amber-50 text-amber-700",
  ayt_soz: "bg-rose-50 text-rose-700",
  ayt_dil: "bg-sky-50 text-sky-700",
};

export function ParentExamsInsightClient({ studentId, studentName }: { studentId: number; studentName?: string }) {
  const qc = useQueryClient();
  const examsQ = useQuery({ queryKey: parentP2Keys.exams(studentId), queryFn: () => getParentExams(studentId) });
  const insightQ = useQuery({ queryKey: parentP2Keys.insight(studentId), queryFn: () => getParentInsight(studentId) });

  const [genErr, setGenErr] = React.useState<string | null>(null);
  // setQueryData ile cache doğrudan güncellenir (yanıt yeni içgörüyü içerir) — invalidate gerekmez
  // eslint-disable-next-line lgs/missing-invalidate
  const genMut = useMutation({
    mutationFn: () => generateParentInsight(studentId),
    onMutate: () => setGenErr(null),
    onSuccess: (data) => qc.setQueryData(parentP2Keys.insight(studentId), data),
    onError: (e) => {
      const code = e instanceof ApiError ? (e.detail?.code ?? null) : null;
      if (code === "not_enough_data") setGenErr("Analiz için yeterli veri yok. Çocuğunuz test çözüp doğru/yanlış girdikçe veya deneme sonucu eklendikçe oluşturulabilir.");
      else if (code === "ai_credit_exhausted") setGenErr("Koçun yapay zekâ kredisi bu ay için dolmuş. Daha sonra tekrar deneyin.");
      else if (code === "ai_not_available") setGenErr(e instanceof ApiError ? e.message : "Yapay zekâ analizi şu an kullanılamıyor.");
      else if (code === "ai_unavailable") setGenErr("Yapay zekâ servisi şu an kullanılamıyor, birkaç dakika sonra deneyin.");
      else setGenErr(e instanceof ApiError ? e.message : "Analiz oluşturulamadı.");
    },
  });

  const insight = insightQ.data?.insight ?? null;
  const aiAvailable = insightQ.data?.ai_available ?? false;
  const isStale = insightQ.data?.is_stale ?? false;
  const reason = insightQ.data?.unavailable_reason ?? null;

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
      </div>

      {/* AI İçgörü */}
      <div className="rounded-2xl border border-violet-200 bg-violet-50/40 p-5">
        <div className="mb-2 flex items-center gap-2">
          <Sparkles className="size-5 text-violet-600" aria-hidden />
          <h2 className="text-base font-semibold text-violet-900">Yapay Zekâ Durum Analizi</h2>
        </div>

        {insightQ.isLoading ? (
          <p className="text-sm text-muted-foreground">Yükleniyor…</p>
        ) : insight ? (
          <div className="space-y-4">
            {isStale ? (
              <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                Bu analizden sonra yeni veri (deneme/çözülen test) eklendi. Güncel analiz için yenileyin.
              </div>
            ) : null}
            <p className="text-sm leading-relaxed text-slate-800">{insight.summary}</p>
            <InsightList icon={<Heart className="size-4 text-emerald-600" aria-hidden />} title="Güçlü yanlar" items={insight.strengths} />
            <InsightList icon={<Target className="size-4 text-amber-600" aria-hidden />} title="Gelişim alanları" items={insight.focus_areas} />
            <InsightList icon={<Sparkles className="size-4 text-violet-600" aria-hidden />} title="Evde nasıl destek olabilirsiniz" items={insight.parent_tips} />
            <div className="flex items-center justify-between border-t border-violet-100 pt-3">
              <p className="text-[11px] text-muted-foreground">Öneri amaçlıdır; kesin değerlendirme değildir.</p>
              {aiAvailable ? (
                <button onClick={() => genMut.mutate()} disabled={genMut.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-violet-300 px-3 py-1.5 text-sm font-semibold text-violet-700 hover:bg-violet-50 disabled:opacity-50">
                  <RefreshCw className={cn("size-3.5", genMut.isPending && "animate-spin")} aria-hidden />
                  {genMut.isPending ? "Yenileniyor…" : "Yenile"}
                </button>
              ) : null}
            </div>
          </div>
        ) : aiAvailable ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">
              Çocuğunuzun ders/konu performansı ve deneme sonuçlarından yapay zekâ ile sade bir durum analizi oluşturun.
            </p>
            <p className="text-[11px] text-muted-foreground">
              Bu analiz çocuğunuzun çalışma verilerini yapay zekâ ile işler. Sonucu yalnız siz görürsünüz.
            </p>
            <button onClick={() => genMut.mutate()} disabled={genMut.isPending}
              className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50">
              <Sparkles className="size-4" aria-hidden />
              {genMut.isPending ? "Oluşturuluyor…" : "Çocuğum için analiz oluştur"}
            </button>
          </div>
        ) : (
          <p className="text-sm text-slate-600">{reason ?? "Yapay zekâ analizi şu an kullanılamıyor."}</p>
        )}

        {genErr ? <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{genErr}</p> : null}
      </div>

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

function InsightList({ icon, title, items }: { icon: React.ReactNode; title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5">
        {icon}
        <p className="text-sm font-semibold text-slate-700">{title}</p>
      </div>
      <ul className="space-y-1">
        {items.map((s, i) => (
          <li key={i} className="flex gap-2 text-sm text-slate-700">
            <span className="text-slate-400">•</span>
            <span className="flex-1">{s}</span>
          </li>
        ))}
      </ul>
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
