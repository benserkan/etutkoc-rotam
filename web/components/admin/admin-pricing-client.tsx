"use client";

import * as React from "react";
import { CircleDollarSign, Loader2, RotateCcw, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSavePricing, useResetPricing } from "@/lib/hooks/use-admin-mutations";
import type { PricingAdminResponse, PricingConfig } from "@/lib/types/admin";

function NumField({ label, value, onChange, suffix }: { label: string; value: number; onChange: (n: number) => void; suffix?: string }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      <div className="flex items-center gap-1">
        <Input type="number" min={0} value={value} onChange={(e) => onChange(Number(e.target.value))} className="h-9" />
        {suffix ? <span className="text-xs text-muted-foreground">{suffix}</span> : null}
      </div>
    </div>
  );
}

export function AdminPricingClient({ initial }: { initial: PricingAdminResponse }) {
  const save = useSavePricing();
  const reset = useResetPricing();

  const [cfg, setCfg] = React.useState<PricingConfig>(structuredClone(initial.config));

  function set<K extends keyof PricingConfig>(k: K, v: PricingConfig[K]) {
    setCfg((c) => ({ ...c, [k]: v }));
  }
  function setSoloTier(i: number, field: "max_students" | "monthly", v: number | null) {
    setCfg((c) => {
      const tiers = c.solo_tiers.map((t, idx) => (idx === i ? { ...t, [field]: v } : t));
      return { ...c, solo_tiers: tiers };
    });
  }
  function setTier(i: number, field: "monthly_total" | "min_coaches" | "max_coaches", v: number | null) {
    setCfg((c) => {
      const tiers = c.institution_tiers.map((t, idx) => (idx === i ? { ...t, [field]: v } : t));
      return { ...c, institution_tiers: tiers };
    });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <CircleDollarSign className="size-5 text-emerald-700" aria-hidden /> Ücretlendirme
          </h1>
          <p className="text-sm text-muted-foreground">
            Üyelik fiyat/limitleri. Buradaki değerler <strong>/pricing sayfası, koç Paket
            ekranı ve erişim kapısı</strong> dahil her yerde geçerlidir (tek kaynak).
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => reset.mutate(undefined, { onSuccess: (res) => setCfg(structuredClone(res.data.config)) })} disabled={reset.isPending}>
          {reset.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <RotateCcw className="size-4" aria-hidden />}
          Varsayılana sıfırla
        </Button>
      </header>

      {/* Solo */}
      <Card>
        <CardContent className="space-y-4 p-4">
          <h2 className="font-medium">Bağımsız Koç (Solo)</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-2">
            <NumField label="Ücretsiz öğrenci" value={cfg.solo_free_students} onChange={(n) => set("solo_free_students", n)} />
            <NumField label="Deneme süresi" value={cfg.solo_trial_days} onChange={(n) => set("solo_trial_days", n)} suffix="gün" />
          </div>
          <div className="space-y-2">
            <Label className="text-xs">Paketler (öğrenci tavanı → aylık ₺). Tavan 0 = sınırsız.</Label>
            {cfg.solo_tiers.map((t, i) => (
              <div key={t.code} className="flex flex-wrap items-center gap-2">
                <span className="w-32 text-sm">{t.label}</span>
                <span className="text-xs text-muted-foreground">≤ öğrenci</span>
                <Input type="number" min={0} value={t.max_students ?? 0} onChange={(e) => setSoloTier(i, "max_students", Number(e.target.value) || null)} className="h-9 w-24" title="öğrenci tavanı (0=sınırsız)" />
                <span className="text-xs text-muted-foreground">→</span>
                <Input type="number" min={0} value={t.monthly} onChange={(e) => setSoloTier(i, "monthly", Number(e.target.value))} className="h-9 w-32" />
                <span className="text-xs text-muted-foreground">₺/ay</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Institution */}
      <Card>
        <CardContent className="space-y-4 p-4">
          <h2 className="font-medium">Kurum</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <NumField label="Ücretsiz öğretmen" value={cfg.institution_free_teachers} onChange={(n) => set("institution_free_teachers", n)} />
            <NumField label="Ücretsiz öğrenci" value={cfg.institution_free_students} onChange={(n) => set("institution_free_students", n)} />
            <NumField label="Koç başına öğrenci" value={cfg.institution_students_per_coach} onChange={(n) => set("institution_students_per_coach", n)} />
            <NumField label="Pilot süresi" value={cfg.institution_trial_days} onChange={(n) => set("institution_trial_days", n)} suffix="gün" />
          </div>
          <div className="space-y-2">
            <Label className="text-xs">Kademeler (koç sayısı → toplam aylık ₺). Toplam boş = özel teklif.</Label>
            {cfg.institution_tiers.map((t, i) => (
              <div key={t.code} className="flex flex-wrap items-center gap-2">
                <span className="w-36 text-sm">{t.label}</span>
                <Input type="number" min={1} value={t.min_coaches} onChange={(e) => setTier(i, "min_coaches", Number(e.target.value))} className="h-9 w-20" title="min koç" />
                <span className="text-xs text-muted-foreground">–</span>
                <Input type="number" min={0} value={t.max_coaches ?? 0} onChange={(e) => setTier(i, "max_coaches", Number(e.target.value) || null)} className="h-9 w-20" title="max koç (0=sınırsız)" />
                <span className="text-xs text-muted-foreground">koç →</span>
                <Input
                  type="number"
                  min={0}
                  value={t.monthly_total ?? 0}
                  disabled={t.price_hidden}
                  onChange={(e) => setTier(i, "monthly_total", Number(e.target.value) || null)}
                  className="h-9 w-28"
                  title="toplam aylık (0=özel teklif)"
                />
                <span className="text-xs text-muted-foreground">{t.price_hidden ? "₺/ay (özel teklif)" : "₺/ay (toplam)"}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:max-w-xs">
        <NumField label="Yıllık ödenen ay (10=2 ay bedava)" value={cfg.annual_paid_months} onChange={(n) => set("annual_paid_months", n)} />
      </div>

      <div className="flex items-center justify-end gap-2">
        <Button onClick={() => save.mutate(cfg, { onSuccess: (res) => setCfg(structuredClone(res.data.config)) })} disabled={save.isPending}>
          {save.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Save className="size-4" aria-hidden />}
          Kaydet
        </Button>
      </div>
    </div>
  );
}
