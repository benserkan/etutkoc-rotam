import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { ParentDashboardView } from "@/components/parent/dashboard-view";
import { getParentDashboard, parentKeys } from "@/lib/parent";

export default function ParentDashboardScreen() {
  const q = useQuery({ queryKey: parentKeys.dashboard(), queryFn: getParentDashboard });

  if (q.isLoading) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }
  if (q.isError || !q.data) {
    return (
      <View className="flex-1 items-center justify-center gap-3 bg-slate-50 px-8">
        <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
        <Pressable
          onPress={() => q.refetch()}
          className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
        >
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }
  return (
    <ParentDashboardView
      children={q.data.children}
      onOpenChild={(id) => router.push({ pathname: "/parent/child", params: { id: String(id) } })}
      refreshing={q.isRefetching}
      onRefresh={() => q.refetch()}
    />
  );
}
