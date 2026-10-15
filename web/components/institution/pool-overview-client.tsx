"use client";

/**
 * Kurum — Haftalık Havuz Panosu (K54/K55, Adım 5, 2026-10-12; yeni tasarım 2026-10-13).
 *
 * Rehberin (havuz editörü + seans ekranı) ve öğrencinin (Havuzum + Bugün kabı) ürettiği
 * verinin kurumdaki yansıması: dönem ilerlemesi · bugün öğrenci katılımı · tempo · kim
 * işaretliyor (öğrenci kaydı / rehber seans işareti) · havuzun yapısı · sinyal aileleri ·
 * şube × dönem · ders bazında · eğilim · geciken seans · rehber yükü.
 * Gizlilik: öğrenci detay sayfası yok (D4 deseni). Her sayı ColumnHint ile açıklanır.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle, BookOpen, CalendarClock, CheckCircle2, ClipboardList, Gauge, Layers, ListChecks,
  ShieldAlert, TrendingUp, UserCheck, Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { ColumnHint } from "@/components/ui/column-hint";
import { Card } from "@/components/ui/card";
import { subjectColors } from "@/components/shared/subject-tag";
import { institutionKeys, getInstitutionPoolOverview } from "@/lib/api/institution";
import type { InstitutionPoolOverviewResponse } from "@/lib/types/institution";

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `%${v}`;
}
function tone(v: number | null | undefined): string {
  if (v == null) return "text-muted-foreground";
  if (v >= 70) return "text-emerald-700 dark:text-emerald-300";
  if (v >= 40) return "text-amber-700 dark:text-amber-300";
  return "text-rose-700 dark:text-rose-300";
}
function barTone(v: number | null | undefined): string {
  if (v == null) return "bg-slate-300 dark:bg-slate-600";
  if (v >= 70) return "bg-emerald-600";
  if (v >= 40) return "bg-amber-500";
  return "bg-rose-600";
}
function fmt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function share(n: number, total: number): number {
  return total > 0 ? Math.round((100 * n) / total) : 0;
}

export function PoolOverviewClient({ initial }: { initial: InstitutionPoolOverviewResponse }) {
  const q = useQuery({ queryKey: institutionKeys.poolOverview(), queryFn: getInstitutionPoolOverview, initialData: initial, staleTime: 30_000 });
  const d = q.data ?? initial;
  return (
    <div className="space-y-6" data-section="institution:pool">
      <header className="rounded-2xl border bg-gradient-to-br from-cyan-700 to-cyan-900 p-5 text-white shadow-sm">
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Layers className="size-6" aria-hidden /> Haftalık Havuz
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-cyan-50">
          Rehber seansta öğrencinin haftalık havuzunu yazar, öğrenci her gün havuzdan kabını kurup işaretler.
          Bu sayfa iki taraftan gelen veriyi kurum düzeyinde toplar; öğrenci ayrıntısı rehberdedir.
        </p>
        {d.students > 0 && (
          <p className="mt-3 text-sm font-medium text-white">
            {d.students} öğrenci · {d.coaches} rehber · {d.open_periods} açık dönem
          </p>
        )}
      </header>

      {d.students === 0 ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          Kurumda haftalık havuz modunda öğrenci yok. Rehber, öğrenci profilinden “Haftalık havuz modu”na geçirince burada görünür.
        </p>
      ) : (
        <>
          <Kpis d={d} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <StudentSide d={d} />
            <CoachSide d={d} />
          </div>
          <Signals d={d} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
            <div className="min-w-0 lg:col-span-3"><Groups d={d} /></div>
            <div className="min-w-0 lg:col-span-2"><Trend d={d} /></div>
          </div>
          <Subjects d={d} />
          <Late d={d} />
          <Coaches d={d} />
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ KPI

function Kpis({ d }: { d: InstitutionPoolOverviewResponse }) {
  const exp = d.avg_expected_pct;
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-section="institution:pool:kpi">
      <Card className="p-4">
        <Label icon={Gauge}>
          <ColumnHint label="Açık dönem ilerlemesi" hint="Şu an açık dönemi olan öğrencilerde: biten birim ÷ havuzdaki birim (öğrenci kaydı + rehber seans işareti); ortalama. Birim = test sayısı, etkinlik/deneme 1. Çizgi = dönemin geçen gün oranı (yüzde bu civarda olmalı)." />
        </Label>
        <div className={cn("mt-1 text-3xl font-bold tabular-nums", tone(d.avg_open_pct))}>{pct(d.avg_open_pct)}</div>
        <div className="relative mt-2 h-2 rounded-full bg-slate-200 dark:bg-slate-700" aria-hidden>
          <div className={cn("h-2 rounded-full", barTone(d.avg_open_pct))} style={{ width: `${Math.min(100, d.avg_open_pct ?? 0)}%` }} />
          {exp != null && <div className="absolute -top-1 h-4 w-0.5 bg-slate-900 dark:bg-white" style={{ left: `${Math.min(100, exp)}%` }} />}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">{exp != null ? `dönemin %${exp}'i geçti` : "beklenen seans günü girilmemiş"}</div>
      </Card>
      <Card className="p-4">
        <Label icon={CheckCircle2}>
          <ColumnHint label="Son dönem %" hint="Her öğrencinin en son KAPANMIŞ döneminde biten birim ÷ havuz; kurum ortalaması. Tatil (ara) dönemleri sayılmaz." />
        </Label>
        <div className={cn("mt-1 text-3xl font-bold tabular-nums", tone(d.avg_last_pct))}>{pct(d.avg_last_pct)}</div>
        <div className="mt-1 text-xs text-muted-foreground">kapanmış dönemlerin ortalaması</div>
      </Card>
      <Card className="p-4">
        <Label icon={CalendarClock}>
          <ColumnHint label="Seansı geciken" hint="Açık dönemi olup beklenen seans günü 3+ gün geçmiş ya da 14 gündür seans yapılmamış öğrenci sayısı (K54)." />
        </Label>
        <div className={cn("mt-1 text-3xl font-bold tabular-nums", d.late_sessions ? "text-amber-700 dark:text-amber-300" : "text-foreground")}>{d.late_sessions}</div>
        <div className="mt-1 text-xs text-muted-foreground">öğrenci</div>
      </Card>
      <Card className="p-4">
        <Label icon={AlertTriangle}>
          <ColumnHint label="Dikkat isteyen öğrenci" hint="Havuz erken uyarı motorunda ana kartı kırmızı (acil) / sarı (dikkat) olan öğrenci sayısı. Öğrenciye kırmızı gösterilmez; rehberin görüşme listesindedir." />
        </Label>
        <div className="mt-1 flex items-baseline gap-3">
          <span className={cn("text-3xl font-bold tabular-nums", d.red_students ? "text-rose-700 dark:text-rose-300" : "text-foreground")}>{d.red_students}</span>
          <span className="text-sm text-muted-foreground">kırmızı</span>
          <span className={cn("text-xl font-semibold tabular-nums", d.amber_students ? "text-amber-700 dark:text-amber-300" : "text-foreground")}>{d.amber_students}</span>
          <span className="text-sm text-muted-foreground">sarı</span>
        </div>
        <div className="mt-1 text-xs text-muted-foreground">{d.students - d.red_students - d.amber_students} öğrenci yolunda</div>
      </Card>
    </div>
  );
}

function Label({ icon: Icon, children }: { icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>; children: React.ReactNode }) {
  return <div className="flex items-center gap-2 text-xs text-muted-foreground"><Icon className="size-4" aria-hidden /> {children}</div>;
}

function SectionTitle({ icon: Icon, children, sub }: { icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>; children: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="mb-3">
      <h2 className="inline-flex items-center gap-2 font-semibold text-foreground">
        <Icon className="size-4 text-cyan-700 dark:text-cyan-400" aria-hidden /> {children}
      </h2>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

function MeterRow({ label, value, total, color, right }: { label: React.ReactNode; value: number; total: number; color: string; right?: string }) {
  const w = share(value, total);
  return (
    <div>
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="text-foreground">{label}</span>
        <span className="font-semibold tabular-nums text-foreground">{right ?? `${value} / ${total}`}</span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-slate-200 dark:bg-slate-700" aria-hidden>
        <div className={cn("h-2 rounded-full", color)} style={{ width: `${w}%` }} />
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ öğrenci tarafı

function StudentSide({ d }: { d: InstitutionPoolOverviewResponse }) {
  const p = d.participation;
  const pc = d.pace;
  const paceTotal = pc.onde + pc.yolunda + pc.geride + pc.belirsiz;
  const seg = [
    { k: "Önde", v: pc.onde, c: "bg-emerald-600" },
    { k: "Yolunda", v: pc.yolunda, c: "bg-cyan-600" },
    { k: "Geride", v: pc.geride, c: "bg-amber-500" },
    { k: "Belirsiz", v: pc.belirsiz, c: "bg-slate-400" },
  ];
  return (
    <Card className="p-4" data-section="institution:pool:students">
      <SectionTitle icon={UserCheck} sub="Öğrencinin Havuzum ve Bugün ekranından gelen veri — bugün itibarıyla.">Öğrenci tarafı</SectionTitle>
      <div className="space-y-3">
        <MeterRow total={p.students} value={p.cup_today} color="bg-cyan-600"
          label={<ColumnHint label="Bugün kabını kuran" hint="Bugün havuzdan en az bir kalemi 'kaba' alıp bugünün görevi yapan öğrenci ÷ havuz öğrencisi." />} />
        <MeterRow total={p.students} value={p.ticked_today} color="bg-emerald-600"
          label={<ColumnHint label="Bugün işaretleyen" hint="Bugünün kabındaki en az bir görevde çözdüğünü işaretleyen öğrenci ÷ havuz öğrencisi. Akşam saatlerinde artar." />} />
        <div className="grid grid-cols-2 gap-3 pt-1">
          <MiniStat value={p.idle} tone={p.idle ? "amber" : "slate"}
            label={<ColumnHint label="Havuza dokunmuyor" hint="2-3 gündür ne giriş ne kap ne işaret olan öğrenci (pool_idle_streak sinyali)." />} />
          <MiniStat value={p.paper} tone="slate"
            label={<ColumnHint label="Kağıt öğrencisi" hint="Uygulamaya kayıt girmeyen, çalışmasını rehber seansta işaretleyen öğrenci. Tempo uyarıları bu öğrencide susar." />} />
        </div>
        <div className="pt-1">
          <div className="flex items-center justify-between text-sm">
            <ColumnHint label="Tempo" hint="Açık dönemi olan öğrencide, öğrencinin Havuzum ekranında gördüğü tempo cümlesinin aynısı: kalan birim ÷ kalan gün ≤ 2 → yolunda; havuz bitti → önde; daha fazlası → geride; havuz boş → belirsiz." />
            <span className="text-xs text-muted-foreground">{paceTotal} açık dönem</span>
          </div>
          <div className="mt-1 flex h-3 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700" aria-hidden>
            {seg.map((s) => s.v > 0 && <div key={s.k} className={s.c} style={{ width: `${share(s.v, paceTotal)}%` }} />)}
          </div>
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-foreground">
            {seg.map((s) => (
              <li key={s.k} className="inline-flex items-center gap-1.5"><span className={cn("size-2.5 rounded-full", s.c)} aria-hidden />{s.k} <b className="tabular-nums">{s.v}</b></li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}

function MiniStat({ label, value, tone: t }: { label: React.ReactNode; value: number; tone: "amber" | "slate" }) {
  return (
    <div className={cn("rounded-lg border p-2.5", t === "amber" && value ? "border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10" : "")}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("text-xl font-bold tabular-nums", t === "amber" && value ? "text-amber-800 dark:text-amber-200" : "text-foreground")}>{value}</div>
    </div>
  );
}

// ------------------------------------------------------------------ rehber tarafı

function CoachSide({ d }: { d: InstitutionPoolOverviewResponse }) {
  const s = d.sources;
  const i = d.items;
  const stu = share(s.student_units, s.done_units);
  return (
    <Card className="p-4" data-section="institution:pool:coachside">
      <SectionTitle icon={ClipboardList} sub="Rehberin havuz editörü ve seans ekranından gelen veri — açık dönemler.">Havuzun yapısı</SectionTitle>
      <div className="space-y-3">
        <div>
          <div className="flex items-center justify-between gap-2 text-sm">
            <ColumnHint label="Kim işaretledi?" hint="Açık dönemlerde biten birimin kaynağı: öğrencinin kendi kaydı (kap görevini işaretlemesi) ve rehberin seansta işaretlediği kısım. Rehber payı yüksekse öğrenci uygulamayı kullanmıyordur." />
            <span className="font-semibold tabular-nums text-foreground">{s.done_units} / {s.total_units} birim</span>
          </div>
          <div className="mt-1 flex h-3 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700" aria-hidden>
            {s.student_units > 0 && <div className="bg-emerald-600" style={{ width: `${share(s.student_units, s.total_units)}%` }} />}
            {s.coach_units > 0 && <div className="bg-violet-600" style={{ width: `${share(s.coach_units, s.total_units)}%` }} />}
          </div>
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-foreground">
            <li className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-emerald-600" aria-hidden />öğrenci kaydı <b className="tabular-nums">{s.student_units}</b>{s.done_units ? ` (%${stu})` : ""}</li>
            <li className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-violet-600" aria-hidden />rehber seans işareti <b className="tabular-nums">{s.coach_units}</b></li>
            <li className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-slate-300 dark:bg-slate-600" aria-hidden />kalan <b className="tabular-nums">{Math.max(0, s.total_units - s.done_units)}</b></li>
          </ul>
        </div>
        <div>
          <div className="text-sm">
            <ColumnHint label={`Havuzdaki kalemler (${i.total})`} hint="Açık dönemlerdeki kalemler (kaldırılanlar hariç). Kitaplı = kitabın bölümüne bağlı (kitap sayacına yazılır); konulu = kaynaksız müfredat konusu; serbest = yalnız metin." />
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2">
            <Pill label="kitaplı" value={i.book} />
            <Pill label="konulu" value={i.topic} />
            <Pill label="serbest" value={i.free} />
            <Pill label={<ColumnHint label="öğretmen ödevi" hint="Ders/özel ders öğretmeninin verdiği, öğrencinin seansta aktardığı kalem (K11)." />} value={i.teacher_homework} />
            <Pill label={<ColumnHint label="devreden" hint="Önceki dönemden kalanı yeni döneme taşınan kalem (K22)." />} value={i.carried} />
            <Pill label={<ColumnHint label="onay bekleyen" hint="Öğrencinin kendi eklediği, rehberin seansta onaylaması gereken kalem (K38). Onaylanana dek yüzdeye girmez." />} value={i.pending_approval} warn />
          </div>
        </div>
      </div>
    </Card>
  );
}

function Pill({ label, value, warn }: { label: React.ReactNode; value: number; warn?: boolean }) {
  return (
    <div className={cn("rounded-lg border px-2.5 py-2", warn && value ? "border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10" : "")}>
      <div className={cn("text-lg font-bold tabular-nums", warn && value ? "text-amber-800 dark:text-amber-200" : "text-foreground")}>{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

// ------------------------------------------------------------------ sinyaller

function Signals({ d }: { d: InstitutionPoolOverviewResponse }) {
  return (
    <Card className="p-4" data-section="institution:pool:signals">
      <SectionTitle icon={ShieldAlert} sub="Erken uyarı motorunun öğrenci başına ürettiği sinyaller, türe göre. Sayı = bu sinyali taşıyan öğrenci (ana kart ya da ek sinyal).">Sinyaller</SectionTitle>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {d.signals.map((s) => (
          <div key={s.key} className={cn("rounded-lg border p-3",
            s.red ? "border-rose-300 bg-rose-50 dark:border-rose-500/40 dark:bg-rose-500/10"
              : s.amber ? "border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10" : "")}
            data-signal={s.key}>
            <div className="text-sm font-medium text-foreground"><ColumnHint label={s.label} hint={s.hint} className="text-left" /></div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className={cn("text-2xl font-bold tabular-nums",
                s.red ? "text-rose-800 dark:text-rose-200" : s.amber ? "text-amber-800 dark:text-amber-200" : "text-foreground")}>{s.students}</span>
              <span className="text-xs text-muted-foreground">öğrenci</span>
            </div>
            {(s.red > 0 || s.amber > 0 || s.info > 0) && (
              <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
                {s.red > 0 && <span className="rounded bg-rose-700 px-1.5 py-0.5 font-medium text-white">{s.red} acil</span>}
                {s.amber > 0 && <span className="rounded bg-amber-400 px-1.5 py-0.5 font-medium text-amber-950">{s.amber} dikkat</span>}
                {s.info > 0 && <span className="rounded bg-slate-600 px-1.5 py-0.5 font-medium text-white">{s.info} bilgi</span>}
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ şube

function Groups({ d }: { d: InstitutionPoolOverviewResponse }) {
  return (
    <Card className="h-full p-4" data-section="institution:pool:groups">
      <SectionTitle icon={Users} sub="Şube = öğrenci profilindeki şube etiketi.">Şube × dönem</SectionTitle>
      <div className="relative overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted-foreground">
            <tr>
              <th className="py-1 pr-3">Şube</th>
              <th className="py-1 pr-3"><ColumnHint label="Öğrenci" hint="Şubedeki havuz modlu öğrenci sayısı." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Son dönem %" hint="Şubedeki öğrencilerin en son kapanmış (tatil hariç) dönem yüzdelerinin ortalaması." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Açık dönem %" hint="Şu an açık dönemde biten ÷ havuz; dönem ortasında düşük olması normal." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Geciken" hint="Şubede beklenen seans günü 3+ gün geçen ya da 14 gündür seanssız öğrenci." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Kırmızı / sarı" hint="Şubede ana sinyali kırmızı / sarı olan öğrenci." /></th>
              <th className="py-1"><ColumnHint label="Ders programı" hint="Rehber şubenin dershane ders programını girdi mi? Girildiyse öğrencinin haftaya dağılım önerisi ve hatırlatmaları o güne göre yapılır." /></th>
            </tr>
          </thead>
          <tbody>
            {d.groups.map((g) => (
              <tr key={g.class_group} className="border-t align-middle">
                <td className="py-2 pr-3 font-medium text-foreground">{g.class_group}</td>
                <td className="py-2 pr-3 tabular-nums">{g.students}</td>
                <td className="py-2 pr-3">
                  <div className="flex items-center gap-2">
                    <span className={cn("w-10 font-semibold tabular-nums", tone(g.last_pct))}>{pct(g.last_pct)}</span>
                    <span className="hidden h-1.5 w-16 rounded-full bg-slate-200 sm:block dark:bg-slate-700" aria-hidden>
                      <span className={cn("block h-1.5 rounded-full", barTone(g.last_pct))} style={{ width: `${g.last_pct ?? 0}%` }} />
                    </span>
                  </div>
                </td>
                <td className={cn("py-2 pr-3 tabular-nums", tone(g.open_pct))}>{pct(g.open_pct)}</td>
                <td className={cn("py-2 pr-3 tabular-nums", g.late_sessions ? "font-semibold text-amber-700 dark:text-amber-300" : "")}>{g.late_sessions}</td>
                <td className="py-2 pr-3 tabular-nums">
                  <span className={g.red ? "font-semibold text-rose-700 dark:text-rose-300" : ""}>{g.red}</span>
                  {" / "}
                  <span className={g.amber ? "font-semibold text-amber-700 dark:text-amber-300" : ""}>{g.amber}</span>
                </td>
                <td className="py-2 text-xs">{g.lessons_set ? <span className="text-emerald-700 dark:text-emerald-300">girildi</span> : <span className="text-muted-foreground">yok</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Trend({ d }: { d: InstitutionPoolOverviewResponse }) {
  return (
    <Card className="h-full p-4" data-section="institution:pool:trend">
      <SectionTitle icon={TrendingUp} sub="Son 4 haftada kapanan dönemlerin ortalama yüzdesi (kapanış haftasına göre; tatil dönemleri hariç).">
        <ColumnHint label="Haftalara göre" hint="Her sütun bir hafta (Pazartesi başlangıç). Değer o hafta kapanan dönemlerin ortalama havuz yüzdesi; sütun altındaki sayı kaç dönem kapandığı." />
      </SectionTitle>
      <div className="flex h-40 items-end gap-3">
        {d.trend.map((t) => (
          <div key={t.week_start} className="flex flex-1 flex-col items-center gap-1">
            <span className={cn("text-xs font-semibold tabular-nums", tone(t.avg_pct))}>{pct(t.avg_pct)}</span>
            <div className="flex h-24 w-full items-end rounded-md bg-slate-100 dark:bg-slate-800">
              <div className={cn("w-full rounded-md", barTone(t.avg_pct))} style={{ height: `${t.avg_pct ?? 0}%` }} />
            </div>
            <span className="text-xs text-foreground">{fmt(t.week_start)}</span>
            <span className="text-[11px] text-muted-foreground">{t.periods} dönem</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ ders

function Subjects({ d }: { d: InstitutionPoolOverviewResponse }) {
  if (!d.subjects.length) return null;
  const max = Math.max(...d.subjects.map((s) => s.total), 1);
  return (
    <Card className="p-4" data-section="institution:pool:subjects">
      <SectionTitle icon={BookOpen} sub="Açık dönem havuzlarındaki birimler derse göre. Çubuğun uzunluğu derse verilen hacim, dolu kısmı biten birim.">
        <ColumnHint label="Derslere göre" hint="Aynı adlı dersler (farklı rehberlerin) birleşir. Birim = test sayısı (etkinlik/deneme 1). Onay bekleyen öğrenci kalemleri dahil değil." />
      </SectionTitle>
      <ul className="space-y-2.5">
        {d.subjects.map((s) => {
          const c = subjectColors(s.name);
          return (
            <li key={s.name}>
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="inline-flex items-center gap-2">
                  <span className="rounded px-1.5 py-0.5 text-xs font-semibold text-white" style={{ backgroundColor: c.chipStrong }}>{s.name}</span>
                  <span className="text-xs text-muted-foreground">{s.students} öğrenci</span>
                </span>
                <span className="tabular-nums text-foreground"><b>{s.done}</b> / {s.total} birim · <span className={tone(s.pct)}>%{s.pct}</span></span>
              </div>
              <div className="mt-1 h-2.5 rounded-full bg-slate-100 dark:bg-slate-800" style={{ width: `${Math.max(8, (100 * s.total) / max)}%` }} aria-hidden>
                <div className="h-2.5 rounded-full" style={{ width: `${s.pct}%`, backgroundColor: c.rail }} />
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

// ------------------------------------------------------------------ geciken

function Late({ d }: { d: InstitutionPoolOverviewResponse }) {
  return (
    <Card className="p-4" data-section="institution:pool:late">
      <SectionTitle icon={CalendarClock} sub="Beklenen seans günü 3+ gün geçen (sarı) ya da 14 gündür seanssız (kırmızı) öğrenciler. Dönem uzar; öğrenci havuzdan çalışmaya devam eder.">
        Seansı geciken öğrenciler ({d.late.length})
      </SectionTitle>
      {d.late.length === 0 ? (
        <p className="text-sm text-muted-foreground">Geciken seans yok.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {d.late.map((r) => (
            <li key={r.student_id} className={cn("rounded-lg border border-l-4 p-3 text-sm",
              r.level === "red" ? "border-l-rose-600" : "border-l-amber-500")}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-foreground">{r.student_name}</span>
                {r.class_group && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">{r.class_group}</span>}
                <span className={cn("ml-auto rounded px-1.5 py-0.5 text-xs font-medium",
                  r.level === "red" ? "bg-rose-700 text-white" : "bg-amber-400 text-amber-950")}>
                  {r.level === "red" ? `${r.days_open} gün seanssız` : `${r.late_days} gün gecikti`}
                </span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">rehber: {r.coach_name}</div>
              <div className="mt-1 text-xs text-foreground">
                dönem {fmt(r.opened_on)} · beklenen {fmt(r.expected_next_on)} · havuz <span className={tone(r.pct)}>{pct(r.pct)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ rehber yükü

function Coaches({ d }: { d: InstitutionPoolOverviewResponse }) {
  return (
    <Card className="p-4" data-section="institution:pool:coaches">
      <SectionTitle icon={ListChecks} sub="Yük = bugünkü görüşme + geciken seans + kırmızı öğrenci (K55). En yüklü rehber üstte.">Rehber yükü</SectionTitle>
      <div className="relative overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted-foreground">
            <tr>
              <th className="py-1 pr-3">Rehber</th>
              <th className="py-1 pr-3"><ColumnHint label="Öğrenci" hint="Rehberin havuz modlu aktif öğrencisi." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Açık dönem %" hint="Rehberin öğrencilerinin açık dönem yüzdelerinin ortalaması." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Bugün görüşme" hint="Bugüne planlı randevusu olan ya da beklenen seans günü bugün olan öğrenci (aynı öğrenci bir kez sayılır)." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Geciken" hint="Beklenen seans günü 3+ gün geçen ya da 14 gündür seanssız öğrenci." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Kırmızı / sarı" hint="Ana sinyali kırmızı / sarı olan öğrenci." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Onay bekleyen" hint="Öğrencilerin eklediği, rehberin seansta onaylaması gereken kalem sayısı." /></th>
              <th className="py-1 pr-3"><ColumnHint label="Toplu / kağıt" hint="Toplu işaretleme sinyali olan öğrenci / uygulamaya kayıt girmeyen (kağıt) öğrenci." /></th>
              <th className="py-1"><ColumnHint label="Yük" hint="Bugünkü görüşme + geciken seans + kırmızı." /></th>
            </tr>
          </thead>
          <tbody>
            {d.coaches_rows.map((c) => (
              <tr key={c.coach_id} className="border-t">
                <td className="py-2 pr-3 font-medium text-foreground">{c.coach_name}</td>
                <td className="py-2 pr-3 tabular-nums">{c.students}</td>
                <td className={cn("py-2 pr-3 tabular-nums", tone(c.avg_open_pct))}>{pct(c.avg_open_pct)}</td>
                <td className="py-2 pr-3 tabular-nums">{c.today_sessions}</td>
                <td className={cn("py-2 pr-3 tabular-nums", c.late_sessions ? "font-semibold text-amber-700 dark:text-amber-300" : "")}>{c.late_sessions}</td>
                <td className="py-2 pr-3 tabular-nums">
                  <span className={c.red ? "font-semibold text-rose-700 dark:text-rose-300" : ""}>{c.red}</span>{" / "}
                  <span className={c.amber ? "font-semibold text-amber-700 dark:text-amber-300" : ""}>{c.amber}</span>
                </td>
                <td className={cn("py-2 pr-3 tabular-nums", c.pending_approval ? "font-semibold text-amber-700 dark:text-amber-300" : "")}>{c.pending_approval}</td>
                <td className="py-2 pr-3 tabular-nums">{c.bulk} / {c.paper}</td>
                <td className="py-2">
                  <span className={cn("inline-flex min-w-8 justify-center rounded-md px-2 py-0.5 font-semibold tabular-nums",
                    c.load >= 4 ? "bg-rose-700 text-white" : c.load >= 2 ? "bg-amber-400 text-amber-950" : "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100")}>{c.load}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
