"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Loader2,
  ChevronDown,
  CheckCircle2,
  CircleDashed,
  CircleSlash,
  Clock,
  MapPin,
  ArrowRight,
} from "lucide-react";

import { getTeacherStudentCurriculum, teacherKeys } from "@/lib/api/teacher";
import type {
  CurriculumProgressResponse,
  CurriculumProjectionItem,
  CurriculumSubjectItem,
  CurriculumTopicItem,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

const STATUS: Record<
  CurriculumTopicItem["status"],
  { label: string; cls: string; Icon: React.ElementType }
> = {
  tamamlandi: { label: "Tamamlandı", cls: "text-emerald-700 bg-emerald-50 border-emerald-200", Icon: CheckCircle2 },
  devam: { label: "Devam", cls: "text-amber-700 bg-amber-50 border-amber-200", Icon: Clock },
  planlandi: { label: "Planlandı", cls: "text-sky-700 bg-sky-50 border-sky-200", Icon: CircleDashed },
  baslanmadi: { label: "Başlanmadı", cls: "text-slate-600 bg-slate-50 border-slate-200", Icon: CircleDashed },
  kaynak_yok: { label: "Kaynak yok", cls: "text-slate-400 bg-slate-50 border-slate-200", Icon: CircleSlash },
};

export function CurriculumPanel({ studentId }: { studentId: number }) {
  const q = useQuery<CurriculumProgressResponse>({
    queryKey: teacherKeys.studentCurriculum(studentId),
    queryFn: () => getTeacherStudentCurriculum(studentId),
    staleTime: 30_000,
  });

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
      <div className="rounded-lg border border-border bg-muted/20 p-6 text-sm text-muted-foreground">
        Bu öğrenci için müfredat haritası oluşturulamadı. Önce kütüphanede kitap
        ünitelerini <strong>“Müfredata eşleştir”</strong> ile resmi konulara bağlayın.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Genel kapsama */}
      <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-indigo-900">
              Müfredat işlenme oranı
            </p>
            <p className="text-xs text-indigo-700">
              {data.overall_started_topics}/{data.overall_total_topics} konuya girildi
              {data.curriculum_model ? ` · ${data.curriculum_model.toUpperCase()}` : ""}
              {data.grade_level ? ` · ${data.grade_level}. sınıf` : ""}
            </p>
          </div>
          <div className="text-right">
            <span className="text-2xl font-bold text-indigo-700">%{data.overall_coverage_pct}</span>
          </div>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-indigo-100">
          <div
            className="h-full rounded-full bg-indigo-500"
            style={{ width: `${data.overall_coverage_pct}%` }}
          />
        </div>
        <p className="mt-2 text-[11px] text-indigo-700">
          “İşlenme” = en az bir test çözülen konu / toplam resmi konu. Aşağıda her
          ders için sıralı konular + durum; “sıradaki” = atanabilecek ilk konu.
        </p>
      </div>

      {data.projection ? <ProjectionCard p={data.projection} /> : null}

      {data.subjects.map((s) => (
        <SubjectBlock key={s.subject_id} subject={s} />
      ))}

      {data.extras.length > 0 ? (
        <details className="rounded-lg border border-amber-200 bg-amber-50/40">
          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-amber-900">
            Müfredata eşleşmemiş üniteler ({data.extras.length}){" "}
            <span className="font-normal text-amber-700">
              — resmi konuya bağlanmamış; haritada görünmez
            </span>
          </summary>
          <ul className="space-y-1 px-4 pb-3 text-xs">
            {data.extras.map((e) => (
              <li key={e.section_id} className="text-amber-800">
                {e.book_name} · <span className="font-medium">{e.label}</span>
                {e.completed > 0 ? ` · ${e.completed} test çözülmüş` : ""}
              </li>
            ))}
          </ul>
          <p className="px-4 pb-3 text-[11px] text-amber-700">
            Bunları kütüphanede “Müfredata eşleştir” ile bağlarsan haritaya girerler.
          </p>
        </details>
      ) : null}
    </div>
  );
}

const VERDICT: Record<
  CurriculumProjectionItem["verdict"],
  { label: string; cls: string; bar: string }
> = {
  yetisir: { label: "Yetişir", cls: "border-emerald-300 bg-emerald-50/60 text-emerald-900", bar: "bg-emerald-500" },
  risk: { label: "Riskli — tempo artmalı", cls: "border-amber-300 bg-amber-50/60 text-amber-900", bar: "bg-amber-500" },
  yetismez: { label: "Yetişmez — acil hızlanma gerek", cls: "border-rose-300 bg-rose-50/60 text-rose-900", bar: "bg-rose-500" },
  sinav_yok: { label: "Sınav tarihi girilmemiş", cls: "border-slate-300 bg-slate-50/60 text-slate-700", bar: "bg-slate-400" },
  veri_yok: { label: "Veri yetersiz", cls: "border-slate-300 bg-slate-50/60 text-slate-700", bar: "bg-slate-400" },
};

