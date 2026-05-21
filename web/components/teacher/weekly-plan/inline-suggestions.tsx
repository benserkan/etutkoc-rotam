"use client";

import * as React from "react";
import {
  AlertTriangle,
  Ban,
  Brain,
  CalendarClock,
  CheckCircle2,
  Loader2,
  Plus,
  Sparkles,
  Sprout,
  Target,
  TrendingDown,
  X,
} from "lucide-react";

import {
  useAcceptAllSuggestions,
  useAcceptSuggestion,
  useRejectSuggestion,
} from "@/lib/hooks/use-insights-mutations";
import type {
  TeacherActivePhase,
  TeacherSuggestionInline,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

interface Props {
  studentId: number;
  dayDate: string;
  suggestions: TeacherSuggestionInline[];
  maturityValue: number;
  maturityLabel: string;
  weeksObserved: number;
  daysObserved: number;
  activePhase: TeacherActivePhase | null;
  trackRequired: boolean;
  trackMissing: boolean;
  trackLabel: string | null;
}

/**
 * Gün kartına gömülü öneri paneli. Görsel: Jinja indigo-50 panel + emoji yığını
 * yerine bg-muted/40 surface + lucide ikon + tonal badge sistemi.
 */
export function InlineSuggestions({
  studentId,
  dayDate,
  suggestions,
  maturityValue,
  maturityLabel,
  weeksObserved,
  daysObserved,
  activePhase,
  trackRequired,
  trackMissing,
  trackLabel,
}: Props) {
  const acceptAll = useAcceptAllSuggestions(studentId);

  const matPct = Math.round(maturityValue * 100);
  const matTone =
    maturityValue < 0.3
      ? "neutral"
      : maturityValue < 0.7
        ? "info"
        : "success";

  function onAcceptAll() {
    if (suggestions.length === 0) return;
    if (!window.confirm(`${suggestions.length} öneriyi tamamen ekle?`)) {
      return;
    }
    acceptAll.mutate({
      body: {
        date: dayDate,
        items: suggestions.map((s) => ({
          book_id: s.book_id,
          section_id: s.section_id,
          planned_count: s.planned_count,
        })),
      },
    });
  }

  return (
    <div className="border-t border-border bg-muted/30">
      <div className="px-5 py-3 flex items-center justify-between gap-3 flex-wrap border-b border-border/60">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center size-6 rounded-md bg-foreground text-background">
              <Sparkles className="size-3.5" aria-hidden />
            </span>
            <span className="text-sm font-semibold text-foreground tracking-tight">
              Öneriler
            </span>
          </div>
          {suggestions.length > 0 ? (
            <Pill tone="success">{suggestions.length} hazır</Pill>
          ) : null}
          <Pill tone={matTone}>
            <Target className="size-3" aria-hidden />
            {maturityLabel || "—"} · %{matPct}
          </Pill>
          {activePhase && activePhase.kind !== "regular" ? (
            <Pill tone={phaseTone(activePhase.kind)}>
              {activePhase.kind_badge} · {activePhase.capacity_multiplier.toFixed(1)}x
            </Pill>
          ) : null}
          {trackLabel ? (
            <Pill tone="violet">
              <Target className="size-3" aria-hidden />
              {trackLabel}
            </Pill>
          ) : null}
        </div>
        {suggestions.length > 0 ? (
          <button
            type="button"
            onClick={onAcceptAll}
            disabled={acceptAll.isPending}
            className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md bg-foreground text-background hover:bg-foreground/90 disabled:opacity-40 transition"
          >
            {acceptAll.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <CheckCircle2 className="size-3.5" aria-hidden />
            )}
            Tümünü ekle ({suggestions.length})
          </button>
        ) : null}
      </div>

      {trackRequired && trackMissing ? (
        <div className="px-5 py-2.5 border-b border-border/60 flex items-start gap-2.5 text-xs">
          <AlertTriangle
            className="size-4 text-amber-600 flex-shrink-0 mt-0.5"
            aria-hidden
          />
          <div className="flex-1">
            <span className="font-semibold text-foreground">Alan seçimi eksik</span>
            <span className="text-muted-foreground">
              {" "}
              — 11. sınıf+ öğrenci için AYT alanı (Sayısal/EA/Sözel/Dil) belirlenmemiş;
              şu an yalnızca TYT içeriği öneriliyor.
            </span>
          </div>
        </div>
      ) : null}

      {weeksObserved === 0 && daysObserved === 0 ? (
        <p className="px-5 py-4 text-xs text-muted-foreground italic">
          Henüz geçmiş plan verisi yok — sistem siz plan yaptıkça öğrenecek.
        </p>
      ) : suggestions.length === 0 ? (
        <p className="px-5 py-4 text-xs text-muted-foreground italic">
          Bu güne ek öneri yok. Mevcut plan tipik düzende veya tüm bölümler ekli.
        </p>
      ) : (
        <div className="px-5 py-3 space-y-2">
          {suggestions.map((s) => (
            <SuggestionCard
              key={`${s.book_id}-${s.section_id}`}
              studentId={studentId}
              dayDate={dayDate}
              s={s}
            />
          ))}
          <p className="text-[11px] text-muted-foreground/80 italic pt-1">
            Güven yüzdesi yüksek olanlar net çerçeveli, zayıf olanlar soluk
            görünür. Daha çok plan biriktikçe öneriler keskinleşir.
          </p>
        </div>
      )}
    </div>
  );
}

