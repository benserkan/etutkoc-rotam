"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, Loader2, Save, UserRound, Users } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  useCreateCampaign,
  usePreviewCampaign,
} from "@/lib/hooks/use-admin-mutations";
import type {
  CampaignFormMeta,
  CampaignPreviewResponse,
} from "@/lib/types/admin";
import { fieldClass } from "@/components/admin/feature-catalog-ui";

interface Props {
  meta: CampaignFormMeta;
}

export function AdminCampaignFormClient({ meta }: Props) {
  const router = useRouter();
  const createMut = useCreateCampaign();
  const previewMut = usePreviewCampaign();

  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [adminNote, setAdminNote] = React.useState("");
  const [segment, setSegment] = React.useState("");
  const [filterPlan, setFilterPlan] = React.useState("");
  const [expires, setExpires] = React.useState("14");
  // Variant A
  const [aKind, setAKind] = React.useState(meta.offer_kinds[0]?.value ?? "discount_percent");
  const [aTitle, setATitle] = React.useState("");
  const [aValue, setAValue] = React.useState("");
  const [aDuration, setADuration] = React.useState("");
  const [aPlan, setAPlan] = React.useState("");
  const [aMsg, setAMsg] = React.useState("");
  // Variant B
  const [hasB, setHasB] = React.useState(false);
  const [bKind, setBKind] = React.useState(meta.offer_kinds[1]?.value ?? "trial_extension");
  const [bTitle, setBTitle] = React.useState("");
  const [bValue, setBValue] = React.useState("");
  const [bDuration, setBDuration] = React.useState("");
  const [bPlan, setBPlan] = React.useState("");
  const [bMsg, setBMsg] = React.useState("");

  const [preview, setPreview] = React.useState<CampaignPreviewResponse | null>(null);

  function runPreview(seg: string, plan: string) {
    if (!seg) {
      setPreview(null);
      return;
    }
    previewMut.mutate({ segment: seg, filter_plan: plan }, { onSuccess: (r) => setPreview(r) });
  }

  function onSelectSegment(value: string) {
    setSegment(value);
    runPreview(value, filterPlan);
  }

  function num(s: string): number | null {
    const t = s.trim();
    return t ? Number(t.replace(",", ".")) : null;
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !segment || !aTitle.trim()) return;
    createMut.mutate(
      {
        name: name.trim(),
        segment,
        filter_plan: filterPlan.trim(),
        description: description.trim(),
        admin_note: adminNote.trim(),
        variant_a_kind: aKind,
        variant_a_title: aTitle.trim(),
        variant_a_value: num(aValue),
        variant_a_duration_months: num(aDuration),
        variant_a_new_plan: aPlan.trim(),
        variant_a_public_message: aMsg.trim(),
        has_variant_b: hasB,
        variant_b_kind: hasB ? bKind : "",
        variant_b_title: hasB ? bTitle.trim() : "",
        variant_b_value: hasB ? num(bValue) : null,
        variant_b_duration_months: hasB ? num(bDuration) : null,
        variant_b_new_plan: hasB ? bPlan.trim() : "",
        variant_b_public_message: hasB ? bMsg.trim() : "",
        offer_expires_in_days: Number(expires) || 14,
      },
      {
        onSuccess: (res) => {
          const id = res.data.campaign_id;
          if (id) router.push(`/admin/revenue/campaigns/${id}`);
          else router.push("/admin/revenue/campaigns");
        },
      },
    );
  }

  return (
    <div className="space-y-5">
      <header>
        <Link href="/admin/revenue/campaigns" className="text-sm text-muted-foreground hover:text-foreground">
          ← Kampanyalar
        </Link>
        <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight">Yeni Toplu Kampanya</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Segment seç, teklif tasarla, A/B varyant ekle (opsiyonel). Kaydedildikten
          sonra detay sayfasından başlat. Kurumlar + bağımsız öğretmenler birlikte hedeflenir.
        </p>
      </header>

      <form onSubmit={submit} className="space-y-5">
        {/* 1. Temel bilgi */}
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold">1. Temel Bilgi</h2>
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs text-muted-foreground">Kampanya adı *</span>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} required maxLength={255}
                     placeholder="ör. Trial sonu son uyarı — Mart 2026" className={cn(fieldClass, "mt-1")} />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Açıklama</span>
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={cn(fieldClass, "mt-1")} />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">İç not (görünmez)</span>
              <textarea value={adminNote} onChange={(e) => setAdminNote(e.target.value)} rows={2} className={cn(fieldClass, "mt-1")} />
            </label>
          </div>
        </Card>

        {/* 2. Segment */}
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold">2. Hedef Segment</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {meta.segments.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => onSelectSegment(s.value)}
                className={cn(
                  "rounded-lg border-2 p-3 text-left transition-colors",
                  segment === s.value ? "border-indigo-500 bg-indigo-50/50" : "border-border hover:border-foreground/30",
                )}
              >
                <div className="text-sm font-semibold">{s.label}</div>
                <div className="mt-1 text-xs text-muted-foreground">{s.description}</div>
                <div className="mt-1 font-mono text-[10px] text-muted-foreground/70">{s.value}</div>
              </button>
            ))}
          </div>
          <label className="mt-3 block">
            <span className="text-xs text-muted-foreground">
              Özel plan filtresi (yalnız &quot;Belirli plandakiler&quot; segmenti için)
            </span>
            <input type="text" value={filterPlan}
                   onChange={(e) => setFilterPlan(e.target.value)}
                   onBlur={() => segment && runPreview(segment, filterPlan)}
                   maxLength={32} placeholder="ör. solo_free"
                   className={cn(fieldClass, "mt-1 w-full font-mono md:w-64")} />
          </label>

          {/* Canlı önizleme */}
          <div className="mt-4">
            {previewMut.isPending ? (
              <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Hesaplanıyor…
              </div>
            ) : preview ? (
              <div className={cn(
                "rounded-lg border p-3",
                preview.count > 0 ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50",
              )}>
                <div className={cn("text-sm font-semibold", preview.count > 0 ? "text-emerald-900" : "text-amber-900")}>
                  {preview.count === 0 ? "Bu segmentte şu anda hedef bulunamadı." : `${preview.count} hedef`}
                  {preview.count > 0 ? (
                    <span className="ml-1 inline-flex items-center gap-2 text-xs font-normal">
                      <span className="inline-flex items-center gap-0.5"><Building2 className="size-3.5" aria-hidden />{preview.inst_count}</span>
                      <span className="inline-flex items-center gap-0.5"><UserRound className="size-3.5" aria-hidden />{preview.user_count}</span>
                    </span>
                  ) : null}
                </div>
                {preview.preview.length > 0 ? (
                  <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                    {preview.preview.map((o) => (
                      <li key={`${o.owner_type}-${o.owner_id}`} className="flex items-center gap-2">
                        {o.owner_type === "institution" ? <Building2 className="size-3" aria-hidden /> : <UserRound className="size-3" aria-hidden />}
                        <span>{o.name}</span>
                        <span className="font-mono text-[10px] text-muted-foreground/70">{o.plan}</span>
                      </li>
                    ))}
                    {preview.count > preview.preview.length ? (
                      <li className="text-muted-foreground/70">… ve {preview.count - preview.preview.length} hedef daha</li>
                    ) : null}
                  </ul>
                ) : null}
              </div>
            ) : (
              <div className="inline-flex items-center gap-1.5 text-xs italic text-muted-foreground">
                <Users className="size-3.5" aria-hidden /> Segment seç → eligible hedef sayısı burada görünür.
              </div>
            )}
          </div>
        </Card>

        {/* 3. Variant A */}
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold">3. Teklif — Varyant A *</h2>
          <VariantFields
            kinds={meta.offer_kinds}
            kind={aKind} setKind={setAKind}
            title={aTitle} setTitle={setATitle}
            value={aValue} setValue={setAValue}
            duration={aDuration} setDuration={setADuration}
            plan={aPlan} setPlan={setAPlan}
            msg={aMsg} setMsg={setAMsg}
            required
          />
        </Card>

        {/* 4. Variant B */}
        <Card className="p-5">
          <label className="flex items-start gap-2">
            <input type="checkbox" checked={hasB} onChange={(e) => setHasB(e.target.checked)} className="mt-1 rounded border-input" />
            <div>
              <div className="text-sm font-semibold">4. A/B Testi — Varyant B ekle (opsiyonel)</div>
              <div className="mt-1 text-xs text-muted-foreground">
                Hedeflerin yarısına A, diğer yarısına B gider; hangisinin daha çok kabul aldığı detayda görünür.
              </div>
            </div>
          </label>
          {hasB ? (
            <div className="mt-4 border-t border-border pt-4">
              <VariantFields
                kinds={meta.offer_kinds}
                kind={bKind} setKind={setBKind}
                title={bTitle} setTitle={setBTitle}
                value={bValue} setValue={setBValue}
                duration={bDuration} setDuration={setBDuration}
                plan={bPlan} setPlan={setBPlan}
                msg={bMsg} setMsg={setBMsg}
              />
            </div>
          ) : null}
        </Card>

        {/* 5. Süre */}
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold">5. Süre</h2>
          <label className="block">
            <span className="text-xs text-muted-foreground">Teklif geçerlilik süresi (gün)</span>
            <input type="number" min="1" max="365" value={expires} onChange={(e) => setExpires(e.target.value)}
                   className={cn(fieldClass, "mt-1 w-32")} />
          </label>
        </Card>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={createMut.isPending} className="bg-indigo-600 text-white hover:bg-indigo-700">
            {createMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Save className="size-4" aria-hidden />}
            Taslak olarak kaydet
          </Button>
          <Link href="/admin/revenue/campaigns" className="text-sm text-muted-foreground hover:text-foreground">İptal</Link>
          <span className="text-xs text-muted-foreground">Kaydedildikten sonra detay sayfasından &quot;Başlat&quot; → e-postalar gider.</span>
        </div>
      </form>
    </div>
  );
}

