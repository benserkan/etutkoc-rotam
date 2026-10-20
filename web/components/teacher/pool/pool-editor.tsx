"use client";

/**
 * Haftalık görev havuzu — REHBER EDİTÖRÜ (dershane modu, tasarım K24–K33).
 *
 * Akış: dönem aç → ders → konu listesi (SON işaretli, kalan, kaynaklar) → miktar
 * → kalem. Rehber günlere dağıtmaz (öğrenci kabını kendi kurar); "gün gün nasıl
 * görünür" yalnız önizlemedir. Havuz yazıldığı anda öğrenciye açıktır.
 * Gün-gün editöre (/week) dokunmaz; öğrenci havuz modunda değilse geçiş kartı.
 */
import * as React from "react";
import { VideoBasketFloat } from "@/components/teacher/weekly-plan/video-basket-float";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowLeft, ArrowRight, BookOpen, CalendarClock, CalendarDays, CalendarRange, Check, ChevronRight, CircleHelp, Eye, Gauge, Inbox, ListChecks, Target,
  MessagesSquare, PencilLine, Plus, Trash2, X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Hint } from "@/components/ui/hint";
import { subjectColors } from "@/components/shared/subject-tag";
import { cn } from "@/lib/utils";
import { GuideHint } from "@/components/guide/guide-hint";
import { AddPanel } from "./pool-add-panel";
import { ModeHistoryList, ModeSwitchDialog } from "@/components/teacher/pool/mode-switch-dialog";
import { PoolFlagsCard } from "./pool-flags-card";
import { PeriodHistory } from "./pool-period-history";
import { DayStrip, SubjectProgress, aggregateSubjects } from "./pool-progress";
import {
  getPool, poolKeys, SOURCE_LABELS, UNIT_LABELS,
  useApprovePoolItem, useClosePeriod, useDeletePoolItem, useOpenPeriod, useSetPoolItemQuantity,
  useSetExpected, useSetLessonDays,
  type PoolBundleResponse, type PoolItemOut,
} from "@/lib/api/pool";

const DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

/** Takvim günü farkı (yerel saat; yaz saati kaymasından etkilenmez). */
function daysBetween(a: string, b: string): number {
  const [y1, m1, d1] = a.split("-").map(Number);
  const [y2, m2, d2] = b.split("-").map(Number);
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86_400_000);
}

function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d + n);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

export type PoolEditorView = "izle" | "duzenle";

export function PoolEditor({ studentId, initial, initialView }: {
  studentId: number; initial: PoolBundleResponse; initialView?: PoolEditorView;
}) {
  const q = useQuery({
    queryKey: poolKeys.bundle(studentId),
    queryFn: () => getPool(studentId),
    initialData: initial,
  });
  const data = q.data ?? initial;
  const { student, period } = data;
  const isHavuz = student.program_mode === "havuz";
  // Kalem ekleme panelinin dersi burada tutulur: eksik ders şeridinden tıklayınca panel o derse atlar.
  const [subjectId, setSubjectId] = React.useState<number | null>(null);
  const addRef = React.useRef<HTMLDivElement>(null);
  const lessonsRef = React.useRef<HTMLDivElement>(null);
  const [lessonsOpen, setLessonsOpen] = React.useState(false);
  // İzle (varsayılan, havuz yazılmışsa): dönem boyunca öğrenci ne yaptı — gün gün + ders ders + açık kalemler.
  // Düzenle: havuzu yazma ekranı (ekleme paneli + liste + önizleme + ders programı). ?mod=duzenle ile doğrudan açılır.
  const [view, setView] = React.useState<PoolEditorView>(
    initialView ?? (initial.period && initial.period.items.length > 0 ? "izle" : "duzenle"),
  );
  const watching = view === "izle" && !!period;
  function jumpToSubject(id: number) {
    setView("duzenle");
    setSubjectId(id);
    addRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function openLessons() {
    setLessonsOpen(true);
    window.setTimeout(() => lessonsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-4 p-4" data-section="pool:editor">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Link
            href={`/teacher/students/${studentId}`}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" aria-hidden /> {student.full_name}
          </Link>
          <h1 className="text-xl font-semibold text-foreground">Haftalık görev havuzu</h1>
          <p className="text-sm text-muted-foreground">
            Seansta havuzu yaz; öğrenci her gün havuzdan kabını kendisi kurar. Havuz yazıldığı anda
            öğrenciye açıktır.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isHavuz && period && <ViewToggle view={view} onChange={setView} />}
          <ModeBadge mode={student.program_mode} />
        </div>
      </header>

      <GuideHint module="Havuz" />

      {!isHavuz ? (
        <>
          <ModeCard studentId={studentId} today={data.today} />
          <ModeHistoryList studentId={studentId} />
        </>
      ) : (
        <>
          {/* Video Sepeti (2026-10-20): havuz öğrencisinde videolar güne değil havuza kalem olarak eklenir */}
          <VideoBasketFloat studentId={studentId} subjects={data.subjects.map((s) => ({ id: s.id, name: s.name }))} />
          <PeriodBar studentId={studentId} data={data} />
          <PoolFlagsCard flags={data.flags} compact />
          {period && watching ? (
            <WatchView studentId={studentId} data={data} onEdit={() => setView("duzenle")} />
          ) : period ? (
            <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
              <div ref={addRef} className="scroll-mt-4 lg:sticky lg:top-4">
                <AddPanel studentId={studentId} data={data} subjectId={subjectId} onSubject={setSubjectId} />
              </div>
              <div className="space-y-4">
                <PoolList studentId={studentId} data={data} onPickSubject={jumpToSubject} />
                <PreviewCard data={data} onOpenLessons={openLessons} />
              </div>
            </div>
          ) : (
            <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
              Açık dönem yok. Seans günü “Dönem aç” ile başla; önceki dönemler aşağıda.
            </p>
          )}
          {!watching && (
            <div ref={lessonsRef} className="scroll-mt-4">
              <ClassGroupPanel studentId={studentId} data={data} open={lessonsOpen} onOpenChange={setLessonsOpen} />
            </div>
          )}
          <PeriodHistory data={data} />
          <ModeHistoryList studentId={studentId} />
        </>
      )}
    </div>
  );
}

function ViewToggle({ view, onChange }: { view: PoolEditorView; onChange: (v: PoolEditorView) => void }) {
  const btn = (v: PoolEditorView, label: string, icon: React.ReactNode, hint: string) => (
    <Hint text={hint}>
      <button
        type="button"
        onClick={() => onChange(v)}
        aria-pressed={view === v}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition",
          view === v ? "bg-cyan-700 text-white shadow-sm" : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )}
      >
        {icon} {label}
      </button>
    </Hint>
  );
  return (
    <div className="inline-flex rounded-lg border bg-card p-0.5" role="group" aria-label="Görünüm" data-section="pool:view">
      {btn("izle", "İzle", <Eye className="size-4" aria-hidden />, "Dönem boyunca öğrenci ne yaptı: gün gün, ders ders ve bekleyen kalemler.")}
      {btn("duzenle", "Düzenle", <PencilLine className="size-4" aria-hidden />, "Havuzu yaz: kalem ekle, kaldır, ders programı ve gün gün önizleme.")}
    </div>
  );
}

