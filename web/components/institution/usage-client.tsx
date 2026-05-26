"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  AlertTriangle,
  CircleDashed,
  Gift,
  History,
  Mail,
  ShieldOff,
  Sparkles,
  Wallet,
  Zap,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { institutionPlanLabel } from "@/lib/institution-plans";
import { Card, CardContent } from "@/components/ui/card";
import {
  getInstitutionUsage,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  UsageBreakdownEntry,
  UsageDailyPoint,
  UsageEventItem,
  UsageResponse,
} from "@/lib/types/institution";
import { UsageDailyBarChart } from "@/components/institution/usage-daily-bar-chart";

interface Props {
  initial: UsageResponse;
}

/**
 * Aylık kredi kullanımı — Jinja `usage_dashboard.html` feature parity.
 *
 * Bölümler:
 *  - Hard-block uyarısı (account.hard_block_enabled)
 *  - %80 / %100 uyarı banner'ları
 *  - Ana karta: bu ay kullanılan / kalan + progress
 *  - Tip kırılımı + 30 gün günlük seri (Recharts bar)
 *  - Plan + birim maliyet kartı
 *  - Son 50 event tablosu
 */
export function UsageClient({ initial }: Props) {
  const q = useQuery<UsageResponse>({
    queryKey: institutionKeys.usage(30),
    queryFn: () => getInstitutionUsage(30),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const { institution, account, breakdown, series, events, warn_threshold_pct } =
    data;

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/institution"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <p className="text-[11px] uppercase tracking-wider text-emerald-700 mt-1 font-semibold">
          Üyelik
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-0.5 flex items-center gap-2">
          <Wallet className="size-6 text-emerald-700" aria-hidden />
          Aylık Kredi Kullanımı
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Yapay zeka önerileri, veliye giden e-posta ve WhatsApp mesajları
          belirli sayıda &ldquo;kredi&rdquo; tüketir. {institution.name} ·{" "}
          <span className="font-mono">{account.period_year_month}</span> ayı ·
          plan:{" "}
          <strong className="text-foreground">
            {institutionPlanLabel(account.plan_code)}
          </strong>
        </p>
      </header>

      {account.hard_block_enabled && <HardBlockBanner />}
      {!account.hard_block_enabled &&
        account.usage_pct >= warn_threshold_pct &&
        account.usage_pct < 100 && (
          <WarnBanner
            pct={account.usage_pct}
            remaining={account.remaining_credits}
          />
        )}
      {!account.hard_block_enabled && account.usage_pct >= 100 && (
        <OveruseBanner
          used={account.used_credits}
          allocated={account.total_allocated}
          pct={account.usage_pct}
        />
      )}

      <MainBalanceCard
        used={account.used_credits}
        allocated={account.total_allocated}
        bonus={account.bonus_credits}
        remaining={account.remaining_credits}
        pct={account.usage_pct}
        firstAt={account.first_event_at}
        lastAt={account.last_event_at}
        totalEvents={account.total_event_count}
        hardBlock={account.hard_block_enabled}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <KindBreakdownCard
          breakdown={breakdown}
          totalAllocated={account.total_allocated}
        />
        <DailySeriesCard series={series} />
      </div>

      <PlanInfoBlock
        plan={account.plan_code}
        allocated={account.allocated_credits}
        bonus={account.bonus_credits}
        period={account.period_year_month}
      />

      <EventsTable events={events} />
    </div>
  );
}

// ============================================================================
// Uyarı banner'ları
// ============================================================================

function HardBlockBanner() {
  return (
    <div className="rounded-md border border-rose-300 bg-rose-50 text-rose-900 px-4 py-3 flex items-start gap-3">
      <ShieldOff className="size-5 shrink-0 mt-0.5" aria-hidden />
      <div className="text-sm">
        <div className="font-semibold">Kullanım geçici olarak durduruldu</div>
        <p className="mt-1 text-rose-800">
          ETÜTKOÇ ekibi tarafından kurumunuzun yapay zeka, e-posta ve WhatsApp
          özellikleri manuel olarak durdurulmuş. Görevlerin oluşturulması ve
          diğer normal işlemler etkilenmez. Açtırmak için{" "}
          <a
            href="mailto:destek@etutkoc.com"
            className="underline font-medium hover:text-rose-950"
          >
            destek@etutkoc.com
          </a>
          &apos;a yazın.
        </p>
      </div>
    </div>
  );
}

function WarnBanner({
  pct,
  remaining,
}: {
  pct: number;
  remaining: number;
}) {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 text-amber-900 px-4 py-3 flex items-start gap-3">
      <AlertTriangle className="size-5 shrink-0 mt-0.5" aria-hidden />
      <div className="text-sm">
        <div className="font-semibold">
          Aylık kredinin %{pct}&apos;i kullanıldı
        </div>
        <p className="mt-1 text-amber-800">
          Bu ay sonuna kadar <b>{remaining}</b> krediniz kaldı. Yapay zeka
          kullanımı veya WhatsApp mesaj gönderimi yoğunsa hızlı tükenebilir.
        </p>
      </div>
    </div>
  );
}

