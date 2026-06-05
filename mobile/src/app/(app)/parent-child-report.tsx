import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ParentChildReportView } from "@/components/parent/child-report-view";
import { getParentWeeklyReport, parentKeys } from "@/lib/parent";
import { cn } from "@/lib/utils";

const TR_MONTHS_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}
function mondayOfToday(): string {
  const d = new Date();
  const dow = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - dow);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function ParentChildReportRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const childId = id ? Number(id) : 0;
  // null = backend varsayılanı (son tamamlanmış hafta)
  const [weekStart, setWeekStart] = useState<string | null>(null);

  const q = useQuery({
    queryKey: parentKeys.weeklyReport(childId, weekStart),
    queryFn: () => getParentWeeklyReport(childId, weekStart),
    enabled: childId > 0,
  });

  const data = q.data;
  const canNext = data ? data.start < mondayOfToday() : false;

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
        <Text className="text-base font-semibold text-slate-800">Haftalık rapor</Text>
      </View>

      {/* Hafta gezgini */}
      {data ? (
        <View className="mx-4 mb-2 flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-2 py-1.5">
          <Pressable
            onPress={() => setWeekStart(data.prev_start)}
            hitSlop={6}
            className="flex-row items-center gap-0.5 rounded-lg px-2 py-1.5 active:bg-slate-100"
          >
            <Ionicons name="chevron-back" size={18} color="#0e7490" />
            <Text className="text-xs font-medium text-brand-700">Önceki</Text>
          </Pressable>
          <Text className="text-sm font-semibold text-slate-700">
            {shortDate(data.start)} – {shortDate(data.end)}
          </Text>
          <Pressable
            onPress={() => canNext && setWeekStart(data.next_start)}
            disabled={!canNext}
            hitSlop={6}
            className={cn("flex-row items-center gap-0.5 rounded-lg px-2 py-1.5", canNext ? "active:bg-slate-100" : "opacity-30")}
          >
            <Text className="text-xs font-medium text-brand-700">Sonraki</Text>
            <Ionicons name="chevron-forward" size={18} color="#0e7490" />
          </Pressable>
        </View>
      ) : null}

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <ParentChildReportView report={data} refreshing={q.isRefetching} onRefresh={() => q.refetch()} />
      )}
    </SafeAreaView>
  );
}
