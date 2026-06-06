import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CoachDnaView, CoachFocusView, CoachGoalsView, CoachInsightView, CoachReviewView } from "@/components/teacher/coach-dev-views";
import { ApiError } from "@/lib/api";
import {
  createTeacherGoal,
  generateTeacherCoachingInsight,
  getTeacherAiConsent,
  getTeacherCoachingInsight,
  getTeacherStudentDna,
  getTeacherStudentFocus,
  getTeacherStudentGoals,
  getTeacherStudentReview,
  seedTeacherReview,
  setTeacherAiConsent,
  teacherDevKeys,
  type TeacherGoalCreateBody,
} from "@/lib/teacher";
import { cn } from "@/lib/utils";

type Tab = "dna" | "odak" | "tekrar" | "hedef" | "icgoru";
const TABS: { key: Tab; label: string }[] = [
  { key: "dna", label: "DNA" },
  { key: "odak", label: "Odak" },
  { key: "tekrar", label: "Tekrar" },
  { key: "hedef", label: "Hedef" },
  { key: "icgoru", label: "İçgörü" },
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

  // AI Koçluk İçgörüsü (GET ücretsiz · POST kredi · rıza + ücretli kapı)
  const insightQ = useQuery({ queryKey: teacherDevKeys.insight(sid), queryFn: () => getTeacherCoachingInsight(sid), enabled: sid > 0 && tab === "icgoru" });
  const consentQ = useQuery({ queryKey: teacherDevKeys.aiConsent, queryFn: getTeacherAiConsent, enabled: sid > 0 && tab === "icgoru" });

  const genMut = useMutation({
    mutationFn: () => generateTeacherCoachingInsight(sid),
    onSuccess: (data) => qc.setQueryData(teacherDevKeys.insight(sid), data),
    onError: (e) => {
      const code = e instanceof ApiError ? e.code : null;
      if (code === "plan_upgrade_required") Alert.alert("Ücretli pakette", "Yapay zekâ içgörüsü ücretli pakette açıktır. Profil → Paketim'den yükseltebilirsin.");
      else if (code === "ai_credit_exhausted") Alert.alert("Kredi bitti", "Bu ay yapay zekâ kredin doldu. Kesintisiz devam için paketini yükselt.");
      else if (code === "not_enough_data") Alert.alert("Seans gerekli", "İçgörü için en az bir seans kaydı gerekir. Önce 'Seanslar' sekmesinden seans ekle.");
      else if (code === "ai_unavailable") Alert.alert("Yapay zekâ şu an kullanılamıyor", "Lütfen birkaç dakika sonra tekrar dene.");
      else Alert.alert("Oluşturulamadı", e instanceof ApiError ? e.message : "İşlem başarısız.");
    },
  });

  const consentMut = useMutation({
    mutationFn: setTeacherAiConsent,
    onSuccess: () => { qc.invalidateQueries({ queryKey: teacherDevKeys.aiConsent }); genMut.mutate(); },
    onError: (e) => Alert.alert("Hata", e instanceof ApiError ? e.message : "Onay kaydedilemedi."),
  });

  function onGenerateInsight() {
    const c = consentQ.data;
    if (c && !c.ai_premium) {
      Alert.alert("Ücretli pakette", "Yapay zekâ içgörüsü ücretli pakette açıktır. Profil → Paketim'den yükseltebilirsin.");
      return;
    }
    if (c && !c.consented) {
      Alert.alert(
        "Yapay zekâ onayı",
        "Öğrenci seans notların yapay zekâ ile işlenir (yurt dışı işleyici dahil). Veriler işlendikten sonra saklanmaz; içgörüyü yalnız sen görürsün. Onaylıyor musun?",
        [
          { text: "Vazgeç", style: "cancel" },
          { text: "Onayla", onPress: () => consentMut.mutate() },
        ],
      );
      return;
    }
    genMut.mutate();
  }
  const insightBusy = genMut.isPending || consentMut.isPending;

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
        ) : tab === "hedef" ? (
          goalsQ.isLoading ? <Loading /> : goalsQ.isError || !goalsQ.data ? <ErrorBox onRetry={() => goalsQ.refetch()} /> : (
            <CoachGoalsView d={goalsQ.data} busy={goalMut.isPending} onCreate={(b) => goalMut.mutate(b)} />
          )
        ) : (
          insightQ.isLoading ? <Loading /> : insightQ.isError || !insightQ.data ? <ErrorBox onRetry={() => insightQ.refetch()} /> : (
            <CoachInsightView cache={insightQ.data} busy={insightBusy} onGenerate={onGenerateInsight} />
          )
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
