"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Award,
  Backpack,
  Brain,
  Building2,
  CalendarClock,
  ChevronRight,
  Gauge,
  GraduationCap,
  HeartPulse,
  Lightbulb,
  Map as MapIcon,
  NotebookPen,
  Palette,
  RotateCcw,
  Timer,
  TrendingDown,
  TrendingUp,
  Trophy,
  UserPlus,
  UserRound,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import {
  adminKeys,
  getAdminSecurityActivity,
  getAdminSecurityActivityHeatmap,
  getAdminSecurityActivityUsers,
} from "@/lib/api/admin";
import type {
  ActivityPanelResponse,
  ActivitySegment,
  ActivityPlanActivityCell,
  ActionSuggestion,
} from "@/lib/types/admin";
import { fmtDateTime, toneBadge, toneDot, toneText } from "@/components/admin/security-ui";
import {
  ActivityHeatmapGrid,
  DauTrendChart,
  SessionBandsBar,
  StickinessSparkline,
  WowBarChart,
} from "@/components/admin/activity-charts";

interface Props {
  initial: ActivityPanelResponse;
  segment: ActivitySegment;
  initialTab?: string;
}

type TabKey = "today" | "risk" | "retention" | "depth" | "time" | "benchmark";

const TABS: { key: TabKey; label: string; icon: LucideIcon }[] = [
  { key: "today", label: "Bugün", icon: HeartPulse },
  { key: "risk", label: "Risk & Erken Uyarı", icon: TrendingDown },
  { key: "retention", label: "Tutunma & Onboarding", icon: RotateCcw },
  { key: "depth", label: "Kullanım Derinliği", icon: Palette },
  { key: "time", label: "Zaman & Isı Haritası", icon: MapIcon },
  { key: "benchmark", label: "Karşılaştırma", icon: Trophy },
];

const SEGMENTS: { key: ActivitySegment; label: string }[] = [
  { key: "all", label: "Hepsi" },
  { key: "institution", label: "Kurumlar" },
  { key: "solo", label: "Bağımsız Öğretmenler" },
];

const ROLE_ICON: Record<string, LucideIcon> = {
  teacher: GraduationCap,
  student: Backpack,
  parent: Users,
  institution_admin: UserRound,
};

const FEATURE_ICON: Record<string, LucideIcon> = {
  task_create: NotebookPen,
  week_note: NotebookPen,
  parent_invitation: UserPlus,
  pomodoro: Timer,
  review: Brain,
};

function OwnerBadge({ ownerType }: { ownerType: string }) {
  if (ownerType === "solo") {
    return <UserRound className="inline size-3.5 shrink-0 text-purple-600" aria-label="Bağımsız öğretmen" />;
  }
  return <Building2 className="inline size-3.5 shrink-0 text-blue-600" aria-label="Kurum" />;
}

type Drill =
  | { kind: "users"; window: string; role: string }
  | { kind: "heatmap"; institutionId: number }
  | null;

