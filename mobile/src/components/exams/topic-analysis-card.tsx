import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { ScrollView, Text, View } from "react-native";

import {
  getExamTopicAnalysis,
  type AnalysisCell,
  type ExamTopicAnalysisResponse,
} from "@/lib/exam-import";
import { cn } from "@/lib/utils";

/**
 * Konu × deneme analizi (Faz 4 mobil) — web ExamTopicAnalysis paritesi:
 * net fırsat listesi + unutulan/gelişen + ısı haritası (yatay kaydırmalı).
 * Koç (studentId) + öğrenci (null) aynı bileşeni kullanır; veri yoksa
 * hiç render olmaz. Salt-okuma, kredi düşmez.
 */

function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}`;
}

function pct(v: number): string {
  return `%${Math.round(v * 100)}`;
}

function cellClasses(acc: number): { bg: string; text: string } {
  if (acc >= 0.75) return { bg: "bg-emerald-500", text: "text-white" };
  if (acc >= 0.5) return { bg: "bg-emerald-200", text: "text-emerald-950" };
  if (acc > 0) return { bg: "bg-amber-200", text: "text-amber-950" };
  return { bg: "bg-rose-400", text: "text-white" };
}

export function analysisQueryKey(
  studentId: number | null,
  section: string | null,
): readonly unknown[] {
  return studentId != null
    ? (["teacher", "student", studentId, "exams", "topic-analysis", section ?? "auto"] as const)
    : (["student", "exams", "topic-analysis", section ?? "auto"] as const);
}

export function TopicAnalysisCard({
  studentId = null,
  section,
}: {
  studentId?: number | null;
  section: string | null;
}) {
  const q = useQuery<ExamTopicAnalysisResponse>({
    queryKey: analysisQueryKey(studentId, section),
    queryFn: () => getExamTopicAnalysis(studentId, section),
    staleTime: 30_000,
  });
  const d = q.data;
  if (!d || d.exams.length === 0) return null;

  const heatTopics = d.topics.slice(0, 10);
  const examIndex = new Map(d.exams.map((e, i) => [e.id, i]));
  const maxGain = d.opportunities[0]?.net_gain_per_exam ?? 0;

  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <Text className="text-sm font-semibold text-slate-800">
        Konu Analizi{" "}
        <Text className="font-normal text-slate-400">
          · {d.exams.length} deneme · {d.analyzed_question_count} soru
        </Text>
      </Text>

      {d.opportunities.length > 0 ? (
        <View className="mt-3 gap-2">
          <View className="flex-row items-center gap-1">
            <Ionicons name="locate-outline" size={14} color="#e11d48" />
            <Text className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Net fırsatı — kapanırsa deneme başına kazanç
            </Text>
          </View>
          {d.opportunities.slice(0, 5).map((o) => (
            <View key={o.topic_id}>
              <View className="flex-row items-center justify-between gap-2">
                <Text className="flex-1 text-xs text-slate-800" numberOfLines={1}>
                  <Text className="font-semibold">{o.topic_name}</Text>
                  <Text className="text-slate-400"> · {o.subject_name}</Text>
                </Text>
                <Text className="text-xs font-bold text-rose-600">
                  +{o.net_gain_per_exam} net
                </Text>
              </View>
              <View className="mt-1 flex-row items-center gap-2">
                <View className="h-1.5 flex-1 overflow-hidden rounded bg-slate-100">
                  <View
                    className="h-full rounded bg-rose-400"
                    style={{
                      width: `${maxGain ? Math.max((o.net_gain_per_exam / maxGain) * 100, 6) : 0}%`,
                    }}
                  />
                </View>
                <Text className="text-[10px] text-slate-400">
                  {o.wrong}Y {o.blank}B/{o.total} · {pct(o.accuracy)}
                </Text>
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {d.forgotten.length > 0 ? (
        <View className="mt-3 rounded-xl bg-rose-50 p-2.5">
          <View className="flex-row items-center gap-1">
            <Ionicons name="trending-down" size={14} color="#be123c" />
            <Text className="text-[11px] font-semibold text-rose-900">
              Unutulan konular
            </Text>
          </View>
          {d.forgotten.map((t) => (
            <Text key={t.topic_id} className="mt-0.5 text-[11px] text-rose-800">
              <Text className="font-semibold">{t.topic_name}</Text> ·{" "}
              {t.subject_name} — {pct(t.first_accuracy)} → {pct(t.last_accuracy)}
            </Text>
          ))}
        </View>
      ) : null}

      {d.improved.length > 0 ? (
        <View className="mt-2 rounded-xl bg-emerald-50 p-2.5">
          <View className="flex-row items-center gap-1">
            <Ionicons name="trending-up" size={14} color="#047857" />
            <Text className="text-[11px] font-semibold text-emerald-900">
              Gelişen konular
            </Text>
          </View>
          {d.improved.map((t) => (
            <Text key={t.topic_id} className="mt-0.5 text-[11px] text-emerald-800">
              <Text className="font-semibold">{t.topic_name}</Text> ·{" "}
              {t.subject_name} — {pct(t.first_accuracy)} → {pct(t.last_accuracy)}
            </Text>
          ))}
        </View>
      ) : null}

      {d.exams.length >= 2 && heatTopics.length > 0 ? (
        <View className="mt-3">
          <Text className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Konu × deneme (doğru/soru — yeşil iyi, kırmızı kötü)
          </Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} className="mt-1.5">
            <View>
              <View className="flex-row">
                <View className="w-28" />
                {d.exams.map((e) => (
                  <Text
                    key={e.id}
                    className="w-12 text-center text-[9px] font-medium text-slate-400"
                  >
                    {shortDate(e.exam_date)}
                  </Text>
                ))}
              </View>
              {heatTopics.map((t) => {
                const cells: (AnalysisCell | null)[] = d.exams.map(() => null);
                for (const c of t.cells) {
                  const i = examIndex.get(c.exam_id);
                  if (i !== undefined) cells[i] = c;
                }
                return (
                  <View key={t.topic_id} className="mt-1 flex-row items-center">
                    <Text
                      className="w-28 pr-1 text-[10px] text-slate-700"
                      numberOfLines={1}
                    >
                      {t.topic_name}
                    </Text>
                    {cells.map((c, i) =>
                      c ? (
                        <View key={i} className="w-12 items-center">
                          <View
                            className={cn(
                              "min-w-10 items-center rounded px-1 py-0.5",
                              cellClasses(c.accuracy).bg,
                            )}
                          >
                            <Text
                              className={cn(
                                "text-[10px] font-semibold",
                                cellClasses(c.accuracy).text,
                              )}
                            >
                              {c.correct}/{c.total}
                            </Text>
                          </View>
                        </View>
                      ) : (
                        <Text key={i} className="w-12 text-center text-slate-300">
                          ·
                        </Text>
                      ),
                    )}
                  </View>
                );
              })}
            </View>
          </ScrollView>
        </View>
      ) : null}

      {d.unmatched_questions > 0 ? (
        <Text className="mt-2 text-[10px] text-amber-700">
          {d.unmatched_questions} soru konuya bağlanmadan kaydedilmiş — koç web
          panelindeki &quot;Satırları düzelt&quot; ile bağlayınca analize girer.
        </Text>
      ) : null}
    </View>
  );
}
