"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, ChevronDown, ClipboardCheck, Plus, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { FollowUpFormDialog } from "@/components/admin/follow-ups/follow-up-form-dialog";
import {
  deltaTone,
  fmtDate,
  fmtDelta,
  fmtValue,
  Sparkline,
} from "@/components/admin/follow-ups/shared";
import { cn } from "@/lib/utils";
import { followUpKeys, getFollowUps, getMetricDetail, getMetrics, metricKeys } from "@/lib/api/follow-ups";
import { useCollectMetrics } from "@/lib/hooks/use-follow-up-mutations";
import type { MetricSummary, MetricsResponse } from "@/lib/types/follow-ups";

export function MetricsClient({ initial }: { initial: MetricsResponse }) {
  const q = useQuery({ queryKey: metricKeys.list(), queryFn: getMetrics, initialData: initial });
  const data = q.data ?? initial;
  const collect = useCollectMetrics();
  const [presetMetric, setPresetMetric] = React.useState<string | null>(null);
  // Takip ekleme penceresi meta'yı (kategori/ölçü listesi) takip ucundan alır
  const fu = useQuery({
    queryKey: followUpKeys.list("open"),
    queryFn: () => getFollowUps("open"),
    enabled: presetMetric !== null,
  });

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-cyan-100 text-cyan-800">
              <BarChart3 className="size-5" aria-hidden />
            </span>
            <div>
              <h1 className="text-lg font-semibold">Ölçümler</h1>
              <p className="mt-0.5 max-w-2xl text-sm text-muted-foreground">
                Önemli ölçüler her gece 05:30&apos;da (TR) kendiliğinden kaydedilir; geçmiş birikir.
                Bir ölçünün haftalar içindeki gidişini görmek için kimsenin betik koşmasına gerek yok.
                Bir ölçüye &quot;takip ekle&quot; dersen vade günü sistem değişimi hesaplayıp sana bildirir.
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {data.history_since
                  ? `Geçmiş ${fmtDate(data.history_since)} tarihinden beri birikiyor.`
                  : "Henüz ölçüm yok — ilk ölçüm bu gece alınacak (ya da şimdi al)."}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/admin/follow-ups">
                <ClipboardCheck className="size-4" aria-hidden />
                Takip listesi
              </Link>
            </Button>
            <Button size="sm" variant="outline" disabled={collect.isPending} onClick={() => collect.mutate()}>
              <RefreshCw className={cn("size-4", collect.isPending && "animate-spin")} aria-hidden />
              Şimdi ölç
            </Button>
          </div>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {data.metrics.map((m) => (
          <MetricCard key={m.key} m={m} onAddFollowUp={() => setPresetMetric(m.key)} />
        ))}
      </div>

      {fu.data ? (
        <FollowUpFormDialog
          key={presetMetric ?? "none"}
          open={presetMetric !== null}
          onOpenChange={(v) => !v && setPresetMetric(null)}
          meta={fu.data.meta}
          presetMetric={presetMetric ?? undefined}
        />
      ) : null}
    </div>
  );
}

