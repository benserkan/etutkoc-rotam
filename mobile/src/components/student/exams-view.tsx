import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import type { ExamRow, StudentExamsResponse } from "@/lib/student";
import { cn } from "@/lib/utils";

const TR_MONTHS_SHORT = [
  "Oca", "Şub", "Mar", "Nis", "May", "Haz",
  "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
];
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}

const SECTION_TONE: Record<string, { bg: string; text: string; bar: string }> = {
  lgs: { bg: "bg-cyan-50", text: "text-cyan-700", bar: "bg-cyan-500" },
  tyt: { bg: "bg-violet-50", text: "text-violet-700", bar: "bg-violet-500" },
  ayt_say: { bg: "bg-emerald-50", text: "text-emerald-700", bar: "bg-emerald-500" },
  ayt_ea: { bg: "bg-amber-50", text: "text-amber-700", bar: "bg-amber-500" },
  ayt_soz: { bg: "bg-rose-50", text: "text-rose-700", bar: "bg-rose-500" },
  ayt_dil: { bg: "bg-sky-50", text: "text-sky-700", bar: "bg-sky-500" },
};
function tone(section: string) {
  return SECTION_TONE[section] ?? { bg: "bg-slate-100", text: "text-slate-600", bar: "bg-slate-400" };
}

interface SectionGroup {
  section: string;
  label: string;
  rows: ExamRow[]; // DESC (en yeni ilk)
}
function groupBySection(rows: ExamRow[]): SectionGroup[] {
  const map = new Map<string, SectionGroup>();
  for (const r of rows) {
    const g = map.get(r.section);
    if (g) g.rows.push(r);
    else map.set(r.section, { section: r.section, label: r.section_label, rows: [r] });
  }
  return Array.from(map.values()).sort((a, b) => b.rows.length - a.rows.length);
}

function StatBox({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <View className="flex-1 items-center">
      <Text className="text-2xl font-extrabold text-white">{value}</Text>
      <Text className="text-[11px] text-brand-100">{label}</Text>
      {sub ? <Text className="text-[10px] text-brand-100/80">{sub}</Text> : null}
    </View>
  );
}

