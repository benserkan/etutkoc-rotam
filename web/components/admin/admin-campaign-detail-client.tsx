"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Ban,
  Building2,
  CheckSquare,
  ExternalLink,
  Loader2,
  Pause,
  Play,
  Rocket,
  Trophy,
  UserRound,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminCampaign } from "@/lib/api/admin";
import {
  useCancelCampaign,
  useCompleteCampaign,
  useLaunchCampaign,
  usePauseCampaign,
  useResumeCampaign,
} from "@/lib/hooks/use-admin-mutations";
import type {
  CampaignDetailResponse,
  CampaignFunnel,
} from "@/lib/types/admin";
import { StatusBadge } from "@/components/admin/feature-catalog-ui";
import { badge } from "@/components/admin/revenue-360-shared";

interface Props {
  initial: CampaignDetailResponse;
  campaignId: number;
}

const RECIP_TONE: Record<string, string> = {
  accepted: "emerald",
  declined: "rose",
  expired: "amber",
  sent: "blue",
  targeted: "slate",
  bounced: "rose",
};

function fmt(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("tr-TR");
  } catch {
    return iso.slice(0, 16);
  }
}

export function AdminCampaignDetailClient({ initial, campaignId }: Props) {
  const q = useQuery<CampaignDetailResponse>({
    queryKey: adminKeys.revenueCampaign(campaignId),
    queryFn: () => getAdminCampaign(campaignId),
    initialData: initial,
    staleTime: 10_000,
  });
  const d = q.data ?? initial;
  const c = d.campaign;
  const ov = d.stats.overall;

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link href="/admin/revenue/campaigns" className="text-sm text-muted-foreground hover:text-foreground">
            ← Kampanyalar
          </Link>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight">{c.name}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
            <StatusBadge label={c.status_label} tone={c.status_color} />
            <span className="text-muted-foreground">{c.segment_label}</span>
            {c.has_variant_b ? (
              <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700">A/B</span>
            ) : null}
          </div>
          {c.description ? <div className="mt-2 text-sm text-muted-foreground">{c.description}</div> : null}
        </div>
        <LifecycleButtons campaignId={campaignId} status={c.status} total={ov.total} />
      </header>

      {/* Funnel */}
      <section>
        <h2 className="mb-2 text-base font-semibold">Funnel — Genel</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <FunnelKpi label="Hedef" value={ov.total} tone="slate" />
          <FunnelKpi label="Gönderildi" value={ov.sent_total} tone="blue" />
          <FunnelKpi label="Kabul" value={ov.accepted} tone="emerald" />
          <FunnelKpi label="Ret" value={ov.declined} tone="rose" />
          <FunnelKpi label="Süresi Doldu" value={ov.expired} tone="amber" />
          <FunnelKpi
            label="Dönüşüm"
            value={ov.accepted_pct != null ? `%${ov.accepted_pct}` : "—"}
            tone="indigo"
            sub="kabul / gönderim"
          />
        </div>
      </section>

      {/* A/B karşılaştırma veya tek varyant */}
      {c.has_variant_b && d.stats.variant_b ? (
        <section>
          <h2 className="mb-2 text-base font-semibold">A/B Karşılaştırma</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <VariantCard title="Varyant A" name={c.variant_a.title} kindLabel={c.variant_a.kind_label} funnel={d.stats.variant_a} tone="indigo" />
            <VariantCard title="Varyant B" name={c.variant_b?.title ?? ""} kindLabel={c.variant_b?.kind_label ?? ""} funnel={d.stats.variant_b} tone="purple" />
          </div>
          <WinnerBanner a={d.stats.variant_a} b={d.stats.variant_b} />
        </section>
      ) : (
        <section>
          <h2 className="mb-2 text-base font-semibold">Teklif Detayı</h2>
          <Card className="p-4">
            <div className="text-xs uppercase text-muted-foreground">Başlık</div>
            <div className="text-base font-semibold">{c.variant_a.title}</div>
            <div className="mt-1 text-xs text-muted-foreground">{c.variant_a.kind_label}</div>
            {c.variant_a.public_message ? (
              <div className="mt-3 rounded bg-muted/50 px-3 py-2 text-sm italic text-muted-foreground">
                &ldquo;{c.variant_a.public_message}&rdquo;
              </div>
            ) : null}
          </Card>
        </section>
      )}

      {/* Recipient listesi */}
      <section>
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <h2 className="text-base font-semibold">Hedefler ({d.recipients.length})</h2>
          {d.stats.institution_count || d.stats.user_count ? (
            <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-0.5"><Building2 className="size-3.5" aria-hidden />{d.stats.institution_count}</span>
              <span className="inline-flex items-center gap-0.5"><UserRound className="size-3.5" aria-hidden />{d.stats.user_count}</span>
            </div>
          ) : null}
        </div>
        {d.recipients.length === 0 ? (
          <Card className="p-10 text-center text-sm text-muted-foreground">
            {c.status === "draft"
              ? "Kampanya henüz başlatılmadı — başlattıktan sonra hedefler burada listelenir."
              : "Bu kampanyada recipient yok."}
          </Card>
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Hedef</th>
                    <th className="px-4 py-2 text-center font-medium">Varyant</th>
                    <th className="px-4 py-2 text-center font-medium">Durum</th>
                    <th className="px-4 py-2 text-left font-medium">Gönderim</th>
                    <th className="px-4 py-2 text-left font-medium">Yanıt</th>
                    <th className="px-4 py-2 text-left font-medium">Teklif</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.recipients.map((r) => (
                    <tr key={r.id} className="hover:bg-muted/40">
                      <td className="px-4 py-2">
                        <span className="inline-flex items-center gap-1">
                          {r.owner_type === "institution" ? <Building2 className="size-3.5 text-muted-foreground" aria-hidden /> : <UserRound className="size-3.5 text-muted-foreground" aria-hidden />}
                          <Link href={r.owner_url} className="font-medium hover:text-indigo-700">{r.owner_name}</Link>
                          {r.owner_plan ? <span className="ml-1 font-mono text-[11px] text-muted-foreground">{r.owner_plan}</span> : null}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span className={cn(
                          "rounded px-1.5 py-0.5 text-[10px] font-semibold",
                          r.variant === "B" ? "bg-purple-100 text-purple-700" : "bg-indigo-100 text-indigo-700",
                        )}>
                          {r.variant}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span className={cn("rounded border px-2 py-0.5 text-[10px] font-semibold", badge(RECIP_TONE[r.status] ?? "slate"))}>
                          {r.status_label}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-xs text-muted-foreground">{fmt(r.sent_at)}</td>
                      <td className="px-4 py-2 text-xs text-muted-foreground">{fmt(r.responded_at)}</td>
                      <td className="px-4 py-2 text-xs">
                        {r.offer_id && r.offer_token ? (
                          <a href={`/offers/${r.offer_token}`} target="_blank" rel="noreferrer"
                             className="inline-flex items-center gap-0.5 text-indigo-600 hover:text-indigo-800">
                            #{r.offer_id} <ExternalLink className="size-3" aria-hidden />
                          </a>
                        ) : r.error_note ? (
                          <span className="text-rose-600">{r.error_note}</span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </section>

      <div className="space-y-1 text-xs text-muted-foreground">
        <div>Oluşturuldu: {fmt(c.created_at)}</div>
        {c.started_at ? <div>Başlatıldı: {fmt(c.started_at)}</div> : null}
        {c.completed_at ? <div>Tamamlandı: {fmt(c.completed_at)}</div> : null}
        {c.admin_note ? (
          <div className="mt-2 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-amber-700 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
            <strong>İç not:</strong> {c.admin_note}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function LifecycleButtons({
  campaignId,
  status,
  total,
}: {
  campaignId: number;
  status: string;
  total: number;
}) {
  const launchMut = useLaunchCampaign(campaignId);
  const pauseMut = usePauseCampaign(campaignId);
  const resumeMut = useResumeCampaign(campaignId);
  const completeMut = useCompleteCampaign(campaignId);
  const cancelMut = useCancelCampaign(campaignId);
  const busy = launchMut.isPending || pauseMut.isPending || resumeMut.isPending || completeMut.isPending || cancelMut.isPending;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {status === "draft" ? (
        <>
          <Button disabled={busy}
                  onClick={() => { if (confirm(`Kampanyayı başlatıp ${total} hedefe e-posta gönder?`)) launchMut.mutate(); }}
                  className="bg-emerald-600 text-white hover:bg-emerald-700">
            {launchMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Rocket className="size-4" aria-hidden />}
            Başlat
          </Button>
          <Button variant="outline" disabled={busy}
                  onClick={() => { if (confirm("Taslak kampanyayı iptal et?")) cancelMut.mutate(); }}>
            <Ban className="size-4" aria-hidden /> İptal
          </Button>
        </>
      ) : null}
      {status === "running" ? (
        <>
          <Button variant="outline" disabled={busy} onClick={() => pauseMut.mutate()}
                  className="border-amber-300 bg-amber-100 text-amber-800 hover:bg-amber-200">
            <Pause className="size-4" aria-hidden /> Duraklat
          </Button>
          <Button disabled={busy} onClick={() => { if (confirm("Kampanyayı tamamlandı işaretle?")) completeMut.mutate(); }}
                  className="bg-indigo-600 text-white hover:bg-indigo-700">
            <CheckSquare className="size-4" aria-hidden /> Tamamla
          </Button>
        </>
      ) : null}
      {status === "paused" ? (
        <>
          <Button disabled={busy} onClick={() => resumeMut.mutate()} className="bg-emerald-600 text-white hover:bg-emerald-700">
            <Play className="size-4" aria-hidden /> Devam Et
          </Button>
          <Button disabled={busy} onClick={() => completeMut.mutate()} className="bg-indigo-600 text-white hover:bg-indigo-700">
            <CheckSquare className="size-4" aria-hidden /> Tamamla
          </Button>
        </>
      ) : null}
    </div>
  );
}

function FunnelKpi({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: number | string;
  tone: string;
  sub?: string;
}) {
  const cls: Record<string, string> = {
    slate: "bg-slate-50 border-slate-200 text-slate-900 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-200",
    blue: "bg-blue-50 border-blue-200 text-blue-900 dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-200",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
    rose: "bg-rose-50 border-rose-200 text-rose-900 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
    amber: "bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-900 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
  };
  return (
    <div className={cn("rounded-lg border p-3", cls[tone] ?? cls.slate)}>
      <div className="text-[10px] uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub ? <div className="text-[10px] opacity-70">{sub}</div> : null}
    </div>
  );
}

function VariantCard({
  title,
  name,
  kindLabel,
  funnel,
  tone,
}: {
  title: string;
  name: string;
  kindLabel: string;
  funnel: CampaignFunnel;
  tone: string;
}) {
  const border = tone === "purple" ? "border-purple-200" : "border-indigo-200";
  const text = tone === "purple" ? "text-purple-700" : "text-indigo-700";
  return (
    <Card className={cn("border-2 p-4", border)}>
      <div className={cn("text-xs font-semibold uppercase", text)}>{title}</div>
      <div className="text-base font-semibold">{name}</div>
      <div className="mt-1 text-xs text-muted-foreground">{kindLabel}</div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
        <div><div className="font-semibold">{funnel.total}</div><div className="text-muted-foreground">Hedef</div></div>
        <div><div className="font-semibold text-emerald-700">{funnel.accepted}</div><div className="text-muted-foreground">Kabul</div></div>
        <div>
          <div className={cn("font-semibold", text)}>{funnel.accepted_pct != null ? `%${funnel.accepted_pct}` : "—"}</div>
          <div className="text-muted-foreground">Dönüşüm</div>
        </div>
      </div>
    </Card>
  );
}

function WinnerBanner({ a, b }: { a: CampaignFunnel; b: CampaignFunnel }) {
  if (a.accepted_pct == null || b.accepted_pct == null) return null;
  let msg: string;
  let tone: string;
  if (a.accepted_pct > b.accepted_pct) {
    msg = `Şu an Varyant A öne geçti (%${a.accepted_pct} vs %${b.accepted_pct})`;
    tone = "indigo";
  } else if (b.accepted_pct > a.accepted_pct) {
    msg = `Şu an Varyant B öne geçti (%${b.accepted_pct} vs %${a.accepted_pct})`;
    tone = "purple";
  } else {
    msg = `Şu an A ve B eşit (%${a.accepted_pct})`;
    tone = "slate";
  }
  return (
    <div className={cn("mt-3 inline-flex items-center gap-1.5 rounded border px-3 py-2 text-xs", badge(tone))}>
      <Trophy className="size-3.5" aria-hidden />
      {msg}
    </div>
  );
}
