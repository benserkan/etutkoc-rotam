import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ActionCenterView } from "@/components/institution/action-center-view";
import { getInstitutionActionCenter, institutionKeys } from "@/lib/institution";

export default function InstitutionActionCenterScreen() {
  const q = useQuery({ queryKey: institutionKeys.actionCenter, queryFn: getInstitutionActionCenter });

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="px-5 pb-1 pt-3">
        <Text className="text-2xl font-extrabold text-slate-900">Müdahale Merkezi</Text>
      </View>
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
        <ActionCenterView data={q.data} refreshing={q.isRefetching} onRefresh={() => q.refetch()} />
      )}
    </SafeAreaView>
  );
}
