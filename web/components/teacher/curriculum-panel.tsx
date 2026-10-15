"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  CircleSlash,
  Clock,
  Inbox,
  Info,
  Loader2,
  Lock,
  MapPin,
  Plus,
  Target,
} from "lucide-react";

import { getTeacherStudentCurriculum, teacherKeys } from "@/lib/api/teacher";
import type {
  CurriculumGradeItem,
  CurriculumProgressResponse,
  CurriculumProjectionItem,
  CurriculumSubjectItem,
  CurriculumTopicItem,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";
import { subjectColors } from "@/components/shared/subject-tag";
import { useCloseTopic, useReopenTopic } from "@/lib/hooks/use-teacher-mutations";
import { useAddPoolItem } from "@/lib/api/pool";

type Status = CurriculumTopicItem["status"];

// Dolgulu rozet + bar tonları (küçük rozette ton+dark çifti yerine dolgu — kontrast).
// "kaynak_yok" DURUM DEĞİL, kaynak bilgisidir: konu başlanmadı + kitabı yok. Görünüşte "Başlanmadı"
// (koç kaynaksız/havuzdan verebilir); kitapsızlık satırda ayrı işaretle söylenir (2026-10-14).
const STATUS: Record<Status, { label: string; badge: string; bar: string; Icon: React.ElementType }> = {
  tamamlandi: { label: "Tamamlandı", badge: "bg-emerald-700 text-white", bar: "bg-emerald-500", Icon: CheckCircle2 },
  devam: { label: "Devam ediyor", badge: "bg-amber-500 text-amber-950", bar: "bg-amber-400", Icon: Clock },
  planlandi: { label: "Planlandı", badge: "bg-sky-700 text-white", bar: "bg-sky-500", Icon: CircleDashed },
  baslanmadi: { label: "Başlanmadı", badge: "bg-slate-600 text-white", bar: "bg-slate-300 dark:bg-slate-600", Icon: CircleDashed },
  kaynak_yok: { label: "Başlanmadı", badge: "bg-slate-600 text-white", bar: "bg-slate-300 dark:bg-slate-600", Icon: CircleDashed },
};
const BAR_ORDER: Status[] = ["tamamlandi", "devam", "planlandi", "baslanmadi"];
const LEGEND: { st: Status; label: string }[] = [
  { st: "tamamlandi", label: "Tamamlandı" },
  { st: "devam", label: "Devam ediyor" },
  { st: "planlandi", label: "Planlandı" },
  { st: "baslanmadi", label: "Başlanmadı" },
];

function countStatuses(topics: CurriculumTopicItem[]): Record<Status, number> {
  const c: Record<Status, number> = { tamamlandi: 0, devam: 0, planlandi: 0, baslanmadi: 0, kaynak_yok: 0 };
  for (const t of topics) c[t.status === "kaynak_yok" ? "baslanmadi" : t.status] += 1;
  return c;
}

/** Konu odak sınıfa mı ait? Odak yoksa (12/mezun) hepsi; sınıfı belirsiz konu odaktadır. */
function inFocus(t: CurriculumTopicItem, focus: number | null): boolean {
  // Sunucu karar verir (TYT/AYT dersinde tüm konular odakta); eski yanıtta sınıfa bak
  if (t.in_focus != null) return t.in_focus;
  return focus == null || t.grade_level == null || t.grade_level === focus;
}

function groupOf(name: string): "TYT" | "AYT" | "OKUL" {
  if (/^TYT\b/i.test(name)) return "TYT";
  if (/^AYT\b/i.test(name)) return "AYT";
  return "OKUL";
}
const GROUP_LABEL = { TYT: "TYT dersleri", AYT: "AYT dersleri", OKUL: "Okul dersleri" } as const;

export function CurriculumPanel({ studentId }: { studentId: number }) {
  const q = useQuery<CurriculumProgressResponse>({
    queryKey: teacherKeys.studentCurriculum(studentId),
    queryFn: () => getTeacherStudentCurriculum(studentId),
    staleTime: 30_000,
  });
  const [picked, setPicked] = React.useState<number | null>(null);

  if (q.isLoading) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        <Loader2 className="mx-auto size-6 animate-spin" aria-hidden />
      </div>
    );
  }
  const data = q.data;
  if (!data || data.subjects.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-muted/20 p-6 text-sm text-muted-foreground">
        Bu öğrencinin sınıfı ve sınav türü için müfredat dersi bulunamadı. Profilde sınıf, alan ve
        müfredat modelinin doğru girildiğini kontrol et.
      </div>
    );
  }

  // Varsayılan ders: en çok çalışılan (işlenen + bekleyen) — yoksa ilk ders
  const workScore = (s: CurriculumSubjectItem) => s.started_topics * 10 + (s.pool_remaining ?? 0) + (s.total_topics - s.no_resource_topics);
  const defaultId = [...data.subjects].sort((a, b) => workScore(b) - workScore(a))[0].subject_id;
  const activeId = data.subjects.some((s) => s.subject_id === picked) ? picked! : defaultId;
  const active = data.subjects.find((s) => s.subject_id === activeId)!;

  const groups = (["TYT", "AYT", "OKUL"] as const)
    .map((g) => ({
      g,
      items: data.subjects
        .filter((s) => groupOf(s.name) === g)
        .sort((a, b) => Number(b.total_topics > 0) - Number(a.total_topics > 0)),
    }))
    .filter((x) => x.items.length > 0);
  const focus = data.focus_grade ?? null;
  const allTopics = data.subjects.flatMap((s) => s.topics).filter((t) => inFocus(t, focus));
  const totals = countStatuses(allTopics);
  const havuz = data.program_mode === "havuz";
  const poolOpen = havuz && data.pool_period_id != null;

  return (
    <div className="space-y-4" data-section="curriculum-panel">
      <Overview data={data} totals={totals} havuz={havuz} />

      <div className="grid gap-4 lg:grid-cols-[minmax(260px,320px)_1fr]">
        <nav className="space-y-3" aria-label="Dersler" data-section="curriculum:subjects">
          {groups.map(({ g, items }) => (
            <div key={g} className="space-y-1.5">
              <p className="px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {GROUP_LABEL[g]} <span className="tabular-nums">({items.length})</span>
              </p>
              {items.map((s) => (
                <SubjectCard key={s.subject_id} s={s} focus={focus} active={s.subject_id === activeId} onClick={() => setPicked(s.subject_id)} />
              ))}
            </div>
          ))}
        </nav>
        <SubjectDetail key={active.subject_id} s={active} focus={focus} studentId={studentId} poolOpen={poolOpen} havuz={havuz} />
      </div>

      {(data.pool_unlinked?.length ?? 0) > 0 ? (
        <details className="rounded-xl border border-amber-200 bg-amber-50/50 dark:border-amber-500/30 dark:bg-amber-500/10" data-section="curriculum:pool-unlinked">
          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-amber-900 dark:text-amber-200">
            Havuzda konusu belirsiz kalemler ({data.pool_unlinked!.length}){" "}
            <span className="font-normal text-amber-800 dark:text-amber-300">— hangi konu olduğu bilinmediği için haritaya işlenmez</span>
          </summary>
          <ul className="space-y-1 px-4 pb-2 text-xs">
            {data.pool_unlinked!.map((u) => (
              <li key={u.item_id} className="text-amber-900 dark:text-amber-200">
                {u.subject_name} · <span className="font-medium">{u.title}</span> · {u.done}/{u.quantity}
              </li>
            ))}
          </ul>
          <p className="px-4 pb-3 text-[11px] text-amber-800 dark:text-amber-300">
            Havuz editöründe bu kalemleri kaldırıp konusu seçilerek yeniden ekle; çalışılan testler o konuya yazılır.
          </p>
        </details>
      ) : null}

      {data.extras.length > 0 ? (
        <details className="rounded-xl border border-amber-200 bg-amber-50/50 dark:border-amber-500/30 dark:bg-amber-500/10">
          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-amber-900 dark:text-amber-200">
            Müfredata eşleşmemiş kitap üniteleri ({data.extras.length}){" "}
            <span className="font-normal text-amber-800 dark:text-amber-300">
              — resmi konuya bağlanmamış; haritada sayılmaz
            </span>
          </summary>
          <ul className="space-y-1 px-4 pb-3 text-xs">
            {data.extras.map((e) => (
              <li key={e.section_id} className="text-amber-900 dark:text-amber-200">
                {e.book_name} · <span className="font-medium">{e.label}</span>
                {e.completed > 0 ? ` · ${e.completed} test çözülmüş` : ""}
              </li>
            ))}
          </ul>
          <p className="px-4 pb-3 text-[11px] text-amber-800 dark:text-amber-300">
            Kütüphanede “Müfredata eşleştir” ile bağlarsan haritaya girerler.
          </p>
        </details>
      ) : null}
    </div>
  );
}

