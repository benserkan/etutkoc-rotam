"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertOctagon,
  BadgeCheck,
  Ban,
  Bug,
  CheckCircle2,
  ChevronDown,
  Eye,
  Flame,
  KeyRound,
  Lightbulb,
  Shield,
  ShieldAlert,
  UserCog,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminSecurityOverview } from "@/lib/api/admin";
import type { AttentionItemModel, SecurityOverviewResponse } from "@/lib/types/admin";
import { ROLE_LABELS_TR } from "@/lib/types/me";
import {
  SeverityBadge,
  fmtDateTime,
  humanizeAgo,
  severityCardClass,
  severityIcon,
  severityIconColor,
} from "@/components/admin/security-ui";

interface Props {
  initial: SecurityOverviewResponse;
}

function roleLabel(role: string): string {
  return (ROLE_LABELS_TR as Record<string, string>)[role] ?? role;
}

function AttentionCard({ it }: { it: AttentionItemModel }) {
  const [open, setOpen] = React.useState(false);
  return (
    <Card className={cn("border-l-4 p-4", severityCardClass(it.severity))}>
      <div className="flex items-start gap-3">
        {React.createElement(severityIcon(it.severity), {
          className: cn("mt-0.5 size-5 shrink-0", severityIconColor(it.severity)),
          "aria-hidden": true,
        })}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <SeverityBadge sev={it.severity} />
            {it.ts ? (
              <span className="text-[11px] text-muted-foreground">{fmtDateTime(it.ts)}</span>
            ) : null}
          </div>
          <h3 className="mt-1 text-sm font-semibold">{it.title}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">{it.description}</p>

          {it.explainer ? (
            <>
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800"
              >
                <Lightbulb className="size-3.5" aria-hidden />
                {open ? "Açıklamayı gizle" : "Bu ne demek? Ne yapmalı?"}
                <ChevronDown className={cn("size-3 transition", open && "rotate-180")} aria-hidden />
              </button>
              {open ? (
                <div className="mt-2 whitespace-pre-line rounded-lg border border-border bg-background/60 p-3 text-xs leading-relaxed text-foreground/90">
                  {it.explainer}
                </div>
              ) : null}
            </>
          ) : null}

          {it.action_url ? (
            <Link
              href={it.action_url}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800"
            >
              {it.action_label || "Detay"} →
            </Link>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function KpiCard({
  icon: Icon,
  label,
  value,
  tone,
  href,
}: {
  icon: typeof Shield;
  label: string;
  value: number;
  tone: string;
  href?: string;
}) {
  const body = (
    <Card className={cn("flex items-center gap-3 p-4", href && "transition hover:border-foreground/30")}>
      <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg", tone)}>
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="min-w-0">
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
        <div className="truncate text-xs text-muted-foreground">{label}</div>
      </div>
    </Card>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

export function SecurityOverviewClient({ initial }: Props) {
  const q = useQuery<SecurityOverviewResponse>({
    queryKey: adminKeys.securityOverview(),
    queryFn: getAdminSecurityOverview,
    initialData: initial,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
  const d = q.data ?? initial;
  const s = d.summary;
  const att = d.attention;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Shield className="size-6 text-slate-700" aria-hidden />
          Güvenlik Kamarası
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Hesap güvenliği canlı görünümü: aktif oturumlar, şüpheli/blokli IP&apos;ler,
          son 24 saat başarısız giriş dağılımı, kritik aksiyon akışı, süper admin
          girişleri ve aktif kimliğe-bürünme oturumları. Sayfa 30 saniyede bir tazelenir.
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Son güncelleme: {fmtDateTime(d.generated_at)}
        </p>
      </header>

      {/* Dikkat Odası */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            <Eye className="size-4" aria-hidden />
            Dikkat Odası
          </h2>
          <span className="text-xs text-muted-foreground">
            {att.by_severity.critical} kritik · {att.by_severity.warn} uyarı · {att.by_severity.info} bilgi
          </span>
        </div>
        {att.is_clean ? (
          <Card className="flex items-center gap-3 border-emerald-200 bg-emerald-50/40 p-4 text-sm text-emerald-800">
            <CheckCircle2 className="size-5 shrink-0 text-emerald-600" aria-hidden />
            Şu an dikkat gerektiren bir durum yok. Her şey sakin görünüyor.
          </Card>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {att.items.map((it, i) => (
              <AttentionCard key={`${it.category}-${i}`} it={it} />
            ))}
          </div>
        )}
      </section>

      {/* Özet KPI */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard icon={Users} label="Aktif oturum" value={s.active_sessions} tone="bg-indigo-100 text-indigo-700" />
        <KpiCard icon={Ban} label="Blokli IP" value={s.blocked_ips} tone="bg-rose-100 text-rose-700" />
        <KpiCard icon={Eye} label="İzlenen IP" value={s.watched_ips} tone="bg-amber-100 text-amber-700" />
        <KpiCard icon={KeyRound} label="Başarısız giriş (24s)" value={s.failed_24h} tone="bg-rose-100 text-rose-700" />
        <KpiCard icon={ShieldAlert} label="Kritik aksiyon (24s)" value={s.critical_24h} tone="bg-rose-100 text-rose-700" />
        <KpiCard icon={BadgeCheck} label="Süper admin giriş (24s)" value={s.super_admin_logins_24h} tone="bg-violet-100 text-violet-700" />
        <KpiCard icon={Flame} label="Açık suistimal" value={d.abuse_open_count} tone="bg-orange-100 text-orange-700" href="/admin/security-monitor/abuse" />
        <KpiCard icon={AlertOctagon} label="Onaysız alarm" value={d.unack_alarm_count} tone="bg-amber-100 text-amber-700" href="/admin/security-monitor/alarms" />
      </section>

      {/* Sistem hatası kısa özet + rol dağılımı */}
      <section className="grid gap-4 lg:grid-cols-3">
        <Link href="/admin/security-monitor/system" className="lg:col-span-1">
          <Card className="flex h-full items-center gap-3 p-4 transition hover:border-foreground/30">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-rose-100 text-rose-700">
              <Bug className="size-5" aria-hidden />
            </span>
            <div>
              <div className="text-2xl font-semibold tabular-nums">{d.system_error_summary.open_groups}</div>
              <div className="text-xs text-muted-foreground">
                Açık hata grubu · son 24s {d.system_error_summary.new_groups_24h} yeni
              </div>
            </div>
          </Card>
        </Link>
        <Card className="p-4 lg:col-span-2">
          <h3 className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
            <Users className="size-4 text-muted-foreground" aria-hidden />
            Aktif oturum rol dağılımı
          </h3>
          {Object.keys(d.role_counts).length === 0 ? (
            <p className="text-sm text-muted-foreground">Aktif oturum yok.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {Object.entries(d.role_counts).map(([role, count]) => (
                <span
                  key={role}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-3 py-1 text-xs"
                >
                  <span className="font-medium">{roleLabel(role)}</span>
                  <span className="tabular-nums text-muted-foreground">{count}</span>
                </span>
              ))}
            </div>
          )}
        </Card>
      </section>

      {/* Aktif kimliğe-bürünme oturumları */}
      {d.active_impersonations.length > 0 ? (
        <section>
          <Card className="border-l-4 border-l-rose-500 bg-rose-50/40 p-4">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold text-rose-800">
              <UserCog className="size-4" aria-hidden />
              Aktif kimliğe-bürünme oturumları ({d.active_impersonations.length})
            </h2>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-2 py-1 text-left">Yönetici</th>
                    <th className="px-2 py-1 text-left">Hedef kullanıcı</th>
                    <th className="px-2 py-1 text-left">Gerekçe</th>
                    <th className="px-2 py-1 text-left">Başladı</th>
                    <th className="px-2 py-1 text-right">Kalan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rose-100">
                  {d.active_impersonations.map((imp) => (
                    <tr key={imp.id}>
                      <td className="px-2 py-1.5">
                        <div className="font-medium">{imp.actor_full_name ?? `#${imp.actor_user_id}`}</div>
                        <div className="text-[11px] text-muted-foreground">{imp.actor_email}</div>
                      </td>
                      <td className="px-2 py-1.5">
                        <div className="font-medium">{imp.target_full_name ?? `#${imp.target_user_id}`}</div>
                        <div className="text-[11px] text-muted-foreground">{imp.target_email}</div>
                      </td>
                      <td className="px-2 py-1.5 text-muted-foreground">{imp.reason ?? "—"}</td>
                      <td className="px-2 py-1.5 text-muted-foreground">{fmtDateTime(imp.started_at)}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">
                        {imp.is_expired_now ? (
                          <span className="text-rose-600">süresi doldu</span>
                        ) : (
                          `${Math.ceil(imp.seconds_left / 60)} dk`
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>
      ) : null}

      {/* 2 sütun: Aktif oturumlar + Şüpheli IP'ler */}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <Activity className="size-4 text-indigo-600" aria-hidden />
              Aktif oturumlar
            </h2>
            <span className="text-xs text-muted-foreground">{d.active_sessions.length}</span>
          </div>
          {d.active_sessions.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Aktif oturum yok.</p>
          ) : (
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-card text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-1.5 text-left">Kullanıcı</th>
                    <th className="px-3 py-1.5 text-left">Rol</th>
                    <th className="px-3 py-1.5 text-left">IP</th>
                    <th className="px-3 py-1.5 text-right">Boşta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.active_sessions.map((sess) => (
                    <tr key={sess.id} className="hover:bg-muted/40">
                      <td className="px-3 py-1.5">
                        <div className="font-medium">{sess.user_full_name ?? sess.user_email}</div>
                        <div className="text-[11px] text-muted-foreground">{sess.user_email}</div>
                      </td>
                      <td className="px-3 py-1.5 text-muted-foreground">{roleLabel(sess.role)}</td>
                      <td className="px-3 py-1.5 font-mono text-[11px] text-muted-foreground">{sess.ip ?? "—"}</td>
                      <td className="px-3 py-1.5 text-right text-muted-foreground">{humanizeAgo(sess.idle_seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <Eye className="size-4 text-amber-600" aria-hidden />
              Şüpheli / blokli IP&apos;ler
            </h2>
            <span className="text-xs text-muted-foreground">{d.suspicious_ips.length}</span>
          </div>
          {d.suspicious_ips.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Şüpheli IP yok.</p>
          ) : (
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-card text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-1.5 text-left">IP</th>
                    <th className="px-3 py-1.5 text-right">Başarısız</th>
                    <th className="px-3 py-1.5 text-right">Hesap</th>
                    <th className="px-3 py-1.5 text-center">Durum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.suspicious_ips.map((ip) => (
                    <tr key={ip.id} className="hover:bg-muted/40">
                      <td className="px-3 py-1.5 font-mono text-[11px]">{ip.ip}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{ip.fail_count}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{ip.distinct_email_count}</td>
                      <td className="px-3 py-1.5 text-center">
                        {ip.is_blocked ? (
                          <span className="inline-flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[11px] font-medium text-rose-700">
                            <Ban className="size-3" aria-hidden /> Blokli
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                            İzleniyor
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      {/* Kritik aksiyon akışı + Süper admin girişleri */}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <ShieldAlert className="size-4 text-rose-600" aria-hidden />
              Kritik aksiyon akışı
            </h2>
          </div>
          {d.critical_audits.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Kritik aksiyon yok.</p>
          ) : (
            <ul className="max-h-96 divide-y divide-border overflow-auto">
              {d.critical_audits.map((a) => (
                <li key={a.id} className="flex items-start justify-between gap-3 px-4 py-2 text-sm">
                  <div className="min-w-0">
                    <div className="font-medium">{a.action_label}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {a.email_attempted ?? (a.actor_id != null ? `Aktör #${a.actor_id}` : "—")}
                      {a.via_admin != null ? (
                        <span className="ml-1 rounded bg-violet-100 px-1 text-violet-700">admin #{a.via_admin}</span>
                      ) : null}
                    </div>
                  </div>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{fmtDateTime(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <BadgeCheck className="size-4 text-violet-600" aria-hidden />
              Süper admin girişleri (24s)
            </h2>
          </div>
          {d.super_admin_logins.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Son 24 saatte süper admin girişi yok.</p>
          ) : (
            <ul className="max-h-96 divide-y divide-border overflow-auto">
              {d.super_admin_logins.map((a) => (
                <li key={a.id} className="flex items-start justify-between gap-3 px-4 py-2 text-sm">
                  <div className="min-w-0">
                    <div className="font-medium">{a.email_attempted ?? `Aktör #${a.actor_id}`}</div>
                    <div className="font-mono text-[11px] text-muted-foreground">{a.ip_address ?? "—"}</div>
                  </div>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{fmtDateTime(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </div>
  );
}
