"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Loader2, Save } from "lucide-react";

import { getStudentSurveyFill, surveyKeys } from "@/lib/api/surveys";
import { useSaveSurveyAnswers } from "@/lib/hooks/use-survey-mutations";
import type {
  StudentSurveyFillResponse,
  SurveyQuestionModel,
} from "@/lib/types/survey";
import { SurveyResultView } from "@/components/shared/survey-result-view";
import { cn } from "@/lib/utils";

/**
 * Öğrenci — anket doldurma ekranı (mobil-öncelikli, büyük dokunma hedefleri).
 *
 * likert5 → 5 büyük buton · slider10 → 1-10 sayı şeridi · open → textarea.
 * "Kaydet" kısmi ilerlemeyi saklar (sonra devam edilebilir); "Tamamla"
 * doğrular — eksik varsa ilk eksiğe kaydırıp işaretler. Tamamlanınca sonuç
 * görünümü (SurveyResultView) gösterilir.
 */

const LIKERT_LABELS = [
  "Hiç uygun değil",
  "Pek uygun değil",
  "Kararsızım",
  "Uygun",
  "Tamamen uygun",
];

export function SurveyFillClient({
  assignmentId,
  initial,
}: {
  assignmentId: number;
  initial: StudentSurveyFillResponse;
}) {
  const q = useQuery({
    queryKey: surveyKeys.studentFill(assignmentId),
    queryFn: () => getStudentSurveyFill(assignmentId),
    initialData: initial,
  });
  const data = q.data ?? initial;
  const completed = data.assignment.status === "completed";

  const [answers, setAnswers] = React.useState<Record<string, number | string>>(
    () => ({ ...data.answers }),
  );
  const [missing, setMissing] = React.useState<Set<number>>(new Set());
  const mut = useSaveSurveyAnswers(assignmentId);

  const total = data.questions.length;
  const requiredQs = data.questions.filter((qq) => qq.qtype !== "open");
  const answeredRequired = requiredQs.filter((qq) => {
    const v = answers[String(qq.id)];
    return v !== undefined && v !== null && String(v).trim() !== "";
  }).length;
  const progressPct =
    requiredQs.length > 0
      ? Math.round((answeredRequired / requiredQs.length) * 100)
      : 100;

  function setAnswer(qid: number, value: number | string) {
    setAnswers((prev) => ({ ...prev, [String(qid)]: value }));
    setMissing((prev) => {
      if (!prev.has(qid)) return prev;
      const next = new Set(prev);
      next.delete(qid);
      return next;
    });
  }

  function savePartial() {
    mut.mutate({ answers, complete: false });
  }

  function complete() {
    mut.mutate(
      { answers, complete: true },
      {
        onSuccess: (res) => {
          if (!res.data.completed && res.data.missing_question_ids.length > 0) {
            const ids = new Set(res.data.missing_question_ids);
            setMissing(ids);
            const first = data.questions.find((qq) => ids.has(qq.id));
            if (first) {
              document
                .getElementById(`survey-q-${first.id}`)
                ?.scrollIntoView({ behavior: "smooth", block: "center" });
            }
          }
        },
      },
    );
  }

  if (completed && data.result) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
        <Link
          href="/student/surveys"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden /> Anketlerim
        </Link>
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 inline-flex items-center gap-2 w-full">
          <CheckCircle2 className="size-4 shrink-0" aria-hidden />
          Bu anketi tamamladın — işte sonucun. Koçun da görüyor; birlikte
          değerlendireceksiniz.
        </div>
        <h1 className="text-xl font-semibold tracking-tight font-display">
          {data.assignment.template.title}
        </h1>
        <SurveyResultView result={data.result} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 px-4 py-6 pb-28">
      <Link
        href="/student/surveys"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> Anketlerim
      </Link>

      <header className="space-y-2">
        <h1 className="text-xl font-semibold tracking-tight font-display">
          {data.assignment.template.title}
        </h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Doğru ya da yanlış cevap yok — seni en iyi anlatan seçeneği işaretle.
          İstediğin an kaydedip sonra devam edebilirsin.
        </p>
        {data.assignment.note ? (
          <p className="text-xs rounded-md border border-cyan-200 bg-cyan-50 text-cyan-900 px-2.5 py-1.5">
            Koçundan not: {data.assignment.note}
          </p>
        ) : null}
        <p className="text-[11px] text-muted-foreground">{data.disclaimer}</p>
      </header>

      <ol className="space-y-4">
        {data.questions.map((qq, idx) => (
          <QuestionCard
            key={qq.id}
            index={idx + 1}
            total={total}
            question={qq}
            value={answers[String(qq.id)]}
            missing={missing.has(qq.id)}
            onChange={(v) => setAnswer(qq.id, v)}
          />
        ))}
      </ol>

      {/* Sabit alt eylem çubuğu */}
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-background/95 backdrop-blur px-4 py-3">
        <div className="mx-auto max-w-3xl space-y-2">
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-[#117A86] transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-[11px] tabular-nums text-muted-foreground">
              {answeredRequired}/{requiredQs.length}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={savePartial}
              disabled={mut.isPending}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50 transition"
            >
              <Save className="size-4" aria-hidden />
              Kaydet
            </button>
            <button
              type="button"
              onClick={complete}
              disabled={mut.isPending}
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-md bg-[#117A86] text-white px-4 py-2 text-sm font-medium hover:bg-[#0d626c] disabled:opacity-50 transition"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <CheckCircle2 className="size-4" aria-hidden />
              )}
              Anketi Tamamla
            </button>
          </div>
          {missing.size > 0 ? (
            <p className="text-xs text-rose-700">
              {missing.size} soru eksik kaldı — kırmızı işaretli soruları
              cevaplayıp tekrar tamamla.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function QuestionCard({
  index,
  total,
  question,
  value,
  missing,
  onChange,
}: {
  index: number;
  total: number;
  question: SurveyQuestionModel;
  value: number | string | undefined;
  missing: boolean;
  onChange: (v: number | string) => void;
}) {
  return (
    <li
      id={`survey-q-${question.id}`}
      className={cn(
        "rounded-lg border p-3.5 space-y-3 scroll-mt-24",
        missing ? "border-rose-400 bg-rose-50/50" : "border-border bg-card",
      )}
    >
      <p className="text-sm leading-relaxed">
        <span className="text-muted-foreground tabular-nums mr-1.5">
          {index}/{total}
        </span>
        {question.text}
      </p>

      {question.qtype === "likert5" ? (
        <div className="grid grid-cols-5 gap-1.5">
          {LIKERT_LABELS.map((label, i) => {
            const v = i + 1;
            const active = value === v;
            return (
              <button
                key={v}
                type="button"
                onClick={() => onChange(v)}
                aria-pressed={active}
                title={label}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-md border px-1 py-2 transition",
                  active
                    ? "border-[#117A86] bg-[#117A86] text-white"
                    : "border-border bg-background hover:bg-muted",
                )}
              >
                <span className="text-base font-semibold tabular-nums">{v}</span>
                <span
                  className={cn(
                    "text-[9px] leading-tight text-center",
                    active ? "text-white/90" : "text-muted-foreground",
                  )}
                >
                  {label}
                </span>
              </button>
            );
          })}
        </div>
      ) : null}

      {question.qtype === "slider10" ? (
        <div className="grid grid-cols-10 gap-1">
          {Array.from({ length: 10 }, (_, i) => i + 1).map((v) => {
            const active = value === v;
            return (
              <button
                key={v}
                type="button"
                onClick={() => onChange(v)}
                aria-pressed={active}
                className={cn(
                  "rounded-md border py-2 text-sm font-medium tabular-nums transition",
                  active
                    ? "border-[#117A86] bg-[#117A86] text-white"
                    : "border-border bg-background hover:bg-muted",
                )}
              >
                {v}
              </button>
            );
          })}
        </div>
      ) : null}

      {question.qtype === "open" ? (
        <textarea
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          placeholder="Kendi cümlelerinle yaz… (boş bırakabilirsin)"
          className="w-full px-3 py-2 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      ) : null}

      {question.qtype === "choice" && question.options.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {question.options.map((o) => {
            const active = value === o.value;
            return (
              <button
                key={o.value}
                type="button"
                onClick={() => onChange(o.value)}
                aria-pressed={active}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-sm transition",
                  active
                    ? "border-[#117A86] bg-[#117A86] text-white"
                    : "border-border bg-background hover:bg-muted",
                )}
              >
                {o.label}
              </button>
            );
          })}
        </div>
      ) : null}
    </li>
  );
}
