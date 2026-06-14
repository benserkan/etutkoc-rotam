"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Info,
  Moon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { QuickAccessStrip } from "@/components/quick-access-strip";
import { ShareExperiencePrompt } from "@/components/testimonials/share-experience-prompt";
import { Card, CardContent } from "@/components/ui/card";
import {
  getInstitutionDashboard,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  InstitutionDashboardResponse,
  TeacherSummaryItem,
} from "@/lib/types/institution";

interface Props {
  initial: InstitutionDashboardResponse;
}

/**
 * Kurum dashboard — Jinja `institution/dashboard.html` ile birebir fonksiyonel:
 *   - Gizlilik notu (sky-50, kaldırılamaz)
 *   - Risk + pasif öğretmen callout'ları (clickable)
 *   - 4 KPI kart (öğretmen / öğrenci / haftalık plan / oran)
 *   - Öğretmen tablosu (ad + öğrenci + plan + tamamlanan + oran + son giriş)
 */
export function DashboardClient({ initial }: Props) {
  const q = useQuery<InstitutionDashboardResponse>({
    queryKey: institutionKeys.dashboard(),
    queryFn: () => getInstitutionDashboard(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const { institution, aggregate, risk, inactive, teacher_summaries } = data;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          {institution.name}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Kurum genel durumu ve öğretmenlerin haftalık performansı.
        </p>
      </header>

      <QuickAccessStrip />

      <ShareExperiencePrompt />

      <PrivacyNote />

      {(risk.at_risk_count > 0 || inactive.inactive_teacher_count > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {risk.at_risk_count > 0 && (
            <RiskCallout
              count={risk.at_risk_count}
              critical={risk.at_risk_critical}
            />
          )}
          {inactive.inactive_teacher_count > 0 && (
            <InactiveCallout
              count={inactive.inactive_teacher_count}
              names={inactive.inactive_teacher_names}
            />
          )}
        </div>
      )}

      <KpiGrid aggregate={aggregate} />

      <TeachersTable summaries={teacher_summaries} />
    </div>
  );
}

function PrivacyNote() {
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50 text-sky-900 px-3 py-2.5 text-xs flex items-start gap-2">
      <Info className="size-4 shrink-0 mt-0.5" aria-hidden />
      <div>
        <strong>Gizlilik:</strong> Bu panelde öğretmenlerin programı, veli
        notları veya öğrenci detayları GÖRÜNMEZ — sadece roster ve agregat
        istatistikler. Detay verilerine erişim için öğretmenle doğrudan
        iletişime geçin.
      </div>
    </div>
  );
}

function RiskCallout({
  count,
  critical,
}: {
  count: number;
  critical: number;
}) {
  return (
    <Link
      href="/institution/at-risk"
      className="group block rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 hover:border-rose-400 hover:bg-rose-100/60 transition"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <AlertTriangle
            className="size-7 shrink-0 text-rose-600"
            aria-hidden
          />
          <div className="min-w-0">
            <div className="font-semibold text-rose-900">
              {count} öğrenci risk altında
            </div>
            <div className="text-xs text-rose-700 mt-0.5">
              {critical > 0 && (
                <>
                  <span className="inline-block mr-1">🔴</span>
                  {critical} kritik ·{" "}
                </>
              )}
              detayları görmek için tıkla
            </div>
          </div>
        </div>
        <ArrowRight
          className="size-5 shrink-0 text-rose-700 transition-transform group-hover:translate-x-0.5"
          aria-hidden
        />
      </div>
    </Link>
  );
}

function InactiveCallout({
  count,
  names,
}: {
  count: number;
  names: string[];
}) {
  const remaining = count - names.length;
  return (
    <Link
      href="/institution/activity-heatmap"
      className="group block rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 hover:border-amber-400 hover:bg-amber-100/60 transition"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <Moon className="size-7 shrink-0 text-amber-600" aria-hidden />
          <div className="min-w-0">
            <div className="font-semibold text-amber-900">
              {count} öğretmen 7+ gündür pasif
            </div>
            <div className="text-xs text-amber-700 mt-0.5 truncate">
              {names.join(" · ")}
              {remaining > 0 ? ` +${remaining} daha` : ""}
            </div>
          </div>
        </div>
        <ArrowRight
          className="size-5 shrink-0 text-amber-700 transition-transform group-hover:translate-x-0.5"
          aria-hidden
        />
      </div>
    </Link>
  );
}

function KpiGrid({
  aggregate,
}: {
  aggregate: InstitutionDashboardResponse["aggregate"];
}) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
      <KpiCard
        label="Öğretmen"
        value={aggregate.teacher_count}
        sub={`${aggregate.active_teacher_count} son 7 günde aktif (giriş yapan)`}
      />
      <KpiCard
        label="Öğrenci"
        value={aggregate.student_count}
        sub="aktif kayıt"
      />
      <KpiCard
        label="Planlanan test"
        value={aggregate.weekly_planned}
        sub={`${aggregate.weekly_completed} çözüldü · soru bankası · son 7 gün`}
      />
      <KpiCard
        label="Planlanan deneme"
        value={aggregate.weekly_deneme_planned}
        sub={`${aggregate.weekly_deneme_completed} çözüldü · branş/genel/tam · son 7 gün`}
      />
      <KpiCard
        label="Test tamamlama"
        value={
          aggregate.weekly_rate_pct == null
            ? "—"
            : `%${aggregate.weekly_rate_pct}`
        }
        sub="son 7 gün · yalnız test"
        valueClassName={rateColorClass(aggregate.weekly_rate_pct)}
      />
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  valueClassName,
}: {
  label: string;
  value: number | string;
  sub?: string;
  valueClassName?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div
          className={cn(
            "text-3xl font-semibold mt-1 tabular-nums",
            valueClassName,
          )}
        >
          {value}
        </div>
        {sub ? (
          <div className="text-[11px] text-muted-foreground mt-1">{sub}</div>
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

// Satır zemini — orana göre (koyu temada da okunur: saydam ton + sol şerit).
// Kurum yöneticisi koçun/sınıfın durumunu bir bakışta ayırt eder.
function rateRowClass(pct: number | null): string {
  if (pct == null) return "";
  if (pct >= 70) return "bg-emerald-500/10 border-l-4 border-l-emerald-500";
  if (pct >= 40) return "bg-amber-500/10 border-l-4 border-l-amber-500";
  return "bg-rose-500/10 border-l-4 border-l-rose-500";
}

function TeachersTable({
  summaries,
}: {
  summaries: TeacherSummaryItem[];
}) {
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-border">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h2 className="font-medium">Öğretmenler — Bu Haftaki Performans</h2>
          <span className="inline-flex items-center gap-2 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-rose-500" aria-hidden /> &lt;%40 acil
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-amber-500" aria-hidden /> %40–69 dikkat
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-emerald-500" aria-hidden /> ≥%70 yolunda
            </span>
          </span>
        </div>
        <Link
          href="/institution/teachers"
          className="text-xs text-accent hover:underline"
        >
          Yönet →
        </Link>
      </div>
      {summaries.length === 0 ? (
        <div className="px-4 py-12 text-center text-sm text-muted-foreground">
          Henüz kuruma bağlı öğretmen yok.{" "}
          <Link
            href="/institution/teachers"
            className="text-accent hover:underline"
          >
            Öğretmen ekle →
          </Link>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-muted-foreground text-xs">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Öğretmen</th>
                <th className="text-right px-4 py-2 font-medium">Öğrenci</th>
                <th className="text-right px-4 py-2 font-medium">Test plan</th>
                <th className="text-right px-4 py-2 font-medium">
                  Test çöz.
                </th>
                <th className="text-right px-4 py-2 font-medium">Deneme (çöz/plan)</th>
                <th className="text-right px-4 py-2 font-medium">Test oranı</th>
                <th className="text-right px-4 py-2 font-medium">Son Giriş</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {summaries.map((s) => (
                <tr
                  key={s.id}
                  className={cn(
                    s.is_active
                      ? rateRowClass(s.weekly_rate_pct)
                      : "bg-muted/30 text-muted-foreground opacity-70",
                  )}
                >
                  <td className="px-4 py-2">
                    <Link
                      href={`/institution/teachers/${s.id}`}
                      className="font-medium hover:text-accent hover:underline"
                    >
                      {s.full_name}
                    </Link>
                    {!s.is_active && (
                      <span className="ml-1.5 inline-flex items-center text-[10px] px-1.5 py-0.5 rounded bg-muted border border-border text-muted-foreground">
                        pasif
                      </span>
                    )}
                    <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
                      {s.email}
                    </div>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {s.student_count}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {s.weekly_planned}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {s.weekly_completed}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                    {s.weekly_deneme_planned > 0
                      ? `${s.weekly_deneme_completed}/${s.weekly_deneme_planned}`
                      : "—"}
                  </td>
                  <td
                    className={cn(
                      "px-4 py-2 text-right tabular-nums font-semibold",
                      rateColorClass(s.weekly_rate_pct),
                    )}
                  >
                    {s.weekly_rate_pct == null
                      ? "—"
                      : `%${s.weekly_rate_pct}`}
                  </td>
                  <td className="px-4 py-2 text-right text-xs text-muted-foreground">
                    {formatLastLogin(s.last_login_days)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function formatLastLogin(days: number | null): string {
  if (days == null) return "hiç";
  if (days === 0) return "bugün";
  if (days === 1) return "dün";
  return `${days} gün önce`;
}
