"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownRight,
  ArrowUpRight,
  Mail,
  Minus,
  Moon,
  Trophy,
  Users,
} from "lucide-react";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";
import { ColumnHint } from "@/components/ui/column-hint";
import { Card, CardContent } from "@/components/ui/card";
import {
  getInstitutionAdminDigestDetail,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  AdminDigestCohortEntry,
  AdminDigestDetailResponse,
  AdminDigestPayload,
  AdminDigestPayloadCompletion,
} from "@/lib/types/institution";
import {
  SendStatusLabel,
  formatDateTime,
  formatRange,
} from "@/components/institution/admin-digest-list-client";

interface Props {
  initial: AdminDigestDetailResponse;
  digestId: number;
}

/**
 * Haftalık özet detayı — Jinja `admin_digest_detail.html` ile birebir.
 *
 * Payload yapısı `build_weekly_digest_payload` çıktısıyla aynı (totals,
 * completion, at_risk, highlight, inactive_teachers, grade_cohorts).
 */

const RATE_HINT =
  "Özetin kapsadığı 7 günde planlanan testlerden çözülenlerin oranı; yalnız yayınlanmış soru bankası testleri, deneme ve etkinlik görevleri hariç. Panel ve tüm sayfalarda aynı ölçü. Yeşil %70 ve üstü, sarı %40–69, kırmızı %40 altı.";

export function AdminDigestDetailClient({ initial, digestId }: Props) {
  const q = useQuery<AdminDigestDetailResponse>({
    queryKey: institutionKeys.adminDigest(digestId),
    queryFn: () => getInstitutionAdminDigestDetail(digestId),
    initialData: initial,
    staleTime: 60_000,
  });
  const data = q.data ?? initial;
  const { payload, recipient_emails } = data;

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/institution/admin-digest"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Arşiv
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
          {formatRange(data.week_start_date, data.week_end_date)}
        </h1>
        <p className="text-sm text-muted-foreground mt-1 flex flex-wrap items-center gap-x-2">
          <span>gönderim:</span>
          <span>
            {data.sent_at ? formatDateTime(data.sent_at) : "—"}
          </span>
          <span aria-hidden>·</span>
          <span className="inline-flex items-center gap-1">
            durum: <SendStatusLabel status={data.send_status} />
          </span>
          <span aria-hidden>·</span>
          <span>{data.recipient_count} alıcı</span>
        </p>
      </header>

      {payload == null ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Mail
              className="size-12 mx-auto text-muted-foreground mb-3"
              aria-hidden
            />
            <p className="text-sm text-muted-foreground">
              Bu haftanın detayları kaydedilmemiş.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <TotalsGrid payload={payload} />
          <CompletionCompareChart payload={payload} />
          <HighlightCard payload={payload} />
          <InactiveTeachersCard payload={payload} />
          <GradeCohortChart cohorts={payload.grade_cohorts} />
          <GradeCohortTable cohorts={payload.grade_cohorts} />
        </>
      )}

      {recipient_emails.length > 0 && (
        <RecipientsBlock
          count={data.recipient_count}
          emails={recipient_emails}
        />
      )}
    </div>
  );
}

function TotalsGrid({ payload }: { payload: AdminDigestPayload }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <KpiCard
        label="Öğretmen"
        info="Özetin hazırlandığı anda kuruma bağlı öğretmen sayısı. Pasif = 7 günden uzun süredir giriş, görev girme ya da veli notu gibi hiçbir hareketi olmayan öğretmen."
        value={payload.totals.teacher_count}
        warn={
          payload.totals.inactive_teacher_count > 0
            ? `${payload.totals.inactive_teacher_count} öğretmen 7+ gündür hareketsiz`
            : undefined
        }
      />
      <KpiCard
        label="Öğrenci"
        info="Özetin hazırlandığı anda kurumdaki aktif öğrenci sayısı (koçluğu sonlandırılanlar hariç)."
        value={payload.totals.student_count}
        sub="aktif öğrenci"
      />
      <CompletionKpi completion={payload.completion} />
      <RiskKpi atRisk={payload.at_risk} />
    </div>
  );
}

