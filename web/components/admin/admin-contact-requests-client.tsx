"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Building2,
  Inbox,
  Loader2,
  Mail,
  MailOpen,
  Phone,
  Settings2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { adminKeys, getAdminContactRequests } from "@/lib/api/admin";
import { useUpdateContactRequest } from "@/lib/hooks/use-admin-mutations";
import type {
  ContactRequestItem,
  ContactRequestListResponse,
} from "@/lib/types/admin";

interface Props {
  initial: ContactRequestListResponse;
}

const FILTERS: { value: string | null; label: string }[] = [
  { value: null, label: "Tümü" },
  { value: "new", label: "Yeni" },
  { value: "contacted", label: "İletişime geçildi" },
  { value: "closed", label: "Kapatıldı" },
];

export function AdminContactRequestsClient({ initial }: Props) {
  const [status, setStatus] = React.useState<string | null>(null);

  const q = useQuery<ContactRequestListResponse>({
    queryKey: adminKeys.contactRequests(status),
    queryFn: () => getAdminContactRequests(status),
    initialData: status === null ? initial : undefined,
    staleTime: 20_000,
  });
  const data = q.data;
  const counts = data?.counts ?? initial.counts;

  return (
    <div className="space-y-5">
      <header>
        <Link href="/admin" className="text-sm text-muted-foreground hover:text-foreground">
          ← Panel
        </Link>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Inbox className="size-6 text-indigo-700" aria-hidden />
          İletişim Talepleri
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Fiyatlandırma sayfasının kurumsal bölümünden gelen teklif/iletişim
          talepleri. Buradan durumunu işaretleyip not ekleyebilirsiniz.
        </p>
      </header>

      {/* Sayım kartları */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <CountCard label="Toplam" value={counts.total ?? 0} tone="slate" />
        <CountCard label="Yeni" value={counts.new ?? 0} tone="amber" />
        <CountCard label="İletişime geçildi" value={counts.contacted ?? 0} tone="sky" />
        <CountCard label="Kapatıldı" value={counts.closed ?? 0} tone="emerald" />
      </div>

      {/* Filtre */}
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setStatus(f.value)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-medium transition",
              status === f.value
                ? "border-indigo-600 bg-indigo-600 text-white"
                : "border-input bg-card text-muted-foreground hover:border-indigo-300",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {!data || data.items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            {q.isLoading ? (
              <Loader2 className="mx-auto size-5 animate-spin" aria-hidden />
            ) : (
              "Bu filtrede talep yok."
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Tarih</th>
                  <th className="px-4 py-2 text-left font-medium">Kişi</th>
                  <th className="px-4 py-2 text-left font-medium">Kurum</th>
                  <th className="px-4 py-2 text-left font-medium">Mesaj</th>
                  <th className="px-4 py-2 text-left font-medium">Durum</th>
                  <th className="px-4 py-2 text-right font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((it) => (
                  <ContactRow key={it.id} item={it} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function CountCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "slate" | "amber" | "sky" | "emerald";
}) {
  const cls: Record<typeof tone, string> = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    sky: "border-sky-200 bg-sky-50 text-sky-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
  };
  return (
    <div className={cn("rounded-xl border p-4", cls[tone])}>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-xs font-medium opacity-80">{label}</div>
    </div>
  );
}

function ContactRow({ item }: { item: ContactRequestItem }) {
  return (
    <tr className={cn(item.status === "new" && "bg-amber-50/30")}>
      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground tabular-nums">
        {formatDateTime(item.created_at)}
      </td>
      <td className="px-4 py-3">
        <div className="font-medium">{item.name}</div>
        <a href={`mailto:${item.email}`} className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:underline">
          <Mail className="size-3" aria-hidden /> {item.email}
        </a>
        {item.phone ? (
          <a href={`tel:${item.phone.replace(/[^0-9+]/g, "")}`} className="ml-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <Phone className="size-3" aria-hidden /> {item.phone}
          </a>
        ) : null}
      </td>
      <td className="px-4 py-3 text-xs">
        {item.institution_name ? (
          <span className="inline-flex items-center gap-1">
            <Building2 className="size-3 text-muted-foreground" aria-hidden /> {item.institution_name}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
        {item.coach_count != null ? (
          <div className="text-muted-foreground">{item.coach_count} koç</div>
        ) : null}
        <div className="mt-0.5 text-[11px] text-muted-foreground/70">{item.source_label}</div>
      </td>
      <td className="max-w-xs px-4 py-3 text-xs text-foreground/80">
        {item.message ? <span className="line-clamp-3">{item.message}</span> : <span className="text-muted-foreground">—</span>}
        {item.admin_note ? (
          <div className="mt-1 rounded bg-muted/60 px-2 py-1 text-[11px] text-muted-foreground">
            Not: {item.admin_note}
          </div>
        ) : null}
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={item.status} label={item.status_label} />
      </td>
      <td className="px-4 py-3 text-right">
        <ManageDialog item={item} />
      </td>
    </tr>
  );
}

function StatusBadge({ status, label }: { status: string; label: string }) {
  const cls: Record<string, string> = {
    new: "bg-amber-50 text-amber-700 border-amber-200",
    contacted: "bg-sky-50 text-sky-700 border-sky-200",
    closed: "bg-slate-100 text-slate-600 border-slate-200",
  };
  return (
    <span className={cn("inline-flex items-center rounded border px-2 py-0.5 text-xs", cls[status] ?? cls.closed)}>
      {label}
    </span>
  );
}

function ManageDialog({ item }: { item: ContactRequestItem }) {
  const mut = useUpdateContactRequest(item.id);
  const [open, setOpen] = React.useState(false);
  const [status, setStatus] = React.useState(item.status);
  const [note, setNote] = React.useState(item.admin_note ?? "");

  function save() {
    mut.mutate(
      { status, admin_note: note.trim() || undefined },
      { onSuccess: () => setOpen(false) },
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800"
      >
        <Settings2 className="size-3.5" aria-hidden /> Yönet
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="inline-flex items-center gap-2">
              <MailOpen className="size-4 text-indigo-700" aria-hidden />
              Talebi yönet
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs">
              <div className="font-medium">{item.name} · {item.email}</div>
              {item.institution_name ? <div className="text-muted-foreground">{item.institution_name}{item.coach_count != null ? ` · ${item.coach_count} koç` : ""}</div> : null}
              {item.message ? <p className="mt-1 text-muted-foreground">{item.message}</p> : null}
              {item.linked_user_id ? (
                <Link
                  href={`/admin/users/${item.linked_user_id}`}
                  className="mt-2 inline-flex items-center gap-1 font-medium text-indigo-600 hover:underline"
                >
                  <ArrowUpRight className="size-3.5" aria-hidden /> Koç sayfasına git (aboneliği aktive et)
                </Link>
              ) : null}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">Durum</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full rounded border border-input bg-card px-3 py-2 text-sm"
              >
                <option value="new">Yeni</option>
                <option value="contacted">İletişime geçildi</option>
                <option value="closed">Kapatıldı</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">Not (yalnız yönetim görür)</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                placeholder="Görüşme notu, sonraki adım…"
                className="w-full rounded border border-input bg-card px-3 py-2 text-sm"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 pt-2">
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={mut.isPending}>
              Vazgeç
            </Button>
            <Button onClick={save} disabled={mut.isPending} className="bg-indigo-600 text-white hover:bg-indigo-700">
              {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              Kaydet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function formatDateTime(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}
