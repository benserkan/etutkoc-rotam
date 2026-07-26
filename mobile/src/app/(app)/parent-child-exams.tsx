import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { getParentExams, parentP2Keys } from "@/lib/parent";
import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";

const SECTION_TONE: Record<string, { bg: string; text: string }> = {
  lgs: { bg: "bg-cyan-50", text: "text-cyan-700" },
  tyt: { bg: "bg-violet-50", text: "text-violet-700" },
  ayt_say: { bg: "bg-emerald-50", text: "text-emerald-700" },
  ayt_ea: { bg: "bg-amber-50", text: "text-amber-700" },
  ayt_soz: { bg: "bg-rose-50", text: "text-rose-700" },
  ayt_dil: { bg: "bg-sky-50", text: "text-sky-700" },
};

export default function ParentChildExamsRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const sid = id ? Number(id) : 0;

  const examsQ = useQuery({ queryKey: parentP2Keys.exams(sid), queryFn: () => getParentExams(sid), enabled: sid > 0 });
  const exams = examsQ.data;

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-200" accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Denemeler & Analiz</Text>
      </View>

      <ScrollView className="flex-1" contentContainerClassName="px-4 py-3 gap-4">
        <DemoHint contextKey="ai-insight" role="parent" />
        {/* Rota'nın Yorumu'na yönlendirme — eski AI kartı oraya gömüldü */}
        <Pressable
          onPress={() => router.back()}
          className="flex-row items-center gap-2.5 rounded-2xl border border-cyan-200 bg-cyan-50/60 p-4 active:bg-cyan-100"
        >
          <Ionicons name="sparkles" size={18} color="#0e7490" />
          <Text className="flex-1 text-sm text-cyan-950">
            <Text className="font-semibold">Rota&apos;nın Yorumu</Text> — deneme
            sonuçlarının yapay zekâ anlatımı artık çocuğunun sayfasında; okuyabilir
            ya da sesli dinleyebilirsin.
          </Text>
          <Ionicons name="chevron-back" size={16} color="#0e7490" />
        </Pressable>

        {/* Deneme geçmişi */}
        <View className="gap-2">
          <Text className="text-[15px] font-semibold text-slate-800">Deneme Geçmişi</Text>
          {examsQ.isLoading ? (
            <Text className="text-sm text-slate-400">Yükleniyor…</Text>
          ) : !exams || exams.rows.length === 0 ? (
            <View className="rounded-xl border border-slate-200 bg-white p-6">
              <Text className="text-center text-sm text-slate-500">Henüz deneme sonucu girilmemiş.</Text>
            </View>
          ) : (
            <>
              <View className="flex-row gap-2">
                <View className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 items-center">
                  <Text className="text-lg font-extrabold text-slate-900">{exams.summary.count}</Text>
                  <Text className="text-[10px] text-slate-400">Deneme</Text>
                </View>
                <View className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 items-center">
                  <Text className="text-lg font-extrabold text-slate-900">{exams.summary.avg_net}</Text>
                  <Text className="text-[10px] text-slate-400">Ortalama net</Text>
                </View>
                <View className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 items-center">
                  <Text className="text-lg font-extrabold text-slate-900">{exams.summary.best_net}</Text>
                  <Text className="text-[10px] text-slate-400">En iyi net</Text>
                </View>
              </View>
              {exams.rows.map((e) => {
                const t = SECTION_TONE[e.section] ?? { bg: "bg-slate-100", text: "text-slate-600" };
                return (
                  <View key={e.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                    <View className="flex-row items-start justify-between gap-2">
                      <Text className="min-w-0 flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={2}>{e.title}</Text>
                      <View className={cn("rounded-full px-2 py-0.5", t.bg)}>
                        <Text className={cn("text-[11px] font-semibold", t.text)}>{e.section_label}</Text>
                      </View>
                    </View>
                    <Text className="mt-0.5 text-xs text-slate-400">{e.exam_date}</Text>
                    <View className="mt-3 flex-row items-end justify-between">
                      <View>
                        <Text className="text-3xl font-extrabold text-slate-900">{e.net}</Text>
                        <Text className="text-[11px] text-slate-400">net</Text>
                      </View>
                      <Text className="text-xs text-slate-500">
                        <Text className="font-semibold text-emerald-600">D {e.total_correct}</Text>{"  "}
                        <Text className="font-semibold text-rose-600">Y {e.total_wrong}</Text>{"  "}
                        <Text className="text-slate-400">B {e.total_blank}</Text>
                      </Text>
                    </View>
                    {e.subjects && e.subjects.length > 0 ? (
                      <View className="mt-2 flex-row flex-wrap gap-1.5 border-t border-slate-100 pt-2">
                        {e.subjects.map((s, i) => (
                          <View key={i} className="rounded-md bg-slate-100 px-2 py-0.5">
                            <Text className="text-[11px] text-slate-600">{s.name}: <Text className="font-semibold text-slate-900">{s.net}</Text></Text>
                          </View>
                        ))}
                      </View>
                    ) : null}
                  </View>
                );
              })}
            </>
          )}
        </View>
        <View className="h-6" />
      </ScrollView>
    </SafeAreaView>
  );
}
