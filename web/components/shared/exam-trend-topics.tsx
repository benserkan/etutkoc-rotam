"use client";

import * as React from "react";
import {
  ArrowRight,
  CalendarPlus,
  Check,
  FileSearch,
  Info,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAddAgendaItems } from "@/lib/hooks/use-exam-progress-mutations";
import type {
  AnalysisEvidenceExam,
  AnalysisEvidenceQuestion,
  AnalysisTrendTopic,
} from "@/lib/types/exam-import";
import { cn } from "@/lib/utils";

/**
 * Unutulan / gelişen konular (2026-10-03 yeniden tasarım).
 *
 * Her konu bir kart: ilk denemeler ↔ son denemeler kıyası SAYIYLA (2/2 → 0/2),
 * deneme deneme nokta şeridi (yarı sınırı görünür) ve kıyasın kaç soruya
 * dayandığı. "Kanıtı gör" → hangi denemede hangi soru, öğrencinin cevabı,
 * doğru cevap. Koç kartı sıradaki seansın gündemine ekleyebilir.
 */

type Kind = "forgotten" | "improved";

function pct(v: number): string {
  return `%${Math.round(v * 100)}`;
}

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return d && m ? `${d}.${m}.${y}` : iso;
}

const LEVEL: Record<AnalysisTrendTopic["evidence_level"], { label: string; cls: string }> = {
  zayif: { label: "az veri", cls: "bg-amber-500 text-amber-950" },
  orta: { label: "orta güven", cls: "bg-slate-500 text-white" },
  guclu: { label: "güçlü kanıt", cls: "bg-cyan-700 text-white" },
};

// deneme noktası — o denemede bu konudaki sonuç
function dotTone(e: AnalysisEvidenceExam): string {
  if (!e.asked) return "border border-dashed border-muted-foreground/40 bg-transparent";
  const acc = e.total ? e.correct / e.total : 0;
  if (acc >= 0.999) return "bg-emerald-500";
  if (acc > 0) return "bg-amber-400";
  return "bg-rose-500";
}

function dotTitle(e: AnalysisEvidenceExam): string {
  if (!e.asked) return `${fmtDate(e.exam_date)} · ${e.title}: bu konudan soru gelmedi`;
  return `${fmtDate(e.exam_date)} · ${e.title}: ${e.total} sorunun ${e.correct}'i doğru`
    + (e.wrong ? ` · ${e.wrong} yanlış` : "") + (e.blank ? ` · ${e.blank} boş` : "");
}

function DotStrip({ evidence }: { evidence: AnalysisEvidenceExam[] }) {
  const first = evidence.filter((e) => e.half === "first");
  const last = evidence.filter((e) => e.half === "last");
  const Dot = (e: AnalysisEvidenceExam) => (
    <span
      key={e.exam_id}
      title={dotTitle(e)}
      aria-label={dotTitle(e)}
      className={cn("inline-block size-3 shrink-0 rounded-full", dotTone(e))}
    />
  );
  return (
    <div className="flex flex-wrap items-center gap-1" aria-label="Deneme deneme sonuç şeridi">
      {first.map(Dot)}
      <span className="mx-1 h-4 w-px bg-border" aria-hidden />
      {last.map(Dot)}
    </div>
  );
}

function SidePill({
  label,
  correct,
  total,
  acc,
  emphasis,
}: {
  label: string;
  correct: number;
  total: number;
  acc: number;
  emphasis: "good" | "bad" | "neutral";
}) {
  return (
    <div className="min-w-0 flex-1 rounded-lg border border-border bg-background px-2.5 py-1.5">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="flex items-baseline gap-1.5">
        <span
          className={cn(
            "text-lg font-bold tabular-nums",
            emphasis === "good" && "text-emerald-700 dark:text-emerald-400",
            emphasis === "bad" && "text-rose-700 dark:text-rose-400",
            emphasis === "neutral" && "text-foreground",
          )}
        >
          {pct(acc)}
        </span>
        <span className="text-xs tabular-nums text-muted-foreground">
          {correct}/{total} doğru
        </span>
      </div>
    </div>
  );
}

