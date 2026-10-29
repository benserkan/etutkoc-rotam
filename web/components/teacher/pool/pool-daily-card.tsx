"use client";

/**
 * K48/K50 — Rehber günlük görüşme listesi (havuz öğrencileri). Bugünkü seans ÜSTTE,
 * öğrenci başına 1 ana sinyal + katlanan ek sinyal, Gördüm/Ertele (pano uyarı akışı
 * ile ortak WarningState). Havuz öğrencisi yoksa HİÇ render etmez.
 */

import * as React from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck2, ChevronDown, Clock, EyeOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAckWarning, useUnackWarning } from "@/lib/hooks/use-teacher-mutations";
import { getPoolDaily, poolDailyKey, type PoolDailyRow } from "@/lib/api/pool";

const LEVEL_DOT: Record<string, string> = { red: "bg-rose-600", amber: "bg-amber-500", green: "bg-emerald-600" };
const LEVEL_LABEL: Record<string, string> = { red: "Acil", amber: "Dikkat", green: "Yolunda" };

export function PoolDailyCard() {
  const q = useQuery({ queryKey: poolDailyKey, queryFn: getPoolDaily, staleTime: 30_000 });
  const data = q.data;
  if (!data || data.counts.students === 0) return null;
  const c = data.counts;
  return (
    <section className="rounded-xl border bg-card p-4" data-section="pool:daily">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="inline-flex items-center gap-2 text-base font-semibold text-foreground">
          <CalendarCheck2 className="size-5 text-cyan-700" aria-hidden /> Bugünkü görüşme listesi · havuz öğrencileri
        </h2>
        <div className="flex flex-wrap gap-1.5 text-[11px] font-semibold">
          <span className="rounded-full bg-cyan-700 px-2 py-0.5 text-white">bugün seans {c.sessions_today}</span>
          <span className="rounded-full bg-rose-600 px-2 py-0.5 text-white">acil {c.red}</span>
          <span className="rounded-full bg-amber-500 px-2 py-0.5 text-amber-950">dikkat {c.amber}</span>
          {c.snoozed > 0 && <span className="rounded-full bg-slate-600 px-2 py-0.5 text-white">ertelenen {c.snoozed}</span>}
        </div>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Seansı bugün olanlar üstte; her öğrencide tek ana sinyal, gerisi “ek” altında. “Gördüm” 3 gün gizler; koşul sürerse geri gelir.
      </p>
      <ul className="mt-3 divide-y">
        {data.rows.map((r) => <Row key={r.student_id} r={r} />)}
      </ul>
    </section>
  );
}

function Row({ r }: { r: PoolDailyRow }) {
  const [open, setOpen] = React.useState(false);
  const qc = useQueryClient();
  const ack = useAckWarning();
  const unack = useUnackWarning();
  const refresh = () => qc.invalidateQueries({ queryKey: poolDailyKey });
  const prim = r.primary;
  return (
    <li className={cn("py-2", r.session_today && "rounded-md bg-cyan-50 px-2")} data-student={r.student_id} data-session-today={r.session_today ? "1" : "0"}>
      <div className="flex flex-wrap items-center gap-2">
        {r.session_today ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-cyan-700 px-2 py-0.5 text-[11px] font-semibold text-white">
            <Clock className="size-3" aria-hidden /> {r.appointment_time ? `bugün ${r.appointment_time}` : "seans günü"}
          </span>
        ) : (
          <span className={cn("size-2.5 shrink-0 rounded-full", LEVEL_DOT[r.level] ?? LEVEL_DOT.green)} aria-label={LEVEL_LABEL[r.level]} />
        )}
        <Link href={`/teacher/students/${r.student_id}/pool/session`} className="font-medium text-foreground hover:underline">
          {r.student_name}
        </Link>
        {r.class_group && <span className="text-xs text-muted-foreground">{r.class_group}</span>}
        {r.pct != null && <span className="text-xs text-muted-foreground">havuz %{r.pct}</span>}
        {r.paper_student && <span className="rounded-full bg-slate-600 px-2 py-0.5 text-[11px] font-semibold text-white">kağıt öğrencisi</span>}
        <span className="ml-auto flex items-center gap-1">
          {prim && !r.primary_snoozed && (
            <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs"
                    onClick={() => ack.mutate({ student_id: r.student_id, code: prim.code, snooze_days: 3 }, { onSuccess: refresh })}>
              <EyeOff className="size-3.5" aria-hidden /> Gördüm
            </Button>
          )}
          {prim && r.primary_snoozed && (
            <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs"
                    onClick={() => unack.mutate({ student_id: r.student_id, code: prim.code }, { onSuccess: refresh })}>
              Geri al
            </Button>
          )}
        </span>
      </div>
      <div className="mt-1 text-sm">
        {prim ? (
          <span className={cn(r.primary_snoozed ? "text-muted-foreground line-through" : "text-foreground")}>
            <b>{prim.title}</b> <span className="opacity-80">— {prim.detail}</span>
          </span>
        ) : (
          <span className="text-muted-foreground">{r.headline}</span>
        )}
      </div>
      {(r.extra.length > 0 || r.good.length > 0) && (
        <div className="mt-1">
          <button type="button" className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground hover:text-foreground"
                  onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} aria-hidden />
            ek {r.extra.length}{r.good.length ? ` · iyi ${r.good.length}` : ""}
          </button>
          {open && (
            <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
              {[...r.extra, ...r.good].map((f) => <li key={f.code}>• <span className="text-foreground">{f.title}</span> — {f.detail}</li>)}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}