/* ---------------------------------------------------------------- Özet */

function Ring({ pct, size = 92 }: { pct: number; size?: number }) {
  const r = (size - 10) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={9} className="fill-none stroke-slate-200 dark:stroke-slate-700" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        strokeWidth={9}
        strokeLinecap="round"
        strokeDasharray={`${(c * Math.min(100, pct)) / 100} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className="fill-none stroke-cyan-600"
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="fill-foreground text-[19px] font-bold">
        %{pct}
      </text>
    </svg>
  );
}

function StackedBar({ counts, total, className }: { counts: Record<Status, number>; total: number; className?: string }) {
  return (
    <div className={cn("flex h-2 w-full overflow-hidden rounded-full bg-muted", className)}>
      {BAR_ORDER.map((st) =>
        counts[st] > 0 ? (
          <span key={st} className={STATUS[st].bar} style={{ width: `${(100 * counts[st]) / Math.max(1, total)}%` }} />
        ) : null,
      )}
    </div>
  );
}

function Overview({ data, totals, havuz }: { data: CurriculumProgressResponse; totals: Record<Status, number>; havuz: boolean }) {
  const total = data.overall_total_topics;
  return (
    <div className="grid gap-3 xl:grid-cols-[1fr_minmax(280px,380px)]">
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <Ring pct={data.overall_coverage_pct} />
          <div className="min-w-0 flex-1 space-y-1.5">
            <p className="text-sm font-semibold text-foreground">
              {data.focus_grade
                ? data.subjects.every((s) => groupOf(s.name) !== "OKUL")
                  ? "TYT / AYT müfredatı"
                  : `${data.focus_grade}. sınıf müfredatı`
                : "Müfredat haritası"}
              {data.focus_grade ? (
                <span className="ml-1.5 rounded bg-cyan-700 px-1.5 py-0.5 text-[10.5px] font-semibold text-white">bu yıl</span>
              ) : null}
            </p>
            <p className="text-[13px] text-muted-foreground">
              {data.focus_grade ? "Bu yılın " : ""}
              {total} resmi konusunun <strong className="text-foreground">{data.overall_started_topics}</strong> tanesine
              girildi, <strong className="text-foreground">{totals.tamamlandi}</strong> konu tamamlandı
              {!data.focus_grade && data.grade_level ? ` · ${data.grade_level}. sınıf` : ""}
              {data.curriculum_model ? ` · ${data.curriculum_model.toUpperCase()}` : ""}
            </p>
            <StackedBar counts={totals} total={total} className="h-2.5" />
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-muted-foreground">
              {LEGEND.map(({ st, label }) => (
                <span key={st} className="inline-flex items-center gap-1">
                  <span className={cn("size-2.5 rounded-sm", STATUS[st].bar)} aria-hidden />
                  {label} <strong className="tabular-nums text-foreground">{totals[st]}</strong>
                </span>
              ))}
            </div>
          </div>
        </div>
        <GradeStrip data={data} />
        <details className="mt-3 rounded-lg bg-muted/50 px-3 py-2 text-[12px] text-muted-foreground" data-section="curriculum:howto">
          <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-foreground">
            <Info className="size-3.5 shrink-0" aria-hidden /> Harita nasıl dolar?
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li><strong className="text-foreground">Kitaptan:</strong> kitap ünitesi resmi konuya eşliyse çözülen test o konuya yazılır.</li>
            <li><strong className="text-foreground">Kaynaksız:</strong> kitap seçmeden konudan verilen görev{havuz ? " ya da havuz kalemi" : ""} çözülünce konu “devam ediyor” olur{havuz ? "; seansta “seansta” alanına yazdığın kaynaksız testler de sayılır" : ""}.</li>
            <li><strong className="text-foreground">Planlandı:</strong> {havuz ? "havuzda bu konudan bekleyen kalem var" : "programda bu konudan bekleyen görev var"}, henüz çözülmedi.</li>
            <li><strong className="text-foreground">Tamamlandı:</strong> tek kaynakta testlerin %98’i; birden fazla kaynakta biri tamamen + ikincisinin %90’ı. <strong className="text-foreground">Koçun “Konuyu kapat” kararı her zaman geçerlidir</strong> — öğrenci kayıtlı olmayan kaynaktan çalıştıysa seansta konuşup buradan kapat.</li>
            <li>Konusu belirsiz kalem (serbest metin) ve deneme kitapları haritaya işlenmez.</li>
            {data.focus_grade ? (
              <li><strong className="text-foreground">Önce bu yıl:</strong> yüzdeler, “sıradaki konu”, ders kartları ve yetişme tahmini {data.focus_grade}. sınıf konularından hesaplanır (TYT/AYT dersinde dersin tüm konuları). Önceki sınıflardan verilen konular kendi sınıf bölümünde görünür ve ayrıca sayılır, tahmine girmez. Hedef eğitim yılı sonu (15 Haziran).</li>
            ) : null}
          </ul>
        </details>
      </div>
      {data.projection ? <ProjectionCard p={data.projection} /> : null}
    </div>
  );
}

/** Sınıf sınıf kapsama: odak sınıf öne, önceki sınıflar + toplam yanında. */
function GradeStrip({ data }: { data: CurriculumProgressResponse }) {
  const grades = (data.grades ?? []).filter((g) => g.grade != null);
  if (grades.length < 2) return null;
  const ordered = [...grades].sort(
    (a, b) => Number(b.is_focus) - Number(a.is_focus) || (b.grade ?? 0) - (a.grade ?? 0),
  );
  const span = [...grades].sort((a, b) => (a.grade ?? 0) - (b.grade ?? 0));
  return (
    <div className="mt-3 flex flex-wrap gap-2" data-section="curriculum:grades">
      {ordered.map((g) => (
        <GradeChip key={g.grade} g={g} />
      ))}
      {data.focus_grade ? (
        <span className="inline-flex items-center gap-1.5 rounded-lg border border-dashed px-2.5 py-1 text-[12px] text-muted-foreground">
          Toplam ({span[0].grade}–{span[span.length - 1].grade}. sınıf)
          <strong className="tabular-nums text-foreground">
            {data.cumulative_started_topics}/{data.cumulative_total_topics} · %{data.cumulative_coverage_pct}
          </strong>
        </span>
      ) : null}
    </div>
  );
}

function GradeChip({ g }: { g: CurriculumGradeItem }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12px]",
        g.is_focus ? "bg-cyan-700 text-white" : "border bg-card text-foreground",
      )}
    >
      <span className="font-semibold">
        {g.grade}. sınıf{g.is_focus ? " · bu yıl" : ""}
      </span>
      <span className={cn("tabular-nums", g.is_focus ? "text-white" : "text-muted-foreground")}>
        {g.started_topics}/{g.total_topics} konu · %{g.coverage_pct}
      </span>
    </span>
  );
}

const VERDICT: Record<CurriculumProjectionItem["verdict"], { label: string; badge: string; bar: string }> = {
  yetisir: { label: "Yetişir", badge: "bg-emerald-700 text-white", bar: "bg-emerald-500" },
  risk: { label: "Riskli — tempo artmalı", badge: "bg-amber-500 text-amber-950", bar: "bg-amber-500" },
  yetismez: { label: "Yetişmez — hızlanma gerek", badge: "bg-rose-700 text-white", bar: "bg-rose-500" },
  sinav_yok: { label: "Sınav tarihi girilmemiş", badge: "bg-slate-600 text-white", bar: "bg-slate-400" },
  veri_yok: { label: "Veri yetersiz", badge: "bg-slate-600 text-white", bar: "bg-slate-400" },
};

function ProjectionCard({ p }: { p: CurriculumProjectionItem }) {
  const v = VERDICT[p.verdict];
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-foreground">
          <Target className="size-4 text-cyan-700 dark:text-cyan-300" aria-hidden />
          {p.target_kind === "okul_yili_sonu" ? "Eğitim yılı sonuna yetişme" : "Sınava yetişme"}
          <span className="text-[11px] font-normal text-muted-foreground">
            {p.target_kind === "okul_yili_sonu" ? "(bu yılın konuları)" : "(tüm konular)"}
          </span>
        </p>
        <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", v.badge)}>{v.label}</span>
      </div>
      {p.has_exam ? (
        <>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            {[
              [p.days_to_exam, p.target_kind === "okul_yili_sonu" ? "gün (15 Haziran)" : "sınava gün"],
              [p.remaining_topics, "kalan konu"],
              [p.pace_per_week, "konu / hafta (son 2 hafta)"],
            ].map(([n, l]) => (
              <div key={String(l)} className="rounded-lg bg-muted/50 px-1 py-2">
                <p className="text-lg font-bold tabular-nums text-foreground">{n}</p>
                <p className="text-[11px] text-muted-foreground">{l}</p>
              </div>
            ))}
          </div>
          <div className="mt-3">
            <div className="flex items-center justify-between text-[12px] text-muted-foreground">
              <span>{p.target_kind === "okul_yili_sonu" ? "Bu tempoyla 15 Haziran’a kadar kapsama" : "Bu tempoyla sınav gününe kadar kapsama"}</span>
              <span className="font-semibold tabular-nums text-foreground">%{p.projected_coverage_pct}</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full rounded-full", v.bar)} style={{ width: `${Math.min(100, p.projected_coverage_pct)}%` }} />
            </div>
          </div>
        </>
      ) : (
        <p className="mt-2 text-[12.5px] text-muted-foreground">
          {p.verdict === "sinav_yok"
            ? "Öğrencinin sınav tarihini profilden girince, mevcut tempoyla müfredatın sınava yetişip yetişmeyeceği burada hesaplanır."
            : "Projeksiyon için yeterli müfredat verisi yok."}
        </p>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- Ders kartı */

function SubjectCard({ s, focus, active, onClick }: {
  s: CurriculumSubjectItem; focus: number | null; active: boolean; onClick: () => void;
}) {
  const counts = countStatuses(s.topics.filter((t) => inFocus(t, focus)));
  const priorTotal = s.prior_total_topics ?? 0;
  const noFocusTopics = focus != null && s.total_topics === 0;
  const bookTopics = s.total_topics - s.no_resource_topics;
  const pool = s.pool_remaining ?? 0;
  const c = subjectColors(s.name);
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      data-testid="curriculum-subject"
      className={cn(
        "w-full rounded-xl border border-l-4 p-3 text-left transition",
        active ? "border-cyan-600 bg-cyan-50 ring-1 ring-cyan-600 dark:bg-cyan-500/10" : "bg-card hover:bg-muted/40",
      )}
      style={{ borderLeftColor: c.rail }}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={cn("text-sm font-semibold", active ? "text-cyan-950 dark:text-cyan-100" : "text-foreground")}>{s.name}</span>
        <span className={cn("shrink-0 text-sm font-bold tabular-nums", active ? "text-cyan-900 dark:text-cyan-100" : "text-foreground")}>
          {noFocusTopics ? "—" : `%${s.coverage_pct}`}
        </span>
      </div>
      {noFocusTopics ? (
        <p className={cn("mt-1.5 text-[12px]", active ? "text-cyan-900 dark:text-cyan-200" : "text-muted-foreground")}>
          {focus}. sınıfta bu dersin konusu yok
        </p>
      ) : (
        <>
          <StackedBar counts={counts} total={s.total_topics} className="mt-2" />
          <p className={cn("mt-1.5 text-[12px]", active ? "text-cyan-900 dark:text-cyan-200" : "text-muted-foreground")}>
            {focus ? `${focus}. sınıf: ` : ""}
            <strong className="tabular-nums">{counts.tamamlandi}</strong> tamam ·{" "}
            <strong className="tabular-nums">{counts.devam + counts.planlandi}</strong> süren ·{" "}
            <strong className="tabular-nums">{s.total_topics}</strong> konu
          </p>
        </>
      )}
      {priorTotal > 0 ? (
        <p className={cn("mt-0.5 text-[12px]", active ? "text-cyan-900 dark:text-cyan-200" : "text-muted-foreground")}>
          önceki sınıflar: <strong className="tabular-nums">{s.prior_started_topics ?? 0}/{priorTotal}</strong> konuya girildi
        </p>
      ) : null}
      {s.next_topic_name ? (
        <p className={cn("mt-1 flex items-start gap-1 text-[12px]", active ? "text-cyan-900 dark:text-cyan-200" : "text-muted-foreground")}>
          <ArrowRight className="mt-0.5 size-3 shrink-0" aria-hidden />
          <span>sıradaki: {s.next_topic_name}</span>
        </p>
      ) : null}
      <div className="mt-1.5 flex flex-wrap gap-1">
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium",
            bookTopics > 0 ? "bg-slate-700 text-white" : "bg-muted text-muted-foreground",
          )}
          title={bookTopics > 0 ? "Kitap ünitesi eşli konu sayısı" : "Bu derste kitap yok — konudan kaynaksız görev verilebilir"}
        >
          <BookOpen className="size-3" aria-hidden />
          {bookTopics > 0 ? `kitap ${bookTopics}/${s.total_topics} konu` : "kitap yok"}
        </span>
        {pool > 0 ? (
          <span className="inline-flex items-center gap-1 rounded bg-sky-700 px-1.5 py-0.5 text-[11px] font-medium text-white">
            <Inbox className="size-3" aria-hidden /> havuzda {pool} test
          </span>
        ) : null}
      </div>
    </button>
  );
}

/* ---------------------------------------------------------------- Ders ayrıntısı */

type Filter = "all" | "active" | "todo" | "done" | "nobook";
const FILTERS: { key: Filter; label: string; match: (t: CurriculumTopicItem) => boolean }[] = [
  { key: "all", label: "Tümü", match: () => true },
  { key: "active", label: "Süren", match: (t) => t.status === "devam" || t.status === "planlandi" },
  { key: "todo", label: "Başlanmadı", match: (t) => t.status === "baslanmadi" || t.status === "kaynak_yok" },
  { key: "done", label: "Tamamlandı", match: (t) => t.status === "tamamlandi" },
  { key: "nobook", label: "Kitabı yok", match: (t) => !t.has_resource },
];

type GradeSection = { key: string; grade: number | null; focus: boolean; topics: CurriculumTopicItem[] };

/** Konuları sınıf bölümlerine ayırır: odak sınıf önce, sonra önceki sınıflar (yeniden eskiye).
 *  Odak yoksa (12/mezun) sınıf sırasıyla. */
function gradeSections(topics: CurriculumTopicItem[], focus: number | null): GradeSection[] {
  const map = new Map<string, GradeSection>();
  for (const t of topics) {
    const isF = focus != null && inFocus(t, focus);
    const g = isF && t.grade_level != null ? focus : t.grade_level;
    const key = String(g ?? "x");
    if (!map.has(key)) map.set(key, { key, grade: g, focus: isF, topics: [] });
    map.get(key)!.topics.push(t);
  }
  return [...map.values()].sort(
    (a, b) =>
      Number(b.focus) - Number(a.focus) ||
      (focus != null ? (b.grade ?? 0) - (a.grade ?? 0) : (a.grade ?? 99) - (b.grade ?? 99)),
  );
}

function isStarted(t: CurriculumTopicItem): boolean {
  return t.status === "devam" || t.status === "tamamlandi" || (t.sourceless_completed ?? 0) > 0;
}

function SubjectDetail({ s, focus, studentId, poolOpen, havuz }: {
  s: CurriculumSubjectItem; focus: number | null; studentId: number; poolOpen: boolean; havuz: boolean;
}) {
  const [filter, setFilter] = React.useState<Filter>("all");
  const f = FILTERS.find((x) => x.key === filter)!;
  const shown = s.topics.filter(f.match);
  const sections = gradeSections(shown, focus);
  // Açık bölüm: odak sınıf varsa yalnız o (önceki sınıflar katlı); 12/mezunda öncelik sınıfı yok →
  // hepsi açık başlar. Durum filtresi seçiliyken bölümler hep açık.
  const [open, setOpen] = React.useState<Set<string>>(() => {
    const all = gradeSections(s.topics, focus);
    const f0 = all.find((x) => x.focus);
    return new Set(f0 ? [f0.key] : all.map((x) => x.key));
  });
  const toggle = (k: string) =>
    setOpen((prev) => {
      const n = new Set(prev);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });
  const priorTotal = s.prior_total_topics ?? 0;
  const forceOpen = filter !== "all" || sections.length === 1;

  return (
    <section className="rounded-xl border border-border bg-card" data-testid="curriculum-detail">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-4 py-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-foreground">{s.name}</h3>
          <p className="text-[12.5px] text-muted-foreground">
            {focus ? `${focus}. sınıf: ` : ""}
            {s.started_topics}/{s.total_topics} konuya girildi · {s.completed_topics} tamamlandı
            {s.last_topic_name ? (
              <>
                {" "}· <MapPin className="inline size-3" aria-hidden /> son işlenen: {s.last_topic_name}
              </>
            ) : null}
            {priorTotal > 0 ? ` · önceki sınıflar ${s.prior_started_topics ?? 0}/${priorTotal}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Durum filtresi">
          {FILTERS.map((x) => {
            const n = s.topics.filter(x.match).length;
            if (x.key !== "all" && n === 0) return null;
            return (
              <button
                key={x.key}
                type="button"
                role="tab"
                aria-selected={filter === x.key}
                onClick={() => setFilter(x.key)}
                className={cn(
                  "rounded-full px-2.5 py-1 text-[12px] font-medium",
                  filter === x.key ? "bg-cyan-700 text-white" : "bg-muted text-foreground hover:bg-muted/70",
                )}
              >
                {x.label} <span className="tabular-nums">{n}</span>
              </button>
            );
          })}
        </div>
      </header>

      {havuz && !poolOpen ? (
        <p className="border-b border-border bg-muted/40 px-4 py-2 text-[12px] text-muted-foreground">
          Havuz dönemi açık değil — konudan kalem eklemek için önce havuz editöründe dönem aç.
        </p>
      ) : null}

      {shown.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">Bu filtrede konu yok.</p>
      ) : (
        <div className="divide-y divide-border">
          {sections.map((sec) => {
            const isOpen = forceOpen || open.has(sec.key);
            const started = sec.topics.filter(isStarted).length;
            const done = sec.topics.filter((t) => t.status === "tamamlandi").length;
            const pct = Math.round((100 * started) / Math.max(1, sec.topics.length));
            return (
              <div key={sec.key} data-section="curriculum:grade" data-grade={sec.grade ?? ""}>
                <button
                  type="button"
                  onClick={() => toggle(sec.key)}
                  aria-expanded={isOpen}
                  disabled={forceOpen}
                  className={cn(
                    "flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 text-left",
                    sec.focus ? "bg-cyan-700 text-white hover:bg-cyan-800" : "bg-muted/60 text-foreground hover:bg-muted",
                  )}
                >
                  <ChevronDown className={cn("size-4 shrink-0 transition-transform", !isOpen && "-rotate-90")} aria-hidden />
                  <span className="text-[13px] font-bold">
                    {sec.grade != null ? `${sec.grade}. Sınıf` : sec.focus ? "Ders konuları" : "Sınıfı belirtilmemiş"}
                    {sec.focus ? " · bu yıl" : ""}
                  </span>
                  <span className={cn("text-[12px] tabular-nums", sec.focus ? "text-white" : "text-muted-foreground")}>
                    {sec.topics.length} konu · {started} girildi · {done} tamam · %{pct}
                  </span>
                </button>
                {isOpen ? (
                  <ol className="divide-y divide-border/70">
                    {sec.topics.map((t, i) => {
                      const prev = i > 0 ? sec.topics[i - 1] : null;
                      const showUnit = !!t.unit_name && (!prev || prev.unit_name !== t.unit_name);
                      return (
                        <React.Fragment key={t.topic_id}>
                          {showUnit ? (
                            <li className="bg-muted/30 px-4 py-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                              {t.unit_name}
                            </li>
                          ) : null}
                          <TopicRow
                            t={t}
                            isNext={t.name === s.next_topic_name && inFocus(t, focus)}
                            indent={!!t.unit_name}
                            studentId={studentId}
                            subjectId={s.subject_id}
                            poolOpen={poolOpen}
                          />
                        </React.Fragment>
                      );
                    })}
                  </ol>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function TopicRow({ t, isNext, indent, studentId, subjectId, poolOpen }: {
  t: CurriculumTopicItem; isNext: boolean; indent: boolean; studentId: number; subjectId: number; poolOpen: boolean;
}) {
  const meta = STATUS[t.status];
  const sources = t.sources ?? [];
  const closeM = useCloseTopic(studentId);
  const reopenM = useReopenTopic(studentId);
  const addM = useAddPoolItem(studentId);
  const [adding, setAdding] = React.useState(false);
  const [qty, setQty] = React.useState("3");
  const poolRem = t.pool_remaining ?? 0;
  const poolMarked = t.pool_marked ?? 0;
  const sl = t.sourceless_completed ?? 0;
  const busy = closeM.isPending || reopenM.isPending;
  const n = Number(qty);
  const qtyOk = Number.isInteger(n) && n >= 1 && n <= 500;
  return (
    <li
      className={cn("group py-2.5 pr-4", indent ? "pl-7" : "pl-4", isNext && "bg-cyan-50/70 dark:bg-cyan-500/10")}
      data-testid="curriculum-topic"
      data-topic-id={t.topic_id}
    >
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1 basis-60">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={cn("text-sm", t.status === "kaynak_yok" ? "text-foreground/80" : "font-medium text-foreground")}>{t.name}</span>
            {isNext ? <span className="rounded bg-cyan-700 px-1.5 py-0.5 text-[10.5px] font-semibold text-white">sıradaki</span> : null}
            {t.exam_mismatch ? (
              <span
                className="inline-flex items-center gap-1 rounded bg-amber-700 px-1.5 py-0.5 text-[10.5px] font-semibold text-white"
                title={
                  `Kitapta işlenmiş görünüyor ama son denemelerde bu konuda doğruluk %${t.exam_accuracy_pct ?? 0} ` +
                  `(${t.exam_answered ?? 0} cevaplanmış soru).` +
                  (t.exam_manual_heavy
                    ? " İşlenmişin çoğu elle/bağımsız girişten — girişi ve konuyu birlikte gözden geçir."
                    : " Konu tekrar/pekiştirme istiyor olabilir.")
                }
              >
                <AlertTriangle className="size-3" aria-hidden />
                deneme doğrulamıyor %{t.exam_accuracy_pct ?? 0}
              </span>
            ) : null}
          </div>
          {sources.length > 0 ? (
            <ul className="mt-1.5 space-y-1">
              {sources.map((src, k) => {
                const pct = Math.round((100 * src.completed) / Math.max(1, src.total));
                return (
                  <li key={k} className="flex items-center gap-2 text-[12px] text-muted-foreground">
                    <BookOpen className="size-3 shrink-0" aria-hidden />
                    <span className="min-w-0 flex-1">{src.book_name}</span>
                    <span className="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-muted">
                      <span
                        className={cn("block h-full rounded-full", pct >= 100 ? "bg-emerald-500" : pct > 0 ? "bg-amber-400" : "bg-transparent")}
                        style={{ width: `${Math.min(100, pct)}%` }}
                      />
                    </span>
                    <span className="w-14 shrink-0 text-right tabular-nums text-foreground">{src.completed}/{src.total}</span>
                  </li>
                );
              })}
            </ul>
          ) : null}
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[12px]">
            {!t.has_resource ? (
              <span className="inline-flex items-center gap-1 text-muted-foreground" title="Bu konu öğrencinin kitaplarında eşli değil — kaynaksız (müfredattan) verilebilir">
                <CircleSlash className="size-3" aria-hidden /> kitap yok
              </span>
            ) : null}
            {sl > 0 ? (
              <span className="rounded bg-amber-500/15 px-1.5 py-0.5 font-medium text-amber-900 dark:text-amber-200" data-testid="topic-sourceless">
                kaynaksız {sl} test çözüldü{poolMarked > 0 ? ` (${poolMarked}’i seansta)` : ""}
              </span>
            ) : null}
            {poolRem > 0 ? (
              <span className="inline-flex items-center gap-1 rounded bg-sky-700 px-1.5 py-0.5 font-medium text-white" data-testid="topic-pool">
                <Inbox className="size-3" aria-hidden /> havuzda {poolRem} test bekliyor
              </span>
            ) : null}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5 [&>button]:opacity-70 [&>button]:transition-opacity group-hover:[&>button]:opacity-100 group-focus-within:[&>button]:opacity-100">
          <span className={cn("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold", t.closed ? "bg-emerald-700 text-white" : meta.badge)}>
            {t.closed ? <Lock className="size-3" aria-hidden /> : <meta.Icon className="size-3" aria-hidden />}
            {t.closed ? "Koç kapattı" : meta.label}
          </span>
          {poolOpen && !t.closed ? (
            <button
              type="button"
              onClick={() => setAdding((v) => !v)}
              aria-expanded={adding}
              className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium text-foreground hover:bg-muted"
            >
              <Plus className="size-3" aria-hidden /> Havuza
            </button>
          ) : null}
          {t.closed ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => reopenM.mutate({ topicId: t.topic_id })}
              className="rounded-md border px-2 py-0.5 text-[11px] font-medium text-foreground hover:bg-muted disabled:opacity-50"
              title="Yanlış kapatıldıysa konuyu yeniden aç"
            >
              Geri aç
            </button>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => closeM.mutate({ topicId: t.topic_id })}
              className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium text-foreground hover:bg-muted disabled:opacity-50"
              title="Öğrenci bu konuyu bitirdi (kayıtlı olmayan bir kaynaktan çalışmış olsa bile). Geri alınabilir."
            >
              <Lock className="size-3" aria-hidden /> Konuyu kapat
            </button>
          )}
        </div>
      </div>
      {adding ? (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 rounded-lg border bg-muted/40 p-2 text-[12px]" data-section="curriculum:pool-add">
          <span className="text-muted-foreground">Kaynaksız havuz kalemi · kaç test?</span>
          {[1, 2, 3, 5, 10].map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setQty(String(v))}
              className={cn("rounded-md px-2 py-0.5 font-medium", qty === String(v) ? "bg-cyan-700 text-white" : "bg-card text-foreground hover:bg-muted")}
            >
              {v}
            </button>
          ))}
          <input
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            inputMode="numeric"
            aria-label="Test sayısı"
            className="h-7 w-14 rounded-md border bg-background px-1 text-center"
          />
          <button
            type="button"
            disabled={!qtyOk || addM.isPending}
            onClick={() =>
              addM.mutate(
                { subject_id: subjectId, topic_id: t.topic_id, quantity: n, unit: "test" },
                { onSuccess: () => setAdding(false) },
              )
            }
            className="rounded-md bg-cyan-700 px-2.5 py-0.5 font-semibold text-white hover:bg-cyan-800 disabled:opacity-50"
          >
            Havuza ekle
          </button>
          <span className="text-muted-foreground">Kitaplı kalem için havuz editörünü kullan.</span>
        </div>
      ) : null}
    </li>
  );
}
