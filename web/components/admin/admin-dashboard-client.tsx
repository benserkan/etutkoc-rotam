"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Building2,
  CalendarDays,
  ClipboardList,
  FileText,
  GraduationCap,
  Heart,
  Inbox,
  Megaphone,
  Send,
  Shield,
  Stethoscope,
  Target,
  TrendingUp,
  Users,
  UserCircle2,
  Wallet,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { getAdminDashboard, getAdminActivityStream, adminKeys } from "@/lib/api/admin";
import type { ActivityStreamResponse } from "@/lib/types/institution";
import type {
  AdminDashboardResponse,
  AuditLogItem,
  HealthAssessmentItem,
  HealthLevel,
  HealthSummary,
  IndependentTeacherActivitySummary,
  IndependentTeacherRiskRow,
} from "@/lib/types/admin";

interface Props {
  initial: AdminDashboardResponse;
}

/**
 * Süper admin dashboard — Jinja `dashboard.html` feature parity.
 *
 * 5 bölüm:
 *  1. Hesap özeti — 4 kart (kurum/bağımsız öğretmen/öğrenci/yönetici)
 *  2. Yüksek failed-login uyarısı (>10)
 *  3. Ticari & ödemeler — kısayol kart grid
 *  4. Sistem & güvenlik — kısayol kart grid
 *  5. Müşteri sağlığı — kurum + bağımsız öğretmen yan yana, top-3
 *  6. Son audit olayları tablosu
 *
 * UI yaklaşımı: shadcn flavored, fresh; Jinja gradient'lerin yerine
 * tonal border-l-4 + soft bg accent.
 */
