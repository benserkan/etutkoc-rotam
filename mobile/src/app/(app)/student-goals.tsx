import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GoalsView } from "@/components/student/goals-view";
import {
  createGoal,
  getStudentGoals,
  studentDevKeys,
  toggleGoal,
  updateGoalProgress,
  type GoalCreateBody,
} from "@/lib/student";

export default function StudentGoalsRoute() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: studentDevKeys.goals, queryFn: getStudentGoals });

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["student", "goals"] });
  }
  const createMut = useMutation({ mutationFn: (b: GoalCreateBody) => createGoal(b), onSuccess: invalidate });
  const progressMut = useMutation({ mutationFn: (v: { id: number; value: number }) => updateGoalProgress(v.id, v.value), onSuccess: invalidate });
  const toggleMut = useMutation({ mutationFn: (id: number) => toggleGoal(id, true), onSuccess: invalidate });

  const busy = createMut.isPending || progressMut.isPending || toggleMut.isPending;

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-200" accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Hedeflerim</Text>
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center"><ActivityIndicator size="large" color="#0e7490" /></View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <GoalsView
          data={q.data}
          busy={busy}
          onCreate={(b) => createMut.mutate(b)}
          onProgress={(id, value) => progressMut.mutate({ id, value })}
          onAchieve={(id) => toggleMut.mutate(id)}
          refreshing={q.isRefetching}
          onRefresh={() => q.refetch()}
        />
      )}
    </SafeAreaView>
  );
}
