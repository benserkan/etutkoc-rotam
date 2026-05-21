"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useCreateExperiment } from "@/lib/hooks/use-admin-mutations";
import type { ExperimentFormMeta } from "@/lib/types/admin";
import { fieldClass } from "@/components/admin/feature-catalog-ui";

interface Props {
  meta: ExperimentFormMeta;
}

export function AdminFeatureExperimentFormClient({ meta }: Props) {
  const router = useRouter();
  const strategies = meta.strategies;
  const [name, setName] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [hypothesis, setHypothesis] = React.useState("");
  const [ctrlStrategy, setCtrlStrategy] = React.useState(
    strategies.find((s) => s.key === "hybrid_full")?.key ?? strategies[0]?.key ?? "",
  );
  const [testStrategy, setTestStrategy] = React.useState(
    strategies.find((s) => s.key === "fuzzy_only")?.key ?? strategies[0]?.key ?? "",
  );
  const [weightCtrl, setWeightCtrl] = React.useState(50);
  const [weightTest, setWeightTest] = React.useState(50);

  const mut = useCreateExperiment();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      {
        name,
        slug,
        hypothesis,
        ctrl_strategy: ctrlStrategy,
        test_strategy: testStrategy,
        weight_ctrl: weightCtrl,
        weight_test: weightTest,
      },
      {
        onSuccess: (res) => {
          const id = res.data.experiment_id;
          if (id) router.push(`/admin/feature-catalog/experiments/${id}`);
          else router.push("/admin/feature-catalog/experiments");
        },
      },
    );
  }

  return (
    <div className="space-y-5">
      <header>
        <Link
          href="/admin/feature-catalog/experiments"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Deney Listesi
        </Link>
        <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight">
          Yeni A/B Deneyi
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          İki strateji karşılaştırması — ziyaretçilerin %X&apos;i kontrol, %Y&apos;si
          test grubuna düşer. &quot;Çalışıyor&quot; durumuna alındığında atama başlar.
        </p>
      </header>

      <form onSubmit={onSubmit}>
        <Card className="max-w-3xl space-y-5 p-5">
          <label className="block">
            <span className="text-sm font-medium">Deney adı *</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={160}
              placeholder="Örn: Hibrit vs Sade Fuzzy"
              className={cn(fieldClass, "mt-1")}
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium">Slug (opsiyonel)</span>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              maxLength={80}
              placeholder="boş bırakırsanız addan üretilir"
              className={cn(fieldClass, "mt-1 font-mono")}
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium">Hipotez (opsiyonel)</span>
            <textarea
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="Örn: Çeşitlilik filtresini kaldırırsak demo tıklama oranı artar."
              className={cn(fieldClass, "mt-1")}
            />
          </label>

          <div className="border-t border-border pt-5">
            <h3 className="mb-3 text-sm font-semibold">Variant&apos;lar</h3>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Kontrol (ctrl)
                </div>
                <label className="mb-2 block">
                  <span className="text-xs text-muted-foreground">Strateji</span>
                  <select
                    value={ctrlStrategy}
                    onChange={(e) => setCtrlStrategy(e.target.value)}
                    className={cn(fieldClass, "mt-1 bg-background")}
                  >
                    {strategies.map((s) => (
                      <option key={s.key} value={s.key}>{s.label}</option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs text-muted-foreground">Ağırlık (%)</span>
                  <input
                    type="number"
                    value={weightCtrl}
                    onChange={(e) => setWeightCtrl(Number(e.target.value))}
                    min={1}
                    max={99}
                    className={cn(fieldClass, "mt-1")}
                  />
                </label>
              </div>

              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Test (test)
                </div>
                <label className="mb-2 block">
                  <span className="text-xs text-muted-foreground">Strateji</span>
                  <select
                    value={testStrategy}
                    onChange={(e) => setTestStrategy(e.target.value)}
                    className={cn(fieldClass, "mt-1 bg-background")}
                  >
                    {strategies.map((s) => (
                      <option key={s.key} value={s.key}>{s.label}</option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs text-muted-foreground">Ağırlık (%)</span>
                  <input
                    type="number"
                    value={weightTest}
                    onChange={(e) => setWeightTest(Number(e.target.value))}
                    min={1}
                    max={99}
                    className={cn(fieldClass, "mt-1")}
                  />
                </label>
              </div>
            </div>
            <p
              className={cn(
                "mt-2 text-[11px]",
                weightCtrl + weightTest === 100 ? "text-muted-foreground" : "text-rose-600",
              )}
            >
              Toplam ağırlık 100 olmalı (şu an {weightCtrl + weightTest}).
            </p>

            <details className="mt-3 text-xs text-muted-foreground">
              <summary className="cursor-pointer font-medium">Strateji açıklamaları</summary>
              <dl className="mt-2 space-y-2 pl-4">
                {strategies.map((s) => (
                  <div key={s.key}>
                    <dt className="font-mono text-foreground">{s.key}</dt>
                    <dd>{s.description}</dd>
                  </div>
                ))}
              </dl>
            </details>
          </div>

          <div className="flex items-center justify-between border-t border-border pt-4">
            <Link
              href="/admin/feature-catalog/experiments"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              İptal
            </Link>
            <Button
              type="submit"
              disabled={mut.isPending}
              className="bg-indigo-600 text-white hover:bg-indigo-700"
            >
              {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              Deneyi Oluştur (Taslak)
            </Button>
          </div>
        </Card>
      </form>
    </div>
  );
}