export function AdminDashboardClient({ initial }: Props) {
  const q = useQuery<AdminDashboardResponse>({
    queryKey: adminKeys.dashboard(),
    queryFn: () => getAdminDashboard(),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-6">
      <header>
        <p className="text-[11px] uppercase tracking-wider text-amber-700 font-semibold inline-flex items-center gap-1">
          <Shield className="size-3.5" aria-hidden />
          Süper Admin
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
          Süper Admin Paneli
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Tüm sistemi buradan yönetebilirsin. Kurum/kullanıcı sayıları,
          müşteri sağlığı, ticari pano kısayolları ve son aktiviteler.
        </p>
      </header>

      <AccountsOverview counts={data.counts} health={data.health_summary} activity={data.teacher_activity_summary} />

      {data.failed_logins_24h > 10 && (
        <FailedLoginsBanner count={data.failed_logins_24h} />
      )}

      {(data.pending_contact_requests ?? 0) > 0 && (
        <PendingRequestsBanner
          subscription={data.pending_subscription_requests ?? 0}
          total={data.pending_contact_requests ?? 0}
        />
      )}

      <ActivitySummary />

      <CommercialShortcuts />

      <SystemShortcuts />

      <CustomerHealth
        health={data.health_summary}
        topUnhealthy={data.top_unhealthy}
        activity={data.teacher_activity_summary}
        topTeacherRisk={data.top_teacher_risk}
      />

      <RecentAudits audits={data.recent_audits} />
    </div>
  );
}

// ============================================================================
// Aktivite Özeti — son 7 gün üyelik + davet hareketleri (her satır → 360)
// ============================================================================

function ActivitySummary() {
  const q = useQuery<ActivityStreamResponse>({
    queryKey: adminKeys.activityStream(7, null),
    queryFn: () => getAdminActivityStream(7, null, 50),
    staleTime: 30_000,
  });
  const counts = q.data?.counts ?? {};
  const items = (q.data?.items ?? []).slice(0, 6);

  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="inline-flex items-center gap-1.5 text-sm font-semibold">
            <Activity className="size-4 text-indigo-700" aria-hidden />
            Son 7 Gün — Üyelik &amp; Davet Aktivitesi
          </h2>
          <Link
            href="/admin/activity-stream"
            className="inline-flex items-center gap-0.5 text-xs font-medium text-indigo-700 hover:underline"
          >
            Tüm aktivite <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <ActivityKpi label="Paket satın alma" value={counts.purchases ?? 0} highlight />
          <ActivityKpi label="Yeni kayıt" value={counts.signup ?? 0} />
          <ActivityKpi label="Davetler" value={counts.invitation ?? 0} />
          <ActivityKpi label="Ticari talep" value={counts.commercial ?? 0} />
        </div>

        <div className="divide-y divide-border">
          {items.length === 0 ? (
            <p className="py-2 text-sm text-muted-foreground">
              Son 7 günde yeni üyelik veya davet aktivitesi yok.
            </p>
          ) : (
            items.map((it) => {
              const Wrapper: React.ElementType = it.detail_url ? Link : "div";
              const wrapperProps = it.detail_url ? { href: it.detail_url } : {};
              return (
                <Wrapper
                  key={it.id}
                  {...wrapperProps}
                  className={cn(
                    "flex items-center gap-3 py-2 text-sm",
                    it.detail_url &&
                      "-mx-2 rounded px-2 transition-colors hover:bg-muted/50",
                  )}
                >
                  <span
                    className={cn(
                      "size-1.5 shrink-0 rounded-full",
                      it.is_commercial ? "bg-emerald-500" : "bg-slate-300",
                    )}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{it.title}</span>
                    {it.subtitle ? (
                      <span className="block truncate text-xs text-muted-foreground">
                        {it.subtitle}
                      </span>
                    ) : null}
                  </span>
                  {it.detail_url ? (
                    <span className="inline-flex shrink-0 items-center gap-0.5 text-[11px] text-indigo-700">
                      360 <ArrowRight className="size-3" aria-hidden />
                    </span>
                  ) : null}
                </Wrapper>
              );
            })
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ActivityKpi({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-2.5",
        highlight ? "border-emerald-200 bg-emerald-50/50" : "border-border bg-muted/30",
      )}
    >
      <div
        className={cn(
          "text-lg font-semibold tabular-nums",
          highlight ? "text-emerald-700" : "text-foreground",
        )}
      >
        {value}
      </div>
      <div className="text-[10px] uppercase leading-tight tracking-wider text-muted-foreground">
        {label}
      </div>
    </div>
  );
}

// ============================================================================
// 1. Hesap Özeti
// ============================================================================

function AccountsOverview({
  counts,
  health,
  activity,
}: {
  counts: AdminDashboardResponse["counts"];
  health: HealthSummary;
  activity: IndependentTeacherActivitySummary;
}) {
  return (
    <section>
      <h2 className="text-sm font-semibold text-foreground inline-flex items-center gap-1.5 mb-3">
        <Users className="size-4 text-indigo-700" aria-hidden />
        Hesap Özeti
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <OverviewCard
          icon={Building2}
          label="Kurumlar"
          value={counts.institutions}
          tone="indigo"
          hint={
            <>
              {counts.active_institutions} aktif
              {health.unhealthy_total > 0 && (
                <>
                  {" · "}
                  <span className="text-rose-600 font-medium">
                    {health.unhealthy_total} risk
                  </span>
                </>
              )}
            </>
          }
          links={[
            { label: "Liste", href: "/admin/institutions" },
            { label: "Ticari", href: "/admin/security-monitor/revenue" },
          ]}
        />
        <OverviewCard
          icon={UserCircle2}
          label="Bağımsız Öğretmenler"
          value={counts.independent_teachers}
          tone="violet"
          hint={
            activity.total > 0 ? (
              <>
                <span className="text-emerald-700 font-medium">
                  {activity.healthy}
                </span>{" "}
                aktif (7g)
                {activity.unhealthy_total > 0 && (
                  <>
                    {" · "}
                    <span className="text-rose-600 font-medium">
                      {activity.unhealthy_total}
                    </span>{" "}
                    dikkat
                  </>
                )}
              </>
            ) : (
              "tek tüzel kişi gibi yönetilir"
            )
          }
          links={[
            { label: "Liste", href: "/admin/independent-teachers" },
            {
              label: "Ticari",
              href: "/admin/security-monitor/revenue?segment=user",
            },
          ]}
        />
        <OverviewCard
          icon={GraduationCap}
          label="Öğrenciler"
          value={counts.students}
          tone="sky"
          hint={<>{counts.parents} veli bağlı</>}
          links={[
            { label: "Öğrenciler", href: "/admin/users?role=student" },
            { label: "Veliler", href: "/admin/users?role=parent" },
          ]}
        />
        <OverviewCard
          icon={Shield}
          label="Yöneticiler"
          value={counts.institution_admins + counts.super_admins}
          tone="amber"
          hint={
            <>
              {counts.institution_admins} kurum yön. ·{" "}
              <span className="text-rose-700 font-medium">
                {counts.super_admins} süper
              </span>
            </>
          }
          links={[
            {
              label: "Kurum yön.",
              href: "/admin/users?role=institution_admin",
            },
            {
              label: "Süper",
              href: "/admin/users?role=super_admin",
            },
          ]}
        />
      </div>
    </section>
  );
}

function OverviewCard({
  icon: Icon,
  label,
  value,
  hint,
  tone,
  links,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
  hint?: React.ReactNode;
  tone: "indigo" | "violet" | "sky" | "amber";
  links: { label: string; href: string }[];
}) {
  const toneClasses = TONE_CLASSES[tone];
  return (
    <Card className={cn("overflow-hidden border-l-4", toneClasses.border)}>
      <CardContent className="p-4 flex items-start gap-3">
        <div
          className={cn(
            "size-11 rounded-lg flex items-center justify-center shrink-0",
            toneClasses.bg,
            toneClasses.text,
          )}
        >
          <Icon className="size-5" aria-hidden />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {label}
          </div>
          <div className="text-3xl font-semibold tabular-nums mt-1">
            {value}
          </div>
          {hint && (
            <div className="text-[11px] text-muted-foreground mt-1">
              {hint}
            </div>
          )}
        </div>
      </CardContent>
      <div className="border-t border-border bg-muted/30 px-3 py-1.5 flex items-center gap-3 text-xs">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="text-muted-foreground hover:text-foreground font-medium"
          >
            {l.label}
          </Link>
        ))}
      </div>
    </Card>
  );
}