/** İzle modu: koçun "seansa kadar öğrenci ne yaptı" sorusunun tek ekranlık cevabı. */
function WatchView({ studentId, data, onEdit }: { studentId: number; data: PoolBundleResponse; onEdit: () => void }) {
  const period = data.period!;
  const del = useDeletePoolItem(studentId);
  const approve = useApprovePoolItem(studentId);
  const [showDone, setShowDone] = React.useState(false);
  const items = period.items;
  const pending = items.filter((i) => i.source === "ogrenci" && i.approval === "bekliyor");
  const open = items.filter((i) => i.remaining > 0 && !pending.includes(i));
  const done = items.filter((i) => i.remaining === 0 && !pending.includes(i));
  const order = new Map(aggregateSubjects(items).map((a, i) => [a.name, i]));
  const rowProps = (it: PoolItemOut) => ({
    studentId,
    onDelete: () => { if (window.confirm("Bu kalemi havuzdan kaldır? (iz kalır)")) del.mutate({ item_id: it.id }); },
    onApprove: (ok: boolean) => approve.mutate({ item_id: it.id, approved: ok }),
  });
  const grouped = (list: PoolItemOut[]) => {
    const g = new Map<string, PoolItemOut[]>();
    for (const it of list) g.set(it.subject_name, [...(g.get(it.subject_name) ?? []), it]);
    return [...g.entries()].sort((a, b) => (order.get(a[0]) ?? 99) - (order.get(b[0]) ?? 99));
  };
  return (
    <div className="space-y-4" data-section="pool:watch">
      <DayStrip studentId={studentId} periodId={period.id} items={items} today={data.today}
                expectedNextOn={period.summary.expected_next_on} />
      <SubjectProgress items={items} />

      {pending.length > 0 && (
        <section className="rounded-xl border border-amber-300 bg-card p-4 dark:border-amber-500/40" data-section="pool:watch:pending">
          <h2 className="font-semibold text-foreground">Onayını bekleyen öğrenci kalemleri ({pending.length})</h2>
          <p className="text-xs text-muted-foreground">Öğrenci kendisi ekledi; kaynağından gösterince onayla, yüzdeye girer.</p>
          <ul className="mt-2 space-y-1.5">{pending.map((it) => <ItemRow key={it.id} it={it} {...rowProps(it)} />)}</ul>
        </section>
      )}

      <section className="rounded-xl border bg-card p-4" data-section="pool:watch:open">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold text-foreground">
            Bekleyen kalemler <span className="text-sm font-normal text-muted-foreground">· {open.length} kalem, {done.length} bitti</span>
          </h2>
          <Button size="sm" variant="outline" onClick={onEdit}>
            <Plus className="size-4" aria-hidden /> Kalem ekle / düzenle
          </Button>
        </div>
        {open.length === 0 ? (
          <p className="mt-3 rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
            Havuzdaki her kalem bitti. Seansta yenisini yazabilirsin.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {grouped(open).map(([name, list]) => (
              <div key={name}>
                <div className="mb-1.5 flex items-center gap-2">
                  <SubjectPill name={name} />
                  <span className="text-xs text-muted-foreground">{list.length} kalem · {list.reduce((a, i) => a + (i.unit === "etkinlik" ? 1 : i.remaining), 0)} birim kaldı</span>
                </div>
                <ul className="space-y-1.5">{list.map((it) => <ItemRow key={it.id} it={it} {...rowProps(it)} />)}</ul>
              </div>
            ))}
          </div>
        )}
        {done.length > 0 && (
          <div className="mt-4 border-t pt-3">
            <button type="button" onClick={() => setShowDone((v) => !v)}
                    className="inline-flex items-center gap-1 text-sm font-medium text-emerald-700 hover:underline dark:text-emerald-300"
                    aria-expanded={showDone}>
              <ChevronRight className={cn("size-4 transition", showDone && "rotate-90")} aria-hidden />
              <Check className="size-4" aria-hidden /> {done.length} kalem bitti {showDone ? "— gizle" : "— göster"}
            </button>
            {showDone && <ul className="mt-2 space-y-1.5">{done.map((it) => <ItemRow key={it.id} it={it} {...rowProps(it)} />)}</ul>}
          </div>
        )}
      </section>
    </div>
  );
}

function ModeBadge({ mode }: { mode: "gun_gun" | "havuz" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold text-white",
        mode === "havuz" ? "bg-cyan-600" : "bg-slate-600",
      )}
    >
      {mode === "havuz" ? "Havuz modu" : "Gün gün program"}
    </span>
  );
}

function ModeCard({ studentId, today }: { studentId: number; today: string }) {
  const [switchOpen, setSwitchOpen] = React.useState(false);
  return (
    <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-4 text-cyan-900 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-100">
      <h2 className="font-semibold">Bu öğrenci gün gün programda</h2>
      <p className="mt-1 text-sm">
        Haftalık havuz modu dershane öğrencisi içindir: seansta haftanın görevlerini topluca
        yazarsın, günlere sen dağıtmazsın. Geçiş genelde program bittiğinde, yeni hafta başlamadan
        yapılır: geçiş gününden sonraki dokunulmamış görevler silinir ve rezervleri kitaba iade edilir;
        çözülenler müfredatta kalır. Geçmeden önce etkisini görürsün.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button onClick={() => setSwitchOpen(true)} data-testid="mode-switch-open"
                className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white">
          Havuz moduna geç
        </Button>
        <Link
          href={`/teacher/students/${studentId}/week`}
          className="inline-flex items-center rounded-md border border-cyan-300 px-3 py-2 text-sm hover:bg-cyan-100 dark:border-cyan-500/40 dark:hover:bg-cyan-500/20"
        >
          Gün gün programa dön
        </Link>
      </div>
      {switchOpen && (
        <ModeSwitchDialog studentId={studentId} toMode="havuz" today={today} open={switchOpen} onOpenChange={setSwitchOpen} />
      )}
    </div>
  );
}

