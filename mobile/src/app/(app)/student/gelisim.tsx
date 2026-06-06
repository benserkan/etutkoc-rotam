import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DevHubView } from "@/components/student/dev-hub-view";
import {
  getStudentDna,
  getStudentFocus,
  getStudentGoals,
  getStudentReview,
  studentDevKeys,
} from "@/lib/student";

export default function StudentGelisimScreen() {
  const dna = useQuery({ queryKey: studentDevKeys.dna, queryFn: getStudentDna });
  const focus = useQuery({ queryKey: studentDevKeys.focus, queryFn: getStudentFocus });
  const review = useQuery({ queryKey: studentDevKeys.review, queryFn: getStudentReview });
  const goals = useQuery({ queryKey: studentDevKeys.goals, queryFn: getStudentGoals });

  const loading = dna.isLoading || focus.isLoading || review.isLoading || goals.isLoading;
  const ready = dna.data && focus.data && review.data && goals.data;
  const refreshing = dna.isRefetching || focus.isRefetching || review.isRefetching || goals.isRefetching;

  function refetchAll() {
    void dna.refetch(); void focus.refetch(); void review.refetch(); void goals.refetch();
  }

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="px-5 pb-1 pt-3">
        <Text className="text-2xl font-extrabold text-slate-900">Gelişimim</Text>
      </View>
      {loading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : !ready ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={refetchAll} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <DevHubView
          dna={dna.data!}
          focus={focus.data!}
          review={review.data!}
          goals={goals.data!}
          onOpenBooks={() => router.push("/student-books")}
          onOpenTopics={() => router.push({ pathname: "/topic-performance", params: { source: "student" } })}
          onOpenFocus={() => router.push("/student-focus")}
          onOpenReview={() => router.push("/student-review")}
          onOpenGoals={() => router.push("/student-goals")}
          refreshing={refreshing}
          onRefresh={refetchAll}
        />
      )}
    </SafeAreaView>
  );
}
