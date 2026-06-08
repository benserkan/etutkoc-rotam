import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ApiError } from "@/lib/api";
import {
  generateParentInsight,
  getParentExams,
  getParentInsight,
  parentP2Keys,
  type ParentInsightResponse,
} from "@/lib/parent";
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

function InsightList({ icon, color, title, items }: { icon: keyof typeof Ionicons.glyphMap; color: string; title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <View className="gap-1.5">
      <View className="flex-row items-center gap-1.5">
        <Ionicons name={icon} size={15} color={color} />
        <Text className="text-sm font-semibold text-slate-700">{title}</Text>
      </View>
      {items.map((s, i) => (
        <View key={i} className="flex-row gap-2">
          <Text className="text-slate-400">•</Text>
          <Text className="flex-1 text-sm leading-5 text-slate-700">{s}</Text>
        </View>
      ))}
    </View>
  );
}

export default function ParentChildExamsRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const sid = id ? Number(id) : 0;
  const qc = useQueryClient();

  const examsQ = useQuery({ queryKey: parentP2Keys.exams(sid), queryFn: () => getParentExams(sid), enabled: sid > 0 });
  const insightQ = useQuery({ queryKey: parentP2Keys.insight(sid), queryFn: () => getParentInsight(sid), enabled: sid > 0 });

  const genMut = useMutation({
    mutationFn: () => generateParentInsight(sid),
    onSuccess: (data: ParentInsightResponse) => qc.setQueryData(parentP2Keys.insight(sid), data),
    onError: (e) => {
      const code = e instanceof ApiError ? e.code : null;
      if (code === "not_enough_data") Alert.alert("Yeterli veri yok", "Çocuğunuz test çözüp doğru/yanlış girdikçe veya deneme eklendikçe analiz oluşturulabilir.");
      else if (code === "ai_credit_exhausted") Alert.alert("Kredi doldu", "Koçun yapay zekâ kredisi bu ay için dolmuş. Daha sonra tekrar deneyin.");
      else if (code === "ai_not_available") Alert.alert("Kullanılamıyor", e instanceof ApiError ? e.message : "Yapay zekâ analizi şu an kullanılamıyor.");
      else if (code === "ai_unavailable") Alert.alert("Yapay zekâ kullanılamıyor", "Birkaç dakika sonra tekrar deneyin.");
      else Alert.alert("Oluşturulamadı", e instanceof ApiError ? e.message : "İşlem başarısız.");
    },
  });

  const insight = insightQ.data?.insight ?? null;
  const aiAvailable = insightQ.data?.ai_available ?? false;
  const isStale = insightQ.data?.is_stale ?? false;
  const reason = insightQ.data?.unavailable_reason ?? null;
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
        {/* AI içgörü */}
        <View className="rounded-2xl border border-violet-200 bg-violet-50/50 p-4">
          <View className="mb-2 flex-row items-center gap-1.5">
            <Ionicons name="sparkles" size={18} color="#7c3aed" />
            <Text className="text-[15px] font-semibold text-violet-900">Yapay Zekâ Durum Analizi</Text>
          </View>

          {insightQ.isLoading ? (
            <Text className="text-sm text-slate-400">Yükleniyor…</Text>
          ) : insight ? (
            <View className="gap-3">
              {isStale ? (
                <View className="flex-row items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5">
                  <Ionicons name="time-outline" size={15} color="#b45309" style={{ marginTop: 1 }} />
                  <Text className="flex-1 text-xs text-amber-800">Bu analizden sonra yeni veri eklendi. Güncel analiz için yenileyin.</Text>
                </View>
              ) : null}
              <Text className="text-sm leading-6 text-slate-800">{insight.summary}</Text>
              <InsightList icon="heart-outline" color="#059669" title="Güçlü yanlar" items={insight.strengths} />
              <InsightList icon="locate-outline" color="#d97706" title="Gelişim alanları" items={insight.focus_areas} />
              <InsightList icon="sparkles-outline" color="#7c3aed" title="Evde nasıl destek olabilirsiniz" items={insight.parent_tips} />
              <View className="flex-row items-center justify-between border-t border-violet-100 pt-3">
                <Text className="text-[11px] text-slate-400">Öneri amaçlıdır.</Text>
                {aiAvailable ? (
                  <Pressable onPress={() => genMut.mutate()} disabled={genMut.isPending}
                    className="flex-row items-center gap-1.5 rounded-lg border border-violet-300 px-3 py-2 active:bg-violet-50">
                    <Ionicons name="refresh" size={14} color="#7c3aed" />
                    <Text className="text-sm font-semibold text-violet-700">{genMut.isPending ? "Yenileniyor…" : "Yenile"}</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>
          ) : aiAvailable ? (
            <View className="gap-3">
              <Text className="text-sm text-slate-700">Çocuğunuzun ders/konu performansı ve deneme sonuçlarından yapay zekâ ile sade bir durum analizi oluşturun.</Text>
              <Text className="text-[11px] text-slate-400">Bu analiz çocuğunuzun çalışma verilerini yapay zekâ ile işler. Sonucu yalnız siz görürsünüz.</Text>
              <Pressable onPress={() => genMut.mutate()} disabled={genMut.isPending}
                className={cn("flex-row items-center justify-center gap-2 rounded-xl py-3.5", genMut.isPending ? "bg-violet-300" : "bg-violet-600 active:bg-violet-700")}>
                <Ionicons name="sparkles" size={18} color="#fff" />
                <Text className="text-base font-semibold text-white">{genMut.isPending ? "Oluşturuluyor…" : "Çocuğum için analiz oluştur"}</Text>
              </Pressable>
            </View>
          ) : (
            <Text className="text-sm text-slate-600">{reason ?? "Yapay zekâ analizi şu an kullanılamıyor."}</Text>
          )}
        </View>

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
