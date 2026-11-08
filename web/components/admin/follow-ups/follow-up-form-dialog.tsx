"use client";

import * as React from "react";
import { Gauge } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useCreateFollowUp, useUpdateFollowUp } from "@/lib/hooks/use-follow-up-mutations";
import type { FollowUpItem, FollowUpListResponse } from "@/lib/types/follow-ups";

import { fmtDate, isoToday } from "./shared";

const QUICK_DUE = [
  { label: "1 hafta", days: 7 },
  { label: "2 hafta", days: 14 },
  { label: "3 hafta", days: 21 },
  { label: "1 ay", days: 30 },
];

const RECURRENCE = [
  { v: "", label: "Tek seferlik" },
  { v: "7", label: "Her hafta" },
  { v: "14", label: "2 haftada bir" },
  { v: "21", label: "3 haftada bir" },
  { v: "28", label: "4 haftada bir" },
  { v: "90", label: "3 ayda bir" },
];

const selectCls =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  meta: FollowUpListResponse["meta"];
  /** Düzenleme; yoksa yeni kayıt */
  item?: FollowUpItem | null;
  /** Yeni kayıtta ön-dolu ölçü (Ölçümler sayfasından "takip ekle") */
  presetMetric?: string;
}

/** Açılınca yeniden bağlanır (key) — durum kayıttan/ön-değerden kurulur. */
export function FollowUpFormDialog(props: Props) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        {props.open ? <FormBody {...props} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function FormBody({ onOpenChange, meta, item, presetMetric }: Props) {
  const create = useCreateFollowUp();
  const update = useUpdateFollowUp();
  const editing = !!item;
  const [title, setTitle] = React.useState(item?.title ?? "");
  const [desc, setDesc] = React.useState(item?.description ?? "");
  const [due, setDue] = React.useState(item?.due_on ?? isoToday(14));
  const [category, setCategory] = React.useState(item?.category ?? (presetMetric ? "olcum" : "diger"));
  const [priority, setPriority] = React.useState<string>(item?.priority ?? "normal");
  const [recurrence, setRecurrence] = React.useState(
    item?.recurrence_days ? String(item.recurrence_days) : "",
  );
  const [useMetric, setUseMetric] = React.useState(!!item?.check || !!presetMetric);
  const firstMetric = presetMetric ?? item?.check?.metric_key ?? meta.metrics[0]?.key ?? "";
  const [metricKey, setMetricKey] = React.useState(firstMetric);
  const metric = meta.metrics.find((m) => m.key === metricKey);
  const [owner, setOwner] = React.useState<string>(
    item?.check?.owner_type ?? (metric?.owners.includes("coach") ? "coach" : "system"),
  );
  const [minChange, setMinChange] = React.useState(String(item?.check?.min_change ?? 3));
  const [baseline, setBaseline] = React.useState(item?.baseline_on ?? isoToday());

  const pending = create.isPending || update.isPending;
  const ownerOk = metric ? metric.owners.includes(owner as "system" | "coach") : false;
  const canSave = title.trim().length > 0 && !!due && (!useMetric || (metric && ownerOk));

  function changeMetric(k: string) {
    setMetricKey(k);
    const m = meta.metrics.find((x) => x.key === k);
    if (m && !m.owners.includes(owner as "system" | "coach")) setOwner(m.owners[0]);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSave) return;
    const check = useMetric
      ? { metric_key: metricKey, owner_type: owner, min_change: Number(minChange) || 3 }
      : null;
    const base = {
      title: title.trim(),
      description: desc.trim() || null,
      due_on: due,
      category,
      priority,
    };
    const done = () => onOpenChange(false);
    if (editing && item) {
      update.mutate(
        {
          id: item.id,
          body: {
            ...base,
            ...(recurrence ? { recurrence_days: Number(recurrence) } : { clear_recurrence: true }),
            ...(check ? { check, baseline_on: baseline } : { clear_check: true }),
          },
        },
        { onSuccess: done },
      );
    } else {
      create.mutate(
        {
          ...base,
          recurrence_days: recurrence ? Number(recurrence) : null,
          check,
          baseline_on: check ? baseline : null,
        },
        { onSuccess: done },
      );
    }
  }

  return (
    <form method="post" onSubmit={submit} className="space-y-4">
      <DialogHeader>
        <DialogTitle>{editing ? "Takibi düzenle" : "Takip listesine ekle"}</DialogTitle>
        <DialogDescription>
          Vadesi gelince panelde rozet çıkar ve sana e-posta + bildirim gider. Bir ölçüye
          bağlarsan sonucu sistem kendisi hesaplar.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-1.5">
        <label className="text-sm font-medium" htmlFor="fu-title">Ne yapılacak?</label>
        <Input id="fu-title" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)}
          placeholder="örn. Öneri motoru isabetini yeniden değerlendir" />
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium" htmlFor="fu-desc">Ayrıntı / nasıl yapılacak</label>
        <textarea id="fu-desc" value={desc} onChange={(e) => setDesc(e.target.value)} rows={3}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          placeholder="Bakılacaklar, komutlar, kime sorulacak…" />
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium" htmlFor="fu-due">Ne zaman?</label>
        <div className="flex flex-wrap items-center gap-2">
          <Input id="fu-due" type="date" value={due} min={isoToday()} onChange={(e) => setDue(e.target.value)}
            className="w-44" />
          {QUICK_DUE.map((q) => (
            <button key={q.days} type="button" onClick={() => setDue(isoToday(q.days))}
              className={cn("rounded-full border px-3 py-1 text-xs",
                due === isoToday(q.days) ? "border-cyan-700 bg-cyan-700 text-white" : "border-border hover:bg-muted")}>
              {q.label} sonra
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="fu-cat">Kategori</label>
          <select id="fu-cat" value={category} onChange={(e) => setCategory(e.target.value)} className={selectCls}>
            {Object.entries(meta.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="fu-pri">Öncelik</label>
          <select id="fu-pri" value={priority} onChange={(e) => setPriority(e.target.value)} className={selectCls}>
            {Object.entries(meta.priorities).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="fu-rec">Tekrar</label>
          <select id="fu-rec" value={recurrence} onChange={(e) => setRecurrence(e.target.value)} className={selectCls}>
            {RECURRENCE.map((r) => <option key={r.v} value={r.v}>{r.label}</option>)}
          </select>
        </div>
      </div>
      {recurrence ? (
        <p className="text-xs text-muted-foreground">
          Tamamlayınca aynı iş {recurrence} gün sonrası için kendiliğinden yeniden açılır.
        </p>
      ) : null}

      <div className="rounded-lg border border-border p-3">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={useMetric} onChange={(e) => setUseMetric(e.target.checked)} />
          <Gauge className="size-4 text-cyan-700" aria-hidden />
          Bir ölçüye bağla — sonucu sistem hesaplasın
        </label>
        {useMetric ? (
          <div className="mt-3 space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground" htmlFor="fu-metric">Ölçü</label>
                <select id="fu-metric" value={metricKey} onChange={(e) => changeMetric(e.target.value)} className={selectCls}>
                  {meta.metrics.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground" htmlFor="fu-owner">Kapsam</label>
                <select id="fu-owner" value={owner} onChange={(e) => setOwner(e.target.value)} className={selectCls}>
                  {(metric?.owners ?? []).map((o) => (
                    <option key={o} value={o}>{meta.owner_types[o] ?? o}</option>
                  ))}
                </select>
              </div>
            </div>
            {metric ? <p className="text-xs text-muted-foreground">{metric.description}</p> : null}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground" htmlFor="fu-base">
                  Karşılaştırma başlangıcı
                </label>
                <Input id="fu-base" type="date" value={baseline} max={isoToday()}
                  onChange={(e) => setBaseline(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground" htmlFor="fu-min">
                  Anlamlı değişim eşiği {metric?.unit === "%" ? "(puan)" : ""}
                </label>
                <Input id="fu-min" type="number" min={0.5} max={50} step={0.5} value={minChange}
                  onChange={(e) => setMinChange(e.target.value)} />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Vade günü {fmtDate(baseline)} değeri ile son değer karşılaştırılır; eşiği aşan düşüş
              ya da yükseliş {owner === "coach" ? "koç adıyla" : ""} rapora yazılır.
              {metric && metric.min_sample > 0
                ? ` ${metric.min_sample} örneğin altındaki değerler karar vermez.`
                : ""}
            </p>
          </div>
        ) : null}
      </div>

      <DialogFooter>
        <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Vazgeç</Button>
        <Button type="submit" disabled={!canSave || pending} className="bg-cyan-700 text-white hover:bg-cyan-800">
          {pending ? "Kaydediliyor…" : editing ? "Kaydet" : "Listeye ekle"}
        </Button>
      </DialogFooter>
    </form>
  );
}
