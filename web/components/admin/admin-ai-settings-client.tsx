"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Check,
  Loader2,
  Lock,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { adminKeys, getAdminAiSettings } from "@/lib/api/admin";
import {
  useDeleteAiSetting,
  useSetAiSetting,
  useTestAiKeys,
} from "@/lib/hooks/use-admin-mutations";
import type {
  AiHealthProbe,
  AiSettingItem,
  AiSettingsResponse,
} from "@/lib/types/admin";

const SOURCE_LABELS: Record<string, { label: string; tone: string }> = {
  db: { label: "Panelden", tone: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200" },
  env: { label: ".env'den", tone: "border-sky-200 bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200" },
  default: { label: "Varsayılan", tone: "border-slate-200 bg-slate-50 text-slate-600 dark:bg-slate-500/10 dark:border-slate-500/30" },
  none: { label: "Ayarlı değil", tone: "border-amber-200 bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200" },
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

      <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
        <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>
          <strong>KVKK:</strong> Öğrenci verili işler (fotoğraf/ses/içgörü) yalnız{" "}
          <strong>ÜCRETLİ</strong> anahtarı kullanır (no-training). Ücretsiz anahtar
          yalnız kişisel veri içermeyen kitap şablonu önerisinde kullanılır; kota
          dolunca ücretliye düşer.
        </span>
      </div>

      <HealthCard />

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

/**
 * Bağlantı sağlığı — anahtarları GERÇEK (minik) çağrıyla dener.
 *
 * 2026-07-14: canlıda AI sessizce durdu (Google faturalandırma askısı → proje
 * 403 "denied access" + ücretsiz katmana düşüp 429). Panelden anlamanın yolu
 * yoktu; ancak bir özelliği deneyip 502 alınca fark ediliyordu.
 */
function HealthCard() {
  const test = useTestAiKeys();
  const h = test.data;

  const overallTone =
    h?.overall === "ok"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200"
      : h?.overall === "degraded"
        ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200"
        : "border-rose-200 bg-rose-50 text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200";

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              Bağlantı sağlığı
            </h2>
            <p className="text-xs text-muted-foreground">
              Anahtarları Google&apos;a küçük bir istekle dener. Kredi düşmez.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5"
            disabled={test.isPending}
            onClick={() => test.mutate()}
          >
            {test.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Activity className="size-4" aria-hidden />
            )}
            Bağlantıyı test et
          </Button>
        </div>

        {h ? (
          <>
            <div className={cn("rounded-md border px-3 py-2 text-sm font-medium", overallTone)}>
              {h.headline}
            </div>
            <ul className="space-y-2">
              {h.probes.map((p) => (
                <ProbeRow key={`${p.slot}-${p.model}`} probe={p} />
              ))}
            </ul>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

const PROBE_TONE: Record<string, string> = {
  ok: "border-emerald-200 bg-emerald-50 dark:border-emerald-500/30 dark:bg-emerald-500/10",
  quota: "border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10",
  denied: "border-rose-200 bg-rose-50 dark:border-rose-500/30 dark:bg-rose-500/10",
  invalid_key: "border-rose-200 bg-rose-50 dark:border-rose-500/30 dark:bg-rose-500/10",
  not_set: "border-slate-200 bg-slate-50 dark:border-slate-500/30 dark:bg-slate-500/10",
  network: "border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10",
  unknown: "border-slate-200 bg-slate-50 dark:border-slate-500/30 dark:bg-slate-500/10",
};

const PROBE_LABEL: Record<string, string> = {
  ok: "Çalışıyor",
  quota: "Kota doldu",
  denied: "Erişim reddedildi",
  invalid_key: "Anahtar geçersiz",
  not_set: "Tanımlı değil",
  network: "Ulaşılamadı",
  unknown: "Bilinmiyor",
};

function ProbeRow({ probe }: { probe: AiHealthProbe }) {
  const ok = probe.status === "ok";
  return (
    <li className={cn("rounded-md border px-3 py-2", PROBE_TONE[probe.status])}>
      <div className="flex flex-wrap items-center gap-2">
        {ok ? (
          <Check className="size-4 text-emerald-700 dark:text-emerald-300" aria-hidden />
        ) : (
          <AlertTriangle className="size-4 text-rose-700 dark:text-rose-300" aria-hidden />
        )}
        <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
          {probe.label}
        </span>
        <span className="rounded bg-slate-900/5 px-1.5 py-0.5 font-mono text-[10px] text-slate-700 dark:bg-white/10 dark:text-slate-300">
          {probe.model}
        </span>
        <span className="ml-auto text-xs font-semibold text-slate-800 dark:text-slate-200">
          {PROBE_LABEL[probe.status]}
          {probe.http_status ? ` · HTTP ${probe.http_status}` : ""}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-800 dark:text-slate-200">{probe.summary}</p>
      {probe.action ? (
        <p className="mt-0.5 text-xs font-medium text-slate-900 dark:text-slate-100">
          → {probe.action}
        </p>
      ) : null}
      {probe.raw_message ? (
        <details className="mt-1">
          <summary className="cursor-pointer text-[11px] text-slate-600 dark:text-slate-400">
            Google&apos;ın ham mesajı
          </summary>
          <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded bg-slate-900/5 p-2 text-[10px] text-slate-700 dark:bg-black/30 dark:text-slate-300">
            {probe.raw_message}
          </pre>
        </details>
      ) : null}
    </li>
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
