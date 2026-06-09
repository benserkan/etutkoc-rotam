"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";
import { Card } from "@/components/ui/card";
import { institutionKeys, getInstitutionCompliance } from "@/lib/api/institution";
import type {
  ComplianceTeacherRow,
  InstitutionComplianceResponse,
} from "@/lib/types/institution";

interface Props {
  initial: InstitutionComplianceResponse;
}

const RATE_TEXT: Record<string, string> = {
  emerald: "text-emerald-700",
  amber: "text-amber-700",
  rose: "text-rose-700",
  slate: "text-slate-500",
};
const RATE_BAR: Record<string, string> = {
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
  slate: "bg-slate-300",
};

function rateText(c: string): string {
  return RATE_TEXT[c] ?? RATE_TEXT.slate;
}
function rateBar(c: string): string {
  return RATE_BAR[c] ?? RATE_BAR.slate;
}
function pct(v: number | null): string {
  return v == null ? "—" : `%${v}`;
}
/** Büyük KPI değeri — null ise kocaman "—" yerine net "veri yok" gösterir. */
function BigPct({ v, className }: { v: number | null; className?: string }) {
  if (v == null) {
    return <div className="mt-1 text-base font-medium text-muted-foreground">veri yok</div>;
  }
  return <div className={cn("mt-1 text-3xl font-bold tabular-nums", className)}>%{v}</div>;
}
function weekShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(5);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function RateBar({ rate, color }: { rate: number | null; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 overflow-hidden rounded bg-slate-100">
        <div className={cn("h-full rounded", rateBar(color))} style={{ width: `${rate ?? 0}%` }} />
      </div>
      <span className={cn("w-9 text-right text-xs font-semibold tabular-nums", rateText(color))}>{pct(rate)}</span>
    </div>
  );
}

