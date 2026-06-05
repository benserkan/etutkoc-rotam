import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { RequestsView } from "@/components/student/requests-view";
import { getStudentRequests, studentKeys, withdrawRequest } from "@/lib/student";

/** Öğrenci "Talepler" sekmesi — koça gönderilen istekler (görüntüle + geri çek). */
export default function StudentRequestsTab() {
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
      <View className="px-4 py-3">
        <Text className="text-xl font-bold text-slate-900">Taleplerim</Text>
        <Text className="mt-0.5 text-xs text-slate-500">Koçuna gönderdiğin istekler ve yanıtları.</Text>
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Talepler yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
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
