"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ScrollText, Settings, UserRound } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminRevenueUser360 } from "@/lib/api/admin";
import type { UserRevenue360Response } from "@/lib/types/admin";
import { StatusBadge } from "@/components/admin/feature-catalog-ui";
import {
  ContactAndTagsPanel,
  CrmActionsPanel,
  CrmNotesPanel,
  HealthV2Card,
  InvoicesTable,
  OffersPanel,
  PlanChangesTimeline,
  TabBar,
  TagBadges,
  badge,
  fmtDate,
  tl,
} from "@/components/admin/revenue-360-shared";

interface Props {
  initial: UserRevenue360Response;
  userId: number;
}

const STUDENT_BAND: Record<string, { tone: string; label: string }> = {
  healthy: { tone: "emerald", label: "Aktif" },
  watch: { tone: "yellow", label: "Gözlem" },
  risk: { tone: "amber", label: "Riskli" },
  critical: { tone: "rose", label: "Kritik" },
};

export function AdminUser360Client({ initial, userId }: Props) {
  const [tab, setTab] = React.useState("health");
  const q = useQuery<UserRevenue360Response>({
    queryKey: adminKeys.revenueUser360(userId),
    queryFn: () => getAdminRevenueUser360(userId),
    initialData: initial,
    staleTime: 15_000,
  });
  const d = q.data ?? initial;
  const owner = d.owner;
  const sh = d.student_health;

  const tabs = [
    { id: "health", label: "Sağlık", badge: sh.unhealthy_total },
    { id: "students", label: "Öğrenciler", badge: d.all_students_total },
    { id: "usage", label: "Kullanım" },
    { id: "billing", label: "Plan & Ödeme" },
    { id: "offers", label: "Teklifler", badge: d.offers.length },
    { id: "notes", label: "Notlar", badge: d.crm_notes.length },
    { id: "actions", label: "Aksiyonlar", badge: d.crm_actions.length },
    { id: "contact", label: "İletişim & Etiketler" },
  ];

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link href="/admin/revenue/action-center" className="text-sm text-muted-foreground hover:text-foreground">
            ← Ticari Pano
          </Link>
          <h1 className="mt-1 flex flex-wrap items-center gap-3 font-display text-2xl font-semibold tracking-tight">
            <span className="inline-flex items-center gap-2">
              <UserRound className="size-6 text-indigo-700" aria-hidden />
              {owner.name}
            </span>
            <StatusBadge label={owner.is_active ? "Aktif" : "Pasif"} tone={owner.is_active ? "emerald" : "slate"} />
            <StatusBadge label={owner.plan} tone="sky" />
            <StatusBadge label="Bağımsız Öğretmen" tone="indigo" />
          </h1>
          <div className="mt-1 text-sm text-muted-foreground">{owner.email ?? "—"}</div>
          <TagBadges tags={d.owner_tags} />
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={`/admin/users/${owner.owner_id}/account-history`}
            className="inline-flex items-center gap-1.5 rounded-md border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200"
          >
            <ScrollText className="size-4" aria-hidden />
            Hesap Hareketleri
          </Link>
          <Link
            href={`/admin/users/${owner.owner_id}`}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium hover:bg-muted"
          >
            <Settings className="size-4" aria-hidden />
            Yönetim
          </Link>
        </div>
      </header>

      {/* Üst KPI */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi
          label="Sağlık Skoru"
          value={d.health_v2 ? `${d.health_v2.score}` : "—"}
          sub={d.health_v2 ? d.health_v2.band_label : `son giriş: ${d.teacher_login_label}`}
          tone={d.health_v2 ? d.health_v2.band_color : "slate"}
        />
        <Kpi label="Aylık Katkı" value={tl(owner.monthly_price_try)} sub={owner.monthly_price_try > 0 ? "aylık" : "ücretsiz / deneme"} tone="emerald" />
        <Kpi label="Öğrenci" value={`${d.student_count}`} sub={`${sh.healthy} aktif (7g)${sh.unhealthy_total ? ` · ${sh.unhealthy_total} risk` : ""}`} tone="indigo" />
        <Kpi label="Tamamlama (30g)" value={`%${d.completion_pct}`} sub={`${d.tasks_completed_30d}/${d.tasks_planned_30d} test`} tone="sky" />
      </div>

      <TabBar tabs={tabs} active={tab} onChange={setTab} />

      {tab === "health" ? (
        <div className="space-y-4">
          <HealthV2Card health={d.health_v2} history={d.score_history} />
          <Card className="overflow-hidden">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">Öğrenci Sağlığı ({sh.total} aktif öğrenci)</h2>
            </div>
            <div className="grid grid-cols-4 divide-x divide-border">
              <BandStat label="7g aktif" value={sh.healthy} tone="emerald" />
              <BandStat label="7-14g" value={sh.watch} tone="yellow" />
              <BandStat label="14-30g" value={sh.risk} tone="amber" />
              <BandStat label="30g+ / Yok" value={sh.critical} tone="rose" />
            </div>
          </Card>
        </div>
      ) : null}

      {tab === "students" ? (
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Öğrenci Listesi ({d.all_students_total})</h2>
            <p className="text-[11px] text-muted-foreground">Pasif öğrenciler altta · sağlık bandına göre sıralı</p>
          </div>
          {d.student_rows.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">Bu öğretmenin öğrencisi yok.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Durum</th>
                    <th className="px-4 py-2 text-left font-medium">Öğrenci</th>
                    <th className="px-4 py-2 text-left font-medium">Sınıf</th>
                    <th className="px-4 py-2 text-left font-medium">Son Giriş</th>
                    <th className="px-4 py-2 text-left font-medium">Aktif/Pasif</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.student_rows.map((s) => {
                    const b = STUDENT_BAND[s.band] ?? { tone: "slate", label: s.band };
                    return (
                      <tr key={s.id} className={cn("hover:bg-muted/40", !s.is_active && "opacity-60")}>
                        <td className="px-4 py-2">
                          <span className={cn("inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-semibold", badge(b.tone))}>
                            {b.label}
                          </span>
                        </td>
                        <td className="px-4 py-2">{s.full_name ?? "—"}</td>
                        <td className="px-4 py-2 text-xs text-muted-foreground">
                          {s.grade_level ? `${s.grade_level}. sınıf` : "—"}
                        </td>
                        <td className="px-4 py-2 text-xs">{s.label}</td>
                        <td className="px-4 py-2 text-xs">
                          {s.is_active ? <span className="text-emerald-700">aktif</span> : <span className="text-muted-foreground">pasif</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : null}

      {tab === "usage" ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Kpi label="Toplam Öğrenci" value={`${d.all_students_total}`} sub={`${d.student_count} aktif`} tone="slate" />
            <Kpi label="Son 7g Aktif Öğrenci" value={`${sh.healthy}`} sub={`/ ${d.student_count} aktif`} tone="emerald" />
            <Kpi label="Planlı Test (30g)" value={`${d.tasks_planned_30d}`} sub={`${d.tasks_completed_30d} çözüldü · %${d.completion_pct}`} tone="indigo" />
            <Kpi label="Taslak Görev" value={`${d.tasks_draft_30d}`} sub="son 30g · yayınlanmamış" tone="amber" />
          </div>
          <Card className="p-4 text-xs text-muted-foreground">
            Bağımsız öğretmen tek kişi — &quot;öğretmen ekibi&quot; metriği yok. Onun yerine kendi öğrencilerinin
            aktivitesi öğretmenin değer üretip üretmediğini gösterir.
          </Card>
        </div>
      ) : null}

      {tab === "billing" ? (
        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold">Mevcut Plan</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
              <Field label="Plan" value={owner.plan} />
              <Field label="Aylık fiyat" value={tl(owner.monthly_price_try)} />
              {owner.trial_ends_at ? <Field label="Deneme bitiş" value={fmtDate(owner.trial_ends_at)} /> : null}
            </dl>
          </Card>
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold">Plan Değişiklik Geçmişi</h2>
            <PlanChangesTimeline changes={d.plan_changes} />
          </Card>
          <InvoicesTable invoices={d.invoices} />
        </div>
      ) : null}

      {tab === "offers" ? <OffersPanel ownerType="user" ownerId={userId} offers={d.offers} meta={d.meta} /> : null}
      {tab === "notes" ? <CrmNotesPanel ownerType="user" ownerId={userId} notes={d.crm_notes} /> : null}
      {tab === "actions" ? <CrmActionsPanel ownerType="user" ownerId={userId} actions={d.crm_actions} meta={d.meta} /> : null}
      {tab === "contact" ? <ContactAndTagsPanel ownerType="user" ownerId={userId} contact={d.owner_contact} tags={d.owner_tags} meta={d.meta} /> : null}
    </div>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: string }) {
  const cls: Record<string, string> = {
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
    rose: "bg-rose-50 border-rose-200 text-rose-900 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
    amber: "bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-900 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
    sky: "bg-sky-50 border-sky-200 text-sky-900 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
    lime: "bg-lime-50 border-lime-200 text-lime-900 dark:bg-lime-500/10 dark:border-lime-500/30 dark:text-lime-200",
    orange: "bg-orange-50 border-orange-200 text-orange-900 dark:bg-orange-500/10 dark:border-orange-500/30 dark:text-orange-200",
    slate: "bg-slate-50 border-slate-200 text-slate-900 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-200",
  };
  return (
    <div className={cn("rounded-lg border p-4", cls[tone] ?? cls.slate)}>
      <div className="text-[10px] uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      <div className="text-[11px] opacity-70">{sub}</div>
    </div>
  );
}

function BandStat({ label, value, tone }: { label: string; value: number; tone: string }) {
  const text: Record<string, string> = {
    emerald: "text-emerald-700",
    yellow: "text-yellow-700",
    amber: "text-amber-700",
    rose: "text-rose-700",
  };
  return (
    <div className="px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={cn("mt-0.5 text-2xl font-bold", text[tone] ?? "text-foreground")}>{value}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
