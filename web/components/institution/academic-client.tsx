"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ClipboardList,
  Info,
  LineChart as LineChartIcon,
  Minus,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";
import { Card } from "@/components/ui/card";
import { institutionKeys, getInstitutionAcademic } from "@/lib/api/institution";
import type {
  AcademicMoverRow,
  InstitutionAcademicResponse,
} from "@/lib/types/institution";

interface Props {
  initial: InstitutionAcademicResponse;
}

const PCT_TEXT: Record<string, string> = {
  emerald: "text-emerald-700",
  amber: "text-amber-700",
  rose: "text-rose-700",
  slate: "text-muted-foreground",
};

function pct(v: number | null): string {
  return v == null ? "—" : `%${v}`;
}

function formatTRDate(iso: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}.${y}`;
}

export function AcademicClient({ initial }: Props) {
  const q = useQuery<InstitutionAcademicResponse>({
    queryKey: institutionKeys.academic(8),
    queryFn: () => getInstitutionAcademic(8),
    initialData: initial,
    staleTime: 30_000,
  });
  const d = q.data ?? initial;
  const s = d.summary;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <LineChartIcon className="size-6 text-indigo-700" aria-hidden />
          Akademik Çıktı
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Öğretmenlerin girdiği deneme sonuçlarının kurum geneli özeti: kaç
          öğrenci deneme giriyor, gidişat nasıl, hangi koçun öğrencileri daha iyi
          sonuç alıyor, kim yükseliyor kim düşüyor.
        </p>
        <DemoHint contextKey="analysis" role="institution_admin" className="mt-2" />
      </header>

      {/* Sade dil notu — net başarı oranı nedir */}
      <Card className="border-sky-200 bg-sky-50/50 p-3 dark:bg-sky-500/10 dark:border-sky-500/30">
        <div className="flex items-start gap-2 text-sm text-sky-900">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p>
            <b>Net başarı oranı</b> = öğrencinin çıkardığı net ÷ sınavdaki soru
            sayısı (yüzde). Ham net sınava göre değişir (LGS ~90 soru, TYT 120);
            bu oran tüm sınav türlerini <b>karşılaştırılabilir</b> kılar.
            Örneğin 30 soruluk denemede 18 net = %60.
          </p>
        </div>
      </Card>

      {/* Özet KPI */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="p-4">
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            <Users className="size-3.5" aria-hidden /> Deneme kapsaması
          </div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{pct(s.coverage_pct)}</div>
          <div className="text-[11px] text-muted-foreground">
            {s.students_with_exam}/{s.total_students} öğrenci deneme girmiş
          </div>
        </Card>
        <Card className="p-4">
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            <ClipboardList className="size-3.5" aria-hidden /> Ortalama net başarı
          </div>
          <div className={cn("mt-1 text-3xl font-bold tabular-nums", PCT_TEXT[s.net_pct_color])}>
            {pct(s.avg_net_pct)}
          </div>
          <div className="text-[11px] text-muted-foreground">tüm denemelerin ortalaması</div>
        </Card>
        <Card className="p-4">
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            <ClipboardList className="size-3.5" aria-hidden /> Toplam deneme
          </div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{s.total_exams}</div>
          <div className="text-[11px] text-muted-foreground">son 30 günde {s.recent_exams} yeni</div>
        </Card>
        <Card className="p-4">
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            Gidişat
          </div>
          <DeltaValue delta={s.delta} />
          <div className="text-[11px] text-muted-foreground">son {s.weeks} hafta net başarı eğilimi</div>
        </Card>
      </section>

      {/* Haftalık trend */}
      {d.trend.some((t) => t.avg_net_pct != null) ? (
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold">Net Başarı Eğilimi (haftalık)</h2>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={d.trend.map((t) => ({
                  week: formatTRDate(t.week_start).slice(0, 5),
                  pct: t.avg_net_pct,
                  count: t.exam_count,
                }))}
                margin={{ top: 5, right: 8, bottom: 0, left: -20 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
                <Tooltip
                  formatter={(v) => [v == null ? "—" : `%${v}`, "Net başarı"]}
                  labelFormatter={(l, p) =>
                    `Hafta ${l} · ${p?.[0]?.payload?.count ?? 0} deneme`
                  }
                  contentStyle={{ fontSize: 12, borderRadius: 8 }}
                />
                <Line
                  type="monotone"
                  dataKey="pct"
                  stroke="#4f46e5"
                  strokeWidth={2}
                  connectNulls
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      ) : null}

      {/* Sınav türü kırılımı */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-2.5">
          <h2 className="text-sm font-semibold">Sınav türüne göre</h2>
          <p className="text-xs text-muted-foreground">
            Ham ortalama net kendi sınav türü içinde anlamlı; net başarı oranı
            türler arasında karşılaştırılabilir.
          </p>
        </div>
        {d.sections.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">
            Henüz deneme sonucu girilmemiş.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-1.5 text-left">Sınav türü</th>
                  <th className="px-3 py-1.5 text-right">Deneme</th>
                  <th className="px-3 py-1.5 text-right">Öğrenci</th>
                  <th className="px-3 py-1.5 text-right">Ort. net</th>
                  <th className="px-3 py-1.5 text-right">Net başarı</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.sections.map((sec) => (
                  <tr key={sec.section} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5 font-medium">{sec.section_label}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{sec.exam_count}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{sec.student_count}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{sec.avg_net.toFixed(2)}</td>
                    <td className={cn("px-3 py-1.5 text-right font-semibold tabular-nums", PCT_TEXT[sec.net_pct_color])}>
                      {pct(sec.avg_net_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Öğretmen kırılımı */}
      {d.teachers.length > 0 ? (
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="text-sm font-semibold">Koça göre</h2>
            <p className="text-xs text-muted-foreground">
              Deneme girilen öğrencilerin koç bazında net başarısı. En yüksek üstte.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-1.5 text-left">Koç</th>
                  <th className="px-3 py-1.5 text-right">Öğrenci</th>
                  <th className="px-3 py-1.5 text-right">Deneme</th>
                  <th className="px-3 py-1.5 text-right">Net başarı</th>
                  <th className="px-3 py-1.5 text-right">Son deneme</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.teachers.map((t) => (
                  <tr key={`${t.teacher_id}-${t.teacher_name}`} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5 font-medium">{t.teacher_name}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{t.student_count}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{t.exam_count}</td>
                    <td className={cn("px-3 py-1.5 text-right font-semibold tabular-nums", PCT_TEXT[t.net_pct_color])}>
                      {pct(t.avg_net_pct)}
                    </td>
                    <td className="px-3 py-1.5 text-right text-xs text-muted-foreground tabular-nums">
                      {formatTRDate(t.last_exam_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {/* Gelişen / Gerileyen */}
      {d.improving.length > 0 || d.declining.length > 0 ? (
        <section className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <MoverCard
            title="En çok gelişen"
            tone="emerald"
            rows={d.improving}
            emptyText="Henüz birden çok denemesi olan ve yükselen öğrenci yok."
          />
          <MoverCard
            title="En çok gerileyen"
            tone="rose"
            rows={d.declining}
            emptyText="Gerileyen öğrenci yok — güzel."
          />
        </section>
      ) : null}

      {/* Deneme girmeyen (kapsama eksiği) */}
      {d.no_exam_program.length > 0 ? (
        <Card className="overflow-hidden border-amber-300">
          <div className="border-b border-amber-200 bg-amber-50/50 px-4 py-2.5 dark:bg-amber-500/10 dark:border-amber-500/30">
            <h2 className="text-sm font-semibold text-amber-900">
              Deneme girilmeyen öğrenciler ({s.no_exam_count})
            </h2>
            <p className="text-xs text-amber-800">
              Koçları bu öğrencilerin deneme sonuçlarını girmeye teşvik edin —
              akademik gidişat ancak ölçülürse yönetilebilir.
            </p>
          </div>
          <ul className="divide-y divide-border">
            {d.no_exam_program.map((r) => (
              <li key={`${r.teacher_id}-${r.teacher_name}`} className="px-4 py-2 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{r.teacher_name}</span>
                  <span className="shrink-0 tabular-nums text-amber-700">{r.count} öğrenci</span>
                </div>
                {r.sample_students.length > 0 ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {r.sample_students.join(", ")}
                    {r.count > r.sample_students.length
                      ? ` +${r.count - r.sample_students.length} daha`
                      : ""}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}

function DeltaValue({ delta }: { delta: number | null }) {
  if (delta == null) {
    return (
      <div className="mt-1 inline-flex items-center gap-1 text-2xl font-bold text-muted-foreground">
        <Minus className="size-5" aria-hidden /> —
      </div>
    );
  }
  if (delta === 0) {
    return (
      <div className="mt-1 inline-flex items-center gap-1 text-2xl font-bold text-muted-foreground">
        <Minus className="size-5" aria-hidden /> 0
      </div>
    );
  }
  const up = delta > 0;
  return (
    <div
      className={cn(
        "mt-1 inline-flex items-center gap-1 text-2xl font-bold tabular-nums",
        up ? "text-emerald-700" : "text-rose-700",
      )}
    >
      {up ? <TrendingUp className="size-5" aria-hidden /> : <TrendingDown className="size-5" aria-hidden />}
      {up ? "+" : ""}
      {delta}
    </div>
  );
}

function MoverCard({
  title,
  tone,
  rows,
  emptyText,
}: {
  title: string;
  tone: "emerald" | "rose";
  rows: AcademicMoverRow[];
  emptyText: string;
}) {
  const toneText = tone === "emerald" ? "text-emerald-700" : "text-rose-700";
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-4 py-2.5">
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="text-xs text-muted-foreground">
          İlk → son deneme net başarı değişimi (en az 2 deneme).
        </p>
      </div>
      {rows.length === 0 ? (
        <p className="p-6 text-center text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <ul className="divide-y divide-border">
          {rows.map((m, i) => (
            <li key={i} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium">{m.student_name}</p>
                <p className="text-xs text-muted-foreground">
                  {m.teacher_name} · {m.exam_count} deneme
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className={cn("font-semibold tabular-nums", toneText)}>
                  {m.delta > 0 ? "+" : ""}
                  {m.delta} puan
                </p>
                <p className="text-xs text-muted-foreground tabular-nums">
                  %{m.first_net_pct} → %{m.last_net_pct}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
