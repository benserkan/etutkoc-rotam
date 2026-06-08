"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  CircleHelp,
  Dna,
  Info,
  Loader2,
  Megaphone,
  Minus,
  Moon,
  Sun,
  Sunrise,
  Sunset,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

import { getTeacherStudentDna, teacherKeys } from "@/lib/api/teacher";
import { useDnaNotifyParent } from "@/lib/hooks/use-teacher-mutations";
import type {
  BurnoutRiskLevel,
  BurnoutSeverity,
  DnaChronotype,
  TeacherDnaResponse,
} from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";

interface Props {
  studentId: number;
}

const TR_DAY_NAMES = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

const CHRONOTYPE_LABELS: Record<DnaChronotype, string> = {
  morning: "Sabahçı",
  afternoon: "Öğle/Erken Öğleden Sonra",
  evening: "Akşamcı",
  night: "Gece Kuşu",
  unknown: "Belirsiz",
};
const CHRONOTYPE_ICON: Record<DnaChronotype, LucideIcon> = {
  morning: Sunrise,
  afternoon: Sun,
  evening: Sunset,
  night: Moon,
  unknown: CircleHelp,
};
const CHRONOTYPE_ICON_TONE: Record<DnaChronotype, string> = {
  morning: "text-amber-500",
  afternoon: "text-sky-500",
  evening: "text-orange-500",
  night: "text-indigo-400",
  unknown: "text-muted-foreground",
};

export function DnaBoard({ studentId }: Props) {
  const q = useQuery<TeacherDnaResponse>({
    queryKey: teacherKeys.studentDna(studentId),
    queryFn: () => getTeacherStudentDna(studentId),
    staleTime: 30_000,
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-12">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
      </div>
    );
  }
  if (q.error || !q.data) {
    return <div className="text-sm text-rose-500">DNA verileri yüklenemedi.</div>;
  }
  return <Body studentId={studentId} d={q.data} />;
}

function Body({ studentId, d }: { studentId: number; d: TeacherDnaResponse }) {
  const [notifyOpen, setNotifyOpen] = React.useState(false);

  return (
    <div className="space-y-6 max-w-6xl">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            <Link
              href={`/teacher/students/${studentId}`}
              className="hover:underline"
            >
              ← {d.student_name}
            </Link>
          </p>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
            <Dna className="size-6 text-sky-500" aria-hidden />
            Çalışma DNA
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {d.window_days} günlük çalışma örüntüsü ve tükenmişlik analizi.
          </p>
          <DemoHint contextKey="dna" role="teacher" className="mt-1.5" />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            onClick={() => setNotifyOpen(true)}
            disabled={d.parent_count === 0}
            variant="default"
            className="gap-2"
            title={
              d.parent_count === 0
                ? "Bağlı aktif veli yok"
                : "DNA verisinden mesaj üret, veliye duyur"
            }
          >
            <Megaphone className="size-4" aria-hidden />
            Veliye duyur
            {d.parent_count > 0 ? (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-foreground/10">
                {d.parent_count}
              </span>
            ) : (
              <span className="text-[10px] text-muted-foreground ml-0.5">
                (veli yok)
              </span>
            )}
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/teacher/burnout">
              Tüm öğrenciler risk listesi
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          </Button>
        </div>
      </header>

      <BurnoutCard d={d} />

      {!d.has_enough_data ? (
        <Card className="border-dashed">
          <CardContent className="text-center py-12">
            <BarChart3
              className="size-8 mx-auto text-muted-foreground/60 mb-2"
              aria-hidden
            />
            <p className="font-medium text-foreground">
              Profil için yeterli veri yok
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              {d.window_days} günlük pencerede yalnızca{" "}
              <b className="text-foreground">{d.total_completed}</b> görev
              tamamlandı. DNA profili için en az 5 tamamlanmış görev gerekiyor.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <HourConfidenceNote d={d} />
          <KpiStrip d={d} />
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">
                Saat × Gün Çalışma Haritası
                <span className="text-xs font-normal text-muted-foreground ml-2">
                  ({d.window_days} gün)
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <DnaHeatmap heatmap={d.heatmap} />
            </CardContent>
          </Card>
          <HourBands d={d} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SubjectBars d={d} />
            <WeeklyTrend d={d} />
          </div>
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer hover:text-foreground inline-flex items-center gap-1.5">
              <Info className="size-3.5" aria-hidden />
              Çalışma DNA nedir, nasıl hesaplanır?
            </summary>
            <div className="mt-2 p-4 rounded-lg bg-muted/40 text-sm leading-relaxed text-foreground/80">
              <p>
                Çalışma DNA&apos;sı, son {d.window_days} günde tamamladığınız
                görevlerin <b>saat × gün</b> dağılımından çıkar. Heatmap
                koyulaştıkça o saat aralığında daha çok görev tamamlanmış
                demektir.
              </p>
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li>
                  <b>Chronotype:</b> hangi saat bandında en aktif olduğu
                </li>
                <li>
                  <b>Peak gün/saat:</b> en yoğun çalışma penceresi
                </li>
                <li>
                  <b>Trend:</b> bu hafta vs geçen hafta tamamlanan görev
                </li>
              </ul>
            </div>
          </details>
        </>
      )}

      <NotifyParentDialog
        studentId={studentId}
        open={notifyOpen}
        onOpenChange={setNotifyOpen}
        preview={d.parent_message_preview}
        parentCount={d.parent_count}
        hourConfidence={d.hour_data_confidence}
        batchCount={d.batch_completion_count}
      />
    </div>
  );
}

