import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { NotificationsView } from "@/components/parent/notifications-view";
import { getParentNotifications, parentKeys } from "@/lib/parent";

export default function ParentNotificationsScreen() {
  const q = useQuery({ queryKey: parentKeys.notifications(), queryFn: getParentNotifications });

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Bildirimler yüklenemedi</Text>
          <Pressable
            onPress={() => q.refetch()}
            className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
          >
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <NotificationsView data={q.data} refreshing={q.isRefetching} onRefresh={() => q.refetch()} />
      )}
    </SafeAreaView>
  );
}
