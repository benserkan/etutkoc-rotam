import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DemoHint } from "@/components/demos/demo-hint";
import { ExamDetailSheet } from "@/components/exams/exam-detail-sheet";
import { ProgressReportCard } from "@/components/exams/progress-report-card";
import { ScoreEstimateCard } from "@/components/exams/score-estimate-card";
import { TopicAnalysisCard } from "@/components/exams/topic-analysis-card";
import { examProgressKeys, fmtNet, fmtTRDate } from "@/lib/exam-progress";
import { getParentExams, parentP2Keys } from "@/lib/parent";
import { cn } from "@/lib/utils";

/**
 * Veli — Deneme Analizi (mobil): özet + net gelişimi + konu analizi + gelişim ve
 * hedef + puan tahmini + deneme detayı (genel ortalama, çeldirici). Salt okuma.
 * Gizlilik: koça özel not ve koçun öğrenciye notu gösterilmez; çeldiricide
 * diğer öğrencilerle kıyas veliye kapalı.
 */

const SECTION_TONE: Record<string, { bg: string; text: string; bar: string }> = {
  lgs: { bg: "bg-cyan-50", text: "text-cyan-700", bar: "bg-cyan-500" },
  tyt: { bg: "bg-violet-50", text: "text-violet-700", bar: "bg-violet-500" },
  ayt_say: { bg: "bg-emerald-50", text: "text-emerald-700", bar: "bg-emerald-500" },
  ayt_ea: { bg: "bg-amber-50", text: "text-amber-700", bar: "bg-amber-500" },
  ayt_soz: { bg: "bg-rose-50", text: "text-rose-700", bar: "bg-rose-500" },
  ayt_dil: { bg: "bg-sky-50", text: "text-sky-700", bar: "bg-sky-500" },
};
const tone = (s: string) => SECTION_TONE[s] ?? { bg: "bg-slate-100", text: "text-slate-600", bar: "bg-slate-400" };

