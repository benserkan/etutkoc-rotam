"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Gauge,
  Info,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { institutionPlanLabel } from "@/lib/institution-plans";
import { Card, CardContent } from "@/components/ui/card";
import {
  getInstitutionQuota,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  PlanQuotaItem,
  QuotaInfoItem,
  QuotaResponse,
} from "@/lib/types/institution";

interface Props {
  initial: QuotaResponse;
}

/**
 * Kurum kuotaları — Jinja `quota_dashboard.html` feature parity.
 *
 * 3 quota_key (teachers/students/institution_admins) için ayrı kartlar,
 * her birinde aktif sayım / limit / progress + warn/at_limit rozetleri.
 * Override badge "size özel" — backend has_override+override_note.
 * Plan karşılaştırma tablosu altta — mevcut plan satırı emerald-ile vurgulu.
 */
export function QuotaClient({ initial }: Props) {
  const q = useQuery<QuotaResponse>({
    queryKey: institutionKeys.quota(),
    queryFn: () => getInstitutionQuota(),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const { institution, plan, summary, plans } = data;

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/institution"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <p className="text-[11px] uppercase tracking-wider text-emerald-700 mt-1 font-semibold">
          Üyelik
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-0.5 flex items-center gap-2">
          <Gauge className="size-6 text-emerald-700" aria-hidden />
          Kurum Limitleri
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          {institution.name} kurumunda planınıza göre en fazla kaç öğretmen,
          öğrenci ve yönetici olabilir. Aktif olarak şu an kaç tane var, ne
          kadar yer kalmış aşağıda görürsünüz. Plan:{" "}
          <strong className="text-foreground">{institutionPlanLabel(plan)}</strong>
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {summary.map((item) => (
          <QuotaCard key={item.key} item={item} />
        ))}
      </div>

      <PlanComparison plans={plans} summary={summary} currentPlan={plan} />

      <HelpBlock />
    </div>
  );
}

// ============================================================================
// Tek bir kuota kartı
// ============================================================================

function QuotaCard({ item }: { item: QuotaInfoItem }) {
  const borderClass = item.is_at_limit
    ? "border-rose-300"
    : item.is_warn
      ? "border-amber-300"
      : "border-border";
  const barClass = item.is_at_limit
    ? "bg-rose-500"
    : item.is_warn
      ? "bg-amber-500"
      : "bg-emerald-500";
  const limitDisplay = item.is_unlimited
    ? "∞ sınırsız"
    : item.limit === 0
      ? "KAPALI"
      : item.limit;
  const pct = Math.min(100, Math.max(0, item.pct));
  return (
    <Card className={cn("transition-shadow", borderClass)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <h3 className="text-sm font-medium text-foreground">{item.label}</h3>
          {item.has_override && (
            <span
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-violet-50 text-violet-700 border border-violet-200"
              title={
                item.override_note ??
                "ETÜTKOÇ ekibi tarafından kuruma özel limit verilmiş"
              }
            >
              <Sparkles className="size-2.5" aria-hidden />
              size özel
            </span>
          )}
        </div>

        <div className="flex items-baseline gap-2 mt-2">
          <span className="text-3xl font-bold tabular-nums">{item.current}</span>
          <span className="text-base text-muted-foreground">
            / {limitDisplay}
          </span>
        </div>

        {!item.is_unlimited && item.limit > 0 && (
          <>
            <div className="w-full h-2 bg-muted rounded-full mt-3 overflow-hidden">
              <div
                className={cn("h-full", barClass)}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="text-[11px] text-muted-foreground mt-1 flex flex-wrap items-center gap-1">
              <span className="tabular-nums">%{item.pct} dolu</span>
              {item.is_at_limit && (
                <span className="text-rose-700 font-medium inline-flex items-center gap-1">
                  <AlertTriangle className="size-3" aria-hidden />
                  Limit doldu, yeni ekleyemezsin
                </span>
              )}
              {item.is_warn && !item.is_at_limit && (
                <span className="text-amber-700 font-medium inline-flex items-center gap-1">
                  <AlertTriangle className="size-3" aria-hidden />
                  limite yaklaşıyor
                </span>
              )}
            </div>
          </>
        )}

        {item.is_unlimited && (
          <div className="text-[11px] text-emerald-700 mt-3 inline-flex items-center gap-1">
            <CheckCircle2 className="size-3" aria-hidden />
            Sınırsız — bu kuotada yer sıkıntısı yok
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Plan karşılaştırma tablosu
// ============================================================================

function PlanComparison({
  plans,
  summary,
  currentPlan,
}: {
  plans: PlanQuotaItem[];
  summary: QuotaInfoItem[];
  currentPlan: string;
}) {
  const keys = summary.map((s) => s.key);
  function valueFor(plan: PlanQuotaItem, key: string): string {
    const v = plan[key as keyof PlanQuotaItem];
    if (typeof v !== "number") return "—";
    if (v === -1) return "∞";
    if (v === 0) return "—";
    return String(v);
  }
  return (
    <Card>
      <div className="px-4 py-2.5 border-b border-border bg-muted/40">
        <h3 className="text-sm font-medium flex items-center gap-1.5">
          <Info className="size-4 text-muted-foreground" aria-hidden />
          Planlara göre standart limitler
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/30 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Plan</th>
              {summary.map((s) => (
                <th key={s.key} className="text-right px-4 py-2 font-medium">
                  {s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {plans.map((p) => {
              const isCurrent = p.plan === currentPlan;
              return (
                <tr
                  key={p.plan}
                  className={cn(
                    isCurrent ? "bg-emerald-50/50 font-medium" : undefined,
                  )}
                >
                  <td className="px-4 py-2">
                    {institutionPlanLabel(p.plan)}
                    {isCurrent && (
                      <span className="ml-2 text-[11px] inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 border border-emerald-200">
                        <CheckCircle2 className="size-2.5" aria-hidden />
                        sizin planınız
                      </span>
                    )}
                  </td>
                  {keys.map((key) => (
                    <td
                      key={key}
                      className="px-4 py-2 text-right font-mono tabular-nums"
                    >
                      {valueFor(p, key)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ============================================================================
// Bilgilendirme
// ============================================================================

function HelpBlock() {
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50 text-sky-900 px-4 py-3 text-xs space-y-2">
      <p className="flex items-start gap-2">
        <Info className="size-4 shrink-0 mt-0.5" aria-hidden />
        <span>
          <strong>Sayım nasıl yapılır?</strong> Sadece <b>aktif</b> (kullanımda
          olan) kullanıcılar limite dahildir. Bir öğrenciyi/öğretmeni
          &ldquo;pasife&rdquo; çekerseniz yer açılır — kayıt korunur ama
          sayılmaz.
        </span>
      </p>
      <p className="flex items-start gap-2">
        <ShieldAlert className="size-4 shrink-0 mt-0.5" aria-hidden />
        <span>
          <strong>Limit dolduğunda ne olur?</strong> Yeni öğrenci/öğretmen
          ekleyemezsiniz. İki seçenek vardır: artık aktif olmayan kullanıcıları
          pasif yapın veya planı yükseltin.
        </span>
      </p>
    </div>
  );
}
