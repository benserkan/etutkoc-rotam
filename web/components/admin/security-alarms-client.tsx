"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BellRing, Radio, ScanSearch } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { adminKeys, getAdminSecurityAlarms } from "@/lib/api/admin";
import { useAlarmAck, useAlarmScan, useAlarmUpdateRule } from "@/lib/hooks/use-admin-mutations";
import type { AlarmRuleItem, AlarmsResponse } from "@/lib/types/admin";
import { fmtDateTime } from "@/components/admin/security-ui";

interface Props {
  initial: AlarmsResponse;
}

function sevTone(sev: string): string {
  if (sev === "critical") return "bg-rose-100 text-rose-800";
  if (sev === "warn") return "bg-amber-100 text-amber-800";
  return "bg-slate-100 text-slate-700";
}

export function SecurityAlarmsClient({ initial }: Props) {
  const q = useQuery<AlarmsResponse>({
    queryKey: adminKeys.securityAlarms(),
    queryFn: getAdminSecurityAlarms,
    initialData: initial,
    staleTime: 15_000,
  });
  const d = q.data ?? initial;

  const scan = useAlarmScan();
  const ack = useAlarmAck();

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/admin/security-monitor" className="text-sm text-muted-foreground hover:text-foreground">
            ← Güvenlik Kamarası
          </Link>
          <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <BellRing className="size-6 text-slate-700" aria-hidden />
            Alarm Ayarları
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Bir şey ters gittiğinde haber veren otomatik uyarı kuralları. Eşik aşılınca süper
            adminlere e-posta gider; sessizlik süresi (cooldown) ile alarm spam&apos;ı engellenir.
          </p>
        </div>
        <Link href="/admin/security-monitor/live" className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted">
          <Radio className="mr-1 inline size-4 text-rose-600" aria-hidden /> Canlı Akış
        </Link>
      </header>

      <div className="flex items-center justify-between">
        <div className="text-sm"><b>{d.unack_count}</b> onaylanmamış alarm</div>
        <Button size="sm" onClick={() => scan.mutate()} disabled={scan.isPending}>
          <ScanSearch className="size-4" aria-hidden /> {scan.isPending ? "Taranıyor…" : "Şimdi tara"}
        </Button>
      </div>

      {/* Kurallar */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-2.5">
          <h2 className="text-sm font-semibold">Alarm Kuralları</h2>
          <div className="text-xs text-muted-foreground">Her kuralın eşiğini, sessizlik süresini, kanalını ve aktiflik durumunu değiştir.</div>
        </div>
        {d.rules.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Kural yok.</p>
        ) : (
          <div className="divide-y divide-border">
            {d.rules.map((r) => <RuleRow key={r.id} rule={r} />)}
          </div>
        )}
      </Card>

      {/* Son tetiklenenler */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-2.5">
          <h2 className="text-sm font-semibold">Son Tetiklenen Alarmlar</h2>
          <div className="text-xs text-muted-foreground">Son 72 saat.</div>
        </div>
        {d.events.length === 0 ? (
          <p className="p-6 text-center text-sm text-emerald-700">Son 72 saatte alarm yok.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr><th className="px-3 py-1.5 text-left">Şiddet</th><th className="px-3 py-1.5 text-left">Kural</th><th className="px-3 py-1.5 text-right">Değer/Eşik</th><th className="px-3 py-1.5 text-left">Zaman</th><th className="px-3 py-1.5 text-left">Teslim</th><th className="px-3 py-1.5 text-right">Aksiyon</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.events.map((e) => (
                  <tr key={e.id} className={cn("hover:bg-muted/40", !e.acknowledged_at && "bg-amber-50/30")}>
                    <td className="px-3 py-1.5"><span className={cn("rounded px-2 py-0.5 text-[11px]", sevTone(e.severity))}>{e.severity}</span></td>
                    <td className="px-3 py-1.5"><div>{e.rule_name}</div><code className="text-[10px] text-muted-foreground">{e.rule_key}</code></td>
                    <td className="px-3 py-1.5 text-right"><span className="font-semibold">{e.value}</span> <span className="text-[11px] text-muted-foreground">/ {e.threshold}</span></td>
                    <td className="px-3 py-1.5 text-[11px] text-muted-foreground">{fmtDateTime(e.triggered_at)}</td>
                    <td className="px-3 py-1.5 text-[11px] text-muted-foreground">{e.delivery_status ?? "—"}</td>
                    <td className="px-3 py-1.5 text-right">
                      {e.acknowledged_at ? (
                        <span className="text-[11px] text-muted-foreground">✓ Onaylı</span>
                      ) : (
                        <button type="button" className="text-xs font-medium text-emerald-600 hover:text-emerald-800" onClick={() => ack.mutate({ eventId: e.id })}>Gördüm</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function RuleRow({ rule }: { rule: AlarmRuleItem }) {
  const update = useAlarmUpdateRule();
  const [threshold, setThreshold] = React.useState(rule.threshold);
  const [cooldown, setCooldown] = React.useState(rule.cooldown_minutes);
  const [enabled, setEnabled] = React.useState(rule.enabled);
  const [channels, setChannels] = React.useState(rule.channels ?? "email,in_app");

  const value = rule.last_value ?? 0;
  const dirty =
    threshold !== rule.threshold ||
    cooldown !== rule.cooldown_minutes ||
    enabled !== rule.enabled ||
    channels !== (rule.channels ?? "email,in_app");

  return (
    <form
      className="flex flex-col gap-3 p-3 lg:flex-row lg:items-center"
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate({ ruleId: rule.id, body: { threshold, cooldown_minutes: cooldown, enabled, channels } });
      }}
    >
      <div className="min-w-0 flex-1">
        <div className="font-medium">{rule.name}</div>
        {rule.description ? <div className="text-xs text-muted-foreground">{rule.description}</div> : null}
        <code className="text-[10px] text-muted-foreground">{rule.key}</code>
        {rule.last_triggered_at ? <span className="ml-2 text-[10px] text-muted-foreground">son tetik: {fmtDateTime(rule.last_triggered_at)}</span> : null}
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:flex lg:items-center">
        <label className="text-xs">
          <span className="block text-[10px] text-muted-foreground">Şu an</span>
          <span className={cn("font-semibold tabular-nums", value > rule.threshold ? "text-rose-700" : "text-foreground")}>{value}</span>
        </label>
        <label className="text-xs">
          <span className="block text-[10px] text-muted-foreground">Eşik</span>
          <input type="number" min={0} max={100000} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} className="w-20 rounded-md border border-input bg-background px-2 py-1 text-right text-xs" />
        </label>
        <label className="text-xs">
          <span className="block text-[10px] text-muted-foreground">Sessizlik (dk)</span>
          <input type="number" min={0} max={1440} value={cooldown} onChange={(e) => setCooldown(Number(e.target.value))} className="w-20 rounded-md border border-input bg-background px-2 py-1 text-right text-xs" />
        </label>
        <label className="text-xs">
          <span className="block text-[10px] text-muted-foreground">Kanal</span>
          <input type="text" value={channels} onChange={(e) => setChannels(e.target.value)} placeholder="email,in_app" className="w-32 rounded-md border border-input bg-background px-2 py-1 text-xs" />
        </label>
        <label className="inline-flex items-center gap-1 text-xs">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Aktif
        </label>
        <Button type="submit" size="sm" variant={dirty ? "default" : "outline"} disabled={!dirty || update.isPending}>Kaydet</Button>
      </div>
    </form>
  );
}
