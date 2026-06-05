import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { SupportThreadView } from "@/components/support/support-thread-view";
import {
  getSupportRequest,
  replySupportRequest,
  resolveSupportRequest,
  reviewSupportRequest,
  supportKeys,
  withdrawSupportRequest,
} from "@/lib/support";

const TERMINAL = ["resolved", "withdrawn"];

export default function SupportThreadRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const reqId = id ? Number(id) : 0;
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: supportKeys.detail(reqId),
    queryFn: () => getSupportRequest(reqId),
    enabled: reqId > 0,
  });

  function invalidate() {
    qc.invalidateQueries({ queryKey: supportKeys.detail(reqId) });
    qc.invalidateQueries({ queryKey: supportKeys.mine });
    qc.invalidateQueries({ queryKey: supportKeys.inbox });
  }

  const replyMut = useMutation({ mutationFn: (body: string) => replySupportRequest(reqId, body), onSuccess: invalidate });
  const withdrawMut = useMutation({ mutationFn: () => withdrawSupportRequest(reqId), onSuccess: invalidate });
  const reviewMut = useMutation({ mutationFn: () => reviewSupportRequest(reqId), onSuccess: invalidate });
  const resolveMut = useMutation({ mutationFn: () => resolveSupportRequest(reqId), onSuccess: invalidate });

  const busy = replyMut.isPending || withdrawMut.isPending || reviewMut.isPending || resolveMut.isPending;

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
        <Text className="text-base font-semibold text-slate-800">Talep</Text>
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
        <SupportThreadView
          data={q.data}
          busy={busy}
          isTerminal={TERMINAL.includes(q.data.status)}
          onReply={(body) => replyMut.mutate(body)}
          onWithdraw={() => withdrawMut.mutate()}
          onReview={() => reviewMut.mutate()}
          onResolve={() => resolveMut.mutate()}
        />
      )}
    </SafeAreaView>
  );
}