function PeriodBar({ studentId, data }: { studentId: number; data: PoolBundleResponse }) {
  const { period, today } = data;
  const open = useOpenPeriod(studentId);
  const close = useClosePeriod(studentId);
  const expected = useSetExpected(studentId);
  const [switchOpen, setSwitchOpen] = React.useState(false);
  const [openedOn, setOpenedOn] = React.useState(today);
  const [next, setNext] = React.useState(addDays(today, 7));
  const [closeOpen, setCloseOpen] = React.useState(false);
  const [closeStatus, setCloseStatus] = React.useState<"ara" | "gorusmesiz">("gorusmesiz");
  const [closeNote, setCloseNote] = React.useState("");
  const [closeAck, setCloseAck] = React.useState(false);
  const [editNext, setEditNext] = React.useState(false);
  const [nextDraft, setNextDraft] = React.useState(period?.expected_next_on ?? "");
  const [carry, setCarry] = React.useState<Record<number, number | null>>({});

  if (!period) {
    return (
      <div className="rounded-lg border bg-card p-4" data-section="pool:open">
        {data.on_break && (
          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-100" data-section="pool:break">
            <span className="font-semibold">Ara (tatil)</span>
            <span>{fmtDate(data.on_break.since)} tarihinden beri — uyarılar ve hatırlatmalar susuyor, havuz boş.</span>
            <span className="ml-auto text-xs opacity-80">Aradan dönmek için aşağıdan dönem aç; kalan kalemleri devredebilirsin.</span>
          </div>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="block text-xs text-muted-foreground">Seans günü (dönem başlar)</span>
            <Input type="date" value={openedOn} onChange={(e) => setOpenedOn(e.target.value)} className="mt-1 w-44" />
          </label>
          <label className="text-sm">
            <span className="block text-xs text-muted-foreground">Beklenen sonraki seans</span>
            <Input type="date" value={next} onChange={(e) => setNext(e.target.value)} className="mt-1 w-44" />
          </label>
          <Hint text="Bugünkü seansla yeni dönemi başlatır. Havuza yazdığın kalemler öğrenciye hemen açılır; dönem bir sonraki seansta kapanır.">
          <Button
            onClick={() => open.mutate({
              opened_on: openedOn, expected_next_on: next || null,
              carry: Object.entries(carry).map(([id, qty]) => ({ item_id: Number(id), quantity: qty })),
            })}
            disabled={open.isPending}
            className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white"
            data-testid="pool-open-period"
          >
            Dönem aç{Object.keys(carry).length ? ` · ${Object.keys(carry).length} kalem devret` : ""}
          </Button>
          </Hint>
          <button
            type="button"
            onClick={() => setSwitchOpen(true)}
            className="ml-auto text-xs text-muted-foreground underline-offset-2 hover:underline"
            data-testid="mode-switch-back"
          >
            Gün gün moda dön
          </button>
          {switchOpen && (
            <ModeSwitchDialog studentId={studentId} toMode="gun_gun" today={today} open={switchOpen} onOpenChange={setSwitchOpen} />
          )}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Dönem bir sonraki gerçekleşen seansta kapanır. Beklenen gün çakılı değil; öğrenci gelmezse
          dönem uzar, tempo yeni güne göre hesaplanır.
        </p>
        {data.carry_candidates.length > 0 && (
          <div className="mt-3 rounded-md border p-3" data-section="pool:carry">
            <div className="text-sm font-semibold text-foreground">Devredilecek kalemler ({data.carry_candidates.length} aday)</div>
            <p className="text-xs text-muted-foreground">
              Son dönemden kalanlar. Yeni haftaya taşınacakları tek tek işaretle, gerekirse miktarı yeniden yaz. Üçüncü kez devredilen kalem “kaçınılan” diye işaretlenir.
            </p>
            <ul className="mt-2 space-y-1">
              {data.carry_candidates.map((c) => (
                <li key={c.item_id} className="flex flex-wrap items-center gap-2 rounded-md border px-2 py-1.5 text-sm" data-carry={c.item_id}>
                  <input type="checkbox" checked={c.item_id in carry} aria-label="Devret"
                         onChange={() => setCarry((prev) => { const n = { ...prev }; if (c.item_id in n) delete n[c.item_id]; else n[c.item_id] = c.remaining; return n; })} />
                  <span className={cn("min-w-0 flex-1 break-words text-foreground", c.teacher_homework && "italic")}>
                    <span className="text-xs text-muted-foreground">{c.subject_name} · </span>{c.title}
                    <span className="text-xs text-muted-foreground"> · kalan {c.remaining} {UNIT_LABELS[c.unit]}</span>
                  </span>
                  {c.carry_count > 0 && <span className="rounded-full bg-slate-600 px-2 py-0.5 text-[11px] font-semibold text-white">Devir ×{c.carry_count}</span>}
                  {c.third_carry && <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[11px] font-semibold text-amber-950">3. devir olacak</span>}
                  {c.item_id in carry && c.unit !== "etkinlik" && (
                    <Input value={String(carry[c.item_id] ?? "")} inputMode="numeric" aria-label="Devir miktarı" className="h-7 w-16 text-center"
                           onChange={(e) => { const n = Number(e.target.value); setCarry((p) => ({ ...p, [c.item_id]: Number.isInteger(n) && n > 0 ? n : null })); }} />
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  const late = !!period.expected_next_on && period.expected_next_on < today;
  const s = period.summary;
  // days_open = açılıştan bu yana GEÇEN gün (backend days_without_session); bugün dönemin (days_open + 1). günü.
  const dayNo = period.days_open + 1;
  const span = period.expected_next_on ? Math.max(1, daysBetween(period.opened_on, period.expected_next_on)) : null;
  const expectedPct = span ? Math.min(100, Math.round((100 * period.days_open) / span)) : null;
  const remainingUnits = Math.max(0, s.total_units - s.done_units);
  const avg = data.volume.avg_done_last3;
  const heavy = avg != null && avg > 0 && data.volume.current_total > avg * 1.5;
  const ahead = expectedPct != null && s.pct >= expectedPct;
  const timeline: string[] = [];
  if (span && span <= 21) for (let i = 0; i <= span; i++) timeline.push(addDays(period.opened_on, i));
  return (
    <section className="overflow-hidden rounded-2xl border bg-card shadow-sm" data-section="pool:period">
      <div className="flex flex-wrap items-start gap-4 bg-gradient-to-r from-cyan-700/10 via-transparent to-transparent p-4">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-foreground">Bu dönem</h2>
            <span className="rounded-full bg-cyan-700 px-2.5 py-0.5 text-xs font-semibold text-white" data-testid="pool-day-no">
              {dayNo}. gün{span ? ` / ${span}` : ""}
            </span>
            {late && <span className="rounded-full bg-rose-700 px-2 py-0.5 text-xs font-semibold text-white">beklenen seans geçti</span>}
            {period.days_open >= 14 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-rose-700 px-2 py-0.5 text-xs font-semibold text-white">
                <AlertTriangle className="size-3" aria-hidden /> 14 gündür seans yok
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <span className="text-muted-foreground">Dönem başlangıcı</span>
            <strong className="text-foreground">{fmtDate(period.opened_on)}</strong>
            <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden />
            <span className="text-muted-foreground">Beklenen seans</span>
            {editNext ? (
              <span className="flex items-center gap-1.5">
                <Input type="date" value={nextDraft} onChange={(e) => setNextDraft(e.target.value)} className="h-8 w-40" />
                <Button size="sm" onClick={() => {
                  expected.mutate({ period_id: period.id, opened_on: period.opened_on, expected_next_on: nextDraft || null });
                  setEditNext(false);
                }}>Kaydet</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditNext(false)}>Vazgeç</Button>
              </span>
            ) : (
              <button type="button" title="Beklenen seans gününü değiştir — öğrenci başka güne yazıldıysa ya da gelmediyse. Tempo yeni güne göre hesaplanır."
                      onClick={() => { setNextDraft(period.expected_next_on ?? ""); setEditNext(true); }}
                      className={cn("inline-flex items-center gap-1 rounded-md border border-dashed px-2 py-0.5 font-semibold hover:border-cyan-600",
                        late ? "text-rose-700 dark:text-rose-300" : "text-foreground")}>
                {fmtDate(period.expected_next_on)}
                <PencilLine className="size-3.5 text-muted-foreground" aria-hidden />
              </button>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Hint text="Seans günü buradan çalış: kalemleri tek tek gözden geçir, yapılanları işaretle, kalanları devret. 'Seansı bitir' dönemi kapatıp yenisini açar.">
            <Link
              href={`/teacher/students/${studentId}/pool/session`}
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-cyan-700 px-3 text-sm font-medium text-white hover:bg-cyan-800"
            >
              <MessagesSquare className="size-4" aria-hidden /> Seans ekranı
            </Link>
          </Hint>
          <Hint text="Seans YAPILMADAN dönemi kapatır: tatil (ara) ya da öğrenci gelmedi (görüşmesiz). Seans yaptıysan Seans ekranından 'Seansı bitir'i kullan.">
            <Button variant="outline" className="h-9" onClick={() => { setCloseAck(false); setCloseNote(""); setCloseOpen(true); }}>
              Seanssız kapat…
            </Button>
          </Hint>
        </div>

        {timeline.length > 0 && (
          <ol className="flex w-full gap-1 overflow-x-auto pb-1" aria-label="Dönem takvimi" data-section="pool:period:timeline">
            {timeline.map((d) => {
              const isToday = d === today;
              const past = d < today;
              const isSession = d === period.expected_next_on;
              const [y, m, dd] = d.split("-").map(Number);
              const wd = (new Date(y, m - 1, dd).getDay() + 6) % 7;
              return (
                <li key={d} className="min-w-[3.25rem] flex-1">
                  <div
                    className={cn(
                      "flex flex-col items-center rounded-lg border px-1 py-1.5 text-center",
                      past && "border-cyan-700/30 bg-cyan-700/10",
                      isToday && "border-cyan-700 bg-cyan-700 text-white shadow-sm",
                      isSession && !isToday && "border-dashed border-cyan-700",
                      !past && !isToday && !isSession && "border-dashed",
                    )}
                    title={isToday ? "Bugün" : isSession ? "Beklenen seans günü — dönem bu gün kapanır" : past ? "Geçen gün" : "Kalan gün"}
                  >
                    <span className={cn("text-[10px] font-medium", isToday ? "text-white" : "text-muted-foreground")}>{DAY_SHORT[wd]}</span>
                    <span className={cn("text-sm font-semibold", isToday ? "text-white" : "text-foreground")}>{dd}</span>
                    <span className={cn("text-[10px]", isToday ? "font-semibold text-white" : isSession ? "font-semibold text-cyan-700 dark:text-cyan-300" : "text-muted-foreground")}>
                      {isToday ? "bugün" : isSession ? "seans" : past ? "geçti" : "kaldı"}
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>

      <dl className="grid gap-px border-t bg-border sm:grid-cols-2 lg:grid-cols-4" data-section="pool:summary">
        <Stat
          icon={<Target className="size-4" aria-hidden />}
          label="Tamamlanan"
          value={`%${s.pct}`}
          valueClass={expectedPct == null ? "text-foreground" : ahead ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700 dark:text-amber-300"}
          hint="Yapılan birim ÷ havuzdaki toplam birim. Birim: her test 1; video, deneme ve etkinlik kalemi 1. Öğrencinin kaydı ve senin seansta işaretlediğin birlikte sayılır; onay bekleyen öğrenci kalemi girmez."
          explain={<>Havuzun <b className="text-foreground">{s.done_units} / {s.total_units}</b> birimi yapıldı{expectedPct != null && <>; dönemin bu gününe kadar beklenen yaklaşık <b className="text-foreground">%{expectedPct}</b> — {ahead ? "takvime göre önde" : "takvime göre geride"}</>}.</>}
        >
          <span className="relative mt-2 block h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
            <span className={cn("block h-full rounded-full", ahead || expectedPct == null ? "bg-emerald-500" : "bg-amber-500")} style={{ width: `${Math.min(100, s.pct)}%` }} />
            {expectedPct != null && <span className="absolute inset-y-0 w-0.5 bg-foreground/70" style={{ left: `${expectedPct}%` }} title={`Beklenen %${expectedPct}`} />}
          </span>
        </Stat>
        <Stat
          icon={<ListChecks className="size-4" aria-hidden />}
          label="Biten kalem"
          value={`${s.items_done} / ${s.items_total}`}
          hint="Kalanı sıfıra inen kalem 'bitti' sayılır. Kısmen yapılmış kalem bitmedi sayılır ama birimi yüzdeye girer."
          explain={<>Havuzdaki {s.items_total} kalemden <b className="text-foreground">{s.items_done}</b> tanesi tamamen bitti, {s.items_total - s.items_done} tanesinde iş var.</>}
        />
        <Stat
          icon={<CalendarClock className="size-4" aria-hidden />}
          label="Seansa kalan"
          value={`${s.days_left} gün`}
          valueClass={late ? "text-rose-700 dark:text-rose-300" : "text-foreground"}
          hint="Bugün dahil, beklenen seans gününe kadar çalışılacak gün sayısı (seans günü sayılmaz). Beklenen gün geçtiyse 1 kabul edilir; dönem öğrenci gelene kadar uzar."
          explain={s.expected_next_on
            ? late
              ? <>Beklenen seans ({fmtDate(s.expected_next_on)}) geçti; tempo 1 gün kabul edilerek hesaplanıyor.</>
              : <>Bugün dahil {s.days_left} çalışma günü var; seans <b className="text-foreground">{fmtDate(s.expected_next_on)}</b>.</>
            : <>Beklenen seans günü girilmemiş; tempo 1 gün kabul edilerek hesaplanıyor.</>}
        />
        <Stat
          icon={<Gauge className="size-4" aria-hidden />}
          label="Günde gereken"
          value={`${s.per_day_needed.toLocaleString("tr-TR")} birim`}
          hint="Kalan birim ÷ seansa kalan gün. Öğrencinin seansa kadar havuzu bitirmesi için ortalama günlük temposu."
          explain={remainingUnits > 0
            ? <>Kalan <b className="text-foreground">{remainingUnits}</b> birim ÷ {s.days_left} gün. Bu tempoyla havuz seansa kadar biter.</>
            : <>Havuz bitti; seansa kadar yeni iş gerekmiyor.</>}
        />
      </dl>

      {(s.pending_student_items > 0 || heavy) && (
        <div className="space-y-1 border-t bg-muted/40 px-4 py-2 text-xs">
          {s.pending_student_items > 0 && (
            <p className="text-amber-800 dark:text-amber-200">{s.pending_student_items} kalemi öğrenci ekledi, onay bekliyor — yüzdeye girmiyor.</p>
          )}
          {heavy && <p className="text-muted-foreground">Bilgi: son 3 dönemde ortalama {avg} birim bitirdi, bu havuz {data.volume.current_total} birim.</p>}
        </div>
      )}

      <Dialog open={closeOpen} onOpenChange={setCloseOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Dönemi seanssız kapat</DialogTitle>
            <DialogDescription>
              Dönem normalde seansta kapanır. Bu pencere yalnız seans YAPILAMADIĞINDA kullanılır.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <div className="rounded-lg border border-cyan-700/40 bg-cyan-500/10 p-3 text-foreground">
              <div className="font-semibold">Seans yaptıysan buradan kapatma</div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Seans ekranındaki “Seansı bitir” yapılanları işaretler (kitap sayacına yazar), kalanları seçerek devreder,
                seans kaydını tutar ve yeni dönemi tek adımda açar.
              </p>
              <Link href={`/teacher/students/${studentId}/pool/session`}
                    className="mt-2 inline-flex h-8 items-center gap-1.5 rounded-md bg-cyan-700 px-3 text-xs font-medium text-white hover:bg-cyan-800">
                <MessagesSquare className="size-3.5" aria-hidden /> Seans ekranına git
              </Link>
            </div>
            <div className="space-y-2" role="radiogroup" aria-label="Kapanış türü">
              {([
                ["gorusmesiz", "Görüşmesiz kapat", "Öğrenci gelmedi ya da seans yapılamadı. Seans kaydı oluşmaz (tahsilata sayılmaz); dönem geçmişte “görüşmesiz” görünür."],
                ["ara", "Ara (tatil)", "Havuz boşalır, uyarılar ve hatırlatmalar susar. Dönüşte yeni dönemi açarken kalanları devredersin."],
              ] as const).map(([v, l, d]) => (
                <label key={v} className={cn("flex cursor-pointer gap-2 rounded-lg border p-2.5", closeStatus === v && "border-cyan-700 bg-muted/50")}>
                  <input type="radio" name="close-status" className="mt-1" checked={closeStatus === v} onChange={() => setCloseStatus(v)} />
                  <span>
                    <span className="block font-medium text-foreground">{l}</span>
                    <span className="block text-xs text-muted-foreground">{d}</span>
                  </span>
                </label>
              ))}
            </div>
            {period.days_open < 7 && !late && (
              <p className="rounded-md bg-amber-400 px-3 py-2 text-xs font-medium text-amber-950">
                {period.days_open === 0 ? "Dönem bugün açıldı" : `Dönem ${period.days_open} gündür açık`} ve beklenen seans ({fmtDate(period.expected_next_on)}) henüz gelmedi.
                Öğrenci gelecekse kapatma; beklenen günü değiştirmen yeterli.
              </p>
            )}
            <label className="block">
              <span className="text-xs font-medium text-foreground">
                Gerekçe {closeStatus === "gorusmesiz" ? "(zorunlu)" : "(isteğe bağlı)"} — dönem notuna yazılır
              </span>
              <Input value={closeNote} onChange={(e) => setCloseNote(e.target.value)} maxLength={500}
                     placeholder={closeStatus === "ara" ? "örn. Ara tatil, 27 Ekim'de dönecek" : "örn. Hastaydı, seansa gelemedi"} className="mt-1" />
            </label>
            <p className="text-xs text-muted-foreground">
              Kalanı olan {period.items.filter((i) => i.remaining > 0 && i.counts).length} kalem devir adayı olur;
              yeni dönemi açınca kalem kalem seçersin.
            </p>
            <label className="flex items-start gap-2 text-xs text-foreground">
              <input type="checkbox" className="mt-0.5" checked={closeAck} onChange={(e) => setCloseAck(e.target.checked)} />
              Bu dönemde seans yapılmadığını onaylıyorum.
            </label>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCloseOpen(false)}>Vazgeç</Button>
            <Button
              onClick={() => {
                close.mutate({ period_id: period.id, closed_on: today, status: closeStatus, note: closeNote.trim() || null });
                setCloseOpen(false);
              }}
              disabled={close.isPending || !closeAck || (closeStatus === "gorusmesiz" && !closeNote.trim())}
              className="bg-rose-700 text-white hover:bg-rose-800 hover:text-white"
            >
              {closeStatus === "ara" ? "Araya al" : "Görüşmesiz kapat"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

/** Dönem kartı ölçüsü: büyük değer + her zaman görünür açıklama cümlesi + (?) ile hesap formülü. */
function Stat({ icon, label, value, valueClass, explain, hint, children }: {
  icon: React.ReactNode; label: string; value: string; valueClass?: string; explain: React.ReactNode; hint: string; children?: React.ReactNode;
}) {
  return (
    <div className="bg-card px-4 py-3">
      <dt className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <span className="grid size-6 place-items-center rounded-md bg-cyan-700/10 text-cyan-700 dark:text-cyan-300">{icon}</span>
        {label}
        <Hint text={hint}>
          <button type="button" aria-label={`${label} nasıl hesaplanır?`} className="ml-auto rounded-full text-muted-foreground hover:text-foreground">
            <CircleHelp className="size-3.5" aria-hidden />
          </button>
        </Hint>
      </dt>
      <dd className={cn("mt-1 text-2xl font-bold tabular-nums", valueClass ?? "text-foreground")}>{value}</dd>
      {children}
      <dd className="mt-1.5 text-xs leading-snug text-muted-foreground">{explain}</dd>
    </div>
  );
}

// ---------------------------------------------------------------- havuz listesi

function itemTitle(i: PoolItemOut): string {
  if (i.section_label && i.book_name) return `${i.book_name} — ${i.section_label}`;
  if (i.topic_name) return i.topic_name + (i.book_name ? ` (${i.book_name})` : "");
  return i.label ?? "—";
}

/** Kalemin K42 birimi: etkinlik 1, diğerleri miktar. */
function itemUnits(i: PoolItemOut): number {
  return i.unit === "etkinlik" ? 1 : i.quantity;
}

/** Dolgulu ders etiketi — ortak ders renk sisteminden (subject-tag), beyaz yazı. */
function SubjectPill({ name, className }: { name: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold text-white", className)}
          style={{ backgroundColor: subjectColors(name).chipStrong }}>
      {name}
    </span>
  );
}

function PoolList({ studentId, data, onPickSubject }: {
  studentId: number; data: PoolBundleResponse; onPickSubject: (subjectId: number) => void;
}) {
  const del = useDeletePoolItem(studentId);
  const approve = useApprovePoolItem(studentId);
  const items = data.period!.items;
  const groups = new Map<string, PoolItemOut[]>();
  for (const it of items) {
    const g = groups.get(it.subject_name) ?? [];
    g.push(it);
    groups.set(it.subject_name, g);
  }
  const counted = items.filter((i) => i.counts);
  const units = counted.reduce((a, i) => a + itemUnits(i), 0);
  // Ders dağılımı çubuğu (birim payı)
  const share = [...groups.entries()]
    .map(([name, list]) => ({ name, units: list.filter((i) => i.counts).reduce((a, i) => a + itemUnits(i), 0) }))
    .filter((x) => x.units > 0)
    .sort((a, b) => b.units - a.units);
  return (
    <section className="rounded-xl border bg-card shadow-sm" data-section="pool:list">
      <header className="space-y-3 border-b px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="grid size-9 place-items-center rounded-lg bg-muted text-foreground" aria-hidden>
            <BookOpen className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="flex flex-wrap items-center gap-2 text-base font-semibold text-foreground">
              Havuz
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">{items.length} kalem</span>
              <span className="rounded-full bg-cyan-700 px-2 py-0.5 text-xs font-semibold text-white">{units} birim</span>
            </h2>
            <p className="text-xs text-muted-foreground">Öğrenci bu listeden her gün kabını kurar.</p>
          </div>
        </div>
        {share.length > 0 && (
          <div className="space-y-1.5" data-section="pool:share">
            <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted" role="img"
                 aria-label={`Ders dağılımı: ${share.map((x) => `${x.name} ${x.units}`).join(", ")}`}>
              {share.map((x) => (
                <span key={x.name} className="h-full" title={`${x.name}: ${x.units} birim`}
                      style={{ width: `${(100 * x.units) / Math.max(1, units)}%`, backgroundColor: subjectColors(x.name).rail }} />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              {share.map((x) => (
                <span key={x.name} className="inline-flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full" style={{ backgroundColor: subjectColors(x.name).rail }} aria-hidden />
                  <span className="text-foreground">{x.name}</span> {x.units} · %{Math.round((100 * x.units) / Math.max(1, units))}
                </span>
              ))}
            </div>
          </div>
        )}
      </header>
      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
          <span className="grid size-11 place-items-center rounded-full bg-muted text-muted-foreground" aria-hidden>
            <Inbox className="size-5" />
          </span>
          <p className="text-sm font-medium text-foreground">Henüz kalem yok</p>
          <p className="max-w-xs text-xs text-muted-foreground">Soldan ders ve konu seç ya da “Hızlı yaz” ile tek satırda ekle.</p>
        </div>
      ) : (
        <div className="space-y-4 p-4">
          {[...groups.entries()].map(([name, list]) => {
            const gUnits = list.filter((i) => i.counts).reduce((a, i) => a + itemUnits(i), 0);
            return (
              <div key={name} data-pool-subject={name}>
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <SubjectPill name={name} />
                  <span className="text-xs text-muted-foreground">{list.length} kalem · {gUnits} birim</span>
                </div>
                <ul className="space-y-1.5">
                  {list.map((it) => <ItemRow key={it.id} it={it} studentId={studentId}
                                             onDelete={() => { if (window.confirm("Bu kalemi havuzdan kaldır? (iz kalır)")) del.mutate({ item_id: it.id }); }}
                                             onApprove={(ok) => approve.mutate({ item_id: it.id, approved: ok })} />)}
                </ul>
              </div>
            );
          })}
        </div>
      )}
      <MissingStrip data={data} onPick={onPickSubject} />
    </section>
  );
}

function ItemRow({ it, studentId, onDelete, onApprove }: {
  it: PoolItemOut; studentId: number; onDelete: () => void; onApprove: (ok: boolean) => void;
}) {
  const setQty = useSetPoolItemQuantity(studentId);
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState(String(it.quantity));
  const draftN = Number(draft);
  const draftOk = Number.isInteger(draftN) && draftN >= 1 && draftN <= 500;
  const editable = it.unit !== "etkinlik";
  function saveQty() {
    if (!draftOk) return;
    if (draftN === it.quantity) { setEditing(false); return; }
    setQty.mutate({ item_id: it.id, quantity: draftN }, { onSuccess: () => setEditing(false) });
  }
  const pending = it.source === "ogrenci" && it.approval === "bekliyor";
  const done = it.remaining === 0;
  const pct = it.quantity > 0 ? Math.round((100 * (it.quantity - it.remaining)) / it.quantity) : 0;
  return (
    <li className={cn("group rounded-lg border border-l-4 bg-background px-3 py-2 text-sm transition hover:shadow-sm",
      done && "opacity-75", pending && "border-amber-300 dark:border-amber-500/40")}
        style={{ borderLeftColor: subjectColors(it.subject_name).rail }}>
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className={cn("break-words text-foreground", it.teacher_homework && "italic", done && "line-through decoration-muted-foreground/60")}>
            {itemTitle(it)}
            {it.label && (it.topic_name || it.section_label) && <span className="text-muted-foreground"> · {it.label}</span>}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            {editing ? (
              <span className="inline-flex items-center gap-1" data-section="pool:item:qty-edit">
                <Input value={draft} inputMode="numeric" autoFocus aria-label="Yeni miktar"
                       onChange={(e) => setDraft(e.target.value)}
                       onKeyDown={(e) => { if (e.key === "Enter") saveQty(); if (e.key === "Escape") { setEditing(false); setDraft(String(it.quantity)); } }}
                       className="h-7 w-16 text-center text-sm" />
                <span className="text-foreground">{UNIT_LABELS[it.unit]}</span>
                <Button type="button" size="sm" className="h-7 bg-cyan-700 px-2 text-white hover:bg-cyan-800 hover:text-white"
                        disabled={!draftOk || setQty.isPending} onClick={saveQty}>
                  Kaydet
                </Button>
                <Button type="button" size="sm" variant="ghost" className="h-7 px-2"
                        onClick={() => { setEditing(false); setDraft(String(it.quantity)); }}>
                  Vazgeç
                </Button>
              </span>
            ) : editable ? (
              <Hint text="Miktarı değiştir (örn. 7 test → 5 test). Yapılan ve öğrencinin kabındaki testlerin altına inilmez.">
                <button type="button" onClick={() => { setDraft(String(it.quantity)); setEditing(true); }}
                        aria-label={`Miktarı değiştir (${it.quantity} ${UNIT_LABELS[it.unit]})`}
                        className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 font-medium tabular-nums text-foreground ring-cyan-600 transition hover:ring-1">
                  {it.quantity} {UNIT_LABELS[it.unit]}
                  <PencilLine className="size-3 text-muted-foreground" aria-hidden />
                </button>
              </Hint>
            ) : (
              <span className="rounded-md bg-muted px-1.5 py-0.5 font-medium tabular-nums text-foreground">
                {it.quantity} {UNIT_LABELS[it.unit]}
              </span>
            )}
            {it.exam_kind && it.question_count ? (
              <span className="tabular-nums">deneme başına {it.question_count} soru</span>
            ) : null}
            {it.completed > 0 && <span>{it.completed} yapıldı · {it.remaining} kaldı</span>}
            {it.book_total != null && (
              <span className="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-foreground" title="Kitabın bu bölümündeki ilerleme (kitap sayacı)">
                <BookOpen className="size-3" aria-hidden /> kitapta {it.book_completed ?? 0}/{it.book_total} çözüldü
              </span>
            )}
            {it.day_hint && <span>· {fmtDate(it.day_hint)}</span>}
            {it.teacher_homework && <Badge tone="violet">ders öğretmeni ödevi</Badge>}
            {it.source !== "rehber" && (
              <Badge tone={it.source === "ogrenci" ? "amber" : "slate"}>
                {SOURCE_LABELS[it.source]}{it.source === "devir" && it.carry_count > 0 ? ` ×${it.carry_count}` : ""}
              </Badge>
            )}
            {pending && <Badge tone="amber">onay bekliyor</Badge>}
            {it.source === "ogrenci" && it.approval === "reddedildi" && <Badge tone="rose">reddedildi</Badge>}
            {it.cup_attempts >= 3 && it.remaining > 0 && <Badge tone="rose">{it.cup_attempts} kez kaba girdi</Badge>}
          </div>
          {it.completed > 0 && (
            <span className="mt-1.5 block h-1 overflow-hidden rounded-full bg-muted" aria-hidden>
              <span className="block h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} />
            </span>
          )}
        </div>
        {pending && (
          <div className="flex shrink-0 gap-1">
            <Hint text="Öğrenci bu kalemi kendisi ekledi. Kaynağından gösterdiyse onayla — onaylanınca dönem yüzdesine girer.">
              <Button size="sm" variant="outline" onClick={() => onApprove(true)}>
                <Check className="size-4" aria-hidden /> Onayla
              </Button>
            </Hint>
            <Hint text="Reddet — kalem yüzdeye girmez, öğrenci reddedildiğini görür.">
              <Button size="sm" variant="ghost" onClick={() => onApprove(false)} aria-label="Reddet">
                <X className="size-4" aria-hidden />
              </Button>
            </Hint>
          </div>
        )}
        <Hint text="Kalemi havuzdan kaldır. Silinmez, iz kalır; öğrenci artık kabına alamaz.">
          <button type="button" onClick={onDelete} title="Kaldır" aria-label="Kaldır"
                  className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:bg-rose-500/10 hover:text-rose-700 dark:hover:text-rose-300">
            <Trash2 className="size-4" aria-hidden />
          </button>
        </Hint>
      </div>
    </li>
  );
}

function Badge({ tone, children }: { tone: "violet" | "amber" | "slate" | "rose" | "cyan"; children: React.ReactNode }) {
  const cls = {
    violet: "bg-violet-600 text-white", amber: "bg-amber-400 text-amber-950", slate: "bg-slate-600 text-white",
    rose: "bg-rose-700 text-white", cyan: "bg-cyan-700 text-white",
  }[tone];
  return <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold", cls)}>{children}</span>;
}

/** Havuz kartının alt bölümü: kalemi olmayan omurga dersleri (K24) — havuzun devamı gibi okunur. */
function MissingStrip({ data, onPick }: { data: PoolBundleResponse; onPick: (subjectId: number) => void }) {
  if (!data.missing_subjects.length) return null;
  const byName = new Map(data.subjects.map((s) => [s.name, s.id] as const));
  return (
    <div className="border-t border-dashed bg-muted/30 px-4 py-3" data-section="pool:missing">
      <div className="flex flex-wrap items-baseline gap-x-2 text-xs">
        <span className="font-semibold text-foreground">Bu havuzda kalemi olmayan dersler ({data.missing_subjects.length})</span>
        <span className="text-muted-foreground">kontrol için, zorunlu değil — tıkla, o dersten ekle</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {data.missing_subjects.map((n) => {
          const id = byName.get(n);
          return (
            <Hint key={n} text={`${n} dersinden havuza kalem eklemek için ekleme panelini bu derse açar.`}>
              <button type="button" disabled={id == null} onClick={() => id != null && onPick(id)}
                      className="inline-flex items-center gap-1.5 rounded-full border border-dashed bg-background px-2.5 py-1 text-xs text-foreground transition hover:border-solid hover:bg-muted disabled:opacity-60">
                <span className="size-2.5 rounded-full" style={{ backgroundColor: subjectColors(n).rail }} aria-hidden />
                {n}
                <Plus className="size-3 text-muted-foreground" aria-hidden />
              </button>
            </Hint>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- gün gün önizleme

/** Pazartesi=0 … Pazar=6 (şube ders programı anahtarı). */
function dowOf(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return (new Date(y, m - 1, d).getDay() + 6) % 7;
}

type PreviewDay = { date: string; dow: number; lessons: number[]; total: number; bySubject: Map<string, number> };

/**
 * Önizleme dağıtımı (yazılmaz, yol gösterir): kalemin kalan birimleri önce dersin DERSHANEDE
 * işlendiği günlere (şube ders programı), o günler arasında en boş olana birer birer; ders programında
 * günü olmayan kalemler en boş güne. Ders programı yoksa düz eşit bölme.
 */
function buildPreview(data: PoolBundleResponse): { days: PreviewDay[]; hasLessons: boolean } {
  const s = data.period!.summary;
  const n = Math.max(1, s.days_left);
  const lessons = data.class_group?.lesson_days ?? {};
  const hasLessons = Object.values(lessons).some((v) => v.length > 0);
  const days: PreviewDay[] = Array.from({ length: n }, (_, i) => {
    const date = addDays(data.today, i);
    const dow = dowOf(date);
    return { date, dow, lessons: lessons[String(dow)] ?? [], total: 0, bySubject: new Map() };
  });
  const open = data.period!.items.filter((i) => i.counts && i.remaining > 0);
  const unitsOf = (i: PoolItemOut) => (i.unit === "etkinlik" ? 1 : i.remaining);
  const place = (i: PoolItemOut, targets: PreviewDay[]) => {
    for (let k = 0; k < unitsOf(i); k++) {
      const d = targets.reduce((a, b) => (b.total < a.total ? b : a));
      d.total += 1;
      d.bySubject.set(i.subject_name, (d.bySubject.get(i.subject_name) ?? 0) + 1);
    }
  };
  const bound = open.filter((i) => i.subject_id != null && days.some((d) => d.lessons.includes(i.subject_id as number)));
  const free = open.filter((i) => !bound.includes(i));
  for (const i of bound) place(i, days.filter((d) => d.lessons.includes(i.subject_id as number)));
  for (const i of free) place(i, days);
  return { days, hasLessons };
}

function PreviewCard({ data, onOpenLessons }: { data: PoolBundleResponse; onOpenLessons: () => void }) {
  const [open, setOpen] = React.useState(false);
  const { days, hasLessons } = buildPreview(data);
  const subjName = new Map(data.subjects.map((x) => [x.id, x.name] as const));
  return (
    <div className="rounded-xl border bg-card text-sm shadow-sm" data-section="pool:preview">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex w-full items-center gap-3 px-4 py-3 text-left">
        <CalendarRange className="size-4 text-muted-foreground" aria-hidden />
        <span className="flex-1 font-medium text-foreground">Gün gün nasıl görünür? (önizleme)</span>
        {hasLessons && <span className="rounded-full bg-violet-700 px-2 py-0.5 text-[11px] font-semibold text-white">ders programına göre</span>}
        <ChevronRight className={cn("size-4 text-muted-foreground transition", open && "rotate-90")} aria-hidden />
      </button>
      {open && (
        <div className="space-y-3 border-t px-4 py-3">
          <p className="text-xs text-muted-foreground">
            {hasLessons
              ? "Her dersin kalan birimleri önce o dersin dershanede işlendiği günlere yerleşti, kalanı en boş güne. Öneri — yazılmaz; öğrenci kabını kendi kurar."
              : "Eşit bölme önerisi — yazılmaz; öğrenci kabını kendi kurar."}
          </p>
          {!hasLessons && data.student.class_group && (
            <button type="button" onClick={onOpenLessons}
                    className="w-full rounded-lg border border-dashed px-3 py-2 text-left text-xs text-foreground hover:bg-muted">
              <span className="font-semibold">Şube ders programını gir</span> — hangi gün hangi ders işleniyorsa kalemler o güne yerleşir.
            </button>
          )}
          <div className="grid gap-2 sm:grid-cols-2">
            {days.map((d) => (
              <div key={d.date} className="rounded-lg border bg-background p-2.5" data-preview-day={d.date}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium text-foreground">{fmtDate(d.date)} · {DAY_NAMES[d.dow]}</span>
                  <span className="font-semibold tabular-nums text-foreground">~{d.total} birim</span>
                </div>
                {d.lessons.length > 0 && (
                  <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
                    <span>Dershanede:</span>
                    {d.lessons.map((sid) => {
                      const nm = subjName.get(sid);
                      return nm ? <span key={sid} className="rounded px-1.5 py-px font-medium text-white" style={{ backgroundColor: subjectColors(nm).chipStrong }}>{nm}</span> : null;
                    })}
                  </div>
                )}
                {d.bySubject.size > 0 ? (
                  <ul className="mt-1.5 space-y-0.5">
                    {[...d.bySubject.entries()].sort((a, b) => b[1] - a[1]).map(([nm, u]) => (
                      <li key={nm} className="flex items-center gap-1.5 text-xs">
                        <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: subjectColors(nm).rail }} aria-hidden />
                        <span className="min-w-0 flex-1 break-words text-foreground">{nm}</span>
                        <span className="tabular-nums text-muted-foreground">{u}</span>
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
    </div>
  );
}

// ---------------------------------------------------------------- şube ders programı

const DAY_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const EMPTY_LESSONS: Record<string, number[]> = {};

function sameLessons(a: Record<string, number[]>, b: Record<string, number[]>): boolean {
  for (let d = 0; d < 7; d++) {
    const x = [...(a[String(d)] ?? [])].sort().join(",");
    const y = [...(b[String(d)] ?? [])].sort().join(",");
    if (x !== y) return false;
  }
  return true;
}

function ClassGroupPanel({ studentId, data, open, onOpenChange }: {
  studentId: number; data: PoolBundleResponse; open: boolean; onOpenChange: (v: boolean) => void;
}) {
  const save = useSetLessonDays(studentId);
  const cg = data.class_group;
  const saved = cg?.lesson_days ?? EMPTY_LESSONS;
  const savedKey = JSON.stringify(saved);
  const [lessons, setLessons] = React.useState<Record<string, number[]>>(saved);
  const [lastSavedKey, setLastSavedKey] = React.useState(savedKey);
  // Sunucudan farklı bir program gelince taslağı tazele (render sırasında; içerik karşılaştırması —
  // nesne kimliğiyle karşılaştırmak boş programda her çizimde yeni {} ürettiği için sonsuz döngüydü)
  if (lastSavedKey !== savedKey) {
    setLastSavedKey(savedKey);
    setLessons(saved);
  }

  if (!data.student.class_group) {
    return (
      <p className="text-xs text-muted-foreground">
        Öğrencinin şubesi yok; şube ders programı ve konu konumu şubeli öğrencilerde tutulur.
      </p>
    );
  }
  function toggle(day: number, sid: number) {
    setLessons((prev) => {
      const cur = new Set(prev[String(day)] ?? []);
      if (cur.has(sid)) cur.delete(sid); else cur.add(sid);
      return { ...prev, [String(day)]: [...cur] };
    });
  }
  const dirty = !sameLessons(lessons, saved);
  const total = Object.values(saved).reduce((a, v) => a + v.length, 0);
  const positions = cg ? Object.entries(cg.positions) : [];
  const groups: Array<[string, typeof data.subjects]> = [];
  const okul = data.subjects.filter((s) => s.group !== "sinav");
  const tyt = data.subjects.filter((s) => s.group === "sinav" && !s.is_ayt);
  const ayt = data.subjects.filter((s) => s.group === "sinav" && s.is_ayt);
  if (okul.length) groups.push([data.curriculum_label ?? "Okul dersleri", okul]);
  if (tyt.length) groups.push(["TYT", tyt]);
  if (ayt.length) groups.push(["AYT", ayt]);
  const perDay = DAY_SHORT.map((_, d) => (lessons[String(d)] ?? []).length);
  return (
    <section className="rounded-xl border bg-card text-sm shadow-sm" data-section="pool:class-group">
      <button type="button" onClick={() => onOpenChange(!open)} aria-expanded={open}
              className="flex w-full items-center gap-3 px-4 py-3 text-left">
        <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-violet-700 text-white" aria-hidden>
          <CalendarDays className="size-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold text-foreground">Şube {data.student.class_group} · dershane ders programı</span>
          <span className="block text-xs text-muted-foreground">
            {total > 0 ? `${total} ders-gün işaretli — önizleme ve öğrencinin sabah hatırlatması bunu kullanır` : "Henüz girilmedi — hangi gün hangi ders işleniyor?"}
          </span>
        </span>
        <ChevronRight className={cn("size-4 text-muted-foreground transition", open && "rotate-90")} aria-hidden />
      </button>
      {open && (
        <div className="space-y-3 border-t px-4 py-3">
          {positions.length > 0 && (
            <div className="text-xs text-muted-foreground">
              Şu an işlenen:{" "}
              {positions.map(([sid, v]) => {
                const sName = data.subjects.find((s) => String(s.id) === sid)?.name ?? `#${sid}`;
                return <span key={sid} className="mr-2 text-foreground">{sName}: {v.topic_name ?? "—"}</span>;
              })}
              <span>(konu listesinden “Şube bu konuda” ile değişir)</span>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Hücreye dokun: o gün dershanede o ders işleniyor. Kalemler önizlemede o güne yerleşir; öğrencinin sabah
            hatırlatması da buna göre konuşur (“bugün biyoloji vardı, biyoloji kalemin var”).
          </p>
          <div className="relative overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[34rem] border-collapse text-xs" aria-label="Şube ders programı">
              <thead>
                <tr className="bg-muted/60">
                  <th className="sticky left-0 z-10 bg-muted px-3 py-2 text-left font-semibold text-foreground">Ders</th>
                  {DAY_SHORT.map((d, i) => (
                    <th key={d} className="px-1 py-2 text-center font-semibold text-foreground">
                      {d}
                      <span className="block text-[10px] font-normal text-muted-foreground">{perDay[i] ? `${perDay[i]} ders` : "—"}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {groups.map(([title, list]) => (
                  <React.Fragment key={title}>
                    {groups.length > 1 && (
                      <tr>
                        <td colSpan={8} className="bg-muted/30 px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</td>
                      </tr>
                    )}
                    {list.map((s) => {
                      const c = subjectColors(s.name);
                      return (
                        <tr key={s.id} className="border-t hover:bg-muted/40">
                          <th scope="row" className="sticky left-0 z-10 bg-card px-3 py-1.5 text-left font-medium text-foreground">
                            <span className="inline-flex items-center gap-2">
                              <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: c.rail }} aria-hidden />
                              <span className="break-words">{s.name}</span>
                            </span>
                          </th>
                          {DAY_SHORT.map((d, day) => {
                            const on = (lessons[String(day)] ?? []).includes(s.id);
                            return (
                              <td key={d} className="px-1 py-1 text-center">
                                <button type="button" onClick={() => toggle(day, s.id)} aria-pressed={on}
                                        aria-label={`${DAY_NAMES[day]} — ${s.name}`}
                                        className={cn("mx-auto grid size-7 place-items-center rounded-md border transition",
                                          on ? "border-transparent text-white shadow-sm" : "border-dashed text-transparent hover:border-solid hover:bg-muted")}
                                        style={on ? { backgroundColor: c.chipStrong } : undefined}>
                                  <Check className="size-3.5" aria-hidden />
                                </button>
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Hint text="Ders programını şube için kaydeder; aynı şubedeki öğrencilerin önizlemesi ve hatırlatmaları da bunu kullanır.">
              <Button size="sm" onClick={() => save.mutate({ lessons })} disabled={save.isPending || !dirty}
                      className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white">
                Programı kaydet
              </Button>
            </Hint>
            {dirty && (
              <>
                <span className="rounded-full bg-amber-400 px-2 py-0.5 text-[11px] font-semibold text-amber-950">kaydedilmedi</span>
                <Button size="sm" variant="ghost" onClick={() => setLessons(saved)}>Geri al</Button>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
