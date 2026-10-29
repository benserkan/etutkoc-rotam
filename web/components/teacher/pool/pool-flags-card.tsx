"use client";

import * as React from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, Info, OctagonAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import type { PoolFlagOut, PoolFlagsOut } from "@/lib/api/pool";

/**
 * Havuz erken uyarı kartı (Adım 4, K40–K51). K48: öğrenci başına 1 ANA kart, gerisi
 * katlanan ek sinyal. Veliye gitmez (K52); öğrenci bu kartı görmez (K48 kırmızı gitmez).
 * Seans ekranı + havuz editörü aynı bileşeni kullanır.
 */
export function PoolFlagsCard({ flags, compact = false }: { flags: PoolFlagsOut; compact?: boolean }) {
  const [open, setOpen] = React.useState(false);
  const primary = flags.primary[0] ?? null;
  const extra = flags.secondary;
  const good = flags.good;
  if (!primary && extra.length === 0 && good.length === 0) {
    return (
      <div
        className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
        data-section="pool:flags"
        data-level="green"
      >
        <CheckCircle2 className="size-4 shrink-0" aria-hidden /> {flags.headline || "Havuz yolunda"}
      </div>
    );
  }
  return (
    <div className="space-y-2" data-section="pool:flags" data-level={flags.level}>
      {primary ? (
        <FlagRow flag={primary} primary compact={compact} />
      ) : (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          <CheckCircle2 className="size-4 shrink-0" aria-hidden /> {flags.headline || "Havuz yolunda"}
        </div>
      )}
      {(extra.length > 0 || good.length > 0) && (
        <div>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground hover:text-foreground"
            aria-expanded={open}
            data-testid="pool-flags-toggle"
          >
            <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} aria-hidden />
            Ek sinyaller ({extra.length}){good.length > 0 ? ` · iyi gidenler (${good.length})` : ""}
          </button>
          {open && (
            <ul className="mt-2 space-y-2" data-section="pool:flags:extra">
              {extra.map((f) => (
                <li key={f.code}><FlagRow flag={f} compact={compact} /></li>
              ))}
              {good.map((f) => (
                <li key={f.code}><FlagRow flag={f} compact={compact} /></li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

const TONE: Record<string, { box: string; badge: string; label: string }> = {
  red: {
    box: "border-rose-200 bg-rose-50 text-rose-950",
    badge: "bg-rose-600 text-white",
    label: "Acil",
  },
  amber: {
    box: "border-amber-200 bg-amber-50 text-amber-950",
    badge: "bg-amber-500 text-amber-950",
    label: "Dikkat",
  },
  green: {
    box: "border-slate-200 bg-card text-foreground",
    badge: "bg-slate-600 text-white",
    label: "Bilgi",
  },
};

const LAYER_LABEL: Record<string, string> = {
  P: "Dönem", K: "Katılım", T: "Tempo", D: "Doğruluk", E: "Deneme", A: "Kaçınma", Z: "Desen", G: "İyi giden",
};

function FlagRow({ flag, primary = false, compact = false }: { flag: PoolFlagOut; primary?: boolean; compact?: boolean }) {
  const [more, setMore] = React.useState(primary && !compact);
  const tone = TONE[flag.level] ?? TONE.green;
  const Icon = flag.level === "red" ? OctagonAlert : flag.level === "amber" ? AlertTriangle : flag.layer === "G" ? CheckCircle2 : Info;
  const isGood = flag.layer === "G";
  return (
    <div
      className={cn("rounded-lg border px-4 py-3", isGood
        ? "border-emerald-200 bg-emerald-50 text-emerald-950"
        : tone.box)}
      data-flag={flag.code}
      data-flag-level={flag.level}
    >
      <div className="flex flex-wrap items-start gap-2">
        <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("font-semibold", primary ? "text-base" : "text-sm")}>{flag.title}</span>
            <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", isGood ? "bg-emerald-600 text-white" : tone.badge)}>
              {isGood ? "İyi" : tone.label}
            </span>
            <span className="rounded-full bg-slate-600 px-2 py-0.5 text-[11px] font-semibold text-white">
              {LAYER_LABEL[flag.layer] ?? flag.layer}
            </span>
            {flag.coach_only && (
              <span className="text-[11px] opacity-80">yalnız rehber</span>
            )}
          </div>
          <p className="mt-1 text-sm opacity-90">{flag.detail}</p>
          {flag.evidence.length > 0 && (
            <div className="mt-1">
              <button
                type="button"
                onClick={() => setMore((v) => !v)}
                className="text-xs font-semibold underline-offset-2 hover:underline"
                aria-expanded={more}
              >
                {more ? "Kanıtı gizle" : "Neden?"}
              </button>
              {more && (
                <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs" data-section="pool:flag:evidence">
                  {flag.evidence.map((e, i) => (
                    <React.Fragment key={i}>
                      <dt className="font-semibold opacity-80">{e.label}</dt>
                      <dd className="break-words">{e.value}</dd>
                    </React.Fragment>
                  ))}
                </dl>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
