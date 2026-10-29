"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BellRing,
  Clock,
  Mail,
  MessageSquare,
  ShieldOff,
  TrendingUp,
  XCircle,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminSecurityNotifications } from "@/lib/api/admin";
import type {
  NotifMatrix,
  NotifWindowSummary,
  NotificationHealthResponse,
} from "@/lib/types/admin";
import { fmtDateTime, fmtPct, successPctColor } from "@/components/admin/security-ui";
import { NotifTrendBarChart } from "@/components/admin/notif-trend-bar-chart";

interface Props {
  initial: NotificationHealthResponse;
}

const STATUS_LABEL: Record<string, string> = {
  queued: "Kuyrukta",
  sent: "Gönderildi",
  failed: "Başarısız",
  suppressed: "Engellendi",
};

const CHANNEL_LABEL: Record<string, string> = {
  email: "E-posta",
  whatsapp: "WhatsApp",
  sms: "SMS",
};

function rowLabel(row: string, isChannel: boolean): string {
  if (isChannel) return CHANNEL_LABEL[row] ?? row;
  return row;
}

function SummaryCard({ s }: { s: NotifWindowSummary }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{s.window_label}</h3>
        <span className={cn("text-lg font-semibold tabular-nums", successPctColor(s.success_pct))}>
          {fmtPct(s.success_pct)}
        </span>
      </div>
      <p className="text-[11px] text-muted-foreground">başarı oranı (gönderildi / gönderildi+başarısız)</p>
      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
        <div>
          <div className="text-base font-semibold tabular-nums text-emerald-600">{s.sent}</div>
          <div className="text-[10px] text-muted-foreground">Gönderildi</div>
        </div>
        <div>
          <div className="text-base font-semibold tabular-nums text-rose-600">{s.failed}</div>
          <div className="text-[10px] text-muted-foreground">Başarısız</div>
        </div>
        <div>
          <div className="text-base font-semibold tabular-nums text-amber-600">{s.queued}</div>
          <div className="text-[10px] text-muted-foreground">Kuyrukta</div>
        </div>
        <div>
          <div className="text-base font-semibold tabular-nums text-slate-500">{s.suppressed}</div>
          <div className="text-[10px] text-muted-foreground">Engellendi</div>
        </div>
      </div>
      <div className="mt-2 border-t border-border pt-2 text-center text-[11px] text-muted-foreground">
        Toplam {s.total} kayıt
      </div>
    </Card>
  );
}

