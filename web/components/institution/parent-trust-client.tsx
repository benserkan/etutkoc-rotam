"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { HeartHandshake, Mail, MailWarning, UserCheck, Users } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { institutionKeys, getInstitutionParentTrust } from "@/lib/api/institution";
import type { ParentTrustResponse } from "@/lib/types/institution";

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
    </div>
  );
}