export function ComplianceClient({ initial }: Props) {
  const q = useQuery<InstitutionComplianceResponse>({
    queryKey: institutionKeys.compliance(8),
    queryFn: () => getInstitutionCompliance(8),
    initialData: initial,
    staleTime: 30_000,
  });
  const d = q.data ?? initial;
  const s = d.summary;

  const trendData = d.trend.map((t) => ({ label: weekShort(t.week_start), rate: t.rate ?? 0 }));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <ClipboardList className="size-6 text-indigo-700" aria-hidden />
          Program Uyumu
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Öğretmenlerin hazırladığı programlara öğrenci uyumu. Tamamlama = yapılan ÷
          planlanan soru; doğruluk = doğru ÷ (doğru+yanlış). Bu hafta:{" "}
          {weekShort(s.week_start)}–{weekShort(s.week_end)}.
        </p>
        <DemoHint contextKey="analysis" role="institution_admin" className="mt-2" />
      </header>

      {/* Kurum özeti KPI */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase text-muted-foreground">Tamamlama</span>
            {s.delta != null ? (
              <span className={cn("inline-flex items-center gap-0.5 text-[11px] font-medium",
                s.delta > 0 ? "text-emerald-600" : s.delta < 0 ? "text-rose-600" : "text-muted-foreground")}>
                {s.delta > 0 ? <TrendingUp className="size-3" aria-hidden /> : s.delta < 0 ? <TrendingDown className="size-3" aria-hidden /> : null}
                {s.delta > 0 ? "+" : ""}{s.delta}
              </span>
            ) : null}
          </div>
          <BigPct v={s.rate} className={rateText(s.rate_color)} />
          <div className="text-[11px] text-muted-foreground">geçen hafta {pct(s.last_week_rate)}</div>
        </Card>
        <Card className="p-4">
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            <Target className="size-3.5" aria-hidden /> Doğruluk
          </div>
          <BigPct v={s.accuracy} />
          <div className="text-[11px] text-muted-foreground">
            {s.accuracy == null
              ? "henüz doğru/yanlış girilmemiş"
              : "yapılan soruların doğruluğu"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] font-semibold uppercase text-muted-foreground">Soru (yapılan/planlanan)</div>
          <div className="mt-1 text-2xl font-bold tabular-nums">{s.completed.toLocaleString("tr-TR")}<span className="text-base text-muted-foreground"> / {s.planned.toLocaleString("tr-TR")}</span></div>
          <div className="text-[11px] text-muted-foreground">{s.student_count} aktif öğrenci</div>
        </Card>
        <Card className={cn("p-4", s.empty_count > 0 && "border-amber-300 bg-amber-50/40")}>
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            <AlertTriangle className="size-3.5" aria-hidden /> Boş Program
          </div>
          <div className={cn("mt-1 text-3xl font-bold tabular-nums", s.empty_count > 0 ? "text-amber-700" : "text-emerald-700")}>{s.empty_count}</div>
          <div className="text-[11px] text-muted-foreground">bu hafta program girilmemiş öğrenci</div>
        </Card>
      </section>

      {/* Trend */}
      <Card className="p-4">
        <h2 className="mb-3 inline-flex items-center gap-2 text-sm font-semibold">
          <TrendingUp className="size-4 text-indigo-600" aria-hidden /> Haftalık tamamlama trendi
        </h2>
        <div style={{ width: "100%", height: 200 }}>
          <ResponsiveContainer>
            <BarChart data={trendData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={{ stroke: "hsl(var(--border))" }} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} width={30} />
              <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.4)" }} contentStyle={{ fontSize: 12, borderRadius: 8 }} formatter={(v) => [`%${v}`, "Tamamlama"]} />
              <Bar dataKey="rate" fill="#6366f1" radius={[3, 3, 0, 0]} maxBarSize={36} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Öğretmen kırılımı */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-2.5">
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
            <Users className="size-4 text-indigo-600" aria-hidden /> Öğretmen kırılımı
          </h2>
          <p className="text-xs text-muted-foreground">En düşük tamamlama üstte. &quot;Boş&quot; = bu hafta program girilmemiş öğrenci.</p>
        </div>
        {d.teachers.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Veri yok.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr><th className="px-3 py-1.5 text-left">Koç</th><th className="px-3 py-1.5 text-right">Öğrenci</th><th className="px-3 py-1.5 text-left">Tamamlama</th><th className="px-3 py-1.5 text-right">Doğruluk</th><th className="px-3 py-1.5 text-right">Boş</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.teachers.map((t: ComplianceTeacherRow, i) => (
                  <tr key={t.teacher_id ?? `none-${i}`} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5 font-medium">{t.teacher_name}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">{t.student_count}</td>
                    <td className="px-3 py-1.5"><RateBar rate={t.rate} color={t.rate_color} /></td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">{pct(t.accuracy)}</td>
                    <td className="px-3 py-1.5 text-right">
                      {t.empty_students > 0 ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">{t.empty_students}</span>
                      ) : (
                        <span className="text-[11px] text-emerald-600">0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Öğrenci dikkat + boş program */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <AlertTriangle className="size-4 text-rose-600" aria-hidden /> En düşük uyumlu öğrenciler
            </h2>
          </div>
          {d.attention_students.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Programlı öğrenci yok.</p>
          ) : (
            <ul className="max-h-96 divide-y divide-border overflow-auto">
              {d.attention_students.map((st, i) => (
                <li key={i} className="flex items-center justify-between gap-3 px-4 py-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{st.student_name}</div>
                    <div className="text-[11px] text-muted-foreground">koç: {st.teacher_name}</div>
                  </div>
                  <RateBar rate={st.rate} color={st.rate_color} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <ClipboardList className="size-4 text-amber-600" aria-hidden /> Boş program (koç başına)
            </h2>
            <p className="text-xs text-muted-foreground">Bu hafta hiç program girilmemiş öğrenciler.</p>
          </div>
          {d.empty_program.length === 0 ? (
            <p className="flex items-center justify-center gap-2 p-6 text-center text-sm text-emerald-700">
              <CheckCircle2 className="size-5" aria-hidden /> Tüm öğrencilere program girilmiş.
            </p>
          ) : (
            <ul className="max-h-96 divide-y divide-border overflow-auto">
              {d.empty_program.map((e, i) => (
                <li key={e.teacher_id ?? `none-${i}`} className="px-4 py-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{e.teacher_name}</span>
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">{e.count} öğrenci</span>
                  </div>
                  <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{e.sample_students.join(", ")}{e.count > e.sample_students.length ? " …" : ""}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
