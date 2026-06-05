import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CoachDnaView, CoachFocusView, CoachGoalsView, CoachReviewView } from "@/components/teacher/coach-dev-views";
import {
  createTeacherGoal,
  getTeacherStudentDna,
  getTeacherStudentFocus,
  getTeacherStudentGoals,
  getTeacherStudentReview,
  seedTeacherReview,
  teacherDevKeys,
  type TeacherGoalCreateBody,
} from "@/lib/teacher";
import { cn } from "@/lib/utils";

type Tab = "dna" | "odak" | "tekrar" | "hedef";
const TABS: { key: Tab; label: string }[] = [
  { key: "dna", label: "DNA" },
  { key: "odak", label: "Odak" },
  { key: "tekrar", label: "Tekrar" },
  { key: "hedef", label: "Hedef" },
];

function ErrorBox({ onRetry }: { onRetry: () => void }) {
  return (
    <View className="items-center gap-3 py-12 px-8">
      <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
      <Pressable onPress={onRetry} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
        <Text className="font-semibold text-white">Tekrar dene</Text>
      </Pressable>
    </View>
  );
}
function Loading() {
  return <View className="items-center py-16"><ActivityIndicator size="large" color="#0e7490" /></View>;
}

export default function TeacherStudentDevRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const sid = id ? Number(id) : 0;
  const qc = useQueryClient();
  const [tab, setTab] = React.useState<Tab>("dna");

  const dnaQ = useQuery({ queryKey: teacherDevKeys.dna(sid), queryFn: () => getTeacherStudentDna(sid), enabled: sid > 0 && tab === "dna" });
  const focusQ = useQuery({ queryKey: teacherDevKeys.focus(sid), queryFn: () => getTeacherStudentFocus(sid), enabled: sid > 0 && tab === "odak" });
  const reviewQ = useQuery({ queryKey: teacherDevKeys.review(sid), queryFn: () => getTeacherStudentReview(sid), enabled: sid > 0 && tab === "tekrar" });
  const goalsQ = useQuery({ queryKey: teacherDevKeys.goals(sid), queryFn: () => getTeacherStudentGoals(sid), enabled: sid > 0 && tab === "hedef" });

  const goalMut = useMutation({
    mutationFn: (b: TeacherGoalCreateBody) => createTeacherGoal(sid, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: teacherDevKeys.goals(sid) }),
  });
  const seedMut = useMutation({
    mutationFn: (subjectId: number) => seedTeacherReview(sid, subjectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: teacherDevKeys.review(sid) }),
  });

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-200" accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Gelişim izleme</Text>
      </View>

      <View className="flex-row gap-1 border-b border-slate-200 px-3">
        {TABS.map((t) => {
          const active = t.key === tab;
          return (
            <Pressable key={t.key} onPress={() => setTab(t.key)} className="flex-1 items-center py-2.5">
              <Text className={cn("text-sm font-semibold", active ? "text-brand-700" : "text-slate-400")}>{t.label}</Text>
              <View className={cn("mt-2 h-0.5 w-full rounded-full", active ? "bg-brand-600" : "bg-transparent")} />
            </Pressable>
          );
        })}
      </View>

      <ScrollView className="flex-1" contentContainerClassName="px-4 py-4">
        {tab === "dna" ? (
          dnaQ.isLoading ? <Loading /> : dnaQ.isError || !dnaQ.data ? <ErrorBox onRetry={() => dnaQ.refetch()} /> : <CoachDnaView d={dnaQ.data} />
        ) : tab === "odak" ? (
          focusQ.isLoading ? <Loading /> : focusQ.isError || !focusQ.data ? <ErrorBox onRetry={() => focusQ.refetch()} /> : <CoachFocusView d={focusQ.data} />
        ) : tab === "tekrar" ? (
          reviewQ.isLoading ? <Loading /> : reviewQ.isError || !reviewQ.data ? <ErrorBox onRetry={() => reviewQ.refetch()} /> : (
            <CoachReviewView d={reviewQ.data} busy={seedMut.isPending} onSeed={(s) => seedMut.mutate(s)} />
          )
        ) : (
          goalsQ.isLoading ? <Loading /> : goalsQ.isError || !goalsQ.data ? <ErrorBox onRetry={() => goalsQ.refetch()} /> : (
            <CoachGoalsView d={goalsQ.data} busy={goalMut.isPending} onCreate={(b) => goalMut.mutate(b)} />
          )
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
