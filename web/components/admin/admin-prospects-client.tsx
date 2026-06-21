"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, Gift, MessageCircle, Pencil, Plus, Search, Trash2, X } from "lucide-react";

import { adminKeys, getAdminProspects } from "@/lib/api/admin";
import {
  useCreateProspect, useUpdateProspect, useSetProspectStatus, useDeleteProspect,
  useCreateProspectOffer,
} from "@/lib/hooks/use-admin-mutations";
import type { ProspectItem, ProspectListResponse, ProspectPlanOption } from "@/lib/types/admin";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const STATUS_TONE: Record<string, string> = {
  new: "bg-sky-50 text-sky-800 border-sky-200 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
  contacted: "bg-indigo-50 text-indigo-800 border-indigo-200 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
  interested: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  member: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  not_interested: "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-300",
  unreachable: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
};

export function AdminProspectsClient({ initial }: { initial: ProspectListResponse }) {
  const [status, setStatus] = React.useState("");
  const [kind, setKind] = React.useState("");
  const [searchInput, setSearchInput] = React.useState("");
  const [q, setQ] = React.useState("");
  const [createOpen, setCreateOpen] = React.useState(false);
  const [editRow, setEditRow] = React.useState<ProspectItem | null>(null);
  const [offerRow, setOfferRow] = React.useState<ProspectItem | null>(null);

  React.useEffect(() => {
    const t = setTimeout(() => setQ(searchInput.trim()), 350);
    return () => clearTimeout(t);
  }, [searchInput]);

  const query = useQuery({
    queryKey: adminKeys.prospects(status, kind, q),
    queryFn: () => getAdminProspects(status, kind, q),
    initialData: !status && !kind && !q ? initial : undefined,
  });
  const data = query.data ?? initial;
  const statuses = data.meta.statuses;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Hedef Havuzu</h1>
          <p className="text-sm text-muted-foreground">
            Sisteme henüz üye olmayan kurum ve bağımsız koç adayları. Tanıtım + kişiye
            özel üyelik teklifi göndereceğin satış adayları burada toplanır.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" /> Yeni Hedef
        </Button>
      </div>

      {/* Durum sayımları + filtre */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setStatus("")}
          className={cn("rounded-full border px-3 py-1 text-xs font-medium",
            status === "" ? "border-cyan-500 bg-cyan-50 text-cyan-800 dark:bg-cyan-500/10 dark:text-cyan-200" : "border-border text-muted-foreground hover:bg-muted")}
        >
          Hepsi ({Object.values(data.counts).reduce((a, b) => a + b, 0)})
        </button>
        {Object.entries(statuses).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setStatus(status === key ? "" : key)}
            className={cn("rounded-full border px-3 py-1 text-xs font-medium",
              status === key ? "border-cyan-500 bg-cyan-50 text-cyan-800 dark:bg-cyan-500/10 dark:text-cyan-200" : "border-border text-muted-foreground hover:bg-muted")}
          >
            {label} ({data.counts[key] ?? 0})
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <select value={kind} onChange={(e) => setKind(e.target.value)}
                  className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm">
            <option value="">Tüm tipler</option>
            {Object.entries(data.meta.kinds).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-slate-400" />
            <Input value={searchInput} onChange={(e) => setSearchInput(e.target.value)}
                   placeholder="Ad / telefon / kurum" className="w-52 pl-8" />
          </div>
        </div>
      </div>

      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left">Ad / Kurum</th>
              <th className="px-3 py-2 text-left">Telefon</th>
              <th className="px-3 py-2 text-left">Tip</th>
              <th className="px-3 py-2 text-left">Şehir</th>
              <th className="px-3 py-2 text-left">Durum</th>
              <th className="px-3 py-2 text-center">İzin</th>
              <th className="px-3 py-2 text-right">İşlem</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.items.map((p) => (
              <tr key={p.id} className="hover:bg-muted/30">
                <td className="px-3 py-2">
                  <div className="font-medium">{p.name}</div>
                  {p.org_name ? <div className="text-xs text-muted-foreground">{p.org_name}</div> : null}
                </td>
                <td className="px-3 py-2 tabular-nums">{p.phone}</td>
                <td className="px-3 py-2">{p.kind_label}</td>
                <td className="px-3 py-2 text-muted-foreground">{p.city ?? "—"}</td>
                <td className="px-3 py-2">
                  <StatusSelect row={p} statuses={statuses} />
                </td>
                <td className="px-3 py-2 text-center">
                  {p.opt_in ? <span className="text-emerald-600" title="WhatsApp izni var">✓</span>
                            : <span className="text-slate-400" title="İzin yok">—</span>}
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => setOfferRow(p)} title="Üyelik teklifi üret"
                            className="rounded p-1.5 text-cyan-600 hover:bg-cyan-50 dark:hover:bg-cyan-500/10">
                      <Gift className="size-4" />
                    </button>
                    <a href={`https://wa.me/${p.phone}`} target="_blank" rel="noopener noreferrer"
                       title="WhatsApp'tan yaz" className="rounded p-1.5 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-500/10">
                      <MessageCircle className="size-4" />
                    </a>
                    <button onClick={() => setEditRow(p)} title="Düzenle" className="rounded p-1.5 text-slate-500 hover:bg-muted">
                      <Pencil className="size-4" />
                    </button>
                    <DeleteButton id={p.id} name={p.name} />
                  </div>
                </td>
              </tr>
            ))}
            {data.items.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-10 text-center text-sm text-muted-foreground">
                Bu filtrelerle hedef yok. Üstteki “Yeni Hedef” ile ekle.
              </td></tr>
            )}
          </tbody>
        </table>
      </Card>

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        WhatsApp ikonu şu an telefonundan manuel mesaj açar. Kurumsal başlıklı (Cloud API)
        otomatik teklif gönderimi — Meta Business doğrulaması tamamlanınca aktive olacak (K2).
      </p>

      {createOpen ? <ProspectDialog kinds={data.meta.kinds} onClose={() => setCreateOpen(false)} /> : null}
      {editRow ? <ProspectDialog kinds={data.meta.kinds} row={editRow} onClose={() => setEditRow(null)} /> : null}
      {offerRow ? <OfferDialog row={offerRow} plans={data.meta.plans} onClose={() => setOfferRow(null)} /> : null}
    </div>
  );
}