function NetTrend({ group }: { group: SectionGroup }) {
  // Kronolojik (eski → yeni), son 10
  const chrono = [...group.rows].reverse().slice(-10);
  const maxNet = Math.max(1, ...chrono.map((r) => r.net));
  const t = tone(group.section);
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="flex-row items-center justify-between">
        <Text className="text-sm font-semibold text-slate-800">Net gelişimi</Text>
        <View className={cn("rounded-full px-2 py-0.5", t.bg)}>
          <Text className={cn("text-[11px] font-semibold", t.text)}>{group.label}</Text>
        </View>
      </View>
      {chrono.length < 2 ? (
        <Text className="mt-3 text-sm text-slate-400">
          Grafik için en az 2 {group.label} denemesi gerekir.
        </Text>
      ) : (
        <View className="mt-3 flex-row items-end gap-1.5">
          {chrono.map((r, i) => {
            // Sabit piksel yükseklik — RN'de % yükseklik sabit-yükseklikli ebeveyn ister.
            const px = Math.max(10, Math.round((r.net / maxNet) * 96));
            return (
              <View key={r.id} className="flex-1 items-center">
                <Text className="mb-1 text-[10px] font-semibold text-slate-700">{r.net}</Text>
                <View
                  className={cn("w-full rounded-t", i === chrono.length - 1 ? t.bar : "bg-slate-200")}
                  style={{ height: px }}
                />
                <Text className="mt-1 text-[9px] text-slate-400">{shortDate(r.exam_date)}</Text>
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}

function ExamCard({ exam }: { exam: ExamRow }) {
  const t = tone(exam.section);
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="flex-row items-start justify-between gap-2">
        <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={2}>
          {exam.title}
        </Text>
        <View className={cn("rounded-full px-2 py-0.5", t.bg)}>
          <Text className={cn("text-[11px] font-semibold", t.text)}>{exam.section_label}</Text>
        </View>
      </View>
      <Text className="mt-0.5 text-xs text-slate-400">{shortDate(exam.exam_date)}</Text>
      <View className="mt-3 flex-row items-end justify-between">
        <View>
          <Text className="text-3xl font-extrabold text-slate-900">{exam.net}</Text>
          <Text className="text-[11px] text-slate-400">net</Text>
        </View>
        <View className="items-end">
          <Text className="text-xs text-slate-500">
            <Text className="font-semibold text-emerald-600">D {exam.total_correct}</Text>
            {"  "}
            <Text className="font-semibold text-rose-600">Y {exam.total_wrong}</Text>
            {"  "}
            <Text className="text-slate-400">B {exam.total_blank}</Text>
          </Text>
          <Text className="mt-0.5 text-[11px] text-slate-400">{exam.total_questions} soru</Text>
        </View>
      </View>
    </View>
  );
}

export function ExamsView({
  data,
  refreshing = false,
  onRefresh,
}: {
  data: StudentExamsResponse;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const groups = React.useMemo(() => groupBySection(data.rows), [data.rows]);
  const [sel, setSel] = React.useState<string | null>(groups[0]?.section ?? null);
  const selGroup = groups.find((g) => g.section === sel) ?? groups[0];

  const s = data.summary;
  const trendUp = (s.trend_delta ?? 0) >= 0;

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ScrollView
        contentContainerClassName="px-4 py-4 gap-4"
        refreshControl={
          onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined
        }
      >
        {s.count === 0 ? (
          <View className="mt-10 items-center gap-3 px-6">
            <Ionicons name="bar-chart-outline" size={44} color="#94a3b8" />
            <Text className="text-center text-base font-semibold text-slate-700">
              Henüz deneme sonucu yok
            </Text>
            <Text className="text-center text-sm text-slate-500">
              Koçun deneme sonuçlarını girdiğinde netlerin ve gelişimin burada görünür.
            </Text>
          </View>
        ) : (
          <>
            {/* Özet */}
            <View className="rounded-2xl bg-brand-700 p-5">
              <Text className="text-xs font-semibold uppercase tracking-wider text-brand-100">
                Denemelerin · {s.count} sonuç
              </Text>
              <View className="mt-3 flex-row">
                <StatBox label="Ortalama" value={String(s.avg_net)} />
                <StatBox label="En iyi" value={String(s.best_net)} />
                <StatBox label="Son net" value={s.last_net != null ? String(s.last_net) : "—"} />
              </View>
              {s.trend_delta != null ? (
                <View className="mt-3 flex-row items-center justify-center gap-1">
                  <Ionicons
                    name={trendUp ? "trending-up" : "trending-down"}
                    size={16}
                    color={trendUp ? "#6ee7b7" : "#fda4af"}
                  />
                  <Text className={cn("text-xs font-semibold", trendUp ? "text-emerald-200" : "text-rose-200")}>
                    İlk denemeye göre {trendUp ? "+" : ""}{s.trend_delta} net
                  </Text>
                </View>
              ) : null}
            </View>

            {/* Net trend (tür seçici — ölçek karışmasın) */}
            {groups.length > 1 ? (
              <View className="flex-row flex-wrap gap-1.5">
                {groups.map((g) => {
                  const active = g.section === selGroup?.section;
                  const t = tone(g.section);
                  return (
                    <Text
                      key={g.section}
                      onPress={() => setSel(g.section)}
                      className={cn(
                        "overflow-hidden rounded-full px-3 py-1.5 text-xs font-medium",
                        active ? cn(t.bg, t.text) : "bg-white text-slate-500 border border-slate-200",
                      )}
                    >
                      {g.label} ({g.rows.length})
                    </Text>
                  );
                })}
              </View>
            ) : null}
            {selGroup ? <NetTrend group={selGroup} /> : null}

            {/* Liste */}
            <Text className="px-1 pt-1 text-sm font-semibold text-slate-700">Tüm denemeler</Text>
            <View className="gap-2.5">
              {data.rows.map((e) => (
                <ExamCard key={e.id} exam={e} />
              ))}
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
