"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bot, GitCommitHorizontal, FileCode2, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { adminKeys, getAdminFeatureCatalogDiscovery } from "@/lib/api/admin";
import {
  useBulkDiscovery,
  useRejectDiscoveryCard,
} from "@/lib/hooks/use-admin-mutations";
import type { DiscoveryQueueResponse } from "@/lib/types/admin";
import { SolidBadge } from "@/components/admin/feature-catalog-ui";

interface Props {
  initial: DiscoveryQueueResponse;
}

export function AdminFeatureCatalogDiscoveryClient({ initial }: Props) {
  const [source, setSource] = React.useState<string>(initial.source ?? "");
  const [showRejected, setShowRejected] = React.useState<boolean>(
    initial.show_rejected ?? false,
  );
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [confirm, setConfirm] = React.useState<null | {
    action: "reject" | "delete";
    ids: number[];
  }>(null);

  const q = useQuery<DiscoveryQueueResponse>({
    queryKey: adminKeys.featureCatalogDiscovery(source || null, showRejected),
    queryFn: () => getAdminFeatureCatalogDiscovery(source || null, showRejected),
    initialData:
      !source && !showRejected ? initial : undefined,
    staleTime: 10_000,
  });
  const data = q.data ?? initial;

  const bulkMut = useBulkDiscovery();
  const rejectMut = useRejectDiscoveryCard();

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function toggleAll() {
    if (selected.size === data.cards.length) setSelected(new Set());
    else setSelected(new Set(data.cards.map((c) => c.id)));
  }

  function doConfirm() {
    if (!confirm) return;
    if (confirm.ids.length === 1 && confirm.action === "reject") {
      rejectMut.mutate(confirm.ids[0], {
        onSettled: () => {
          setConfirm(null);
          setSelected(new Set());
        },
      });
    } else {
      bulkMut.mutate(
        { action: confirm.action, ids: confirm.ids },
        {
          onSettled: () => {
            setConfirm(null);
            setSelected(new Set());
          },
        },
      );
    }
  }

  const busy = bulkMut.isPending || rejectMut.isPending;

  return (
    <div className="space-y-5">
      <header>
        <Link
          href="/admin/feature-catalog"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Vitrin Kartları
        </Link>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Bot className="size-6 text-indigo-700" aria-hidden />
          Onay Kuyruğu
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Otomatik keşif aracının ürettiği taslak kart adayları. Bunlar yayına
          çıkmaz — yalnız onayla DRAFT&apos;tan çıkar. Reddedilenler gizlenir
          (silinmez), tekrar üretilmezler.
        </p>
      </header>

      {/* Sayım rozetleri */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">
            Bekleyen toplam
          </div>
          <div className="mt-1 text-3xl font-semibold text-indigo-700">
            {data.counts.total ?? 0}
          </div>
        </Card>
        <button
          type="button"
          onClick={() => setSource(source === "migration" ? "" : "migration")}
          className={cn(
            "rounded-lg border bg-card p-4 text-left transition hover:border-blue-400",
            source === "migration" ? "border-blue-400 ring-2 ring-blue-200" : "border-border",
          )}
        >
          <div className="inline-flex items-center gap-1 text-xs uppercase tracking-wider text-muted-foreground">
            <FileCode2 className="size-3.5" aria-hidden /> Migration
          </div>
          <div className="mt-1 text-3xl font-semibold text-blue-700">
            {data.counts.migration ?? 0}
          </div>
        </button>
        <button
          type="button"
          onClick={() => setSource(source === "commit" ? "" : "commit")}
          className={cn(
            "rounded-lg border bg-card p-4 text-left transition hover:border-amber-400",
            source === "commit" ? "border-amber-400 ring-2 ring-amber-200" : "border-border",
          )}
        >
          <div className="inline-flex items-center gap-1 text-xs uppercase tracking-wider text-muted-foreground">
            <GitCommitHorizontal className="size-3.5" aria-hidden /> Commit
          </div>
          <div className="mt-1 text-3xl font-semibold text-amber-700">
            {data.counts.commit ?? 0}
          </div>
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        {source ? (
          <button
            type="button"
            onClick={() => setSource("")}
            className="text-indigo-600 hover:text-indigo-800"
          >
            ← tüm kaynaklar
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => setShowRejected((v) => !v)}
          className={cn(
            "ml-auto inline-flex items-center gap-1 rounded border px-3 py-1 text-xs font-medium",
            showRejected
              ? "border-rose-300 bg-rose-100 text-rose-700"
              : "border-border bg-muted/50 text-muted-foreground",
          )}
        >
          {showRejected ? "✓ reddedilenler dahil" : "reddedilenleri göster"}
        </button>
      </div>

      {data.cards.length === 0 ? (
        <Card className="p-12 text-center text-sm text-muted-foreground">
          Onay bekleyen aday yok.
          <span className="mt-2 block text-xs text-muted-foreground/70">
            Yeni adaylar: <code className="rounded bg-muted px-1">python -m scripts.discover_features</code>
          </span>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          {/* Toplu işlem barı */}
          <div className="flex flex-wrap items-center gap-3 border-b border-border bg-muted/40 px-4 py-2 text-sm">
            <label className="inline-flex items-center gap-2 font-medium">
              <input
                type="checkbox"
                checked={selected.size === data.cards.length && data.cards.length > 0}
                onChange={toggleAll}
                className="rounded border-input"
              />
              Tümünü seç
            </label>
            <span className="text-xs text-muted-foreground">{selected.size} seçildi</span>
            <div className="ml-auto flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Seçilenler için:</span>
              <button
                type="button"
                disabled={selected.size === 0 || busy}
                onClick={() => setConfirm({ action: "reject", ids: Array.from(selected) })}
                className="rounded border border-amber-300 bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 hover:bg-amber-200 disabled:opacity-40"
              >
                Reddet (gizle)
              </button>
              <button
                type="button"
                disabled={selected.size === 0 || busy}
                onClick={() => setConfirm({ action: "delete", ids: Array.from(selected) })}
                className="rounded border border-rose-300 bg-rose-100 px-3 py-1 text-xs font-medium text-rose-800 hover:bg-rose-200 disabled:opacity-40"
              >
                Sil
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-xs text-muted-foreground">
                <tr>
                  <th className="w-10 px-4 py-2" />
                  <th className="w-28 px-4 py-2 text-left">Kaynak</th>
                  <th className="w-28 px-4 py-2 text-left">Tarih</th>
                  <th className="px-4 py-2 text-left">Aday başlığı</th>
                  <th className="w-44 px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.cards.map((c) => (
                  <tr
                    key={c.id}
                    className={cn(
                      "border-t border-border",
                      c.manual_hide && "bg-rose-50/30 opacity-60",
                    )}
                  >
                    <td className="px-4 py-3 align-top">
                      <input
                        type="checkbox"
                        checked={selected.has(c.id)}
                        onChange={() => toggle(c.id)}
                        className="rounded border-input"
                      />
                    </td>
                    <td className="px-4 py-3 align-top">
                      {c.is_migration ? (
                        <SolidBadge label="📜 migration" tone="indigo" />
                      ) : (
                        <SolidBadge label="💾 commit" tone="amber" />
                      )}
                      {c.manual_hide ? (
                        <div className="mt-1 text-[10px] font-medium text-rose-600">REDDEDİLDİ</div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                      {c.introduced_at ? c.introduced_at.slice(0, 10) : "—"}
                      {c.introduced_in_commit ? (
                        <div className="mt-0.5 font-mono text-[10px] text-muted-foreground/70">
                          {c.introduced_in_commit.slice(0, 7)}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 align-top">
                      <div className="font-medium">{c.title}</div>
                      {c.tagline &&
                      c.tagline !== "(otomatik üretildi — admin düzenleyecek)" ? (
                        <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                          {c.tagline}
                        </div>
                      ) : null}
                      <div className="mt-1.5 font-mono text-[11px] text-muted-foreground">
                        {c.slug}
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Link
                          href={`/admin/feature-catalog/${c.id}`}
                          className="rounded border border-indigo-200 bg-indigo-100 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-200"
                        >
                          Aç &amp; Düzenle →
                        </Link>
                        {!c.manual_hide ? (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => setConfirm({ action: "reject", ids: [c.id] })}
                            className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-700 hover:bg-amber-100"
                          >
                            Reddet
                          </button>
                        ) : null}
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => setConfirm({ action: "delete", ids: [c.id] })}
                          className="rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700 hover:bg-rose-100"
                        >
                          Sil
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Dialog open={confirm != null} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirm?.action === "reject" ? "Adayları reddet" : "Adayları sil"}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {confirm?.ids.length} aday için bu işlemi onaylıyor musun?
            {confirm?.action === "reject"
              ? " Reddedilenler gizlenir (silinmez)."
              : " Silinen adaylar kalıcı olarak kaldırılır."}
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button variant="ghost" onClick={() => setConfirm(null)} disabled={busy}>
              Vazgeç
            </Button>
            <Button
              onClick={doConfirm}
              disabled={busy}
              className={
                confirm?.action === "reject"
                  ? "bg-amber-600 text-white hover:bg-amber-700"
                  : "bg-rose-600 text-white hover:bg-rose-700"
              }
            >
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              {confirm?.action === "reject" ? "Reddet" : "Sil"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
