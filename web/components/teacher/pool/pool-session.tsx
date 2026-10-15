"use client";

/**
 * Havuz SEANS EKRANI (K18–K22) — tek ekran, sekme yok:
 *   tek cümle özet → kalem kalem yapıldı/yapılmadı (öğretmen ödevi ayrı renk; rehber seansta
 *   "işaretlendi" yazar, öğrenci kaydından AYRI sayaç) → kaçınılan kalemler → deneme şeridi
 *   (3 satır) → gündem kuyruğu → önceki seans notu → "Seansı bitir": kalem kalem devir + yeni
 *   dönem + seans kaydı.
 */
import * as React from "react";
import { toast } from "sonner";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, BookOpen, Check, ClipboardList, FileText, Lock, TrendingDown, TrendingUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useCloseTopic, useReopenTopic } from "@/lib/hooks/use-teacher-mutations";
import { PoolFlagsCard } from "./pool-flags-card";
import { SubjectTag, subjectColors } from "@/components/shared/subject-tag";
import { DayStrip, SplitBar, SubjectProgress, aggregateSubjects, itemUnitSplit } from "./pool-progress";
import {
  getPoolSession, poolSessionKey, SOURCE_LABELS, UNIT_LABELS, useFinishSession, useSessionMark,
  type PoolSessionResponse, type SessionItemOut,
} from "@/lib/api/pool";

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d + n);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

function itemTitle(i: SessionItemOut): string {
  if (i.section_label && i.book_name) return `${i.book_name} — ${i.section_label}`;
  if (i.topic_name) return i.topic_name + (i.book_name ? ` (${i.book_name})` : "");
  return i.label ?? "—";
}

function Ring({ pct }: { pct: number }) {
  const r = 42;
  const c = 2 * Math.PI * r;
  const p = Math.max(0, Math.min(100, pct));
  const stroke = p >= 70 ? "#059669" : p >= 40 ? "#d97706" : "#e11d48";
  return (
    <svg viewBox="0 0 100 100" className="size-28 shrink-0" aria-hidden>
      <circle cx="50" cy="50" r={r} fill="none" strokeWidth="10" className="stroke-muted" />
      <circle cx="50" cy="50" r={r} fill="none" strokeWidth="10" stroke={stroke} strokeLinecap="round"
              strokeDasharray={`${(c * p) / 100} ${c}`} transform="rotate(-90 50 50)" />
      <text x="50" y="50" textAnchor="middle" dominantBaseline="central" className="fill-foreground text-[22px] font-bold">%{p}</text>
    </svg>
  );
}

export function PoolSession({ studentId, initial }: { studentId: number; initial: PoolSessionResponse }) {
  const q = useQuery({ queryKey: poolSessionKey(studentId), queryFn: () => getPoolSession(studentId), initialData: initial });
  const data = q.data ?? initial;
  const [finishOpen, setFinishOpen] = React.useState(false);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 p-4" data-section="pool:session">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Link href={`/teacher/students/${studentId}/pool`} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="size-4" aria-hidden /> Havuz editörü
          </Link>
          <h1 className="text-2xl font-semibold text-foreground">Seans · {data.student.full_name}</h1>
          <p className="text-sm text-muted-foreground">Öğrenci karşında: ders ders bak, kaynağına bakıp işaretle, sonra seansı bitir ve yeni havuzu yaz.</p>
        </div>
        {data.period && (
          <Button onClick={() => setFinishOpen(true)} className="bg-cyan-700 text-white hover:bg-cyan-800">Seansı bitir</Button>
        )}
      </header>

      {!data.period ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          Açık dönem yok. <Link href={`/teacher/students/${studentId}/pool`} className="underline">Havuz editöründen</Link> dönem aç.
        </p>
      ) : (
        <>
          <Hero data={data} />
          <SubjectProgress items={data.items} />
          <DayStrip studentId={studentId} periodId={data.period.id} items={data.items} today={data.today} expectedNextOn={data.period.summary.expected_next_on} />
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
            <ItemList studentId={studentId} data={data} />
            <aside className="min-w-0 space-y-4">
              <PoolFlagsCard flags={data.flags} />
              <AvoidedCard data={data} />
              <ExamStrip studentId={studentId} data={data} />
              <AgendaCard data={data} />
              <PreviousSessionCard data={data} />
            </aside>
          </div>
          <FinishDialog studentId={studentId} data={data} open={finishOpen} onOpenChange={setFinishOpen} />
        </>
      )}
    </div>
  );
}