function SuggestionCard({
  studentId,
  dayDate,
  s,
}: {
  studentId: number;
  dayDate: string;
  s: TeacherSuggestionInline;
}) {
  const accept = useAcceptSuggestion(studentId);
  const reject = useRejectSuggestion(studentId);
  const [count, setCount] = React.useState(s.planned_count);

  const conf = s.confidence;
  const opacity =
    conf < 0.2 ? 0.55 : conf < 0.4 ? 0.7 : conf < 0.6 ? 0.85 : 1;
  const isStrong = conf >= 0.6;

  return (
    <div
      className={cn(
        "rounded-lg border bg-card transition hover:shadow-sm",
        isStrong ? "border-border" : "border-dashed border-border/70",
      )}
      style={{ opacity }}
    >
      <div className="px-3 py-2 flex items-center gap-3">
        <ConfidenceMark conf={conf} label={s.confidence_label} />
        <div className="flex-1 min-w-0">
          <div className="text-sm leading-snug">
            <span className="font-semibold text-foreground">{s.book_name}</span>
            <span className="text-muted-foreground"> · {s.section_label}</span>
            {s.topic_name ? (
              <span className="text-muted-foreground/70"> ({s.topic_name})</span>
            ) : null}
            <span className="ml-1.5 text-xs text-muted-foreground/80">
              · {s.subject_name}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 mt-1">
            {s.reasons.map((reason, i) => (
              <ReasonBadge key={i} reason={reason} />
            ))}
            <span className="text-[10px] text-muted-foreground/70 ml-0.5">
              güven %{Math.round(conf * 100)}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <input
            type="number"
            min={1}
            max={s.remaining > 0 ? s.remaining : undefined}
            value={count}
            onChange={(e) => setCount(Number(e.target.value) || 1)}
            className="w-12 px-1.5 py-1 border border-input bg-background rounded text-xs text-right tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <button
            type="button"
            onClick={() =>
              accept.mutate({
                body: {
                  date: dayDate,
                  book_id: s.book_id,
                  section_id: s.section_id,
                  planned_count: Math.max(1, count),
                },
              })
            }
            disabled={accept.isPending || reject.isPending}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-foreground text-background text-xs hover:bg-foreground/90 disabled:opacity-40 transition"
          >
            {accept.isPending ? (
              <Loader2 className="size-3 animate-spin" aria-hidden />
            ) : (
              <Plus className="size-3" aria-hidden />
            )}
            Ekle
          </button>
          <button
            type="button"
            onClick={() =>
              reject.mutate({
                body: {
                  date: dayDate,
                  book_id: s.book_id,
                  section_id: s.section_id,
                },
              })
            }
            disabled={accept.isPending || reject.isPending}
            className="p-1 rounded-md text-muted-foreground hover:text-destructive hover:bg-muted transition"
            title="Bu öneriyi reddet (sistem öğrensin)"
            aria-label="Reddet"
          >
            {reject.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <X className="size-3.5" aria-hidden />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function ConfidenceMark({ conf, label }: { conf: number; label: string }) {
  const tone =
    conf >= 0.7
      ? "bg-emerald-600 text-white"
      : conf >= 0.4
        ? "bg-foreground/80 text-background"
        : "bg-muted-foreground/40 text-background";
  return (
    <span
      className={cn(
        "text-[9px] uppercase tracking-wider font-bold px-1.5 py-1 rounded-md flex-shrink-0",
        tone,
      )}
    >
      {label}
    </span>
  );
}

type Tone = "neutral" | "info" | "success" | "violet" | "amber" | "rose" | "sky";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "border-border bg-muted text-muted-foreground",
  info: "border-indigo-200 bg-indigo-50 text-indigo-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  violet: "border-violet-200 bg-violet-50 text-violet-700",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  rose: "border-rose-200 bg-rose-50 text-rose-700",
  sky: "border-sky-200 bg-sky-50 text-sky-700",
};

function Pill({
  tone,
  children,
}: {
  tone: Tone;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border",
        TONE_CLASS[tone],
      )}
    >
      {children}
    </span>
  );
}

function ReasonBadge({ reason }: { reason: string }) {
  const lower = reason.toLocaleLowerCase("tr-TR");
  let Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }> =
    Sparkles;
  let tone: Tone = "neutral";
  let text = reason;
  if (lower.includes("tekrar kart")) {
    Icon = Brain;
    tone = "rose";
    text = "Tekrar kartında zorlandı";
  } else if (lower.includes("belirgin geride")) {
    Icon = TrendingDown;
    tone = "rose";
    text = "Geride kalma";
  } else if (lower.includes("dikkat gerektir")) {
    Icon = AlertTriangle;
    tone = "amber";
    text = "Dikkat gerekiyor";
  } else if (lower.includes("önceden atan") || lower.includes("onceden atan")) {
    Icon = CalendarClock;
    tone = "info";
  } else if (lower.includes("reddet")) {
    Icon = Ban;
    tone = "rose";
  } else if (lower.includes("öğreniyor") || lower.includes("ogreniyor")) {
    Icon = Sprout;
    tone = "success";
    text = "Sistem öğreniyor";
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-md border",
        TONE_CLASS[tone],
      )}
      title={reason}
    >
      <Icon className="size-3" aria-hidden />
      <span>{text}</span>
    </span>
  );
}

function phaseTone(kind: string): Tone {
  switch (kind) {
    case "winter_break":
      return "sky";
    case "summer_camp":
      return "amber";
    case "exam_prep":
      return "rose";
    default:
      return "neutral";
  }
}
