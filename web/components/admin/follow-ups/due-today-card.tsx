"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";

import { cn } from "@/lib/utils";
import { followUpKeys, getFollowUps } from "@/lib/api/follow-ups";

import { fmtDate, VerdictBadge } from "./shared";

/** Panonun üstünde: vadesi gelmiş/geçmiş takipler. Yoksa yalnız sıradaki işi söyler. */
export function FollowUpsDueCard() {
  const q = useQuery({ queryKey: followUpKeys.list("open"), queryFn: () => getFollowUps("open") });
  if (!q.data) return null;
  const due = q.data.items.filter((i) => i.bucket === "overdue" || i.bucket === "today");
  const next = q.data.items.find((i) => i.bucket === "upcoming" || i.bucket === "later");

  if (!due.length) {
    if (!next) return null;
    return (
      <Link href="/admin/follow-ups"
        className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-sm hover:bg-muted/50">
        <ClipboardCheck className="size-4 text-cyan-700" aria-hidden />
        <span className="text-slate-700">Bugün bakılacak takip yok. Sıradaki:</span>
        <span className="font-medium">{next.title}</span>
        <span className="text-slate-600">— {fmtDate(next.effective_due)}</span>
      </Link>
    );
  }

  return (
    <section className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-slate-900" data-section="admin:follow-ups-due">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="inline-flex items-center gap-2 font-semibold">
          <ClipboardCheck className="size-4 text-amber-700" aria-hidden />
          Bugün bakılacaklar · {due.length}
        </h2>
        <Link href="/admin/follow-ups" className="text-sm font-medium text-amber-900 underline">
          Takip listesini aç
        </Link>
      </div>
      <ul className="mt-2 space-y-1.5">
        {due.slice(0, 5).map((it) => (
          <li key={it.id} className="flex flex-wrap items-center gap-2 text-sm">
            <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold text-white",
              it.days_left < 0 ? "bg-rose-600" : "bg-amber-600")}>
              {it.days_left < 0 ? `${-it.days_left} gün gecikti` : "Bugün"}
            </span>
            <span className="break-words font-medium">{it.title}</span>
            {it.report ? <VerdictBadge verdict={it.report.verdict} /> : null}
          </li>
        ))}
      </ul>
      {due.length > 5 ? <p className="mt-1 text-xs text-slate-700">+{due.length - 5} iş daha</p> : null}
    </section>
  );
}
