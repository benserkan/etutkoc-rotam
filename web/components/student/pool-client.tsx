"use client";

/**
 * Havuzum — öğrenci web (dershane modu, K34–K41; mobil `student-pool.tsx` ile aynı akış).
 * Öğrenci bugünün kabını havuzdan kendisi kurar; kap = Bugün sayfasındaki görev. Yapılmayan
 * kalem gece havuza döner. Rehber yeni havuzu seansta yazar.
 *
 * Tasarım (2026-10-13): ders renkleri ortak `subjectColors` (koç ekranıyla aynı) · ders bazında ilerleme
 * çubukları · kapta her görevin dersi · belirgin "Bugün sayfasında işaretle" · haftalık dağılım koç
 * önizlemesiyle aynı (şube ders programına göre, sunucu hesaplar) · modern "Kalem ekle" penceresi.
 */
import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight, CalendarCheck2, CalendarRange, Check, ChevronRight, Minus, Plus, Sparkles, Undo2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { subjectColors } from "@/components/shared/subject-tag";
import { cn } from "@/lib/utils";
import { PoolPeriodDialog } from "@/components/shared/pool-period-dialog";
import {
  getStudentPool, getStudentPoolPeriod, studentPoolKey, studentPoolPeriodKey, UNIT_LABELS,
  useAddStudentPoolItem, useCupAdd, useCupReturn,
  type PoolUnit, type StudentCupTask, type StudentPoolItem, type StudentPoolResponse,
} from "@/lib/api/pool-student";

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", weekday: "short" });
}

function itemUnits(it: StudentPoolItem): number {
  return it.unit === "etkinlik" ? 1 : it.quantity;
}

/** Dolgulu ders etiketi — koç ekranıyla aynı renk (beyaz yazı). */
function SubjectPill({ name, size = "sm" }: { name: string; size?: "sm" | "xs" }) {
  return (
    <span className={cn("inline-flex shrink-0 items-center rounded-md font-semibold text-white",
      size === "xs" ? "px-1.5 py-px text-[10px]" : "px-2 py-0.5 text-xs")}
          style={{ backgroundColor: subjectColors(name).chipStrong }}>
      {name}
    </span>
  );
}

function Bar({ pct, color, className }: { pct: number; color?: string; className?: string }) {
  return (
    <span className={cn("block h-1.5 overflow-hidden rounded-full bg-muted", className)} aria-hidden>
      <span className="block h-full rounded-full" style={{ width: `${Math.min(100, Math.max(0, pct))}%`, backgroundColor: color ?? "rgb(16 185 129)" }} />
    </span>
  );
}