function MetricCard({ m, onAddFollowUp }: { m: MetricSummary; onAddFollowUp: () => void }) {
  const [open, setOpen] = React.useState(false);
  const hasCoach = m.owners.includes("coach");
  return (
    <article className="rounded-xl border border-border bg-card p-4" data-metric={m.key}>
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1 basis-64">
          <h2 className="font-semibold">{m.label}</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">{m.description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-5">
          <div>
            <div className="text-xs text-muted-foreground">Son değer (sistem geneli)</div>
            <div className="text-2xl font-semibold tabular-nums">{fmtValue(m.latest_value, m.unit)}</div>
            <div className="text-xs text-muted-foreground">
              {m.latest_on ? fmtDate(m.latest_on) : "ölçüm yok"}
              {m.sample_n ? ` · ${m.sample_n} örnek` : ""}
            </div>
          </div>
          <div className="text-sm">
            <div className="text-xs text-muted-foreground">7 gün önceye göre</div>
            <div className={cn("font-semibold tabular-nums", deltaTone(m.delta_7d, m.higher_is_better))}>
              {fmtDelta(m.delta_7d, m.unit)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">30 gün önceye göre</div>
            <div className={cn("font-semibold tabular-nums", deltaTone(m.delta_30d, m.higher_is_better))}>
              {fmtDelta(m.delta_30d, m.unit)}
            </div>
          </div>
          <div>
            <div className="mb-1 text-xs text-muted-foreground">Son 60 gün</div>
            <Sparkline points={m.points} width={140} height={36} />
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {hasCoach ? (
          <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>
            <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} aria-hidden />
            Koç kırılımı ({m.coach_count})
          </Button>
        ) : null}
        <Button size="sm" variant="outline" onClick={onAddFollowUp}>
          <Plus className="size-4" aria-hidden />
          Takip ekle
        </Button>
        {m.min_sample > 0 ? (
          <span className="text-xs text-muted-foreground">
            {m.min_sample} örneğin altındaki değerler soluk gösterilir, karara katılmaz.
          </span>
        ) : null}
      </div>
      {open ? <MetricDetail metricKey={m.key} unit={m.unit} higherIsBetter={m.higher_is_better} /> : null}
    </article>
  );
}

function MetricDetail({ metricKey, unit, higherIsBetter }: { metricKey: string; unit: string; higherIsBetter: boolean }) {
  const q = useQuery({ queryKey: metricKeys.detail(metricKey, 90), queryFn: () => getMetricDetail(metricKey, 90) });
  if (!q.data) return <p className="mt-3 text-sm text-muted-foreground">Yükleniyor…</p>;
  const coaches = q.data.owners.filter((o) => o.owner_type === "coach");
  return (
    <div className="mt-3">
      {q.data.linked_follow_ups.length ? (
        <p className="mb-2 text-xs text-slate-700">
          Bu ölçüye bağlı açık takip:{" "}
          {q.data.linked_follow_ups.map((f, i) => (
            <span key={f.id}>
              {i ? ", " : ""}
              <Link href="/admin/follow-ups" className="font-medium text-cyan-800 underline">{f.title}</Link>
              {` (${fmtDate(f.effective_due)})`}
            </span>
          ))}
        </p>
      ) : null}
      {coaches.length === 0 ? (
        <p className="text-sm text-muted-foreground">Koç bazında ölçüm yok.</p>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-1.5 pr-3 font-medium">Koç</th>
                <th className="py-1.5 pr-3 font-medium">Son değer</th>
                <th className="py-1.5 pr-3 font-medium">3 hafta önceye göre</th>
                <th className="py-1.5 pr-3 font-medium">Örnek</th>
                <th className="py-1.5 font-medium">Son 90 gün</th>
              </tr>
            </thead>
            <tbody>
              {coaches.map((o) => (
                <tr key={o.owner_id} className={cn("border-t border-border", !o.enough_sample && "text-slate-500")}>
                  <td className="py-2 pr-3">
                    <Link href={`/admin/users/${o.owner_id}`} className="hover:underline">{o.owner_label}</Link>
                  </td>
                  <td className="py-2 pr-3 font-semibold tabular-nums">{fmtValue(o.latest_value, unit)}</td>
                  <td className={cn("py-2 pr-3 tabular-nums", o.enough_sample && deltaTone(o.delta_21d, higherIsBetter))}>
                    {fmtDelta(o.delta_21d, unit)}
                  </td>
                  <td className="py-2 pr-3 tabular-nums">
                    {o.sample_n ?? "—"}
                    {!o.enough_sample ? <span className="ml-1 text-xs">(az)</span> : null}
                  </td>
                  <td className="py-2"><Sparkline points={o.points} width={110} height={26} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
