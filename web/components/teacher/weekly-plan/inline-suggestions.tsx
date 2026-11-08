"use client";

import * as React from "react";
import {
  AlertTriangle,
  Ban,
  Brain,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  CircleDotDashed,
  ListOrdered,
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
  /** Öneri isabeti (0..1, gece ölçümü) — koçun verdiği bölüm ekrandaki önerilerde miydi */
  recHitRate?: number | null;
  recHitItems?: number | null;
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
  recHitRate = null,
  recHitItems = null,
}: Props) {
  const acceptAll = useAcceptAllSuggestions(studentId);
  // Öneriler VARSAYILAN KAPALI (kullanıcı 2026-05-24) — gün kartı sadeleşsin.
  // Başlık + sayı sinyali görünür kalır; liste tıklayınca açılır.
  const [expanded, setExpanded] = React.useState(false);

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

  const hasSuggestions = suggestions.length > 0;
  return (
    <div className="border-t border-border border-l-[3px] border-l-indigo-400/70 bg-indigo-500/[0.04]">
      <div className="px-5 py-3 flex items-center justify-between gap-3 flex-wrap">
        {/* Başlık = aç/kapa toggle (liste varsayılan kapalı) */}
        <button
          type="button"
          onClick={() => hasSuggestions && setExpanded((v) => !v)}
          className={cn(
            "flex items-center gap-2 flex-wrap text-left rounded-md -mx-1 px-1 py-0.5",
            hasSuggestions ? "hover:bg-indigo-500/5 cursor-pointer" : "cursor-default",
          )}
          aria-expanded={expanded}
        >
          <span className="inline-flex items-center justify-center size-6 rounded-md bg-indigo-600 text-white">
            <Sparkles className="size-3.5" aria-hidden />
          </span>
          <span className="text-sm font-semibold text-foreground tracking-tight">
            Öneriler
          </span>
          {hasSuggestions ? (
            <Pill tone="success">{suggestions.length} hazır</Pill>
          ) : null}
          <Pill tone={matTone}>
            <Target className="size-3" aria-hidden />
            {maturityLabel || "—"} · %{matPct}
          </Pill>
          {recHitRate != null ? (
            <Pill tone="info">
              <span title="Son haftalarda verdiğin bölümlerin kaçı önceden burada önerilmişti (gece ölçülür)">
                İsabet %{Math.round(recHitRate * 100)}
              </span>
            </Pill>
          ) : null}
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
          {hasSuggestions ? (
            <ChevronDown
              className={cn(
                "size-4 text-muted-foreground transition-transform",
                expanded && "rotate-180",
              )}
              aria-hidden
            />
          ) : null}
        </button>
        {hasSuggestions ? (
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

      {/* Alan-eksik uyarısı her zaman görünür (nadir + önemli) */}
      {trackRequired && trackMissing ? (
        <div className="px-5 py-2.5 border-b border-border flex items-start gap-2.5 text-xs">
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

      {/* Liste yalnız açıkken. Boş durum mesajları da açıkken (gürültü olmasın). */}
      {!expanded ? null : weeksObserved === 0 && daysObserved === 0 ? (
        <p className="px-5 py-4 text-xs text-muted-foreground italic border-t border-border">
          Henüz geçmiş plan verisi yok — sistem siz plan yaptıkça öğrenecek.
        </p>
      ) : suggestions.length === 0 ? (
        <p className="px-5 py-4 text-xs text-muted-foreground italic border-t border-border">
          Bu güne ek öneri yok. Mevcut plan tipik düzende veya tüm bölümler ekli.
        </p>
      ) : (
        <div className="px-5 py-3 space-y-2 border-t border-border">
          {suggestions.map((s) => (
            <SuggestionCard
              key={`${s.book_id}-${s.section_id}`}
              studentId={studentId}
              dayDate={dayDate}
              s={s}
            />
          ))}
          <p className="text-[11px] text-muted-foreground/80 italic pt-1">
            {recHitRate != null && recHitItems
              ? `Son haftalarda verdiğin ${recHitItems} bölümün %${Math.round(recHitRate * 100)}'i önceden burada önerilmişti. `
              : ""}
            Sıralama, senin bu öğrenciye görev verme alışkanlığından ve öğrencinin
            verisinden (yapılmayan görev, zorlandığı konu, deneme yanlışı) öğrenilir.
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
        isStrong ? "border-border" : "border-dashed border-border",
      )}
      style={{ opacity }}
    >
      <div className="px-3 py-1.5 flex items-center gap-2.5">
        <ConfidenceMark conf={conf} label={s.confidence_label} />
        {/* Tek satır: ad · bölüm · ders · güven% + (varsa) ilk gerekçe rozeti */}
        <div className="flex-1 min-w-0 flex items-center gap-1.5 flex-wrap text-sm leading-snug">
          <span className="font-semibold text-foreground truncate">{s.book_name}</span>
          <span className="text-muted-foreground truncate">· {s.section_label}</span>
          <span className="text-xs text-muted-foreground/80">· {s.subject_name}</span>
          <span className="text-[10px] text-muted-foreground/70">· güven %{Math.round(conf * 100)}</span>
          {s.reasons.slice(0, 1).map((reason, i) => (
            <ReasonBadge key={i} reason={reason} />
          ))}
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
      <WhyLine reasons={s.reasons} />
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

/**
 * Gerekçe satırı: motorun sayılı gerekçeleri ("Yapılmayan görev: son 3 haftada 3 test
 * verilip yapılmadı"). Kırpılmaz — satır kaydırır (dar kapta "…" yasak).
 */
function WhyLine({ reasons }: { reasons: string[] }) {
  const parts = reasons.filter((r) => r.includes(": ")).slice(0, 3);
  if (parts.length === 0) return null;
  return (
    <p className="px-3 pb-1.5 -mt-0.5 text-[11px] leading-snug text-muted-foreground break-words">
      {parts.map((r, i) => {
        const [label, ...rest] = r.split(": ");
        return (
          <span key={i}>
            {i > 0 ? " · " : null}
            <span className="font-medium text-foreground/80">{label}</span>
            {": "}
            {rest.join(": ")}
          </span>
        );
      })}
    </p>
  );
}

const SIGNAL_BADGES: Record<string, { tone: Tone; Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }> }> = {
  "Son günlerin devamı": { tone: "success", Icon: CircleDotDashed },
  "Sıradaki bölüm": { tone: "success", Icon: ListOrdered },
  "Kitapta sıradaki bölüm": { tone: "info", Icon: ListOrdered },
  "Yapılmayan görev": { tone: "amber", Icon: AlertTriangle },
  "Aksayan ders": { tone: "amber", Icon: AlertTriangle },
  "Geçen hafta zorlandığı konu": { tone: "rose", Icon: TrendingDown },
  "Uzun süredir verilmeyen ders": { tone: "amber", Icon: CalendarClock },
  "Kaynakta geride kalan ders": { tone: "amber", Icon: TrendingDown },
  "Denemede yanlış": { tone: "rose", Icon: Target },
  "Açık yanlış": { tone: "rose", Icon: Target },
  "Tekrarda zorlanma": { tone: "rose", Icon: Brain },
  "Koçun gün alışkanlığı": { tone: "info", Icon: CalendarClock },
};

function ReasonBadge({ reason }: { reason: string }) {
  const lower = reason.toLocaleLowerCase("tr-TR");
  const sigLabel = reason.includes(": ") ? reason.split(": ")[0] : null;
  const sig = sigLabel ? SIGNAL_BADGES[sigLabel] : undefined;
  if (sigLabel && sig) {
    const SigIcon = sig.Icon;
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-md border",
          TONE_CLASS[sig.tone],
        )}
        title={reason}
      >
        <SigIcon className="size-3" aria-hidden />
        <span>{sigLabel}</span>
      </span>
    );
  }
  let Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }> =
    Sparkles;
  let tone: Tone = "neutral";
  let text = reason;
  if (lower.includes("müfredatta sıradaki")) {
    Icon = ListOrdered;
    tone = "success";
    text = "Müfredatta sıradaki";
  } else if (lower.includes("müfredatta yaklaşan")) {
    Icon = ListOrdered;
    tone = "info";
    text = "Müfredatta yaklaşan";
  } else if (lower.includes("müfredatta ileride")) {
    Icon = ListOrdered;
    tone = "amber";
    text = "Müfredatta ileride";
  } else if (lower.includes("başlanan konuyu")) {
    Icon = CircleDotDashed;
    tone = "info";
    text = "Konuyu tamamlama";
  } else if (lower.includes("tekrar kart")) {
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
