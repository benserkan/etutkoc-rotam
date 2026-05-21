"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Building2, Flame, ScanSearch, UserRound, Zap } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { adminKeys, getAdminSecurityAbuse } from "@/lib/api/admin";
import { useAbuseRemediate, useAbuseResolve, useAbuseScan } from "@/lib/hooks/use-admin-mutations";
import type { AbuseResponse, AbuseSignalItem } from "@/lib/types/admin";
import { fmtDateTime, toneBadge } from "@/components/admin/security-ui";

interface Props {
  initial: AbuseResponse;
  onlyOpen: boolean;
  kind: string | null;
}

export function SecurityAbuseClient({ initial, onlyOpen, kind }: Props) {
  const router = useRouter();
  const q = useQuery<AbuseResponse>({
    queryKey: adminKeys.securityAbuse(onlyOpen, kind),
    queryFn: () => getAdminSecurityAbuse(onlyOpen, kind),
    initialData: initial,
    staleTime: 15_000,
  });
  const d = q.data ?? initial;
  const meta = d.meta;

  const scan = useAbuseScan();
  const resolve = useAbuseResolve();
  const remediate = useAbuseRemediate();

  const [resolveFor, setResolveFor] = React.useState<AbuseSignalItem | null>(null);
  const [resolveNote, setResolveNote] = React.useState("");
  const [remediateFor, setRemediateFor] = React.useState<AbuseSignalItem | null>(null);

  function applyFilter(nextKind: string | null, nextOnlyOpen: boolean) {
    const qs = new URLSearchParams();
    qs.set("only_open", nextOnlyOpen ? "1" : "0");
    if (nextKind) qs.set("kind", nextKind);
    router.push(`/admin/security-monitor/abuse?${qs.toString()}`);
  }

  return (
    <div className="space-y-5">
      <header>
        <Link href="/admin/security-monitor" className="text-sm text-muted-foreground hover:text-foreground">
          ← Güvenlik Kamarası
        </Link>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Flame className="size-6 text-orange-600" aria-hidden />
          Kötüye Kullanım Kamerası
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Anormal davranış kalıplarını otomatik yakalar: aynı öğretmenin kısa sürede çok veli daveti
          göndermesi, anormal bildirim üretimi, tek cihazdan çoklu hesap, toplu sessizleştirme.
        </p>
      </header>

      {/* Aksiyon barı */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-muted-foreground">
          <b className="text-foreground">{d.open_count}</b> açık sinyal
          {d.filter_kind ? <> · filtre: <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{meta.kind_labels[d.filter_kind] ?? d.filter_kind}</code></> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={() => scan.mutate()} disabled={scan.isPending}>
            <ScanSearch className="size-4" aria-hidden /> {scan.isPending ? "Taranıyor…" : "Şimdi tara"}
          </Button>
          <select
            value={kind ?? ""}
            onChange={(e) => applyFilter(e.target.value || null, onlyOpen)}
            className="rounded-md border border-input bg-background px-2 py-1.5 text-xs"
          >
            <option value="">Tüm türler</option>
            {Object.entries(meta.kind_labels).map(([k, label]) => (
              <option key={k} value={k}>{label}</option>
            ))}
          </select>
          <label className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <input type="checkbox" checked={onlyOpen} onChange={(e) => applyFilter(kind, e.target.checked)} />
            Sadece açıklar
          </label>
        </div>
      </div>

      {/* Tür açıklama kartları */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {Object.entries(meta.kind_labels).map(([k, label]) => (
          <Card key={k} className="p-3">
            <div className="text-sm font-medium">{label}</div>
            <div className="mt-1 text-xs text-muted-foreground">{meta.kind_descriptions[k] ?? ""}</div>
          </Card>
        ))}
      </div>

      {/* Sinyal listesi */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-2.5">
          <h2 className="text-sm font-semibold">Sinyaller</h2>
        </div>
        {d.signals.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Açık sinyal yok. &quot;Şimdi tara&quot; ile güncel veriyi kontrol edebilirsin.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr><th className="px-3 py-1.5 text-left">Tür</th><th className="px-3 py-1.5 text-left">Şiddet</th><th className="px-3 py-1.5 text-left">Kim/Kurum</th><th className="px-3 py-1.5 text-right">Sayı</th><th className="px-3 py-1.5 text-left">Son tespit</th><th className="px-3 py-1.5 text-right">Aksiyon</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.signals.map((s) => {
                  const sevColor = meta.severity_colors[s.severity] ?? "slate";
                  const actLabel = meta.action_button_labels[s.kind];
                  const hasAction = actLabel && actLabel !== "—";
                  const ip = typeof s.details?.ip === "string" ? s.details.ip : null;
                  return (
                    <tr key={s.id} className="hover:bg-muted/40">
                      <td className="px-3 py-1.5">
                        <div className="font-medium">{s.kind_label}</div>
                        {ip ? <div className="font-mono text-[11px] text-muted-foreground">{ip}</div> : null}
                      </td>
                      <td className="px-3 py-1.5">
                        <span className={cn("rounded-full border px-2 py-0.5 text-[11px]", toneBadge(sevColor))}>{meta.severity_labels[s.severity] ?? s.severity}</span>
                        {s.resolved_at ? <span className="ml-1 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] text-emerald-700">çözüldü</span> : null}
                      </td>
                      <td className="px-3 py-1.5 text-xs">
                        {s.actor_full_name ? (
                          <>
                            <Link href={`/admin/users/${s.actor_user_id}`} className="inline-flex items-center gap-1 font-medium text-indigo-600 hover:underline"><UserRound className="size-3" aria-hidden />{s.actor_full_name}</Link>
                            <div className="text-muted-foreground">{s.actor_email}</div>
                          </>
                        ) : s.tenant_name ? (
                          <Link href={`/admin/institutions/${s.tenant_id}`} className="inline-flex items-center gap-1 font-medium text-indigo-600 hover:underline"><Building2 className="size-3" aria-hidden />{s.tenant_name}</Link>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-3 py-1.5 text-right font-semibold tabular-nums">{s.count}</td>
                      <td className="px-3 py-1.5 whitespace-nowrap text-[11px] text-muted-foreground">{fmtDateTime(s.last_seen_at)}</td>
                      <td className="px-3 py-1.5 text-right">
                        {!s.resolved_at ? (
                          <div className="inline-flex items-center gap-2">
                            {hasAction ? (
                              <button type="button" className="inline-flex items-center gap-1 rounded bg-rose-600 px-2 py-1 text-xs font-medium text-white hover:bg-rose-700" onClick={() => setRemediateFor(s)}>
                                <Zap className="size-3" aria-hidden /> {actLabel}
                              </button>
                            ) : null}
                            <button type="button" className="text-xs font-medium text-emerald-600 hover:text-emerald-800" onClick={() => { setResolveFor(s); setResolveNote(""); }}>Çöz</button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Remediate confirm */}
      <Dialog open={remediateFor != null} onOpenChange={(o) => { if (!o) setRemediateFor(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Toplu aksiyon uygula</DialogTitle>
            <DialogDescription>
              {remediateFor ? <>&quot;{remediateFor.kind_label}&quot; sinyali için <b>{meta.action_button_labels[remediateFor.kind]}</b> aksiyonu uygulanacak. Sinyal otomatik çözüldü olarak işaretlenecek.</> : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRemediateFor(null)} disabled={remediate.isPending}>Vazgeç</Button>
            <Button variant="destructive" onClick={() => { if (remediateFor) remediate.mutate({ signalId: remediateFor.id }, { onSuccess: () => setRemediateFor(null) }); }} disabled={remediate.isPending}>
              {remediate.isPending ? "Uygulanıyor…" : "Uygula"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resolve note dialog */}
      <Dialog open={resolveFor != null} onOpenChange={(o) => { if (!o) setResolveFor(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sinyali çöz (aksiyonsuz)</DialogTitle>
            <DialogDescription>{resolveFor ? `"${resolveFor.kind_label}" sinyalini incelendi/sorun yok olarak kapat.` : null}</DialogDescription>
          </DialogHeader>
          <textarea
            value={resolveNote}
            onChange={(e) => setResolveNote(e.target.value)}
            rows={3}
            maxLength={500}
            placeholder="Açıklama (opsiyonel)"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setResolveFor(null)} disabled={resolve.isPending}>Vazgeç</Button>
            <Button onClick={() => { if (resolveFor) resolve.mutate({ signalId: resolveFor.id, note: resolveNote }, { onSuccess: () => setResolveFor(null) }); }} disabled={resolve.isPending}>
              {resolve.isPending ? "Kaydediliyor…" : "Çözüldü işaretle"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
