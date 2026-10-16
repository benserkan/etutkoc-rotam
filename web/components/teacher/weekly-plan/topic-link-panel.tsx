"use client";

/**
 * "Diğer/Özet/Tekrar" görevine "N test" yazıldığında açılan uyarı + konu seçici
 * (2026-10-16, Açı Seçkin Kurs saha bulgusu). Koç görevi serbest metinle
 * verdiğinde içindeki testler hiçbir tabloya girmiyordu; panel konuyu önerir,
 * koç onaylarsa görev "konuya bağlı test" olarak kaydedilir.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link2, Loader2 } from "lucide-react";

import {
  getSubjectTopics,
  getTaskTopicSuggest,
  taskTopicKeys,
  topicOptionLabel,
  type TopicOption,
  type TopicSuggestion,
} from "@/lib/api/task-topic-link";

/** Formun kullanacağı öneri sorgusu + seçim. `touched` olmadıkça kesin öneri seçili sayılır. */
export function useTopicLink(
  studentId: number,
  subjectId: number | null,
  text: string,
  notes: string,
  count: number | null,
) {
  const enabled = subjectId !== null && count !== null && text.trim().length > 0;
  const sugQ = useQuery({
    queryKey: taskTopicKeys.suggest(studentId, subjectId ?? 0, text, notes),
    queryFn: () =>
      getTaskTopicSuggest(studentId, { subject_id: subjectId ?? 0, text, notes: notes || null }),
    enabled,
    staleTime: 60_000,
  });
  const [choice, setChoice] = React.useState<{ key: string; topicId: number | null } | null>(null);
  const key = `${subjectId}|${text}|${notes}`;
  const touched = choice !== null && choice.key === key;
  const auto = sugQ.data?.confident && sugQ.data.topic ? sugQ.data.topic.topic_id : null;
  const topicId = !enabled ? null : touched ? choice.topicId : auto;
  return {
    enabled,
    suggestion: sugQ.data ?? null,
    loading: sugQ.isLoading && enabled,
    topicId,
    setTopicId: (id: number | null) => setChoice({ key, topicId: id }),
    reset: () => setChoice(null),
  };
}

export function TopicLinkPanel({
  studentId,
  subjectId,
  count,
  suggestion,
  loading,
  value,
  onChange,
}: {
  studentId: number;
  subjectId: number;
  count: number;
  suggestion: TopicSuggestion | null;
  loading: boolean;
  value: number | null;
  onChange: (topicId: number | null) => void;
}) {
  const [showAll, setShowAll] = React.useState(false);
  const allQ = useQuery({
    queryKey: taskTopicKeys.subjectTopics(studentId, subjectId),
    queryFn: () => getSubjectTopics(studentId, subjectId),
    enabled: showAll,
    staleTime: 5 * 60_000,
  });

  const sug = suggestion;
  const options: TopicOption[] = showAll
    ? (allQ.data?.topics ?? [])
    : dedupe([...(sug?.topic ? [sug.topic] : []), ...(sug?.options ?? [])]);

  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 text-amber-900 px-3 py-2.5 text-xs space-y-2 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
      <p className="flex items-start gap-1.5">
        <Link2 className="size-3.5 shrink-0 mt-0.5" aria-hidden />
        <span>
          <strong>Bu görevde {count} test var.</strong> Bir konuya bağlarsan testler
          müfredat ilerlemesine, konu performansına ve kurum tablolarına yansır.
          Bağlamazsan görev yalnız &ldquo;yapıldı / yapılmadı&rdquo; olarak sayılır.
        </span>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label className="font-medium" htmlFor="topic-link-select">
          Konu
        </label>
        {loading ? (
          <span className="inline-flex items-center gap-1">
            <Loader2 className="size-3 animate-spin" aria-hidden /> öneri aranıyor…
          </span>
        ) : (
          <select
            id="topic-link-select"
            aria-label="Görevin konusu"
            value={value === null ? "" : String(value)}
            onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
            className="w-full min-w-0 sm:w-auto sm:flex-1 rounded-md border border-amber-300 bg-white px-2 py-1 text-xs text-slate-900 dark:border-amber-500/40 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">— konuya bağlama (etkinlik olarak kaydet) —</option>
            {options.map((o) => (
              <option key={o.topic_id} value={o.topic_id}>
                {topicOptionLabel(o)}
                {o.parent_name ? ` (${o.parent_name})` : ""}
              </option>
            ))}
          </select>
        )}
        {!showAll ? (
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className="underline underline-offset-2 font-medium"
          >
            Tüm konular
          </button>
        ) : allQ.isLoading ? (
          <Loader2 className="size-3 animate-spin" aria-hidden />
        ) : null}
      </div>
      {sug?.reason && !showAll ? <p className="text-[11px]">{sug.reason}</p> : null}
    </div>
  );
}

function dedupe(list: TopicOption[]): TopicOption[] {
  const seen = new Set<number>();
  return list.filter((o) => (seen.has(o.topic_id) ? false : (seen.add(o.topic_id), true)));
}
