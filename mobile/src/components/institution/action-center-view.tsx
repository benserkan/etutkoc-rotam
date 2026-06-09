import { Ionicons } from "@expo/vector-icons";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import type { ActionCenterItem, ActionCenterResponse } from "@/lib/institution";
import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";

const SEV: Record<string, { card: string; chip: string; chipText: string; icon: keyof typeof Ionicons.glyphMap; label: string }> = {
  critical: { card: "border-l-rose-500", chip: "bg-rose-50", chipText: "text-rose-700", icon: "alert-circle", label: "Kritik" },
  warn: { card: "border-l-amber-400", chip: "bg-amber-50", chipText: "text-amber-700", icon: "warning", label: "Uyarı" },
  info: { card: "border-l-sky-400", chip: "bg-sky-50", chipText: "text-sky-700", icon: "information-circle", label: "Bilgi" },
};
const CAT_ICON: Record<string, keyof typeof Ionicons.glyphMap> = {
  empty_program: "calendar-outline",
  low_compliance: "trending-down-outline",
  at_risk: "pulse-outline",
  inactive_program: "alarm-outline",
};

function Card({ item }: { item: ActionCenterItem }) {
  const s = SEV[item.severity] ?? SEV.info;
  return (
    <View className={cn("rounded-2xl border border-l-4 border-slate-200 bg-white p-4", s.card)}>
      <View className="flex-row items-center justify-between gap-2">
        <View className="flex-1 flex-row items-center gap-2">
          <Ionicons name={CAT_ICON[item.category] ?? "ellipse-outline"} size={18} color="#475569" />
          <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={2}>
            {item.title}
          </Text>
        </View>
        <View className={cn("rounded-full px-2 py-0.5", s.chip)}>
          <Text className={cn("text-[11px] font-semibold", s.chipText)}>{s.label}</Text>
        </View>
      </View>
      <Text className="mt-1.5 text-sm text-slate-600">{item.description}</Text>
      {item.teacher_name ? (
        <Text className="mt-1 text-xs text-slate-400">Sorumlu koç: {item.teacher_name}</Text>
      ) : null}
      {item.suggestion ? (
        <View className="mt-2 rounded-lg bg-slate-50 px-3 py-2">
          <Text className="text-[11px] font-semibold text-slate-500">Öneri</Text>
          <Text className="text-xs text-slate-600">{item.suggestion}</Text>
        </View>
      ) : null}
    </View>
  );
}

export function ActionCenterView({
  data,
  refreshing = false,
  onRefresh,
}: {
  data: ActionCenterResponse;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const s = data.summary;
  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-4 gap-4"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined}
    >
      <DemoHint contextKey="analysis" role="institution_admin" />
      <View className="flex-row gap-3">
        <View className="flex-1 rounded-2xl border border-slate-200 bg-white p-3">
          <Text className="text-2xl font-extrabold text-rose-600">{s.critical}</Text>
          <Text className="text-[11px] text-slate-400">Kritik</Text>
        </View>
        <View className="flex-1 rounded-2xl border border-slate-200 bg-white p-3">
          <Text className="text-2xl font-extrabold text-amber-600">{s.warn}</Text>
          <Text className="text-[11px] text-slate-400">Uyarı</Text>
        </View>
        <View className="flex-1 rounded-2xl border border-slate-200 bg-white p-3">
          <Text className="text-2xl font-extrabold text-sky-600">{s.info}</Text>
          <Text className="text-[11px] text-slate-400">Bilgi</Text>
        </View>
      </View>

      {data.items.length === 0 ? (
        <View className="mt-8 items-center gap-2 px-6">
          <Ionicons name="checkmark-circle-outline" size={44} color="#10b981" />
          <Text className="text-center text-base font-semibold text-slate-700">Her şey yolunda</Text>
          <Text className="text-center text-sm text-slate-500">Şu an dikkat gerektiren bir durum yok.</Text>
        </View>
      ) : (
        <View className="gap-2.5">
          {data.items.map((it, i) => (
            <Card key={`${it.category}-${i}`} item={it} />
          ))}
        </View>
      )}
    </ScrollView>
  );
}
