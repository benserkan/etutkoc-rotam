import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { RequestsView } from "@/components/student/requests-view";
import { getStudentRequests, studentKeys, withdrawRequest } from "@/lib/student";

export default function RequestsRoute() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: studentKeys.requests(), queryFn: () => getStudentRequests() });
  const [busy, setBusy] = React.useState(false);

  async function onWithdraw(id: number) {
    setBusy(true);
    try {
      await withdrawRequest(id);
      await qc.invalidateQueries({ queryKey: ["student"] });
    } catch {
      // sessiz geç
    } finally {
      setBusy(false);
    }
  }

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
        <Text className="text-base font-semibold text-slate-800">Taleplerim</Text>
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Talepler yüklenemedi</Text>
          <Pressable
            onPress={() => q.refetch()}
            className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
          >
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <RequestsView
          data={q.data}
          busy={busy}
          onWithdraw={onWithdraw}
          refreshing={q.isRefetching}
          onRefresh={() => q.refetch()}
        />
      )}
    </SafeAreaView>
  );
}