const TONE_CLASSES: Record<
  "indigo" | "violet" | "sky" | "amber" | "rose" | "emerald",
  { border: string; bg: string; text: string; pill: string }
> = {
  indigo: {
    border: "border-l-indigo-500",
    bg: "bg-indigo-50",
    text: "text-indigo-700",
    pill: "bg-indigo-50 text-indigo-700 border-indigo-200",
  },
  violet: {
    border: "border-l-violet-500",
    bg: "bg-violet-50",
    text: "text-violet-700",
    pill: "bg-violet-50 text-violet-700 border-violet-200",
  },
  sky: {
    border: "border-l-sky-500",
    bg: "bg-sky-50",
    text: "text-sky-700",
    pill: "bg-sky-50 text-sky-700 border-sky-200",
  },
  amber: {
    border: "border-l-amber-500",
    bg: "bg-amber-50",
    text: "text-amber-700",
    pill: "bg-amber-50 text-amber-700 border-amber-200",
  },
  rose: {
    border: "border-l-rose-500",
    bg: "bg-rose-50",
    text: "text-rose-700",
    pill: "bg-rose-50 text-rose-700 border-rose-200",
  },
  emerald: {
    border: "border-l-emerald-500",
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    pill: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
};

// ============================================================================
// 2. Failed logins banner
// ============================================================================

function FailedLoginsBanner({ count }: { count: number }) {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 flex items-start gap-3">
      <AlertTriangle className="size-5 shrink-0 mt-0.5 text-amber-700" aria-hidden />
      <div className="flex-1 text-sm">
        <div className="font-semibold text-amber-900">
          Yüksek başarısız giriş hareketi
        </div>
        <div className="text-amber-800 mt-1">
          Son 24 saatte <strong className="tabular-nums">{count}</strong>{" "}
          başarısız giriş veya kilitleme olayı kaydedildi.{" "}
          <Link
            href="/admin/security-monitor"
            className="underline font-medium hover:text-amber-950"
          >
            Güvenlik kamarasını aç
          </Link>{" "}
          ·{" "}
          <Link
            href="/admin/audit?action=login_failed"
            className="underline font-medium hover:text-amber-950"
          >
            Audit log
          </Link>
        </div>
      </div>
    </div>
  );
}