function TrendCard({
  t,
  kind,
  onEvidence,
  studentId,
  queued,
  onQueued,
}: {
  t: AnalysisTrendTopic;
  kind: Kind;
  onEvidence: () => void;
  studentId: number | null;
  queued: boolean;
  onQueued: () => void;
}) {
  const add = useAddAgendaItems(studentId ?? 0);
  const lv = LEVEL[t.evidence_level] ?? LEVEL.zayif;
  const n = t.first_total + t.last_total;
  const lastNote =
    kind === "forgotten"
      ? [t.last_wrong ? `${t.last_wrong} yanlış` : null, t.last_blank ? `${t.last_blank} boş` : null]
          .filter(Boolean)
          .join(" · ")
      : null;
  return (
    <li
      className={cn(
        "rounded-xl border border-border border-l-4 bg-card p-3",
        kind === "forgotten" ? "border-l-rose-500" : "border-l-emerald-500",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="break-words text-sm font-semibold text-foreground">{t.topic_name}</div>
          <div className="text-xs text-muted-foreground">{t.subject_name}</div>
        </div>
        <span
          className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold", lv.cls)}
          title={`Kıyas ${n} soruya dayanıyor`}
        >
          {lv.label} · {n} soru
        </span>
      </div>

      <div className="mt-2 flex items-center gap-1.5">
        <SidePill
          label={`İlk ${t.first_exam_count} deneme`}
          correct={t.first_correct}
          total={t.first_total}
          acc={t.first_accuracy}
          emphasis={kind === "forgotten" ? "good" : "neutral"}
        />
        <ArrowRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <SidePill
          label={`Son ${t.last_exam_count} deneme`}
          correct={t.last_correct}
          total={t.last_total}
          acc={t.last_accuracy}
          emphasis={kind === "forgotten" ? "bad" : "good"}
        />
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <DotStrip evidence={t.evidence} />
        {lastNote ? (
          <span className="text-[11px] text-muted-foreground">son denemelerde {lastNote}</span>
        ) : null}
      </div>

      <div className="mt-2.5 flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" onClick={onEvidence}>
          <FileSearch className="size-4" aria-hidden />
          Kanıtı gör
        </Button>
        {studentId != null && kind === "forgotten" ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={queued || add.isPending}
            onClick={() =>
              add.mutate(
                [
                  {
                    text:
                      `${t.topic_name} tekrar edilmeli — ${t.subject_name} · ilk denemelerde `
                      + `${t.first_correct}/${t.first_total}, son denemelerde `
                      + `${t.last_correct}/${t.last_total} doğru (unutulma işareti).`,
                    key: `forgot:${t.topic_id}`,
                    source: "exam",
                  },
                ],
                { onSuccess: onQueued },
              )
            }
          >
            {queued ? <Check className="size-4" aria-hidden /> : <CalendarPlus className="size-4" aria-hidden />}
            {queued ? "Seans gündeminde" : "Seansa ekle"}
          </Button>
        ) : null}
      </div>
    </li>
  );
}

const RESULT_LABEL: Record<string, { label: string; cls: string }> = {
  dogru: { label: "Doğru", cls: "bg-emerald-600 text-white" },
  yanlis: { label: "Yanlış", cls: "bg-rose-600 text-white" },
  bos: { label: "Boş", cls: "bg-slate-500 text-white" },
};

function QuestionLine({ q }: { q: AnalysisEvidenceQuestion }) {
  const r = RESULT_LABEL[q.result] ?? RESULT_LABEL.bos;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5 text-sm">
      <span className="w-16 shrink-0 font-medium tabular-nums text-foreground">
        {q.question_no != null ? `Soru ${q.question_no}` : "Soru"}
      </span>
      <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold", r.cls)}>{r.label}</span>
      {q.student_answer || q.correct_answer ? (
        <span className="text-xs text-muted-foreground">
          Öğrenci: <b className="text-foreground">{q.student_answer || "—"}</b>
          {" · "}Doğru cevap: <b className="text-foreground">{q.correct_answer || "—"}</b>
        </span>
      ) : null}
      {q.label_raw ? (
        <span className="basis-full break-words pl-16 text-[11px] text-muted-foreground sm:basis-auto sm:pl-0">
          karnede: {q.label_raw}
        </span>
      ) : null}
    </li>
  );
}

