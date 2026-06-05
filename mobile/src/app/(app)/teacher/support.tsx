import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { SupportListView } from "@/components/support/support-list-view";
import {
  createSupportRequest,
  getMyRequests,
  getSupportInbox,
  supportKeys,
} from "@/lib/support";

export default function TeacherSupportScreen() {
  const qc = useQueryClient();
  const [view, setView] = React.useState<"mine" | "inbox">("mine");

  const mine = useQuery({ queryKey: supportKeys.mine, queryFn: getMyRequests });
  const inbox = useQuery({ queryKey: supportKeys.inbox, queryFn: getSupportInbox });

  const createMut = useMutation({
    mutationFn: (body: { category: string; subject: string; body: string }) => createSupportRequest(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: supportKeys.mine }),
  });

  const active = view === "mine" ? mine : inbox;
  const showInbox = (inbox.data?.items.length ?? 0) > 0;

  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <View className="px-5 pb-1 pt-3">
        <Text className="text-2xl font-extrabold text-slate-900">Destek</Text>
      </View>
      {active.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : active.isError || !active.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => active.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView className="flex-1">
          <SupportListView
            view={view}
            onChangeView={setView}
            showInbox={showInbox}
            data={active.data}
            createBusy={createMut.isPending}
            onCreate={(b) => createMut.mutate(b)}
            onOpen={(id) => router.push({ pathname: "/support-thread", params: { id: String(id) } })}
          />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
