import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { getStudentPool, poolKeys } from "@/lib/pool";

/**
 * Bugün ekranı üst kartı — yalnız haftalık havuz modundaki öğrencide görünür.
 * Gün-gün öğrencisinde hiçbir şey çizmez (mode != havuz).
 */
export function PoolBanner() {
  const q = useQuery({ queryKey: poolKeys.pool, queryFn: getStudentPool, staleTime: 30_000 });
  const d = q.data;
  if (!d || d.mode !== "havuz") return null;
  const s = d.summary;
  const openCup = d.cup.filter((c) => c.status !== "completed").length;
  return (
    <Pressable onPress={() => router.push("/student-pool")} className="rounded-2xl border border-brand-200 bg-brand-50 p-4 active:bg-brand-100">
      <View className="flex-row items-center justify-between">
        <Text className="text-sm font-semibold text-brand-900">Haftanın havuzu</Text>
        <Ionicons name="chevron-forward" size={18} color="#0e7490" />
      </View>
      {s ? (
        <Text className="mt-0.5 text-xs text-brand-800">
          %{s.pct} bitti · seansa {s.days_left} gün · bugün kabında {openCup} açık kalem
        </Text>
      ) : (
        <Text className="mt-0.5 text-xs text-brand-800">Rehberin haftanın havuzunu seansta yazacak.</Text>
      )}
      {s && openCup === 0 ? (
        <Text className="mt-1 text-xs font-medium text-brand-900">Bugün havuzdan ne alıyorsun? →</Text>
      ) : null}
    </Pressable>
  );
}