function OveruseBanner({
  used,
  allocated,
  pct,
}: {
  used: number;
  allocated: number;
  pct: number;
}) {
  const overflow = Math.max(0, used - allocated);
  return (
    <div className="rounded-md border border-rose-300 bg-rose-50 text-rose-900 px-4 py-3 flex items-start gap-3">
      <AlertOctagon className="size-5 shrink-0 mt-0.5" aria-hidden />
      <div className="text-sm">
        <div className="font-semibold">Aylık krediniz tükendi</div>
        <p className="mt-1 text-rose-800">
          Bu ay <b className="tabular-nums">{overflow}</b> kredi aşım yaptınız
          (toplam %{pct}). Sistem çalışmaya devam ediyor — kurum
          üyeliklerinde aşımda otomatik durdurma yok. <b>Bir sonraki ayın
          1&apos;inde</b> krediniz otomatik yenilenecek. Daha yüksek limit için
          plan yükseltmeyi düşünebilirsiniz.
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// Ana bakiye kartı
// ============================================================================

function MainBalanceCard({
  used,
  allocated,
  bonus,
  remaining,
  pct,
  firstAt,
  lastAt,
  totalEvents,
  hardBlock,
}: {
  used: number;
  allocated: number;
  bonus: number;
  remaining: number;
  pct: number;
  firstAt: string | null;
  lastAt: string | null;
  totalEvents: number;
  hardBlock: boolean;
}) {
  const remainingTone =
    pct >= 100
      ? "text-rose-700"
      : pct >= 80
        ? "text-amber-700"
        : "text-emerald-700";
  const barTone =
    pct >= 100
      ? "bg-rose-500"
      : pct >= 80
        ? "bg-amber-500"
        : "bg-emerald-500";
  const displayPct = Math.min(100, pct);
  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Bu Ay Kullanılan
            </div>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-4xl font-bold tabular-nums">{used}</span>
              <span className="text-base text-muted-foreground tabular-nums">
                / {allocated} kredi
              </span>
              {bonus > 0 && (
                <span className="ml-2 inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-violet-50 text-violet-700 border border-violet-200">
                  <Gift className="size-3" aria-hidden />+{bonus} bonus
                </span>
              )}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Kalan
            </div>
            <div
              className={cn("text-3xl font-bold mt-1 tabular-nums", remainingTone)}
            >
              {remaining}
            </div>
          </div>
        </div>

        <div className="w-full h-3 bg-muted rounded-full overflow-hidden">
          <div
            className={cn("h-full", barTone)}
            style={{ width: `${displayPct}%` }}
          />
        </div>
        <div className="text-[11px] text-muted-foreground flex justify-between tabular-nums">
          <span>%0</span>
          <span className="font-medium text-foreground">%{pct}</span>
          <span>%100</span>
        </div>

        {/* Şeffaflık satırı — ilk/son kullanım + toplam olay */}
        <div className="border-t border-border pt-3 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
          <div>
            <div className="text-muted-foreground">İlk kullanım</div>
            <div className="tabular-nums font-medium">{firstAt ? formatEventTime(firstAt) : "—"}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Son kullanım</div>
            <div className="tabular-nums font-medium">{lastAt ? formatEventTime(lastAt) : "—"}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Bu ay toplam olay</div>
            <div className="tabular-nums font-medium">{totalEvents} işlem</div>
          </div>
        </div>

        {/* "-6 nasıl olur" açıklaması — yalnız kalan eksiyse */}
        {remaining < 0 && (
          <div className="rounded-md border border-rose-200 bg-rose-50/60 px-3 py-2 text-xs text-rose-900">
            <b>Kalan {remaining} kredi nasıl mümkün?</b> Aylık kota {allocated}{bonus > 0 ? ` (+${bonus} bonus)` : ""} ama kullanım {used}.
            {hardBlock ? (
              <> Sert kilit (hard-block) AÇIK olmasına rağmen aşımın olması süper admin&apos;in açıkça izin verdiği işlemlerden veya bonus krediden kaynaklanabilir.</>
            ) : (
              <> Sert kilit KAPALI — kurumun işlerini durdurmamak için yumuşak aşım kabul edildi. Ay sonunda kota sıfırlanır. Limiti artırmak için süper admin bonus kredi ekleyebilir veya plan yükseltebilir.</>
            )}
            {" "}<span className="opacity-80">Aşağıdaki &quot;Son 50 İşlem&quot; tablosundan hangi işlemlerin ne kadar tükettiğini olay olay görebilirsin.</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Tip kırılımı
// ============================================================================

function KindBreakdownCard({
  breakdown,
  totalAllocated,
}: {
  breakdown: UsageBreakdownEntry[];
  totalAllocated: number;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
          <CircleDashed className="size-4 text-muted-foreground" aria-hidden />
          Hangi İşlem Ne Kadar Kullanıldı?
        </h3>
        {breakdown.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">
            Bu ay henüz kredi tüketen işlem yapılmadı.
          </p>
        ) : (
          <ul className="space-y-3">
            {breakdown.map((b) => {
              const pct =
                totalAllocated > 0
                  ? Math.floor((100 * b.credits) / totalAllocated)
                  : 0;
              return (
                <li key={b.kind}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{b.label}</span>
                    <span className="font-mono text-muted-foreground tabular-nums">
                      {b.credits} kredi · %{pct}
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-muted rounded-full mt-1 overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full"
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// 30 günlük seri (Recharts)
// ============================================================================

function DailySeriesCard({ series }: { series: UsageDailyPoint[] }) {
  return (
    <Card>
      <CardContent className="p-5">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
          <Zap className="size-4 text-muted-foreground" aria-hidden />
          Son 30 Gün — Günlük Tüketim
        </h3>
        {series.length === 0 || series.every((p) => p.credits === 0) ? (
          <p className="text-sm text-muted-foreground italic">
            Bu pencerede tüketim kaydı yok.
          </p>
        ) : (
          <UsageDailyBarChart series={series} />
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Plan + birim maliyet bilgisi
// ============================================================================

const KIND_COSTS: Array<{ label: string; cost: number }> = [
  { label: "Yapay zeka kitap şablonu", cost: 5 },
  { label: "Yapay zeka öğrenci içgörüsü", cost: 5 },
  { label: "E-posta gönderimi", cost: 1 },
  { label: "WhatsApp mesajı", cost: 5 },
  { label: "Diğer", cost: 1 },
];

function PlanInfoBlock({
  plan,
  allocated,
  bonus,
  period,
}: {
  plan: string;
  allocated: number;
  bonus: number;
  period: string;
}) {
  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Plan" value={institutionPlanLabel(plan)} />
          <Stat
            label="Aylık Limit"
            value={`${allocated} kredi`}
          />
          <Stat
            label="Hediye Kredi"
            value={`+${bonus}`}
            valueClassName={bonus > 0 ? "text-violet-700" : undefined}
          />
          <Stat label="Bu Ay" value={period} mono />
        </div>

        <div className="pt-3 border-t border-border">
          <p className="text-[11px] text-muted-foreground mb-2">
            Her bir işlem kaç kredi tüketir:
          </p>
          <div className="flex flex-wrap gap-2 text-[11px]">
            {KIND_COSTS.map((kc) => (
              <span
                key={kc.label}
                className="px-2 py-0.5 rounded border border-border bg-muted/40 inline-flex items-center gap-1"
              >
                <Sparkles className="size-2.5 text-emerald-600" aria-hidden />
                {kc.label}: <b className="tabular-nums">{kc.cost} kredi</b>
              </span>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  mono,
  uppercase,
  valueClassName,
}: {
  label: string;
  value: string;
  mono?: boolean;
  uppercase?: boolean;
  valueClassName?: string;
}) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "text-base font-semibold mt-0.5",
          mono && "font-mono",
          uppercase && "uppercase",
          valueClassName,
        )}
      >
        {value}
      </div>
    </div>
  );
}

// ============================================================================
// Son 50 event tablosu
// ============================================================================

function EventsTable({ events }: { events: UsageEventItem[] }) {
  return (
    <Card>
      <div className="px-4 py-2.5 border-b border-border bg-muted/40">
        <h3 className="text-sm font-medium flex items-center gap-1.5">
          <History className="size-4 text-muted-foreground" aria-hidden />
          Son 50 İşlem
        </h3>
      </div>
      {events.length === 0 ? (
        <p className="p-6 text-center text-sm text-muted-foreground italic">
          Henüz kayıt yok.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Ne Zaman</th>
                <th className="text-left px-4 py-2 font-medium">Ne Yapıldı</th>
                <th className="text-right px-4 py-2 font-medium">
                  Tüketilen Kredi
                </th>
                <th className="text-right px-4 py-2 font-medium">
                  Sonra Kalan
                </th>
                <th className="text-left px-4 py-2 font-medium">Kim Yaptı</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {events.map((e) => {
                const after = e.balance_after;
                const afterTone = after == null
                  ? "text-muted-foreground"
                  : after < 0
                    ? "text-rose-700"
                    : after === 0
                      ? "text-amber-700"
                      : "text-foreground";
                return (
                  <tr key={e.id}>
                    <td className="px-4 py-1.5 text-muted-foreground tabular-nums">
                      {formatEventTime(e.occurred_at)}
                    </td>
                    <td className="px-4 py-1.5 font-medium inline-flex items-center gap-1.5">
                      <Mail className="size-3 text-muted-foreground" aria-hidden />
                      {e.kind_label}
                    </td>
                    <td className="px-4 py-1.5 text-right font-mono tabular-nums">
                      -{e.credits}
                    </td>
                    <td className={cn("px-4 py-1.5 text-right font-mono tabular-nums", afterTone)}>
                      {after ?? "—"}
                    </td>
                    <td className="px-4 py-1.5 text-muted-foreground">
                      {e.actor_name ?? (e.actor_user_id != null ? `#${e.actor_user_id}` : "Otomatik (sistem)")}
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

function formatEventTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}
