"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { HeartHandshake, List, Mail, MailWarning, UserCheck, Users } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import {
  institutionKeys,
  getInstitutionParentTrust,
  getInstitutionParentTrustNotifications,
} from "@/lib/api/institution";
import type {
  ParentTrustNotificationListResponse,
  ParentTrustResponse,
} from "@/lib/types/institution";

interface Props {
  initial: ParentTrustResponse;
}

function pct(v: number | null): string {
  return v == null ? "—" : `%${v}`;
}
function successColor(v: number | null): string {
  if (v == null) return "text-muted-foreground";
  if (v >= 95) return "text-emerald-700";
  if (v >= 80) return "text-amber-700";
  return "text-rose-700";
}

export function ParentTrustClient({ initial }: Props) {
  const q = useQuery<ParentTrustResponse>({
    queryKey: institutionKeys.parentTrust(30),
    queryFn: () => getInstitutionParentTrust(30),
    initialData: initial,
    staleTime: 30_000,
  });
  const d = q.data ?? initial;
  const s = d.summary;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <HeartHandshake className="size-6 text-indigo-700" aria-hidden />
          Veli Güveni
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Kurumun veli nezdindeki değeri: kaç öğrencinin velisi sistemde, veliler
          aktif mi ve onlara giden bildirimler ulaşıyor mu (son {s.days} gün).
        </p>
      </header>

      {/* Özet KPI */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="p-4">
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            <Users className="size-3.5" aria-hidden /> Veli kapsaması
          </div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{pct(s.coverage_pct)}</div>
          <div className="text-[11px] text-muted-foreground">{s.covered_students}/{s.total_students} öğrencinin velisi bağlı</div>
        </Card>
        <Card className="p-4">
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            <UserCheck className="size-3.5" aria-hidden /> Aktif veli
          </div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{s.active_parents}</div>
          <div className="text-[11px] text-muted-foreground">{s.parent_count} bağlı veliden son {s.days}g giriş</div>
        </Card>
        <Card className={cn("p-4", s.pending_invites > 0 && "border-amber-300 bg-amber-50/40")}>
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            <Mail className="size-3.5" aria-hidden /> Bekleyen davet
          </div>
          <div className={cn("mt-1 text-3xl font-bold tabular-nums", s.pending_invites > 0 ? "text-amber-700" : "")}>{s.pending_invites}</div>
          <div className="text-[11px] text-muted-foreground">kabul bekleyen veli daveti</div>
        </Card>
        <Card className="p-4">
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-muted-foreground">
            <MailWarning className="size-3.5" aria-hidden /> Bildirim başarısı
          </div>
          <div className={cn("mt-1 text-3xl font-bold tabular-nums", successColor(s.notif_success_pct))}>{pct(s.notif_success_pct)}</div>
          <div className="text-[11px] text-muted-foreground">{s.notif_sent} ulaştı · {s.notif_failed} başarısız</div>
        </Card>
      </section>

      {/* Kanal kırılımı */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-2.5">
          <h2 className="text-sm font-semibold">Bildirim kanalları (son {s.days} gün)</h2>
          <p className="text-xs text-muted-foreground">Velilere giden bildirimlerin kanal bazında teslim sağlığı.</p>
        </div>
        {d.channels.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Bu dönemde velilere bildirim gönderilmemiş.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr><th className="px-3 py-1.5 text-left">Kanal</th><th className="px-3 py-1.5 text-right">Ulaştı</th><th className="px-3 py-1.5 text-right">Başarısız</th><th className="px-3 py-1.5 text-right">Engellendi</th><th className="px-3 py-1.5 text-right">Başarı</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.channels.map((c) => (
                  <tr key={c.channel} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5 font-medium">{c.channel_label}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-emerald-700">{c.sent}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-rose-700">{c.failed}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">{c.suppressed}</td>
                    <td className={cn("px-3 py-1.5 text-right font-semibold tabular-nums", successColor(c.success_pct))}>{pct(c.success_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {s.coverage_pct != null && s.coverage_pct < 60 ? (
        <Card className="border-amber-300 bg-amber-50/40 p-4 text-sm text-amber-900">
          Veli kapsaması düşük (%{s.coverage_pct}). Öğretmenleri velileri sisteme davet etmeye
          teşvik edin — veli iletişimi kayıt yenilemeyi ve memnuniyeti güçlendirir.
        </Card>
      ) : null}

      <NotificationDetailSection days={s.days} />
    </div>
  );
}


const STATUS_TONE: Record<string, { text: string; bg: string; border: string }> = {
  sent:       { text: "text-emerald-800", bg: "bg-emerald-50",  border: "border-emerald-200" },
  failed:     { text: "text-rose-800",    bg: "bg-rose-50",     border: "border-rose-200" },
  suppressed: { text: "text-slate-700",   bg: "bg-slate-50",    border: "border-slate-200" },
  queued:     { text: "text-amber-800",   bg: "bg-amber-50",    border: "border-amber-200" },
};

function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2,"0")}.${String(d.getMonth()+1).padStart(2,"0")} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`;
}

function NotificationDetailSection({ days }: { days: number }) {
  const [status, setStatus] = React.useState<string | null>(null);
  const q = useQuery<ParentTrustNotificationListResponse>({
    queryKey: institutionKeys.parentTrustNotifications(days, status),
    queryFn: () => getInstitutionParentTrustNotifications(days, status),
    staleTime: 30_000,
  });
  const items = q.data?.items ?? [];
  const total = q.data?.total_count ?? 0;

  const FILTERS: Array<{ key: string | null; label: string; tone?: string }> = [
    { key: null, label: "Tümü" },
    { key: "sent", label: "Ulaştı", tone: "text-emerald-700" },
    { key: "failed", label: "Başarısız", tone: "text-rose-700" },
    { key: "suppressed", label: "Engellendi", tone: "text-slate-700" },
  ];

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-4 py-2.5">
        <h2 className="inline-flex items-center gap-1.5 text-sm font-semibold">
          <List className="size-4 text-muted-foreground" aria-hidden />
          Son {days} gün bildirim detayı
        </h2>
        <p className="text-xs text-muted-foreground">
          Hangi veliye/öğrenciye giden bildirim ulaştı/başarısız oldu — tek tek.
          Başarısız satırlardaki hata satırı sebebi gösterir.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2 text-xs">
        {FILTERS.map((f) => (
          <button
            key={f.key ?? "all"}
            type="button"
            onClick={() => setStatus(f.key)}
            className={cn(
              "rounded-full border px-3 py-1 transition",
              status === f.key
                ? "border-foreground bg-foreground/5 font-medium"
                : "border-border text-muted-foreground hover:bg-muted/40",
              f.tone,
            )}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-muted-foreground tabular-nums">
          {q.isLoading ? "yükleniyor…" : `${items.length}${total !== items.length ? ` / ${total}` : ""} kayıt`}
        </span>
      </div>
      {items.length === 0 && !q.isLoading ? (
        <p className="p-6 text-center text-sm text-muted-foreground">
          Bu dönemde bu filtreyle eşleşen bildirim yok.
        </p>
      ) : (
        <div className="divide-y divide-border">
          {items.map((n) => {
            const tone = STATUS_TONE[n.status] ?? STATUS_TONE.suppressed;
            return (
              <div key={n.id} className="px-4 py-3">
                <div className="flex items-start gap-3">
                  <span
                    className={cn(
                      "shrink-0 rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
                      tone.text, tone.bg, tone.border,
                    )}
                  >
                    {n.status_label}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                      <span className="text-sm font-medium">{n.kind_label}</span>
                      <span className="text-xs text-muted-foreground">·</span>
                      <span className="text-xs text-muted-foreground">{n.channel_label}</span>
                      <span className="ml-auto text-[11px] text-muted-foreground tabular-nums">
                        {fmtDateTime(n.sent_at ?? n.created_at)}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {n.student_name ? <span>öğrenci: <b className="text-foreground">{n.student_name}</b></span> : null}
                      {n.parent_email ? <span className="ml-2">→ {n.parent_email}</span> : null}
                    </div>
                    {n.subject ? (
                      <div className="mt-0.5 truncate text-xs italic text-muted-foreground">
                        {n.subject}
                      </div>
                    ) : null}
                    {n.error ? (
                      <div className="mt-1 rounded border border-rose-200 bg-rose-50/60 px-2 py-1 text-xs text-rose-800">
                        <span className="font-semibold">Hata:</span> {n.error}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