function VariantFields({
  kinds, kind, setKind, title, setTitle, value, setValue,
  duration, setDuration, plan, setPlan, msg, setMsg, required,
}: {
  kinds: { value: string; label: string }[];
  kind: string; setKind: (v: string) => void;
  title: string; setTitle: (v: string) => void;
  value: string; setValue: (v: string) => void;
  duration: string; setDuration: (v: string) => void;
  plan: string; setPlan: (v: string) => void;
  msg: string; setMsg: (v: string) => void;
  required?: boolean;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      <label className="block">
        <span className="text-xs text-muted-foreground">Teklif türü{required ? " *" : ""}</span>
        <select value={kind} onChange={(e) => setKind(e.target.value)} className={cn(fieldClass, "mt-1")}>
          {kinds.map((k) => (
            <option key={k.value} value={k.value}>{k.label}</option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="text-xs text-muted-foreground">Başlık{required ? " *" : ""}</span>
        <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} required={required} maxLength={255}
               placeholder="ör. 3 ay %20 indirim" className={cn(fieldClass, "mt-1")} />
      </label>
      <label className="block">
        <span className="text-xs text-muted-foreground">Değer</span>
        <input type="number" step="0.01" min="0" value={value} onChange={(e) => setValue(e.target.value)} className={cn(fieldClass, "mt-1")} />
      </label>
      <label className="block">
        <span className="text-xs text-muted-foreground">Süre (ay)</span>
        <input type="number" min="1" max="999" value={duration} onChange={(e) => setDuration(e.target.value)} className={cn(fieldClass, "mt-1")} />
      </label>
      <label className="block md:col-span-2">
        <span className="text-xs text-muted-foreground">Yeni plan (yükseltme için)</span>
        <input type="text" value={plan} onChange={(e) => setPlan(e.target.value)} maxLength={32}
               placeholder="solo_pro" className={cn(fieldClass, "mt-1 font-mono")} />
      </label>
      <label className="block md:col-span-2">
        <span className="text-xs text-muted-foreground">Hedefe mesaj</span>
        <textarea value={msg} onChange={(e) => setMsg(e.target.value)} rows={2} className={cn(fieldClass, "mt-1")} />
      </label>
    </div>
  );
}
