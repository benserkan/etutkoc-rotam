"use client";

/**
 * Kart İçerikleri editörü (Faz 2B, 2026-08-05) — "kartlar bayatladı" sorununun
 * kalıcı çözümü: süper admin paket kartlarının özellik maddelerini, tagline'ları,
 * kredi notlarını ve tıkla-gör sözlüğünü KODSUZ günceller. Kaydedilen içerik
 * /pricing + Paketim + anasayfa + üyelik teklifi + mobil Paketim'e ANINDA yansır
 * (deploy gerekmez). Sıfırla → kod varsayılanına döner.
 *
 * Biçim kuralı (yoğunluk dersi): her madde "Kısa Başlık — kısa detay".
 * Sunucu bloklamaz ama tavsiye uyarısı döner (uzun ayraçsız madde + hiçbir
 * maddede geçmeyen sözlük terimi).
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, LayoutTemplate, Loader2, Plus, RotateCcw, Save, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getAdminPricingContent, adminKeys } from "@/lib/api/admin";
import {
  useResetPricingContent,
  useSavePricingContent,
} from "@/lib/hooks/use-admin-mutations";
import type {
  PricingContentAdminResponse,
  PricingContentConfig,
  PricingGlossaryEntry,
} from "@/lib/types/admin";

const TIER_LABELS: Record<string, string> = {
  free: "Keşif (ücretsiz)",
  solo_pro: "Patika",
  solo_elite: "Rota",
  solo_unlimited: "Zirve",
};

function LinesArea({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: string[];
  onChange: (lines: string[]) => void;
}) {
  return (
    <div className="space-y-1">
      <Label className="text-xs font-semibold">{label}</Label>
      {hint ? <p className="text-[11px] text-muted-foreground">{hint}</p> : null}
      <textarea
        value={value.join("\n")}
        onChange={(e) => onChange(e.target.value.split("\n"))}
        rows={Math.max(3, value.length + 1)}
        className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-5"
        spellCheck={false}
      />
    </div>
  );
}

export function AdminPricingContentClient() {
  const q = useQuery<PricingContentAdminResponse>({
    queryKey: adminKeys.pricingContent(),
    queryFn: getAdminPricingContent,
    staleTime: 30_000,
  });
  const save = useSavePricingContent();
  const reset = useResetPricingContent();

  const [cfg, setCfg] = React.useState<PricingContentConfig | null>(null);
  // Sunucudan ilk veri gelince form state'i tohumla (render-sırasında set deseni)
  const [seeded, setSeeded] = React.useState(false);
  if (q.data && !seeded) {
    setCfg(structuredClone(q.data.config));
    setSeeded(true);
  }

  if (!q.data || !cfg) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Kart içerikleri yükleniyor…
        </CardContent>
      </Card>
    );
  }
  const warnings = q.data.warnings;

  function setGlossary(i: number, field: keyof PricingGlossaryEntry, v: string) {
    setCfg((c) => {
      if (!c) return c;
      const g = c.glossary.map((e, idx) =>
        idx === i ? { ...e, [field]: v === "" ? null : v } : e,
      );
      return { ...c, glossary: g };
    });
  }

  return (
    <Card>
      <CardContent className="space-y-5 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <LayoutTemplate className="size-4 text-violet-700" aria-hidden />
              Kart İçerikleri (kodsuz yönetim)
            </h2>
            <p className="mt-1 max-w-2xl text-xs text-muted-foreground">
              Paket kartlarındaki özellik maddeleri, tagline&apos;lar, kredi notları ve
              tıkla-gör sözlüğü. Kaydedince <strong>/pricing, Paketim, anasayfa ve
              mobil ANINDA</strong> bu içeriği gösterir — kod değişikliği gerekmez.
              Madde biçimi: <code className="rounded bg-muted px-1">Kısa Başlık — kısa detay</code>.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (window.confirm("İçerik override'ı silinip kod varsayılanına dönülecek. Emin misin?")) {
                  reset.mutate(undefined, {
                    onSuccess: (res) => setCfg(structuredClone(res.data.config)),
                  });
                }
              }}
              disabled={reset.isPending}
            >
              <RotateCcw className="size-4" aria-hidden /> Sıfırla
            </Button>
            <Button
              size="sm"
              onClick={() =>
                save.mutate(cfg, {
                  onSuccess: (res) => setCfg(structuredClone(res.data.config)),
                })
              }
              disabled={save.isPending}
            >
              {save.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Save className="size-4" aria-hidden />
              )}
              Kaydet
            </Button>
          </div>
        </div>

        {warnings.length > 0 ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
            <p className="mb-1 flex items-center gap-1.5 font-semibold">
              <AlertTriangle className="size-3.5" aria-hidden /> Tavsiyeler (kaydetmeyi engellemez)
            </p>
            <ul className="list-inside list-disc space-y-0.5">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {/* Tagline + kredi notları */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label className="text-xs font-semibold">Tagline&apos;lar (kart alt başlığı)</Label>
            {Object.keys(TIER_LABELS).map((code) => (
              <div key={code} className="flex items-center gap-2">
                <span className="w-28 shrink-0 text-xs text-muted-foreground">{TIER_LABELS[code]}</span>
                <Input
                  value={cfg.taglines[code] ?? ""}
                  onChange={(e) =>
                    setCfg({ ...cfg, taglines: { ...cfg.taglines, [code]: e.target.value } })
                  }
                  className="h-8 text-xs"
                />
              </div>
            ))}
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold">
              Kredi notları — <code className="rounded bg-muted px-1">{"{kredi}"}</code> yer tutucusu tahsis sayısıyla değişir
            </Label>
            {["solo_pro", "solo_elite", "solo_unlimited"].map((code) => (
              <div key={code} className="flex items-center gap-2">
                <span className="w-28 shrink-0 text-xs text-muted-foreground">{TIER_LABELS[code]}</span>
                <Input
                  value={cfg.credit_notes[code] ?? ""}
                  onChange={(e) =>
                    setCfg({ ...cfg, credit_notes: { ...cfg.credit_notes, [code]: e.target.value } })
                  }
                  className="h-8 text-xs"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Özellik listeleri */}
        <div className="grid gap-4 md:grid-cols-2">
          <LinesArea
            label="Keşif (ücretsiz) özellikleri"
            hint="Satır başına bir madde."
            value={cfg.free_features}
            onChange={(lines) => setCfg({ ...cfg, free_features: lines })}
          />
          {["solo_pro", "solo_elite", "solo_unlimited"].map((code) => (
            <LinesArea
              key={code}
              label={`${TIER_LABELS[code]} — YENİ özellikleri`}
              hint={'Kademeli model: yalnız bu paketin EKLEDİKLERİ ("öncekinin hepsi, artı").'}
              value={cfg.tier_new[code] ?? []}
              onChange={(lines) => setCfg({ ...cfg, tier_new: { ...cfg.tier_new, [code]: lines } })}
            />
          ))}
        </div>

        {/* Sözlük */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-semibold">
              Tıkla-gör sözlüğü — terim, kart maddesindeki kısa başlıkla BİREBİR eşleşmeli
            </Label>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setCfg({
                  ...cfg,
                  glossary: [
                    ...cfg.glossary,
                    { term: "", explanation: "", image: null, image_w: null, image_h: null, image_full: null },
                  ],
                })
              }
            >
              <Plus className="size-4" aria-hidden /> Terim ekle
            </Button>
          </div>
          <div className="space-y-3">
            {cfg.glossary.map((g, i) => (
              <div key={i} className="rounded-lg border border-border p-3">
                <div className="flex items-start gap-2">
                  <div className="grid flex-1 gap-2 md:grid-cols-2">
                    <Input
                      placeholder="Terim (madde başlığıyla birebir)"
                      value={g.term}
                      onChange={(e) => setGlossary(i, "term", e.target.value)}
                      className="h-8 text-xs"
                    />
                    <Input
                      placeholder="Kırpılmış görsel yolu (/static/… — boş = yalnız metin)"
                      value={g.image ?? ""}
                      onChange={(e) => setGlossary(i, "image", e.target.value)}
                      className="h-8 text-xs"
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-rose-600 hover:text-rose-700"
                    onClick={() =>
                      setCfg({ ...cfg, glossary: cfg.glossary.filter((_, j) => j !== i) })
                    }
                    aria-label="Terimi sil"
                  >
                    <Trash2 className="size-4" aria-hidden />
                  </Button>
                </div>
                <textarea
                  placeholder="Sade açıklama (ilk kez okuyanın dili — 1-2 cümle)"
                  value={g.explanation}
                  onChange={(e) => setGlossary(i, "explanation", e.target.value)}
                  rows={2}
                  className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-xs leading-5"
                />
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
