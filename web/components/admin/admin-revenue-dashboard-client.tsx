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
      // Her drill üst toggle'ın seçili segment'ini takip eder.
      // health:* ve invoice_bucket:* kurum-merkezli kalır (backend zaten görmezden gelir).
      const seg = segment as "all" | "institution" | "user";
      const res = await getAdminRevenueDrill(key, plan, seg);
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
                      className="flex items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900 transition hover:bg-amber-100 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200 dark:hover:bg-amber-500/20"
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
                        b.key.startsWith("overdue") ? "border-rose-300 bg-rose-50 text-rose-900 hover:bg-rose-100 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200 dark:hover:bg-rose-500/20"
                          : ["due_today", "due_tomorrow"].includes(b.key) ? "border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200 dark:hover:bg-amber-500/20"
                          : "border-emerald-300 bg-emerald-50 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200 dark:hover:bg-emerald-500/20",
                      )}>
                <div className="text-[10px] font-semibold uppercase tracking-wide opacity-80">{b.label}</div>
                <div className="mt-0.5 text-2xl font-bold">{b.count}</div>
                <div className="text-xs font-semibold opacity-90">{tl(b.total_try)}</div>
              </button>
            ))}
          </div>
        </Card>
      ) : null}

      {/* Alt KPI grid — segment-aware (mrr_combined kullanır) */}
      {d.mrr_combined ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <KpiButton
            label="Aylık Gelir"
            value={tl(d.mrr_combined.total_try)}
            sub={segment === "all"
              ? `${d.mrr_combined.paying_count} ödeyen (${d.mrr_combined.institution_paying_count} kurum + ${d.mrr_combined.user_paying_count} koç)`
              : segment === "institution"
                ? `${d.mrr_combined.institution_paying_count} ödeyen kurum`
                : `${d.mrr_combined.user_paying_count} ödeyen koç`}
            tone="emerald"
            onClick={() => openDrill("paying")}
          />
          <KpiButton
            label={segment === "all" ? "Toplam Sahip" : segment === "institution" ? "Toplam Kurum" : "Toplam Koç"}
            value={`${d.mrr_combined.total_owners}`}
            sub={segment === "all"
              ? `${d.mrr_combined.institution_count} kurum + ${d.mrr_combined.user_count} koç`
              : segment === "institution"
                ? `${d.mrr_combined.institution_count - d.mrr_combined.institution_paying_count} ücretsiz`
                : `${d.mrr_combined.user_count - d.mrr_combined.user_paying_count} ücretsiz`}
            tone="blue"
            onClick={() => openDrill("free")}
          />
          <KpiButton
            label="Denemesi Yakın"
            value={`${d.trial_combined.length}`}
            sub={`son 30g ${d.trial_expired_30d} denemesi bitti`}
            tone="amber"
            onClick={() => openDrill("trial:expired_30d")}
          />
          <KpiButton
            label="Terk Riski"
            value={`${cp.unhealthy_total}`}
            sub={cp.critical > 0
              ? `${cp.critical} kritik · ${cp.risk} risk`
              : cp.unhealthy_total > 0
                ? `${cp.risk} risk · ${cp.watch} izle`
                : "temiz"}
            tone={cp.critical > 0 ? "rose" : cp.unhealthy_total > 0 ? "amber" : "emerald"}
            onClick={() => openDrill(cp.critical > 0 ? "health:critical" : "health:risk")}
          />
        </div>
      ) : null}
      {segment !== "all" ? (
        <p className="-mt-2 text-[11px] text-muted-foreground">
          <strong>Not:</strong> Terk Riski yalnız kurumlar için hesaplanır (sağlık endeksi tenant-bazlı).
          Koç riski için <Link href="/admin/revenue/action-center" className="text-indigo-600 underline">Aksiyon Merkezi</Link>&apos;ne bakın.
        </p>
      ) : null}

      {/* Plan hareketleri (30g) */}
      <section>
        <div className="mb-2 flex items-baseline gap-2">
          <h2 className="text-sm font-semibold text-muted-foreground">Son 30 günde plan hareketleri</h2>
          <span className="text-[11px] text-muted-foreground">
            ({segment === "all" ? "Kurum + Bağımsız Koç" : segment === "institution" ? "Yalnız kurumlar" : "Yalnız bağımsız koçlar"})
          </span>
        </div>
        <div className="mb-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-700">
          <strong className="text-slate-900">Ne demek?</strong>{" "}
          <span><strong>Yeni kayıt</strong>: ilk kez sisteme dahil oldu.</span>{" · "}
          <span><strong>Yükselen</strong>: ücretsizden ücretliye veya daha üst pakete geçti.</span>{" · "}
          <span><strong>Düşüren</strong>: pakedi küçülttü.</span>{" · "}
          <span><strong>Net Büyüme</strong>: yükselen − düşüren (pozitif = büyüme).</span>{" · "}
          <span><strong>Duraklatma</strong>: yaz penceresinde pakedi geçici dondurma.</span>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <ChangeKpi label="Yeni kayıt" value={cs.signups} tooltip="İlk kayıt — kurumun/koçun sisteme yeni eklendiği an" onClick={cs.signups > 0 ? () => openDrill("plan_change:signup") : undefined} />
          <ChangeKpi label="Yükselen" value={`↑ ${cs.upgrades}`} tone="emerald" tooltip="Pakete yükseltme — daha üst plana geçen" onClick={cs.upgrades > 0 ? () => openDrill("plan_change:upgrade") : undefined} />
          <ChangeKpi label="Düşüren" value={`↓ ${cs.downgrades}`} tone="rose" tooltip="Paket alçaltma — daha alt plana inen" onClick={cs.downgrades > 0 ? () => openDrill("plan_change:downgrade") : undefined} />
          <ChangeKpi label="Net Büyüme" value={`${cs.net_growth >= 0 ? "+" : ""}${cs.net_growth}`} tone={cs.net_growth >= 0 ? "emerald" : "rose"} tooltip="Yükselen − Düşüren. Pozitif = paket büyümesi." />
          <ChangeKpi label="Duraklatma" value={cs.pauses} tooltip="Yaz penceresinde pakedi geçici durduranlar" onClick={cs.pauses > 0 ? () => openDrill("plan_change:pause") : undefined} />
        </div>
      </section>

      {/* Plan Dağılımı — segment-aware (plan_dist_combined kullanır) */}
      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">Plan Dağılımı</h2>
          <p className="text-xs text-muted-foreground">
            Her pakette kaç {segment === "all" ? "kurum/koç" : segment === "institution" ? "kurum" : "koç"} + aylık katkı.
            Satıra tıkla → liste açılır.
          </p>
        </div>
        {(d.plan_dist_combined ?? []).length === 0 ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">Veri yok.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Paket</th>
                  {segment === "all" ? (
                    <>
                      <th className="px-3 py-2 text-right">Toplam</th>
                      <th className="px-3 py-2 text-right">Kurum</th>
                      <th className="px-3 py-2 text-right">Koç</th>
                    </>
                  ) : (
                    <th className="px-3 py-2 text-right">{segment === "institution" ? "Kurum" : "Koç"}</th>
                  )}
                  <th className="px-3 py-2 text-right">Aylık fiyat</th>
                  <th className="px-3 py-2 text-right">Aylık katkı</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(d.plan_dist_combined ?? []).map((p) => (
                  <tr key={p.plan} className="cursor-pointer hover:bg-muted/40" onClick={() => openDrill(`plan:${p.plan}`, p.plan)}>
                    <td className="px-3 py-2">
                      <div>{p.label}</div>
                      <code className="text-[11px] text-muted-foreground">{p.plan}</code>
                    </td>
                    {segment === "all" ? (
                      <>
                        <td className="px-3 py-2 text-right font-semibold text-indigo-700">{p.count} →</td>
                        <td className="px-3 py-2 text-right text-blue-700">{p.institution_count}</td>
                        <td className="px-3 py-2 text-right text-violet-700">{p.user_count}</td>
                      </>
                    ) : (
                      <td className="px-3 py-2 text-right font-semibold text-indigo-700">
                        {segment === "institution" ? p.institution_count : p.user_count} →
                      </td>
                    )}
                    <td className="px-3 py-2 text-right text-muted-foreground">{p.monthly_price_try > 0 ? `${p.monthly_price_try} ₺` : "—"}</td>
                    <td className={cn("px-3 py-2 text-right", p.estimated_mrr > 0 ? "font-semibold text-emerald-700" : "text-muted-foreground")}>
                      {p.estimated_mrr > 0 ? tl(p.estimated_mrr) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

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
                <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800">{drill.count} kayıt</span>
              </div>
              <button type="button" onClick={() => setDrill(null)} className="text-muted-foreground hover:text-foreground" aria-label="Kapat">
                <X className="size-4" aria-hidden />
              </button>
            </div>
            {drill.rows.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-muted-foreground">Bu kategoride kayıt yok — temiz.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-muted/40 text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left">Kim</th>
                      <th className="px-3 py-2 text-left">Plan Hareketi</th>
                      <th className="px-3 py-2 text-right">Aylık</th>
                      <th className="px-3 py-2 text-left">Ne zaman</th>
                      <th className="px-3 py-2 text-right" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {drill.rows.map((r, idx) => {
                      const isUser = r.owner_type === "user";
                      const hasMovement = r.from_plan_label || r.to_plan_label;
                      return (
                        <tr key={`${r.owner_type}-${r.owner_id}-${idx}`} className="hover:bg-muted/40">
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-2">
                              <span
                                className={cn(
                                  "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium",
                                  isUser
                                    ? "bg-violet-100 text-violet-800"
                                    : "bg-blue-100 text-blue-800",
                                )}
                                title={isUser ? "Bağımsız koç" : "Kurum"}
                              >
                                {isUser ? "Koç" : "Kurum"}
                              </span>
                              <div className="font-medium">{r.display_name}</div>
                            </div>
                            <div className="ml-7 font-mono text-[10px] text-muted-foreground">
                              {isUser ? `user #${r.user_id}` : `#${r.institution_id}`}
                              {r.user_email ? ` · ${r.user_email}` : ""}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            {hasMovement ? (
                              <div className="space-y-0.5">
                                <div className="flex items-center gap-1">
                                  <span className="text-muted-foreground">{r.from_plan_label ?? "—"}</span>
                                  <span className="text-indigo-600">→</span>
                                  <span className="font-medium text-foreground">{r.to_plan_label ?? "—"}</span>
                                </div>
                                <code className="block text-[10px] text-muted-foreground">{r.from_plan ?? "—"} → {r.to_plan ?? "—"}</code>
                              </div>
                            ) : (
                              <div>
                                <div>{r.plan_label}</div>
                                <code className="text-[10px] text-muted-foreground">{r.plan}</code>
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2 text-right">
                            {r.monthly_price_try && r.monthly_price_try > 0 ? (
                              <span className="font-semibold text-emerald-700">{tl(r.monthly_price_try)}</span>
                            ) : <span className="text-muted-foreground">—</span>}
                          </td>
                          <td className="max-w-xs break-words px-3 py-2 text-muted-foreground">
                            {r.event_at ? (
                              <div>
                                {new Date(r.event_at).toLocaleString("tr-TR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                                {r.event_days_ago != null ? (
                                  <span className="ml-1 text-[10px]">({r.event_days_ago === 0 ? "bugün" : `${r.event_days_ago} gün önce`})</span>
                                ) : null}
                              </div>
                            ) : r.reason ? (
                              <span>{r.reason}</span>
                            ) : (
                              <span>—</span>
                            )}
                            {r.health_score != null ? (
                              <div className="text-[10px]">Sağlık: {r.health_score}/100</div>
                            ) : null}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right">
                            <Link href={r.detail_url || (isUser ? `/admin/revenue/users/${r.user_id}` : `/admin/revenue/institutions/${r.institution_id}`)}
                                  className="inline-flex items-center gap-0.5 font-medium text-indigo-600 hover:text-indigo-800">
                              360 <ArrowUpRight className="size-3" aria-hidden />
                            </Link>
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
      </div>

      <p className="text-xs text-muted-foreground">
        Veri zamanı: {new Date(d.generated_at).toLocaleString("tr-TR")}
      </p>
    </div>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: string }) {
  const cls: Record<string, string> = {
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-900 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
    amber: "bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
    sky: "bg-sky-50 border-sky-200 text-sky-900 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
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
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200 dark:hover:bg-emerald-500/20",
    blue: "bg-blue-50 border-blue-200 text-blue-900 hover:bg-blue-100 dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-200 dark:hover:bg-blue-500/20",
    amber: "bg-amber-50 border-amber-200 text-amber-900 hover:bg-amber-100 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200 dark:hover:bg-amber-500/20",
    rose: "bg-rose-50 border-rose-200 text-rose-900 hover:bg-rose-100 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200 dark:hover:bg-rose-500/20",
  };
  return (
    <button type="button" onClick={onClick} className={cn("rounded-lg border p-4 text-left transition", cls[tone] ?? cls.blue)}>
      <div className="text-xs uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-[11px] underline underline-offset-2 opacity-70">{sub} →</div>
    </button>
  );
}

function ChangeKpi({ label, value, tone, onClick, tooltip }: { label: string; value: number | string; tone?: string; onClick?: () => void; tooltip?: string }) {
  const text = tone === "emerald" ? "text-emerald-700 dark:text-emerald-400" : tone === "rose" ? "text-rose-700 dark:text-rose-400" : "text-foreground";
  const inner = (
    <>
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <span>{label}</span>
        {tooltip ? (
          <span title={tooltip} className="cursor-help text-slate-400" aria-label={tooltip}>
            ⓘ
          </span>
        ) : null}
      </div>
      <div className={cn("mt-0.5 text-xl font-semibold", text)}>{value}</div>
      {onClick ? <div className="mt-1 text-[10px] text-indigo-600 underline underline-offset-2">→ Listeyi gör</div> : null}
    </>
  );
  if (onClick) {
    return <button type="button" onClick={onClick} className="rounded-lg border border-border bg-card p-3 text-left hover:bg-muted">{inner}</button>;
  }
  return <div className="rounded-lg border border-border bg-card p-3">{inner}</div>;
}
