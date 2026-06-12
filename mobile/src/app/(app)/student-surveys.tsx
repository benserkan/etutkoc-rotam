import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { getStudentSurveys, surveyKeys, type SurveyAssignmentRow } from "@/lib/surveys";

/** Öğrenci — Anketlerim listesi (bekleyen + tamamlanan). */
export default function StudentSurveysRoute() {
  const q = useQuery({ queryKey: surveyKeys.studentList, queryFn: getStudentSurveys });

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
        <Text className="text-base font-semibold text-slate-800">Anketlerim</Text>
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
        <ScrollView
          className="flex-1"
          contentContainerClassName="px-4 py-3 gap-3"
          refreshControl={
            <RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor="#0e7490" />
          }
        >
          <Text className="text-xs leading-5 text-slate-500">
            Koçunun gönderdiği tanıma anketleri. Doğru ya da yanlış cevap yok —
            seni en iyi anlatan seçeneği işaretle.
          </Text>

          <Text className="mt-1 text-xs font-bold uppercase tracking-wide text-slate-500">
            Seni bekleyenler
          </Text>
          {q.data.pending.length === 0 ? (
            <View className="rounded-2xl border border-slate-200 bg-white p-4">
              <Text className="text-sm text-slate-400">Şu an bekleyen anket yok.</Text>
            </View>
          ) : (
            q.data.pending.map((a) => <SurveyRow key={a.id} row={a} />)
          )}

          {q.data.completed.length > 0 ? (
            <>
              <Text className="mt-2 text-xs font-bold uppercase tracking-wide text-slate-500">
                Tamamladıkların
              </Text>
              {q.data.completed.map((a) => (
                <SurveyRow key={a.id} row={a} done />
              ))}
            </>
          ) : null}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

function SurveyRow({ row, done }: { row: SurveyAssignmentRow; done?: boolean }) {
  const started = row.status === "in_progress";
  return (
    <Pressable
      onPress={() => router.push({ pathname: "/student-survey-fill", params: { id: String(row.id) } })}
      className="flex-row items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3.5 active:bg-slate-100"
    >
      <Ionicons
        name={done ? "checkmark-circle" : "time-outline"}
        size={22}
        color={done ? "#059669" : "#d97706"}
      />
      <View className="flex-1">
        <Text className="text-[14px] font-semibold text-slate-900" numberOfLines={1}>
          {row.template.title}
        </Text>
        <Text className="mt-0.5 text-xs text-slate-500">
          {done
            ? "Tamamlandı — sonucunu gör"
            : started
              ? `Devam ediyor · ${row.answered_count}/${row.template.question_count} soru`
              : `${row.template.question_count} soru · ~${row.template.estimated_minutes} dk`}
        </Text>
        {!done && row.note ? (
          <View className="mt-1.5 rounded-lg border border-cyan-200 bg-cyan-50 px-2 py-1">
            <Text className="text-[11px] text-cyan-900">Koçundan not: {row.note}</Text>
          </View>
        ) : null}
      </View>
      <Ionicons name="chevron-forward" size={18} color="#94a3b8" />
    </Pressable>
  );
}