export function SecurityActivityClient({ initial, segment, initialTab }: Props) {
  const [tab, setTab] = React.useState<TabKey>(
    (TABS.find((t) => t.key === initialTab)?.key) ?? "today",
  );
  const [drill, setDrill] = React.useState<Drill>(null);

  const q = useQuery<ActivityPanelResponse>({
    queryKey: adminKeys.securityActivity(segment),
    queryFn: () => getAdminSecurityActivity(segment),
    initialData: initial,
    staleTime: 20_000,
  });
  const d = q.data ?? initial;
  const cs = d.critical_summary;

  return (
    <div className="space-y-5">
      <header>
        <Link href="/admin/security-monitor" className="text-sm text-muted-foreground hover:text-foreground">
          ← Güvenlik Kamarası
        </Link>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Activity className="size-6 text-slate-700" aria-hidden />
          Aktivite Kamerası
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Sistemi günlük/haftalık/aylık kimler kullanıyor; hangi kurumlar veya bağımsız
          öğretmenler sessizleşmiş; en yoğun saatler hangileri — bir bakışta gör.
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">Veri zamanı: {fmtDateTime(d.generated_at)}</p>
      </header>

      {/* Kritik Özet — her zaman görünür */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <CritCard label="Yapışkanlık" value={`%${cs.stickiness_pct}`} hint={cs.stickiness_label} tone={cs.stickiness_color} onClick={() => setTab("retention")} />
        <CritCard label="Kritik Hesap" value={cs.critical_institutions} hint="14g+ sessiz" tone={cs.critical_institutions > 0 ? "rose" : "emerald"} onClick={() => setTab("risk")} />
        <CritCard label="Sert Düşüş" value={cs.sharp_drop_count} hint="%50+ kayıp" tone={cs.sharp_drop_count > 0 ? "rose" : "slate"} onClick={() => setTab("risk")} />
        <CritCard label="Ödeyen ama Pasif" value={cs.paying_idle_count} hint="terk riski" tone={cs.paying_idle_count > 0 ? "rose" : "emerald"} onClick={() => setTab("risk")} />
        <CritCard label="Yavaş Onboarding" value={cs.onboarding_stuck_count} hint="yeni %50 altı" tone={cs.onboarding_stuck_count > 0 ? "amber" : "emerald"} onClick={() => setTab("retention")} />
        <CritCard label="Champion" value={cs.champion_count} hint="referans adayı" tone="emerald" onClick={() => setTab("benchmark")} />
      </section>

      {/* Segment toggle (URL state) */}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Görüntüle:</span>
        {SEGMENTS.map((s) => (
          <Link
            key={s.key}
            href={`/admin/security-monitor/activity?segment=${s.key}&tab=${tab}`}
            className={cn(
              "rounded-full border px-3 py-1.5 font-medium transition",
              segment === s.key
                ? "border-indigo-600 bg-indigo-600 text-white"
                : "border-border bg-card text-foreground hover:border-indigo-300",
            )}
          >
            {s.label}
          </Link>
        ))}
      </div>

      {/* Sekme bar */}
      <div className="flex flex-wrap items-center gap-1 border-b border-border">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cn(
                "-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition",
                active
                  ? "border-indigo-500 text-indigo-700"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-4" aria-hidden />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Drill host */}
      {drill ? (
        <div>
          {drill.kind === "users" ? (
            <ActiveUsersDrill window={drill.window} role={drill.role} onClose={() => setDrill(null)} />
          ) : (
            <HeatmapDrill institutionId={drill.institutionId} onClose={() => setDrill(null)} />
          )}
        </div>
      ) : null}

      {/* Sekme içerikleri */}
      {tab === "today" && <TodayTab d={d} segment={segment} onDrill={setDrill} />}
      {tab === "risk" && <RiskTab d={d} onDrill={setDrill} />}
      {tab === "retention" && <RetentionTab d={d} />}
      {tab === "depth" && <DepthTab d={d} />}
      {tab === "time" && <TimeTab d={d} segment={segment} onDrill={setDrill} />}
      {tab === "benchmark" && <BenchmarkTab d={d} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Kritik özet kartı
// ---------------------------------------------------------------------------

function CritCard({
  label,
  value,
  hint,
  tone,
  onClick,
}: {
  label: string;
  value: React.ReactNode;
  hint: string;
  tone: string;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} className="text-left">
      <Card className="p-3 transition hover:border-foreground/30">
        <div className={cn("text-[10px] font-semibold uppercase", toneText(tone))}>{label}</div>
        <div className="mt-0.5 text-2xl font-bold tabular-nums">{value}</div>
        <div className="text-[10px] text-muted-foreground">{hint}</div>
      </Card>
    </button>
  );
}

function SuggestionPopover({ suggestions }: { suggestions: ActionSuggestion[] }) {
  if (!suggestions.length) return null;
  return (
    <details className="relative inline-block">
      <summary className="inline-flex cursor-pointer list-none items-center gap-0.5 text-[11px] text-amber-700 hover:text-amber-900">
        <Lightbulb className="size-3.5" aria-hidden /> Öneri
      </summary>
      <div className="absolute right-0 top-6 z-20 w-64 rounded-md border border-amber-300 bg-popover p-2 shadow-lg">
        <div className="mb-1 text-[10px] font-semibold uppercase text-amber-700">Önerilen Aksiyonlar</div>
        <ul className="space-y-1 text-[11px]">
          {suggestions.map((s, i) => (
            <li key={i} className="text-foreground">
              <b>{s.label}</b>
              <div className="text-[10px] text-muted-foreground">{s.hint}</div>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}

function OwnerLink({ ownerType, name, url }: { ownerType: string; name: string | null; url: string }) {
  return (
    <Link href={url} className="inline-flex items-center gap-1 font-medium text-indigo-700 hover:underline">
      <OwnerBadge ownerType={ownerType} />
      <span className="truncate">{name}</span>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Drill panelleri (on-demand)
// ---------------------------------------------------------------------------

function ActiveUsersDrill({ window, role, onClose }: { window: string; role: string; onClose: () => void }) {
  const q = useQuery({
    queryKey: adminKeys.securityActivityUsers(window, role, null),
    queryFn: () => getAdminSecurityActivityUsers(window, role, null),
  });
  return (
    <Card className="overflow-hidden border-l-4 border-l-indigo-500">
      <div className="flex items-center justify-between gap-3 border-b border-border bg-indigo-50/40 px-4 py-2.5">
        <div>
          <h3 className="inline-flex items-center gap-1.5 text-sm font-semibold">
            <Users className="size-4 text-indigo-600" aria-hidden />
            Aktif Kullanıcı Listesi
            {q.data ? <span className="font-normal text-muted-foreground">— {q.data.role_label} · {q.data.window_label} ({q.data.rows.length})</span> : null}
          </h3>
        </div>
        <button type="button" onClick={onClose} className="rounded p-1 text-muted-foreground hover:bg-muted">
          <X className="size-4" aria-hidden />
        </button>
      </div>
      {q.isLoading ? (
        <p className="p-6 text-center text-sm text-muted-foreground">Yükleniyor…</p>
      ) : !q.data || q.data.rows.length === 0 ? (
        <p className="p-6 text-center text-sm text-muted-foreground">Bu pencerede aktif kullanıcı yok.</p>
      ) : (
        <ul className="max-h-96 divide-y divide-border overflow-auto">
          {q.data.rows.map((r) => (
            <li key={r.user_id} className="flex items-center justify-between gap-3 px-4 py-2 text-sm hover:bg-muted/40">
              <div className="min-w-0">
                <div className="truncate font-medium">{r.name}</div>
                <div className="truncate text-[11px] text-muted-foreground">
                  {r.email ?? "—"}
                  {r.institution_name ? <> · {r.institution_name}</> : null}
                  {r.role ? <> · {r.role}</> : null}
                </div>
              </div>
              <span className="shrink-0 text-[11px] text-muted-foreground">{fmtDateTime(r.last_login_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function HeatmapDrill({ institutionId, onClose }: { institutionId: number; onClose: () => void }) {
  const q = useQuery({
    queryKey: adminKeys.securityActivityHeatmap(institutionId),
    queryFn: () => getAdminSecurityActivityHeatmap(institutionId),
  });
  return (
    <Card className="overflow-hidden border-l-4 border-l-indigo-500">
      <div className="flex items-center justify-between gap-3 border-b border-border bg-indigo-50/40 px-4 py-2.5">
        <div className="min-w-0">
          <h3 className="inline-flex items-center gap-1.5 text-sm font-semibold">
            <MapIcon className="size-4 text-indigo-600" aria-hidden />
            <Building2 className="size-3.5 text-blue-600" aria-hidden />
            <span className="truncate">{q.data?.institution_name ?? "Kurum"} — Aktivite Haritası</span>
          </h3>
          {q.data ? (
            <p className="text-[11px] text-muted-foreground">
              Son {q.data.days_window} gün · {q.data.total} giriş · plan {q.data.plan ?? "—"}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {q.data?.institution_id ? (
            <Link href={`/admin/revenue/institutions/${q.data.institution_id}`} className="rounded border border-indigo-300 px-2 py-1 text-xs text-indigo-700 hover:bg-indigo-50">
              Kurum 360 →
            </Link>
          ) : null}
          <button type="button" onClick={onClose} className="rounded p-1 text-muted-foreground hover:bg-muted">
            <X className="size-4" aria-hidden />
          </button>
        </div>
      </div>
      {q.isLoading ? (
        <p className="p-6 text-center text-sm text-muted-foreground">Yükleniyor…</p>
      ) : !q.data || q.data.total === 0 ? (
        <p className="p-6 text-center text-sm text-muted-foreground">Bu kurumda son 7 günde giriş kaydı yok.</p>
      ) : (
        <div className="space-y-2 p-3">
          {q.data.patterns.length > 0 ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-muted-foreground">Otomatik örüntü:</span>
              {q.data.patterns.map((p, i) => (
                <span key={i} className={cn("rounded-full border px-2 py-0.5 text-[11px]", toneBadge(p.tone))} title={p.detail ?? ""}>
                  {p.label}
                </span>
              ))}
            </div>
          ) : null}
          <ActivityHeatmapGrid matrix={q.data.matrix} dayLabels={q.data.day_labels} maxValue={q.data.max_value} />
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sekme: BUGÜN
// ---------------------------------------------------------------------------

function TodayTab({
  d,
  segment,
  onDrill,
}: {
  d: ActivityPanelResponse;
  segment: ActivitySegment;
  onDrill: (drill: Drill) => void;
}) {
  const stickiness = d.totals.mau > 0 ? Math.round((d.totals.dau * 1000) / d.totals.mau) / 10 : 0;
  return (
    <div className="space-y-5">
      {/* DAU/WAU/MAU + yapışkanlık */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <ActiveCard label="Günlük Aktif" value={d.totals.dau} hint="son 24 saat · tıkla → liste" tone="indigo" onClick={() => onDrill({ kind: "users", window: "dau", role: "" })} />
        <ActiveCard label="Haftalık Aktif" value={d.totals.wau} hint="son 7 gün · tıkla → liste" tone="purple" onClick={() => onDrill({ kind: "users", window: "wau", role: "" })} />
        <ActiveCard label="Aylık Aktif" value={d.totals.mau} hint="son 30 gün · tıkla → liste" tone="fuchsia" onClick={() => onDrill({ kind: "users", window: "mau", role: "" })} />
        <Card className="p-4">
          <div className="text-[11px] font-semibold uppercase text-muted-foreground">Yapışkanlık Oranı</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">%{stickiness}</div>
          <div className="text-[11px] text-muted-foreground">Günlük ÷ Aylık · %30+ sağlıklı</div>
        </Card>
      </section>

      {/* Rol kırılımı */}
      {d.role_breakdown.length > 0 ? (
        <Card className="p-4">
          <h2 className="mb-3 inline-flex items-center gap-2 text-sm font-semibold">
            <Users className="size-4 text-indigo-600" aria-hidden /> Bugün aktif — rol kırılımı
          </h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {d.role_breakdown.map((r) => {
              const Icon = ROLE_ICON[r.role] ?? Users;
              return (
                <button key={r.role} type="button" onClick={() => onDrill({ kind: "users", window: "dau", role: r.role })} className="text-left">
                  <div className={cn("rounded-lg border p-3 transition hover:border-foreground/30", toneBadge(r.color))}>
                    <div className="inline-flex items-center gap-1 text-[11px] font-medium uppercase">
                      <Icon className="size-3.5" aria-hidden /> {r.label}
                    </div>
                    <div className="mt-1 text-2xl font-semibold tabular-nums">{r.today}</div>
                    <div className="text-[11px]">
                      Dün: {r.yesterday}
                      {r.delta > 0 ? <span className="ml-1 text-emerald-700">↑ %{r.delta_pct}</span> : r.delta < 0 ? <span className="ml-1 text-rose-700">↓ %{-r.delta_pct}</span> : <span className="ml-1 opacity-70">—</span>}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </Card>
      ) : null}

      {/* Solo özel panel */}
      {d.solo_special && (segment === "solo" || segment === "all") ? (
        <Card className="border-l-4 border-l-purple-500 p-4">
          <h2 className="mb-3 inline-flex items-center gap-2 text-sm font-semibold text-purple-800">
            <UserRound className="size-4" aria-hidden /> Bağımsız Öğretmene Özel Metrikler
          </h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <SoloMetricCard title="Veli İletişim Oranı" value={`%${d.solo_special.parent_outreach.ratio_pct ?? 0}`} sub={`${d.solo_special.parent_outreach.sent_count ?? 0} / ${d.solo_special.parent_outreach.total ?? 0} öğretmen davet göndermiş`} label={d.solo_special.parent_outreach.label} color={d.solo_special.parent_outreach.color} />
            <SoloMetricCard title="Öğrenci Başına Haftalık Görev" value={String(d.solo_special.discipline.avg_per_student_per_week ?? 0)} sub={`${d.solo_special.discipline.total_tasks ?? 0} görev / ${d.solo_special.discipline.total_students ?? 0} öğrenci`} label={d.solo_special.discipline.label} color={d.solo_special.discipline.color} />
            <SoloMetricCard title="Haftalık Tutarlılık" value={String(d.solo_special.consistency.avg_missing_weeks ?? 0)} sub={`Ort. kayıp hafta · ${d.solo_special.consistency.consistent_count ?? 0}/${d.solo_special.consistency.total ?? 0} tam tutarlı`} label={d.solo_special.consistency.label} color={d.solo_special.consistency.color} />
          </div>
        </Card>
      ) : null}

      {/* WoW */}
      <Card className="p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
            <TrendingUp className="size-4 text-indigo-600" aria-hidden /> Bu hafta vs Geçen hafta — Günlük Aktif
          </h2>
          <span className="text-xs text-muted-foreground">
            {d.wow.this_total} / {d.wow.last_total}
            {d.wow.delta > 0 ? <span className="ml-1 text-emerald-700">↑ +{d.wow.delta} (%{d.wow.delta_pct})</span> : d.wow.delta < 0 ? <span className="ml-1 text-rose-700">↓ {d.wow.delta} (%{d.wow.delta_pct})</span> : null}
          </span>
        </div>
        {d.wow.max_value > 0 ? <WowBarChart wow={d.wow} /> : <p className="py-8 text-center text-sm text-muted-foreground">Son 14 günde giriş kaydı yok.</p>}
      </Card>
    </div>
  );
}

function ActiveCard({ label, value, hint, tone, onClick }: { label: string; value: number; hint: string; tone: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="text-left">
      <Card className={cn("p-4 transition hover:border-foreground/30", toneBadge(tone))}>
        <div className="text-[11px] font-semibold uppercase">{label}</div>
        <div className="mt-1 text-3xl font-semibold tabular-nums underline-offset-2 hover:underline">{value}</div>
        <div className="text-[11px] opacity-80">{hint}</div>
      </Card>
    </button>
  );
}

function SoloMetricCard({ title, value, sub, label, color }: { title: string; value: string; sub: string; label: string; color: string }) {
  return (
    <div className={cn("rounded-lg border bg-card p-4")}>
      <div className={cn("text-[11px] font-semibold uppercase", toneText(color))}>{title}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
      <div className="text-[11px] text-muted-foreground">{sub}</div>
      <div className={cn("mt-1 text-[11px]", toneText(color))}>{label}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sekme: RISK
// ---------------------------------------------------------------------------

function RiskTab({ d, onDrill }: { d: ActivityPanelResponse; onDrill: (drill: Drill) => void }) {
  const hb = d.heartbeat_summary;
  const quads: { key: keyof typeof QUAD_META; rows: ActivityPlanActivityCell[] }[] = [
    { key: "paying_idle", rows: d.plan_activity.paying_idle },
    { key: "paying_active", rows: d.plan_activity.paying_active },
    { key: "free_active", rows: d.plan_activity.free_active },
    { key: "free_idle", rows: d.plan_activity.free_idle },
  ];
  return (
    <div className="space-y-5">
      {/* Kalp atışı */}
      <Card className="overflow-hidden">
        <div className="border-b border-border bg-rose-50/40 px-4 py-2.5">
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
            <HeartPulse className="size-4 text-rose-600" aria-hidden /> Hesap Kalp Atışı — Son Giriş
          </h2>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
            <span>🟢 {hb.healthy} sağlıklı</span><span>🟡 {hb.watch} izle</span><span>🟠 {hb.warning} dikkat</span>
            <span>🔴 {hb.critical} risk</span><span>⚫ {hb.dead} kayıp</span><span>◯ {hb.no_login} giriş yok</span>
          </div>
        </div>
        {d.heartbeats.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Veri yok.</p>
        ) : (
          <ul className="max-h-96 divide-y divide-border overflow-auto">
            {d.heartbeats.map((r, i) => (
              <li key={`${r.owner_type}-${r.owner_id}-${i}`} className="flex items-center justify-between gap-3 px-4 py-2 hover:bg-muted/40">
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <span className={cn("size-2 shrink-0 rounded-full", toneDot(r.band_color))} />
                  <OwnerLink ownerType={r.owner_type} name={r.institution_name} url={r.detail_url} />
                  <span className="font-mono text-[10px] text-muted-foreground">{r.plan}</span>
                  {r.owner_type === "solo" && r.student_count != null ? <span className="text-[10px] text-muted-foreground">· {r.student_count} öğr.</span> : null}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={cn("rounded px-1.5 py-0.5 text-[11px] font-semibold", toneBadge(r.band_color))}>{r.label}</span>
                  <SuggestionPopover suggestions={d.action_suggestions[r.band] ?? []} />
                  {r.owner_type !== "solo" && r.institution_id ? (
                    <button type="button" onClick={() => onDrill({ kind: "heatmap", institutionId: r.institution_id! })} className="inline-flex items-center gap-0.5 text-[11px] text-muted-foreground underline hover:text-indigo-700">
                      <MapIcon className="size-3" aria-hidden /> Harita
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Plan × Aktivite quadrant */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {quads.map(({ key, rows }) => {
          const meta = QUAD_META[key];
          return (
            <Card key={key} className={cn("overflow-hidden border-2", meta.border)}>
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <div className={cn("text-[10px] font-semibold uppercase", meta.text)}>{meta.tag}</div>
                  <div className="text-sm font-semibold">{meta.title}</div>
                  <div className="text-[11px] text-muted-foreground">{meta.hint}</div>
                </div>
                <div className={cn("text-3xl font-bold", meta.text)}>{d.plan_activity.totals[key] ?? 0}</div>
              </div>
              {rows.length > 0 ? (
                <ul className="max-h-56 divide-y divide-border overflow-auto border-t border-border">
                  {rows.map((r, i) => (
                    <li key={`${r.owner_id}-${i}`} className="flex items-center justify-between gap-2 px-4 py-1.5 text-xs">
                      <OwnerLink ownerType={r.owner_type} name={r.institution_name} url={r.detail_url} />
                      <span className="whitespace-nowrap text-muted-foreground"><span className="font-mono text-[10px]">{r.plan}</span> · {r.label}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </Card>
          );
        })}
      </div>

      {/* Sönüş hızı */}
      {d.decay_rates.length > 0 ? (
        <Card className="overflow-hidden">
          <div className="border-b border-border bg-amber-50/40 px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <TrendingDown className="size-4 text-amber-600" aria-hidden /> Hesap Sönüş Hızı (son 7g vs önceki 7g)
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-1.5 text-left">Hesap</th>
                  <th className="px-3 py-1.5 text-right">Önceki 7g</th>
                  <th className="px-3 py-1.5 text-right">Son 7g</th>
                  <th className="px-3 py-1.5 text-right">Değişim</th>
                  <th className="px-3 py-1.5 text-left">Durum</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.decay_rates.slice(0, 30).map((r, i) => (
                  <tr key={`${r.owner_id}-${i}`} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5"><OwnerLink ownerType={r.owner_type} name={r.institution_name} url={r.detail_url} /><div className="font-mono text-[10px] text-muted-foreground">{r.plan}</div></td>
                    <td className="px-3 py-1.5 text-right font-mono text-muted-foreground">{r.previous_7d}</td>
                    <td className="px-3 py-1.5 text-right font-mono font-semibold">{r.recent_7d}</td>
                    <td className={cn("px-3 py-1.5 text-right font-mono font-semibold", r.change_pct < 0 ? "text-rose-700" : r.change_pct > 0 ? "text-emerald-700" : "text-muted-foreground")}>{r.change_pct > 0 ? "+" : ""}{r.change_pct}%</td>
                    <td className="px-3 py-1.5"><span className={cn("rounded px-2 py-0.5 text-[11px] font-semibold", toneBadge(r.color))}>{r.label}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {/* Sessizleşen hesaplar */}
      <Card className="overflow-hidden">
        <div className="border-b border-border bg-amber-50/40 px-4 py-2.5">
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
            <CalendarClock className="size-4 text-amber-600" aria-hidden /> Sessizleşen Hesaplar — Son 7 Gün
          </h2>
        </div>
        {d.silent_tenants_7d.length === 0 ? (
          <p className="p-6 text-center text-sm text-emerald-700">Tüm aktif hesaplar son 7 günde sisteme girdi.</p>
        ) : (
          <ul className="max-h-96 divide-y divide-border overflow-auto">
            {d.silent_tenants_7d.map((t, i) => (
              <li key={`${t.owner_id}-${i}`} className="flex items-center justify-between px-4 py-2">
                <OwnerLink ownerType={t.owner_type} name={t.tenant_name} url={t.detail_url ?? `/admin/revenue/institutions/${t.tenant_id}`} />
                <span className="text-xs text-rose-600">7 gündür sessiz</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

const QUAD_META = {
  paying_idle: { tag: "KRİTİK", title: "Ödeyen ama Pasif", hint: "Para ödüyor ama kullanmıyor — acil temas", border: "border-rose-300", text: "text-rose-700" },
  paying_active: { tag: "CHAMPION", title: "Ödeyen ve Aktif", hint: "En değerli müşteriler — referans adayı", border: "border-emerald-300", text: "text-emerald-700" },
  free_active: { tag: "UPGRADE ADAYI", title: "Free ve Aktif", hint: "Aktif kullanıyor — ücretli plan şansı yüksek", border: "border-amber-300", text: "text-amber-700" },
  free_idle: { tag: "İHMAL", title: "Free ve Pasif", hint: "Ne ödüyor ne kullanıyor — düşük öncelik", border: "border-slate-200", text: "text-slate-600" },
} as const;

// ---------------------------------------------------------------------------
// Sekme: TUTUNMA
// ---------------------------------------------------------------------------

function RetentionTab({ d }: { d: ActivityPanelResponse }) {
  const s = d.stickiness;
  return (
    <div className="space-y-5">
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="p-4">
          <div className={cn("text-[11px] font-semibold uppercase", toneText(s.color))}>Yapışkanlık</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">%{s.ratio_pct}</div>
          <div className="text-[11px] text-muted-foreground">{s.dau} / {s.mau} (Günlük/Aylık)</div>
          <div className={cn("text-[11px]", toneText(s.color))}>{s.label}</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] font-semibold uppercase text-muted-foreground">Son 30 Gün Trend</div>
          <div className="mt-2"><StickinessSparkline series={d.stickiness_trend_30d} /></div>
          <div className="mt-1 text-[10px] text-muted-foreground">Günlük/Aylık oranı %</div>
        </Card>
        <RetentionCard title="1. Hafta Tutunma" m={d.week1} good="iyi onboarding" />
        <RetentionCard title="30 Gün Hayatta Kalma" m={d.day30} good="sağlıklı" />
      </section>

      {/* Geri dönenler */}
      <Card className="overflow-hidden">
        <div className="border-b border-border bg-emerald-50/40 px-4 py-2.5">
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
            <RotateCcw className="size-4 text-emerald-600" aria-hidden /> Geri Dönen Kullanıcılar ({d.resurrected.length})
          </h2>
        </div>
        {d.resurrected.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">14g+ sessizlik sonrası geri dönen kullanıcı yok.</p>
        ) : (
          <ul className="max-h-64 divide-y divide-border overflow-auto">
            {d.resurrected.slice(0, 20).map((u) => (
              <li key={u.user_id} className="flex items-center justify-between px-4 py-1.5 text-xs">
                <span><span className="font-medium">{u.name}</span> <span className="text-muted-foreground">· {u.role}</span></span>
                <span className="text-[11px] text-emerald-700">{u.gap_days}g sessizlik → döndü</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Onboarding */}
      {d.onboarding.length > 0 ? <OnboardingTable d={d} /> : null}
    </div>
  );
}

function RetentionCard({ title, m, good }: { title: string; m: ActivityPanelResponse["week1"]; good: string }) {
  const tone = m.ratio_pct == null ? "slate" : m.ratio_pct >= 50 ? "emerald" : m.ratio_pct >= 25 ? "amber" : "rose";
  return (
    <Card className="p-4">
      <div className="text-[11px] font-semibold uppercase text-muted-foreground">{title}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">{m.ratio_pct != null ? `%${m.ratio_pct}` : "—"}</div>
      <div className="text-[11px] text-muted-foreground">{m.total > 0 ? `${m.active} / ${m.total} aktif` : "yeni kayıt yok"}</div>
      <div className={cn("text-[11px]", toneText(tone))}>{m.ratio_pct == null ? "veri yetersiz" : m.ratio_pct >= 50 ? good : m.ratio_pct >= 25 ? "orta" : "zayıf"}</div>
    </Card>
  );
}

function OnboardingTable({ d }: { d: ActivityPanelResponse }) {
  const headers = d.onboarding[0].milestones;
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border bg-amber-50/40 px-4 py-2.5">
        <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
          <UserPlus className="size-4 text-amber-600" aria-hidden /> Yeni Hesap Onboarding Durumu
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-1.5 text-left">Hesap</th>
              <th className="px-3 py-1.5 text-center">Yaş</th>
              {headers.map((m) => (
                <th key={m.key} className="px-2 py-1.5 text-center" title={m.label}>{m.label.replace(/^[^\s]+\s/, "")}</th>
              ))}
              <th className="px-3 py-1.5 text-right">İlerleme</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {d.onboarding.map((o, i) => (
              <tr key={`${o.owner_id}-${i}`} className="hover:bg-muted/40">
                <td className="px-3 py-1.5"><OwnerLink ownerType={o.owner_type} name={o.institution_name} url={o.detail_url} /></td>
                <td className="px-3 py-1.5 text-center text-[11px] text-muted-foreground">{o.age_days}g</td>
                {o.milestones.map((m) => (
                  <td key={m.key} className="px-2 py-1.5 text-center">
                    {m.done == null ? <span className="text-slate-300">—</span> : m.done ? <span className="text-emerald-600">✓</span> : <span className="text-slate-300">·</span>}
                  </td>
                ))}
                <td className="px-3 py-1.5 text-right">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-2 w-14 overflow-hidden rounded bg-slate-100">
                      <span className={cn("block h-full", o.completion_pct >= 80 ? "bg-emerald-500" : o.completion_pct >= 40 ? "bg-amber-500" : "bg-rose-500")} style={{ width: `${o.completion_pct}%` }} />
                    </span>
                    <span className="font-mono text-[11px] text-muted-foreground">{o.done_count}/{o.total_count}</span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sekme: DERİNLİK
// ---------------------------------------------------------------------------

function DepthTab({ d }: { d: ActivityPanelResponse }) {
  const sd = d.session_duration;
  const maxPop = Math.max(...d.feature_popularity.map((f) => f.total_events), 1);
  return (
    <div className="space-y-5">
      {/* Oturum süresi */}
      <Card className="p-4">
        <h2 className="mb-3 inline-flex items-center gap-2 text-sm font-semibold">
          <Timer className="size-4 text-cyan-600" aria-hidden /> Oturum Süresi Dağılımı (son {sd.days_window}g)
        </h2>
        {sd.count === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">Bu pencerede sonlanmış oturum yok.</p>
        ) : (
          <>
            <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              <MiniStat label="Ortalama" value={`${sd.avg_min} dk`} sub={`${sd.count} oturum`} />
              <MiniStat label="Medyan" value={`${sd.median_min} dk`} sub="tipik kullanıcı" />
              <MiniStat label='< 1 dk ("açtı kapattı")' value={`%${sd.under_1_pct}`} sub={`${sd.under_1min}/${sd.count}`} tone={sd.under_1_pct >= 40 ? "rose" : "amber"} />
              <MiniStat label='> 30 dk ("çalışıyor")' value={`%${sd.over_30_pct}`} sub={`${sd.over_30min}/${sd.count}`} tone="emerald" />
            </div>
            <SessionBandsBar bands={sd.bands} />
          </>
        )}
      </Card>

      {/* Öğretmen/öğrenci oranı */}
      {d.teacher_student_ratios.length > 0 ? (
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold"><GraduationCap className="size-4 text-cyan-600" aria-hidden /> Öğretmen × Öğrenci Oranı</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr><th className="px-3 py-1.5 text-left">Hesap</th><th className="px-3 py-1.5 text-right">Akt. Öğretmen</th><th className="px-3 py-1.5 text-right">Akt. Öğrenci</th><th className="px-3 py-1.5 text-right">Oran</th><th className="px-3 py-1.5 text-left">Durum</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.teacher_student_ratios.slice(0, 30).map((r, i) => (
                  <tr key={`${r.owner_id}-${i}`} className="hover:bg-muted/40">
                    <td className="px-3 py-1.5"><OwnerLink ownerType={r.owner_type} name={r.institution_name} url={r.detail_url} /></td>
                    <td className="px-3 py-1.5 text-right font-mono text-muted-foreground">{r.owner_type === "solo" ? "1" : r.active_teachers}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-muted-foreground">{r.active_students}</td>
                    <td className="px-3 py-1.5 text-right font-mono font-semibold">{r.ratio != null ? r.ratio : "—"}</td>
                    <td className="px-3 py-1.5"><span className={cn("rounded px-2 py-0.5 text-[11px] font-semibold", toneBadge(r.color))}>{r.label}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {/* Power users */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <PowerUserList title="En Aktif" subtitle="referans/case study adayı" rows={d.power_users.top} tone="emerald" />
        <PowerUserList title="En Sessiz Aktifler" subtitle="intervention/eğitim listesi" rows={d.power_users.bottom} tone="amber" />
      </div>

      {/* Feature popülerlik */}
      {d.feature_popularity.length > 0 ? (
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold"><Palette className="size-4 text-purple-600" aria-hidden /> Özellik Popülerliği (son 30g)</h2>
          </div>
          <div className="divide-y divide-border">
            {d.feature_popularity.map((f) => {
              const Icon = FEATURE_ICON[f.key] ?? Palette;
              const pct = maxPop > 0 ? Math.round((f.total_events * 100) / maxPop) : 0;
              return (
                <div key={f.key} className="flex items-center gap-3 px-4 py-2 text-sm">
                  <Icon className="size-4 shrink-0 text-purple-600" aria-hidden />
                  <span className="w-40 shrink-0 font-medium">{f.label}</span>
                  <div className="h-3 flex-1 overflow-hidden rounded bg-slate-100">
                    <div className={cn("h-full rounded", f.total_events === 0 ? "bg-rose-300" : "bg-purple-500")} style={{ width: `${pct}%` }} />
                  </div>
                  <span className={cn("w-12 text-right font-mono", f.total_events === 0 ? "text-rose-700" : "text-foreground")}>{f.total_events}</span>
                  <span className="hidden w-28 text-right text-[11px] text-muted-foreground sm:inline">{f.distinct_institutions} kurum · {f.distinct_users} kişi</span>
                </div>
              );
            })}
          </div>
        </Card>
      ) : null}

      {/* Feature matrix */}
      {d.feature_matrix.rows.length > 0 ? (
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold"><Palette className="size-4 text-purple-600" aria-hidden /> Özellik Kullanım Matrisi</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead className="bg-muted/40 text-[10px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="sticky left-0 z-10 bg-muted/40 px-3 py-2 text-left">Hesap</th>
                  {d.feature_matrix.features.map((f) => {
                    const Icon = FEATURE_ICON[f.key] ?? Palette;
                    return <th key={f.key} className="px-2 py-2 text-center" title={f.label}><Icon className="mx-auto size-4" aria-hidden /></th>;
                  })}
                  <th className="px-3 py-2 text-right">Adop.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.feature_matrix.rows.map((r, i) => (
                  <tr key={`${r.owner_id}-${i}`} className="hover:bg-muted/40">
                    <td className="sticky left-0 z-10 bg-card px-3 py-1.5"><OwnerLink ownerType={r.owner_type} name={r.institution_name} url={r.detail_url} /></td>
                    {r.cells.map((c) => (
                      <td key={c.key} className="px-2 py-1.5 text-center">
                        {c.used ? <span className="inline-block size-5 rounded bg-emerald-500 text-center leading-5 text-white">✓</span> : <span className="inline-block size-5 rounded bg-slate-100 text-center leading-5 text-slate-300">·</span>}
                      </td>
                    ))}
                    <td className={cn("px-3 py-1.5 text-right font-mono font-semibold", r.adoption_pct >= 60 ? "text-emerald-700" : r.adoption_pct >= 40 ? "text-amber-700" : "text-rose-700")}>%{r.adoption_pct}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function MiniStat({ label, value, sub, tone }: { label: string; value: string; sub: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className={cn("text-[11px] font-semibold uppercase", tone ? toneText(tone) : "text-muted-foreground")}>{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      <div className="text-[11px] text-muted-foreground">{sub}</div>
    </div>
  );
}

function PowerUserList({ title, subtitle, rows, tone }: { title: string; subtitle: string; rows: ActivityPanelResponse["power_users"]["top"]; tone: string }) {
  return (
    <Card className="overflow-hidden">
      <div className={cn("border-b border-border px-4 py-2.5")}>
        <h3 className={cn("text-sm font-semibold", toneText(tone))}>{title} ({rows.length})</h3>
        <div className="text-[11px] text-muted-foreground">{subtitle}</div>
      </div>
      {rows.length === 0 ? (
        <p className="p-6 text-center text-sm text-muted-foreground">—</p>
      ) : (
        <ul className="divide-y divide-border">
          {rows.map((u) => (
            <li key={u.user_id} className="flex items-center justify-between gap-2 px-4 py-2 text-xs">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{u.name}</div>
                <div className="truncate text-[11px] text-muted-foreground">{u.role}{u.institution_name ? <> · {u.institution_name}</> : null}</div>
              </div>
              <div className="shrink-0 text-right">
                <div className={cn("text-base font-bold", toneText(tone))}>{u.active_days}g</div>
                <div className="text-[10px] text-muted-foreground">%{u.activity_pct} aktiflik</div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sekme: ZAMAN
// ---------------------------------------------------------------------------

function TimeTab({ d, segment, onDrill }: { d: ActivityPanelResponse; segment: ActivitySegment; onDrill: (drill: Drill) => void }) {
  return (
    <div className="space-y-5">
      <Card className="p-4">
        <h2 className="mb-1 inline-flex items-center gap-2 text-sm font-semibold"><MapIcon className="size-4 text-slate-600" aria-hidden /> Saat × Gün Isı Haritası — Son 7 Gün</h2>
        <p className="mb-3 text-[11px] text-muted-foreground">Saatler UTC; Türkiye için +3 ekle. Toplam {d.heatmap.total} giriş.</p>
        {d.heatmap.total === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">Bu pencerede giriş yok.</p> : <ActivityHeatmapGrid matrix={d.heatmap.matrix} dayLabels={d.heatmap.day_labels} maxValue={d.heatmap.max_value} />}
      </Card>

      <Card className="p-4">
        <h2 className="mb-3 inline-flex items-center gap-2 text-sm font-semibold"><Gauge className="size-4 text-cyan-600" aria-hidden /> Günlük Aktif Kullanıcı Trendi — Son 14 Gün</h2>
        <DauTrendChart series={d.dau_trend_14d} />
      </Card>

      {segment === "solo" ? (
        <Card className="border-l-4 border-l-purple-500 bg-purple-50/40 p-3 text-sm text-purple-900">
          Isı haritası ve günlük trend sistem genelidir (kurum + bağımsız birleşik). Bireysel görünüm için Risk veya Karşılaştırma sekmelerine bak.
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="border-b border-border bg-emerald-50/40 px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold"><Trophy className="size-4 text-emerald-600" aria-hidden /> En Aktif Kurumlar</h2>
          </div>
          {d.per_tenant.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">Veri yok.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr><th className="px-3 py-1.5 text-left">Kurum</th><th className="px-3 py-1.5 text-right">Bugün</th><th className="px-3 py-1.5 text-right">Bu hafta</th><th className="px-3 py-1.5 text-right">Bu ay</th><th className="px-3 py-1.5 text-center">Harita</th></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.per_tenant.map((t) => (
                    <tr key={t.tenant_id} className="hover:bg-muted/40">
                      <td className="px-3 py-1.5"><Link href={`/admin/revenue/institutions/${t.tenant_id}`} className="font-medium text-indigo-700 hover:underline">{t.tenant_name}</Link><div className="text-[10px] text-muted-foreground">{t.plan}</div></td>
                      <td className={cn("px-3 py-1.5 text-right font-semibold", t.dau === 0 ? "text-rose-700" : "")}>{t.dau}</td>
                      <td className="px-3 py-1.5 text-right text-muted-foreground">{t.wau}</td>
                      <td className="px-3 py-1.5 text-right text-muted-foreground">{t.mau}</td>
                      <td className="px-3 py-1.5 text-center">
                        <button type="button" onClick={() => onDrill({ kind: "heatmap", institutionId: t.tenant_id })} className="text-muted-foreground hover:text-indigo-700" title="Bu kurumun heatmap'i">
                          <MapIcon className="mx-auto size-4" aria-hidden />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sekme: KARŞILAŞTIRMA
// ---------------------------------------------------------------------------

function BenchmarkTab({ d }: { d: ActivityPanelResponse }) {
  return (
    <div className="space-y-5">
      {d.plan_benchmark.length > 0 ? (
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-2.5">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold"><Gauge className="size-4 text-blue-600" aria-hidden /> Plan Başına Benchmark</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr><th className="px-3 py-1.5 text-left">Plan</th><th className="px-3 py-1.5 text-right">Hesap</th><th className="px-3 py-1.5 text-right">Akt. Öğretmen</th><th className="px-3 py-1.5 text-right">Akt. Öğrenci</th><th className="px-3 py-1.5 text-right">Adopsiyon</th><th className="px-3 py-1.5 text-right">Oturum</th><th className="px-3 py-1.5 text-right">Aylık Ücret</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.plan_benchmark.map((r, i) => (
                  <tr key={`${r.owner_type}-${r.plan}-${i}`} className={cn("hover:bg-muted/40", r.monthly_price === 0 && "bg-muted/20")}>
                    <td className="px-3 py-1.5"><div className="font-medium">{r.plan_label}</div><div className="font-mono text-[10px] text-muted-foreground">{r.plan}</div></td>
                    <td className="px-3 py-1.5 text-right font-mono text-muted-foreground">{r.institution_count}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-muted-foreground">{r.avg_active_teachers}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-muted-foreground">{r.avg_active_students}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{r.avg_feature_adoption}/{r.feature_total} <span className="text-[10px] text-muted-foreground">(%{r.avg_feature_adoption_pct})</span></td>
                    <td className="px-3 py-1.5 text-right font-mono text-muted-foreground">{r.avg_session_min > 0 ? `${r.avg_session_min}dk` : "—"}</td>
                    <td className={cn("px-3 py-1.5 text-right font-mono", r.monthly_price > 0 ? "font-semibold text-emerald-700" : "text-muted-foreground")}>{r.monthly_price > 0 ? `${r.monthly_price.toLocaleString("tr-TR")} ₺` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {/* Champions */}
      {d.champions.length > 0 ? (
        <section>
          <h2 className="mb-3 inline-flex items-center gap-2 text-sm font-semibold"><Trophy className="size-4 text-emerald-600" aria-hidden /> Champion Hesaplar — En Üst %10</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {d.champions.map((c, i) => (
              <Card key={`${c.owner_id}-${i}`} className="border-2 border-emerald-300 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase text-emerald-700">
                      <Award className="size-3.5" aria-hidden /> Champion <OwnerBadge ownerType={c.owner_type} />
                    </div>
                    <Link href={c.detail_url} className="block truncate text-sm font-semibold hover:text-emerald-700 hover:underline">{c.institution_name}</Link>
                    <div className="font-mono text-[10px] text-muted-foreground">{c.plan}{c.is_paying ? " · ödeyen" : ""}</div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-2xl font-bold text-emerald-700">{c.score}</div>
                    <div className="text-[9px] text-muted-foreground">skor / 100</div>
                  </div>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
                  <div><div className="text-muted-foreground">Yoğunluk</div><div className="font-semibold">{c.density}g/kişi</div></div>
                  <div><div className="text-muted-foreground">Adopsiyon</div><div className="font-semibold">{c.feature_adoption}/{c.feature_total}</div></div>
                  <div><div className="text-muted-foreground">Yaş</div><div className="font-semibold">{c.age_months}ay</div></div>
                  <div><div className="text-muted-foreground">Öğr/Öğret</div><div className="font-semibold">{c.student_teacher_ratio}</div></div>
                </div>
                <div className="mt-2 border-t border-emerald-100 pt-2">
                  <SuggestionPopover suggestions={d.action_suggestions.champion ?? []} />
                  <Link href={`${c.detail_url}?tab=actions`} className="ml-2 inline-flex items-center gap-0.5 text-[11px] text-emerald-700 hover:underline">
                    CRM aksiyonu <ChevronRight className="size-3" aria-hidden />
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