function MatrixTable({
  title,
  icon: Icon,
  matrix,
  isChannel,
}: {
  title: string;
  icon: typeof Mail;
  matrix: NotifMatrix;
  isChannel: boolean;
}) {
  const visibleRows = matrix.rows.filter((r) => (matrix.rollups[r]?.total ?? 0) > 0);
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-4 py-2.5">
        <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
          <Icon className="size-4 text-indigo-600" aria-hidden />
          {title}
        </h2>
      </div>
      {visibleRows.length === 0 ? (
        <p className="p-6 text-center text-sm text-muted-foreground">Son 24 saatte kayıt yok.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-1.5 text-left">{isChannel ? "Kanal" : "Tür"}</th>
                {matrix.statuses.map((st) => (
                  <th key={st} className="px-3 py-1.5 text-right">{STATUS_LABEL[st] ?? st}</th>
                ))}
                <th className="px-3 py-1.5 text-right">Başarı</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {visibleRows.map((r) => {
                const roll = matrix.rollups[r];
                return (
                  <tr key={r} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5 font-medium">{rowLabel(r, isChannel)}</td>
                    {matrix.statuses.map((st) => {
                      const v = matrix.matrix[r]?.[st] ?? 0;
                      return (
                        <td
                          key={st}
                          className={cn(
                            "px-3 py-1.5 text-right tabular-nums",
                            v === 0 && "text-muted-foreground/40",
                            st === "failed" && v > 0 && "font-medium text-rose-600",
                          )}
                        >
                          {v}
                        </td>
                      );
                    })}
                    <td className={cn("px-3 py-1.5 text-right tabular-nums font-medium", successPctColor(roll?.success_pct))}>
                      {fmtPct(roll?.success_pct ?? null)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function SecurityNotificationsClient({ initial }: Props) {
  const q = useQuery<NotificationHealthResponse>({
    queryKey: adminKeys.securityNotifications(),
    queryFn: getAdminSecurityNotifications,
    initialData: initial,
    staleTime: 15_000,
  });
  const d = q.data ?? initial;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <BellRing className="size-6 text-slate-700" aria-hidden />
          Bildirim Sağlığı
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Velilere giden e-posta/WhatsApp bildirimlerinin teslimat sağlığı: başarı oranı,
          kanal ve tür bazında dağılım, neden engellendikleri ve son başarısız gönderimler.
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">Son güncelleme: {fmtDateTime(d.generated_at)}</p>
      </header>

      {/* Özet kartları */}
      <section className="grid gap-3 md:grid-cols-2">
        <SummaryCard s={d.summary_24h} />
        <SummaryCard s={d.summary_7d} />
      </section>

      {/* En eski kuyruk uyarısı */}
      {d.oldest_queued_minutes != null && d.oldest_queued_minutes > 0 ? (
        <Card
          className={cn(
            "flex items-center gap-3 border-l-4 p-3 text-sm",
            d.oldest_queued_minutes >= 60
              ? "border-l-rose-500 bg-rose-50/40 text-rose-800"
              : "border-l-amber-500 bg-amber-50/40 text-amber-800",
          )}
        >
          <Clock className="size-5 shrink-0" aria-hidden />
          En eski kuyrukta bekleyen bildirim {d.oldest_queued_minutes} dakikadır gönderilmeyi bekliyor.
        </Card>
      ) : null}

      {/* 7 günlük trend */}
      <section>
        <Card className="p-4">
          <h2 className="mb-3 inline-flex items-center gap-2 text-sm font-semibold">
            <TrendingUp className="size-4 text-indigo-600" aria-hidden />
            Son 7 gün teslimat trendi
          </h2>
          <NotifTrendBarChart series={d.daily_trend_7d} />
        </Card>
      </section>

      {/* Kanal + tür matrisi */}
      <section className="grid gap-4 lg:grid-cols-2">
        <MatrixTable title="Kanal × durum (24s)" icon={Mail} matrix={d.channel_matrix_24h} isChannel />
        <MatrixTable title="Tür × durum (24s)" icon={MessageSquare} matrix={d.kind_matrix_24h} isChannel={false} />
      </section>

      {/* Suppress dağılımı + son hatalar */}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <ShieldOff className="size-4 text-slate-600" aria-hidden />
              Engellenme nedenleri (24s)
            </h2>
          </div>
          {d.suppress_distribution_24h.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Engellenen bildirim yok.</p>
          ) : (
            <ul className="divide-y divide-border">
              {d.suppress_distribution_24h.map((r) => (
                <li key={r.slug} className="flex items-center justify-between px-4 py-2 text-sm">
                  <span>{r.label}</span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium tabular-nums">{r.count}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <XCircle className="size-4 text-rose-600" aria-hidden />
              Son başarısız gönderimler (24s)
            </h2>
          </div>
          {d.recent_failures_24h.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Başarısız gönderim yok.</p>
          ) : (
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-card text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-1.5 text-left">Alıcı</th>
                    <th className="px-3 py-1.5 text-left">Kanal</th>
                    <th className="px-3 py-1.5 text-left">Hata</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.recent_failures_24h.map((f) => (
                    <tr key={f.id} className="hover:bg-muted/40">
                      <td className="px-3 py-1.5">
                        <div className="font-medium">{f.parent_name ?? f.parent_email ?? `#${f.parent_id ?? "?"}`}</div>
                        {f.student_name ? (
                          <div className="text-[11px] text-muted-foreground">öğr: {f.student_name}</div>
                        ) : null}
                      </td>
                      <td className="px-3 py-1.5 text-muted-foreground">
                        {CHANNEL_LABEL[f.channel] ?? f.channel}
                      </td>
                      <td className="px-3 py-1.5 text-[11px] text-rose-600" title={f.error}>
                        <span className="line-clamp-2">{f.error || "—"}</span>
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
