"use client";

/**
 * Havuz ilerleme görünümleri — seans ekranı ve editörün "İzle" modu AYNI bileşeni kullanır:
 *   • SubjectProgress: ders ders birim ilerlemesi (öğrenci kaydı / seansta işaret / kalan)
 *   • DayStrip: dönemin gün gün şeridi (her gün ders renkli dilimler + tıkla → o günün görevleri)
 * Birim kuralı backend `pool_mode._units` ile aynı: test sayısı; etkinlik 1 birim.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { SubjectTag, subjectColors } from "@/components/shared/subject-tag";
import { cn } from "@/lib/utils";
import { getPoolPeriodDetail, poolPeriodDetailKey, type PoolItemOut } from "@/lib/api/pool";

/** Backend `date.weekday()` sırası: Pazartesi = 0. */
export const DAY_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

export function fmtShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d + n);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

/** Kalemin birim kırılımı. `session_marked` yoksa (editör paketi) yapılan − öğrenci kaydı = rehber işareti. */
export function itemUnitSplit(it: PoolItemOut & { session_marked?: number }): { total: number; student: number; session: number } {
  if (it.unit === "etkinlik") {
    const done = it.remaining === 0 ? 1 : 0;
    return { total: 1, student: it.completed > 0 ? done : 0, session: it.completed > 0 ? 0 : done };
  }
  const total = it.quantity;
  const student = Math.min(it.completed, total);
  const done = Math.max(0, total - it.remaining);
  const session = it.session_marked != null ? Math.min(it.session_marked, total - student) : Math.max(0, done - student);
  return { total, student, session };
}

export interface SubjectAgg {
  name: string;
  total: number;
  student: number;
  session: number;
  items: number;
  itemsDone: number;
  avoided: number;
  homework: number;
}

type ProgressItem = PoolItemOut & { session_marked?: number; avoided?: boolean };

export function aggregateSubjects(items: ProgressItem[]): SubjectAgg[] {
  const map = new Map<string, SubjectAgg>();
  for (const it of items) {
    if (!it.counts) continue;
    const a = map.get(it.subject_name) ?? { name: it.subject_name, total: 0, student: 0, session: 0, items: 0, itemsDone: 0, avoided: 0, homework: 0 };
    const u = itemUnitSplit(it);
    a.total += u.total;
    a.student += u.student;
    a.session += u.session;
    a.items += 1;
    if (it.remaining === 0) a.itemsDone += 1;
    if (it.avoided) a.avoided += 1;
    if (it.teacher_homework) a.homework += 1;
    map.set(it.subject_name, a);
  }
  return [...map.values()].sort((x, y) => y.total - x.total);
}

export function pctOf(n: number, total: number): number {
  return total > 0 ? Math.round((100 * n) / total) : 0;
}

function pctTone(p: number): string {
  if (p >= 70) return "text-emerald-700 dark:text-emerald-300";
  if (p >= 40) return "text-amber-700 dark:text-amber-300";
  return "text-rose-700 dark:text-rose-300";
}

/** Öğrenci kaydı (dolu) + seansta işaret (açık ton) + kalan (boş) üç parçalı çubuk. */
export function SplitBar({ total, student, session, color, className }: { total: number; student: number; session: number; color: string; className?: string }) {
  const a = total > 0 ? (100 * student) / total : 0;
  const b = total > 0 ? (100 * session) / total : 0;
  return (
    <div className={cn("flex h-2.5 w-full overflow-hidden rounded-full bg-muted", className)} aria-hidden>
      <div style={{ width: `${a}%`, backgroundColor: color }} />
      <div style={{ width: `${b}%`, backgroundColor: color, opacity: 0.4 }} />
    </div>
  );
}

