"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bug,
  CheckCircle2,
  ChevronDown,
  Gauge,
  ServerCrash,
  Timer,
} from "lucide-react";

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
import { adminKeys, getAdminSecuritySystem } from "@/lib/api/admin";
import { useResolveSystemError } from "@/lib/hooks/use-admin-mutations";
import type { SystemErrorGroup, SystemHealthDataResponse } from "@/lib/types/admin";
import { fmtDateTime, humanizeAgo } from "@/components/admin/security-ui";

interface Props {
  initial: SystemHealthDataResponse;
}

function statusTone(code: number): string {
  if (code >= 500) return "bg-rose-50 text-rose-700 border-rose-200";
  if (code >= 400) return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-slate-50 text-slate-600 border-slate-200";
}

function ResolveButton({ group }: { group: SystemErrorGroup }) {
  const [open, setOpen] = React.useState(false);
  const [note, setNote] = React.useState("");
  const mut = useResolveSystemError();

  function submit() {
    mut.mutate(
      { errorId: group.id, note },
      { onSuccess: () => setOpen(false) },
    );
  }

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        <CheckCircle2 className="size-3.5" aria-hidden />
        Çözüldü
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Hata grubunu çöz</DialogTitle>
            <DialogDescription>
              <span className="font-mono text-xs">{group.exception_type}</span> ·{" "}
              {group.method} {group.endpoint}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="resolve-note">
              Çözüm notu (opsiyonel)
            </label>
            <textarea
              id="resolve-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="Ne yapıldı / kök neden?"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={mut.isPending}>
              Vazgeç
            </Button>
            <Button onClick={submit} disabled={mut.isPending}>
              {mut.isPending ? "Kaydediliyor…" : "Çözüldü olarak işaretle"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ErrorGroupRow({ group }: { group: SystemErrorGroup }) {
  const [expanded, setExpanded] = React.useState(false);
  return (
    <Card className="overflow-hidden">
      <div className="flex items-start gap-3 p-3">
        <span className={cn("mt-0.5 inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[11px]", statusTone(group.status_code))}>
          {group.status_code}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-semibold">{group.exception_type}</span>
            <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
              {group.method} {group.endpoint}
            </span>
            <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-medium text-rose-700">
              {group.count}×
            </span>
          </div>
          {group.exception_message ? (
            <p className="mt-1 truncate text-xs text-muted-foreground" title={group.exception_message}>
              {group.exception_message}
            </p>
          ) : null}
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
            <span>İlk: {fmtDateTime(group.first_seen_at)}</span>
            <span>Son: {fmtDateTime(group.last_seen_at)} ({humanizeAgo(group.age_seconds)})</span>
            {group.last_ip ? <span className="font-mono">{group.last_ip}</span> : null}
          </div>
          {group.stack_trace ? (
            <>
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-800"
              >
                <ChevronDown className={cn("size-3 transition", expanded && "rotate-180")} aria-hidden />
                {expanded ? "Yığını gizle" : "Yığın izini göster"}
              </button>
              {expanded ? (
                <pre className="mt-1 max-h-64 overflow-auto rounded-md bg-slate-900 p-2 font-mono text-[10px] leading-relaxed text-slate-100">
                  {group.stack_trace}
                </pre>
              ) : null}
            </>
          ) : null}
        </div>
        <div className="shrink-0">
          <ResolveButton group={group} />
        </div>
      </div>
    </Card>
  );
}

export function SecuritySystemClient({ initial }: Props) {
  const q = useQuery<SystemHealthDataResponse>({
    queryKey: adminKeys.securitySystem(),
    queryFn: getAdminSecuritySystem,
    initialData: initial,
    staleTime: 10_000,
  });
  const d = q.data ?? initial;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <ServerCrash className="size-6 text-slate-700" aria-hidden />
          Sistem Sağlığı
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Yakalanan uygulama hataları (açık gruplar), en çok hata üreten uç noktalar
          ve yavaş istekler. Bir hatayı çözüldü olarak işaretleyince listeden düşer.
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">Son güncelleme: {fmtDateTime(d.generated_at)}</p>
      </header>

      {/* Özet */}
      <section className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <div className="text-2xl font-semibold tabular-nums">{d.summary.open_groups}</div>
          <div className="text-xs text-muted-foreground">Açık hata grubu</div>
        </Card>
        <Card className="p-4">
          <div className="text-2xl font-semibold tabular-nums">{d.summary.new_groups_24h}</div>
          <div className="text-xs text-muted-foreground">Son 24s yeni grup</div>
        </Card>
        <Card className="p-4">
          <div className="text-2xl font-semibold tabular-nums">{d.summary.total_events_24h}</div>
          <div className="text-xs text-muted-foreground">Son 24s toplam olay</div>
        </Card>
      </section>

      {/* Açık hata grupları */}
      <section className="space-y-3">
        <h2 className="inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          <Bug className="size-4" aria-hidden />
          Açık hata grupları
        </h2>
        {d.error_groups.length === 0 ? (
          <Card className="flex items-center gap-3 border-emerald-200 bg-emerald-50/40 p-4 text-sm text-emerald-800">
            <CheckCircle2 className="size-5 shrink-0 text-emerald-600" aria-hidden />
            Açık hata yok. Sistem temiz görünüyor.
          </Card>
        ) : (
          <div className="space-y-2">
            {d.error_groups.map((g) => (
              <ErrorGroupRow key={g.id} group={g} />
            ))}
          </div>
        )}
      </section>

      {/* Endpoint hata oranı + yavaş istekler */}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <Gauge className="size-4 text-amber-600" aria-hidden />
              En çok hata üreten uç noktalar (24s)
            </h2>
          </div>
          {d.endpoint_top.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Veri yok.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-1.5 text-left">Uç nokta</th>
                  <th className="px-3 py-1.5 text-right">Olay</th>
                  <th className="px-3 py-1.5 text-right">Grup</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.endpoint_top.map((e, i) => (
                  <tr key={`${e.method}-${e.endpoint}-${i}`} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5">
                      <span className="rounded bg-muted px-1 text-[11px] text-muted-foreground">{e.method}</span>{" "}
                      <span className="font-mono text-[11px]">{e.endpoint}</span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-medium">{e.total}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">{e.groups}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <Timer className="size-4 text-indigo-600" aria-hidden />
              Yavaş istekler (24s)
            </h2>
          </div>
          {d.slow_requests.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Yavaş istek yok.</p>
          ) : (
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-card text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-1.5 text-left">Uç nokta</th>
                    <th className="px-3 py-1.5 text-right">Süre</th>
                    <th className="px-3 py-1.5 text-right">Zaman</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.slow_requests.map((r) => (
                    <tr key={r.id} className="hover:bg-muted/40">
                      <td className="px-3 py-1.5">
                        <span className="rounded bg-muted px-1 text-[11px] text-muted-foreground">{r.method}</span>{" "}
                        <span className="font-mono text-[11px]">{r.endpoint}</span>
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums font-medium text-amber-700">
                        {r.response_time_ms} ms
                      </td>
                      <td className="px-3 py-1.5 text-right text-[11px] text-muted-foreground">
                        {fmtDateTime(r.recorded_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
