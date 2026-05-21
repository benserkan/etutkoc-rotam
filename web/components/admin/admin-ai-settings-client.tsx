"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Loader2, Lock, Save, ShieldCheck, Sparkles, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { adminKeys, getAdminAiSettings } from "@/lib/api/admin";
import { useSetAiSetting, useDeleteAiSetting } from "@/lib/hooks/use-admin-mutations";
import type { AiSettingItem, AiSettingsResponse } from "@/lib/types/admin";

const SOURCE_LABELS: Record<string, { label: string; tone: string }> = {
  db: { label: "Panelden", tone: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  env: { label: ".env'den", tone: "border-sky-200 bg-sky-50 text-sky-700" },
  default: { label: "Varsayılan", tone: "border-slate-200 bg-slate-50 text-slate-600" },
  none: { label: "Ayarlı değil", tone: "border-amber-200 bg-amber-50 text-amber-800" },
};

export function AdminAiSettingsClient({ initial }: { initial: AiSettingsResponse }) {
  const q = useQuery<AiSettingsResponse>({
    queryKey: adminKeys.aiSettings(),
    queryFn: getAdminAiSettings,
    initialData: initial,
    staleTime: 30_000,
  });
  const items = q.data?.items ?? [];
  const get = (name: string) => items.find((i) => i.name === name);

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <Sparkles className="size-5 text-cyan-700" aria-hidden /> AI Ayarları (Gemini)
        </h1>
        <p className="text-sm text-muted-foreground">
          Tek sağlayıcı Gemini. Buraya girilen anahtarları <strong>tüm sistem</strong>{" "}
          kullanır; anahtarlar şifreli saklanır ve maskeli gösterilir.
        </p>
      </header>

      <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
        <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>
          <strong>KVKK:</strong> Öğrenci verili işler (fotoğraf/ses/içgörü) yalnız{" "}
          <strong>ÜCRETLİ</strong> anahtarı kullanır (no-training). Ücretsiz anahtar
          yalnız kişisel veri içermeyen kitap şablonu önerisinde kullanılır; kota
          dolunca ücretliye düşer.
        </span>
      </div>

      {get("gemini_paid_api_key") ? (
        <SecretCard item={get("gemini_paid_api_key")!} placeholder="AIza... (ücretli)" />
      ) : null}
      {get("gemini_paid_model") ? (
        <ModelCard item={get("gemini_paid_model")!} placeholder="gemini-2.5-pro" />
      ) : null}
      {get("gemini_free_api_key") ? (
        <SecretCard item={get("gemini_free_api_key")!} placeholder="AIza... (ücretsiz, opsiyonel)" />
      ) : null}
      {get("gemini_free_model") ? (
        <ModelCard item={get("gemini_free_model")!} placeholder="gemini-2.5-flash" />
      ) : null}

      <p className="text-[11px] text-muted-foreground">
        Çoklu ücretsiz anahtar için sunucu <code>.env</code> içinde{" "}
        <code>GEMINI_FREE_API_KEYS</code> (virgülle) kullanılabilir; kota dolunca sıradakine geçer.
      </p>
    </div>
  );
}

function SourceBadge({ source }: { source: string }) {
  const s = SOURCE_LABELS[source] ?? SOURCE_LABELS.none;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] font-medium", s.tone)}>
      {source === "none" ? <Lock className="size-3" aria-hidden /> : <Check className="size-3" aria-hidden />}
      {s.label}
    </span>
  );
}

function SecretCard({ item, placeholder }: { item: AiSettingItem; placeholder: string }) {
  const setIt = useSetAiSetting();
  const delIt = useDeleteAiSetting();
  const [value, setValue] = React.useState("");
  const [confirm, setConfirm] = React.useState(false);

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-medium">{item.label}</h2>
          <SourceBadge source={item.source} />
        </div>
        {item.is_set ? (
          <div className="rounded-md bg-muted/50 px-3 py-2 text-sm">
            Mevcut: <code className="font-mono">{item.value || "••••"}</code>
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            className="min-w-[220px] flex-1 font-mono"
          />
          <Button
            onClick={() => setIt.mutate({ name: item.name, value: value.trim() }, { onSuccess: () => setValue("") })}
            disabled={!value.trim() || setIt.isPending}
          >
            {setIt.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Save className="size-4" aria-hidden />}
            Kaydet
          </Button>
        </div>
        {item.source === "db" ? (
          confirm ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-rose-700">Silinsin mi?</span>
              <Button size="sm" variant="ghost" onClick={() => setConfirm(false)} disabled={delIt.isPending}>Vazgeç</Button>
              <Button size="sm" variant="destructive" onClick={() => delIt.mutate({ name: item.name }, { onSuccess: () => setConfirm(false) })} disabled={delIt.isPending}>
                {delIt.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Trash2 className="size-4" aria-hidden />} Sil
              </Button>
            </div>
          ) : (
            <button type="button" onClick={() => setConfirm(true)} className="text-xs text-rose-600 hover:underline">
              Anahtarı sil
            </button>
          )
        ) : null}
      </CardContent>
    </Card>
  );
}

function ModelCard({ item, placeholder }: { item: AiSettingItem; placeholder: string }) {
  const setIt = useSetAiSetting();
  const [value, setValue] = React.useState(item.value ?? "");

  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label htmlFor={`m-${item.name}`} className="font-medium">{item.label}</Label>
          <SourceBadge source={item.source} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Input
            id={`m-${item.name}`}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            className="min-w-[220px] flex-1 font-mono"
          />
          <Button
            onClick={() => setIt.mutate({ name: item.name, value: value.trim() })}
            disabled={!value.trim() || value.trim() === item.value || setIt.isPending}
          >
            {setIt.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Save className="size-4" aria-hidden />}
            Kaydet
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