export function PoolClient({ initial, openAdd = false }: { initial: StudentPoolResponse; openAdd?: boolean }) {
  const q = useQuery({ queryKey: studentPoolKey, queryFn: getStudentPool, initialData: initial });
  const data = q.data ?? initial;
  const [pick, setPick] = React.useState<StudentPoolItem | null>(null);
  const [addOpen, setAddOpen] = React.useState(openAdd);
  const router = useRouter();
  const cupAdd = useCupAdd();

  if (data.mode !== "havuz") {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        Haftalık havuz modu kapalı. Programın gün gün hazırlanıyor; <Link href="/student/day" className="underline">Bugün</Link> sayfasına dön.
      </div>
    );
  }
  if (!data.period_id || !data.summary) {
    return (
      <div className="space-y-3" data-section="student:pool:empty">
        <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          {data.on_break
            ? `Ara (tatil) — ${fmtDate(data.on_break.since)} tarihinden beri. Hatırlatma gelmez; rehberin yeni dönemi açınca havuzun burada görünür.`
            : "Havuz henüz yazılmadı. Rehberin seansta haftanın havuzunu yazınca burada görünür."}
        </div>
        <PreviousPeriods data={data} />
      </div>
    );
  }
  const s = data.summary;
  const suggested = data.items.filter((i) => i.suggested);
  const groups = new Map<string, StudentPoolItem[]>();
  for (const it of data.items) {
    const g = groups.get(it.subject_name) ?? [];
    g.push(it);
    groups.set(it.subject_name, g);
  }
  function onPick(it: StudentPoolItem) {
    if (it.unit === "etkinlik" || it.remaining === 1) cupAdd.mutate({ item_id: it.id });
    else setPick(it);
  }

  return (
    <div className="space-y-5" data-section="student:pool">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-foreground">Havuzum</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Bugün yapacaklarını havuzdan kabına al; işaretlemeyi Bugün sayfasında yaparsın. Yapmadığın kalem gece havuza döner.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <Link href="/student/day"><CalendarCheck2 className="size-4" aria-hidden /> Bugün sayfası</Link>
          </Button>
          <Button onClick={() => setAddOpen(true)} className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white">
            <Plus className="size-4" aria-hidden /> Kalem ekle
          </Button>
        </div>
      </header>

      {/* Özet (K41) */}
      <div className="rounded-xl bg-gradient-to-br from-cyan-700 to-cyan-900 p-5 text-white shadow-md" data-section="student:pool:summary">
        <div className="text-xs font-semibold uppercase tracking-wider text-cyan-100">Bu haftanın havuzu</div>
        <div className="mt-2 flex items-end justify-between gap-3">
          <div className="text-3xl font-extrabold">{s.done_units}<span className="text-lg font-semibold text-cyan-100">/{s.total_units} birim</span></div>
          <div className="text-2xl font-bold">%{s.pct}</div>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/25">
          <div className="h-full rounded-full bg-white dark:bg-white" style={{ width: `${Math.min(100, s.pct)}%` }} />
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5 text-xs font-medium">
          <span className="rounded-full bg-white/15 px-2.5 py-1">{s.items_done}/{s.items_total} kalem bitti</span>
          <span className="rounded-full bg-white/15 px-2.5 py-1">seansa {s.days_left} gün{s.expected_next_on ? ` · ${fmtDate(s.expected_next_on)}` : ""}</span>
          <span className="rounded-full bg-white/15 px-2.5 py-1">günde ~{Math.max(1, Math.round(s.per_day_needed))} birim</span>
        </div>
        {/* "Tempo biraz geride" ipucu aynı cümleyi zaten söylüyor — tekrar etme */}
        {!(s.pace === "geride" && data.hints.some((h) => h.code === "pool_behind")) ? (
          <div className={cn("mt-2 text-sm font-medium", s.pace === "geride" ? "text-amber-100" : "text-cyan-50")}>{s.pace_note}</div>
        ) : null}
      </div>

      {/* K41/K46/K48: yönlendirme — kırmızı yok, yargı yok */}
      {data.hints.length > 0 && (
        <ul className="space-y-2" data-section="student:pool:hints">
          {data.hints.map((h) => (
            <li key={h.code} className="flex gap-2 rounded-lg border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm text-cyan-950 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-100">
              <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span><span className="font-semibold">{h.title}.</span> <span className="opacity-90">{h.note}</span></span>
            </li>
          ))}
        </ul>
      )}

      {data.lesson_today.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground" data-section="student:pool:lesson-today">
          <span className="font-medium text-foreground">Bugün dershanede:</span>
          {data.lesson_today.map((n) => <SubjectPill key={n} name={n} size="xs" />)}
        </div>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="space-y-4">
          <CupCard cup={data.cup} />

          {suggested.length > 0 && (
            <section className="rounded-xl border border-cyan-200 bg-cyan-50 p-4 dark:border-cyan-500/30 dark:bg-cyan-500/10" data-section="student:pool:suggest">
              <h2 className="text-sm font-semibold text-cyan-900 dark:text-cyan-100">Bugün için öneri</h2>
              <p className="text-xs text-cyan-800 dark:text-cyan-200">Günü belli olan ya da bugün dershanede işlenen dersin kalemleri önce.</p>
              <ul className="mt-2 space-y-1.5">
                {suggested.map((it) => <ItemRow key={it.id} it={it} onPick={onPick} busy={cupAdd.isPending} showSubject />)}
              </ul>
            </section>
          )}

          <Distribution data={data} />
        </div>

        <div className="space-y-4">
          <SubjectProgress data={data} />
          <section className="space-y-4 rounded-xl border bg-card p-4 shadow-sm" data-section="student:pool:list">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-semibold text-foreground">Havuzdaki kalemler</h2>
              <span className="text-xs text-muted-foreground">Kaba al → Bugün sayfasında görev olur</span>
            </div>
            {[...groups.entries()].map(([name, list]) => {
              const tot = list.filter((i) => i.counts).reduce((a, i) => a + itemUnits(i), 0);
              const dn = list.filter((i) => i.counts).reduce((a, i) => a + Math.min(i.done, itemUnits(i)), 0);
              const c = subjectColors(name);
              return (
                <div key={name} data-pool-subject={name}>
                  <div className="mb-1.5 flex flex-wrap items-center gap-2">
                    <SubjectPill name={name} />
                    <span className="text-xs text-muted-foreground">{dn}/{tot} birim</span>
                    <Bar pct={tot ? (100 * dn) / tot : 0} color={c.rail} className="w-24" />
                  </div>
                  <ul className="space-y-1.5">
                    {list.map((it) => <ItemRow key={it.id} it={it} onPick={onPick} busy={cupAdd.isPending} />)}
                  </ul>
                </div>
              );
            })}
          </section>
        </div>
      </div>

      <PreviousPeriods data={data} />

      {pick && (
        <CountDialog item={pick} onClose={() => setPick(null)}
                     cupUnits={data.cup.filter((c) => c.status !== "completed").reduce((a, c) => a + Math.max(0, c.planned - c.completed), 0)}
                     perDay={data.summary?.per_day_needed ?? 0}
                     onPick={(n) => cupAdd.mutate({ item_id: pick.id, count: n }, { onSuccess: () => setPick(null) })} busy={cupAdd.isPending} />
      )}
      <AddDialog open={addOpen} data={data}
                 onOpenChange={(v) => {
                   setAddOpen(v);
                   // Bugün'den "?ekle=1" ile gelindiyse kapanınca adresi temizle (yenilemede yeniden açılmasın)
                   if (!v && openAdd) router.replace("/student/pool", { scroll: false });
                 }} />
    </div>
  );
}

