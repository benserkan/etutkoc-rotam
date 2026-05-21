"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ListChecks, Plus } from "lucide-react";

import { Card } from "@/components/ui/card";
import { adminKeys, getAdminFeatureExperiments } from "@/lib/api/admin";
import type { ExperimentListResponse } from "@/lib/types/admin";
import { StatusBadge } from "@/components/admin/feature-catalog-ui";

interface Props {
  initial: ExperimentListResponse;
}

export function AdminFeatureExperimentsClient({ initial }: Props) {
  const q = useQuery<ExperimentListResponse>({
    queryKey: adminKeys.featureExperiments(),
    queryFn: () => getAdminFeatureExperiments(),
    initialData: initial,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            href="/admin/feature-catalog"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Vitrin Kartları
          </Link>
          <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <ListChecks className="size-6 text-indigo-700" aria-hidden />
            A/B Deneyleri
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Anasayfa sıralama stratejilerini karşılaştır. Aynı anda yalnız{" "}
            <strong>bir</strong> deney &quot;Çalışıyor&quot; olabilir; ziyaretçiler
            deterministik iki gruba dağıtılır ve tıklama oranları karşılaştırılır.
          </p>
        </div>
        <Link
          href="/admin/feature-catalog/experiments/new"
          className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          <Plus className="size-4" aria-hidden />
          Yeni Deney
        </Link>
      </header>

      {data.experiments.length === 0 ? (
        <Card className="p-12 text-center text-sm text-muted-foreground">
          Henüz deney yok.
          <div className="mt-3">
            <Link
              href="/admin/feature-catalog/experiments/new"
              className="text-indigo-600 hover:text-indigo-800"
            >
              Yeni deney oluştur →
            </Link>
          </div>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Deney</th>
                  <th className="px-3 py-2 text-left font-medium">Durum</th>
                  <th className="px-3 py-2 text-left font-medium">Variant&apos;lar</th>
                  <th className="px-3 py-2 text-left font-medium">Başlangıç</th>
                  <th className="px-3 py-2 text-right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.experiments.map((e) => (
                  <tr key={e.id} className="hover:bg-muted/40">
                    <td className="px-4 py-3 align-top">
                      <Link
                        href={`/admin/feature-catalog/experiments/${e.id}`}
                        className="font-medium hover:text-indigo-700"
                      >
                        {e.name}
                      </Link>
                      <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                        {e.slug}
                      </div>
                      {e.hypothesis ? (
                        <div className="mt-1 line-clamp-2 max-w-md text-xs text-muted-foreground">
                          {e.hypothesis}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-3 py-3 align-top">
                      <StatusBadge label={e.status_label} tone={e.status_badge} />
                    </td>
                    <td className="px-3 py-3 align-top text-xs">
                      {e.variants.map((v) => (
                        <div key={v.slug}>
                          <span className="font-mono">{v.slug}</span>
                          <span className="text-muted-foreground"> · </span>
                          {v.label}
                          <span className="text-muted-foreground"> · </span>%{v.weight}
                        </div>
                      ))}
                    </td>
                    <td className="px-3 py-3 align-top text-xs text-muted-foreground">
                      {e.start_at ? e.start_at.slice(0, 10) : "—"}
                    </td>
                    <td className="px-3 py-3 text-right align-top">
                      <Link
                        href={`/admin/feature-catalog/experiments/${e.id}`}
                        className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
                      >
                        Aç →
                      </Link>
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
