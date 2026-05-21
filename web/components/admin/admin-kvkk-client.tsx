"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Scale, ShieldCheck, X } from "lucide-react";

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
import { adminKeys, getAdminKvkk } from "@/lib/api/admin";
import {
  useKvkkApply,
  useKvkkReject,
} from "@/lib/hooks/use-admin-mutations";
import type {
  KvkkDashboardResponse,
  KvkkRequestItem,
  KvkkRequestStatus,
} from "@/lib/types/admin";

interface Props {
  initial: KvkkDashboardResponse;
}

/**
 * KVKK denetim paneli — Jinja `kvkk_dashboard.html` feature parity.
 *
 * 5 durum sayım kartı + bekleyen talepler tablosu (apply/reject) + sistem veri
 * envanteri + son talepler özet tablosu.
 */
export function AdminKvkkClient({ initial }: Props) {
  const q = useQuery<KvkkDashboardResponse>({
    queryKey: adminKeys.kvkk(),
    queryFn: () => getAdminKvkk(),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header>
        <Link
          href="/admin"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <p className="text-[11px] uppercase tracking-wider text-rose-700 font-semibold mt-1">
          Süper Admin
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-0.5 inline-flex items-center gap-2">
          <Scale className="size-6 text-rose-700" aria-hidden />
          KVKK Denetim Paneli
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          KVKK madde 11 kapsamında alınan veri sahibi taleplerini ve sistem geneli
          kişisel veri envanterini izleyin. Beklemede olan silme talepleri 30 gün
          sonunda otomatik uygulanır; aciliyet hâlinde aşağıdan manuel
          uygulayabilirsiniz.
        </p>
      </header>

      {/* 5 durum kartı */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard label="Toplam Talep" value={data.summary.total} tone="default" />
        <StatCard
          label="İşleniyor"
          value={data.summary.processing}
          tone="amber"
        />
        <StatCard label="Bekliyor" value={data.summary.pending} tone="sky" />
        <StatCard
          label="Tamamlandı"
          value={data.summary.completed}
          tone="emerald"
        />
        <StatCard
          label="İptal/Red"
          value={data.summary.cancelled + data.summary.rejected}
          tone="slate"
        />
      </div>

      <PendingRequestsCard rows={data.pending_rows} />

      <DataInventoryCard items={data.data_inventory} />

      <RecentRequestsCard rows={data.recent_rows} />
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "default" | "amber" | "sky" | "emerald" | "slate";
}) {
  const map = {
    default: { border: "border-border", text: "text-foreground" },
    amber: { border: "border-amber-200 bg-amber-50/40", text: "text-amber-900" },
    sky: { border: "border-sky-200 bg-sky-50/40", text: "text-sky-900" },
    emerald: { border: "border-emerald-200 bg-emerald-50/40", text: "text-emerald-900" },
    slate: { border: "border-slate-200 bg-slate-50/40", text: "text-slate-900" },
  };
  const m = map[tone];
  return (
    <Card className={cn("border", m.border)}>
      <CardContent className="p-3">
        <div className="text-xs uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div className={cn("text-2xl font-bold tabular-nums mt-1", m.text)}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function PendingRequestsCard({ rows }: { rows: KvkkRequestItem[] }) {
  return (
    <Card>
      <div className="px-4 py-3 border-b border-border">
        <h2 className="font-medium">Bekleyen Talepler</h2>
      </div>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted-foreground italic">
          Bekleyen talep yok 🎉
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-muted-foreground text-xs">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Tip</th>
                <th className="text-left px-4 py-2 font-medium">Hesap</th>
                <th className="text-left px-4 py-2 font-medium">
                  Talep Tarihi
                </th>
                <th className="text-left px-4 py-2 font-medium">
                  İşleme Tarihi
                </th>
                <th className="text-left px-4 py-2 font-medium">Sebep</th>
                <th className="text-right px-4 py-2 font-medium">İşlem</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((r) => (
                <PendingRow key={r.id} req={r} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function PendingRow({ req }: { req: KvkkRequestItem }) {
  const kindTone =
    req.kind === "delete"
      ? "text-rose-700"
      : req.kind === "export"
        ? "text-sky-700"
        : "text-foreground";
  return (
    <tr>
      <td className={cn("px-4 py-2.5 font-medium", kindTone)}>
        {req.kind_label}
      </td>
      <td className="px-4 py-2.5">
        {req.target_user ? (
          <>
            {req.target_user.full_name}
            <span className="text-xs text-muted-foreground ml-1">
              ({req.target_user.email})
            </span>
          </>
        ) : (
          <span className="text-muted-foreground/60">— (silinmiş)</span>
        )}
      </td>
      <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">
        {formatDate(req.created_at)}
      </td>
      <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">
        {req.process_after ? formatDate(req.process_after) : "—"}
      </td>
      <td className="px-4 py-2.5 text-xs text-foreground/80 max-w-xs">
        {req.reason ?? "—"}
      </td>
      <td className="px-4 py-2.5 text-right whitespace-nowrap">
        {req.kind === "delete" && <ApplyButton id={req.id} />}
        {req.kind === "delete" && (
          <span className="text-muted-foreground/40 mx-1">·</span>
        )}
        <RejectButton id={req.id} />
      </td>
    </tr>
  );
}

function ApplyButton({ id }: { id: number }) {
  const router = useRouter();
  const mut = useKvkkApply(id);
  const [open, setOpen] = React.useState(false);

  function doApply() {
    mut.mutate(undefined, {
      onSuccess: () => {
        setOpen(false);
        router.refresh();
      },
    });
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-rose-600 hover:text-rose-800 font-medium px-2 inline-flex items-center gap-0.5"
      >
        <ShieldCheck className="size-3" aria-hidden />
        Hemen Uygula
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Silme Talebini Hemen Uygula</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Bu silme talebini hemen uygulamak istediğinize emin misiniz?
            <strong> Kullanıcı anonimleştirilecek</strong> (email
            <code className="text-xs bg-muted/50 px-1 mx-1 rounded">
              anonymized-&#123;id&#125;@kvkk.local
            </code>
            , şifre hash temizlenir, is_active=False).
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={doApply}
              disabled={mut.isPending}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <ShieldCheck className="size-4" aria-hidden />
              )}
              Anonimleştir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function RejectButton({ id }: { id: number }) {
  const router = useRouter();
  const mut = useKvkkReject(id);
  const [open, setOpen] = React.useState(false);
  const [note, setNote] = React.useState("Süper admin reddetti");

  function doReject() {
    mut.mutate(
      { note: note.trim() },
      {
        onSuccess: () => {
          setOpen(false);
          router.refresh();
        },
      },
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-muted-foreground hover:text-foreground font-medium px-2 inline-flex items-center gap-0.5"
      >
        <X className="size-3" aria-hidden />
        Reddet
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Talebi Reddet</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Bu talebi reddetmek istediğinize emin misiniz?
          </p>
          <div>
            <label className="text-xs font-medium block mb-1">
              Red gerekçesi (admin notu)
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              maxLength={500}
              className="w-full px-3 py-2 border border-input rounded text-sm bg-card"
            />
          </div>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={doReject}
              disabled={mut.isPending}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              Reddet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function DataInventoryCard({
  items,
}: {
  items: KvkkDashboardResponse["data_inventory"];
}) {
  return (
    <Card>
      <div className="px-4 py-3 border-b border-border">
        <h2 className="font-medium">Sistem Veri Envanteri</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          KVKK madde 10 aydınlatma metni kaynağı.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Tablo</th>
              <th className="text-left px-4 py-2 font-medium">Etiket</th>
              <th className="text-left px-4 py-2 font-medium">
                Kişisel Veri?
              </th>
              <th className="text-left px-4 py-2 font-medium">Saklama</th>
              <th className="text-left px-4 py-2 font-medium">Hukuki Temel</th>
              <th className="text-left px-4 py-2 font-medium">Amaç</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((it, idx) => (
              <tr key={idx}>
                <td className="px-4 py-2 text-xs text-muted-foreground font-mono">
                  {it.table_name}
                </td>
                <td className="px-4 py-2">{it.label}</td>
                <td className="px-4 py-2">
                  {it.contains_pii ? (
                    <span className="text-xs text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                      PII
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">Anonim</span>
                  )}
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground">
                  {it.retention_days != null
                    ? `${it.retention_days} gün`
                    : "Sözleşme süresince"}
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground">
                  {it.legal_basis}
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground">
                  {it.purpose}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function RecentRequestsCard({ rows }: { rows: KvkkRequestItem[] }) {
  return (
    <Card>
      <div className="px-4 py-3 border-b border-border">
        <h2 className="font-medium">Son Talepler (20)</h2>
      </div>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted-foreground italic">
          Henüz talep yok.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-muted-foreground text-xs">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Tip</th>
                <th className="text-left px-4 py-2 font-medium">Hesap</th>
                <th className="text-left px-4 py-2 font-medium">Durum</th>
                <th className="text-left px-4 py-2 font-medium">Tarih</th>
                <th className="text-left px-4 py-2 font-medium">Not</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-2">{r.kind_label}</td>
                  <td className="px-4 py-2">
                    {r.target_user ? (
                      r.target_user.full_name
                    ) : (
                      <span className="text-muted-foreground/60">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={r.status} label={r.status_label} />
                  </td>
                  <td className="px-4 py-2 text-xs text-muted-foreground tabular-nums">
                    {formatDate(r.created_at)}
                  </td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {r.admin_note ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function StatusBadge({
  status,
  label,
}: {
  status: KvkkRequestStatus;
  label: string;
}) {
  const map: Record<KvkkRequestStatus, string> = {
    completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
    processing: "bg-amber-50 text-amber-700 border-amber-200",
    pending: "bg-sky-50 text-sky-700 border-sky-200",
    cancelled: "bg-slate-100 text-slate-600 border-slate-200",
    rejected: "bg-rose-50 text-rose-700 border-rose-200",
  };
  return (
    <span
      className={cn("text-xs px-1.5 py-0.5 rounded border", map[status])}
    >
      {label}
    </span>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}