function PendingRequestsBanner({ subscription, total }: { subscription: number; total: number }) {
  return (
    <div className="rounded-md border border-indigo-300 bg-indigo-50 px-4 py-3 flex items-start gap-3">
      <Inbox className="size-5 shrink-0 mt-0.5 text-indigo-700" aria-hidden />
      <div className="flex-1 text-sm">
        <div className="font-semibold text-indigo-900">
          {subscription > 0
            ? `${subscription} abonelik aktivasyon talebi onay bekliyor`
            : `${total} iletişim talebi bekliyor`}
        </div>
        <div className="text-indigo-800 mt-1">
          {subscription > 0
            ? "Koç(lar) “öde ve devam et” ile aktivasyon istedi. Ödemeyi alıp planı aktive edin."
            : "Fiyatlandırma/iletişim formundan gelen talepler var."}{" "}
          <Link
            href="/admin/contact-requests"
            className="underline font-medium hover:text-indigo-950"
          >
            İletişim Talepleri&apos;ni aç
          </Link>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 3. Commercial shortcuts
// ============================================================================

const COMMERCIAL_SHORTCUTS = [
  {
    href: "/admin/security-monitor/revenue",
    icon: TrendingUp,
    label: "Ticari Pano",
    desc: "Aylık gelir · plan · sağlık · risk",
    tone: "indigo" as const,
  },
  {
    href: "/admin/revenue/action-center",
    icon: Target,
    label: "Aksiyon Merkezi",
    desc: "Ödeme hatırlatması · sinyaller · hızlı eylem",
    tone: "rose" as const,
  },
  {
    href: "/admin/security-monitor/revenue/invoices",
    icon: CalendarDays,
    label: "Ödeme Takvimi",
    desc: "Faturalar · vade · gecikme",
    tone: "amber" as const,
  },
  {
    href: "/admin/revenue/campaigns",
    icon: Send,
    label: "Kampanyalar",
    desc: "Hedef grup · A/B testi · dönüşüm",
    tone: "violet" as const,
  },
  {
    href: "/admin/revenue/forecast",
    icon: TrendingUp,
    label: "Tahmin",
    desc: "30/60/90g aylık gelir · senaryo",
    tone: "emerald" as const,
  },
  {
    href: "/admin/revenue/cohort",
    icon: Heart,
    label: "Kohort & Yaşam Değeri",
    desc: "Tutunma · ayrılma · plan ömrü",
    tone: "sky" as const,
  },
  {
    href: "/admin/revenue/action-templates",
    icon: ClipboardList,
    label: "Aksiyon Şablonları",
    desc: "Hazır e-posta/SMS taslakları",
    tone: "indigo" as const,
  },
];

function CommercialShortcuts() {
  return (
    <section>
      <header className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-emerald-700 font-semibold">
            Satış · Ödemeler · CRM
          </p>
          <h2 className="text-sm font-semibold inline-flex items-center gap-1.5 mt-0.5">
            <Wallet className="size-4 text-emerald-700" aria-hidden />
            Ticari & Ödemeler
          </h2>
        </div>
        <Link
          href="/admin/security-monitor/revenue"
          className="text-xs text-emerald-700 hover:text-emerald-900 font-medium inline-flex items-center gap-0.5"
        >
          Ticari panoyu aç
          <ArrowRight className="size-3" aria-hidden />
        </Link>
      </header>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
        {COMMERCIAL_SHORTCUTS.map((s) => (
          <ShortcutTile key={s.href} {...s} />
        ))}
      </div>
    </section>
  );
}

// ============================================================================
// 4. System shortcuts
// ============================================================================

const SYSTEM_SHORTCUTS = [
  {
    href: "/admin/security-monitor",
    icon: Shield,
    label: "Güvenlik Kamarası",
    desc: "Aktif oturum · brute force · kritik akış",
    tone: "rose" as const,
  },
  {
    href: "/admin/system-health",
    icon: Stethoscope,
    label: "Sistem Sağlığı",
    desc: "Cron · bildirim · DB",
    tone: "sky" as const,
  },
  {
    href: "/admin/feature-catalog/dashboard",
    icon: TrendingUp,
    label: "Vitrin Yönetimi",
    desc: "Kartlar · deneyler · keşif",
    tone: "violet" as const,
  },
  {
    href: "/admin/audit",
    icon: FileText,
    label: "Audit Log",
    desc: "Tüm aksiyon geçmişi",
    tone: "indigo" as const,
  },
];

function SystemShortcuts() {
  return (
    <section>
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
        Altyapı · İzleme
      </p>
      <h2 className="text-sm font-semibold inline-flex items-center gap-1.5 mt-0.5 mb-3">
        <Megaphone className="size-4 text-muted-foreground" aria-hidden />
        Sistem & Güvenlik
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {SYSTEM_SHORTCUTS.map((s) => (
          <ShortcutTile key={s.href} {...s} />
        ))}
      </div>
    </section>
  );
}

function ShortcutTile({
  href,
  icon: Icon,
  label,
  desc,
  tone,
  disabled,
}: {
  href: string;
  icon: React.ElementType;
  label: string;
  desc: string;
  tone: keyof typeof TONE_CLASSES;
  disabled?: boolean;
}) {
  const tc = TONE_CLASSES[tone];
  const inner = (
    <div className="p-3 h-full">
      <div className={cn("inline-flex items-center justify-center size-7 rounded-md mb-2", tc.bg, tc.text)}>
        <Icon className="size-4" aria-hidden />
      </div>
      <div className="text-sm font-medium">{label}</div>
      <div className="text-xs text-muted-foreground mt-0.5">{desc}</div>
      {disabled && (
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground/60 mt-1.5">
          yakında
        </div>
      )}
    </div>
  );
  if (disabled) {
    return (
      <div
        className="rounded-lg border border-border bg-card hover:border-border cursor-not-allowed opacity-70"
        title="Sonraki pakette aktive olacak"
      >
        {inner}
      </div>
    );
  }
  return (
    <Link
      href={href}
      className={cn(
        "block rounded-lg border border-border bg-card hover:shadow-sm hover:border-l-4 transition",
        tc.border,
      )}
    >
      {inner}
    </Link>
  );
}

// ============================================================================
// 5. Müşteri Sağlığı
// ============================================================================

function CustomerHealth({
  health,
  topUnhealthy,
  activity,
  topTeacherRisk,
}: {
  health: HealthSummary;
  topUnhealthy: HealthAssessmentItem[];
  activity: IndependentTeacherActivitySummary;
  topTeacherRisk: IndependentTeacherRiskRow[];
}) {
  const totalInstitutions =
    health.healthy + health.watch + health.risk + health.critical;
  if (totalInstitutions === 0 && activity.total === 0) return null;

  return (
    <section>
      <p className="text-[11px] uppercase tracking-wider text-rose-700 font-semibold">
        Müşteri Takibi
      </p>
      <h2 className="text-sm font-semibold inline-flex items-center gap-1.5 mt-0.5 mb-3">
        <Heart className="size-4 text-rose-700" aria-hidden />
        Müşteri Sağlığı
      </h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {totalInstitutions > 0 && (
          <InstitutionHealthCard
            health={health}
            topUnhealthy={topUnhealthy}
            total={totalInstitutions}
          />
        )}
        {activity.total > 0 && (
          <TeacherActivityCard
            activity={activity}
            topRisk={topTeacherRisk}
          />
        )}
      </div>
    </section>
  );
}

function InstitutionHealthCard({
  health,
  topUnhealthy,
  total,
}: {
  health: HealthSummary;
  topUnhealthy: HealthAssessmentItem[];
  total: number;
}) {
  return (
    <Card className="overflow-hidden flex flex-col">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between bg-indigo-50/30">
        <div className="flex items-center gap-2">
          <Building2 className="size-4 text-indigo-700" aria-hidden />
          <h3 className="font-semibold text-sm">Kurum Sağlığı</h3>
          <span className="text-xs text-muted-foreground">({total} kurum)</span>
        </div>
        <Link
          href="/admin/institutions"
          className="text-xs text-indigo-700 hover:text-indigo-900 font-medium"
        >
          Tümünü gör →
        </Link>
      </div>
      <div className="grid grid-cols-4 divide-x divide-border border-b border-border">
        <BandStat label="Sağlıklı" value={health.healthy} tone="emerald" />
        <BandStat label="Gözlem" value={health.watch} tone="yellow" />
        <BandStat label="Riskli" value={health.risk} tone="amber" />
        <BandStat label="Kritik" value={health.critical} tone="rose" />
      </div>
      <div
        className={cn(
          "p-4 flex-1",
          topUnhealthy.length > 0 ? "bg-rose-50/20" : "bg-emerald-50/20",
        )}
      >
        {topUnhealthy.length > 0 ? (
          <>
            <p className="text-[11px] font-semibold mb-2 inline-flex items-center gap-1">
              <AlertTriangle
                className="size-3.5 text-amber-500"
                aria-hidden
              />
              En çok dikkat isteyen
            </p>
            <ul className="space-y-1.5">
              {topUnhealthy.map((h) => (
                <li key={h.institution.id} className="flex items-center gap-2 text-sm">
                  <span className="text-base shrink-0">{h.level_emoji}</span>
                  <Link
                    href={`/admin/revenue/institutions/${h.institution.id}`}
                    className="font-medium hover:text-indigo-700 flex-1 truncate"
                    title={`${h.institution.name} — Ticari 360'a git`}
                  >
                    {h.institution.name}
                  </Link>
                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                    {h.indicators.length} sebep
                  </span>
                  <ScoreBadge score={h.score} color={h.level_color} />
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-xs text-emerald-700 inline-flex items-center gap-1.5">
            <span>✓</span> Risk/kritik kurum yok — temiz tablo.
          </p>
        )}
      </div>
    </Card>
  );
}

function TeacherActivityCard({
  activity,
  topRisk,
}: {
  activity: IndependentTeacherActivitySummary;
  topRisk: IndependentTeacherRiskRow[];
}) {
  return (
    <Card className="overflow-hidden flex flex-col">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between bg-violet-50/30">
        <div className="flex items-center gap-2">
          <UserCircle2 className="size-4 text-violet-700" aria-hidden />
          <h3 className="font-semibold text-sm">
            Bağımsız Öğretmen Aktivitesi
          </h3>
          <span className="text-xs text-muted-foreground">
            ({activity.total} öğretmen)
          </span>
        </div>
        <Link
          href="/admin/security-monitor/revenue"
          className="text-xs text-indigo-700 hover:text-indigo-900 font-medium"
        >
          Ticari pano →
        </Link>
      </div>
      <div className="grid grid-cols-4 divide-x divide-border border-b border-border">
        <BandStat label="7g aktif" value={activity.healthy} tone="emerald" />
        <BandStat label="7-14g" value={activity.watch} tone="yellow" />
        <BandStat label="14-30g" value={activity.risk} tone="amber" />
        <BandStat label="30g+ / Yok" value={activity.critical} tone="rose" />
      </div>
      <div
        className={cn(
          "p-4 flex-1",
          topRisk.length > 0 ? "bg-rose-50/20" : "bg-emerald-50/20",
        )}
      >
        {topRisk.length > 0 ? (
          <>
            <p className="text-[11px] font-semibold mb-2 inline-flex items-center gap-1">
              <AlertTriangle
                className="size-3.5 text-amber-500"
                aria-hidden
              />
              En çok dikkat isteyen
            </p>
            <ul className="space-y-1.5">
              {topRisk.map((r) => (
                <li key={r.user.id} className="flex items-center gap-2 text-sm">
                  <span className="text-base shrink-0">
                    {r.band === "critical" ? "🔴" : "🟠"}
                  </span>
                  <Link
                    href={`/admin/revenue/users/${r.user.id}`}
                    className="font-medium hover:text-indigo-700 flex-1 truncate"
                    title={`${r.user.full_name} — User 360'a git`}
                  >
                    {r.user.full_name}
                  </Link>
                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                    {r.label}
                  </span>
                  <BandPill band={r.band} />
                </li>
              ))}
            </ul>
            <p className="text-[10px] text-muted-foreground italic mt-2 pt-2 border-t border-border">
              Şu anki ölçüt: son giriş tarihi (Health v2 user-variant&apos;ı
              sonra eklenecek)
            </p>
          </>
        ) : (
          <p className="text-xs text-emerald-700 inline-flex items-center gap-1.5">
            <span>✓</span> Risk altında bağımsız öğretmen yok — herkes 14 gün
            içinde girmiş.
          </p>
        )}
      </div>
    </Card>
  );
}

function BandStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "emerald" | "yellow" | "amber" | "rose";
}) {
  const colorMap = {
    emerald: { dot: "bg-emerald-500", text: "text-emerald-700" },
    yellow: { dot: "bg-yellow-500", text: "text-yellow-700" },
    amber: { dot: "bg-amber-500", text: "text-amber-700" },
    rose: { dot: "bg-rose-500", text: "text-rose-700" },
  };
  const c = colorMap[tone];
  return (
    <div className="px-3 py-2.5 bg-card">
      <div className="flex items-center gap-1.5">
        <span className={cn("size-2 rounded-full", c.dot)} />
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
          {label}
        </span>
      </div>
      <div className={cn("text-2xl font-bold tabular-nums mt-0.5", c.text)}>
        {value}
      </div>
    </div>
  );
}

function ScoreBadge({ score, color }: { score: number; color: string }) {
  // color is "rose"|"amber"|"yellow"|"emerald" from backend
  const map: Record<string, string> = {
    rose: "bg-rose-100 text-rose-800 border-rose-300",
    amber: "bg-amber-100 text-amber-800 border-amber-300",
    yellow: "bg-yellow-100 text-yellow-800 border-yellow-300",
    emerald: "bg-emerald-100 text-emerald-800 border-emerald-300",
  };
  return (
    <span
      className={cn(
        "text-[10px] px-1.5 py-0.5 rounded font-mono font-bold border tabular-nums",
        map[color] ?? "bg-slate-100 text-slate-800 border-slate-300",
      )}
    >
      {score}
    </span>
  );
}

function BandPill({ band }: { band: HealthLevel }) {
  const map: Record<HealthLevel, string> = {
    critical: "bg-rose-100 text-rose-800 border-rose-300",
    risk: "bg-amber-100 text-amber-800 border-amber-300",
    watch: "bg-yellow-100 text-yellow-800 border-yellow-300",
    healthy: "bg-emerald-100 text-emerald-800 border-emerald-300",
  };
  return (
    <span
      className={cn(
        "text-[10px] px-1.5 py-0.5 rounded font-mono font-bold border",
        map[band],
      )}
    >
      {band}
    </span>
  );
}

// ============================================================================
// 6. Son audit
// ============================================================================

function RecentAudits({ audits }: { audits: AuditLogItem[] }) {
  return (
    <section>
      <header className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-violet-700 font-semibold">
            Sistem Olayları
          </p>
          <h2 className="text-sm font-semibold inline-flex items-center gap-1.5 mt-0.5">
            <FileText className="size-4 text-violet-700" aria-hidden />
            Son Audit Olayları
          </h2>
        </div>
        <Link
          href="/admin/audit"
          className="text-xs text-violet-700 hover:text-violet-900 font-medium inline-flex items-center gap-0.5"
        >
          Tümünü gör
          <ArrowRight className="size-3" aria-hidden />
        </Link>
      </header>

      {audits.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground italic">
            Henüz audit kaydı yok.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-muted-foreground">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Zaman</th>
                  <th className="text-left px-4 py-2 font-medium">Olay</th>
                  <th className="text-left px-4 py-2 font-medium">Kim</th>
                  <th className="text-left px-4 py-2 font-medium">Hedef</th>
                  <th className="text-left px-4 py-2 font-medium">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {audits.map((a) => (
                  <AuditRow key={a.id} audit={a} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </section>
  );
}

function AuditRow({ audit }: { audit: AuditLogItem }) {
  const actionClass = actionToneClass(audit.action);
  return (
    <tr>
      <td className="px-4 py-2 text-muted-foreground tabular-nums">
        {formatAuditTime(audit.created_at)}
      </td>
      <td className="px-4 py-2">
        <span className={actionClass}>{audit.action}</span>
        {audit.via_admin != null && (
          <span
            className="ml-1.5 text-[10px] uppercase tracking-wider bg-violet-100 text-violet-700 border border-violet-200 px-1 py-0.5 rounded"
            title={`Admin #${audit.via_admin} tarafından sahte oturum`}
          >
            via #{audit.via_admin}
          </span>
        )}
      </td>
      <td className="px-4 py-2">
        {audit.actor_id ? `#${audit.actor_id}` : "—"}
        {audit.email_attempted && (
          <span className="text-muted-foreground/70 ml-1">
            · {audit.email_attempted}
          </span>
        )}
      </td>
      <td className="px-4 py-2 text-muted-foreground">
        {audit.target_type
          ? `${audit.target_type}${audit.target_id != null ? ` #${audit.target_id}` : ""}`
          : "—"}
      </td>
      <td className="px-4 py-2 text-muted-foreground font-mono text-[10px]">
        {audit.ip_address ?? "—"}
      </td>
    </tr>
  );
}

function actionToneClass(action: string): string {
  if (["login_failed", "login_locked", "permission_denied"].includes(action))
    return "text-rose-700 font-medium";
  if (["login_success", "logout"].includes(action))
    return "text-emerald-700";
  if (action.startsWith("impersonate"))
    return "text-violet-700 font-semibold";
  if (
    action.startsWith("user_") ||
    action.startsWith("institution_") ||
    action === "role_change"
  )
    return "text-indigo-700";
  return "text-foreground/80";
}

function formatAuditTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}
