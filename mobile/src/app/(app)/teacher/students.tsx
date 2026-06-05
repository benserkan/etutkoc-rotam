import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { StudentsListView } from "@/components/teacher/students-list-view";
import { getTeacherStudents, teacherKeys } from "@/lib/teacher";

export default function TeacherStudentsScreen() {
  const q = useQuery({ queryKey: teacherKeys.students(), queryFn: () => getTeacherStudents() });

  if (q.isLoading) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }
  if (q.isError || !q.data) {
    return (
      <View className="flex-1 items-center justify-center gap-3 bg-slate-50 px-8">
        <Text className="text-center text-base font-semibold text-slate-700">Öğrenciler yüklenemedi</Text>
        <Pressable
          onPress={() => q.refetch()}
          className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
        >
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }
  return (
    <StudentsListView
      items={q.data.items}
      onOpenStudent={(id) => router.push({ pathname: "/teacher-student", params: { id: String(id) } })}
      refreshing={q.isRefetching}
      onRefresh={() => q.refetch()}
    />
  );
}
