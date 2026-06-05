import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ExamsTab } from "@/components/teacher/exams-tab";
import { SessionsTab } from "@/components/teacher/sessions-tab";
import { StudentDetailView } from "@/components/teacher/student-detail-view";
import { getTeacherStudent, teacherKeys } from "@/lib/teacher";
import { cn } from "@/lib/utils";

type Tab = "genel" | "denemeler" | "seanslar";
const TABS: { key: Tab; label: string }[] = [
  { key: "genel", label: "Genel" },
  { key: "denemeler", label: "Denemeler" },
  { key: "seanslar", label: "Seanslar" },
];

export default function TeacherStudentRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const studentId = id ? Number(id) : 0;
  const [tab, setTab] = React.useState<Tab>("genel");

  const q = useQuery({
    queryKey: teacherKeys.student(studentId),
    queryFn: () => getTeacherStudent(studentId),
    enabled: studentId > 0,
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
        <Text className="text-base font-semibold text-slate-800" numberOfLines={1}>
          {q.data?.student.full_name ?? "Öğrenci"}
        </Text>
      </View>

      {/* Sekmeler */}
      <View className="flex-row gap-1 border-b border-slate-200 px-3">
        {TABS.map((t) => {
          const active = t.key === tab;
          return (
            <Pressable key={t.key} onPress={() => setTab(t.key)} className="flex-1 items-center py-2.5">
              <Text className={cn("text-sm font-semibold", active ? "text-brand-700" : "text-slate-400")}>
                {t.label}
              </Text>
              <View className={cn("mt-2 h-0.5 w-full rounded-full", active ? "bg-brand-600" : "bg-transparent")} />
            </Pressable>
          );
        })}
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
      ) : tab === "genel" ? (
        <StudentDetailView data={q.data} />
      ) : tab === "denemeler" ? (
        <ScrollView className="flex-1 bg-slate-50">
          <ExamsTab studentId={studentId} />
        </ScrollView>
      ) : (
        <ScrollView className="flex-1 bg-slate-50">
          <SessionsTab studentId={studentId} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