function KpiCard({
  label,
  info,
  value,
  sub,
  warn,
  valueClassName,
}: {
  label: string;
  info?: string;
  value: number | string;
  sub?: string;
  warn?: string;
  valueClassName?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {info ? <ColumnHint label={label} hint={info} /> : label}
        </div>
        <div
          className={cn(
            "text-3xl font-semibold mt-1 tabular-nums",
            valueClassName,
          )}
        >
          {value}
        </div>
        {warn ? (
          <div className="text-[11px] text-amber-700 dark:text-amber-300 mt-1">{warn}</div>
        ) : null}
        {sub ? (
          <div className="text-[11px] text-muted-foreground mt-1">{sub}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function CompletionKpi({
  completion,
}: {
  completion: AdminDigestPayloadCompletion;
}) {
  const rt = completion.this_week_rate;
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          <ColumnHint label="Tamamlama" hint={`${RATE_HINT} Alt satırdaki fark yüzde PUANdır (örneğin %50'den %60'a çıkış +10 puan).`} />
        </div>
        <div
          className={cn(
            "text-3xl font-semibold mt-1 tabular-nums",
            rt == null
              ? "text-muted-foreground"
              : rt >= 70
                ? "text-emerald-700"
                : rt >= 40
                  ? "text-amber-700"
                  : "text-rose-700",
          )}
        >
          {rt == null ? "—" : `%${rt}`}
        </div>
        {completion.delta_pct != null && (
          <div
            className={cn(
              "text-[11px] mt-1 inline-flex items-center gap-0.5 tabular-nums",
              completion.direction === "up"
                ? "text-emerald-700"
                : completion.direction === "down"
                  ? "text-rose-700"
                  : "text-muted-foreground",
            )}
          >
            {completion.direction === "up" && (
              <>
                <ArrowUpRight className="size-3.5" aria-hidden />+
                {Math.abs(completion.delta_pct)} puan
              </>
            )}
            {completion.direction === "down" && (
              <>
                <ArrowDownRight className="size-3.5" aria-hidden />−
                {Math.abs(completion.delta_pct)} puan
              </>
            )}
            {(completion.direction === "flat" ||
              completion.direction === "unknown") && (
              <>
                <Minus className="size-3.5" aria-hidden />
                {completion.direction === "flat" ? "stabil" : "—"}
              </>
            )}
            <span className="ml-1 text-muted-foreground">
              (önceki 7 güne göre)
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RiskKpi({
  atRisk,
}: {
  atRisk: AdminDigestPayload["at_risk"];
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          <ColumnHint label="Riskli öğrenci" hint="Risk puanı 30 ve üstü (Dikkat, Risk veya Kritik) olan öğrenci sayısı. Risk puanı; 5+ gün giriş yapmama, düşük haftalık tamamlama, üst üste boş günler, önceki haftaya göre düşüş ve programsızlıktan oluşur (0–100). Kritik = 80 ve üstü." />
        </div>
        <div
          className={cn(
            "text-3xl font-semibold mt-1 tabular-nums",
            atRisk.total > 0 ? "text-rose-700" : "text-emerald-700",
          )}
        >
          {atRisk.total}
        </div>
        {atRisk.critical > 0 ? (
          <div className="text-[11px] text-rose-700 mt-1 inline-flex items-center gap-1">
            {atRisk.critical} kritik
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function HighlightCard({ payload }: { payload: AdminDigestPayload }) {
  const { highlight } = payload;
  if (!highlight.best_grade_label && !highlight.worst_grade_label) return null;
  const sameTopBottom =
    highlight.best_grade_label != null &&
    highlight.best_grade_label === highlight.worst_grade_label;
  return (
    <Card>
      <CardContent className="p-4">
        <h3 className="text-sm font-medium mb-2 flex items-center gap-1.5">
          <Trophy className="size-4 text-amber-600" aria-hidden />
          Sınıf bazlı öne çıkanlar
        </h3>
        <div className="space-y-1 text-sm">
          {highlight.best_grade_label ? (
            <div>
              🏆 En yüksek tamamlama:{" "}
              <strong>{highlight.best_grade_label}</strong> —{" "}
              <span className="text-emerald-700 font-semibold tabular-nums">
                %{highlight.best_grade_rate}
              </span>
            </div>
          ) : null}
          {highlight.worst_grade_label && !sameTopBottom ? (
            <div>
              ⚠️ En düşük tamamlama:{" "}
              <strong>{highlight.worst_grade_label}</strong> —{" "}
              <span className="text-rose-700 font-semibold tabular-nums">
                %{highlight.worst_grade_rate}
              </span>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function InactiveTeachersCard({
  payload,
}: {
  payload: AdminDigestPayload;
}) {
  const { inactive_teachers, totals } = payload;
  if (inactive_teachers.length === 0) return null;
  const remaining = totals.inactive_teacher_count - inactive_teachers.length;
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 dark:bg-amber-500/10 dark:border-amber-500/30">
      <h3 className="text-sm font-medium text-amber-900 mb-2 flex items-center gap-1.5">
        <Moon className="size-4" aria-hidden />
        Son 7 gündür pasif öğretmenler
      </h3>
      <ul className="text-xs text-amber-800 space-y-1">
        {inactive_teachers.map((t) => (
          <li key={t.id}>
            {t.name}{" "}
            <span className="text-amber-700 font-mono">· {t.email}</span>
          </li>
        ))}
        {remaining > 0 && (
          <li className="italic">+{remaining} daha</li>
        )}
      </ul>
    </div>
  );
}

const RATE_HEX: Record<string, string> = {
  green: "#059669",
  amber: "#d97706",
  red: "#e11d48",
  slate: "#94a3b8",
};

function CompletionCompareChart({ payload }: { payload: AdminDigestPayload }) {
  const c = payload.completion;
  if (c.this_week_rate == null && c.last_week_rate == null) return null;
  const data = [
    { name: "Geçen hafta", rate: c.last_week_rate ?? 0 },
    { name: "Bu hafta", rate: c.this_week_rate ?? 0 },
  ];
  return (
    <Card>
      <div className="px-4 py-2 border-b border-border bg-muted/40">
        <h3 className="text-sm font-medium">Program tamamlama — haftalık karşılaştırma</h3>
      </div>
      <CardContent className="p-4">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
            <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
            <Bar dataKey="rate" name="Tamamlama %" radius={[4, 4, 0, 0]} barSize={64}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.rate >= 70 ? "#059669" : d.rate >= 40 ? "#d97706" : "#e11d48"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {c.delta_pct != null ? (
          <p className="mt-1 text-center text-xs text-muted-foreground">
            {c.direction === "up" ? `Geçen haftaya göre ${Math.abs(c.delta_pct)} puan yükseldi` :
             c.direction === "down" ? `Geçen haftaya göre ${Math.abs(c.delta_pct)} puan düştü` : "Geçen haftayla aynı seviyede"}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function GradeCohortChart({ cohorts }: { cohorts: AdminDigestCohortEntry[] }) {
  const data = cohorts.filter((c) => c.rate != null).map((c) => ({ name: c.label, rate: c.rate ?? 0, color: c.color }));
  if (data.length === 0) return null;
  return (
    <Card>
      <div className="px-4 py-2 border-b border-border bg-muted/40">
        <h3 className="text-sm font-medium inline-flex items-center gap-1.5">
          <Users className="size-4" aria-hidden /> Sınıf bazlı tamamlama (grafik)
        </h3>
      </div>
      <CardContent className="p-4">
        <ResponsiveContainer width="100%" height={Math.max(160, data.length * 34)}>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }}>
            <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
            <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 11 }} />
            <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
            <Bar dataKey="rate" name="Tamamlama %" radius={[0, 4, 4, 0]} barSize={18}>
              {data.map((d, i) => (
                <Cell key={i} fill={RATE_HEX[d.color] ?? "#94a3b8"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

function GradeCohortTable({
  cohorts,
}: {
  cohorts: AdminDigestCohortEntry[];
}) {
  if (cohorts.length === 0) return null;
  return (
    <Card>
      <div className="px-4 py-2 border-b border-border bg-muted/40">
        <h3 className="text-sm font-medium inline-flex items-center gap-1.5">
          <Users className="size-4" aria-hidden />
          Sınıf bazlı dağılım
        </h3>
      </div>
      <div className="relative overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/30 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Sınıf</th>
              <th className="text-right px-4 py-2 font-medium">
                <ColumnHint label="Öğrenci" hint="Bu sınıf düzeyindeki aktif öğrenci sayısı." />
              </th>
              <th className="text-right px-4 py-2 font-medium">
                <ColumnHint label="Tamamlama" hint={RATE_HINT} />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {cohorts.map((c) => (
              <tr key={c.label}>
                <td className="px-4 py-2 font-medium">{c.label}</td>
                <td className="px-4 py-2 text-right tabular-nums">{c.n}</td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {c.rate == null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <span
                      className={cn(
                        "font-semibold",
                        c.color === "green" && "text-emerald-700",
                        c.color === "amber" && "text-amber-700",
                        c.color === "red" && "text-rose-700",
                        c.color === "slate" && "text-muted-foreground",
                      )}
                    >
                      %{c.rate}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function RecipientsBlock({
  count,
  emails,
}: {
  count: number;
  emails: string[];
}) {
  return (
    <details className="rounded-md border border-border bg-muted/30 px-3 py-2.5 text-xs text-foreground/80">
      <summary className="cursor-pointer font-medium inline-flex items-center gap-1.5">
        <Mail className="size-3.5 inline-block" aria-hidden />
        Alıcılar ({count})
      </summary>
      <pre className="mt-2 font-mono text-xs whitespace-pre-wrap break-all">
        {emails.join(", ")}
      </pre>
    </details>
  );
}

