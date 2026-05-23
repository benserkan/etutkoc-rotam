"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Building2,
  CircleDollarSign,
  ClipboardList,
  Clock,
  Heart,
  ListChecks,
  Loader2,
  Megaphone,
  Receipt,
  Target,
  TrendingUp,
  UserRound,
  Wallet,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import {
  adminKeys,
  getAdminRevenueDashboard,
  getAdminRevenueDrill,
} from "@/lib/api/admin";
import type {
  RevenueDashboardResponse,
  RevenueDrillResponse,
} from "@/lib/types/admin";
import { tl } from "@/components/admin/revenue-360-shared";

interface Props {
  initial: RevenueDashboardResponse;
}

function daysUntil(iso: string | null): number | null {
  if (!iso) return null;
  const diff = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(diff / 86_400_000));
}

const SEGMENTS: { value: string; label: string }[] = [
  { value: "all", label: "Hepsi" },
  { value: "institution", label: "Kurumlar" },
  { value: "user", label: "Bağımsız" },
];

const QUICK_LINKS = [
  { href: "/admin/revenue/forecast", label: "Tahmin", icon: TrendingUp },
  { href: "/admin/revenue/campaigns", label: "Kampanyalar", icon: Megaphone },
  { href: "/admin/revenue/cohort", label: "Kohort & LTV", icon: Heart },
  { href: "/admin/revenue/action-center", label: "Aksiyon Merkezi", icon: Target },
  { href: "/admin/revenue/action-templates", label: "Şablonlar", icon: ClipboardList },
];