// ---------------------------------------------------------------- bugünün kabı

function CupCard({ cup }: { cup: StudentCupTask[] }) {
  const done = cup.filter((c) => c.status === "completed").length;
  return (
    <section className="rounded-xl border bg-card shadow-sm" data-section="student:pool:cup">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
        <h2 className="font-semibold text-foreground">Bugünün kabı</h2>
        {cup.length > 0 && (
          <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-semibold",
            done === cup.length ? "bg-emerald-700 text-white" : "bg-muted text-foreground")}>
            {cup.length} kalem · {done} bitti
          </span>
        )}
      </div>
      <div className="space-y-3 p-4">
        {cup.length === 0 ? (
          <p className="text-sm text-muted-foreground">Kabın boş. Sağdan bugün yapacağın kalemleri seç.</p>
        ) : (
          <ul className="space-y-1.5">
            {cup.map((c) => <CupRow key={c.task_id} c={c} />)}
          </ul>
        )}
        <Link href="/student/day"
              className="flex items-center justify-center gap-2 rounded-lg bg-cyan-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-800">
          <CalendarCheck2 className="size-4" aria-hidden /> Bugün sayfasında işaretle <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>
    </section>
  );
}

function CupRow({ c }: { c: StudentCupTask }) {
  const ret = useCupReturn();
  const done = c.status === "completed";
  const pct = c.planned ? (100 * c.completed) / c.planned : done ? 100 : 0;
  const color = c.subject_name ? subjectColors(c.subject_name).rail : undefined;
  return (
    <li className="rounded-lg border border-l-4 bg-background px-3 py-2 text-sm" style={color ? { borderLeftColor: color } : undefined}>
      <div className="flex items-start gap-2">
        <span className={cn("mt-0.5", done ? "text-emerald-700 dark:text-emerald-300" : "text-muted-foreground")}>
          {done ? <Check className="size-4" aria-hidden /> : <span className="inline-block size-4 rounded-full border-2" />}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          {c.subject_name && <SubjectPill name={c.subject_name} size="xs" />}
          <div className={cn("break-words text-foreground", done && "text-muted-foreground line-through decoration-muted-foreground/50")}>{c.title}</div>
          {c.planned > 0 && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Bar pct={pct} color={done ? undefined : color} className="w-24" />
              <span className="tabular-nums">{c.completed}/{c.planned}</span>
            </div>
          )}
        </div>
        {c.can_return && (
          <button type="button" onClick={() => ret.mutate({ task_id: c.task_id })} disabled={ret.isPending}
                  className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground" title="Havuza geri al" aria-label="Havuza geri al">
            <Undo2 className="size-4" aria-hidden />
          </button>
        )}
      </div>
    </li>
  );
}

