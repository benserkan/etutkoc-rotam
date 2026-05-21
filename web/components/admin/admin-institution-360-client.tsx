"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2, Settings, ScrollText } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminRevenueInstitution360 } from "@/lib/api/admin";
import type { InstitutionRevenue360Response } from "@/lib/types/admin";
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
  initial: InstitutionRevenue360Response;
  institutionId: number;
}

export function AdminInstitution360Client({ initial, institutionId }: Props) {
  const [tab, setTab] = React.useState("health");
  const q = useQuery<InstitutionRevenue360Response>({
    queryKey: adminKeys.revenueInstitution360(institutionId),
    queryFn: () => getAdminRevenueInstitution360(institutionId),
    initialData: initial,
    staleTime: 15_000,
  });
  const d = q.data ?? initial;
  const ident = d.identity;
  const usage = d.usage_30d;
  const billing = d.billing;

  const tabs = [
    { id: "health", label: "Sağlık ve Riskler", badge: d.risks.length },
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
              <Building2 className="size-6 text-indigo-700" aria-hidden />
              {ident.name}
            </span>
            <StatusBadge label={ident.is_active ? "Aktif" : "Pasif"} tone={ident.is_active ? "emerald" : "slate"} />
            <StatusBadge label={ident.plan_label} tone="sky" />
          </h1>
          <div className="mt-1 font-mono text-sm text-muted-foreground">
            {ident.slug}
            {ident.contact_email ? ` · ${ident.contact_email}` : ""}
          </div>
          <TagBadges tags={d.owner_tags} />
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={`/admin/institutions/${ident.id}/account-history`}
            className="inline-flex items-center gap-1.5 rounded-md border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100"
          >
            <ScrollText className="size-4" aria-hidden />
            Hesap Hareketleri
          </Link>
          <Link
            href={`/admin/institutions/${ident.id}`}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium hover:bg-muted"
          >
            <Settings className="size-4" aria-hidden />
            Yönetim
          </Link>
        </div>
      </header>

      {/* Üst KPI */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Sağlık Skoru" value={d.health.score != null ? `${d.health.score}` : "—"} sub={d.health.label} tone={d.health.color} />
        <Kpi label="Aylık Katkı" value={tl(ident.plan_monthly_price_try)} sub={ident.plan_monthly_price_try > 0 ? "aylık" : "ücretsiz / deneme"} tone="emerald" />
        <Kpi
          label="Son 30g Aktif"
          value={`${usage.active_teacher_count + usage.active_student_count}`}
          sub={`${usage.active_teacher_count}/${usage.total_teacher_count} öğr · ${usage.active_student_count}/${usage.total_student_count} öğrenci`}
          tone="indigo"
        />
        <Kpi
          label="Ödeme Durumu"
          value={billing.overdue_count > 0 ? `${billing.overdue_count}!` : billing.next_due_at ? "✓" : "—"}
          sub={
            billing.overdue_count > 0
              ? `${tl(billing.overdue_total_try)} gecikmiş`
              : billing.next_due_at
                ? `sonraki: ${fmtDate(billing.next_due_at)}`
                : "ödeme yok"
          }
          tone={billing.overdue_count > 0 ? "rose" : billing.next_due_at ? "amber" : "slate"}
        />
      </div>

      <TabBar tabs={tabs} active={tab} onChange={setTab} />

      {tab === "health" ? (
        <div className="space-y-4">
          <HealthV2Card health={d.health_v2} triggers={d.health_triggers} history={d.health_history} />
          <Card className="overflow-hidden">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">Açık Riskler ({d.risks.length})</h2>
            </div>
            {d.risks.length === 0 ? (
              <div className="px-4 py-10 text-center text-sm text-emerald-700">Açık risk yok — temiz.</div>
            ) : (
              <ul className="divide-y divide-border">
                {d.risks.map((r, i) => {
                  const tone = r.severity === "critical" ? "rose" : r.severity === "risk" ? "amber" : "slate";
                  return (
                    <li key={i} className="flex items-start gap-3 px-4 py-3">
                      <div className={cn("w-1 self-stretch rounded", `bg-${tone}-500`)} />
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium">{r.title}</span>
                          <span className={cn("rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase", badge(tone))}>
                            {r.severity}
                          </span>
                        </div>
                        {r.message ? <div className="mt-0.5 text-xs text-muted-foreground">{r.message}</div> : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      ) : null}

      {tab === "usage" ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi label="Aktif Öğretmen" value={`${usage.active_teacher_count}`} sub={`${usage.total_teacher_count} kayıtlı${usage.teacher_active_pct != null ? ` · %${usage.teacher_active_pct}` : ""}`} tone="indigo" />
          <Kpi label="Aktif Öğrenci" value={`${usage.active_student_count}`} sub={`${usage.total_student_count} kayıtlı${usage.student_active_pct != null ? ` · %${usage.student_active_pct}` : ""}`} tone="emerald" />
          <Kpi label="Bildirim — Gitti" value={`${usage.notification_sent}`} sub="son 30 günde" tone="sky" />
          <Kpi label="Bildirim — Hata" value={`${usage.notification_failed}`} sub="son 30 günde" tone={usage.notification_failed > 0 ? "rose" : "slate"} />
        </div>
      ) : null}

      {tab === "billing" ? (
        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold">Mevcut Plan</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
              <Field label="Plan" value={ident.plan_label} mono={ident.plan} />
              <Field label="Aylık fiyat" value={ident.plan_monthly_price_try > 0 ? tl(ident.plan_monthly_price_try) : "—"} />
              <Field label="Abonelik tipi" value={ident.subscription_kind ?? "—"} />
              {ident.trial_ends_at ? <Field label="Deneme bitiş" value={fmtDate(ident.trial_ends_at)} /> : null}
              {ident.subscription_period_end ? <Field label="Akademik yıl bitiş" value={fmtDate(ident.subscription_period_end)} /> : null}
              {ident.performance_guarantee ? <Field label="Garanti" value="60 gün performans aktif" /> : null}
            </dl>
          </Card>
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold">Fatura Özeti</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <Field label="Son ödeme" value={billing.last_paid_at ? `${fmtDate(billing.last_paid_at)} · ${tl(billing.last_paid_amount_try)}` : "—"} />
              <Field label="Sonraki vade" value={billing.next_due_at ? `${fmtDate(billing.next_due_at)} · ${tl(billing.next_due_amount_try)}` : "yok"} />
              <Field label="Gecikmiş" value={billing.overdue_count > 0 ? `${billing.overdue_count} adet · ${tl(billing.overdue_total_try)}` : "yok"} />
              <Field label="Yaşam boyu ödenmiş" value={tl(billing.lifetime_paid_try)} />
            </dl>
          </Card>
          <InvoicesTable invoices={d.invoices} />
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold">Plan Değişiklik Geçmişi</h2>
            <PlanChangesTimeline changes={d.plan_changes} />
          </Card>
        </div>
      ) : null}

      {tab === "offers" ? <OffersPanel ownerType="institution" ownerId={institutionId} offers={d.offers} meta={d.meta} /> : null}
      {tab === "notes" ? <CrmNotesPanel ownerType="institution" ownerId={institutionId} notes={d.crm_notes} /> : null}
      {tab === "actions" ? <CrmActionsPanel ownerType="institution" ownerId={institutionId} actions={d.crm_actions} meta={d.meta} /> : null}
      {tab === "contact" ? <ContactAndTagsPanel ownerType="institution" ownerId={institutionId} contact={d.owner_contact} tags={d.owner_tags} meta={d.meta} /> : null}
    </div>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: string }) {
  const cls: Record<string, string> = {
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900",
    rose: "bg-rose-50 border-rose-200 text-rose-900",
    amber: "bg-amber-50 border-amber-200 text-amber-900",
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-900",
    sky: "bg-sky-50 border-sky-200 text-sky-900",
    slate: "bg-slate-50 border-slate-200 text-slate-900",
    yellow: "bg-yellow-50 border-yellow-200 text-yellow-900",
  };
  return (
    <div className={cn("rounded-lg border p-4", cls[tone] ?? cls.slate)}>
      <div className="text-[10px] uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      <div className="text-[11px] opacity-70">{sub}</div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
      {mono ? <dd className="font-mono text-[11px] text-muted-foreground">{mono}</dd> : null}
    </div>
  );
}
