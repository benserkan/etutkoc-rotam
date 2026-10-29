"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Layers, PackageOpen } from "lucide-react";

import { getStudentPool, studentPoolKey } from "@/lib/api/pool-student";
import { cn } from "@/lib/utils";

/**
 * Bugün sayfasının EN ÜSTÜNDEKİ havuz kartı — yalnız haftalık havuz modundaki öğrencide.
 *
 * Havuz öğrencisinin asıl çalışma yeri havuzdur; kart tarih gezgini / yazdır / görev iste
 * düğmelerinden ÖNCE gelir ve dolgulu, büyük bir giriş olarak tasarlanmıştır (2026-10-13 saha:
 * öğrenci soluk bir satır olan eski kartı görmeyip "havuz nerede" diye aradı).
 * Kartın tamamı tek bağlantıdır (iç içe link yok).
 */
export function PoolBanner() {
  const q = useQuery({ queryKey: studentPoolKey, queryFn: getStudentPool, staleTime: 30_000 });
  const d = q.data;
  if (!d || d.mode !== "havuz") return null;
  const s = d.summary;
  // Kap durumu: boş (hiç kalem alınmadı) ≠ bitti (alınanların hepsi tamam). Yalnız açık kaleme bakmak
  // "hepsini bitirdim" durumunu "kap boş" sanıyordu (2026-10-13 saha).
  const cupTotal = d.cup.length;
  const openCup = d.cup.filter((c) => c.status !== "completed").length;
  const cupDone = cupTotal - openCup;
  const leftItems = d.items.filter((i) => i.counts && i.remaining > 0).length;
  const cupEmpty = !!s && cupTotal === 0;
  const cupAllDone = !!s && cupTotal > 0 && openCup === 0;

  return (
    <Link
      href="/student/pool"
      data-section="student:pool-banner"
      className="group block overflow-hidden rounded-xl bg-gradient-to-br from-cyan-700 to-cyan-900 text-white shadow-md ring-1 ring-cyan-900/20 transition hover:shadow-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-cyan-500/50"
    >
      <div className="flex flex-wrap items-center gap-4 p-4 sm:p-5">
        <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-white/15" aria-hidden>
          <Layers className="size-6" />
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          <div>
            <div className="text-lg font-semibold leading-tight">Haftanın havuzu</div>
            <div className="text-sm text-cyan-50">
              {s
                ? "Bu haftanın görevleri burada — bugün çalışacaklarını havuzdan kabına al."
                : d.on_break
                  ? "Ara (tatil) — yeni dönem açılınca havuzun burada olacak."
                  : "Rehberin haftanın havuzunu seansta yazacak."}
            </div>
          </div>
          {s && (
            <>
              <div className="flex items-center gap-2">
                <span className="h-2 w-full max-w-xs overflow-hidden rounded-full bg-white/20" aria-hidden>
                  <span className="block h-full rounded-full bg-white" style={{ width: `${Math.min(100, s.pct)}%` }} />
                </span>
                <span className="shrink-0 text-sm font-semibold">%{s.pct} bitti</span>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs font-medium">
                <span className="rounded-full bg-white/15 px-2.5 py-1">seansa {s.days_left} gün</span>
                <span className="rounded-full bg-white/15 px-2.5 py-1">
                  {cupTotal === 0 ? "bugün kabın boş" : `bugün kabında ${cupTotal} kalem · ${cupDone} bitti`}
                </span>
                <span className="rounded-full bg-white/15 px-2.5 py-1">havuzda {leftItems} kalem bekliyor</span>
              </div>
            </>
          )}
        </div>
        <span className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-cyan-900 transition group-hover:gap-3">
          Havuzu aç <ArrowRight className="size-4" aria-hidden />
        </span>
      </div>
      {cupEmpty && (
        <div className={cn("flex items-center gap-2 bg-amber-400 px-4 py-2 text-sm font-semibold text-amber-950 sm:px-5")}>
          <PackageOpen className="size-4 shrink-0" aria-hidden />
          Bugünün kabı boş — havuzdan bugün çalışacaklarını seç.
        </div>
      )}
      {cupAllDone && (
        <div className="flex items-center gap-2 bg-emerald-700 px-4 py-2 text-sm font-semibold text-white sm:px-5">
          <CheckCircle2 className="size-4 shrink-0" aria-hidden />
          Bugünün kabındaki {cupTotal} kalemi bitirdin — istersen havuzdan bir kalem daha alabilirsin.
        </div>
      )}
    </Link>
  );
}
