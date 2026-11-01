"use client";

/**
 * Havuz dönemi kapanırken üretilen uyarılar (H2, 2026-11-01).
 * Bayraklar yalnız açık dönemden hesaplandığı için seans kapanınca kayboluyordu; backend
 * kapanış anında saklar. Yalnız koç yüzeylerinde (dönem geçmişi kartı + dönem penceresi) çizilir.
 */
import * as React from "react";
import { AlertTriangle, Info } from "lucide-react";

import type { PoolClosingFlag } from "@/lib/api/pool";
import { cn } from "@/lib/utils";

const TONE: Record<string, string> = {
  red: "border-rose-200 bg-rose-50 text-rose-900",
  amber: "border-amber-200 bg-amber-50 text-amber-900",
  green: "border-slate-200 bg-slate-50 text-slate-800",
};
const BADGE: Record<string, string> = {
  red: "bg-rose-700 text-white",
  amber: "bg-amber-600 text-slate-950",
  green: "bg-slate-600 text-white",
};
const LABEL: Record<string, string> = { red: "Acil", amber: "Dikkat", green: "Bilgi" };

function signal(flags: PoolClosingFlag[]) {
  return flags.filter((f) => f.layer !== "G");
}

/** Dönem kartı için kısa satır: "Kapanırken 4 uyarı · 3 gündür havuza dokunmadı". */
export function ClosingFlagsLine({ flags }: { flags: PoolClosingFlag[] | undefined }) {
  const list = signal(flags ?? []).filter((f) => f.level !== "green");
  if (list.length === 0) return null;
  const red = list.some((f) => f.level === "red");
  return (
    <span
      className={cn("mt-1.5 flex items-start gap-1 text-[11px] font-medium",
        red ? "text-rose-700" : "text-amber-800")}
      data-section="pool:history:closing-flags"
    >
      <AlertTriangle className="mt-px size-3 shrink-0" aria-hidden />
      <span className="break-words">
        Kapanırken {list.length} uyarı · {list.slice(0, 2).map((f) => f.title).join(" · ")}
        {list.length > 2 ? ` · +${list.length - 2}` : ""}
      </span>
    </span>
  );
}

/** Dönem penceresi için tam liste (kanıtlı). */
export function ClosingFlagsPanel({ flags }: { flags: PoolClosingFlag[] | undefined }) {
  const list = signal(flags ?? []);
  if (list.length === 0) return null;
  return (
    <section className="space-y-1.5" data-section="pool:period-dialog:closing-flags">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Dönem kapanırken uyarılar
      </h3>
      <ul className="space-y-1.5">
        {list.map((f) => (
          <li key={f.code} className={cn("rounded-md border px-3 py-2 text-sm", TONE[f.level] ?? TONE.green)}>
            <details>
              <summary className="flex cursor-pointer list-none items-start gap-2">
                {f.level === "green" ? <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
                  : <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />}
                <span className="min-w-0 flex-1">
                  <span className="font-semibold break-words">{f.title}</span>
                  {f.detail ? <span className="block text-xs opacity-90 break-words">{f.detail}</span> : null}
                </span>
                <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold", BADGE[f.level] ?? BADGE.green)}>
                  {LABEL[f.level] ?? f.level}
                </span>
              </summary>
              {f.evidence.length > 0 && (
                <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 pl-6 text-xs">
                  {f.evidence.map(([k, v], i) => (
                    <React.Fragment key={i}>
                      <dt className="font-medium break-words">{k}</dt>
                      <dd className="break-words">{v}</dd>
                    </React.Fragment>
                  ))}
                </dl>
              )}
            </details>
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-muted-foreground">
        Kapanış günündeki değerlendirme; yeni dönem açılınca canlı uyarılardan düştüğü için burada saklanır.
      </p>
    </section>
  );
}
