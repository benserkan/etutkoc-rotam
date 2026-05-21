"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Loader2,
  Target,
  TriangleAlert,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminRevenueActionCenter } from "@/lib/api/admin";
import { useRevenueQuickAction } from "@/lib/hooks/use-admin-mutations";
import type {
  ActionCenterItem,
  ActionCenterResponse,
} from "@/lib/types/admin";
import {
  SeverityBadge,
  actionKindIcon,
  sevCard,
  sevHead,
  sevScore,
  severityTone,
  suggestBtnTone,
  tl,
} from "@/components/admin/revenue-ui";

interface Props {
  initial: ActionCenterResponse;
}

const SUMMARY_CARDS: { key: string; label: string; sub: string; tone: string }[] = [
  { key: "critical", label: "Kritik", sub: "acil müdahale", tone: "rose" },
  { key: "high", label: "Yüksek", sub: "bu hafta temas", tone: "amber" },
  { key: "medium", label: "Orta", sub: "izle / e-posta", tone: "slate" },
  { key: "positive", label: "Pozitif", sub: "memnuniyet / upsell", tone: "emerald" },
];

const CARD_TONE: Record<string, string> = {
  rose: "bg-rose-50 border-rose-200 text-rose-900",
  amber: "bg-amber-50 border-amber-200 text-amber-900",
  slate: "bg-slate-50 border-slate-200 text-slate-900",
  emerald: "bg-emerald-50 border-emerald-200 text-emerald-900",
  indigo: "bg-indigo-50 border-indigo-200 text-indigo-900",
};

export function AdminActionCenterClient({ initial }: Props) {
  const q = useQuery<ActionCenterResponse>({
    queryKey: adminKeys.revenueActionCenter(),
    queryFn: () => getAdminRevenueActionCenter(),
    initialData: initial,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;
  const sc = data.severity_counts;

  return (
    <div className="space-y-5">
      <header>
        <span className="text-sm text-muted-foreground">Ticari Pano</span>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Target className="size-6 text-indigo-700" aria-hidden />
          Aksiyon Merkezi — Bugün Ne Yapmalıyım?
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Tüm sinyaller tek listede: kritik kurumlar, denemesi bitenler, ödeme
          gecikenler. En yüksek puanlı sinyal başlık olur; önerilen aksiyonu tek
          tıkla başlatabilirsin.
        </p>
      </header>

      {/* Sayım kartları */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {SUMMARY_CARDS.map((c) => (
          <div key={c.key} className={cn("rounded-lg border p-3", CARD_TONE[c.tone])}>
            <div className="text-xs uppercase tracking-wide opacity-80">{c.label}</div>
            <div className="mt-1 text-2xl font-semibold">{sc[c.key] ?? 0}</div>
            <div className="text-[11px] opacity-70">{c.sub}</div>
          </div>
        ))}
        <div className={cn("rounded-lg border p-3", CARD_TONE.indigo)}>
          <div className="text-xs uppercase tracking-wide opacity-80">Toplam</div>
          <div className="mt-1 text-2xl font-semibold">{data.total_count}</div>
          <div className="text-[11px] opacity-70">kurum listede</div>
        </div>
      </div>

      {data.items.length === 0 ? (
        <Card className="p-12 text-center text-sm text-emerald-700">
          <CheckCircle2 className="mx-auto mb-2 size-8" aria-hidden />
          Tebrikler — bugün için açık aksiyon yok. Tüm kurumlar sağlıklı, ödemeler
          güncel, deneme alarmı yok.
        </Card>
      ) : (
        <div className="space-y-3">
          {data.items.map((it) => (
            <ActionRow key={it.institution_id} it={it} />
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Veri zamanı: {new Date(data.generated_at).toLocaleString("tr-TR")} · En fazla
        50 satır · Bir öneri butonuna basınca aksiyon &quot;Bekliyor + 3 gün
        takip&quot; olarak Kurum 360&apos;ta açılır.
      </p>
    </div>
  );
}

function ActionRow({ it }: { it: ActionCenterItem }) {
  const tone = severityTone(it.severity);
  const quick = useRevenueQuickAction();
  const [pendingKind, setPendingKind] = React.useState<string | null>(null);

  function runQuick(kind: string, summary: string) {
    setPendingKind(kind);
    quick.mutate(
      {
        institution_id: it.institution_id,
        kind,
        summary,
        result: "pending",
        follow_up_days: 3,
      },
      { onSettled: () => setPendingKind(null) },
    );
  }

  return (
    <Card className={cn("overflow-hidden", sevCard(tone))}>
      <div className={cn("flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3", sevHead(tone))}>
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <span className={cn("inline-flex size-12 items-center justify-center rounded-full text-sm font-bold", sevScore(tone))}>
            {it.total_score}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href={`/admin/revenue/institutions/${it.institution_id}`}
                className="inline-flex items-center gap-1 text-sm font-semibold hover:text-indigo-700"
              >
                <Building2 className="size-4 text-muted-foreground" aria-hidden />
                {it.institution_name}
              </Link>
              <SeverityBadge severity={it.severity} />
              <span className="text-[11px] text-muted-foreground">{it.plan_label}</span>
              {it.monthly_price_try > 0 ? (
                <span className="text-[11px] font-semibold text-emerald-700">
                  {tl(it.monthly_price_try)}/ay
                </span>
              ) : null}
            </div>
            <div className="mt-0.5 text-sm">{it.primary_signal.title}</div>
            {it.primary_signal.description ? (
              <div className="text-xs text-muted-foreground">{it.primary_signal.description}</div>
            ) : null}
          </div>
        </div>
      </div>

      {it.other_signals.length > 0 ? (
        <div className="border-b border-border bg-muted/30 px-4 py-2">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
            + {it.other_signals.length} başka sinyal
          </div>
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {it.other_signals.map((s, i) => (
              <li key={i}>
                · {s.title}
                {s.description ? <span className="opacity-70"> — {s.description}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="px-4 py-3">
        <div className="mb-2 text-[10px] uppercase tracking-wide text-muted-foreground">
          Önerilen aksiyonlar
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {it.suggested_actions.map((sa, i) => {
            const Icon = actionKindIcon(sa.kind);
            const isPending = quick.isPending && pendingKind === sa.kind;
            return (
              <button
                key={i}
                type="button"
                disabled={quick.isPending}
                onClick={() => runQuick(sa.kind, sa.summary)}
                title={`${sa.summary} (3 gün takip)`}
                className={cn(
                  "inline-flex items-center gap-1 rounded border px-2.5 py-1 text-xs font-medium disabled:opacity-50",
                  suggestBtnTone(sa.color),
                )}
              >
                {isPending ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                ) : (
                  <Icon className="size-3.5" aria-hidden />
                )}
                {sa.label}
              </button>
            );
          })}
          <Link
            href={`/admin/revenue/institutions/${it.institution_id}`}
            className="inline-flex items-center gap-0.5 rounded border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted"
          >
            Kurum 360 <ArrowRight className="size-3" aria-hidden />
          </Link>
        </div>
        {it.last_action_at ? (
          <div className="mt-2 text-[11px] text-muted-foreground">
            Son temas: {new Date(it.last_action_at).toLocaleString("tr-TR")}
            {it.last_action_summary ? ` — "${it.last_action_summary.slice(0, 80)}"` : ""}
          </div>
        ) : (
          <div className="mt-2 inline-flex items-center gap-1 text-[11px] text-amber-700">
            <TriangleAlert className="size-3.5" aria-hidden />
            Bu kuruma daha önce hiç temas edilmemiş.
          </div>
        )}
      </div>
    </Card>
  );
}
