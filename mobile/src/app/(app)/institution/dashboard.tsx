import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { InstitutionDashboardView } from "@/components/institution/dashboard-view";
import { getInstitutionDashboard, institutionKeys } from "@/lib/institution";

export default function InstitutionDashboardScreen() {
  const q = useQuery({ queryKey: institutionKeys.dashboard, queryFn: getInstitutionDashboard });

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <InstitutionDashboardView
          data={q.data}
          refreshing={q.isRefetching}
          onRefresh={() => q.refetch()}
          onOpenTeacher={(id) => router.push({ pathname: "/institution-teacher", params: { id: String(id) } })}
        />
      )}
    </SafeAreaView>
  );
}