const BURNOUT_LEVEL_META: Record<
  BurnoutRiskLevel,
  {
    icon: LucideIcon;
    label: string;
    accent: string;
    ringColor: string;
    iconColor: string;
  }
> = {
  healthy: {
    icon: CheckCircle2,
    label: "Sağlıklı",
    accent: "border-l-emerald-500",
    ringColor: "ring-emerald-500/20",
    iconColor: "text-emerald-500",
  },
  watch: {
    icon: AlertCircle,
    label: "Dikkat",
    accent: "border-l-sky-500",
    ringColor: "ring-sky-500/20",
    iconColor: "text-sky-500",
  },
  warn: {
    icon: AlertTriangle,
    label: "Uyarı",
    accent: "border-l-amber-500",
    ringColor: "ring-amber-500/20",
    iconColor: "text-amber-500",
  },
  critical: {
    icon: AlertOctagon,
    label: "Kritik",
    accent: "border-l-rose-500",
    ringColor: "ring-rose-500/20",
    iconColor: "text-rose-500",
  },
};

function BurnoutCard({ d }: { d: TeacherDnaResponse }) {
  const meta = BURNOUT_LEVEL_META[d.burnout_risk_level];
  const Icon = meta.icon;

  return (
    <Card className={cn("border-l-4 ring-1 ring-inset", meta.accent, meta.ringColor)}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Icon className={cn("size-7", meta.iconColor)} aria-hidden />
            <div>
              <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                Tükenmişlik Riski
              </div>
              <div className="text-2xl font-bold tabular-nums text-foreground inline-flex items-baseline gap-2">
                {d.burnout_risk_score}
                <span className="text-base font-normal text-muted-foreground">
                  / 100
                </span>
                <span className={cn("text-sm font-semibold", meta.iconColor)}>
                  {meta.label}
                </span>
              </div>
            </div>
          </div>
          <div className="text-xs text-muted-foreground">
            {d.burnout_signals.length} aktif sinyal
          </div>
        </div>

        {d.burnout_signals.length > 0 ? (
          <div className="space-y-2 mt-4">
            {d.burnout_signals.map((s) => (
              <SignalRow
                key={s.kind}
                sev={s.severity}
                signal={s}
              />
            ))}
          </div>
        ) : (
          <div className="mt-3 inline-flex items-center gap-2 text-sm text-emerald-500">
            <CheckCircle2 className="size-4" aria-hidden />
            Şu an çalışma örüntüsünde anomali yok. Sağlıklı bir tempo.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const SEVERITY_META: Record<
  BurnoutSeverity,
  { tone: string; pill: string; icon: LucideIcon }
> = {
  low: { tone: "text-sky-500", pill: "bg-sky-500/10 text-sky-500", icon: Info },
  medium: {
    tone: "text-amber-500",
    pill: "bg-amber-500/10 text-amber-500",
    icon: AlertCircle,
  },
  high: {
    tone: "text-rose-500",
    pill: "bg-rose-500/10 text-rose-500",
    icon: AlertTriangle,
  },
};

function SignalRow({
  sev,
  signal,
}: {
  sev: BurnoutSeverity;
  signal: { kind: string; label: string; detail: string };
}) {
  const meta = SEVERITY_META[sev];
  const Icon = meta.icon;
  return (
    <div className="border border-border rounded-lg p-3 flex items-start gap-3 bg-background/40">
      <Icon className={cn("size-5 flex-shrink-0 mt-0.5", meta.tone)} aria-hidden />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-foreground">{signal.label}</span>
          <span
            className={cn(
              "text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md",
              meta.pill,
            )}
          >
            {sev}
          </span>
        </div>
        <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
          {signal.detail}
        </p>
      </div>
    </div>
  );
}

function HourConfidenceNote({ d }: { d: TeacherDnaResponse }) {
  if (d.hour_data_confidence >= 80) return null;
  const isLow = d.hour_data_confidence < 50;
  const Icon = isLow ? AlertTriangle : Info;
  const accentColor = isLow ? "text-amber-500" : "text-sky-500";
  const borderColor = isLow ? "border-l-amber-500" : "border-l-sky-500";
  return (
    <Card className={cn("border-l-4", borderColor)}>
      <CardContent className="p-3 flex items-start gap-3 text-sm">
        <Icon className={cn("size-5 flex-shrink-0 mt-0.5", accentColor)} aria-hidden />
        <div className="flex-1 leading-relaxed text-foreground/90">
          <b>Saat verisinin güvenilirliği: %{d.hour_data_confidence}</b>
          {d.batch_completion_count > 0 ? (
            <>
              {" "}— {d.batch_completion_count} görev <i>toplu işaretleme</i>{" "}
              kümesinde tespit edildi (gün sonu topluca tikleme)
              {d.fallback_scheduled_count > 0 ? (
                <>
                  , {d.fallback_scheduled_count} tanesi planlanan saatine
                  düşürülerek kurtarıldı
                </>
              ) : null}
              .
            </>
          ) : null}
          {isLow ? (
            <span className="block text-xs mt-1.5 text-muted-foreground">
              Daha doğru saat profili için görevleri bittiği anda tek tek
              tikletmeyi dene. Chronotype/peak hour/heatmap saat ekseni
              güvensiz olabilir; gün ve sayı bazlı veriler etkilenmedi.
            </span>
          ) : (
            <span className="block text-xs mt-1.5 text-muted-foreground">
              Saat metriklerine kısmen güvenebilirsin; gün ve sayı bazlı her
              şey güvenilir.
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function KpiStrip({ d }: { d: TeacherDnaResponse }) {
  const ChronoIcon = CHRONOTYPE_ICON[d.chronotype];
  const chronoTone = CHRONOTYPE_ICON_TONE[d.chronotype];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <Card>
        <CardContent className="p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Chronotype
          </div>
          <div className="mt-1.5 inline-flex items-center gap-2 text-base font-semibold text-foreground">
            <ChronoIcon className={cn("size-5", chronoTone)} aria-hidden />
            {CHRONOTYPE_LABELS[d.chronotype]}
          </div>
        </CardContent>
      </Card>
      <Kpi label="En yoğun gün" value={d.peak_day_name ?? "—"} />
      <Kpi
        label="En yoğun saat"
        value={
          d.peak_hour !== null
            ? `${String(d.peak_hour).padStart(2, "0")}:00`
            : "—"
        }
      />
      <Kpi
        label="Tamamlama"
        value={`${d.total_completed} / ${d.total_planned}`}
        sub={`%${Math.round(d.completion_rate * 100)} verim`}
      />
    </div>
  );
}

function Kpi({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div className="text-2xl font-bold mt-1 tabular-nums text-foreground">
          {value}
        </div>
        {sub ? (
          <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function HourBands({ d }: { d: TeacherDnaResponse }) {
  const bands: {
    label: string;
    count: number;
    icon: LucideIcon;
    tone: string;
  }[] = [
    { label: "Sabah (06-12)", count: d.morning_count, icon: Sunrise, tone: "text-amber-500" },
    { label: "Öğleden sonra", count: d.afternoon_count, icon: Sun, tone: "text-sky-500" },
    { label: "Akşam (18-22)", count: d.evening_count, icon: Sunset, tone: "text-orange-500" },
    { label: "Gece (22-06)", count: d.night_count, icon: Moon, tone: "text-indigo-400" },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {bands.map((b) => {
        const Icon = b.icon;
        return (
          <Card key={b.label}>
            <CardContent className="p-4 text-center">
              <Icon className={cn("size-6 mx-auto", b.tone)} aria-hidden />
              <div className="text-[11px] text-muted-foreground mt-1.5">
                {b.label}
              </div>
              <div className="text-xl font-bold mt-0.5 tabular-nums text-foreground">
                {b.count}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function SubjectBars({ d }: { d: TeacherDnaResponse }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">
          Ders Bazlı Çalışma
        </CardTitle>
      </CardHeader>
      <CardContent>
        {d.by_subject.length === 0 ? (
          <p className="text-sm text-muted-foreground">Veri yok.</p>
        ) : (
          <div className="space-y-3">
            {d.by_subject.slice(0, 8).map((s) => {
              const pct = Math.round(s.completion_rate * 100);
              return (
                <div key={s.subject_id ?? s.subject_name}>
                  <div className="flex items-center justify-between text-sm mb-1 gap-2">
                    <span className="text-foreground truncate">
                      {s.subject_name}
                    </span>
                    <span className="text-xs text-muted-foreground whitespace-nowrap tabular-nums">
                      {s.completed}/{s.planned} · %{pct}
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function WeeklyTrend({ d }: { d: TeacherDnaResponse }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Haftalık Eğilim</CardTitle>
      </CardHeader>
      <CardContent>
        {!d.trend || d.trend.direction === "insufficient" ? (
          <p className="text-sm text-muted-foreground">
            İki haftalık karşılaştırma için yeterli veri yok.
          </p>
        ) : (
          <>
            <div className="flex items-baseline gap-3">
              <div
                className={cn(
                  "text-3xl font-bold inline-flex items-center gap-2 tabular-nums",
                  d.trend.direction === "up"
                    ? "text-emerald-500"
                    : d.trend.direction === "down"
                      ? "text-rose-500"
                      : "text-muted-foreground",
                )}
              >
                {d.trend.direction === "up" ? (
                  <TrendingUp className="size-6" aria-hidden />
                ) : d.trend.direction === "down" ? (
                  <TrendingDown className="size-6" aria-hidden />
                ) : (
                  <Minus className="size-6" aria-hidden />
                )}
                {d.trend.delta_pct !== null
                  ? `${Math.round(d.trend.delta_pct)}%`
                  : ""}
              </div>
              <div className="text-sm text-muted-foreground">
                Bu hafta:{" "}
                <b className="text-foreground">{d.trend.this_week_completed}</b>{" "}
                · Geçen:{" "}
                <b className="text-foreground">{d.trend.last_week_completed}</b>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {d.trend.direction === "up"
                ? "Verim artıyor."
                : d.trend.direction === "down"
                  ? "Verim düşüyor — neden olabilir?"
                  : "İstikrarlı tempo."}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function DnaHeatmap({ heatmap }: { heatmap: number[][] }) {
  const maxV = React.useMemo(() => {
    let m = 0;
    for (const row of heatmap) for (const v of row) if (v > m) m = v;
    return m;
  }, [heatmap]);

  return (
    <div className="overflow-x-auto">
      <div
        className="grid gap-[3px] text-[10px] min-w-[480px]"
        style={{ gridTemplateColumns: "32px repeat(24, minmax(14px, 1fr))" }}
      >
        <div />
        {Array.from({ length: 24 }, (_, h) => (
          <div
            key={`h-${h}`}
            className="text-center text-muted-foreground/60 pt-0.5"
          >
            {h % 3 === 0 ? String(h).padStart(2, "0") : ""}
          </div>
        ))}
        {heatmap.map((row, d) => (
          <React.Fragment key={`d-${d}`}>
            <div className="text-right text-muted-foreground pr-1 py-0.5">
              {TR_DAY_NAMES[d]}
            </div>
            {row.map((v, h) => {
              const lvl =
                maxV === 0
                  ? 0
                  : v === 0
                    ? 0
                    : v / maxV < 0.25
                      ? 1
                      : v / maxV < 0.5
                        ? 2
                        : v / maxV < 0.75
                          ? 3
                          : 4;
              return (
                <div
                  key={`c-${d}-${h}`}
                  title={`${TR_DAY_NAMES[d]} ${String(h).padStart(2, "0")}:00 — ${v} görev`}
                  className={cn(
                    "aspect-square rounded-[3px] transition hover:scale-150 cursor-default",
                    HEAT_CELL[lvl],
                  )}
                />
              );
            })}
          </React.Fragment>
        ))}
      </div>
      <div className="flex items-center justify-end gap-1.5 mt-3 text-xs text-muted-foreground">
        <span>Az</span>
        {[0, 1, 2, 3, 4].map((l) => (
          <span
            key={l}
            className={cn("inline-block w-3 h-3 rounded-[3px]", HEAT_CELL[l])}
          />
        ))}
        <span>Çok</span>
      </div>
    </div>
  );
}

const HEAT_CELL: Record<number, string> = {
  0: "bg-muted/60",
  1: "bg-sky-500/25",
  2: "bg-sky-500/50",
  3: "bg-sky-500/75",
  4: "bg-sky-500",
};

function NotifyParentDialog({
  studentId,
  open,
  onOpenChange,
  preview,
  parentCount,
  hourConfidence,
  batchCount,
}: {
  studentId: number;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  preview: string;
  parentCount: number;
  hourConfidence: number;
  batchCount: number;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        {open ? (
          <NotifyParentDialogBody
            studentId={studentId}
            onClose={() => onOpenChange(false)}
            preview={preview}
            parentCount={parentCount}
            hourConfidence={hourConfidence}
            batchCount={batchCount}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function NotifyParentDialogBody({
  studentId,
  onClose,
  preview,
  parentCount,
  hourConfidence,
  batchCount,
}: {
  studentId: number;
  onClose: () => void;
  preview: string;
  parentCount: number;
  hourConfidence: number;
  batchCount: number;
}) {
  const [text, setText] = React.useState(preview);
  const mut = useDnaNotifyParent(studentId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      { body: { body: text } },
      {
        onSuccess: () => {
          onClose();
        },
      },
    );
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle className="inline-flex items-center gap-2">
          <Megaphone className="size-4" aria-hidden />
          Veliye duyur
        </DialogTitle>
        <p className="text-xs text-muted-foreground mt-0.5">
          DNA verisinden hazırlanan mesaj — {parentCount} aktif veliye
          gönderilecek (email + WhatsApp tercihlerine göre).
        </p>
      </DialogHeader>

      {hourConfidence < 50 ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-foreground/90 inline-flex items-start gap-2">
          <AlertTriangle
            className="size-4 text-amber-500 flex-shrink-0 mt-0.5"
            aria-hidden
          />
          <span>
            <b>Saat verisi güvensiz (%{hourConfidence})</b> — bu öğrencide toplu
            işaretleme örüntüsü tespit edildi ({batchCount} görev). Otomatik
            mesajdan chronotype/en yoğun saat/gece kuşu ifadeleri çıkarıldı;
            sadece sayı/gün bazlı veriler kullanıldı.
          </span>
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-xs font-semibold text-foreground uppercase tracking-wider mb-2">
            Mesaj önizleme — değiştirebilirsin
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={2000}
            required
            rows={12}
            className="w-full px-3 py-2 border border-border rounded-md text-sm font-mono leading-relaxed bg-background focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-ring"
          />
          <div className="flex justify-between mt-1 text-[11px] text-muted-foreground">
            <span>Öğrenci bu mesajı görmez — sadece veli kanalına düşer.</span>
            <span className="tabular-nums">{text.length} / 2000</span>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>
            Vazgeç
          </Button>
          <Button
            type="submit"
            disabled={mut.isPending || text.trim().length === 0}
          >
            {mut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Megaphone className="size-4" aria-hidden />
            )}
            Veliye gönder
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}