function OfferDialog({ row, plans, onClose }: { row: ProspectItem; plans: ProspectPlanOption[]; onClose: () => void }) {
  const mut = useCreateProspectOffer(row.id);
  const [f, setF] = React.useState({
    plan_code: plans[0]?.code ?? "", cycle: "monthly", amount: "",
    title: "", message: "", expires_in_days: "7",
  });
  const [result, setResult] = React.useState<{ public_url: string; wa_url: string } | null>(null);
  const set = (k: string, v: string) => setF((s) => ({ ...s, [k]: v }));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      {
        plan_code: f.plan_code, cycle: f.cycle,
        amount: f.amount ? Number(f.amount) : null,
        title: f.title || null, message: f.message || null,
        expires_in_days: f.expires_in_days ? Number(f.expires_in_days) : null,
      },
      { onSuccess: (res) => setResult(res.data) },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{row.name} — üyelik teklifi</DialogTitle></DialogHeader>
        {result ? (
          <div className="space-y-3">
            <p className="text-sm text-emerald-700 dark:text-emerald-300">Teklif linki hazır. WhatsApp&apos;tan gönderebilirsin.</p>
            <div className="rounded-lg border border-border bg-muted/30 p-2 text-xs break-all">{result.public_url}</div>
            <div className="flex flex-wrap gap-2">
              <a href={result.wa_url} target="_blank" rel="noopener noreferrer"
                 className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700">
                <MessageCircle className="size-4" /> WhatsApp&apos;tan gönder
              </a>
              <button onClick={() => { navigator.clipboard?.writeText(result.public_url); toast.success("Link kopyalandı"); }}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm hover:bg-muted">
                <Copy className="size-4" /> Linki kopyala
              </button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Kurumsal başlıklı otomatik (Cloud API) gönderim Meta doğrulaması sonrası (K2) eklenecek.
            </p>
            <div className="flex justify-end"><Button onClick={onClose}>Kapat</Button></div>
          </div>
        ) : (
          <form onSubmit={submit} method="post" className="space-y-3">
            <div>
              <Label>Plan *</Label>
              <select value={f.plan_code} onChange={(e) => set("plan_code", e.target.value)} required
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm">
                {plans.map((p) => <option key={p.code} value={p.code}>{p.label} ({p.monthly}₺/ay)</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Döngü</Label>
                <select value={f.cycle} onChange={(e) => set("cycle", e.target.value)}
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm">
                  <option value="monthly">Aylık</option>
                  <option value="annual">Akademik Yıl</option>
                </select>
              </div>
              <div>
                <Label>Özel fiyat (₺)</Label>
                <Input value={f.amount} onChange={(e) => set("amount", e.target.value)} placeholder="boş = plan fiyatı" />
              </div>
            </div>
            <div>
              <Label>Başlık (sayfada büyük görünür)</Label>
              <Input value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="Örn. Sana özel %20 indirim" />
            </div>
            <div>
              <Label>Mesaj</Label>
              <textarea value={f.message} onChange={(e) => set("message", e.target.value)} rows={2}
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" placeholder="(opsiyonel)" />
            </div>
            <div>
              <Label>Geçerlilik (gün)</Label>
              <Input value={f.expires_in_days} onChange={(e) => set("expires_in_days", e.target.value)} className="w-24" />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="outline" onClick={onClose}>Vazgeç</Button>
              <Button type="submit" disabled={mut.isPending || !f.plan_code}>Teklif + Link üret</Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function StatusSelect({ row, statuses }: { row: ProspectItem; statuses: Record<string, string> }) {
  const mut = useSetProspectStatus(row.id);
  return (
    <select
      value={row.status}
      onChange={(e) => mut.mutate(e.target.value)}
      disabled={mut.isPending}
      className={cn("rounded border px-1.5 py-0.5 text-[11px] font-semibold", STATUS_TONE[row.status] ?? STATUS_TONE.new)}
    >
      {Object.entries(statuses).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
    </select>
  );
}

function DeleteButton({ id, name }: { id: number; name: string }) {
  const mut = useDeleteProspect(id);
  const [confirm, setConfirm] = React.useState(false);
  if (confirm) {
    return (
      <span className="inline-flex items-center gap-1">
        <button onClick={() => mut.mutate()} disabled={mut.isPending}
                className="rounded bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold text-white hover:bg-rose-700">Sil</button>
        <button onClick={() => setConfirm(false)} className="rounded p-1 text-slate-400 hover:bg-muted"><X className="size-3.5" /></button>
      </span>
    );
  }
  return (
    <button onClick={() => setConfirm(true)} title={`${name} sil`} className="rounded p-1.5 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/10">
      <Trash2 className="size-4" />
    </button>
  );
}

function ProspectDialog({ kinds, row, onClose }: { kinds: Record<string, string>; row?: ProspectItem; onClose: () => void }) {
  const isEdit = !!row;
  const create = useCreateProspect();
  const update = useUpdateProspect(row?.id ?? 0);
  const mut = isEdit ? update : create;
  const [f, setF] = React.useState({
    name: row?.name ?? "", phone: row?.phone ?? "", kind: row?.kind ?? "coach",
    org_name: row?.org_name ?? "", email: row?.email ?? "", city: row?.city ?? "",
    opt_in: row?.opt_in ?? false, note: row?.note ?? "",
  });
  const set = (k: string, v: string | boolean) => setF((s) => ({ ...s, [k]: v }));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(f as never, { onSuccess: () => onClose() });
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{isEdit ? "Hedefi düzenle" : "Yeni hedef ekle"}</DialogTitle></DialogHeader>
        <form onSubmit={submit} method="post" className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <Label>Ad Soyad *</Label>
              <Input value={f.name} onChange={(e) => set("name", e.target.value)} required placeholder="Yetkili / koç adı" />
            </div>
            <div>
              <Label>Cep Telefonu *</Label>
              <Input value={f.phone} onChange={(e) => set("phone", e.target.value)} required placeholder="05XX..." />
            </div>
            <div>
              <Label>Tip</Label>
              <select value={f.kind} onChange={(e) => set("kind", e.target.value)}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm">
                {Object.entries(kinds).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <Label>Kurum adı</Label>
              <Input value={f.org_name} onChange={(e) => set("org_name", e.target.value)} placeholder="(opsiyonel)" />
            </div>
            <div>
              <Label>E-posta</Label>
              <Input value={f.email} onChange={(e) => set("email", e.target.value)} placeholder="(opsiyonel)" />
            </div>
            <div>
              <Label>Şehir</Label>
              <Input value={f.city} onChange={(e) => set("city", e.target.value)} placeholder="(opsiyonel)" />
            </div>
            <div className="col-span-2">
              <Label>Not</Label>
              <textarea value={f.note} onChange={(e) => set("note", e.target.value)}
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" rows={2} placeholder="(opsiyonel)" />
            </div>
            <label className="col-span-2 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={f.opt_in} onChange={(e) => set("opt_in", e.target.checked)} />
              WhatsApp izni var (opt-in) — soğuk listede dikkat
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>Vazgeç</Button>
            <Button type="submit" disabled={mut.isPending}>{isEdit ? "Kaydet" : "Ekle"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
