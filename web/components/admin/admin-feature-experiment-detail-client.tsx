"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Pause, Play, Square } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { adminKeys, getAdminFeatureExperiment } from "@/lib/api/admin";
import { useSetExperimentStatus } from "@/lib/hooks/use-admin-mutations";
import type {
  ExperimentDetailResponse,
  ExperimentVariantStat,
} from "@/lib/types/admin";
import { StatusBadge } from "@/components/admin/feature-catalog-ui";

interface Props {
  initial: ExperimentDetailResponse;
  experimentId: number;
}

const CONFIRM_TEXT: Record<string, string> = {
  running:
    "Deneyi başlatmak istediğinizden emin misiniz? Mevcut çalışan deney varsa duraklatılır.",
  completed: "Deneyi sonlandırmak istediğinizden emin misiniz? Bu işlem geri alınmaz.",
};

export function AdminFeatureExperimentDetailClient({ initial, experimentId }: Props) {
  const q = useQuery<ExperimentDetailResponse>({
    queryKey: adminKeys.featureExperiment(experimentId),
    queryFn: () => getAdminFeatureExperiment(experimentId),
    initialData: initial,
    staleTime: 10_000,
  });
  const data = q.data ?? initial;
  const exp = data.experiment;
  const mut = useSetExperimentStatus(experimentId);
  const [confirmStatus, setConfirmStatus] = React.useState<string | null>(null);

  function apply(status: string) {
    // Duraklat onay gerektirmez (Jinja'da da öyle)
    if (status === "paused") {
      mut.mutate({ status });
      return;
    }
    setConfirmStatus(status);
  }
  function doConfirm() {
    if (!confirmStatus) return;
    mut.mutate({ status: confirmStatus }, { onSettled: () => setConfirmStatus(null) });
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            href="/admin/feature-catalog/experiments"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Deney Listesi
          </Link>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight">
            {exp.name}
          </h1>
          <div className="mt-1 flex items-center gap-2 text-xs">
            <StatusBadge label={exp.status_label} tone={exp.status_badge} />
            <span className="font-mono text-muted-foreground">{exp.slug}</span>
          </div>
          {exp.hypothesis ? (
            <div className="mt-3 max-w-3xl rounded border border-border bg-muted/40 p-3 text-sm">
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Hipotez
              </div>
              {exp.hypothesis}
            </div>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {exp.status === "draft" ? (
            <Button onClick={() => apply("running")} disabled={mut.isPending} className="bg-emerald-600 text-white hover:bg-emerald-700">
              <Play className="size-4" aria-hidden />
              Başlat
            </Button>
          ) : null}
          {exp.status === "running" ? (
            <>
              <Button onClick={() => apply("paused")} disabled={mut.isPending} variant="outline" className="border-amber-300 bg-amber-100 text-amber-800 hover:bg-amber-200">
                <Pause className="size-4" aria-hidden />
                Duraklat
              </Button>
              <Button onClick={() => apply("completed")} disabled={mut.isPending} variant="outline" className="border-indigo-300 bg-indigo-100 text-indigo-800 hover:bg-indigo-200">
                <Square className="size-4" aria-hidden />
                Sonlandır
              </Button>
            </>
          ) : null}
          {exp.status === "paused" ? (
            <Button onClick={() => apply("running")} disabled={mut.isPending} className="bg-emerald-600 text-white hover:bg-emerald-700">
              <Play className="size-4" aria-hidden />
              Devam Et
            </Button>
          ) : null}
        </div>
      </header>

      <Card className="overflow-hidden">
        <div className="border-b border-border bg-muted/40 px-4 py-3">
          <h2 className="text-sm font-semibold">Variant İstatistikleri</h2>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            CTR = (demo tıklama + bağlantı tıklama) ÷ gösterim. %95 güven aralığı
            parantez içinde.
          </p>
        </div>

        {!data.has_any_data ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            Henüz veri yok.{" "}
            {exp.status === "running"
              ? "Ziyaretçi gelmeye başladığında bu tablo dolacak."
              : 'Deney "Çalışıyor" durumuna alındığında veri toplamaya başlar.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Variant</th>
                  <th className="px-3 py-2 text-right font-medium">Gösterim</th>
                  <th className="px-3 py-2 text-right font-medium">Görüntüleme</th>
                  <th className="px-3 py-2 text-right font-medium">Tıklama</th>
                  <th className="px-3 py-2 text-left font-medium">CTR (%95 GA)</th>
                  <th className="px-3 py-2 text-right font-medium">Kontrol farkı</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.stats.map((v) => (
                  <StatRow
                    key={v.slug}
                    v={v}
                    poolLabel={
                      data.experiment.variants.find((b) => b.slug === v.slug)?.pool_label ?? null
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="max-w-3xl text-xs text-muted-foreground">
        <strong>Wilson güven aralığı:</strong> az veride bile sağlam. CI&apos;ler
        çakışmıyorsa &quot;anlamlı fark ✓&quot; çıkar; çakışıyorsa daha fazla veri
        gerekir. Düşük örneklemde (≪30 gösterim) işaret gösterilmez.
      </p>

      <Dialog open={confirmStatus != null} onOpenChange={(o) => !o && setConfirmStatus(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Durumu değiştir</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {confirmStatus ? CONFIRM_TEXT[confirmStatus] ?? "Onaylıyor musun?" : ""}
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button variant="ghost" onClick={() => setConfirmStatus(null)} disabled={mut.isPending}>
              Vazgeç
            </Button>
            <Button
              onClick={doConfirm}
              disabled={mut.isPending}
              className="bg-indigo-600 text-white hover:bg-indigo-700"
            >
              {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              Onayla
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StatRow({ v, poolLabel }: { v: ExperimentVariantStat; poolLabel?: string | null }) {
  const barMax = 0.3;
  const loW = Math.min(100, (v.ctr_low / barMax) * 100);
  const hiW = Math.min(100, (v.ctr_high / barMax) * 100);
  const centerW = Math.min(100, (v.ctr / barMax) * 100);
  const liftInt = v.lift_pct != null ? Math.round(v.lift_pct) : null;

  return (
    <tr>
      <td className="px-4 py-3 align-top">
        <div className="font-medium">{v.label}</div>
        <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
          {v.slug} · {v.weight}%
        </div>
        <div className="mt-0.5 text-[11px] text-muted-foreground">{v.strategy_label}</div>
        {poolLabel ? (
          <div className="mt-1 inline-block rounded bg-cyan-100 px-1.5 py-px text-[10px] font-medium text-cyan-900">
            {poolLabel}
          </div>
        ) : null}
        {v.is_control ? (
          <div className="mt-1 inline-block rounded border border-border bg-muted px-1.5 py-px text-[10px] text-muted-foreground">
            Kontrol
          </div>
        ) : null}
      </td>
      <td className="px-3 py-3 text-right align-top font-mono">{v.impression}</td>
      <td className="px-3 py-3 text-right align-top font-mono">{v.view}</td>
      <td className="px-3 py-3 text-right align-top font-mono">
        <span className="font-semibold text-indigo-700">{v.total_clicks}</span>
        {v.demo_click > 0 && v.cta_click > 0 ? (
          <div className="text-[10px] text-muted-foreground">
            ▶ {v.demo_click} · 🖱 {v.cta_click}
          </div>
        ) : null}
      </td>
      <td className="px-3 py-3 align-top">
        {v.impression === 0 ? (
          <span className="text-xs text-muted-foreground">—</span>
        ) : (
          <>
            <div className="text-sm font-semibold">%{(v.ctr * 100).toFixed(2)}</div>
            <div className="text-[11px] text-muted-foreground">
              (%{(v.ctr_low * 100).toFixed(2)} – %{(v.ctr_high * 100).toFixed(2)})
            </div>
            <div className="relative mt-1.5 h-1.5 w-32 rounded-full bg-muted">
              <div
                className="absolute h-full rounded-full bg-indigo-200"
                style={{ left: `${loW}%`, width: `${Math.max(0, hiW - loW)}%` }}
              />
              <div
                className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-700 ring-2 ring-white"
                style={{ left: `${centerW}%` }}
              />
            </div>
          </>
        )}
      </td>
      <td className="px-3 py-3 text-right align-top">
        {v.is_control ? (
          <span className="text-[11px] text-muted-foreground">—</span>
        ) : liftInt == null ? (
          <span className="text-[11px] text-muted-foreground">veri bekleniyor</span>
        ) : (
          <>
            <div
              className={cn(
                "text-sm font-semibold",
                liftInt > 0 ? "text-emerald-700" : liftInt < 0 ? "text-rose-700" : "text-foreground",
              )}
            >
              {liftInt >= 0 ? "+" : ""}
              {liftInt}%
            </div>
            {v.vs_control_significant ? (
              <div className="mt-0.5 inline-block rounded border border-emerald-200 bg-emerald-100 px-1.5 py-px text-[10px] text-emerald-700">
                anlamlı fark ✓
              </div>
            ) : (
              <div className="mt-0.5 text-[10px] text-muted-foreground">yeterli veri yok</div>
            )}
          </>
        )}
      </td>
    </tr>
  );
}