function Hero({ data }: { data: PoolSessionResponse }) {
  const p = data.period!;
  const s = p.summary;
  const all = data.items.filter((i) => i.counts).map(itemUnitSplit);
  const total = all.reduce((a, u) => a + u.total, 0);
  const student = all.reduce((a, u) => a + u.student, 0);
  const session = all.reduce((a, u) => a + u.session, 0);
  return (
    <div className="flex flex-wrap items-center gap-5 rounded-xl border bg-card p-5" data-section="pool:session:headline">
      <Ring pct={s.pct} />
      <div className="min-w-[16rem] flex-1 space-y-3">
        <p className="text-base font-medium text-foreground">{data.headline}</p>
        <div className="space-y-1.5">
          <SplitBar total={total} student={student} session={session} color="#0e7490" className="h-3" />
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-cyan-700" /> öğrenci kaydı <b className="text-foreground">{student}</b></span>
            <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-cyan-700/40" /> seansta işaretlenen <b className="text-foreground">{session}</b></span>
            <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-muted-foreground/30" /> kalan <b className="text-foreground">{Math.max(0, total - student - session)}</b> birim</span>
          </div>
        </div>
      </div>
      <dl className="grid w-full grid-cols-2 gap-2 sm:w-auto">
        <Stat label="Dönem" value={`${p.days_open + 1}. gün`} sub={`${fmtDate(p.opened_on)} açıldı`} />
        <Stat label="Kalem" value={`${s.items_done}/${s.items_total}`} sub="tamamlandı" />
        <Stat label="Seansa" value={`${s.days_left} gün`} sub={s.expected_next_on ? `beklenen ${fmtDate(s.expected_next_on)}` : "beklenen gün yok"} />
        <Stat label="Günde gereken" value={`${s.per_day_needed}`} sub="birim" />
      </dl>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="min-w-[7.5rem] rounded-lg border bg-background px-3 py-2">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold text-foreground">{value}</dd>
      <dd className="text-[11px] text-muted-foreground">{sub}</dd>
    </div>
  );
}

