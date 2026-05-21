"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2, Receipt, UserRound } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminRevenueInvoices } from "@/lib/api/admin";
import type { RevenueInvoicesResponse } from "@/lib/types/admin";
import { StatusBadge } from "@/components/admin/feature-catalog-ui";
import { tl } from "@/components/admin/revenue-360-shared";

interface Props {
  initial: RevenueInvoicesResponse;
}

function fmt(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("tr-TR");
  } catch {
    return iso.slice(0, 10);
  }
}

export function AdminRevenueInvoicesClient({ initial }: Props) {
  const [statusFilter, setStatusFilter] = React.useState<string | null>(initial.status_filter);
  const q = useQuery<RevenueInvoicesResponse>({
    queryKey: adminKeys.revenueInvoices(statusFilter),
    queryFn: () => getAdminRevenueInvoices(statusFilter),
    initialData: statusFilter === initial.status_filter ? initial : undefined,
    staleTime: 15_000,
  });
  const d = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header>
        <Link href="/admin/security-monitor/revenue" className="text-sm text-muted-foreground hover:text-foreground">
          ← Ticari Pano
        </Link>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Receipt className="size-6 text-indigo-700" aria-hidden />
          Faturalar
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Kurum + bağımsız öğretmen ödeme kayıtları — durum, vade, tahsilat geçmişi.
          Manuel müdahaleler (hatırlat/öden/ötele/iptal) ilgili 360 sayfasının fatura sekmesinde.
        </p>
      </header>

      {/* Status sayım chip-bar */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {d.statuses.map((s) => {
          const c = d.status_counts[s.value];
          if (!c || c.count === 0) return null;
          const active = statusFilter === s.value;
          return (
            <button key={s.value} type="button" onClick={() => setStatusFilter(active ? null : s.value)}
                    className={cn(
                      "rounded-lg border bg-card p-3 text-left transition hover:border-foreground/30",
                      active ? "border-indigo-400 ring-2 ring-indigo-200" : "border-border",
                    )}>
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{s.label}</div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-semibold">{c.count}</span>
                <span className="text-[11px] text-muted-foreground">fatura</span>
              </div>
              <div className="text-xs text-muted-foreground">{tl(c.total_try)}</div>
            </button>
          );
        })}
      </div>

      {statusFilter ? (
        <div className="text-sm text-muted-foreground">
          Filtre: <code className="rounded bg-muted px-2 py-0.5 text-xs">{statusFilter}</code>
          <button type="button" onClick={() => setStatusFilter(null)} className="ml-2 text-xs text-indigo-600 hover:text-indigo-800">
            × temizle
          </button>
        </div>
      ) : null}

      {d.rows.length === 0 ? (
        <Card className="p-12 text-center text-sm text-muted-foreground">Bu filtreye uyan fatura yok.</Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Sahip</th>
                  <th className="px-3 py-2 text-left">Paket</th>
                  <th className="px-3 py-2 text-right">Tutar</th>
                  <th className="px-3 py-2 text-left">Vade</th>
                  <th className="px-3 py-2 text-left">Ödendi</th>
                  <th className="px-3 py-2 text-center">Durum</th>
                  <th className="px-3 py-2 text-left">Yöntem</th>
                  <th className="px-3 py-2 text-right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.rows.map((r) => (
                  <tr key={r.id} className="hover:bg-muted/40">
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1.5">
                        {r.owner_type === "user" ? <UserRound className="size-3.5 text-purple-600" aria-hidden /> : <Building2 className="size-3.5 text-indigo-600" aria-hidden />}
                        <Link href={r.owner_url} className="font-medium hover:text-indigo-700">{r.owner_name}</Link>
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-muted-foreground">{r.plan}</td>
                    <td className="px-3 py-2 text-right font-semibold">{tl(r.amount_try)}</td>
                    <td className="px-3 py-2 text-muted-foreground">{fmt(r.due_at)}</td>
                    <td className="px-3 py-2 text-muted-foreground">{fmt(r.paid_at)}</td>
                    <td className="px-3 py-2 text-center">
                      <StatusBadge label={r.status_label} tone={r.status_color} />
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{r.payment_method ?? "—"}</td>
                    <td className="px-3 py-2 text-right">
                      <Link href={r.owner_url} className="text-xs text-indigo-600 hover:text-indigo-800">Detay →</Link>
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
