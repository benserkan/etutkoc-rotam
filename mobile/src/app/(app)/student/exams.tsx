import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { ExamsView } from "@/components/student/exams-view";
import { getStudentExams, studentKeys } from "@/lib/student";

export default function StudentExamsScreen() {
  const q = useQuery({ queryKey: studentKeys.exams(), queryFn: getStudentExams });

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
        <Text className="text-center text-base font-semibold text-slate-700">Denemeler yüklenemedi</Text>
        <Pressable
          onPress={() => q.refetch()}
          className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
        >
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }
  return <ExamsView data={q.data} refreshing={q.isRefetching} onRefresh={() => q.refetch()} />;
}