function ItemList({ studentId, data }: { studentId: number; data: PoolSessionResponse }) {
  const mark = useSessionMark(studentId);
  const groups = new Map<string, SessionItemOut[]>();
  for (const it of data.items) {
    const g = groups.get(it.subject_name) ?? [];
    g.push(it);
    groups.set(it.subject_name, g);
  }
  const order = new Map(aggregateSubjects(data.items).map((a, i) => [a.name, i]));
  return (
    <section className="min-w-0 rounded-xl border bg-card p-4" data-section="pool:session:items">
      <h2 className="flex items-center gap-2 font-semibold text-foreground">
        <ClipboardList className="size-4" aria-hidden /> Kalem kalem
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">
        “Öğrenci” = kendi kaydı · “Seansta” = sen kaynağına bakıp işaretledin (kitaplı kalemde kitap sayacına da yazılır).
        <span className="ml-1 italic text-violet-700 dark:text-violet-300">Eğik yazı = ders öğretmeninin ödevi.</span>
      </p>
      <div className="mt-3 space-y-4">
        {[...groups.entries()].sort((a, b) => (order.get(a[0]) ?? 99) - (order.get(b[0]) ?? 99)).map(([name, list]) => {
          const c = subjectColors(name);
          return (
            <div key={name}>
              <div className="mb-1.5 flex items-center gap-2">
                <SubjectTag name={name} />
                <span className="text-xs text-muted-foreground">{list.filter((i) => i.remaining === 0).length}/{list.length} kalem bitti</span>
              </div>
              <ul className="space-y-1.5">
                {list.map((it) => (
                  <ItemRow key={it.id} it={it} rail={c.rail} studentId={studentId}
                           onMark={(n) => mark.mutate({ item_id: it.id, count: n })} busy={mark.isPending} />
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ItemRow({ it, rail, studentId, onMark, busy }: { it: SessionItemOut; rail: string; studentId: number; onMark: (c: number) => void; busy: boolean }) {
  const maxMark = Math.max(0, it.quantity - it.completed);
  const [val, setVal] = React.useState(String(it.session_marked));
  const done = it.remaining === 0;
  const u = itemUnitSplit(it);
  return (
    <li
      className={cn(
        "rounded-lg border border-l-4 bg-background px-3 py-2 text-sm",
        done && "bg-emerald-500/5",
        it.avoided && !done && "border-amber-400 dark:border-amber-500/50",
      )}
      style={{ borderLeftColor: rail }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn("shrink-0", done ? "text-emerald-700 dark:text-emerald-300" : "text-muted-foreground")} title={done ? "Tamamlandı" : "Kalan var"}>
          {done ? <Check className="size-4" aria-hidden /> : <span className="inline-block size-4 rounded-full border" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className={cn("break-words font-medium text-foreground", it.teacher_homework && "italic text-violet-800 dark:text-violet-200")}>{itemTitle(it)}</div>
          <div className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
            <span>{it.quantity} {UNIT_LABELS[it.unit]}</span>
            <span>· öğrenci {it.completed}</span>
            <span>· seansta {it.session_marked}</span>
            <span>· kalan {it.remaining}</span>
            {it.source !== "rehber" && <span>· {SOURCE_LABELS[it.source]}{it.approval === "bekliyor" ? " (onay bekliyor)" : ""}</span>}
            {it.avoided && <span className="text-amber-800 dark:text-amber-200">· {it.avoided_reason}</span>}
          </div>
        </div>
        {it.book_id && (
          <Link
            href={`/teacher/students/${studentId}#books`}
            className="text-xs text-cyan-700 underline-offset-2 hover:underline dark:text-cyan-300"
            title="Kitaba bak (koltuk ızgarası Kitaplar sekmesinde)"
          >
            <BookOpen className="inline size-3.5" aria-hidden /> kitaba bak
          </Link>
        )}
        {it.closure_topic_id ? <TopicCloseButton studentId={studentId} topicId={it.closure_topic_id} closed={!!it.topic_closed} /> : null}
        {it.unit !== "etkinlik" ? (
          <label className="flex items-center gap-1 text-xs text-muted-foreground">
            seansta
            <Input
              value={val}
              inputMode="numeric"
              onChange={(e) => setVal(e.target.value)}
              onBlur={() => {
                const n = Number(val);
                if (Number.isInteger(n) && n >= 0 && n <= maxMark && n !== it.session_marked) onMark(n);
                else setVal(String(it.session_marked));
              }}
              className="h-7 w-14 text-center"
              aria-label="Seansta işaretlenen"
              disabled={busy}
            />
            <span>/ {maxMark}</span>
          </label>
        ) : (
          <Button size="sm" variant={it.session_marked > 0 ? "outline" : "default"} disabled={busy}
                  onClick={() => onMark(it.session_marked > 0 ? 0 : 1)}>
            {it.session_marked > 0 ? "yapıldı ✓" : "yapıldı"}
          </Button>
        )}
      </div>
      {it.unit !== "etkinlik" && <SplitBar total={u.total} student={u.student} session={u.session} color={rail} className="mt-2 h-1.5" />}
    </li>
  );
}

/** Seansta öğrenciyle konuşup konuyu kapat (müfredatta "Tamamlandı"; kayıtlı olmayan kaynaktan çalışıldıysa da). */
function TopicCloseButton({ studentId, topicId, closed }: { studentId: number; topicId: number; closed: boolean }) {
  const closeM = useCloseTopic(studentId);
  const reopenM = useReopenTopic(studentId);
  const busy = closeM.isPending || reopenM.isPending;
  return closed ? (
    <button
      type="button"
      disabled={busy}
      onClick={() => reopenM.mutate({ topicId })}
      className="inline-flex items-center gap-1 rounded-md bg-emerald-700 px-2 py-0.5 text-[11px] font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
      title="Konu kapalı (müfredatta tamamlandı). Yanlışsa geri aç."
    >
      <Lock className="size-3" aria-hidden /> konu kapalı · geri aç
    </button>
  ) : (
    <button
      type="button"
      disabled={busy}
      onClick={() => closeM.mutate({ topicId })}
      className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium text-foreground hover:bg-muted disabled:opacity-50"
      title="Öğrenci bu konuyu bitirdi (kayıtlı olmayan bir kaynaktan çalışmış olsa bile). Müfredatta Tamamlandı olur; geri alınabilir."
    >
      <Lock className="size-3" aria-hidden /> Konuyu kapat
    </button>
  );
}

function AvoidedCard({ data }: { data: PoolSessionResponse }) {
  if (!data.avoided.length) return null;
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100" data-section="pool:session:avoided">
      <h2 className="flex items-center gap-2 font-semibold"><AlertTriangle className="size-4" aria-hidden /> Kaçınılan kalemler</h2>
      <ul className="mt-1 list-disc pl-5 text-sm">
        {data.avoided.map((it) => <li key={it.id}>{itemTitle(it)} — {it.avoided_reason}</li>)}
      </ul>
      <p className="mt-1 text-xs">Seansta konuş: zor mu geldi, kaynak mı yok, zaman mı kalmadı?</p>
    </div>
  );
}

function ExamStrip({ studentId, data }: { studentId: number; data: PoolSessionResponse }) {
  const e = data.exam;
  if (!e) return null;
  const up = (e.delta ?? 0) >= 0;
  return (
    <Link href={`/teacher/students/${studentId}#exams`} className="block rounded-lg border bg-card p-4 hover:bg-accent" data-section="pool:session:exam">
      <h2 className="flex items-center gap-2 font-semibold text-foreground">
        {up ? <TrendingUp className="size-4 text-emerald-600 dark:text-emerald-300" aria-hidden /> : <TrendingDown className="size-4 text-rose-600 dark:text-rose-300" aria-hidden />}
        Deneme · {e.title} ({fmtDate(e.exam_date)}){!e.in_period && <span className="text-xs font-normal text-muted-foreground">· bu dönemden önce</span>}
      </h2>
      <div className="mt-1 space-y-0.5 text-sm text-foreground">
        <p>
          Net <strong>{e.net.toLocaleString("tr-TR")}</strong>
          {e.delta != null && <span className={up ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"}> ({e.delta > 0 ? "+" : ""}{e.delta.toLocaleString("tr-TR")} · {e.prev_title})</span>}
          {e.delta == null && <span className="text-muted-foreground"> · aynı türde önceki deneme yok</span>}
        </p>
        <p>Yanlış konular: {e.wrong_topics.length ? e.wrong_topics.map((w) => `${w.name} (${w.wrong})`).join(", ") : "konulu yanlış yok"}</p>
        <p className={e.studied_but_wrong.length ? "text-rose-700 dark:text-rose-300" : "text-muted-foreground"}>
          Bu dönem çalıştığı konudan denemede kaçırdığı: {e.studied_but_wrong.length ? e.studied_but_wrong.map((w) => `${w.name} (${w.wrong})`).join(", ") : "yok"}
        </p>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">Dokun → Denemeler sekmesi</p>
    </Link>
  );
}

function AgendaCard({ data }: { data: PoolSessionResponse }) {
  if (!data.agenda_queue.length) return null;
  return (
    <div className="rounded-lg border bg-card p-4 text-sm" data-section="pool:session:agenda">
      <h2 className="font-semibold text-foreground">Seansa eklenenler</h2>
      <ul className="mt-1 list-disc pl-5 text-foreground">
        {data.agenda_queue.map((a) => <li key={a.id}>{a.text}</li>)}
      </ul>
    </div>
  );
}

function PreviousSessionCard({ data }: { data: PoolSessionResponse }) {
  const p = data.previous_session;
  if (!p) return null;
  return (
    <div className="rounded-lg border bg-card p-4 text-sm" data-section="pool:session:previous">
      <h2 className="flex items-center gap-2 font-semibold text-foreground"><FileText className="size-4" aria-hidden /> Önceki seans · {fmtDate(p.session_date)}</h2>
      <p className="mt-1 text-foreground"><span className="text-muted-foreground">Gündem:</span> {p.agenda || "—"}</p>
      {p.coach_note && <p className="text-foreground"><span className="text-muted-foreground">Not:</span> {p.coach_note}</p>}
      {p.next_change && <p className="text-foreground"><span className="text-muted-foreground">Değiştirilecek:</span> {p.next_change}</p>}
    </div>
  );
}

function FinishDialog({ studentId, data, open, onOpenChange }: {
  studentId: number; data: PoolSessionResponse; open: boolean; onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const finish = useFinishSession(studentId);
  const leftovers = data.items.filter((i) => i.remaining > 0 && i.counts && i.approval !== "reddedildi");
  const [carry, setCarry] = React.useState<Record<number, number | null>>({});
  const [next, setNext] = React.useState(addDays(data.today, 7));
  const [agenda, setAgenda] = React.useState(data.headline);
  const [note, setNote] = React.useState("");
  const [change, setChange] = React.useState("");
  const [mood, setMood] = React.useState<number | null>(null);
  const [record, setRecord] = React.useState(true);
  // 2026-10-15: "Bu seansla gün gün programa geç" — yeni dönem açılmaz, devir yapılmaz.
  const [toGunGun, setToGunGun] = React.useState(false);
  const leftoverUnits = leftovers.reduce((a, i) => a + i.remaining, 0);

  function toggle(it: SessionItemOut) {
    setCarry((prev) => {
      const n = { ...prev };
      if (it.id in n) delete n[it.id]; else n[it.id] = it.remaining;
      return n;
    });
  }
  function submit() {
    finish.mutate(
      {
        closed_on: data.today,
        expected_next_on: next || null,
        carry: toGunGun ? [] : Object.entries(carry).map(([id, qty]) => ({ item_id: Number(id), quantity: qty })),
        record_session: record,
        switch_to_gun_gun: toGunGun,
        agenda: agenda || null,
        coach_note: note || null,
        next_change: change || null,
        mood,
      },
      {
        onSuccess: () => {
          onOpenChange(false);
          if (toGunGun) {
            toast.success("Seans bitti — öğrenci gün gün programa geçti", { description: "İlk haftalık programı hazırla." });
            router.push(`/teacher/students/${studentId}/week`);
          } else {
            toast.success("Seans bitti — yeni dönem açıldı");
            router.push(`/teacher/students/${studentId}/pool?mod=duzenle`); // sıradaki iş: yeni havuzu yazmak
          }
        },
      },
    );
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Seansı bitir</DialogTitle>
          <DialogDescription>
            {toGunGun
              ? "Bu dönem kapanır, seans kaydı yazılır ve öğrenci gün gün programa geçer. Yeni dönem açılmaz."
              : "Bu dönem kapanır, seans kaydı yazılır, bugün yeni dönem açılır. Kalanı olan kalemleri tek tek seç: ekle, miktarı değiştir ya da bırak."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-sm">
          <label className="flex items-start gap-2 rounded-md border px-3 py-2" data-testid="finish-to-gun-gun">
            <input type="checkbox" className="mt-0.5" checked={toGunGun} onChange={(e) => setToGunGun(e.target.checked)} />
            <span>
              <span className="font-medium text-foreground">Bu seansla gün gün programa geç</span>
              <span className="block text-xs text-muted-foreground">Haftalık havuz biter; bundan sonra programı günlere sen yazarsın.</span>
            </span>
          </label>
          {toGunGun && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100" data-section="pool:finish:switch">
              <p className="font-semibold">Geçişte ne olur?</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                <li>Bu döneme kadar çözülenler müfredata ve kitap sayacına yazılmıştı — aynen kalır.</li>
                <li>
                  {leftovers.length
                    ? `Kalanı olan ${leftovers.length} kalem (${leftoverUnits} birim) havuzdan çıkar; dönem geçmişinde iz olarak durur, devredilmez.`
                    : "Havuzda kalan kalem yok."}
                </li>
                <li>Bugün ve sonrası için kaba alınıp hiç dokunulmamış görevler silinir; kısmen çözülmüş görev kalır.</li>
                <li>İlk 3 gün “Programı yok” uyarısı kırmızı yerine sarı görünür — ilk programı hazırlama süresi.</li>
              </ul>
            </div>
          )}
          {!toGunGun && (
          <div>
            <div className="mb-1 font-medium text-foreground">Devredilecek kalemler ({leftovers.length} aday)</div>
            {leftovers.length === 0 && <p className="text-xs text-muted-foreground">Kalan yok — havuz bitti.</p>}
            <ul className="space-y-1">
              {leftovers.map((it) => (
                <li key={it.id} className="flex flex-wrap items-center gap-2 rounded-md border px-2 py-1.5">
                  <input type="checkbox" checked={it.id in carry} onChange={() => toggle(it)} aria-label="Devret" />
                  <span className="min-w-0 flex-1 break-words text-foreground">{itemTitle(it)} <span className="text-xs text-muted-foreground">· kalan {it.remaining} {UNIT_LABELS[it.unit]}</span></span>
                  {it.id in carry && it.unit !== "etkinlik" && (
                    <Input
                      value={String(carry[it.id] ?? "")}
                      inputMode="numeric"
                      onChange={(e) => { const n = Number(e.target.value); setCarry((p) => ({ ...p, [it.id]: Number.isInteger(n) && n > 0 ? n : null })); }}
                      className="h-7 w-16 text-center"
                      aria-label="Devir miktarı"
                    />
                  )}
                </li>
              ))}
            </ul>
          </div>
          )}
          {!toGunGun && (
          <label className="block">
            <span className="text-xs text-muted-foreground">Beklenen sonraki seans</span>
            <Input type="date" value={next} onChange={(e) => setNext(e.target.value)} className="mt-1 w-44" />
          </label>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={record} onChange={(e) => setRecord(e.target.checked)} /> Seans kaydı yaz (Seanslar sekmesi + tahsilat)
          </label>
          {record && (
            <div className="space-y-2">
              <label className="block"><span className="text-xs text-muted-foreground">Gündem</span>
                <textarea value={agenda} onChange={(e) => setAgenda(e.target.value)} rows={2} className="mt-1 w-full rounded-md border bg-background p-2 text-sm" /></label>
              <label className="block"><span className="text-xs text-muted-foreground">Görüşme notu (yalnız sana)</span>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} className="mt-1 w-full rounded-md border bg-background p-2 text-sm" /></label>
              <label className="block"><span className="text-xs text-muted-foreground">Değiştirilecek</span>
                <Input value={change} onChange={(e) => setChange(e.target.value)} className="mt-1" /></label>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                Ruh hali
                {[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} type="button" onClick={() => setMood(mood === n ? null : n)}
                          className={cn("size-7 rounded-full border text-sm", mood === n ? "border-cyan-600 bg-cyan-600 text-white" : "hover:bg-accent")}>{n}</button>
                ))}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Vazgeç</Button>
          <Button onClick={submit} disabled={finish.isPending} data-testid="finish-submit"
                  className={toGunGun ? "bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white" : undefined}>
            {toGunGun ? "Bitir ve gün gün programa geç" : "Bitir ve yeni dönemi aç"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
