import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { PlanView } from "@/components/teacher/plan-view";
import { ApiError } from "@/lib/api";
import { getTeacherPlan, requestTeacherSubscription, teacherMiscKeys, upgradeTeacherPlan } from "@/lib/teacher";

export default function TeacherPlanRoute() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: teacherMiscKeys.plan, queryFn: getTeacherPlan });

  const upMut = useMutation({
    mutationFn: (plan: string) => upgradeTeacherPlan(plan),
    onSuccess: () => qc.invalidateQueries({ queryKey: teacherMiscKeys.plan }),
    onError: (e) => {
      const msg = e instanceof ApiError ? e.message : "İşlem başarısız";
      Alert.alert("İşlem başarısız", msg);
    },
  });

  const subMut = useMutation({
    mutationFn: (v: { plan: string; cycle: string }) => requestTeacherSubscription(v.plan, v.cycle),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: teacherMiscKeys.plan });
      Alert.alert(res.already_pending ? "Talebin zaten alınmış" : "Talebin alındı", res.message);
    },
    onError: (e) => {
      const msg = e instanceof ApiError ? e.message : "İşlem başarısız";
      Alert.alert("İşlem başarısız", msg);
    },
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
        <Text className="text-base font-semibold text-slate-800">Paketim</Text>
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
        <PlanView
          data={q.data}
          busy={upMut.isPending || subMut.isPending}
          onUpgrade={(code) => upMut.mutate(code)}
          onRequestSubscription={(plan, cycle) => subMut.mutate({ plan, cycle })}
          refreshing={q.isRefetching}
          onRefresh={() => q.refetch()}
        />
      )}
    </SafeAreaView>
  );
}
