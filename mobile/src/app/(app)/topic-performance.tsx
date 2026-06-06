import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  getTopicPerformance,
  topicPerfKeys,
  type SubjectPerfRow,
  type TopicPerfSource,
  type TopicPerformanceResponse,
} from "@/lib/topic-performance";
import { cn } from "@/lib/utils";

function accTone(pct: number | null): { text: string; bar: string; bg: string } {
  if (pct == null) return { text: "text-slate-400", bar: "bg-slate-300", bg: "bg-slate-100" };
  if (pct >= 70) return { text: "text-emerald-700", bar: "bg-emerald-500", bg: "bg-emerald-50" };
  if (pct >= 40) return { text: "text-amber-700", bar: "bg-amber-500", bg: "bg-amber-50" };
  return { text: "text-rose-700", bar: "bg-rose-500", bg: "bg-rose-50" };
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function SummaryCard({ label, value, tone }: { label: string; value: string; tone?: "emerald" | "amber" | "rose" }) {
  const c = tone === "emerald" ? "text-emerald-700" : tone === "amber" ? "text-amber-700" : tone === "rose" ? "text-rose-700" : "text-slate-900";
  return (
    <View className="flex-1 rounded-xl border border-slate-200 bg-white px-2.5 py-2">
      <Text className={cn("text-lg font-extrabold", c)}>{value}</Text>
      <Text className="text-[10px] text-slate-400">{label}</Text>
    </View>
  );
}

function SubjectCard({ s }: { s: SubjectPerfRow }) {
  const [open, setOpen] = React.useState(false);
  const t = accTone(s.accuracy_pct);
  return (
    <View className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <Pressable onPress={() => setOpen((v) => !v)} className="flex-row items-center gap-2.5 px-4 py-3 active:bg-slate-50">
        <Ionicons name={open ? "chevron-down" : "chevron-forward"} size={16} color="#94a3b8" />
        <View className="min-w-0 flex-1">
          <Text className="text-sm font-semibold text-slate-900" numberOfLines={1}>{s.subject_name}</Text>
          <Text className="text-[11px] text-slate-400">
            {s.tests_solved} test · {s.topics.length} konu · <Text className="text-emerald-600">{s.correct}D</Text> / <Text className="text-rose-600">{s.wrong}Y</Text>
          </Text>
        </View>
        <View className={cn("rounded-full px-2 py-0.5", t.bg)}>
          <Text className={cn("text-xs font-semibold", t.text)}>{s.accuracy_pct == null ? "D/Y yok" : `%${s.accuracy_pct}`}</Text>
        </View>
      </Pressable>
      {s.accuracy_pct != null ? (
        <View className="mx-4 mb-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <View className={cn("h-full rounded-full", t.bar)} style={{ width: `${s.accuracy_pct}%` }} />
        </View>
      ) : null}
      {open ? (
        <View className="border-t border-slate-100 px-2 py-1.5">
          {s.topics.map((tp) => {
            const tt = accTone(tp.accuracy_pct);
            return (
              <View key={`${tp.topic_id ?? "l"}-${tp.topic_name}`} className="rounded-lg px-2 py-2">
                <View className="flex-row items-center justify-between gap-2">
                  <Text className="min-w-0 flex-1 text-[13px] font-medium text-slate-800" numberOfLines={1}>{tp.topic_name}</Text>
                  <Text className={cn("text-xs font-semibold", tt.text)}>{tp.accuracy_pct == null ? "—" : `%${tp.accuracy_pct}`}</Text>
                </View>
                <View className="mt-1 flex-row items-center gap-3">
                  <Text className="text-[11px] text-slate-400">{tp.tests_solved} test</Text>
                  <Text className="text-[11px] text-emerald-600">{tp.correct}D</Text>
                  <Text className="text-[11px] text-rose-600">{tp.wrong}Y</Text>
                  {tp.last_solved_at ? <Text className="ml-auto text-[11px] text-slate-400">son: {fmtDate(tp.last_solved_at)}</Text> : null}
                </View>
                {tp.accuracy_pct != null ? (
                  <View className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-100">
                    <View className={cn("h-full rounded-full", tt.bar)} style={{ width: `${tp.accuracy_pct}%` }} />
                  </View>
                ) : null}
              </View>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

export default function TopicPerformanceRoute() {
  const params = useLocalSearchParams<{ source?: string; id?: string }>();
  const source = (params.source ?? "student") as TopicPerfSource;
  const sid = params.id ? Number(params.id) : undefined;

  const key = source === "student" ? topicPerfKeys.student() : source === "parent" ? topicPerfKeys.parent(sid ?? 0) : topicPerfKeys.teacher(sid ?? 0);
  const q = useQuery<TopicPerformanceResponse>({ queryKey: key, queryFn: () => getTopicPerformance(source, sid) });

  const who = source === "parent" ? "Çocuğunuzun" : source === "student" ? "Senin" : "Öğrencinin";

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-200" accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Konu Performansı</Text>
      </View>

      {q.isLoading ? (
        <View className="items-center py-16"><ActivityIndicator size="large" color="#0e7490" /></View>
      ) : q.isError || !q.data ? (
        <View className="items-center gap-3 py-16 px-8">
          <Text className="text-center text-sm font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : q.data.subjects.length === 0 ? (
        <View className="items-center gap-2 px-8 py-16">
          <Ionicons name="locate-outline" size={36} color="#94a3b8" />
          <Text className="text-center text-sm font-medium text-slate-700">Henüz konu performansı yok</Text>
          <Text className="text-center text-xs text-slate-400">
            {source === "student"
              ? "Test çözüp doğru/yanlış sayını girdikçe her dersin konularındaki performansın burada birikir."
              : `${who} çözdüğü testlerde doğru/yanlış girildikçe ders ve konu bazında performans burada görünür.`}
          </Text>
        </View>
      ) : (
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-3 gap-3">
          <View className="rounded-xl border border-slate-200 bg-white px-3 py-2.5">
            <Text className="text-[11px] leading-relaxed text-slate-500">
              Her dersin konularında çözülen test ve doğru/yanlış oranı. <Text className="font-medium text-slate-700">Doğruluk</Text> = doğru ÷ (doğru+yanlış). Kırmızı konular tekrar ister.
            </Text>
          </View>
          <View className="flex-row gap-2">
            <SummaryCard label="Çözülen test" value={String(q.data.overall.tests_solved)} />
            <SummaryCard label="Doğru" value={String(q.data.overall.correct)} tone="emerald" />
            <SummaryCard label="Yanlış" value={String(q.data.overall.wrong)} tone="rose" />
            <SummaryCard
              label="Doğruluk"
              value={q.data.overall.accuracy_pct == null ? "—" : `%${q.data.overall.accuracy_pct}`}
              tone={q.data.overall.accuracy_pct == null ? undefined : q.data.overall.accuracy_pct >= 70 ? "emerald" : q.data.overall.accuracy_pct >= 40 ? "amber" : "rose"}
            />
          </View>
          {q.data.subjects.map((s) => <SubjectCard key={s.subject_id} s={s} />)}
          <View className="h-6" />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
