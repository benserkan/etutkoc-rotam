"use client";

/**
 * K52 — Veli: haftalık havuz + bugünün kabı SALT OKUMA (uyarı yok). Yalnız çocuk havuz
 * modundaysa render olur; gün gün programdaki çocukta hiç görünmez.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Layers } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { PoolPeriodDialog } from "@/components/shared/pool-period-dialog";
import { getParentPoolPeriod, getParentStudentPool, parentKeys } from "@/lib/api/parent";

function fmt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function ParentPoolCard({ studentId }: { studentId: number }) {
  const q = useQuery({ queryKey: parentKeys.studentPool(studentId), queryFn: () => getParentStudentPool(studentId), staleTime: 60_000 });
  const d = q.data;
  if (!d || d.mode !== "havuz") return null;
  if (!d.period_id || !d.summary) {
    return (
      <Card data-section="parent:pool">
        <CardContent className="p-4 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-2 font-semibold text-foreground"><Layers className="size-4" aria-hidden /> Haftalık görev havuzu</span>
          <p className="mt-1">{d.on_break ? `Ara (tatil) — ${fmt(d.on_break.since)} tarihinden beri; yeni dönem açılınca havuz burada görünür.` : "Rehber yeni dönemin havuzunu seansta yazınca burada görünür."}</p>
          <PreviousPeriods studentId={studentId} previous={d.previous} />
        </CardContent>
      </Card>
    );
  }
  const s = d.summary;
  const groups = new Map<string, typeof d.items>();
  for (const it of d.items) {
    const g = groups.get(it.subject_name) ?? [];
    g.push(it);
    groups.set(it.subject_name, g);
  }
  return (
    <Card data-section="parent:pool">
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="inline-flex items-center gap-2 font-semibold text-foreground"><Layers className="size-4" aria-hidden /> Haftalık görev havuzu</h2>
          <span className="text-xs text-muted-foreground">dönem {fmt(d.opened_on)} → {d.expected_next_on ? `beklenen seans ${fmt(d.expected_next_on)}` : "seans günü belirsiz"}</span>
        </div>
        <div className="rounded-lg bg-cyan-700 p-4 text-white">
          <div className="flex items-end justify-between">
            <div className="text-2xl font-extrabold">{s.done_units}<span className="text-base font-semibold text-cyan-100">/{s.total_units} birim</span></div>
            <div className="text-xl font-bold">%{s.pct}</div>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/25"><div className="h-full rounded-full bg-white" style={{ width: `${Math.min(100, s.pct)}%` }} /></div>
          <div className="mt-1 text-xs text-cyan-100">{s.items_done}/{s.items_total} kalem · seansa {s.days_left} gün · birim = test sayısı (video/deneme 1)</div>
        </div>
        <p className="text-xs text-muted-foreground">
          Rehber seansta haftanın havuzunu yazar; {"çocuğunuz"} her gün havuzdan kabını kendisi kurar. Bu görünüm bilgi amaçlıdır; uyarı üretmez.
        </p>
        <div data-section="parent:pool:cup">
          <h3 className="text-sm font-semibold text-foreground">Bugünün kabı</h3>
          {d.cup.length === 0 ? (
            <p className="text-sm text-muted-foreground">Bugün henüz havuzdan kalem alınmadı.</p>
          ) : (
            <ul className="mt-1 space-y-1 text-sm">
              {d.cup.map((t, i) => (
                <li key={i} className={cn("flex items-center gap-2", t.status === "completed" ? "text-emerald-800" : "text-foreground")}>
                  <span className={cn("size-2 rounded-full", t.status === "completed" ? "bg-emerald-600" : "bg-slate-400")} aria-hidden />
                  {t.title}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div data-section="parent:pool:items">
          <h3 className="text-sm font-semibold text-foreground">Havuz</h3>
          <div className="mt-1 space-y-2">
            {[...groups.entries()].map(([name, list]) => (
              <div key={name}>
                <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{name}</div>
                <ul className="space-y-0.5 text-sm">
                  {list.map((it) => (
                    <li key={it.id} className="flex flex-wrap items-center gap-2">
                      <span className={cn(it.remaining === 0 ? "text-muted-foreground line-through" : "text-foreground", it.teacher_homework && "italic")}>{it.title}</span>
                      <span className="text-xs text-muted-foreground">{it.done}/{it.quantity} {it.unit}</span>
                      {it.in_cup_today && <span className="rounded-full bg-cyan-700 px-2 py-0.5 text-[11px] font-semibold text-white">bugün kapta</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <PreviousPeriods studentId={studentId} previous={d.previous} />
      </CardContent>
    </Card>
  );
}

/** K52/K60: önceki dönemler — dokununca kalem kalem + gün gün pencere (salt okuma, uyarı yok). */
function PreviousPeriods({ studentId, previous }: { studentId: number; previous: { id: number; opened_on: string; pct: number }[] }) {
  const [openId, setOpenId] = React.useState<number | null>(null);
  if (previous.length === 0) return null;
  return (
    <div className="mt-2 text-xs text-muted-foreground" data-section="parent:pool:previous">
      <span>Önceki dönemler: </span>
      <span className="inline-flex flex-wrap gap-1 align-middle">
        {previous.map((p) => (
          <button key={p.id} type="button" onClick={() => setOpenId(p.id)}
                  className="rounded-full border px-2 py-0.5 text-foreground hover:bg-muted"
                  data-testid={`parent-pool-period-${p.id}`}>
            {fmt(p.opened_on)} %{p.pct}
          </button>
        ))}
      </span>
      <PoolPeriodDialog open={openId != null} onOpenChange={(v) => { if (!v) setOpenId(null); }}
                        queryKey={parentKeys.studentPoolPeriod(studentId, openId ?? 0)}
                        queryFn={() => getParentPoolPeriod(studentId, openId!)} />
    </div>
  );
}
