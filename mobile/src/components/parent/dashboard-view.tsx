import { Ionicons } from "@expo/vector-icons";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import type { ParentChildSummary, WarningLevel } from "@/lib/parent";
import { cn } from "@/lib/utils";
import { QuickAccessStrip } from "@/components/quick-access-strip";

const WARN: Record<WarningLevel, { border: string; dot: string; label: string; text: string }> = {
  red: { border: "border-l-rose-500", dot: "bg-rose-500", label: "Acil", text: "text-rose-700" },
  amber: { border: "border-l-amber-400", dot: "bg-amber-400", label: "Dikkat", text: "text-amber-700" },
  green: { border: "border-l-emerald-500", dot: "bg-emerald-500", label: "Yolunda", text: "text-emerald-700" },
};

const SECTION_SHORT: Record<string, string> = {
  lgs: "LGS", tyt: "TYT", ayt_say: "AYT", ayt_ea: "AYT", ayt_soz: "AYT", ayt_dil: "YDT",
};
const RELATION: Record<string, string> = {
  anne: "Anne", baba: "Baba", vasi: "Vasi", diger: "Veli",
};

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <View className="flex-1 rounded-xl bg-slate-50 px-3 py-2.5">
      <Text className="text-[11px] text-slate-500">{label}</Text>
      <Text className="text-base font-bold text-slate-900">{value}</Text>
      {sub ? <Text className="text-[10px] text-slate-400">{sub}</Text> : null}
    </View>
  );
}

function ChildCard({ c, onPress }: { c: ParentChildSummary; onPress?: () => void }) {
  const w = WARN[c.warning_level];
  const grade =
    c.display_grade_label ?? (c.grade_level != null ? `${c.grade_level}. sınıf` : "");
  const relation = c.relation ? RELATION[c.relation] ?? null : null;

  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      className={cn("rounded-2xl border border-l-4 border-slate-200 bg-white p-4", w.border, onPress && "active:bg-slate-50")}
    >
      <View className="flex-row items-center gap-2">
        <View className="flex-1">
          <Text className="text-lg font-bold text-slate-900">{c.full_name}</Text>
          <Text className="text-xs text-slate-500">
            {grade}
            {relation ? ` · ${relation}` : ""}
          </Text>
        </View>
        <View className="flex-row items-center gap-1.5">
          <View className={cn("size-2 rounded-full", w.dot)} />
          <Text className={cn("text-xs font-semibold", w.text)}>{w.label}</Text>
        </View>
        {onPress ? <Ionicons name="chevron-forward" size={18} color="#cbd5e1" /> : null}
      </View>

      <View className="mt-3 flex-row gap-2">
        <Metric label="Bugün" value={`${c.today_gorev_done}/${c.today_gorev_total}`} sub="görev" />
        <Metric label="Son 7 gün" value={c.week_gorev_rate != null ? `%${c.week_gorev_rate}` : "—"} sub="tutturma" />
        <Metric label="Tutarlılık" value={c.consistency_7d != null ? `%${c.consistency_7d}` : "—"} />
      </View>

      {c.latest_exam_title ? (
        <View className="mt-3 flex-row items-center justify-between rounded-xl bg-cyan-50 p-3">
          <View className="flex-1 pr-2">
            <Text className="text-[11px] font-semibold uppercase tracking-wide text-cyan-700">Son deneme</Text>
            <Text className="text-sm text-cyan-900" numberOfLines={1}>{c.latest_exam_title}</Text>
          </View>
          <View className="items-end">
            <Text className="text-xl font-extrabold text-cyan-800">
              {c.latest_exam_net}
              <Text className="text-xs font-semibold"> net</Text>
            </Text>
            {c.latest_exam_section ? (
              <Text className="text-[11px] text-cyan-600">
                {SECTION_SHORT[c.latest_exam_section] ?? c.latest_exam_section.toUpperCase()}
                {c.latest_exam_count > 1 ? ` · ${c.latest_exam_count} deneme` : ""}
              </Text>
            ) : null}
          </View>
        </View>
      ) : null}
    </Pressable>
  );
}

export function ParentDashboardView({
  children,
  onOpenChild,
  refreshing = false,
  onRefresh,
}: {
  children: ParentChildSummary[];
  onOpenChild?: (id: number) => void;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ScrollView
        contentContainerClassName="px-4 py-4 gap-3"
        refreshControl={
          onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined
        }
      >
        <Text className="px-1 text-xl font-bold text-slate-900">Çocuklarım</Text>
        <QuickAccessStrip padded={false} />
        {children.length === 0 ? (
          <View className="mt-10 items-center gap-3 px-6">
            <Ionicons name="people-outline" size={44} color="#94a3b8" />
            <Text className="text-center text-base font-semibold text-slate-700">Bağlı öğrenci yok</Text>
            <Text className="text-center text-sm text-slate-500">
              Koç davet gönderdiğinde çocuğun burada görünür.
            </Text>
          </View>
        ) : (
          children.map((c) => (
            <ChildCard key={c.student_id} c={c} onPress={onOpenChild ? () => onOpenChild(c.student_id) : undefined} />
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
