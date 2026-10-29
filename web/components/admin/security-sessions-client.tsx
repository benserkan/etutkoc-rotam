"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Ban, KeyRound, ShieldCheck, UserCog, Users } from "lucide-react";

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
import { adminKeys, getAdminSecurityOverview } from "@/lib/api/admin";
import {
  useBlockIp,
  useRevokeImpersonation,
  useRevokeSession,
  useUnblockIp,
} from "@/lib/hooks/use-admin-mutations";
import type { SecurityOverviewResponse } from "@/lib/types/admin";
import { ROLE_LABELS_TR } from "@/lib/types/me";
import { fmtDateTime, humanizeAgo } from "@/components/admin/security-ui";

interface Props {
  initial: SecurityOverviewResponse;
}

const ROLE_BADGE: Record<string, string> = {
  super_admin: "bg-rose-100 text-rose-700",
  institution_admin: "bg-indigo-100 text-indigo-700",
  teacher: "bg-emerald-100 text-emerald-700",
  parent: "bg-amber-100 text-amber-700",
  student: "bg-slate-100 text-slate-700",
};

function roleLabel(role: string): string {
  return (ROLE_LABELS_TR as Record<string, string>)[role] ?? role;
}

export function SecuritySessionsClient({ initial }: Props) {
  const q = useQuery<SecurityOverviewResponse>({
    queryKey: adminKeys.securityOverview(),
    queryFn: getAdminSecurityOverview,
    initialData: initial,
    staleTime: 10_000,
  });
  const d = q.data ?? initial;
  const s = d.summary;

  const revoke = useRevokeSession();
  const blockIp = useBlockIp();
  const unblockIp = useUnblockIp();
  const endImp = useRevokeImpersonation();

  // confirm dialog state
  const [confirm, setConfirm] = React.useState<null | { title: string; desc: string; run: () => void }>(null);

  // manuel blok formu
  const [manualIp, setManualIp] = React.useState("");
  const [manualHours, setManualHours] = React.useState(1);

  return (
    <div className="space-y-5">
      <header>
        <Link href="/admin/security-monitor" className="text-sm text-muted-foreground hover:text-foreground">
          ← Güvenlik Kamarası
        </Link>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <KeyRound className="size-6 text-slate-700" aria-hidden />
          Oturumlar & IP&apos;ler
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Şu an sisteme girmiş kullanıcılar, şüpheli IP adresleri, son 24 saatte başarısız
          giriş denemeleri. Buradan uzaktan oturum kapatabilir, IP engelleyebilirsin.
        </p>
      </header>

      {/* Aktif sahte oturumlar */}
      {d.active_impersonations.length > 0 ? (
        <Card className="overflow-hidden border-2 border-violet-300">
          <div className="border-b border-violet-200 bg-violet-50/60 px-4 py-2.5 text-sm font-semibold text-violet-900">
            <UserCog className="mr-1 inline size-4" aria-hidden />
            Aktif Sahte Oturumlar ({d.active_impersonations.length})
            <span className="ml-2 text-xs font-normal text-violet-700">— 30 dk sonra otomatik kapanır</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-violet-100/40 text-[11px] uppercase tracking-wide text-violet-700">
                <tr>
                  <th className="px-3 py-2 text-left">Süper Admin</th>
                  <th className="px-3 py-2 text-left">Hedef</th>
                  <th className="px-3 py-2 text-left">Gerekçe</th>
                  <th className="px-3 py-2 text-left">Başlangıç</th>
                  <th className="px-3 py-2 text-left">Kalan</th>
                  <th className="px-3 py-2 text-right">Aksiyon</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-violet-100">
                {d.active_impersonations.map((i) => (
                  <tr key={i.id}>
                    <td className="px-3 py-2"><div className="font-medium">{i.actor_full_name}</div><div className="text-[11px] text-muted-foreground">{i.actor_email}</div></td>
                    <td className="px-3 py-2"><div className="font-medium">{i.target_full_name}</div><div className="text-[11px] text-muted-foreground">{i.target_email}</div></td>
                    <td className="max-w-xs px-3 py-2 text-xs italic text-muted-foreground">&quot;{i.reason}&quot;</td>
                    <td className="px-3 py-2 text-[11px] text-muted-foreground">{fmtDateTime(i.started_at)}</td>
                    <td className="px-3 py-2 text-xs">
                      {i.is_expired_now ? (
                        <span className="rounded bg-rose-100 px-2 py-0.5 text-rose-700">Süre doldu</span>
                      ) : (
                        <span className="rounded bg-amber-100 px-2 py-0.5 text-amber-800">{Math.floor(i.seconds_left / 60)} dk</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        className="text-xs font-medium text-rose-600 hover:text-rose-800"
                        onClick={() => setConfirm({ title: "Sahte oturumu sonlandır", desc: "Bu sahte oturumu uzaktan sonlandırmak istediğine emin misin?", run: () => endImp.mutate({ impId: i.id }) })}
                      >
                        Sonlandır
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {/* Özet */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <SummaryCard label="Aktif oturum" value={s.active_sessions} tone="emerald" />
        <SummaryCard label="Bloklu IP" value={s.blocked_ips} tone={s.blocked_ips > 0 ? "rose" : "slate"} />
        <SummaryCard label="İzlenen IP" value={s.watched_ips} tone="amber" />
        <SummaryCard label="24s başarısız giriş" value={s.failed_24h} tone="slate" />
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Aktif oturumlar */}
        <Card className="overflow-hidden lg:col-span-2">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold"><Users className="size-4 text-indigo-600" aria-hidden /> Aktif Oturumlar</h2>
            <div className="flex flex-wrap gap-1 text-[11px] text-muted-foreground">
              {Object.entries(d.role_counts).map(([role, n]) => (
                <span key={role} className="rounded bg-muted px-2 py-0.5">{roleLabel(role)}: {n}</span>
              ))}
            </div>
          </div>
          {d.active_sessions.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Şu an aktif oturum yok.</p>
          ) : (
            <div className="max-h-[28rem] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-card text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr><th className="px-3 py-1.5 text-left">Kullanıcı</th><th className="px-3 py-1.5 text-left">Rol</th><th className="px-3 py-1.5 text-left">IP</th><th className="px-3 py-1.5 text-right">Boşta</th><th className="px-3 py-1.5 text-right">Aksiyon</th></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.active_sessions.map((sess) => (
                    <tr key={sess.id} className="hover:bg-muted/40">
                      <td className="px-3 py-1.5"><div className="font-medium">{sess.user_full_name ?? sess.user_email}</div><div className="text-[11px] text-muted-foreground">{sess.user_email}</div></td>
                      <td className="px-3 py-1.5"><span className={cn("rounded px-2 py-0.5 text-[11px]", ROLE_BADGE[sess.role] ?? ROLE_BADGE.student)}>{roleLabel(sess.role)}</span></td>
                      <td className="px-3 py-1.5 font-mono text-[11px] text-muted-foreground">{sess.ip ?? "—"}</td>
                      <td className="px-3 py-1.5 text-right text-[11px] text-muted-foreground">{humanizeAgo(sess.idle_seconds)}</td>
                      <td className="px-3 py-1.5 text-right">
                        <button type="button" className="text-xs font-medium text-rose-600 hover:text-rose-800" onClick={() => setConfirm({ title: "Oturumu kapat", desc: `${sess.user_full_name ?? sess.user_email} kullanıcısının oturumunu uzaktan kapat?`, run: () => revoke.mutate({ sessionToken: sess.session_token }) })}>Kapat</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* 24h fail buckets */}
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="text-sm font-semibold">24s Başarısız Giriş (IP başına)</h2>
          </div>
          {d.failed_login_buckets.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Son 24s başarısız giriş yok.</p>
          ) : (
            <ul className="max-h-[28rem] divide-y divide-border overflow-auto">
              {d.failed_login_buckets.map((b, i) => (
                <li key={i} className="flex items-center justify-between gap-2 px-3 py-2">
                  <div className="min-w-0">
                    <div className="truncate font-mono text-xs">{b.ip ?? "(IP yok)"}</div>
                    <div className="text-[11px] text-muted-foreground">{b.fail_count} deneme · {b.distinct_email_count} farklı e-posta</div>
                  </div>
                  {b.ip ? (
                    <button type="button" className="shrink-0 text-xs font-medium text-rose-600 hover:text-rose-800" onClick={() => blockIp.mutate({ ip: b.ip!, hours: 1, note: "Bucket'tan manuel" })}>Bloka al</button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Şüpheli/Bloklu IP'ler */}
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
          <div>
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold"><Ban className="size-4 text-rose-600" aria-hidden /> Şüpheli & Bloklu IP&apos;ler</h2>
            <div className="text-[11px] text-muted-foreground">Brute force eşiği aşılırsa otomatik 1 saat blok.</div>
          </div>
          <form
            className="flex items-center gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              const ip = manualIp.trim();
              if (!ip) return;
              blockIp.mutate({ ip, hours: manualHours, note: "Manuel" }, { onSuccess: () => setManualIp("") });
            }}
          >
            <input value={manualIp} onChange={(e) => setManualIp(e.target.value)} placeholder="IP adresi" className="w-32 rounded-md border border-input bg-background px-2 py-1 text-xs" />
            <input type="number" min={1} max={720} value={manualHours} onChange={(e) => setManualHours(Number(e.target.value))} className="w-16 rounded-md border border-input bg-background px-2 py-1 text-xs" />
            <Button type="submit" size="sm" variant="destructive" disabled={blockIp.isPending}>Blok</Button>
          </form>
        </div>
        {d.suspicious_ips.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Şu an şüpheli IP yok.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr><th className="px-3 py-1.5 text-left">IP</th><th className="px-3 py-1.5 text-left">Sinyal</th><th className="px-3 py-1.5 text-center">Durum</th><th className="px-3 py-1.5 text-left">Süre sonu</th><th className="px-3 py-1.5 text-right">Aksiyon</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.suspicious_ips.map((r) => (
                  <tr key={r.id} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5 font-mono text-xs">{r.ip}</td>
                    <td className="px-3 py-1.5 text-[11px] text-muted-foreground">{r.fail_count} fail · {r.distinct_email_count} farklı e-posta</td>
                    <td className="px-3 py-1.5 text-center">
                      {r.is_blocked ? <span className="rounded bg-rose-100 px-2 py-0.5 text-[11px] text-rose-700">Bloklu</span> : <span className="rounded bg-amber-100 px-2 py-0.5 text-[11px] text-amber-700">İzleniyor</span>}
                    </td>
                    <td className="px-3 py-1.5 text-[11px] text-muted-foreground">{r.blocked_until ? fmtDateTime(r.blocked_until) : "—"}</td>
                    <td className="px-3 py-1.5 text-right">
                      {r.is_blocked ? (
                        <button type="button" className="text-xs font-medium text-emerald-600 hover:text-emerald-800" onClick={() => unblockIp.mutate({ ip: r.ip })}>Serbest</button>
                      ) : (
                        <button type="button" className="text-xs font-medium text-rose-600 hover:text-rose-800" onClick={() => blockIp.mutate({ ip: r.ip, hours: 1, note: "Manuel" })}>Bloka al</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Süper admin girişleri */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-2.5">
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="size-4 text-violet-600" aria-hidden /> Süper Admin Girişleri (24s)</h2>
        </div>
        {d.super_admin_logins.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Son 24s süper admin girişi yok.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr><th className="px-3 py-1.5 text-left">Aktör</th><th className="px-3 py-1.5 text-left">IP</th><th className="px-3 py-1.5 text-left">Tarayıcı</th><th className="px-3 py-1.5 text-left">Zaman</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.super_admin_logins.map((a) => (
                  <tr key={a.id} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5"><div className="font-medium">{a.email_attempted ?? `Aktör #${a.actor_id}`}</div></td>
                    <td className="px-3 py-1.5 font-mono text-[11px]">{a.ip_address ?? "—"}</td>
                    <td className="max-w-xs truncate px-3 py-1.5 text-[11px] text-muted-foreground">{a.user_agent ?? "—"}</td>
                    <td className="px-3 py-1.5 text-[11px] text-muted-foreground">{fmtDateTime(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Confirm dialog */}
      <Dialog open={confirm != null} onOpenChange={(o) => { if (!o) setConfirm(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{confirm?.title}</DialogTitle>
            <DialogDescription>{confirm?.desc}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirm(null)}>Vazgeç</Button>
            <Button variant="destructive" onClick={() => { confirm?.run(); setConfirm(null); }}>Onayla</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SummaryCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  const cls: Record<string, string> = {
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900",
    rose: "bg-rose-50 border-rose-200 text-rose-900",
    amber: "bg-amber-50 border-amber-200 text-amber-900",
    slate: "bg-slate-50 border-slate-200 text-slate-900",
  };
  return (
    <div className={cn("rounded-lg border p-3", cls[tone] ?? cls.slate)}>
      <div className="text-[11px] opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