// ---------------------------------------------------------------- havuz listesi

function ItemRow({ it, onPick, busy, showSubject = false }: {
  it: StudentPoolItem; onPick: (it: StudentPoolItem) => void; busy: boolean; showSubject?: boolean;
}) {
  const done = it.remaining === 0;
  const pending = it.source === "ogrenci" && it.approval === "bekliyor";
  const c = subjectColors(it.subject_name);
  const total = itemUnits(it);
  const pct = total ? (100 * Math.min(it.done, total)) / total : 0;
  return (
    <li className={cn("flex items-center gap-3 rounded-lg border border-l-4 bg-background px-3 py-2.5 text-sm transition hover:shadow-sm",
      done && "opacity-80")} style={{ borderLeftColor: c.rail }}>
      <div className="min-w-0 flex-1 space-y-1">
        {showSubject && <SubjectPill name={it.subject_name} size="xs" />}
        <div className={cn("break-words font-medium text-foreground", it.teacher_homework && "italic")}>{it.title}</div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span className="rounded bg-muted px-1.5 py-0.5 font-semibold text-foreground">{it.quantity} {UNIT_LABELS[it.unit]}</span>
          <span>{done ? "bitti" : `${it.remaining} kaldı`}{it.done > 0 && !done ? ` · ${it.done} yapıldı` : ""}</span>
          {it.day_hint ? <span>· {fmtDate(it.day_hint)}</span> : null}
          {it.teacher_homework ? <span className="rounded bg-violet-700 px-1.5 py-0.5 font-semibold text-white">ders öğretmeni ödevi</span> : null}
          {pending ? <span className="rounded bg-amber-400 px-1.5 py-0.5 font-semibold text-amber-950">onay bekliyor</span> : null}
        </div>
        {it.done > 0 && <Bar pct={pct} color={c.rail} className="max-w-xs" />}
      </div>
      {done ? (
        <span className="grid size-8 place-items-center rounded-full bg-emerald-700 text-white" aria-label="bitti">
          <Check className="size-4" aria-hidden />
        </span>
      ) : it.in_cup_today ? (
        <span className="rounded-full bg-cyan-700 px-2.5 py-1 text-xs font-semibold text-white">kapta</span>
      ) : (
        <Button size="sm" onClick={() => onPick(it)} disabled={busy}
                className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white">Kaba al</Button>
      )}
    </li>
  );
}