export function SubjectProgress({ items, title = "Derslere göre ilerleme" }: { items: ProgressItem[]; title?: string }) {
  const subjects = aggregateSubjects(items);
  if (!subjects.length) return null;
  return (
    <section className="rounded-xl border bg-card p-4" data-section="pool:subjects">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold text-foreground">{title}</h2>
        <span className="text-xs text-muted-foreground">koyu = öğrenci kaydı · açık = seansta işaretlenen · birim = test (etkinlik 1)</span>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {subjects.map((a) => {
          const c = subjectColors(a.name);
          const pct = pctOf(a.student + a.session, a.total);
          return (
            <div key={a.name} className="rounded-lg border border-l-4 bg-background p-3" style={{ borderLeftColor: c.rail }} data-subject={a.name}>
              <div className="flex items-start justify-between gap-2">
                <SubjectTag name={a.name} />
                <span className={cn("text-xl font-bold", pctTone(pct))}>%{pct}</span>
              </div>
              <SplitBar total={a.total} student={a.student} session={a.session} color={c.rail} className="mt-2" />
              <div className="mt-1.5 flex flex-wrap gap-x-2 text-xs text-muted-foreground">
                <span><b className="text-foreground">{a.student + a.session}</b>/{a.total} birim</span>
                <span>· {a.itemsDone}/{a.items} kalem bitti</span>
                {a.session > 0 && <span>· {a.session} seansta</span>}
              </div>
              {(a.avoided > 0 || a.homework > 0) && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {a.avoided > 0 && <span className="rounded-full bg-amber-700 px-2 py-0.5 text-[11px] font-semibold text-white">{a.avoided} kaçınılan</span>}
                  {a.homework > 0 && <span className="rounded-full bg-violet-700 px-2 py-0.5 text-[11px] font-semibold text-white">{a.homework} öğretmen ödevi</span>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function DayStrip({ studentId, periodId, items, today, expectedNextOn }: {
  studentId: number;
  periodId: number;
  items: PoolItemOut[];
  today: string;
  expectedNextOn: string | null;
}) {
  const detail = useQuery({
    queryKey: poolPeriodDetailKey(studentId, periodId),
    queryFn: () => getPoolPeriodDetail(studentId, periodId),
  });
  const [sel, setSel] = React.useState<string | null>(null);
  const subjOf = new Map<number, string>(items.map((i) => [i.id, i.subject_name]));
  const days = detail.data?.days ?? [];
  const max = Math.max(1, ...days.map((d) => d.done_units));
  const active = days.find((d) => d.date === sel) ?? null;
  // Beklenen seans gününe kadar kalan günler soluk yer tutucu: dönemin neresinde olunduğu bir bakışta görünür.
  const future: string[] = [];
  if (expectedNextOn && days.length) {
    let d = addDays(days[days.length - 1].date, 1);
    while (d <= expectedNextOn && future.length < 14) { future.push(d); d = addDays(d, 1); }
  }
  const worked = days.filter((d) => d.tasks.length > 0).length;
  return (
    <section className="rounded-xl border bg-card p-4" data-section="pool:days">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold text-foreground">
          Gün gün
          {days.length > 0 && <span className="ml-2 text-xs font-normal text-muted-foreground">kap kurulan gün {worked}/{days.length}</span>}
        </h2>
        <span className="text-xs text-muted-foreground">Öğrencinin her gün kaba alıp işlediği. Güne dokun → o günün görevleri.</span>
      </div>
      {detail.isLoading ? (
        <p className="mt-3 text-sm text-muted-foreground">Yükleniyor…</p>
      ) : (
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {days.map((d) => {
            const bySubj = new Map<string, number>();
            for (const t of d.tasks) {
              const n = t.item_id != null ? subjOf.get(t.item_id) ?? "Diğer" : "Diğer";
              bySubj.set(n, (bySubj.get(n) ?? 0) + (t.itemless ? (t.status === "completed" ? 1 : 0) : t.done));
            }
            const empty = d.tasks.length === 0;
            const open = d.tasks.filter((t) => t.status !== "completed").length;
            return (
              <button
                key={d.date}
                type="button"
                data-day={d.date}
                onClick={() => setSel(sel === d.date ? null : d.date)}
                className={cn(
                  "flex w-20 shrink-0 flex-col items-stretch gap-1 rounded-lg border p-2 text-left transition-colors hover:bg-accent",
                  empty && "border-dashed",
                  d.date === today && "border-cyan-600",
                  sel === d.date && "ring-2 ring-cyan-600",
                )}
                aria-pressed={sel === d.date}
              >
                <span className="text-[11px] font-semibold text-foreground">{DAY_SHORT[d.weekday]} {fmtShort(d.date)}</span>
                <div className="flex h-14 flex-col-reverse overflow-hidden rounded bg-muted">
                  {[...bySubj.entries()].map(([n, v]) => (
                    <div key={n} title={`${n}: ${v}`} style={{ height: `${(56 * v) / max}px`, backgroundColor: subjectColors(n).rail }} />
                  ))}
                </div>
                <span className="text-[11px] text-muted-foreground">{empty ? "kap boş" : `${d.done_units} birim`}</span>
                {open > 0 && <span className="text-[11px] text-amber-700 dark:text-amber-300">{open} açık</span>}
              </button>
            );
          })}
          {future.map((d) => {
            const [y, m, dd] = d.split("-").map(Number);
            const wd = (new Date(y, m - 1, dd).getDay() + 6) % 7;
            const isSession = d === expectedNextOn;
            return (
              <div key={d} className={cn("flex w-20 shrink-0 flex-col gap-1 rounded-lg border border-dashed p-2 opacity-60", isSession && "border-cyan-600 opacity-100")}>
                <span className="text-[11px] font-semibold text-muted-foreground">{DAY_SHORT[wd]} {fmtShort(d)}</span>
                <div className="h-14 rounded bg-muted/50" />
                <span className="text-[11px] text-muted-foreground">{isSession ? "seans" : "gelecek"}</span>
              </div>
            );
          })}
        </div>
      )}
      {active && (
        <div className="mt-3 rounded-lg border bg-background p-3 text-sm" data-section="pool:days:detail">
          <div className="font-medium text-foreground">{DAY_SHORT[active.weekday]} {fmtShort(active.date)}</div>
          {active.tasks.length === 0 ? (
            <p className="text-xs text-muted-foreground">Bu gün kap boş kaldı.</p>
          ) : (
            <div className="mt-1 space-y-1">
              {active.tasks.map((t) => {
                const n = t.item_id != null ? subjOf.get(t.item_id) ?? "Diğer" : "Diğer";
                const done = t.status === "completed";
                return (
                  <div key={t.task_id} className="flex flex-wrap items-center gap-2 text-xs">
                    <span className={cn("size-2 rounded-full", done ? "bg-emerald-500" : "bg-amber-400")} />
                    <SubjectTag name={n} size="xs" />
                    <span className="min-w-0 flex-1 break-words text-foreground">{t.title}</span>
                    <span className="text-muted-foreground">
                      {t.itemless ? (done ? "yapıldı" : "yapılmadı") : `${t.done}${t.planned ? `/${t.planned}` : ""} test`}
                      {t.correct != null || t.wrong != null ? ` · ${t.correct ?? 0}D ${t.wrong ?? 0}Y ${t.blank ?? 0}B` : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
