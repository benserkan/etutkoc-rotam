"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Megaphone, Plus } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminCampaigns } from "@/lib/api/admin";
import type { CampaignsListResponse } from "@/lib/types/admin";
import { StatusBadge } from "@/components/admin/feature-catalog-ui";

interface Props {
  initial: CampaignsListResponse;
}

function convTone(pct: number | null): string {
  if (pct == null) return "text-muted-foreground";
  if (pct >= 20) return "text-emerald-700";
  if (pct >= 10) return "text-amber-700";
  return "text-rose-700";
}

export function AdminCampaignsClient({ initial }: Props) {
  const q = useQuery<CampaignsListResponse>({
    queryKey: adminKeys.revenueCampaigns(),
    queryFn: () => getAdminCampaigns(),
    initialData: initial,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <span className="text-sm text-muted-foreground">Ticari Pano</span>
          <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <Megaphone className="size-6 text-indigo-700" aria-hidden />
            Toplu Kampanyalar
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Belirli bir segmente (ücretsiz plandakiler, denemesi bitmek üzere
            olanlar, vb.) aynı teklifi tek seferde gönder. Kurum + bağımsız
            öğretmen birlikte hedeflenir.
          </p>
        </div>
        <Link
          href="/admin/revenue/campaigns/new"
          className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          <Plus className="size-4" aria-hidden />
          Yeni Kampanya
        </Link>
      </header>

      {data.campaigns.length === 0 ? (
        <Card className="p-12 text-center text-sm text-muted-foreground">
          Henüz kampanya yok.{" "}
          <Link href="/admin/revenue/campaigns/new" className="text-indigo-600 hover:text-indigo-800">
            Yeni kampanya oluştur →
          </Link>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Kampanya</th>
                  <th className="px-4 py-2 text-left font-medium">Segment</th>
                  <th className="px-4 py-2 text-center font-medium">Durum</th>
                  <th className="px-4 py-2 text-right font-medium">Hedef</th>
                  <th className="px-4 py-2 text-right font-medium">Gönderildi</th>
                  <th className="px-4 py-2 text-right font-medium">Kabul</th>
                  <th className="px-4 py-2 text-right font-medium">Dönüşüm</th>
                  <th className="px-4 py-2 text-left font-medium">Oluşturuldu</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.campaigns.map((c) => (
                  <tr key={c.id} className="hover:bg-muted/40">
                    <td className="px-4 py-3">
                      <Link href={`/admin/revenue/campaigns/${c.id}`} className="font-medium hover:text-indigo-700">
                        {c.name}
                      </Link>
                      {c.has_variant_b ? (
                        <span className="ml-1 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700">A/B</span>
                      ) : null}
                      {c.description ? (
                        <div className="max-w-xs truncate text-xs text-muted-foreground">{c.description}</div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{c.segment_label}</td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge label={c.status_label} tone={c.status_color} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-muted-foreground">{c.funnel.total}</td>
                    <td className="px-4 py-3 text-right font-mono text-muted-foreground">{c.funnel.sent_total}</td>
                    <td className="px-4 py-3 text-right font-mono text-emerald-700">{c.funnel.accepted}</td>
                    <td className={cn("px-4 py-3 text-right font-mono font-semibold", convTone(c.funnel.accepted_pct))}>
                      {c.funnel.accepted_pct != null ? `%${c.funnel.accepted_pct}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {c.created_at ? new Date(c.created_at).toLocaleDateString("tr-TR") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