export function AdminRevenueDashboardClient({ initial }: Props) {
  const [segment, setSegment] = React.useState(initial.segment ?? "all");
  const q = useQuery<RevenueDashboardResponse>({
    queryKey: adminKeys.revenueDashboard(segment),
    queryFn: () => getAdminRevenueDashboard(segment),
    initialData: segment === initial.segment ? initial : undefined,
    staleTime: 15_000,
  });
  const d = q.data ?? initial;
  const cs = d.change_summary_30d;
  const cp = d.churn_proxy;

  // Drill paneli
  const [drill, setDrill] = React.useState<RevenueDrillResponse | null>(null);
  const [drillLoading, setDrillLoading] = React.useState(false);
  const drillRef = React.useRef<HTMLDivElement>(null);

  async function openDrill(key: string, plan?: string) {
    setDrillLoading(true);
    try {
      const res = await getAdminRevenueDrill(key, plan);
      setDrill(res);
      setTimeout(() => drillRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    } finally {
      setDrillLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <span className="text-sm text-muted-foreground">Güvenlik Kamarası</span>
          <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <CircleDollarSign className="size-6 text-emerald-700" aria-hidden />
            Ticari Pano
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Aylık gelir, plan dağılımı, denemesi bitenler, plan hareketleri,
            ödeme takvimi ve terk riski — bir bakışta. KPI&apos;lara tıkla → arkasındaki
            kurum listesi açılır.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {QUICK_LINKS.map((l) => (
            <Link key={l.href} href={l.href}
                  className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium hover:bg-muted">
              <l.icon className="size-3.5" aria-hidden />
              {l.label}
            </Link>
          ))}
        </div>
      </header>

      {/* Segment toggle (owner-aware) */}
      {d.mrr_combined ? (
        <Card className="p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">
              {segment === "all" ? "Birleşik Görünüm (Kurum + Bağımsız Öğretmen)"
                : segment === "institution" ? "Sadece Kurumlar" : "Sadece Bağımsız Öğretmenler"}
            </h2>
            <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5 text-xs">
              {SEGMENTS.map((s) => (
                <button key={s.value} type="button" onClick={() => setSegment(s.value)}
                        className={cn(
                          "rounded-md px-3 py-1.5 font-medium transition",
                          segment === s.value ? "bg-card text-indigo-700 shadow-sm" : "text-muted-foreground hover:text-foreground",
                        )}>
                  {s.label}
                  <span className="ml-0.5 text-[10px] opacity-60">({d.segment_counts[s.value] ?? 0})</span>
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Kpi label="Toplam Aylık Gelir" value={tl(d.mrr_combined.total_try)} tone="emerald"
                 sub={segment === "all" ? `Kurum ${tl(d.mrr_combined.institution_mrr_try)} · Öğretmen ${tl(d.mrr_combined.user_mrr_try)}` : "MRR"} />
            <Kpi label="Toplam Aktif Sahip" value={`${d.mrr_combined.total_owners}`} tone="indigo"
                 sub={`${d.mrr_combined.institution_count} kurum + ${d.mrr_combined.user_count} öğretmen`} />
            <Kpi label="Ödeyen" value={`${d.mrr_combined.paying_count}`} tone="amber"
                 sub={`${d.mrr_combined.institution_paying_count} kurum + ${d.mrr_combined.user_paying_count} öğretmen`} />
            <Kpi label="Ortalama Aylık" value={tl(d.mrr_combined.avg_per_paying)} tone="sky" sub="ödeyen başına" />
          </div>
          {d.trial_combined.length > 0 ? (
            <div className="mt-4 border-t border-border pt-4">
              <div className="mb-2.5 flex items-center gap-2 text-sm font-semibold">
                <Clock className="size-4 text-amber-600" aria-hidden />
                7 gün içinde denemesi bitenler
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">
                  {d.trial_combined.length}
                </span>
                <span className="text-xs font-normal text-muted-foreground">— dönüşüm fırsatı</span>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {d.trial_combined.slice(0, 12).map((o, idx) => {
                  const dl = daysUntil(o.trial_ends_at);
                  return (
                    <Link
                      key={`${o.owner_type}-${o.owner_id}-${idx}`}
                      href={o.url}
                      className="flex items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900 transition hover:bg-amber-100"
                    >
                      <span className="flex min-w-0 items-center gap-1.5">
                        {o.owner_type === "institution"
                          ? <Building2 className="size-4 shrink-0 opacity-70" aria-hidden />
                          : <UserRound className="size-4 shrink-0 opacity-70" aria-hidden />}
                        <span className="truncate text-sm font-medium">{o.name}</span>
                      </span>
                      {dl != null ? (
                        <span className={cn(
                          "shrink-0 rounded px-1.5 py-0.5 text-[11px] font-bold",
                          dl <= 1 ? "bg-rose-200 text-rose-900" : dl <= 3 ? "bg-amber-200 text-amber-900" : "bg-white text-amber-800",
                        )}>
                          {dl} gün
                        </span>
                      ) : null}
                    </Link>
                  );
                })}
              </div>
              {d.trial_combined.length > 12 ? (
                <p className="mt-2 text-xs text-muted-foreground">+{d.trial_combined.length - 12} daha</p>
              ) : null}
            </div>
          ) : null}
        </Card>
      ) : null}

      {/* Ödeme takvimi */}
      {d.payment_calendar.total_count > 0 ? (
        <Card className={cn("overflow-hidden", d.payment_calendar.overdue_total_try > 0 ? "border-rose-200" : "border-amber-200")}>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
            <div>
              <h2 className="inline-flex items-center gap-1.5 text-sm font-semibold">
                <Wallet className="size-4" aria-hidden />
                Ödeme Takvimi — Önümüzdeki {d.payment_calendar.days_horizon} Gün
              </h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {d.payment_calendar.total_count} fatura · toplam {tl(d.payment_calendar.total_amount_try)}
                {d.payment_calendar.overdue_total_try > 0 ? ` (gecikti: ${tl(d.payment_calendar.overdue_total_try)})` : ""}
              </p>
            </div>
            <Link href="/admin/security-monitor/revenue/invoices"
                  className="inline-flex items-center gap-1 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium hover:bg-muted">
              <Receipt className="size-3.5" aria-hidden /> Tüm faturalar
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-2 p-3 md:grid-cols-4">
            {d.payment_calendar.buckets.map((b) => (
              <button key={b.key} type="button" onClick={() => openDrill(`invoice_bucket:${b.key}`)}
                      className={cn(
                        "rounded-lg border p-2.5 text-left transition",
                        b.key.startsWith("overdue") ? "border-rose-300 bg-rose-50 text-rose-900 hover:bg-rose-100"
                          : ["due_today", "due_tomorrow"].includes(b.key) ? "border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100"
                          : "border-emerald-300 bg-emerald-50 text-emerald-900 hover:bg-emerald-100",
                      )}>
                <div className="text-[10px] font-semibold uppercase tracking-wide opacity-80">{b.label}</div>
                <div className="mt-0.5 text-2xl font-bold">{b.count}</div>
                <div className="text-xs font-semibold opacity-90">{tl(b.total_try)}</div>
              </button>
            ))}
          </div>
        </Card>
      ) : null}

      {/* Üst KPI (kurum-merkezli, drill'li) */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiButton label="Aylık Gelir" value={tl(d.mrr.total_try)} sub={`${d.mrr.paying_institutions} ödeyen kurum`}
                   tone="emerald" onClick={() => openDrill("paying")} />
        <KpiButton label="Toplam Kurum" value={`${d.mrr.total_institutions}`} sub={`${d.mrr.free_institutions} ücretsiz`}
                   tone="blue" onClick={() => openDrill("free")} />
        <KpiButton label="Denemesi Yakın" value={`${d.trial_ending_soon.length}`} sub={`son 30g ${d.trial_expired_30d} bitti`}
                   tone="amber" onClick={() => openDrill("trial:expired_30d")} />
        <KpiButton label="Terk Riski" value={`${cp.unhealthy_total}`}
                   sub={cp.critical > 0 ? `${cp.critical} kritik · ${cp.risk} risk` : cp.unhealthy_total > 0 ? `${cp.risk} risk · ${cp.watch} izle` : "temiz"}
                   tone={cp.critical > 0 ? "rose" : cp.unhealthy_total > 0 ? "amber" : "emerald"}
                   onClick={() => openDrill(cp.critical > 0 ? "health:critical" : "health:risk")} />
      </div>

      {/* Plan hareketleri (30g) */}
      <section>
        <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Son 30 günde plan hareketleri</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <ChangeKpi label="Yeni kayıt" value={cs.signups} onClick={cs.signups > 0 ? () => openDrill("plan_change:signup") : undefined} />
          <ChangeKpi label="Yükselen" value={`↑ ${cs.upgrades}`} tone="emerald" onClick={cs.upgrades > 0 ? () => openDrill("plan_change:upgrade") : undefined} />
          <ChangeKpi label="Düşüren" value={`↓ ${cs.downgrades}`} tone="rose" onClick={cs.downgrades > 0 ? () => openDrill("plan_change:downgrade") : undefined} />
          <ChangeKpi label="Net Büyüme" value={`${cs.net_growth >= 0 ? "+" : ""}${cs.net_growth}`} tone={cs.net_growth >= 0 ? "emerald" : "rose"} />
          <ChangeKpi label="Duraklatma" value={cs.pauses} onClick={cs.pauses > 0 ? () => openDrill("plan_change:pause") : undefined} />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Plan dağılımı */}
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Plan Dağılımı</h2>
            <p className="text-xs text-muted-foreground">Her pakette kaç kurum + aylık katkı. Satıra tıkla → kurum listesi.</p>
          </div>
          {d.plan_distribution.length === 0 ? (
            <div className="px-4 py-6 text-sm text-muted-foreground">Veri yok.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Paket</th>
                  <th className="px-3 py-2 text-right">Kurum</th>
                  <th className="px-3 py-2 text-right">Aylık fiyat</th>
                  <th className="px-3 py-2 text-right">Aylık katkı</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.plan_distribution.map((p) => (
                  <tr key={p.plan} className="cursor-pointer hover:bg-muted/40" onClick={() => openDrill(`plan:${p.plan}`, p.plan)}>
                    <td className="px-3 py-2">
                      <div>{p.label}</div>
                      <code className="text-[11px] text-muted-foreground">{p.plan}</code>
                    </td>
                    <td className="px-3 py-2 text-right font-semibold text-indigo-700">{p.count} →</td>
                    <td className="px-3 py-2 text-right text-muted-foreground">{p.monthly_price_try > 0 ? `${p.monthly_price_try} ₺` : "—"}</td>
                    <td className={cn("px-3 py-2 text-right", p.estimated_mrr > 0 ? "font-semibold text-emerald-700" : "text-muted-foreground")}>
                      {p.estimated_mrr > 0 ? tl(p.estimated_mrr) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {/* Denemesi bitenler */}
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Denemesi Bitmek Üzere — 7 Gün</h2>
            <p className="text-xs text-muted-foreground">Ödeyen müşteriye dönüşüm fırsatı.</p>
          </div>
          {d.trial_ending_soon.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">7 gün içinde denemesi biten kurum yok.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Kurum</th>
                  <th className="px-3 py-2 text-left">Paket</th>
                  <th className="px-3 py-2 text-right">Kalan</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.trial_ending_soon.map((t, idx) => (
                  <tr key={`${t.institution_id}-${idx}`} className="hover:bg-muted/40">
                    <td className="px-3 py-2">
                      <Link href={`/admin/revenue/institutions/${t.institution_id}`} className="font-medium hover:text-indigo-700">
                        {t.institution_name}
                      </Link>
                    </td>
                    <td className="px-3 py-2"><code className="text-xs">{t.plan}</code></td>
                    <td className="px-3 py-2 text-right">
                      <span className={cn(
                        "rounded px-2 py-0.5 text-xs",
                        t.days_left <= 1 ? "bg-rose-100 text-rose-800" : t.days_left <= 3 ? "bg-amber-100 text-amber-800" : "bg-blue-100 text-blue-800",
                      )}>{t.days_left} gün</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      {/* Drill paneli */}
      <div ref={drillRef}>
        {drillLoading ? (
          <Card className="p-6 text-center text-sm text-muted-foreground">
            <Loader2 className="mx-auto size-5 animate-spin" aria-hidden />
          </Card>
        ) : drill ? (
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-2.5">
              <div className="inline-flex items-center gap-2 text-sm">
                <ListChecks className="size-4" aria-hidden />
                <span className="font-semibold">{drill.title}</span>
                <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800">{drill.count} kurum</span>
              </div>
              <button type="button" onClick={() => setDrill(null)} className="text-muted-foreground hover:text-foreground" aria-label="Kapat">
                <X className="size-4" aria-hidden />
              </button>
            </div>
            {drill.rows.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-muted-foreground">Bu kategoride kurum yok — temiz.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-muted/40 text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left">Kurum</th>
                      <th className="px-3 py-2 text-left">Paket</th>
                      <th className="px-3 py-2 text-right">Aylık</th>
                      <th className="px-3 py-2 text-left">Sebep / Detay</th>
                      <th className="px-3 py-2 text-right" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {drill.rows.map((r, idx) => (
                      <tr key={`${r.institution_id}-${idx}`} className="hover:bg-muted/40">
                        <td className="px-3 py-2">
                          <div className="font-medium">{r.institution_name}</div>
                          <div className="font-mono text-[10px] text-muted-foreground">#{r.institution_id}</div>
                        </td>
                        <td className="px-3 py-2">
                          <div>{r.plan_label}</div>
                          <code className="text-[10px] text-muted-foreground">{r.plan}</code>
                        </td>
                        <td className="px-3 py-2 text-right">
                          {r.monthly_price_try && r.monthly_price_try > 0 ? (
                            <span className="font-semibold text-emerald-700">{tl(r.monthly_price_try)}</span>
                          ) : <span className="text-muted-foreground">—</span>}
                        </td>
                        <td className="max-w-md break-words px-3 py-2 text-muted-foreground">
                          {r.reason ?? "—"}
                          {r.health_score != null ? (
                            <div className="text-[10px]">Sağlık: {r.health_score}/100</div>
                          ) : null}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-right">
                          <Link href={r.detail_url || `/admin/revenue/institutions/${r.institution_id}`}
                                className="inline-flex items-center gap-0.5 font-medium text-indigo-600 hover:text-indigo-800">
                            360 <ArrowUpRight className="size-3" aria-hidden />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        ) : null}
      </div>

      <p className="text-xs text-muted-foreground">
        Veri zamanı: {new Date(d.generated_at).toLocaleString("tr-TR")}
      </p>
    </div>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: string }) {
  const cls: Record<string, string> = {
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900",
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-900",
    amber: "bg-amber-50 border-amber-200 text-amber-900",
    sky: "bg-sky-50 border-sky-200 text-sky-900",
  };
  return (
    <div className={cn("rounded-lg border p-3", cls[tone] ?? cls.indigo)}>
      <div className="text-[10px] uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 font-mono text-xl font-semibold">{value}</div>
      <div className="text-[11px] opacity-70">{sub}</div>
    </div>
  );
}

function KpiButton({ label, value, sub, tone, onClick }: { label: string; value: string; sub: string; tone: string; onClick: () => void }) {
  const cls: Record<string, string> = {
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900 hover:bg-emerald-100",
    blue: "bg-blue-50 border-blue-200 text-blue-900 hover:bg-blue-100",
    amber: "bg-amber-50 border-amber-200 text-amber-900 hover:bg-amber-100",
    rose: "bg-rose-50 border-rose-200 text-rose-900 hover:bg-rose-100",
  };
  return (
    <button type="button" onClick={onClick} className={cn("rounded-lg border p-4 text-left transition", cls[tone] ?? cls.blue)}>
      <div className="text-xs uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-[11px] underline underline-offset-2 opacity-70">{sub} →</div>
    </button>
  );
}

function ChangeKpi({ label, value, tone, onClick }: { label: string; value: number | string; tone?: string; onClick?: () => void }) {
  const text = tone === "emerald" ? "text-emerald-700" : tone === "rose" ? "text-rose-700" : "text-foreground";
  const inner = (
    <>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("mt-0.5 text-xl font-semibold", text)}>{value}</div>
      {onClick ? <div className="mt-1 text-[10px] text-indigo-600 underline underline-offset-2">→ Listeyi gör</div> : null}
    </>
  );
  if (onClick) {
    return <button type="button" onClick={onClick} className="rounded-lg border border-border bg-card p-3 text-left hover:bg-muted">{inner}</button>;
  }
  return <div className="rounded-lg border border-border bg-card p-3">{inner}</div>;
}
