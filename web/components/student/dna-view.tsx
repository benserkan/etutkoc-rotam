import * as React from "react";
import {
  AlertTriangle,
  Moon,
  Sun,
  Sunrise,
  Sunset,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { JargonTooltip } from "@/components/jargon-tooltip";
import { DemoHint } from "@/components/demos/demo-hint";
import type {
  BurnoutRiskLevel,
  BurnoutSignal,
  DnaChronotype,
  DnaResponse,
  DnaSubjectActivity,
  DnaTrend,
} from "@/lib/types/student";

interface Props {
  data: DnaResponse;
}

const DAY_NAMES = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

const CHRONOTYPE_META: Record<
  DnaChronotype,
  { label: string; emoji: string; icon: React.ComponentType<{ className?: string }> }
> = {
  morning: { label: "Sabahçı (06-12)", emoji: "🌅", icon: Sunrise },
  afternoon: { label: "Öğleden sonra (12-18)", emoji: "☀️", icon: Sun },
  evening: { label: "Akşamcı (18-22)", emoji: "🌆", icon: Sunset },
  night: { label: "Gececi (22-06)", emoji: "🌙", icon: Moon },
  unknown: { label: "Yetersiz veri", emoji: "❓", icon: Sun },
};

const RISK_META: Record<BurnoutRiskLevel, { label: string; bg: string }> = {
  healthy: {
    label: "Sağlıklı",
    bg: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  },
  watch: {
    label: "Gözlemde",
    bg: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200",
  },
  warn: {
    label: "Dikkat",
    bg: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  },
  critical: {
    label: "Kritik",
    bg: "bg-destructive/15 text-destructive",
  },
};

export function DnaView({ data }: Props) {
  const chrono = CHRONOTYPE_META[data.chronotype];
  const risk = RISK_META[data.burnout_risk_level];
  // GÖREV tamamlama (deneme soruları test'e karışmaz) — eski hacim-oranına fallback
  const completionPct =
    data.gorev_total > 0
      ? Math.round((data.gorev_done / data.gorev_total) * 100)
      : Math.round(data.completion_rate * 100);

  return (
    <div className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
          Çalışma DNA&apos;n
        </h1>
        <p className="text-sm text-muted-foreground">
          Son {data.window_days} günde nasıl çalışıyorsun? Saat dilimlerine, ders
          dağılımına ve haftalık trende göre kendi örüntün çıkarıldı.
        </p>
        <DemoHint contextKey="dna" role="student" />
      </header>

      {!data.has_enough_data ? (
        <div className="rounded-lg border border-amber-300/50 bg-amber-50 dark:bg-amber-950/20 px-4 py-3 text-sm">
          <p className="font-medium">Henüz yeterli veri yok</p>
          <p className="text-muted-foreground mt-0.5">
            Profil hesabı için en az 5 tamamlanmış göreve ihtiyacın var. Bu
            sayfa görev tamamladıkça zenginleşecek.
          </p>
        </div>
      ) : null}

      {/* Üst sıra kartlar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Tip
          </p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-2xl" aria-hidden>
              {chrono.emoji}
            </span>
            <p className="font-medium leading-tight">{chrono.label}</p>
          </div>
          {data.peak_hour !== null ? (
            <p className="text-xs text-muted-foreground mt-2">
              En yoğun saat: <span className="font-medium text-foreground">{data.peak_hour}:00</span>
              {data.peak_day_name ? (
                <span> · {data.peak_day_name}</span>
              ) : null}
            </p>
          ) : null}
        </Card>

        <Card>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Tamamlama
          </p>
          <p className="font-display text-3xl font-bold tabular-nums mt-1">
            %{completionPct}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {data.gorev_total > 0 ? (
              <>{data.gorev_done} / {data.gorev_total} görev</>
            ) : (
              <>{data.total_completed} / {data.total_planned}</>
            )}{" "}
            · son {data.window_days} gün
          </p>
          {data.gorev_total > 0 &&
          (data.test_planned > 0 || data.deneme_count > 0) ? (
            <p className="text-[11px] text-muted-foreground/80 mt-0.5">
              {data.test_planned > 0
                ? `${data.test_completed}/${data.test_planned} test`
                : ""}
              {data.test_planned > 0 && data.deneme_count > 0 ? " · " : ""}
              {data.deneme_count > 0 ? `${data.deneme_count} deneme` : ""}
            </p>
          ) : null}
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Yorgunluk durumu
            </p>
            <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", risk.bg)}>
              {risk.label}
            </span>
          </div>
          <p className="font-display text-3xl font-bold tabular-nums mt-1">
            {data.burnout_risk_score}
            <span className="text-base font-normal text-muted-foreground">/100</span>
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {data.burnout_signals.length} sinyal
          </p>
        </Card>
      </div>

      {/* Saat bandı + heatmap */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Hangi saatlerde aktifsin?</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <BandPill icon={<Sunrise className="size-3.5" aria-hidden />} label="Sabah" value={data.morning_count} total={data.total_completed} />
          <BandPill icon={<Sun className="size-3.5" aria-hidden />} label="Öğle" value={data.afternoon_count} total={data.total_completed} />
          <BandPill icon={<Sunset className="size-3.5" aria-hidden />} label="Akşam" value={data.evening_count} total={data.total_completed} />
          <BandPill icon={<Moon className="size-3.5" aria-hidden />} label="Gece" value={data.night_count} total={data.total_completed} />
        </div>
        <Heatmap heatmap={data.heatmap} />
        {data.hour_data_confidence < 70 ? (
          <p className="text-xs text-muted-foreground inline-flex items-center gap-1">
            <AlertTriangle className="size-3.5 text-amber-500" aria-hidden />
            Saat verisinin güvenirliği %{data.hour_data_confidence} — toplu
            işaretleme yapmış olabilirsin; saat metrikleri için biraz daha veri
            gerek.
          </p>
        ) : null}
      </section>

      {/* Trend */}
      {data.trend ? <TrendCard trend={data.trend} /> : null}

      {/* Ders bazlı */}
      {data.by_subject.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Ders bazlı tamamlama</h2>
          <ul className="space-y-2">
            {data.by_subject.map((s) => (
              <SubjectRow key={s.subject_name} s={s} />
            ))}
          </ul>
        </section>
      ) : null}

      {/* Burnout sinyalleri */}
      {data.burnout_signals.length > 0 ? (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold flex items-center gap-1.5">
            <JargonTooltip
              term="Yorgunluk sinyalleri"
              content="Aşırı çalışma örüntülerini erken tespit eden 5 sinyalden kaçı tetiklenmiş."
            />
          </h2>
          <ul className="space-y-2">
            {data.burnout_signals.map((sig) => (
              <BurnoutRow key={sig.kind} sig={sig} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

// =============================================================================
// Alt parçalar
// =============================================================================

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-1">
      {children}
    </div>
  );
}

function BandPill({
  icon,
  label,
  value,
  total,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  total: number;
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          {icon}
          {label}
        </span>
        <span className="tabular-nums">%{pct}</span>
      </div>
      <p className="font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function Heatmap({ heatmap }: { heatmap: number[][] }) {
  // Max'a göre ölçek için
  let max = 1;
  for (const row of heatmap) {
    for (const v of row) {
      if (v > max) max = v;
    }
  }
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid grid-cols-[2.25rem_repeat(24,minmax(1rem,1.25rem))] gap-1 text-[10px]">
        <span aria-hidden />
        {Array.from({ length: 24 }, (_, h) => (
          <span key={h} className="text-center text-muted-foreground">
            {h % 3 === 0 ? h : ""}
          </span>
        ))}
        {heatmap.map((row, di) => (
          <React.Fragment key={di}>
            <span className="text-muted-foreground self-center">
              {DAY_NAMES[di]}
            </span>
            {row.map((v, hi) => {
              const ratio = v / max;
              return (
                <span
                  key={hi}
                  className="h-4 rounded-sm"
                  style={{
                    backgroundColor:
                      v === 0
                        ? "var(--muted)"
                        : `color-mix(in oklab, var(--primary) ${Math.round(ratio * 100)}%, var(--muted))`,
                  }}
                  title={`${DAY_NAMES[di]} ${hi}:00 → ${v} görev`}
                  aria-label={`${DAY_NAMES[di]} ${hi}:00 ${v} görev`}
                />
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

function TrendCard({ trend }: { trend: DnaTrend }) {
  const dir = trend.direction;
  const Icon =
    dir === "up" ? TrendingUp : dir === "down" ? TrendingDown : TrendingDown;
  const tone =
    dir === "up"
      ? "text-emerald-600"
      : dir === "down"
        ? "text-destructive"
        : "text-muted-foreground";
  const label =
    dir === "up"
      ? "Yükselişte"
      : dir === "down"
        ? "Düşüşte"
        : dir === "flat"
          ? "Sabit"
          : "Yetersiz veri";
  return (
    <section className="rounded-lg border border-border bg-card p-4 flex items-center gap-4">
      <Icon className={cn("size-8", tone)} aria-hidden />
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">
          Bu hafta {trend.this_week_completed} · Geçen hafta {trend.last_week_completed}
          {trend.delta_pct !== null ? ` · %${Math.abs(Math.round(trend.delta_pct))} ${dir === "up" ? "artış" : "azalış"}` : ""}
        </p>
      </div>
    </section>
  );
}

function SubjectRow({ s }: { s: DnaSubjectActivity }) {
  const pct = Math.round(s.completion_rate * 100);
  return (
    <li className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium truncate">{s.subject_name}</span>
        <span className="text-xs text-muted-foreground tabular-nums">
          {s.completed}/{s.planned} · %{pct}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className={cn(
            "h-full",
            pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-400" : "bg-rose-400",
          )}
          style={{ width: `${pct}%` }}
          aria-hidden
        />
      </div>
    </li>
  );
}

function BurnoutRow({ sig }: { sig: BurnoutSignal }) {
  const tone =
    sig.severity === "high"
      ? "border-destructive/40 bg-destructive/5"
      : sig.severity === "medium"
        ? "border-amber-400/40 bg-amber-50 dark:bg-amber-950/10"
        : "border-blue-400/40 bg-blue-50 dark:bg-blue-950/10";
  return (
    <li className={cn("rounded-md border px-3 py-2 text-sm", tone)}>
      <p className="font-medium">
        <span aria-hidden className="mr-1.5">
          {sig.emoji}
        </span>
        {sig.label}
      </p>
      <p className="text-xs text-muted-foreground mt-0.5">{sig.detail}</p>
    </li>
  );
}