export default function ParentChildExamsRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const sid = id ? Number(id) : 0;
  const qc = useQueryClient();

  const examsQ = useQuery({ queryKey: parentP2Keys.exams(sid), queryFn: () => getParentExams(sid), enabled: sid > 0 });
  const exams = examsQ.data;
  const rows = React.useMemo(() => exams?.rows ?? [], [exams]);
  const [detailId, setDetailId] = React.useState<number | null>(null);
  const detail = rows.find((r) => r.id === detailId) ?? null;

  const sections = React.useMemo(() => {
    const m = new Map<string, { label: string; n: number }>();
    for (const r of rows) {
      const k = r.series_key || r.section; // tür + genel/branş
      const e = m.get(k);
      if (e) e.n += 1;
      else m.set(k, { label: r.series_label || r.section_label, n: 1 });
    }
    return [...m.entries()].map(([value, v]) => ({ value, ...v })).sort((a, b) => b.n - a.n);
  }, [rows]);
  const [sel, setSel] = React.useState<string | null>(null);
  const active = sel && sections.some((s) => s.value === sel) ? sel : sections[0]?.value ?? null;
  const chrono = rows.filter((r) => (r.series_key || r.section) === active).slice().reverse().slice(-10);
  const maxNet = Math.max(1, ...chrono.map((r) => r.net));

  const refresh = () => {
    qc.invalidateQueries({ queryKey: examProgressKeys.all(null, sid) });
    qc.invalidateQueries({ queryKey: ["parent", "student", sid] });
    void examsQ.refetch();
  };

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable
          onPress={() => router.back()}
          hitSlop={8}
          className="size-10 items-center justify-center rounded-full active:bg-slate-200"
          accessibilityLabel="Geri"
        >
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Deneme Analizi</Text>
      </View>

      <ScrollView
        className="flex-1"
        contentContainerClassName="px-4 py-3 gap-4"
        refreshControl={<RefreshControl refreshing={examsQ.isRefetching} onRefresh={refresh} tintColor="#0e7490" />}
      >
        <DemoHint contextKey="ai-insight" role="parent" />
        <Pressable
          onPress={() => router.back()}
          className="flex-row items-center gap-2.5 rounded-2xl border border-cyan-200 bg-cyan-50/60 p-4 active:bg-cyan-100"
        >
          <Ionicons name="sparkles" size={18} color="#0e7490" />
          <Text className="flex-1 text-sm text-cyan-950">
            <Text className="font-semibold">Rota&apos;nın Yorumu</Text> — deneme sonuçlarının yapay zekâ
            anlatımı çocuğunuzun sayfasında; okuyabilir ya da sesli dinleyebilirsiniz.
          </Text>
          <Ionicons name="chevron-back" size={16} color="#0e7490" />
        </Pressable>

        {examsQ.isLoading ? (
          <Text className="text-sm text-slate-400">Yükleniyor…</Text>
        ) : !exams || rows.length === 0 ? (
          <View className="rounded-xl border border-slate-200 bg-white p-6">
            <Text className="text-center text-sm text-slate-500">Henüz deneme sonucu girilmemiş.</Text>
          </View>
        ) : (
          <>
            <View className="flex-row gap-2">
              {[
                { l: "Deneme", v: String(exams.summary.count) },
                { l: "Ortalama net", v: fmtNet(exams.summary.avg_net) },
                { l: "En iyi net", v: fmtNet(exams.summary.best_net) },
              ].map((x) => (
                <View key={x.l} className="flex-1 items-center rounded-xl border border-slate-200 bg-white px-3 py-2">
                  <Text className="text-lg font-extrabold text-slate-900">{x.v}</Text>
                  <Text className="text-[10px] text-slate-400">{x.l}</Text>
                </View>
              ))}
            </View>

            {sections.length > 1 ? (
              <View className="flex-row flex-wrap gap-1.5">
                {sections.map((g) => {
                  const on = g.value === active;
                  const t = tone(g.value);
                  return (
                    <Pressable
                      key={g.value}
                      onPress={() => setSel(g.value)}
                      className={cn("rounded-full border px-3 py-1.5", on ? cn(t.bg, "border-transparent") : "border-slate-200 bg-white")}
                    >
                      <Text className={cn("text-xs font-medium", on ? t.text : "text-slate-500")}>
                        {g.label} ({g.n})
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            ) : null}

            {chrono.length >= 2 ? (
              <View className="rounded-2xl border border-slate-200 bg-white p-4">
                <Text className="text-sm font-semibold text-slate-800">Net gelişimi</Text>
                <View className="mt-3 flex-row items-end gap-1.5">
                  {chrono.map((r, i) => (
                    <View key={r.id} className="flex-1 items-center">
                      <Text className="mb-1 text-[10px] font-semibold text-slate-700">{fmtNet(r.net)}</Text>
                      <View
                        className={cn("w-full rounded-t", i === chrono.length - 1 ? tone(r.section).bar : "bg-slate-200")}
                        style={{ height: Math.max(10, Math.round((r.net / maxNet) * 96)) }}
                      />
                      <Text className="mt-1 text-[9px] text-slate-400">{fmtTRDate(r.exam_date).slice(0, 5)}</Text>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}

            <TopicAnalysisCard parentStudentId={sid} section={active} />
            <ProgressReportCard studentId={null} parentStudentId={sid} section={active} />
            <ScoreEstimateCard studentId={null} parentStudentId={sid} />

            <Text className="px-1 pt-1 text-[15px] font-semibold text-slate-800">Tüm denemeler</Text>
            {rows.map((e) => {
              const t = tone(e.section);
              return (
                <Pressable
                  key={e.id}
                  onPress={() => setDetailId(e.id)}
                  className="rounded-2xl border border-slate-200 bg-white p-4 active:bg-slate-50"
                >
                  <View className="flex-row items-start justify-between gap-2">
                    <Text className="min-w-0 flex-1 text-[15px] font-semibold text-slate-900">{e.title}</Text>
                    <View className={cn("rounded-full px-2 py-0.5", t.bg)}>
                      <Text className={cn("text-[11px] font-semibold", t.text)}>{e.section_label}</Text>
                    </View>
                  </View>
                  <Text className="mt-0.5 text-xs text-slate-400">{fmtTRDate(e.exam_date)}</Text>
                  <View className="mt-3 flex-row items-end justify-between">
                    <View>
                      <Text className="text-3xl font-extrabold text-slate-900">{fmtNet(e.net)}</Text>
                      <Text className="text-[11px] text-slate-400">net</Text>
                    </View>
                    <View className="items-end">
                      <Text className="text-xs text-slate-500">
                        <Text className="font-semibold text-emerald-600">D {e.total_correct}</Text>{"  "}
                        <Text className="font-semibold text-rose-600">Y {e.total_wrong}</Text>{"  "}
                        <Text className="text-slate-400">B {e.total_blank}</Text>
                      </Text>
                      {e.averages?.total != null ? (
                        <Text className="mt-0.5 text-[11px] text-slate-500">
                          {e.averages.label}: {fmtNet(e.averages.total)}
                        </Text>
                      ) : null}
                    </View>
                  </View>
                  <Text className="mt-2 text-right text-[11px] font-medium text-brand-700">Detay ›</Text>
                </Pressable>
              );
            })}
          </>
        )}
        <View className="h-6" />
      </ScrollView>

      <ExamDetailSheet exam={detail} studentId={null} parentStudentId={sid} share={null} onClose={() => setDetailId(null)} />
    </SafeAreaView>
  );
}
