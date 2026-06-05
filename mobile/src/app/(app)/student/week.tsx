import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { WeekView } from "@/components/student/week-view";
import { getStudentWeek, studentKeys } from "@/lib/student";

export default function StudentWeekScreen() {
  const [start, setStart] = React.useState<string | undefined>(undefined);
  const weekQ = useQuery({ queryKey: studentKeys.week(start), queryFn: () => getStudentWeek(start) });

  if (weekQ.isLoading) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }

  if (weekQ.isError || !weekQ.data) {
    return (
      <View className="flex-1 items-center justify-center gap-3 bg-slate-50 px-8">
        <Text className="text-center text-base font-semibold text-slate-700">Hafta yüklenemedi</Text>
        <Pressable
          onPress={() => weekQ.refetch()}
          className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
        >
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }

  const week = weekQ.data;
  return (
    <WeekView
      week={week}
      onPrev={() => setStart(week.prev_start)}
      onNext={() => setStart(week.next_start)}
      onThisWeek={() => setStart(undefined)}
      onOpenDay={(date) => router.push({ pathname: "/day", params: { date } })}
      refreshing={weekQ.isRefetching}
      onRefresh={() => weekQ.refetch()}
    />
  );
}
