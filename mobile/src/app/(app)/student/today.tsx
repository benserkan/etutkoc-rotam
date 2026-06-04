import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { TodayView } from "@/components/student/today-view";
import {
  completeTask,
  getStudentDay,
  studentKeys,
  uncompleteTask,
  type StudentTask,
} from "@/lib/student";

export default function TodayScreen() {
  const qc = useQueryClient();
  const dayQ = useQuery({ queryKey: studentKeys.day(), queryFn: () => getStudentDay() });
  const [busyId, setBusyId] = React.useState<number | null>(null);

  const toggle = useMutation({
    mutationFn: async (task: StudentTask) => {
      const done =
        task.status === "completed" ||
        (task.planned_count > 0 && task.completed_count >= task.planned_count);
      return done ? uncompleteTask(task.id) : completeTask(task.id);
    },
    onMutate: (task) => setBusyId(task.id),
    onSettled: async () => {
      setBusyId(null);
      await qc.invalidateQueries({ queryKey: studentKeys.day() });
    },
  });

  if (dayQ.isLoading) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }

  if (dayQ.isError || !dayQ.data) {
    return (
      <View className="flex-1 items-center justify-center gap-3 bg-slate-50 px-8">
        <Text className="text-center text-base font-semibold text-slate-700">
          Bugünün programı yüklenemedi
        </Text>
        <Text className="text-center text-sm text-slate-500">İnternet bağlantını kontrol et.</Text>
        <Pressable
          onPress={() => dayQ.refetch()}
          className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
        >
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <TodayView
      day={dayQ.data}
      busyTaskId={busyId}
      onToggle={(t) => toggle.mutate(t)}
      refreshing={dayQ.isRefetching}
      onRefresh={() => dayQ.refetch()}
    />
  );
}
