import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ParentChildDetailView } from "@/components/parent/child-detail-view";
import { parentKeys } from "@/lib/parent";
import { getParentChild } from "@/lib/parent-detail";

export default function ParentChildRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const childId = id ? Number(id) : 0;
  const q = useQuery({
    queryKey: parentKeys.child(childId),
    queryFn: () => getParentChild(childId),
    enabled: childId > 0,
  });

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
        <Text className="text-base font-semibold text-slate-800">{q.data?.student.full_name ?? "Öğrenci"}</Text>
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable
            onPress={() => q.refetch()}
            className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
          >
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <ParentChildDetailView data={q.data} />
      )}
    </SafeAreaView>
  );
}