function EvidenceGroup({ title, rows }: { title: string; rows: AnalysisEvidenceExam[] }) {
  return (
    <div>
      <h6 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h6>
      <ul className="space-y-2">
        {rows.map((e) => (
          <li key={e.exam_id} className="rounded-lg border border-border bg-card px-3 py-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="min-w-0 break-words text-sm font-medium text-foreground">{e.title}</span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {fmtDate(e.exam_date)}
                {e.asked ? ` · ${e.correct}/${e.total} doğru` : ""}
              </span>
            </div>
            {e.asked ? (
              <ul className="mt-1 divide-y divide-border/60">
                {e.questions.map((q) => (
                  <QuestionLine key={q.question_id} q={q} />
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">Bu denemede bu konudan soru gelmedi.</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function EvidenceDialog({
  t,
  kind,
  open,
  onOpenChange,
}: {
  t: AnalysisTrendTopic | null;
  kind: Kind;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
        {t ? (
          <>
            <DialogHeader>
              <DialogTitle className="break-words">
                {t.topic_name} <span className="font-normal text-muted-foreground">· {t.subject_name}</span>
              </DialogTitle>
              <DialogDescription>
                İlk {t.first_exam_count} denemede {t.first_total} sorunun {t.first_correct}&apos;i doğru (
                {pct(t.first_accuracy)}) → son {t.last_exam_count} denemede {t.last_total} sorunun{" "}
                {t.last_correct}&apos;i doğru ({pct(t.last_accuracy)}).
              </DialogDescription>
            </DialogHeader>

            <div className="flex gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
              <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>
                Bu türdeki denemeler tarih sırasıyla ikiye bölünür; konunun ilk yarıdaki doğruluğu son
                yarıyla kıyaslanır. Fark en az 34 puan ve her yarıda en az 2 soru varsa konu{" "}
                {kind === "forgotten" ? "“unutulan”" : "“gelişen”"} sayılır. Boş bırakılan soru doğru
                sayılmaz.
              </span>
            </div>
            {t.evidence_level === "zayif" ? (
              <p className="rounded-lg bg-amber-500 px-3 py-2 text-xs font-medium text-amber-950">
                Kıyas yalnız {t.first_total + t.last_total} soruya dayanıyor — tek soru sonucu
                değiştirebilir. Kesin karar için bir deneme daha görmek iyi olur.
              </p>
            ) : null}

            <div className="space-y-4">
              <EvidenceGroup title="İlk denemeler" rows={t.evidence.filter((e) => e.half === "first")} />
              <EvidenceGroup title="Son denemeler" rows={t.evidence.filter((e) => e.half === "last")} />
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

export function ExamTrendTopics({
  forgotten,
  improved,
  studentId,
}: {
  forgotten: AnalysisTrendTopic[];
  improved: AnalysisTrendTopic[];
  /** Koç yüzeyi: "Seansa ekle" görünür. Öğrenci/veli: null. */
  studentId: number | null;
}) {
  const [sel, setSel] = React.useState<{ t: AnalysisTrendTopic; kind: Kind } | null>(null);
  const [queued, setQueued] = React.useState<Set<number>>(() => new Set());
  if (!forgotten.length && !improved.length) return null;

  const column = (kind: Kind, items: AnalysisTrendTopic[]) => {
    const isF = kind === "forgotten";
    const Icon = isF ? TrendingDown : TrendingUp;
    return (
      <div className="min-w-0 space-y-2">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex size-7 items-center justify-center rounded-lg text-white",
              isF ? "bg-rose-600" : "bg-emerald-600",
            )}
          >
            <Icon className="size-4" aria-hidden />
          </span>
          <div className="min-w-0">
            <h5 className="text-sm font-semibold text-foreground">
              {isF ? "Unutulan konular" : "Gelişen konular"}{" "}
              <span className="font-normal text-muted-foreground">({items.length})</span>
            </h5>
            <p className="text-xs text-muted-foreground">
              {isF
                ? "İlk denemelerde biliyordu, son denemelerde düştü — tekrar planlanmalı."
                : "İlk denemelere göre doğruluğu belirgin arttı."}
            </p>
          </div>
        </div>
        {items.length ? (
          <ul className="space-y-2">
            {items.map((t) => (
              <TrendCard
                key={t.topic_id}
                t={t}
                kind={kind}
                studentId={studentId}
                onEvidence={() => setSel({ t, kind })}
                queued={queued.has(t.topic_id)}
                onQueued={() => setQueued((s) => new Set(s).add(t.topic_id))}
              />
            ))}
          </ul>
        ) : (
          <p className="rounded-xl border border-dashed border-border px-3 py-4 text-center text-xs text-muted-foreground">
            {isF ? "Düşüş gösteren konu yok." : "Belirgin gelişen konu henüz yok."}
          </p>
        )}
      </div>
    );
  };

  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h5 className="text-sm font-semibold text-foreground">Konu değişimleri</h5>
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span className="size-2.5 rounded-full bg-emerald-500" /> hepsi doğru
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="size-2.5 rounded-full bg-amber-400" /> kısmen
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="size-2.5 rounded-full bg-rose-500" /> hiç doğru yok
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="size-2.5 rounded-full border border-dashed border-muted-foreground/50" /> sorulmadı
          </span>
          <span>| = ilk/son deneme sınırı</span>
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {column("forgotten", forgotten)}
        {column("improved", improved)}
      </div>
      <EvidenceDialog
        t={sel?.t ?? null}
        kind={sel?.kind ?? "forgotten"}
        open={sel != null}
        onOpenChange={(v) => !v && setSel(null)}
      />
    </div>
  );
}
