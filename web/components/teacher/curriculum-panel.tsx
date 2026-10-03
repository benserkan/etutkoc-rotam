"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CircleDashed,
  CircleSlash,
  Clock,
  Info,
  Loader2,
  Lock,
  MapPin,
  Target,
} from "lucide-react";

import { getTeacherStudentCurriculum, teacherKeys } from "@/lib/api/teacher";
import type {
  CurriculumProgressResponse,
  CurriculumProjectionItem,
  CurriculumSubjectItem,
  CurriculumTopicItem,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

type Status = CurriculumTopicItem["status"];

// Dolgulu rozet + bar tonları (küçük rozette ton+dark çifti yerine dolgu — kontrast).
const STATUS: Record<Status, { label: string; badge: string; bar: string; Icon: React.ElementType }> = {
  tamamlandi: { label: "Tamamlandı", badge: "bg-emerald-600 text-white", bar: "bg-emerald-500", Icon: CheckCircle2 },
  devam: { label: "Devam ediyor", badge: "bg-amber-500 text-amber-950", bar: "bg-amber-400", Icon: Clock },
  planlandi: { label: "Planlandı", badge: "bg-sky-600 text-white", bar: "bg-sky-500", Icon: CircleDashed },
  baslanmadi: { label: "Başlanmadı", badge: "bg-slate-500 text-white", bar: "bg-slate-300 dark:bg-slate-600", Icon: CircleDashed },
  kaynak_yok: { label: "Kaynak yok", badge: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200", bar: "bg-slate-100 dark:bg-slate-800", Icon: CircleSlash },
};
const STATUS_ORDER: Status[] = ["tamamlandi", "devam", "planlandi", "baslanmadi", "kaynak_yok"];

function countStatuses(topics: CurriculumTopicItem[]): Record<Status, number> {
  const c: Record<Status, number> = { tamamlandi: 0, devam: 0, planlandi: 0, baslanmadi: 0, kaynak_yok: 0 };
  for (const t of topics) c[t.status] += 1;
  return c;
}

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
        Bu öğrenci için müfredat haritası oluşturulamadı. Önce kütüphanede kitap
        ünitelerini <strong>“Müfredata eşleştir”</strong> ile resmi konulara bağlayın.
      </div>
    );
  }

  // Varsayılan: kaynağı olan ilk ders
  const defaultId =
    data.subjects.find((s) => s.no_resource_topics < s.total_topics)?.subject_id ??
    data.subjects[0].subject_id;
  const activeId = data.subjects.some((s) => s.subject_id === picked) ? picked! : defaultId;
  const active = data.subjects.find((s) => s.subject_id === activeId)!;

  const withSource = data.subjects.filter((s) => s.no_resource_topics < s.total_topics);
  const noSource = data.subjects.filter((s) => s.no_resource_topics >= s.total_topics);
  const allTopics = data.subjects.flatMap((s) => s.topics);
  const totals = countStatuses(allTopics);

  return (
    <div className="space-y-4" data-section="curriculum-panel">
      <Overview data={data} totals={totals} />

      <div className="grid gap-4 lg:grid-cols-[minmax(260px,320px)_1fr]">
        <nav className="space-y-2" aria-label="Dersler">
          {withSource.map((s) => (
            <SubjectCard
              key={s.subject_id}
              s={s}
              active={s.subject_id === activeId}
              onClick={() => setPicked(s.subject_id)}
            />
          ))}
          {noSource.length > 0 ? (
            <details
              className="rounded-xl border border-border bg-card"
              open={withSource.length === 0 || noSource.some((s) => s.subject_id === activeId)}
              data-testid="curriculum-nosource"
            >
              <summary className="cursor-pointer px-3 py-2.5 text-[13px] font-medium text-foreground">
                Kaynağı olmayan dersler ({noSource.length})
                <span className="block text-[11.5px] font-normal text-muted-foreground">
                  Kitap atanınca haritaya girer; konular yine görülebilir.
                </span>
              </summary>
              <div className="flex flex-wrap gap-1.5 px-3 pb-3">
                {noSource.map((s) => (
                  <button
                    key={s.subject_id}
                    type="button"
                    onClick={() => setPicked(s.subject_id)}
                    aria-pressed={s.subject_id === activeId}
                    className={cn(
                      "rounded-md px-2 py-1 text-[12px]",
                      s.subject_id === activeId
                        ? "bg-cyan-700 text-white"
                        : "bg-muted text-foreground hover:bg-muted/70",
                    )}
                  >
                    {s.name} <span className="tabular-nums opacity-80">{s.total_topics}</span>
                  </button>
                ))}
              </div>
            </details>
          ) : null}
        </nav>
        <SubjectDetail key={active.subject_id} s={active} />
      </div>

      {data.extras.length > 0 ? (
        <details className="rounded-xl border border-amber-200 bg-amber-50/50 dark:border-amber-500/30 dark:bg-amber-500/10">
          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-amber-900 dark:text-amber-200">
            Müfredata eşleşmemiş üniteler ({data.extras.length}){" "}
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
      {STATUS_ORDER.map((st) =>
        counts[st] > 0 ? (
          <span key={st} className={STATUS[st].bar} style={{ width: `${(100 * counts[st]) / Math.max(1, total)}%` }} />
        ) : null,
      )}
    </div>
  );
}

function Overview({ data, totals }: { data: CurriculumProgressResponse; totals: Record<Status, number> }) {
  const total = data.overall_total_topics;
  return (
    <div className="grid gap-3 xl:grid-cols-[1fr_minmax(280px,380px)]">
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <Ring pct={data.overall_coverage_pct} />
          <div className="min-w-0 flex-1 space-y-1.5">
            <p className="text-sm font-semibold text-foreground">Müfredat haritası</p>
            <p className="text-[13px] text-muted-foreground">
              {total} resmi konunun <strong className="text-foreground">{data.overall_started_topics}</strong>’ine
              girildi, <strong className="text-foreground">{totals.tamamlandi}</strong> konu tamamlandı
              {data.grade_level ? ` · ${data.grade_level}. sınıf` : ""}
              {data.curriculum_model ? ` · ${data.curriculum_model.toUpperCase()}` : ""}
            </p>
            <StackedBar counts={totals} total={total} className="h-2.5" />
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-muted-foreground">
              {STATUS_ORDER.map((st) => (
                <span key={st} className="inline-flex items-center gap-1">
                  <span className={cn("size-2.5 rounded-sm", STATUS[st].bar)} aria-hidden />
                  {STATUS[st].label} <strong className="tabular-nums text-foreground">{totals[st]}</strong>
                </span>
              ))}
            </div>
          </div>
        </div>
        <p className="mt-3 flex items-start gap-1.5 rounded-lg bg-muted/50 px-3 py-2 text-[12px] text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            <strong className="text-foreground">Tamamlandı kuralı:</strong> konu tek kaynaktaysa testlerinin %98’i;
            birden fazla kaynaktaysa biri tamamen bitmiş ve ikinci kaynaktan %90’ı çözülmüş olmalı.
            Koçun “konuyu kapat” kararı her zaman geçerlidir. Deneme kitapları sayılmaz.
          </span>
        </p>
      </div>
      {data.projection ? <ProjectionCard p={data.projection} /> : null}
    </div>
  );
}

const VERDICT: Record<CurriculumProjectionItem["verdict"], { label: string; badge: string; bar: string }> = {
  yetisir: { label: "Yetişir", badge: "bg-emerald-600 text-white", bar: "bg-emerald-500" },
  risk: { label: "Riskli — tempo artmalı", badge: "bg-amber-500 text-amber-950", bar: "bg-amber-500" },
  yetismez: { label: "Yetişmez — hızlanma gerek", badge: "bg-rose-600 text-white", bar: "bg-rose-500" },
  sinav_yok: { label: "Sınav tarihi girilmemiş", badge: "bg-slate-500 text-white", bar: "bg-slate-400" },
  veri_yok: { label: "Veri yetersiz", badge: "bg-slate-500 text-white", bar: "bg-slate-400" },
};

function ProjectionCard({ p }: { p: CurriculumProjectionItem }) {
  const v = VERDICT[p.verdict];
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-foreground">
          <Target className="size-4 text-cyan-700 dark:text-cyan-300" aria-hidden />
          Sınava yetişme
        </p>
        <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", v.badge)}>{v.label}</span>
      </div>
      {p.has_exam ? (
        <>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            {[
              [p.days_to_exam, "gün kaldı"],
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
              <span>Bu tempoyla sınav gününe kadar kapsama</span>
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

function SubjectCard({ s, active, onClick }: { s: CurriculumSubjectItem; active: boolean; onClick: () => void }) {
  const counts = countStatuses(s.topics);
  const noSource = s.no_resource_topics >= s.total_topics;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      data-testid="curriculum-subject"
      className={cn(
        "w-full rounded-xl border p-3 text-left transition",
        active
          ? "border-cyan-600 bg-cyan-50 ring-1 ring-cyan-600 dark:bg-cyan-500/10"
          : "border-border bg-card hover:border-cyan-400 hover:bg-muted/40",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={cn("text-sm font-semibold", active ? "text-cyan-950 dark:text-cyan-100" : "text-foreground")}>
          {s.name}
        </span>
        <span className={cn("shrink-0 text-sm font-bold tabular-nums", active ? "text-cyan-900 dark:text-cyan-100" : "text-foreground")}>
          %{s.coverage_pct}
        </span>
      </div>
      <StackedBar counts={counts} total={s.total_topics} className="mt-2" />
      <p className={cn("mt-1.5 text-[12px]", active ? "text-cyan-900 dark:text-cyan-200" : "text-muted-foreground")}>
        {noSource ? (
          "Bu derste kaynak yok"
        ) : (
          <>
            <strong className="tabular-nums">{counts.tamamlandi}</strong> tamam ·{" "}
            <strong className="tabular-nums">{counts.devam + counts.planlandi}</strong> süren ·{" "}
            <strong className="tabular-nums">{s.total_topics}</strong> konu
          </>
        )}
      </p>
      {s.next_topic_name ? (
        <p className={cn("mt-1 flex items-start gap-1 text-[12px]", active ? "text-cyan-900 dark:text-cyan-200" : "text-muted-foreground")}>
          <ArrowRight className="mt-0.5 size-3 shrink-0" aria-hidden />
          <span>sıradaki: {s.next_topic_name}</span>
        </p>
      ) : null}
    </button>
  );
}

/* ---------------------------------------------------------------- Ders ayrıntısı */

type Filter = "all" | "active" | "todo" | "done" | "none";
const FILTERS: { key: Filter; label: string; match: (s: Status) => boolean }[] = [
  { key: "all", label: "Tümü", match: () => true },
  { key: "active", label: "Süren", match: (s) => s === "devam" || s === "planlandi" },
  { key: "todo", label: "Başlanmadı", match: (s) => s === "baslanmadi" },
  { key: "done", label: "Tamamlandı", match: (s) => s === "tamamlandi" },
  { key: "none", label: "Kaynak yok", match: (s) => s === "kaynak_yok" },
];

function SubjectDetail({ s }: { s: CurriculumSubjectItem }) {
  const [filter, setFilter] = React.useState<Filter>("all");
  const f = FILTERS.find((x) => x.key === filter)!;
  const shown = s.topics.filter((t) => f.match(t.status));

  return (
    <section className="rounded-xl border border-border bg-card" data-testid="curriculum-detail">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-4 py-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-foreground">{s.name}</h3>
          <p className="text-[12.5px] text-muted-foreground">
            {s.started_topics}/{s.total_topics} konuya girildi · {s.completed_topics} tamamlandı
            {s.last_topic_name ? (
              <>
                {" "}· <MapPin className="inline size-3" aria-hidden /> son işlenen: {s.last_topic_name}
              </>
            ) : null}
          </p>
        </div>
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Durum filtresi">
          {FILTERS.map((x) => {
            const n = s.topics.filter((t) => x.match(t.status)).length;
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
                  filter === x.key
                    ? "bg-cyan-700 text-white"
                    : "bg-muted text-foreground hover:bg-muted/70",
                )}
              >
                {x.label} <span className="tabular-nums">{n}</span>
              </button>
            );
          })}
        </div>
      </header>

      {shown.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">Bu filtrede konu yok.</p>
      ) : (
        <ol className="divide-y divide-border/70">
          {shown.map((t, i) => {
            const prev = i > 0 ? shown[i - 1] : null;
            const showGrade = t.grade_level != null && (!prev || prev.grade_level !== t.grade_level);
            const showUnit = !!t.unit_name && (!prev || prev.unit_name !== t.unit_name || showGrade);
            return (
              <React.Fragment key={t.topic_id}>
                {showGrade ? (
                  <li className="bg-cyan-700 px-4 py-1 text-[12px] font-bold text-white">{t.grade_level}. Sınıf</li>
                ) : null}
                {showUnit ? (
                  <li className="bg-muted/60 px-4 py-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t.unit_name}
                  </li>
                ) : null}
                <TopicRow t={t} isNext={t.name === s.next_topic_name} indent={!!t.unit_name} />
              </React.Fragment>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function TopicRow({ t, isNext, indent }: { t: CurriculumTopicItem; isNext: boolean; indent: boolean }) {
  const meta = STATUS[t.status];
  const sources = t.sources ?? [];
  return (
    <li
      className={cn("flex flex-wrap items-start gap-x-3 gap-y-2 py-2.5 pr-4", indent ? "pl-7" : "pl-4", isNext && "bg-cyan-50/70 dark:bg-cyan-500/10")}
      data-testid="curriculum-topic"
    >
      <div className="min-w-0 flex-1 basis-60">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={cn("text-sm", t.status === "kaynak_yok" ? "text-muted-foreground" : "font-medium text-foreground")}>
            {t.name}
          </span>
          {isNext ? (
            <span className="rounded bg-cyan-700 px-1.5 py-0.5 text-[10.5px] font-semibold text-white">sıradaki</span>
          ) : null}
          {t.exam_mismatch ? (
            <span
              className="inline-flex items-center gap-1 rounded bg-amber-600 px-1.5 py-0.5 text-[10.5px] font-semibold text-white"
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
                  <span className="w-14 shrink-0 text-right tabular-nums text-foreground">
                    {src.completed}/{src.total}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : t.sourceless_completed ? (
          <p className="mt-1 text-[12px] text-muted-foreground">Kaynaksız {t.sourceless_completed} test çözüldü</p>
        ) : null}
      </div>
      <span className={cn("inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold", t.closed ? "bg-emerald-700 text-white" : meta.badge)}>
        {t.closed ? <Lock className="size-3" aria-hidden /> : <meta.Icon className="size-3" aria-hidden />}
        {t.closed ? "Koç kapattı" : meta.label}
      </span>
    </li>
  );
}