function ProjectionCard({ p }: { p: CurriculumProjectionItem }) {
  const v = VERDICT[p.verdict];
  return (
    <div className={cn("rounded-lg border p-4", v.cls)}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">Sınava yetişme projeksiyonu</p>
        <span className="rounded-full border border-current/30 px-2 py-0.5 text-xs font-semibold">
          {v.label}
        </span>
      </div>
      {p.has_exam ? (
        <>
          <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
            <div>
              <p className="text-lg font-bold tabular-nums">{p.days_to_exam}</p>
              <p className="opacity-80">gün kaldı</p>
            </div>
            <div>
              <p className="text-lg font-bold tabular-nums">{p.remaining_topics}</p>
              <p className="opacity-80">kalan konu</p>
            </div>
            <div>
              <p className="text-lg font-bold tabular-nums">{p.pace_per_week}</p>
              <p className="opacity-80">konu/hafta (son 2 hafta)</p>
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-center justify-between text-[11px]">
              <span className="opacity-80">Bu tempoyla sınava kadar ulaşılacak kapsama</span>
              <span className="font-semibold tabular-nums">%{p.projected_coverage_pct}</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-black/10">
              <div className={cn("h-full rounded-full", v.bar)} style={{ width: `${Math.min(100, p.projected_coverage_pct)}%` }} />
            </div>
          </div>
        </>
      ) : (
        <p className="mt-2 text-xs opacity-80">
          {p.verdict === "sinav_yok"
            ? "Öğrencinin sınav tarihini girince, mevcut çalışma temposuna göre müfredatın yetişip yetişmeyeceği burada hesaplanır."
            : "Projeksiyon için yeterli müfredat verisi yok."}
        </p>
      )}
    </div>
  );
}

function SubjectBlock({ subject: s }: { subject: CurriculumSubjectItem }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-muted/30"
      >
        <span className="min-w-0 flex-1">
          <span className="font-medium text-foreground">{s.name}</span>
          <span className="ml-2 text-xs text-muted-foreground">
            {s.started_topics}/{s.total_topics} konu · %{s.coverage_pct}
          </span>
          {s.next_topic_name ? (
            <span className="mt-0.5 block truncate text-[11px] text-indigo-700">
              <ArrowRight className="mr-1 inline size-3" aria-hidden />
              sıradaki: {s.next_topic_name}
            </span>
          ) : s.last_topic_name ? (
            <span className="mt-0.5 block truncate text-[11px] text-emerald-700">
              <MapPin className="mr-1 inline size-3" aria-hidden />
              son işlenen: {s.last_topic_name}
            </span>
          ) : null}
        </span>
        <span className="flex w-24 shrink-0 flex-col items-end">
          <span className="text-sm font-semibold text-foreground">%{s.coverage_pct}</span>
          <span className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full rounded-full bg-indigo-500"
              style={{ width: `${s.coverage_pct}%` }}
            />
          </span>
        </span>
        <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
      </button>

      {open ? (
        <ul className="divide-y divide-border/60 border-t border-border">
          {s.topics.map((t, i) => {
            const meta = STATUS[t.status];
            const isNext = t.name === s.next_topic_name;
            const prev = i > 0 ? s.topics[i - 1] : null;
            // sınıf başlığı: grade değiştiğinde (tekrar eden tema adlarını ayırır)
            const showGrade = t.grade_level != null && (!prev || prev.grade_level !== t.grade_level);
            // tema/ünite başlığı: unit_name değiştiğinde bir kez göster (Maarif)
            const showUnit = t.unit_name && (!prev || prev.unit_name !== t.unit_name || showGrade);
            return (
              <React.Fragment key={t.topic_id}>
                {showGrade ? (
                  <li className="bg-indigo-100/80 px-4 py-1.5 dark:bg-indigo-950/40">
                    <span className="text-xs font-bold text-indigo-800 dark:text-indigo-200">
                      {t.grade_level}. Sınıf
                    </span>
                  </li>
                ) : null}
                {showUnit ? (
                  <li className="bg-slate-100/70 px-4 py-1.5 dark:bg-slate-800/40">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                      {t.unit_name}
                    </span>
                  </li>
                ) : null}
                <li
                  className={cn(
                    "flex items-center gap-3 py-2 pr-4",
                    t.unit_name ? "pl-7" : "pl-4",
                    isNext && "bg-indigo-50/50",
                  )}
                >
                  <span className="min-w-0 flex-1">
                    <span className={cn("text-sm", t.status === "kaynak_yok" ? "text-muted-foreground" : "text-foreground")}>
                      {t.name}
                    </span>
                    {isNext ? (
                      <span className="ml-2 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700">
                        sıradaki
                      </span>
                    ) : null}
                    {t.has_resource && t.test_total > 0 ? (
                      <span className="ml-2 text-[11px] text-muted-foreground tabular-nums">
                        {t.completed}/{t.test_total} test
                      </span>
                    ) : null}
                  </span>
                  <span
                    className={cn(
                      "inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium",
                      meta.cls,
                    )}
                  >
                    <meta.Icon className="size-3" aria-hidden />
                    {meta.label}
                  </span>
                </li>
              </React.Fragment>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