/** Derslere göre ilerleme — renkli çubuklar (sayılan kalemler, K42 birimi). */
function SubjectProgress({ data }: { data: StudentPoolResponse }) {
  const rows = new Map<string, { done: number; total: number }>();
  for (const it of data.items) {
    if (!it.counts) continue;
    const r = rows.get(it.subject_name) ?? { done: 0, total: 0 };
    r.total += itemUnits(it);
    r.done += Math.min(it.done, itemUnits(it));
    rows.set(it.subject_name, r);
  }
  if (rows.size === 0) return null;
  return (
    <section className="rounded-xl border bg-card p-4 shadow-sm" data-section="student:pool:subjects">
      <h2 className="mb-2 font-semibold text-foreground">Derslere göre</h2>
      <ul className="space-y-2">
        {[...rows.entries()].sort((a, b) => b[1].total - a[1].total).map(([name, r]) => {
          const c = subjectColors(name);
          const pct = r.total ? Math.round((100 * r.done) / r.total) : 0;
          return (
            <li key={name} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 text-sm">
              <span className="flex min-w-0 items-center gap-2">
                <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: c.rail }} aria-hidden />
                <span className="break-words text-foreground">{name}</span>
              </span>
              <span className="text-xs tabular-nums text-muted-foreground">{r.done}/{r.total} · %{pct}</span>
              <span className="col-span-2 block h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
                <span className="block h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: c.rail }} />
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------- haftaya dağılım (koç önizlemesiyle aynı)

function Distribution({ data }: { data: StudentPoolResponse }) {
  const [open, setOpen] = React.useState(false);
  const dow = (iso: string) => {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { weekday: "long" });
  };
  return (
    <section className="rounded-xl border bg-card text-sm shadow-sm" data-section="student:pool:projection">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
              className="flex w-full items-center gap-3 px-4 py-3 text-left">
        <CalendarRange className="size-4 text-muted-foreground" aria-hidden />
        <span className="flex-1 font-medium text-foreground">Haftaya nasıl dağılır? (öneri, zorunlu değil)</span>
        {data.lesson_days_set && <span className="rounded-full bg-violet-700 px-2 py-0.5 text-[11px] font-semibold text-white">ders programına göre</span>}
        <ChevronRight className={cn("size-4 text-muted-foreground transition", open && "rotate-90")} aria-hidden />
      </button>
      {open && (
        <div className="space-y-3 border-t px-4 py-3">
          <p className="text-xs text-muted-foreground">
            {data.lesson_days_set
              ? "Her dersin kalanı önce o dersin dershanede işlendiği güne yerleşti, kalanı en boş güne. Kabını sen kurarsın; bu yalnız yol gösterir."
              : "Kalanın günlere eşit bölünmüş hâli. Kabını sen kurarsın; bu yalnız yol gösterir."}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {data.projection.map((p) => (
              <div key={p.date} className={cn("rounded-lg border bg-background p-2.5", p.date === data.today && "border-cyan-700")}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium text-foreground">{fmtDate(p.date).replace(/\s\S+$/, "")} · {dow(p.date)}{p.date === data.today ? " · bugün" : ""}</span>
                  <span className="font-semibold tabular-nums text-foreground">~{p.units} birim</span>
                </div>
                {p.lessons && p.lessons.length > 0 && (
                  <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
                    <span>Dershanede:</span>
                    {p.lessons.map((n) => <SubjectPill key={n} name={n} size="xs" />)}
                  </div>
                )}
                {p.subjects && p.subjects.length > 0 ? (
                  <ul className="mt-1.5 space-y-0.5">
                    {p.subjects.map((x) => (
                      <li key={x.name} className="flex items-center gap-1.5 text-xs">
                        <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: subjectColors(x.name).rail }} aria-hidden />
                        <span className="min-w-0 flex-1 break-words text-foreground">{x.name}</span>
                        <span className="tabular-nums text-muted-foreground">{x.units}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-xs text-muted-foreground">boş gün</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

/** K60/K41: önceki dönemler — dokununca kalem kalem + gün gün pencere (salt okuma, yargı yok). */
function PreviousPeriods({ data }: { data: StudentPoolResponse }) {
  const [openId, setOpenId] = React.useState<number | null>(null);
  if (data.previous.length === 0) return null;
  return (
    <div className="text-xs text-muted-foreground" data-section="student:pool:previous">
      <span>Önceki dönemlerin: </span>
      <span className="inline-flex flex-wrap gap-1 align-middle">
        {data.previous.map((p) => (
          <button key={p.id} type="button" onClick={() => setOpenId(p.id)}
                  className="rounded-full border px-2 py-0.5 text-foreground hover:bg-muted"
                  data-testid={`student-pool-period-${p.id}`}>
            {fmtDate(p.opened_on)} %{p.pct}
          </button>
        ))}
      </span>
      <PoolPeriodDialog open={openId != null} onOpenChange={(v) => { if (!v) setOpenId(null); }}
                        queryKey={studentPoolPeriodKey(openId ?? 0)} queryFn={() => getStudentPoolPeriod(openId!)} />
    </div>
  );
}

// ---------------------------------------------------------------- kaba al: kaç tane?

/** Bugün kabında bundan fazlası "gerçekçi mi?" sorusunu açar (engel değil): günde gerekenin 2 katı, en az 10. */
function cupLimit(perDay: number): number {
  return Math.max(10, Math.ceil(perDay * 2));
}

function CountDialog({ item, onClose, onPick, busy, cupUnits, perDay }: {
  item: StudentPoolItem; onClose: () => void; onPick: (n: number) => void; busy: boolean; cupUnits: number; perDay: number;
}) {
  const opts = Array.from({ length: Math.min(item.remaining, 8) }, (_, i) => i + 1);
  const [confirmN, setConfirmN] = React.useState<number | null>(null);
  const limit = cupLimit(perDay);
  const counts = item.unit !== "etkinlik";
  function choose(n: number) {
    if (counts && cupUnits + n > limit) setConfirmN(n);
    else onPick(n);
  }
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Bugün kaç tane?</DialogTitle>
          <DialogDescription>
            {item.title} · kalan {item.remaining} {UNIT_LABELS[item.unit]}
            {cupUnits > 0 ? ` · kabında şu an ${cupUnits} birim var` : ""}
          </DialogDescription>
        </DialogHeader>
        {confirmN == null ? (
          <div className="flex flex-wrap gap-2">
            {opts.map((n) => (
              <button key={n} type="button" onClick={() => choose(n)} disabled={busy}
                      className="size-11 rounded-full border text-base font-semibold text-foreground hover:bg-accent">{n}</button>
            ))}
            {item.remaining > 8 && (
              <button type="button" onClick={() => choose(item.remaining)} disabled={busy}
                      className="h-11 rounded-full border px-4 text-base font-semibold text-foreground hover:bg-accent">hepsi ({item.remaining})</button>
            )}
          </div>
        ) : (
          <div className="space-y-3 rounded-lg bg-amber-400 p-3 text-sm text-amber-950" data-section="student:pool:cup-heavy">
            <p className="font-semibold">Bugün {cupUnits + confirmN} {UNIT_LABELS[item.unit]} — gerçekten çözecek misin?</p>
            <p className="text-xs">
              Kabında {cupUnits} birim var, {confirmN} daha eklersen {cupUnits + confirmN} olur. Havuzu bitirmek için günde
              yaklaşık {Math.max(1, Math.round(perDay))} birim yeter. Kaba almak çözmek değildir: yapmadığın kısım gün sonunda havuza
              döner; “yaptım” dediklerini rehberin seansta kitabından birlikte kontrol eder.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" className="border-amber-950/40 bg-white text-amber-950 hover:bg-amber-50 dark:bg-white dark:text-amber-950 dark:hover:bg-amber-100"
                      onClick={() => setConfirmN(null)}>Daha az seç</Button>
              <Button size="sm" className="bg-amber-950 text-white hover:bg-amber-900 hover:text-white" disabled={busy}
                      onClick={() => onPick(confirmN)}>Evet, {confirmN} al</Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------- kalem ekle (K38)

const QUICK_QTY = [1, 2, 3, 5, 10];

function AddDialog({ open, onOpenChange, data }: { open: boolean; onOpenChange: (v: boolean) => void; data: StudentPoolResponse }) {
  const add = useAddStudentPoolItem();
  const [subjectId, setSubjectId] = React.useState<number | null>(null);
  const [label, setLabel] = React.useState("");
  const [qty, setQty] = React.useState("");
  const [unit, setUnit] = React.useState<PoolUnit>("test");
  const [homework, setHomework] = React.useState(false);
  const n = Number(qty);
  const isActivity = unit === "etkinlik";
  const ok = subjectId != null && label.trim().length > 0 && (isActivity || (Number.isInteger(n) && n > 0));
  const subj = data.subjects.find((x) => x.id === subjectId) ?? null;
  const groups: Array<[string, typeof data.subjects]> = [];
  const okul = data.subjects.filter((x) => x.group !== "sinav");
  const tyt = data.subjects.filter((x) => x.group === "sinav" && !x.is_ayt);
  const ayt = data.subjects.filter((x) => x.group === "sinav" && x.is_ayt);
  if (okul.length) groups.push(["Okul dersleri", okul]);
  if (tyt.length) groups.push(["TYT", tyt]);
  if (ayt.length) groups.push(["AYT", ayt]);
  function reset() { setLabel(""); setQty(""); setHomework(false); }
  function step(delta: number) {
    const cur = Number.isInteger(n) && n > 0 ? n : 0;
    setQty(String(Math.max(1, cur + delta)));
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Havuza kalem ekle</DialogTitle>
          <DialogDescription>Ders öğretmeninin verdiği ödev ya da kendi ek çalışman. Rehberin seansta onaylayınca yüzdeye girer.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-sm">
          <section className="space-y-2">
            <StepTitle n={1} title="Hangi ders?" />
            {groups.map(([title, list]) => (
              <div key={title}>
                {groups.length > 1 && <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>}
                <div className="flex flex-wrap gap-1.5">
                  {list.map((x) => {
                    const c = subjectColors(x.name);
                    const on = subjectId === x.id;
                    return (
                      <button key={x.id} type="button" onClick={() => setSubjectId(x.id)} aria-pressed={on}
                              className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition",
                                on ? "border-transparent text-white shadow-sm" : "bg-background text-foreground hover:bg-muted")}
                              style={on ? { backgroundColor: c.chipStrong } : undefined}>
                        {!on && <span className="size-2 rounded-full" style={{ backgroundColor: c.rail }} aria-hidden />}
                        {x.name}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </section>

          <section className="space-y-2">
            <StepTitle n={2} title="Ne çalışacaksın?" />
            <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="örn. Palme sayfa 45'e kadar"
                   aria-label="Ne çalışacaksın" className="h-10" />
            <label className="flex items-center gap-2 text-xs text-foreground">
              <input type="checkbox" checked={homework} onChange={(e) => setHomework(e.target.checked)} />
              Ders / özel ders öğretmenimin verdiği ödev
            </label>
          </section>

          <section className="space-y-2">
            <StepTitle n={3} title="Ne kadar?" />
            <div className="flex w-full flex-wrap rounded-lg bg-muted p-0.5 text-xs font-medium" role="radiogroup" aria-label="Birim">
              {data.units.map((u) => (
                <button key={u} type="button" role="radio" aria-checked={unit === u} onClick={() => setUnit(u)}
                        className={cn("flex-1 rounded-md px-2.5 py-1.5 transition",
                          unit === u ? "bg-cyan-700 text-white shadow-sm" : "text-muted-foreground hover:text-foreground")}>
                  {UNIT_LABELS[u]}
                </button>
              ))}
            </div>
            {isActivity ? (
              <p className="text-xs text-muted-foreground">Etkinlik (video, özet, tekrar) tek birim sayılır; miktar gerekmez.</p>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center rounded-lg border">
                  <button type="button" onClick={() => step(-1)} className="grid size-9 place-items-center text-foreground hover:bg-muted" aria-label="Bir azalt">
                    <Minus className="size-4" aria-hidden />
                  </button>
                  <Input value={qty} onChange={(e) => setQty(e.target.value.replace(/\D/g, ""))} inputMode="numeric" placeholder="0"
                         className="h-9 w-16 rounded-none border-0 text-center text-base font-semibold" aria-label="Miktar" />
                  <button type="button" onClick={() => step(1)} className="grid size-9 place-items-center text-foreground hover:bg-muted" aria-label="Bir arttır">
                    <Plus className="size-4" aria-hidden />
                  </button>
                </div>
                {QUICK_QTY.map((v) => (
                  <button key={v} type="button" onClick={() => setQty(String(v))}
                          className={cn("min-w-9 rounded-md border px-2.5 py-1.5 text-xs font-semibold tabular-nums",
                            n === v ? "border-transparent bg-cyan-700 text-white" : "bg-background text-foreground hover:bg-muted")}>
                    {v}
                  </button>
                ))}
              </div>
            )}
          </section>

          <div className="rounded-lg border border-dashed bg-muted/40 p-3 text-xs" data-section="student:pool:add-preview">
            <div className="mb-1 font-semibold text-foreground">Havuzuna eklenecek</div>
            {ok && subj ? (
              <div className="flex flex-wrap items-center gap-1.5 text-foreground">
                <SubjectPill name={subj.name} size="xs" />
                <span className="font-medium">{label.trim()}</span>
                <span className="rounded bg-muted px-1.5 py-0.5 font-semibold">{isActivity ? "1 etkinlik" : `${n} ${UNIT_LABELS[unit]}`}</span>
                {homework && <span className="rounded bg-violet-700 px-1.5 py-0.5 font-semibold text-white">öğretmen ödevi</span>}
              </div>
            ) : (
              <p className="text-muted-foreground">Ders, ne çalışacağın ve miktarı seç.</p>
            )}
            <p className="mt-1 text-muted-foreground">Rehberin seansta kaynağından görüp onaylayınca yüzdeye girer.</p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Vazgeç</Button>
          <Button disabled={!ok || add.isPending} className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white"
                  onClick={() => subjectId != null && add.mutate(
                    { subject_id: subjectId, label: label.trim() || null, quantity: isActivity ? 1 : n, unit, teacher_homework: homework },
                    { onSuccess: () => { onOpenChange(false); reset(); } },
                  )}>
            Havuza ekle
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function StepTitle({ n, title }: { n: number; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="grid size-5 place-items-center rounded-full bg-cyan-700 text-[11px] font-bold text-white" aria-hidden>{n}</span>
      <span className="font-semibold text-foreground">{title}</span>
    </div>
  );
}
